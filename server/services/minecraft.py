"""
Minecraft Server Service - Quản lý Paper Minecraft Server
"""
import os
import shutil
import subprocess
import threading
from server.config import state, Config, BASE_DATA_DIR
from server.utils import add_log


def setup_plugins_directory():
    """Thiết lập thư mục plugins với symlink"""
    persistent_plugins_dir = os.path.join(BASE_DATA_DIR, "plugins")
    if not os.path.exists(persistent_plugins_dir):
        os.makedirs(persistent_plugins_dir, exist_ok=True)

    local_plugins_dir = "plugins"
    if os.path.exists(local_plugins_dir) and not os.path.islink(local_plugins_dir):
        try:
            shutil.rmtree(local_plugins_dir)
        except Exception as e:
            add_log(f"Không thể xóa thư mục plugins cũ: {e}", "error")

    if not os.path.exists(local_plugins_dir):
        try:
            os.symlink(persistent_plugins_dir, local_plugins_dir)
            add_log("Đã liên kết thành công thư mục gốc 'plugins' vào '/data/plugins'", "system")
        except Exception as e:
            add_log(f"Lỗi tạo Symlink cho plugins: {e}", "error")


def run_paper():
    """
    Khởi chạy Paper Minecraft Server
    """
    global java_process
    
    setup_plugins_directory()

    cmd = [
        "java",
        f"-Xms{Config.MC_RAM_MIN}",
        f"-Xmx{Config.MC_RAM_MAX}",
        "-XshowSettings:vm",
        "-jar",
        Config.PAPER_JAR,
        "--config", os.path.join(BASE_DATA_DIR, "server.properties"),
        "-W",
        BASE_DATA_DIR,
        "--nogui"
    ]

    add_log("Starting Paper Minecraft Server with High-Performance Settings...", "system")

    try:
        state.java_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in state.java_process.stdout:
            from server.utils import parse_and_add_raw_log
            parse_and_add_raw_log(line)
    except Exception as e:
        add_log(f"Lỗi khởi chạy Paper Server: {e}", "error")


def send_command(cmd):
    """
    Gửi lệnh đến Minecraft Server
    
    Args:
        cmd: Lệnh cần gửi (có thể có / hoặc không)
        
    Returns:
        tuple: (success: bool, message: str)
    """
    if not state.java_process or state.java_process.poll() is not None:
        return False, "Server Minecraft hiện đang không chạy!"

    add_log(f"Execute Console Input: {cmd}", "command")
    try:
        state.java_process.stdin.write(cmd + "\n")
        state.java_process.stdin.flush()
        return True, "Thành công"
    except Exception as e:
        return False, str(e)


def is_server_running():
    """
    Kiểm tra server có đang chạy không
    
    Returns:
        bool: True nếu server đang chạy
    """
    return state.java_process is not None and state.java_process.poll() is None


def stop_server():
    """
    Gửi lệnh stop đến Minecraft Server và chờ process kết thúc
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not is_server_running():
        return False, "Server Minecraft hiện đang không chạy!"
    
    add_log("Đang dừng Minecraft Server...", "system")
    try:
        # Gửi lệnh stop
        state.java_process.stdin.write("stop\n")
        state.java_process.stdin.flush()
        
        # Chờ process kết thúc (timeout 60 giây)
        try:
            state.java_process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            state.java_process.kill()
            state.java_process.wait(timeout=5)
        
        state.java_process = None
        state.current_mc_ram = 0
        state.current_mc_cpu = 0
        state.mc_tps = 20.0
        state.mc_mspt = 0
        state.mc_players = 0
        state.mc_max_players = 0
        
        add_log("Minecraft Server đã dừng thành công.", "system")
        return True, "Server đã dừng"
    except Exception as e:
        add_log(f"Lỗi khi dừng server: {e}", "error")
        return False, str(e)


def restart_paper():
    """
    Dừng và khởi động lại Minecraft Server (không restart toàn bộ Space)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    add_log("===== KHỞI ĐỘNG LẠI MINECRAFT SERVER =====", "system")
    
    # Bước 1: Dừng server nếu đang chạy
    if is_server_running():
        success, msg = stop_server()
        if not success:
            return False, f"Lỗi khi dừng server: {msg}"
    
    # Bước 2: Chờ một chút để giải phóng port
    import time
    time.sleep(2)
    
    # Bước 3: Khởi động lại
    add_log("Đang khởi động lại Minecraft Server...", "system")
    try:
        # Khởi chạy trong thread mới để không block API
        thread = threading.Thread(target=run_paper_internal, daemon=True)
        thread.start()
        return True, "Server đang khởi động lại..."
    except Exception as e:
        add_log(f"Lỗi khi khởi động lại server: {e}", "error")
        return False, str(e)


def run_paper_internal():
    """Internal function để chạy Paper (dùng cho restart)"""
    setup_plugins_directory()
    
    cmd = [
        "java",
        f"-Xms{Config.MC_RAM_MIN}",
        f"-Xmx{Config.MC_RAM_MAX}",
        "-XshowSettings:vm",
        "-jar",
        Config.PAPER_JAR,
        "--config", os.path.join(BASE_DATA_DIR, "server.properties"),
        "-W",
        BASE_DATA_DIR,
        "--nogui"
    ]
    
    try:
        state.java_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        for line in state.java_process.stdout:
            from server.utils import parse_and_add_raw_log
            parse_and_add_raw_log(line)
    except Exception as e:
        add_log(f"Lỗi khởi chạy Paper Server: {e}", "error")