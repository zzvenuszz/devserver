"""
Playit Tunnel Service - Quản lý Playit tunnel network
"""
import os
import subprocess
from server.config import state, Config
from server.utils import add_log


def run_playit():
    """
    Khởi chạy Playit Tunnel Network
    """
    global playit_process
    secret_key = Config.PLAYIT_SECRET_KEY

    if not secret_key:
        add_log("PLAYIT_SECRET_KEY environment variable not found", "error")
        return

    cmd = ["./playit", "--secret", secret_key]
    add_log("Starting Playit Tunnel Network...", "playit")

    try:
        state.playit_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in state.playit_process.stdout:
            from server.utils import parse_and_add_raw_log
            parse_and_add_raw_log(f"[PLAYIT] {line}")
    except Exception as e:
        add_log(f"Lỗi khởi chạy Playit: {e}", "error")


def is_playit_running():
    """
    Kiểm tra Playit có đang chạy không
    
    Returns:
        bool: True nếu Playit đang chạy
    """
    return state.playit_process is not None and state.playit_process.poll() is None