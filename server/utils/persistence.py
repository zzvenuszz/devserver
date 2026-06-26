"""
Persistence Module - Lưu và load settings từ disk
"""
import json
import os
from server.config import state, Config

# Đường dẫn thư mục và files
PANEL_DIR = "/data/panel"
SETTINGS_FILE = os.path.join(PANEL_DIR, "settings.json")
BENCHMARK_FILE = os.path.join(PANEL_DIR, "benchmark_results.json")


def ensure_panel_dir():
    """Đảm bảo thư mục /data/panel tồn tại"""
    os.makedirs(PANEL_DIR, exist_ok=True)


def load_settings():
    """Load settings từ file, nếu chưa có thì tạo mới với default values"""
    ensure_panel_dir()
    
    default_settings = {
        "monitor": {
            "mode": "auto",
            "track_tps": True,
            "track_players": True,
            "track_cpu": True,
            "track_ram": True,
            "track_disk": True,
            "track_network": True
        },
        "theme": {
            "mode": "dark"
        }
    }
    
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Merge với default để đảm bảo có đủ keys
                return {**default_settings, **settings}
        else:
            # Tạo file mới với default values
            save_settings(default_settings)
            return default_settings
    except Exception as e:
        print(f"Error loading settings: {e}")
        return default_settings


def save_settings(settings):
    """Lưu settings vào file"""
    ensure_panel_dir()
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving settings: {e}")
        return False


def load_benchmark_results():
    """Load kết quả benchmark từ file"""
    ensure_panel_dir()
    
    try:
        if os.path.exists(BENCHMARK_FILE):
            with open(BENCHMARK_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading benchmark results: {e}")
    
    return None


def save_benchmark_results(disk_max, net_max):
    """Lưu kết quả benchmark"""
    ensure_panel_dir()
    try:
        data = {
            "disk_max_speed": disk_max,
            "net_max_speed": net_max,
            "timestamp": str(__import__('datetime').datetime.now())
        }
        with open(BENCHMARK_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving benchmark results: {e}")
        return False


def apply_settings_to_state(settings):
    """Áp dụng settings vào global state"""
    try:
        # Monitor settings
        if "monitor" in settings:
            monitor = settings["monitor"]
            state.monitor_mode = monitor.get("mode", "auto")
            
            # Track flags (sẽ dùng trong monitor.py)
            state.monitor_track_tps = monitor.get("track_tps", True)
            state.monitor_track_players = monitor.get("track_players", True)
            state.monitor_track_cpu = monitor.get("track_cpu", True)
            state.monitor_track_ram = monitor.get("track_ram", True)
            state.monitor_track_disk = monitor.get("track_disk", True)
            state.monitor_track_network = monitor.get("track_network", True)
        
        # Theme settings
        if "theme" in settings:
            state.theme_mode = settings["theme"].get("mode", "dark")
        
        # Benchmark results
        benchmark = load_benchmark_results()
        if benchmark:
            state.disk_max_speed = benchmark.get("disk_max_speed", Config.MONITOR_DISK_MAX_DEFAULT)
            state.net_max_speed = benchmark.get("net_max_speed", Config.MONITOR_NET_MAX_DEFAULT)
        
    except Exception as e:
        print(f"Error applying settings: {e}")


def get_current_settings():
    """Lấy settings hiện tại từ state"""
    return {
        "monitor": {
            "mode": state.monitor_mode,
            "track_tps": getattr(state, 'monitor_track_tps', True),
            "track_players": getattr(state, 'monitor_track_players', True),
            "track_cpu": getattr(state, 'monitor_track_cpu', True),
            "track_ram": getattr(state, 'monitor_track_ram', True),
            "track_disk": getattr(state, 'monitor_track_disk', True),
            "track_network": getattr(state, 'monitor_track_network', True)
        },
        "theme": {
            "mode": getattr(state, 'theme_mode', 'dark')
        },
        "benchmark": {
            "disk_max_speed": state.disk_max_speed,
            "net_max_speed": state.net_max_speed
        }
    }