"""
VnMine Panel - Entry Point
Điểm khởi chạy ứng dụng Flask
"""
import threading
import os
import time
from server import create_app
from server.services import fetch_server_info, run_paper, run_playit, monitor_java
from server.services.monitor import start_monitor_threads, benchmark_disk_network
from server.utils.persistence import load_settings, apply_settings_to_state, save_benchmark_results
from server.config import state


# Tạo Flask app
app = create_app()


# --- ĐIỀU HƯỚNG LUỒNG KHỞI ĐỘNG HỆ THỐNG ---

def start_background_services():
    """Khởi chạy các services chạy nền"""
    threading.Thread(target=fetch_server_info, daemon=True).start()
    threading.Thread(target=run_paper, daemon=True).start()
    threading.Thread(target=run_playit, daemon=True).start()
    threading.Thread(target=monitor_java, daemon=True).start()
    start_monitor_threads()
    # Chạy benchmark disk/network sau 2 giây để không block startup
    threading.Thread(target=lambda: (time.sleep(2), benchmark_disk_network()), daemon=True).start()


if __name__ == "__main__":
    # Load settings từ disk trước khi khởi chạy services
    print("[SYSTEM] Đang load settings từ /data/panel/...")
    settings = load_settings()
    apply_settings_to_state(settings)
    print(f"[SYSTEM] Settings đã được load: mode={state.monitor_mode}, theme={state.theme_mode}")
    
    # Khởi chạy background services
    start_background_services()
    
    # Chạy Flask app
    port = int(os.getenv("PORT", 7860))
    app.run(host="0.0.0.0", port=port)
