"""
Monitor Service - Giám sát tài nguyên hệ thống và Minecraft Server
"""
import time
import os
import psutil
import threading
import tempfile
from datetime import datetime
from server.config import state, Config
from server.utils import add_log
from server.services.minecraft import send_command


def benchmark_disk_network():
    """
    Benchmark tốc độ Disk và Network khi khởi động
    Lưu max speed vào state và file để dùng làm mốc 100%
    """
    add_log("Đang chạy benchmark Disk & Network...", "monitor")
    
    try:
        # Benchmark Disk - tạo file 10MB và đo tốc độ ghi/đọc
        test_file = os.path.join(tempfile.gettempdir(), "benchmark_test.dat")
        test_size = Config.MONITOR_BENCHMARK_FILE_SIZE * 1024 * 1024  # MB to bytes
        test_data = os.urandom(test_size)
        
        # Test write speed
        start_time = time.time()
        with open(test_file, "wb") as f:
            f.write(test_data)
            f.flush()
            os.fsync(f.fileno())
        write_time = time.time() - start_time
        write_speed = (test_size / 1024 / 1024) / write_time if write_time > 0 else 0
        
        # Test read speed
        start_time = time.time()
        with open(test_file, "rb") as f:
            _ = f.read()
        read_time = time.time() - start_time
        read_speed = (test_size / 1024 / 1024) / read_time if read_time > 0 else 0
        
        # Cleanup
        try:
            os.remove(test_file)
        except Exception:
            pass
        
        # Lấy max speed
        disk_max = max(write_speed, read_speed)
        state.disk_max_speed = max(disk_max, Config.MONITOR_DISK_MAX_DEFAULT)
        
        # Benchmark Network - download từ localhost
        try:
            import http.server
            import socketserver
            import urllib.request
            import threading
            
            # Tạo file nhỏ để serve
            net_test_file = os.path.join(tempfile.gettempdir(), "net_benchmark.dat")
            net_test_size = Config.MONITOR_BENCHMARK_NET_SIZE * 1024 * 1024
            with open(net_test_file, "wb") as f:
                f.write(os.urandom(net_test_size))
            
            # Start server
            PORT = 18999
            handler = http.server.SimpleHTTPRequestHandler
            with socketserver.TCPServer(("", PORT), handler) as httpd:
                server_thread = threading.Thread(target=httpd.serve_forever)
                server_thread.daemon = True
                server_thread.start()
                
                # Test download
                url = f"http://localhost:{PORT}/net_benchmark.dat"
                start_time = time.time()
                urllib.request.urlopen(url, timeout=5)
                download_time = time.time() - start_time
                net_speed = (net_test_size / 1024 / 1024) / download_time if download_time > 0 else 0
                
                httpd.shutdown()
            
            # Cleanup
            try:
                os.remove(net_test_file)
            except Exception:
                pass
            
            state.net_max_speed = max(net_speed, Config.MONITOR_NET_MAX_DEFAULT)
            
        except Exception as e:
            add_log(f"Network benchmark failed: {e}", "monitor")
            state.net_max_speed = Config.MONITOR_NET_MAX_DEFAULT
        
        # Lưu benchmark results vào file
        from server.utils.persistence import save_benchmark_results
        save_benchmark_results(state.disk_max_speed, state.net_max_speed)
        
        add_log(f"Benchmark hoàn tất: Disk Max={state.disk_max_speed:.1f} MB/s, Net Max={state.net_max_speed:.1f} MB/s", "monitor")
        
    except Exception as e:
        add_log(f"Benchmark failed: {e}", "monitor")
        state.disk_max_speed = Config.MONITOR_DISK_MAX_DEFAULT
        state.net_max_speed = Config.MONITOR_NET_MAX_DEFAULT


def get_status_color(metric_type, value):
    """
    Xác định màu trạng thái dựa trên tỷ lệ % của max speed
    Logic: 
    - Usage THẤP (< 20% max) → server nhàn → GREEN
    - Usage TRUNG BÌNH (20-50% max) → YELLOW
    - Usage CAO (>= 50% max) → server tải nặng → RED
    
    Returns: "green", "yellow", "red"
    """
    if metric_type == "disk":
        if state.disk_max_speed > 0:
            ratio = (value / state.disk_max_speed) * 100
        else:
            ratio = 0
        
        if ratio < 20:  # < 20% max speed - nhàn
            return "green"
        elif ratio < 50:  # 20-50% max speed - trung bình
            return "yellow"
        else:  # >= 50% max speed - tải nặng
            return "red"
    
    elif metric_type == "network":
        if state.net_max_speed > 0:
            ratio = (value / state.net_max_speed) * 100
        else:
            ratio = 0
        
        if ratio < 20:  # < 20% max speed - nhàn
            return "green"
        elif ratio < 50:  # 20-50% max speed - trung bình
            return "yellow"
        else:  # >= 50% max speed - tải nặng
            return "red"
    
    elif metric_type == "cpu":
        if value > 90:
            return "red"
        elif value > 70:
            return "yellow"
        else:
            return "green"
    
    elif metric_type == "ram":
        if value > 90:
            return "red"
        elif value > 70:
            return "yellow"
        else:
            return "green"
    
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
    
    # Tạo message theo metric (đã cập nhật nghĩa cho đúng)
    if metric_type == "disk":
        if new_status == "green":
            msg = "[Giám sát] Disk đang nhàn (usage thấp). Chunk sẽ load nhanh."
            color = "green"
        elif new_status == "yellow":
            msg = "[Cảnh báo] Disk đang ở mức sử dụng trung bình."
            color = "yellow"
        else:
            msg = "[Cảnh báo] Disk đang căng thẳng (usage cao). Chunk có thể load chậm!"
            color = "red"
    
    elif metric_type == "network":
        if new_status == "green":
            msg = "[Giám sát] Network đang nhàn (bandwidth thấp). Kết nối tốt."
            color = "green"
        elif new_status == "yellow":
            msg = "[Cảnh báo] Network đang ở mức sử dụng trung bình."
            color = "yellow"
        else:
            msg = "[Cảnh báo] Network đang căng thẳng (bandwidth cao). Có thể có lag!"
            color = "red"
    
    elif metric_type == "cpu":
        if new_status == "green":
            msg = "[Giám sát] CPU đang ổn định."
            color = "green"
        elif new_status == "yellow":
            msg = "[Cảnh báo] CPU đang ở mức cao."
            color = "yellow"
        else:
            msg = "[Cảnh báo] CPU quá tải! Server có thể bị lag!"
            color = "red"
    
    elif metric_type == "ram":
        if new_status == "green":
            msg = "[Giám sát] RAM đang ổn định."
            color = "green"
        elif new_status == "yellow":
            msg = "[Cảnh báo] RAM đang ở mức cao."
            color = "yellow"
        else:
            msg = "[Cảnh báo] RAM gần đầy! Có thể gây crash!"
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
            
            # CPU hệ thống (chỉ thu thập nếu được bật)
            if getattr(state, 'monitor_track_cpu', True):
                state.system_cpu = int(psutil.cpu_percent(interval=0.5))
            else:
                state.system_cpu = 0
            
            # RAM hệ thống (chỉ thu thập nếu được bật)
            if getattr(state, 'monitor_track_ram', True):
                mem = psutil.virtual_memory()
                state.system_ram = int(mem.used / 1024 / 1024)
                state.system_ram_total = int(mem.total / 1024 / 1024)
            else:
                state.system_ram = 0
                state.system_ram_total = 0
            
            # Disk I/O (chỉ thu thập nếu được bật)
            if getattr(state, 'monitor_track_disk', True):
                curr_disk = psutil.disk_io_counters()
                if prev_disk and curr_disk:
                    state.disk_read = round((curr_disk.read_bytes - prev_disk.read_bytes) / 1024 / 1024, 2)
                    state.disk_write = round((curr_disk.write_bytes - prev_disk.write_bytes) / 1024 / 1024, 2)
                prev_disk = curr_disk
            else:
                state.disk_read = 0
                state.disk_write = 0
            
            # Network I/O (chỉ thu thập nếu được bật)
            if getattr(state, 'monitor_track_network', True):
                curr_net = psutil.net_io_counters()
                if prev_net and curr_net:
                    state.net_sent = round((curr_net.bytes_sent - prev_net.bytes_sent) / 1024 / 1024, 2)
                    state.net_recv = round((curr_net.bytes_recv - prev_net.bytes_recv) / 1024 / 1024, 2)
                prev_net = curr_net
            else:
                state.net_sent = 0
                state.net_recv = 0
            
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
                # Chỉ gửi lệnh tps nếu được bật
                if getattr(state, 'monitor_track_tps', True):
                    send_command("tps")
                    time.sleep(0.5)
                
                # Chỉ gửi lệnh list nếu được bật
                if getattr(state, 'monitor_track_players', True):
                    send_command("list")
                    time.sleep(0.5)
                
                # Ping server (giả lập bằng thời gian response)
                state.mc_ping = 0  # Sẽ được cập nhật bởi API
            
            time.sleep(15)  # Tăng interval lên 15s để giảm spam
        except Exception:
            time.sleep(15)


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
            
            # Kiểm tra CPU (chỉ nếu được bật)
            if getattr(state, 'monitor_track_cpu', True):
                new_cpu_status = get_status_color("cpu", state.system_cpu)
                if new_cpu_status != state.current_alert_status["cpu"]:
                    old = state.current_alert_status["cpu"]
                    state.current_alert_status["cpu"] = new_cpu_status
                    send_minecraft_alert("cpu", old, new_cpu_status, state.system_cpu)
            
            # Kiểm tra RAM (chỉ nếu được bật)
            if getattr(state, 'monitor_track_ram', True):
                ram_percent = (state.system_ram / state.system_ram_total * 100) if state.system_ram_total > 0 else 0
                new_ram_status = get_status_color("ram", ram_percent)
                if new_ram_status != state.current_alert_status["ram"]:
                    old = state.current_alert_status["ram"]
                    state.current_alert_status["ram"] = new_ram_status
                    send_minecraft_alert("ram", old, new_ram_status, ram_percent)
            
            # Kiểm tra Disk (chỉ nếu được bật)
            if getattr(state, 'monitor_track_disk', True):
                total_disk = state.disk_read + state.disk_write
                new_disk_status = get_status_color("disk", total_disk)
                if new_disk_status != state.current_alert_status["disk"]:
                    old = state.current_alert_status["disk"]
                    state.current_alert_status["disk"] = new_disk_status
                    send_minecraft_alert("disk", old, new_disk_status, total_disk)
            
            # Kiểm tra Network (chỉ nếu được bật)
            if getattr(state, 'monitor_track_network', True):
                total_net = state.net_sent + state.net_recv
                new_net_status = get_status_color("network", total_net)
                if new_net_status != state.current_alert_status["network"]:
                    old = state.current_alert_status["network"]
                    state.current_alert_status["network"] = new_net_status
                    send_minecraft_alert("network", old, new_net_status, total_net)
            
            # Kiểm tra TPS (chỉ nếu được bật)
            if getattr(state, 'monitor_track_tps', True):
                new_tps_status = get_status_color("tps", state.mc_tps)
                if new_tps_status != state.current_alert_status["tps"]:
                    old = state.current_alert_status["tps"]
                    state.current_alert_status["tps"] = new_tps_status
                    send_minecraft_alert("tps", old, new_tps_status, state.mc_tps)
            
            # Kiểm tra MSPT (luôn bật vì không gửi lệnh)
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
        "mode": state.monitor_mode,
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
        "disk_max_speed": state.disk_max_speed,
        "net_max_speed": state.net_max_speed,
        "alert_status": state.current_alert_status,
        "alert_history": state.alert_history[-20:],  # 20 alert gần nhất
        "track_flags": {
            "tps": getattr(state, 'monitor_track_tps', True),
            "players": getattr(state, 'monitor_track_players', True),
            "cpu": getattr(state, 'monitor_track_cpu', True),
            "ram": getattr(state, 'monitor_track_ram', True),
            "disk": getattr(state, 'monitor_track_disk', True),
            "network": getattr(state, 'monitor_track_network', True)
        }
    }


def get_chart_data():
    """Lấy dữ liệu chart"""
    return state.chart_data


def toggle_monitor():
    """Bật/tắt monitor"""
    state.monitor_enabled = not state.monitor_enabled
    if state.monitor_enabled:
        state.monitor_last_active = time.time()
    return state.monitor_enabled


def set_monitor_mode(mode):
    """Đặt chế độ monitor: 'on', 'off', 'auto'"""
    if mode in ["on", "off", "auto"]:
        state.monitor_mode = mode
        if mode == "on":
            state.monitor_enabled = True
            state.monitor_last_active = time.time()
        elif mode == "off":
            state.monitor_enabled = False
        # auto mode sẽ được xử lý bởi frontend
    return state.monitor_mode


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