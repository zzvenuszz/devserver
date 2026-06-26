"""
Monitor Routes - API endpoints cho dashboard monitor
"""
from flask import Blueprint, jsonify, request
from server.config import state, Config
from server.services.monitor import (
    get_monitor_stats, get_chart_data, toggle_monitor,
    start_monitor_threads
)

monitor_bp = Blueprint('monitor', __name__)


@monitor_bp.route("/api/monitor/stats")
def api_monitor_stats():
    """Lấy tất cả metrics monitor hiện tại"""
    return jsonify(get_monitor_stats())


@monitor_bp.route("/api/monitor/chart")
def api_monitor_chart():
    """Lấy dữ liệu biểu đồ"""
    return jsonify(get_chart_data())


@monitor_bp.route("/api/monitor/toggle", methods=["POST"])
def api_monitor_toggle():
    """Bật/tắt monitor"""
    new_state = toggle_monitor()
    return jsonify({
        "status": "success",
        "enabled": new_state
    })


@monitor_bp.route("/api/monitor/settings", methods=["GET"])
def api_monitor_settings_get():
    """Lấy cấu hình monitor"""
    return jsonify({
        "thresholds": {
            "disk_good": Config.MONITOR_DISK_GOOD,
            "disk_warn": Config.MONITOR_DISK_WARN,
            "net_good": Config.MONITOR_NET_GOOD,
            "net_warn": Config.MONITOR_NET_WARN,
            "tps_good": Config.MONITOR_TPS_GOOD,
            "tps_warn": Config.MONITOR_TPS_WARN,
            "mspt_good": Config.MONITOR_MSPT_GOOD,
            "mspt_warn": Config.MONITOR_MSPT_WARN
        },
        "cooldown": Config.MONITOR_COOLDOWN,
        "chart_duration": Config.MONITOR_CHART_DURATION
    })


@monitor_bp.route("/api/monitor/alerts")
def api_monitor_alerts():
    """Lấy lịch sử cảnh báo"""
    return jsonify({
        "alerts": state.alert_history[-50:]  # 50 alert gần nhất
    })


@monitor_bp.route("/api/monitor/start-threads", methods=["POST"])
def api_start_threads():
    """Khởi chạy monitor threads (gọi một lần khi app start)"""
    start_monitor_threads()
    return jsonify({"status": "success", "message": "Monitor threads started"})