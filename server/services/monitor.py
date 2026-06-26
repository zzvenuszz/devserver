"""
Monitor Service - Giám sát tài nguyên hệ thống và Minecraft Server
"""
import time
import psutil
from server.config import state
from server.utils import add_log


def monitor_java():
    """
    Giám sát RAM và CPU của Minecraft Server process
    Chạy trong thread riêng, log mỗi 15 giây
    """
    while True:
        try:
            if state.java_process and state.java_process.poll() is None:
                p = psutil.Process(state.java_process.pid)
                state.current_mc_ram = p.memory_info().rss // 1024 // 1024
                state.current_mc_cpu = int(p.cpu_percent(interval=0.5))
                add_log(f"[MONITOR] Server MC Process Stats -> RAM Used: {state.current_mc_ram}MB | CPU: {state.current_mc_cpu}%", "monitor")
            else:
                state.current_mc_ram = 0
                state.current_mc_cpu = 0
        except Exception:
            pass
        time.sleep(15)


def get_server_stats():
    """
    Lấy thống kê hiện tại của server
    
    Returns:
        dict: Thông tin stats (status, ram_used, cpu, ip, location)
    """
    status_mc = "RUNNING" if (state.java_process and state.java_process.poll() is None) else "STOPPED"
    
    return {
        "status": status_mc,
        "ram_used": state.current_mc_ram,
        "cpu": state.current_mc_cpu,
        "ip": state.server_ip,
        "location": state.server_location
    }