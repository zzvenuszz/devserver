"""
Cấu hình tập trung cho ứng dụng Flask
"""
import os
import time

# Cấu hình cơ bản
BASE_DATA_DIR = "/data"
if not os.path.exists(BASE_DATA_DIR):
    os.makedirs(BASE_DATA_DIR, exist_ok=True)

# Flask App Configuration
class Config:
    # Secret Key cho mã hóa session
    SECRET_KEY = os.getenv("ADMIN_PASS", "fallback_secret_key_if_not_set_123890")
    
    # Cấu hình Cookie hoạt động trong Iframe/Proxy
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'None'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Server configuration
    HOST = "0.0.0.0"
    PORT = int(os.getenv("PORT", 7860))
    
    # Minecraft Server Settings
    MC_RAM_MIN = "1G"
    MC_RAM_MAX = "10G"
    PAPER_JAR = "paper.jar"
    
    # Playit Configuration
    PLAYIT_SECRET_KEY = os.getenv("PLAYIT_SECRET_KEY")
    
    # Logging
    MAX_LOGS = 5000
    LOGS_TO_RETURN = 600
    
    # Monitor Thresholds
    MONITOR_DISK_GOOD = 20  # MB/s
    MONITOR_DISK_WARN = 5   # MB/s
    MONITOR_NET_GOOD = 10   # MB/s
    MONITOR_NET_WARN = 2    # MB/s
    MONITOR_TPS_GOOD = 19.8
    MONITOR_TPS_WARN = 18.0
    MONITOR_MSPT_GOOD = 20  # ms
    MONITOR_MSPT_WARN = 40  # ms
    
    # Monitor Settings
    MONITOR_COOLDOWN = 300  # 5 phút giữa các alert lặp lại
    MONITOR_CHART_DURATION = 1800  # 30 phút lịch sử
    
    # Benchmark Settings
    MONITOR_BENCHMARK_FILE_SIZE = 10  # MB - kích thước file test
    MONITOR_BENCHMARK_NET_SIZE = 1  # MB - kích thước file test network
    MONITOR_DISK_MAX_DEFAULT = 100  # MB/s - default nếu benchmark fail
    MONITOR_NET_MAX_DEFAULT = 50   # MB/s - default nếu benchmark fail


# Global state (sẽ được quản lý bởi services)
class GlobalState:
    """Lưu trạng thái toàn cục của ứng dụng"""
    def __init__(self):
        self.logs = []
        self.java_process = None
        self.playit_process = None
        self.current_mc_ram = 0
        self.current_mc_cpu = 0
        self.server_ip = "Đang lấy..."
        self.server_location = "Đang lấy..."
        
        # System stats
        self.system_cpu = 0
        self.system_ram = 0
        self.system_ram_total = 0
        self.disk_read = 0
        self.disk_write = 0
        self.net_sent = 0
        self.net_recv = 0
        
        # Minecraft stats
        self.mc_tps = 20.0
        self.mc_mspt = 0
        self.mc_players = 0
        self.mc_max_players = 0
        self.mc_ping = 0
        
        # Monitor control
        self.monitor_enabled = False
        self.monitor_mode = "auto"  # "on", "off", "auto"
        self.monitor_last_active = time.time()
        self.disk_max_speed = Config.MONITOR_DISK_MAX_DEFAULT
        self.net_max_speed = Config.MONITOR_NET_MAX_DEFAULT
        
        # Monitor track flags (được load từ settings)
        self.monitor_track_tps = True
        self.monitor_track_players = True
        self.monitor_track_cpu = True
        self.monitor_track_ram = True
        self.monitor_track_disk = True
        self.monitor_track_network = True
        
        # Theme
        self.theme_mode = "dark"
        
        # Alert system
        self.current_alert_status = {
            "disk": "green",
            "network": "green",
            "tps": "green",
            "mspt": "green"
        }
        self.last_alert_times = {}
        self.alert_history = []
        
        # Chart data (30 phút, 1 điểm/giây = 1800 điểm)
        self.chart_data = {
            "timestamps": [],
            "tps": [],
            "mspt": [],
            "cpu": [],
            "ram": [],
            "disk": [],
            "network": []
        }
    
    def reset(self):
        """Reset state (hữu ích cho testing)"""
        self.logs = []
        self.java_process = None
        self.playit_process = None
        self.current_mc_ram = 0
        self.current_mc_cpu = 0
        self.system_cpu = 0
        self.system_ram = 0
        self.system_ram_total = 0
        self.disk_read = 0
        self.disk_write = 0
        self.net_sent = 0
        self.net_recv = 0
        self.mc_tps = 20.0
        self.mc_mspt = 0
        self.mc_players = 0
        self.mc_max_players = 0
        self.mc_ping = 0
        self.monitor_enabled = False
        self.monitor_mode = "auto"
        self.disk_max_speed = Config.MONITOR_DISK_MAX_DEFAULT
        self.net_max_speed = Config.MONITOR_NET_MAX_DEFAULT
        self.monitor_track_tps = True
        self.monitor_track_players = True
        self.monitor_track_cpu = True
        self.monitor_track_ram = True
        self.monitor_track_disk = True
        self.monitor_track_network = True
        self.theme_mode = "dark"
        self.current_alert_status = {
            "disk": "green",
            "network": "green",
            "tps": "green",
            "mspt": "green"
        }
        self.last_alert_times = {}
        self.alert_history = []
        self.chart_data = {
            "timestamps": [],
            "tps": [],
            "mspt": [],
            "cpu": [],
            "ram": [],
            "disk": [],
            "network": []
        }


# Singleton instance
state = GlobalState()