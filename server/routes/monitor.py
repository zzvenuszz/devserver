"""
Monitor Routes - API endpoints cho dashboard monitor
"""
import threading
from flask import Blueprint, jsonify, request
from server.config import state, Config
from server.services.monitor import (
    get_monitor_stats, get_chart_data, toggle_monitor,
    set_monitor_mode, benchmark_disk_network, start_monitor_threads
)
from server.utils.persistence import (
    load_settings, save_settings, get_current_settings,
    load_benchmark_results, save_benchmark_results
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


@monitor_bp.route("/api/monitor/mode", methods=["POST"])
def api_monitor_mode():
    """Đặt chế độ monitor: on/off/auto"""
    data = request.get_json()
    mode = data.get("mode", "auto")
    result = set_monitor_mode(mode)
    return jsonify({
        "status": "success",
        "mode": result
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
        "chart_duration": Config.MONITOR_CHART_DURATION,
        "disk_max": state.disk_max_speed,
        "net_max": state.net_max_speed
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


@monitor_bp.route("/api/monitor/benchmark", methods=["POST"])
def api_benchmark():
    """Chạy benchmark disk/network"""
    # Chạy trong thread riêng để không block
    threading.Thread(target=benchmark_disk_network, daemon=True).start()
    return jsonify({"status": "success", "message": "Benchmark started"})


@monitor_bp.route("/api/settings", methods=["GET"])
def api_get_settings():
    """Lấy settings hiện tại"""
    return jsonify(get_current_settings())


@monitor_bp.route("/api/settings", methods=["POST"])
def api_update_settings():
    """Cập nhật settings"""
    data = request.get_json()
    
    try:
        # Load settings hiện tại
        settings = load_settings()
        
        # Update monitor settings
        if "monitor" in data:
            settings["monitor"].update(data["monitor"])
            
            # Áp dụng vào state
            state.monitor_mode = settings["monitor"].get("mode", "auto")
            state.monitor_track_tps = settings["monitor"].get("track_tps", True)
            state.monitor_track_players = settings["monitor"].get("track_players", True)
            state.monitor_track_cpu = settings["monitor"].get("track_cpu", True)
            state.monitor_track_ram = settings["monitor"].get("track_ram", True)
            state.monitor_track_disk = settings["monitor"].get("track_disk", True)
            state.monitor_track_network = settings["monitor"].get("track_network", True)
            
            # Nếu mode là "on", tự động bật monitor
            if state.monitor_mode == "on":
                state.monitor_enabled = True
                state.monitor_last_active = time.time()
        
        # Update theme settings
        if "theme" in data:
            settings["theme"].update(data["theme"])
            state.theme_mode = settings["theme"].get("mode", "dark")
        
        # Lưu vào file
        save_settings(settings)
        
        return jsonify({
            "status": "success",
            "settings": settings
        })
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
