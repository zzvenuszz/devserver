"""
Console Routes - API cho console và command
"""
import os
from flask import Blueprint, jsonify, request
from server.config import state, Config
from server.services.minecraft import send_command, is_server_running, stop_server, restart_paper
from server.services.paper import get_paper_versions, ensure_paper_jar
from server.utils import add_log
from server.utils.persistence import load_settings, save_settings

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
            "jar": os.path.basename(jar_path),
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


@console_bp.route("/api/ping")
def api_ping():
    """Health check endpoint"""
    return jsonify({"status": "pong"})


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
