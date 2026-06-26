"""
Monitor Service - Giám sát tài nguyên hệ thống và Minecraft Server
"""
import time
import psutil
import threading
from datetime import datetime
from server.config import state, Config
from server.utils import add_log
from server.services.minecraft import send_command


def get_status_color(metric_type, value):
    """
    Xác định màu trạng thái dựa trên ngưỡng
    Returns: "green", "yellow", "red"
    """
    if metric_type == "disk":
        if value >= Config.MONITOR_DISK_GOOD:
            return "green"
        elif value >= Config.MONITOR_DISK_WARN:
            return "yellow"
        else:
            return "red"
    
    elif metric_type == "network":
        if value >= Config.MONITOR_NET_GOOD:
            return "green"
        elif value >= Config.MONITOR_NET_WARN:
            return "yellow"
        else:
            return "red"
    
    elif metric_type == "tps":
        if value >= Config.MONITOR_TPS_GOOD:
            return "green"
        elif value >= Config.MONITOR_TPS_WARN:
            return "yellow"
        else:
            return "red"
    
    elif metric_type == "mspt":
        if value <= Config.MONITOR_MSPT_GOOD:
            return "green"
        elif value <= Config.MONITOR_MSPT_WARN:
            return "yellow"
        else:
            return "red"
    
    return "green"


def send_minecraft_alert(metric_type, old_status, new_status, value):
    """Gửi alert vào Minecraft chat qua tellraw"""
    if not state.java_process or state.java_process.poll() is not None:
        return
    
    # Không gửi nếu trạng thái giống nhau
    if old_status == new_status:
        return
    
    # Kiểm tra cooldown
    alert_key = f"{metric_type}_{new_status}"
    current_time = time.time()
    
    if alert_key in state.last_alert_times:
        if current_time - state.last_alert_times[alert_key] < Config.MONITOR_COOLDOWN:
            return
    
    state.last_alert_times[alert_key] = current_time
    
    # Tạo message theo metric
    if metric_type == "disk":
        if new_status == "green":
            msg = "[Giám sát] Disk đang ở mức tốt. Chunk sẽ load nhanh."
            color = "green"
        elif new_status == "yellow":
            msg = "[Cảnh báo] Disk đang ở mức trung bình. Chunk có thể load hơi chậm."
            color = "yellow"
        else:
            msg = "[Cảnh báo] Disk đang ở mức rất thấp. Chunk sẽ load rất chậm."
            color = "red"
    
    elif metric_type == "network":
        if new_status == "green":
            msg = "[Giám sát] Network đang ổn định. Kết nối tốt."
            color = "green"
        elif new_status == "yellow":
            msg = "[Cảnh báo] Network hơi yếu. Có thể có lag khi kết nối."
            color = "yellow"
        else:
            msg = "[Cảnh báo] Network rất yếu. Người chơi có thể bị disconnect."
            color = "red"
    
    elif metric_type == "tps":
        if new_status == "green":
            msg = "[Giám sát] TPS đang ổn định. Server chạy mượt."
            color = "green"
        elif new_status == "yellow":
            msg = "[Cảnh báo] TPS giảm. Server có thể bị lag nhẹ."
            color = "yellow"
        else:
            msg = "[Cảnh báo] TPS rất thấp. Server đang bị lag nghiêm trọng!"
            color = "red"
    
    elif metric_type == "mspt":
        if new_status == "green":
            msg = "[Giám sát] MSPT đang ở mức tốt. Server phản hồi nhanh."
            color = "green"
        elif new_status == "yellow":
            msg = "[Cảnh báo] MSPT tăng. Server phản hồi chậm hơn."
            color = "yellow"
        else:
            msg = "[Cảnh báo] MSPT rất cao. Server phản hồi rất chậm!"
            color = "red"
    
    else:
        return
    
    # Gửi tellraw command
    tellraw_cmd = f'tellraw @a {{"text":"{msg}","color":"{color}"}}'
    send_command(tellraw_cmd)
    
    # Log
    add_log(f"[ALERT] {metric_type.upper()}: {old_status} -> {new_status} (Value: {value})", "monitor")
    
    # Lưu vào alert history
    state.alert_history.append({
        "time": datetime.now().strftime("%H:%M"),
        "metric": metric_type.upper(),
        "old": old_status.upper(),
        "new": new_status.upper()
    })
    
    # Giới hạn lịch sử
    if len(state.alert_history) > 100:
        state.alert_history = state.alert_history[-100:]


def monitor_system():
    """Theo dõi tài nguyên hệ thống (CPU, RAM, Disk, Network)"""
    prev_disk = psutil.disk_io_counters()
    prev_net = psutil.net_io_counters()
    
    while True:
        try:
            if not state.monitor_enabled:
                time.sleep(1)
                continue
            
            # CPU hệ thống
            state.system_cpu = int(psutil.cpu_percent(interval=0.5))
            
            # RAM hệ thống
            mem = psutil.virtual_memory()
            state.system_ram = int(mem.used / 1024 / 1024)
            state.system_ram_total = int(mem.total / 1024 / 1024)
            
            # Disk I/O
            curr_disk = psutil.disk_io_counters()
            if prev_disk and curr_disk:
                state.disk_read = round((curr_disk.read_bytes - prev_disk.read_bytes) / 1024 / 1024, 2)
                state.disk_write = round((curr_disk.write_bytes - prev_disk.write_bytes) / 1024 / 1024, 2)
            prev_disk = curr_disk
            
            # Network I/O
            curr_net = psutil.net_io_counters()
            if prev_net and curr_net:
                state.net_sent = round((curr_net.bytes_sent - prev_net.bytes_sent) / 1024 / 1024, 2)
                state.net_recv = round((curr_net.bytes_recv - prev_net.bytes_recv) / 1024 / 1024, 2)
            prev_net = curr_net
            
            time.sleep(1)
        except Exception:
            time.sleep(1)


def monitor_minecraft():
    """Theo dõi TPS, MSPT, Players, Ping từ Minecraft server"""
    while True:
        try:
            if not state.monitor_enabled:
                time.sleep(1)
                continue
            
            if state.java_process and state.java_process.poll() is None:
                # Gửi lệnh lấy TPS
                send_command("tps")
                time.sleep(0.5)
                
                # Gửi lệnh lấy players
                send_command("list")
                time.sleep(0.5)
                
                # Đọc log để parse TPS, MSPT, Players
                # (Log đã được parse bởi parse_and_add_raw_log)
                # Chúng ta sẽ đọc từ state nếu có
                
                # Ping server (giả lập bằng thời gian response)
                # Thực tế cần measure từ server response
                state.mc_ping = 0  # Sẽ được cập nhật bởi API
            
            time.sleep(5)  # Check mỗi 5 giây
        except Exception:
            time.sleep(5)


def chart_data_collector():
    """Thu thập dữ liệu chart mỗi giây"""
    while True:
        try:
            if not state.monitor_enabled:
                time.sleep(1)
                continue
            
            now = datetime.now()
            timestamp = now.strftime("%H:%M:%S")
            
            # Thêm dữ liệu mới
            state.chart_data["timestamps"].append(timestamp)
            state.chart_data["tps"].append(state.mc_tps)
            state.chart_data["mspt"].append(state.mc_mspt)
            state.chart_data["cpu"].append(state.system_cpu)
            state.chart_data["ram"].append(state.system_ram)
            
            # Tính tổng disk và network
            total_io = state.disk_read + state.disk_write
            total_net = state.net_sent + state.net_recv
            state.chart_data["disk"].append(total_io)
            state.chart_data["network"].append(total_net)
            
            # Giới hạn 30 phút (1800 điểm)
            max_points = Config.MONITOR_CHART_DURATION
            for key in state.chart_data:
                if len(state.chart_data[key]) > max_points:
                    state.chart_data[key] = state.chart_data[key][-max_points:]
            
            time.sleep(1)
        except Exception:
            time.sleep(1)


def alert_manager():
    """Quản lý logic cảnh báo và gửi alert"""
    while True:
        try:
            if not state.monitor_enabled:
                time.sleep(1)
                continue
            
            # Kiểm tra Disk
            total_disk = state.disk_read + state.disk_write
            new_disk_status = get_status_color("disk", total_disk)
            if new_disk_status != state.current_alert_status["disk"]:
                old = state.current_alert_status["disk"]
                state.current_alert_status["disk"] = new_disk_status
                send_minecraft_alert("disk", old, new_disk_status, total_disk)
            
            # Kiểm tra Network
            total_net = state.net_sent + state.net_recv
            new_net_status = get_status_color("network", total_net)
            if new_net_status != state.current_alert_status["network"]:
                old = state.current_alert_status["network"]
                state.current_alert_status["network"] = new_net_status
                send_minecraft_alert("network", old, new_net_status, total_net)
            
            # Kiểm tra TPS
            new_tps_status = get_status_color("tps", state.mc_tps)
            if new_tps_status != state.current_alert_status["tps"]:
                old = state.current_alert_status["tps"]
                state.current_alert_status["tps"] = new_tps_status
                send_minecraft_alert("tps", old, new_tps_status, state.mc_tps)
            
            # Kiểm tra MSPT
            new_mspt_status = get_status_color("mspt", state.mc_mspt)
            if new_mspt_status != state.current_alert_status["mspt"]:
                old = state.current_alert_status["mspt"]
                state.current_alert_status["mspt"] = new_mspt_status
                send_minecraft_alert("mspt", old, new_mspt_status, state.mc_mspt)
            
            time.sleep(1)
        except Exception:
            time.sleep(1)


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


def get_monitor_stats():
    """Lấy tất cả metrics monitor hiện tại"""
    return {
        "enabled": state.monitor_enabled,
        "system_cpu": state.system_cpu,
        "system_ram": state.system_ram,
        "system_ram_total": state.system_ram_total,
        "disk_read": state.disk_read,
        "disk_write": state.disk_write,
        "net_sent": state.net_sent,
        "net_recv": state.net_recv,
        "mc_tps": state.mc_tps,
        "mc_mspt": state.mc_mspt,
        "mc_players": state.mc_players,
        "mc_max_players": state.mc_max_players,
        "mc_ping": state.mc_ping,
        "alert_status": state.current_alert_status,
        "alert_history": state.alert_history[-20:]  # 20 alert gần nhất
    }


def get_chart_data():
    """Lấy dữ liệu chart"""
    return state.chart_data


def toggle_monitor():
    """Bật/tắt monitor"""
    state.monitor_enabled = not state.monitor_enabled
    return state.monitor_enabled


def parse_tps_from_log(line):
    """Parse TPS từ log Minecraft"""
    # Ví dụ: "TPS: 19.8, 20.0, 20.0"
    if "TPS:" in line:
        try:
            parts = line.split("TPS:")[1].strip().split(",")
            if parts:
                tps = float(parts[0].strip())
                state.mc_tps = round(tps, 2)
        except Exception:
            pass


def parse_mspt_from_log(line):
    """Parse MSPT từ log Minecraft"""
    # Ví dụ: "MSPT: 15.2"
    if "MSPT:" in line:
        try:
            mspt = float(line.split("MSPT:")[1].strip().split()[0])
            state.mc_mspt = round(mspt, 2)
        except Exception:
            pass


def parse_players_from_log(line):
    """Parse số người chơi từ log"""
    # Ví dụ: "There are 5/20 players online"
    if "players online" in line:
        try:
            parts = line.split("There are")[1].split("players online")[0].strip().split("/")
            if len(parts) == 2:
                state.mc_players = int(parts[0].strip())
                state.mc_max_players = int(parts[1].strip())
        except Exception:
            pass


def start_monitor_threads():
    """Khởi chạy tất cả threads monitor"""
    threads = [
        threading.Thread(target=monitor_system, daemon=True),
        threading.Thread(target=monitor_minecraft, daemon=True),
        threading.Thread(target=alert_manager, daemon=True),
        threading.Thread(target=chart_data_collector, daemon=True)
    ]
    
    for t in threads:
        t.start()
    
    add_log("Monitor threads đã được khởi chạy", "system")