"""
Server Info Service - Lấy thông tin IP và Location của máy chủ
"""
import urllib.request
import json
from server.config import state
from server.utils import add_log


def fetch_server_info():
    """
    Hàm lấy IP và Location chi tiết sử dụng endpoint tối ưu cho Cloud Spaces
    """
    # Danh sách các API dịch vụ định vị dự phòng để đảm bảo luôn lấy được dữ liệu cụ thể
    endpoints = [
        {"url": "http://ip-api.com/json/", "ip_key": "query", "city_key": "city", "country_key": "country"},
        {"url": "https://ipinfo.io/json", "ip_key": "ip", "city_key": "city", "country_key": "country"}
    ]
    
    for provider in endpoints:
        try:
            req = urllib.request.Request(
                provider["url"], 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                
                state.server_ip = data.get(provider["ip_key"], "Unknown")
                city = data.get(provider["city_key"], "")
                country = data.get(provider["country_key"], "")
                
                if city or country:
                    state.server_location = f"{city}, {country}".strip(", ")
                    add_log(f"Đã định vị máy chủ tại: {state.server_location}", "system")
                    return  # Hoàn thành lấy dữ liệu, thoát hàm
        except Exception as e:
            print(f"Lỗi khi thử lấy dữ liệu từ {provider['url']}: {e}")
            continue

    # Nếu tất cả các bên đều lỗi, sử dụng giải pháp cuối cùng
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as resp:
            state.server_ip = resp.read().decode().strip()
            state.server_location = "N/A (Bị chặn API định vị)"
    except Exception:
        state.server_ip = "Không rõ IP"
        state.server_location = "Không rõ vị trí"