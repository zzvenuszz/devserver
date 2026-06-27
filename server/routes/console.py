"""
Console Routes - API cho console và command
"""
from flask import Blueprint, jsonify, request
from server.config import state, Config
from server.services.minecraft import send_command, is_server_running, stop_server, restart_paper
from server.utils import add_log

console_bp = Blueprint('console', __name__)


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