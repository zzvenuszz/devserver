"""
Console Routes - API cho console và command
"""
import json
from flask import Blueprint, Response, jsonify, request, stream_with_context
from server.config import state, Config
from server.services.minecraft import (
    send_command, is_server_running, stop_server, restart_paper,
    launch_server_from_jar,
)
from server.services.paper import get_paper_versions, ensure_paper_jar
from server.utils import add_log
from server.utils.persistence import load_settings, save_settings
from server.services.server_properties import get_server_properties, save_server_properties

console_bp = Blueprint('console', __name__)


@console_bp.route("/api/minecraft/versions")
def api_minecraft_versions():
    """Return PaperMC's currently supported Minecraft version list."""
    try:
        return jsonify({
            "status": "success",
            "versions": get_paper_versions(),
            "selected": state.minecraft_version,
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@console_bp.route("/api/minecraft/version", methods=["POST"])
def api_minecraft_version_select():
    """Persist a Paper version and make sure its server JAR is present."""
    data = request.get_json(silent=True) or {}
    version = str(data.get("version", "")).strip()
    try:
        if version not in get_paper_versions():
            return jsonify({"status": "error", "message": "Phiên bản Paper không hợp lệ hoặc không còn được hỗ trợ."}), 400

        settings = load_settings()
        settings.setdefault("minecraft", {})["version"] = version
        if not save_settings(settings):
            raise RuntimeError("Không thể lưu cài đặt phiên bản vào /data/panel/settings.json")
        state.minecraft_version = version
        jar_path = ensure_paper_jar(version)
        add_log(f"Đã chọn Paper {version}; server JAR sẵn sàng tại {jar_path}", "system")
        return jsonify({
            "status": "success",
            "version": version,
            "jar": jar_path,
            "running": is_server_running(),
            "message": "Đã tải và lưu server JAR. Hãy khởi động lại server để áp dụng phiên bản mới." if is_server_running() else "Đã tải và lưu server JAR; server sẽ dùng phiên bản này khi khởi động.",
        })
    except Exception as exc:
        add_log(f"Không thể tải Paper {version}: {exc}", "error")
        return jsonify({"status": "error", "message": str(exc)}), 502


@console_bp.route("/api/logs")
def get_logs():
    """Lấy danh sách logs gần nhất"""
    return jsonify({"logs": state.logs[-Config.LOGS_TO_RETURN:]})


@console_bp.route("/api/logs/stream")
def stream_logs():
    """Stream log entries over one Server-Sent Events connection."""
    try:
        last_event_id = max(0, int(request.headers.get("Last-Event-ID", "0")))
    except ValueError:
        last_event_id = 0

    @stream_with_context
    def generate():
        nonlocal last_event_id
        if last_event_id == 0:
            with state.logs_condition:
                snapshot = list(state.logs[-Config.LOGS_TO_RETURN:])
                last_event_id = snapshot[-1]["id"] if snapshot else state.log_sequence
            yield f"id: {last_event_id}\nevent: snapshot\ndata: {json.dumps(snapshot, ensure_ascii=False)}\n\n"

        while True:
            with state.logs_condition:
                new_entries = [entry for entry in state.logs if entry["id"] > last_event_id]
                if not new_entries:
                    state.logs_condition.wait(timeout=15)
                    new_entries = [entry for entry in state.logs if entry["id"] > last_event_id]

            if not new_entries:
                yield ": keep-alive\n\n"
                continue

            for entry in new_entries:
                last_event_id = entry["id"]
                yield f"id: {last_event_id}\ndata: {json.dumps(entry, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@console_bp.route("/api/ping")
def api_ping():
    """Health check endpoint"""
    return jsonify({"status": "pong"})


@console_bp.route("/api/server/start", methods=["POST"])
def api_start_server():
    """Start a detected server JAR from persistent /data storage."""
    success, message = launch_server_from_jar()
    return jsonify({"status": "success" if success else "error", "message": message}), (200 if success else 409)


@console_bp.route("/api/server/properties", methods=["GET", "POST"])
def api_server_properties():
    """Read or update the typed persistent server.properties settings."""
    if request.method == "GET":
        try:
            return jsonify({"status": "success", "properties": get_server_properties()})
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

    data = request.get_json(silent=True) or {}
    try:
        properties = save_server_properties(data.get("properties", []))
        add_log("Đã lưu cài đặt vào /data/server.properties.", "system")
        return jsonify({
            "status": "success",
            "properties": properties,
            "running": is_server_running(),
            "message": "Đã lưu /data/server.properties. Hãy restart server để áp dụng thay đổi.",
        })
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@console_bp.route("/api/command", methods=["POST"])
def send_command_route():
    """API gửi lệnh đến Minecraft Server"""
    raw_cmd = request.json.get("command", "").strip()
    if not raw_cmd:
        return jsonify({"status": "error", "message": "Lệnh trống"})

    # Xử lý lệnh
    if raw_cmd.startswith("/"):
        cmd = raw_cmd[1:].strip()
    else:
        mc_commands = [
            "stop", "reload", "rl", "op", "deop", "ban", "pardon", "kick", 
            "gamemode", "gm", "tp", "teleport", "give", "clear", "xp", 
            "seed", "whitelist", "list", "help", "time", "weather", 
            "gamerule", "difficulty", "say", "plugins", "pl", "version", 
            "mv", "multiverse", "tps", "save-all"
        ]
        
        first_word = raw_cmd.split(" ")[0].lower()
        if first_word in mc_commands:
            cmd = raw_cmd
        else:
            cmd = f"say {raw_cmd}"

    success, message = send_command(cmd)
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": message})


@console_bp.route("/api/server/stop", methods=["POST"])
def api_stop_server():
    """API dừng Minecraft Server"""
    success, message = stop_server()
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message})


@console_bp.route("/api/server/restart", methods=["POST"])
def api_restart_server():
    """API khởi động lại Minecraft Server (không restart toàn bộ Space)"""
    success, message = restart_paper()
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message})
