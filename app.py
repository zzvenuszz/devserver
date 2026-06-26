"""
VnMine Panel - Entry Point
Điểm khởi chạy ứng dụng Flask
"""
import threading
import os
from server import create_app
from server.services import fetch_server_info, run_paper, run_playit, monitor_java


# Tạo Flask app
app = create_app()


# --- ĐIỀU HƯỚNG LUỒNG KHỞI ĐỘNG HỆ THỐNG ---

def start_background_services():
    """Khởi chạy các services chạy nền"""
    threading.Thread(target=fetch_server_info, daemon=True).start()
    threading.Thread(target=run_paper, daemon=True).start()
    threading.Thread(target=run_playit, daemon=True).start()
    threading.Thread(target=monitor_java, daemon=True).start()


if __name__ == "__main__":
    # Khởi chạy background services
    start_background_services()
    
    # Chạy Flask app
    port = int(os.getenv("PORT", 7860))
    app.run(host="0.0.0.0", port=port)