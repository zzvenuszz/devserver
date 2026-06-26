"""
Cấu hình tập trung cho ứng dụng Flask
"""
import os

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
    
    def reset(self):
        """Reset state (hữu ích cho testing)"""
        self.logs = []
        self.java_process = None
        self.playit_process = None
        self.current_mc_ram = 0
        self.current_mc_cpu = 0


# Singleton instance
state = GlobalState()