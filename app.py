from flask import Flask, send_from_directory, render_template_string, request, redirect, jsonify, session
import urllib.request
import urllib.parse
import subprocess
import threading
import shutil
import psutil
import datetime
import zipfile
import hashlib
import time
import json
import re
import os

app = Flask(__name__)

# Cấu hình Secret Key cho Flask để mã hóa dữ liệu Session
app.secret_key = os.getenv("ADMIN_PASS", "fallback_secret_key_if_not_set_123890")

# Cấu hình Cookie hoạt động được trong Iframe/Proxy của Hugging Face
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE='None',
    PERMANENT_SESSION_LIFETIME=86400
)

logs = []
java_process = None
playit_process = None
current_mc_ram = 0
current_mc_cpu = 0

# Biến toàn cục lưu thông tin Máy chủ
server_ip = "Đang lấy..."
server_location = "Đang lấy..."

# Đường dẫn bộ nhớ lưu trữ cố định trên Hugging Face
BASE_DATA_DIR = "/data"
if not os.path.exists(BASE_DATA_DIR):
    os.makedirs(BASE_DATA_DIR, exist_ok=True)


def fetch_server_info():
    """Hàm lấy IP và Location chi tiết sử dụng endpoint tối ưu cho Cloud Spaces"""
    global server_ip, server_location
    
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
                
                server_ip = data.get(provider["ip_key"], "Unknown")
                city = data.get(provider["city_key"], "")
                country = data.get(provider["country_key"], "")
                
                if city or country:
                    server_location = f"{city}, {country}".strip(", ")
                    add_log(f"Đã định vị máy chủ tại: {server_location}", "system")
                    return # Hoàn thành lấy dữ liệu, thoát hàm
        except Exception as e:
            print(f"Lỗi khi thử lấy dữ liệu từ {provider['url']}: {e}")
            continue

    # Nếu tất cả các bên đều lỗi, sử dụng giải pháp cuối cùng
    try:
        with urllib.request.urlopen("https://api.ipify.org", timeout=5) as resp:
            server_ip = resp.read().decode().strip()
            server_location = "N/A (Bị chặn API định vị)"
    except Exception:
        server_ip = "Không rõ IP"
        server_location = "Không rõ vị trí"


def add_log(msg, log_type="system"):
    """Phân loại log có cấu trúc để frontend dễ dàng lọc và tô màu"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "time": timestamp,
        "type": log_type,
        "text": msg.strip()
    }
    print(f"[{log_type.upper()}] {msg.strip()}")
    logs.append(log_entry)
    if len(logs) > 5000:
        logs.pop(0)


def parse_and_add_raw_log(line):
    """Phân tích tối ưu dựa trên dữ liệu log thực tế để phân loại chính xác vào các tab"""
    line_str = line.strip()
    if not line_str:
        return

    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    line_str = ansi_escape.sub('', line_str)

    log_type = "system"

    if "[MONITOR]" in line_str:
        log_type = "monitor"
    elif "[PLAYIT]" in line_str or "playit_agent_core" in line_str:
        log_type = "playit"
    elif "ERROR" in line_str.upper() or "WARN" in line_str.upper() or "EXCEPTION" in line_str.upper():
        log_type = "error"
    elif "issued server command:" in line_str or "made advancement" in line_str or "teleported to" in line_str:
        log_type = "command"
    elif re.search(r'\[Async Chat Thread.*\]:\s+<.*>', line_str) or "joined the game" in line_str or "left the game" in line_str or "[Server]" in line_str:
        log_type = "chat"
    elif re.search(r'\]\s+\[(.*?)\]:', line_str):
        match = re.search(r'\]\s+\[(.*?)\]:', line_str)
        if match and match.group(1) not in ["Server thread", "Configurate", "Paper", "System", "INFO", "WARN", "ERROR"]:
            log_type = "plugins"

    add_log(line_str, log_type=log_type)


def run_paper():
    global java_process

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

    cmd = [
        "java",
        "-Xms1G",
        "-Xmx10G",
        "-XshowSettings:vm",
        "-jar",
        "paper.jar",
        "-W",
        BASE_DATA_DIR,
        "--nogui"
    ]

    add_log("Starting Paper Minecraft Server with High-Performance Settings...", "system")

    java_process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    for line in java_process.stdout:
        parse_and_add_raw_log(line)


def run_playit():
    global playit_process
    secret_key = os.getenv("PLAYIT_SECRET_KEY")

    if not secret_key:
        add_log("PLAYIT_SECRET_KEY environment variable not found", "error")
        return

    cmd = ["./playit", "--secret", secret_key]
    add_log("Starting Playit Tunnel Network...", "playit")

    try:
        playit_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in playit_process.stdout:
            parse_and_add_raw_log(f"[PLAYIT] {line}")
    except Exception as e:
        add_log(f"Lỗi khởi chạy Playit: {e}", "error")


def monitor_java():
    global current_mc_ram, current_mc_cpu
    while True:
        try:
            if java_process and java_process.poll() is None:
                p = psutil.Process(java_process.pid)
                current_mc_ram = p.memory_info().rss // 1024 // 1024
                current_mc_cpu = int(p.cpu_percent(interval=0.5))
                add_log(f"[MONITOR] Server MC Process Stats -> RAM Used: {current_mc_ram}MB | CPU: {current_mc_cpu}%", "monitor")
            else:
                current_mc_ram = 0
                current_mc_cpu = 0
        except Exception:
            pass
        time.sleep(15)


# --- HỆ THỐNG BẢO MẬT ĐĂNG NHẬP ---

@app.before_request
def check_authentication():
    allowed_routes = ["login", "static", "api_ping"]
    if request.endpoint in allowed_routes:
        return None
    if not session.get("logged_in"):
        return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    correct_password = os.getenv("ADMIN_PASS")
    if not correct_password:
        return """
        <body style="font-family:sans-serif; background:#1e1e24; color:#fff; padding:50px; text-align:center;">
            <h2 style="color:#ff3333;">⚠️ LỖI BẢO MẬT KHỞI CHẠY</h2>
            <p>Bạn chưa cài đặt biến môi trường <strong>ADMIN_PASS</strong> trong mục Settings của Hugging Face Space!</p>
        </body>
        """

    error_msg = ""
    if request.method == "POST":
        input_pass = request.form.get("password", "")
        if input_pass == correct_password:
            session["logged_in"] = True
            session.permanent = True 
            return redirect("/")
        else:
            error_msg = "Mật khẩu quản trị không chính xác!"

    login_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>VnMine Panel Login</title>
        <meta charset="utf-8">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #121214; color: #e0e0e6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .login-card { background: #1e1e24; padding: 30px; border-radius: 8px; width: 100%; max-width: 360px; text-align: center; border: 1px solid #333; }
            h2 { color: #4caf50; margin-bottom: 20px; }
            input[type="password"] { width: 100%; padding: 12px; background: #111; border: 1px solid #444; color: white; border-radius: 4px; box-sizing: border-box; margin-bottom: 15px; text-align: center; }
            button { width: 100%; background: #4caf50; color: white; border: none; padding: 12px; border-radius: 4px; font-weight: bold; cursor: pointer; }
            .error { color: #ff3333; font-size: 13px; margin-bottom: 15px; text-align: left; background: rgba(255,51,51,0.1); padding: 8px; border-radius: 4px; border-left: 3px solid #ff3333; }
        </style>
    </head>
    <body>
        <div class="login-card">
            <h2>🧱 VnMine Panel Pro</h2>
            {% if error_msg %}<div class="error">{{ error_msg }}</div>{% endif %}
            <form method="POST">
                <input type="password" name="password" placeholder="Nhập mật khẩu quản trị..." required autofocus>
                <button type="submit">XÁC THỰC</button>
            </form>
        </div>
    </body>
    </html>
    """
    return render_template_string(login_html, error_msg=error_msg)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# --- API CONSOLE & LỆNH ---

@app.route("/api/logs")
def get_logs():
    return jsonify({"logs": logs[-600:]})


@app.route("/api/ping")
def api_ping():
    return jsonify({"status": "pong"})


@app.route("/api/command", methods=["POST"])
def send_command():
    global java_process
    raw_cmd = request.json.get("command", "").strip()
    if not raw_cmd:
        return jsonify({"status": "error", "message": "Lệnh trống"})

    if raw_cmd.startswith("/"):
        cmd = raw_cmd[1:].strip()
    else:
        mc_commands = ["stop", "reload", "rl", "op", "deop", "ban", "pardon", "kick", "gamemode", "gm", 
                       "tp", "teleport", "give", "clear", "xp", "seed", "whitelist", "list", "help", "time", 
                       "weather", "gamerule", "difficulty", "say", "plugins", "pl", "version", "mv", "multiverse", "tps", "save-all"]
        
        first_word = raw_cmd.split(" ")[0].lower()
        if first_word in mc_commands:
            cmd = raw_cmd
        else:
            cmd = f"say {raw_cmd}"

    if java_process and java_process.poll() is None:
        add_log(f"Execute Console Input: {cmd}", "command")
        try:
            java_process.stdin.write(cmd + "\n")
            java_process.stdin.flush()
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    else:
        return jsonify({"status": "error", "message": "Server Minecraft hiện đang không chạy!"})


# --- GIAO DIỆN CHÍNH ---

@app.route("/")
@app.route("/files")
@app.route("/files/<path:subpath>")
def index(subpath=""):
    active_tab = "files" if request.path.startswith("/files") else "console"
    target_dir = os.path.join(BASE_DATA_DIR, subpath)
    file_content = None
    edit_file_path = ""
    dir_items = []

    if not os.path.abspath(target_dir).startswith(os.path.abspath(BASE_DATA_DIR)):
        return "Bị từ chối truy cập vùng dữ liệu an toàn!", 403

    if os.path.exists(target_dir):
        if os.path.isfile(target_dir):
            edit_file_path = subpath
            active_tab = "files"
            try:
                with open(target_dir, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()
            except Exception as e:
                file_content = f"Không thể đọc nội dung file: {e}"
        else:
            try:
                dir_items = os.listdir(target_dir)
            except Exception:
                dir_items = []

    formatted_items = []
    if subpath:
        parent = os.path.dirname(subpath)
        parent_url = f"/files/{parent}" if parent and parent != subpath else "/files"
        formatted_items.append({
            "name": ".. (Thư mục cha)", 
            "is_dir": True, 
            "is_parent_link": True,
            "path": parent_url,
            "size": "-",
            "mtime": "-"
        })

    for item in sorted(dir_items):
        item_path = os.path.join(subpath, item)
        full_path = os.path.join(BASE_DATA_DIR, item_path)
        is_directory = os.path.isdir(full_path)
        
        try:
            stat_info = os.stat(full_path)
            size_val = f"{stat_info.st_size // 1024} KB" if not is_directory else "Folder"
            time_val = datetime.datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            size_val = "Unknown"
            time_val = "Unknown"

        formatted_items.append({
            "name": item, 
            "is_dir": is_directory,
            "is_parent_link": False,
            "path": f"/files/{item_path}", 
            "raw_path": item_path,
            "size": size_val,
            "mtime": time_val
        })

    status_mc = "RUNNING" if (java_process and java_process.poll() is None) else "STOPPED"
    stats_data = {
        "status": status_mc,
        "ram_used": current_mc_ram,
        "cpu": current_mc_cpu,
        "ip": server_ip,
        "location": server_location
    }

    main_html = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <title>VnMine Web Panel Ultimate</title>
        <meta charset="utf-8">
        <style>
            :root {
                --bg-main: #1e1e24;
                --bg-nav: #111116;
                --bg-tabs: #16161a;
                --bg-card: #25252b;
                --bg-console: #0c0c0f;
                --bg-log-box: #050507;
                --bg-input: #111;
                --bg-quick-btn: #1b1b20;
                --text-main: #e0e0e6;
                --text-muted: #aaa;
                --text-dark-gray: #888;
                --border-color: #3d3d45;
                --border-light: #2d2d35;
                --border-focus: #4caf50;
                
                --log-sys: #a0a0a0;
                --log-command: #39e360;
                --log-error: #ff5252;
                --log-plugins: #1ce1ff;
                --log-chat: #ff9233;
                --log-playit: #b07fff;
                --log-monitor: #8c8c8c;
                --link-color: #38b6ff;
                --link-dir-color: #ffc107;
            }

            [data-theme="light"] {
                --bg-main: #f4f6f9;
                --bg-nav: #ffffff;
                --bg-tabs: #eaecef;
                --bg-card: #ffffff;
                --bg-console: #f8f9fa;
                --bg-log-box: #ffffff;
                --bg-input: #e9ecef;
                --bg-quick-btn: #f1f3f5;
                --text-main: #212529;
                --text-muted: #495057;
                --text-dark-gray: #6c757d;
                --border-color: #ced4da;
                --border-light: #dee2e6;
                --border-focus: #218838;
                
                --log-sys: #333333;
                --log-command: #155724;
                --log-error: #721c24;
                --log-plugins: #0c5460;
                --log-chat: #a04000;
                --log-playit: #4a148c;
                --log-monitor: #5a5a5a;
                --link-color: #0056b3;
                --link-dir-color: #b15b00;
            }

            html, body { 
                height: 100vh; 
                margin: 0; 
                padding: 0; 
                overflow: hidden; 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: var(--bg-main); 
                color: var(--text-main); 
                display: flex;
                flex-direction: column;
                transition: background 0.3s, color 0.3s;
            }
            .navbar { 
                background: var(--bg-nav);
                padding: 10px 20px; 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                box-shadow: 0 2px 5px rgba(0,0,0,0.15);
                flex-shrink: 0;
            }
            .navbar h2 { margin: 0; color: #4caf50; font-size: 20px; }
            .nav-right-controls { display: flex; align-items: center; gap: 15px; }
            .stats-bar { display: flex; gap: 12px; font-size: 13px; color: var(--text-muted); align-items: center; }
            .stats-bar span { background: var(--bg-card); padding: 4px 8px; border-radius: 4px; border: 1px solid var(--border-color); color: var(--text-main); }
            .logout-btn { background: #dc3545; color: white; text-decoration: none; padding: 4px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; }
            
            .theme-selector {
                display: flex;
                background: var(--bg-input);
                border: 1px solid var(--border-color);
                border-radius: 20px;
                padding: 2px;
                gap: 2px;
            }
            .theme-btn {
                background: none;
                border: none;
                color: var(--text-muted);
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
                border-radius: 15px;
                cursor: pointer;
                transition: all 0.2s;
            }
            .theme-btn.active {
                background: #4caf50;
                color: white;
            }

            .tabs { 
                display: flex; 
                background: var(--bg-tabs);
                border-bottom: 2px solid var(--border-light); 
                flex-shrink: 0;
            }
            .tab-btn { padding: 12px 25px; border: none; background: none; color: var(--text-dark-gray); font-size: 15px; cursor: pointer; font-weight: bold; text-decoration: none; }
            .tab-btn.active { color: #4caf50; border-bottom: 3px solid #4caf50; background: var(--bg-main); }
            
            .container { 
                padding: 15px; 
                flex: 1;
                display: flex;
                flex-direction: column;
                overflow: hidden; 
                box-sizing: border-box;
            }
            
            /* CONSOLE LAYOUT */
            .console-layout {
                display: flex;
                flex-direction: column;
                flex: 1;
                overflow: hidden;
            }
            .console-filter-bar { 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                margin-bottom: 10px; 
                flex-shrink: 0; 
            }
            .console-filter-tabs { display: flex; gap: 5px; flex-wrap: wrap; }
            .filter-btn { background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-muted); padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; }
            .filter-btn.active { background: #4caf50; color: white; border-color: #4caf50; }
            
            .btn-copy-logs { background: #007bff; color: white; border: none; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; display: flex; align-items: center; gap: 5px; }

            .console-main-frame {
                display: grid;
                grid-template-columns: 7fr 3fr;
                gap: 15px;
                flex: 1;
                overflow: hidden;
            }

            .console-box { 
                background: var(--bg-console); 
                border: 1px solid var(--border-color);
                border-radius: 6px; 
                padding: 15px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            #logs-output { 
                flex: 1;
                overflow-y: auto; 
                font-family: 'Courier New', monospace; 
                font-size: 13px; 
                line-height: 1.6; 
                padding: 10px;
                background: var(--bg-log-box);
                border: 1px solid var(--border-light);
                border-radius: 4px;
                margin-bottom: 10px;
            }
            
            .log-item { margin-bottom: 2px; white-space: pre-wrap; word-break: break-all; color: var(--text-main); }
            .log-system { color: var(--log-sys); }
            .log-command { color: var(--log-command); font-weight: bold; } 
            .log-error { color: var(--log-error); font-weight: bold; background: rgba(255,77,77,0.08); padding: 1px 4px; border-radius: 2px; }
            .log-plugins { color: var(--log-plugins); font-weight: bold; }
            .log-chat { color: var(--log-chat); background: rgba(253,126,20,0.08); padding: 2px 4px; font-weight: 500; border-radius: 2px; }
            .log-playit { color: var(--log-playit); }
            .log-monitor { color: var(--log-monitor); font-size: 12px; }
            
            .cmd-container { position: relative; flex-shrink: 0; }
            .cmd-input-group { display: flex; gap: 10px; }
            #cmd-input { flex: 1; background: var(--bg-input); border: 1px solid var(--border-color); color: var(--text-main); padding: 12px; font-family: monospace; border-radius: 4px; font-size: 14px; }
            #cmd-input:focus { border-color: var(--border-focus); outline: none; }
            #autocomplete-box { position: absolute; bottom: 50px; left: 0; right: 0; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 4px; max-height: 150px; overflow-y: auto; z-index: 100; display: none; }
            .suggest-item { padding: 8px 12px; cursor: pointer; font-family: monospace; font-size: 13px; color: var(--text-muted); }
            .suggest-item:hover, .suggest-item.selected { background: var(--bg-input); color: #4caf50; }
            #btn-send { background: #4caf50; color: white; border: none; padding: 0 25px; border-radius: 4px; cursor: pointer; font-weight: bold; }

            .quick-panel {
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                padding: 15px;
                display: flex;
                flex-direction: column;
                overflow-y: auto;
            }
            .quick-panel h3 { margin-top: 0; margin-bottom: 12px; font-size: 14px; color: #4caf50; border-bottom: 1px solid var(--border-color); padding-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; }
            .cmd-group { display: flex; flex-direction: column; gap: 8px; margin-bottom: 18px; }
            .cmd-group-title { font-size: 11px; font-weight: bold; color: var(--text-dark-gray); margin-bottom: 2px; text-transform: uppercase; }
            .btn-quick { background: var(--bg-quick-btn); border: 1px solid var(--border-color); color: var(--text-main); padding: 8px 12px; text-align: left; border-radius: 4px; cursor: pointer; font-family: monospace; font-size: 12px; font-weight: 500; transition: all 0.2s; }
            .btn-quick:hover { background: #4caf50; color: white; border-color: #4caf50; transform: translateX(2px); }

            /* FILE MANAGER STYLE */
            .fm-layout { 
                display: grid; 
                grid-template-columns: 1.2fr 0.8fr; 
                gap: 15px; 
                flex: 1;
                overflow: hidden;
            }
            @media (max-width: 1000px) { 
                .fm-layout { grid-template-columns: 1fr; overflow-y: auto; } 
            }
            .card { 
                background: var(--bg-card); 
                border-radius: 6px;
                border: 1px solid var(--border-color);
                padding: 15px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            .card h3 { margin-top: 0; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; color: #4caf50; flex-shrink: 0; }
            
            .fm-toolbar { 
                display: flex; 
                gap: 10px; 
                margin-bottom: 15px; 
                background: var(--bg-quick-btn); 
                border: 1px solid var(--border-color); 
                padding: 10px; 
                border-radius: 4px; 
                align-items: center; 
                flex-shrink: 0; 
                justify-content: space-between;
            }
            .toolbar-left { display: flex; gap: 10px; align-items: center; flex: 1; }
            .toolbar-right { display: flex; gap: 10px; align-items: center; }
            
            .table-wrapper {
                flex: 1;
                overflow-y: auto;
                border: 1px solid var(--border-light);
                border-radius: 4px;
            }
            .fm-table { width: 100%; border-collapse: collapse; font-family: monospace; font-size: 13px; text-align: left; }
            .fm-table th { background: var(--bg-tabs); padding: 10px; color: var(--text-muted); border-bottom: 2px solid var(--border-light); position: sticky; top: 0; z-index: 10; }
            .fm-table td { padding: 8px 10px; border-bottom: 1px solid var(--border-light); vertical-align: middle; color: var(--text-main); }
            .fm-table tr:hover { background: var(--bg-input); }
            
            .file-link { text-decoration: none; color: var(--link-color); display: flex; align-items: center; gap: 5px; }
            .file-link.dir { color: var(--link-dir-color); font-weight: bold; }
            
            .actions { display: flex; gap: 5px; justify-content: flex-end; align-items: center; width: 100%; }
            .btn-action { text-decoration: none; padding: 6px 0; width: 55px; text-align: center; border-radius: 3px; font-size: 11px; color: #fff; cursor: pointer; border: none; font-family: sans-serif; font-weight: bold; display: inline-block; box-sizing: border-box; }
            .btn-del { background: #dc3545; } .btn-dl { background: #007bff; } .btn-ren { background: #17a2b8; } 
            .btn-zip { background: #6f42c1; } .btn-unzip { background: #fd7e14; } .btn-hash { background: #ff9233; }
            
            .editor-wrapper {
                flex: 1;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            #editor-text { 
                flex: 1;
                width: 100%; 
                background: var(--bg-log-box); 
                color: var(--text-main); 
                font-family: monospace; 
                padding: 10px; 
                border: 1px solid var(--border-color); 
                border-radius: 4px; 
                box-sizing: border-box; 
                line-height: 1.5;
                resize: none;
            }
            .btn-save { background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 10px; flex-shrink: 0; }
            .input-text-style { background: var(--bg-input); border: 1px solid var(--border-color); color: var(--text-main); padding: 6px 10px; border-radius: 4px; font-size: 13px; }
            .btn-tool { background: #28a745; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: bold; display: flex; align-items: center; gap: 5px; }

            .custom-modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; justify-content: center; align-items: center; z-index: 2000; display: none; }
            .custom-modal-box { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 6px; padding: 20px; width: 100%; max-width: 480px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); display: flex; flex-direction: column; gap: 15px; }
            .custom-modal-title { font-size: 16px; font-weight: bold; color: #4caf50; border-bottom: 1px solid var(--border-light); padding-bottom: 8px; margin: 0; }
            .custom-modal-body { font-size: 14px; color: var(--text-main); display: flex; flex-direction: column; gap: 10px; }
            .custom-modal-footer { display: flex; justify-content: flex-end; gap: 10px; margin-top: 5px; }
            .modal-log-area { background: #000; border: 1px solid #333; color: #00ff00; font-family: monospace; font-size: 12px; padding: 10px; max-height: 150px; overflow-y: auto; border-radius: 4px; white-space: pre-wrap; word-break: break-all; }
        </style>
    </head>
    <body>
        <div class="navbar">
            <h2>🧱 VnMine Panel Ultimate</h2>
            <div class="nav-right-controls">
                <div class="theme-selector">
                    <button class="theme-btn" id="theme-light" onclick="changeThemeMode('light')">☀️ Sáng</button>
                    <button class="theme-btn" id="theme-dark" onclick="changeThemeMode('dark')">🌙 Tối</button>
                    <button class="theme-btn" id="theme-auto" onclick="changeThemeMode('auto')">⚙️ Auto</button>
                </div>

                <div class="stats-bar">
                    <span>IP Host: <strong style="color:#1ce1ff;">{{ stats.ip }}</strong></span>
                    <span>Vị trí: <strong style="color:#ffca28;">{{ stats.location }}</strong></span>
                    <span>Browser Ping: <strong id="ping-display" style="color:#e11cff;">-- ms</strong></span>
                    <span>Server MC: <strong style="color: {{ 'green' if stats.status == 'RUNNING' else 'red' }}">{{ stats.status }}</strong></span>
                    <span>MC RAM: <strong style="color:#28a745;">{{ stats.ram_used }} MB</strong></span>
                    <span>MC CPU: <strong style="color:#007bff;">{{ stats.cpu }} %</strong></span>
                    <a href="/logout" class="logout-btn">🔒 Đăng xuất</a>
                </div>
            </div>
        </div>

        <div class="tabs">
            <a href="/" class="tab-btn {{ 'active' if active_tab == 'console' else '' }}">💻 Live Console</a>
            <a href="/files" class="tab-btn {{ 'active' if active_tab == 'files' else '' }}">📂 File Manager v4</a>
        </div>

        <div class="container">
            {% if active_tab == 'console' %}
            <div class="console-layout">
                <div class="console-filter-bar">
                    <div class="console-filter-tabs">
                        <button class="filter-btn active" onclick="setFilter('all', this)">TẤT CẢ LOGS</button>
                        <button class="filter-btn" onclick="setFilter('system', this)">⚙️ HỆ THỐNG (INFO)</button>
                        <button class="filter-btn" onclick="setFilter('command', this)">💻 LỆNH & ĐIỀU KHIỂN</button>
                        <button class="filter-btn" onclick="setFilter('chat', this)">💬 CHAT GAME</button>
                        <button class="filter-btn" onclick="setFilter('plugins', this)">📦 PLUGINS</button>
                        <button class="filter-btn" onclick="setFilter('error', this)">⚠️ LỖI/WARN</button>
                        <button class="filter-btn" onclick="setFilter('playit', this)">🌐 PLAYIT</button>
                        <button class="filter-btn" onclick="setFilter('monitor', this)">📊 GIÁM SÁT</button>
                    </div>
                    <button class="btn-copy-logs" onclick="copyAllLogs()">📋 Copy Toàn Bộ Logs</button>
                </div>
                
                <div class="console-main-frame">
                    <div class="console-box">
                        <div id="logs-output">Đang đồng bộ luồng dữ liệu dữ liệu log...</div>
                        <div class="cmd-container">
                            <div id="autocomplete-box"></div>
                            <div class="cmd-input-group">
                                <input type="text" id="cmd-input" placeholder="Nhập lệnh hoặc gõ văn bản tự do để chat vào game..." autocomplete="off">
                                <button id="btn-send" onclick="sendCmd()">Gửi Lệnh</button>
                            </div>
                        </div>
                    </div>

                    <div class="quick-panel">
                        <h3>⚡ Điều Khiển Nhanh</h3>
                        
                        <div class="cmd-group">
                            <div class="cmd-group-title">Hệ thống & Hiệu năng</div>
                            <button class="btn-quick" onclick="sendQuickCmd('tps')">📊 Kiểm tra hiệu năng (/tps)</button>
                            <button class="btn-quick" onclick="sendQuickCmd('version')">ℹ️ Phiên bản Server (/version)</button>
                            <button class="btn-quick" onclick="sendQuickCmd('save-all')">💾 Lưu dữ liệu nhanh (/save-all)</button>
                            <button class="btn-quick" onclick="sendQuickCmd('reload confirm')" style="color: #ffca28;">🔄 Nạp lại cấu hình (/reload)</button>
                        </div>

                        <div class="cmd-group">
                            <div class="cmd-group-title">Môi trường thế giới</div>
                            <button class="btn-quick" onclick="sendQuickCmd('time set day')">☀️ Đặt thời gian: Ban Ngày</button>
                            <button class="btn-quick" onclick="sendQuickCmd('time set night')">🌙 Đặt thời gian: Ban Đêm</button>
                            <button class="btn-quick" onclick="sendQuickCmd('weather clear')">☀️ Thời tiết: Trời trong xanh</button>
                            <button class="btn-quick" onclick="sendQuickCmd('weather storm')">⛈️ Thời tiết: Mưa giông bão</button>
                        </div>

                        <div class="cmd-group">
                            <div class="cmd-group-title">Thành viên & Tiện ích</div>
                            <button class="btn-quick" onclick="sendQuickCmd('list')">👥 Danh sách người chơi (/list)</button>
                            <button class="btn-quick" onclick="sendQuickCmd('plugins')">📦 Kiểm tra Plugins (/plugins)</button>
                            <button class="btn-quick" onclick="sendQuickCmd('seed')">🌱 Xem mã Seed thế giới (/seed)</button>
                            <button class="btn-quick" onclick="sendQuickCmd('whitelist list')">📜 Danh sách Whitelist</button>
                        </div>
                    </div>
                </div>
            </div>

            <script>
                let currentFilter = 'all';
                const commandList = [
                    "stop", "reload", "plugins", "version", "seed", "whitelist on", "whitelist off", "whitelist add ", "whitelist list",
                    "op ", "deop ", "gamemode creative ", "gamemode survival ", "gamemode adventure ", "gamemode spectator ",
                    "time set day", "time set night", "weather clear", "weather rain", "difficulty peaceful", "difficulty easy", "difficulty hard",
                    "mv list", "mv info", "mv tp ", "tps", "save-all"
                ];
                let selectedSuggestIndex = -1;

                function setFilter(filterType, btnElem) {
                    currentFilter = filterType;
                    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
                    btnElem.classList.add('active');
                    renderLogs();
                }

                let rawLogsData = [];
                function fetchLogs() {
                    fetch('/api/logs')
                    .then(res => res.json())
                    .then(data => {
                        rawLogsData = data.logs;
                        renderLogs();
                    });
                }

                function renderLogs() {
                    const el = document.getElementById('logs-output');
                    const isAtBottom = el.scrollHeight - el.clientHeight <= el.scrollTop + 60;
                    
                    let htmlContent = "";
                    rawLogsData.forEach(item => {
                        if (currentFilter === 'all' || item.type === currentFilter) {
                            htmlContent += `<div class="log-item log-${item.type}">[${item.time}] ${item.text}</div>`;
                        }
                    });
                    
                    el.innerHTML = htmlContent || "<div style='color: var(--text-dark-gray);'>Không có bản ghi nào thuộc tab này...</div>";
                    if (isAtBottom) el.scrollTop = el.scrollHeight;
                }

                function sendCmd() {
                    const input = document.getElementById('cmd-input');
                    const val = input.value.trim();
                    if(!val) return;
                    executeCommandApi(val);
                    input.value = '';
                    closeAutocomplete();
                }

                function sendQuickCmd(cmdStr) {
                    executeCommandApi(cmdStr);
                }

                function executeCommandApi(cmdStr) {
                    fetch('/api/command', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({command: cmdStr})
                    }).then(res => res.json()).then(data => {
                        if(data.status === 'error') alert(data.message);
                        fetchLogs();
                    });
                }

                function copyAllLogs() {
                    if (rawLogsData.length === 0) {
                        alert("Không có dữ liệu log nào để sao chép!");
                        return;
                    }
                    let textToCopy = rawLogsData.map(item => `[${item.time}] [${item.type.toUpperCase()}] ${item.text}`).join('\\n');
                    navigator.clipboard.writeText(textToCopy).then(() => {
                        alert("🎉 Đã copy toàn bộ logs vào bộ nhớ tạm!");
                    }).catch(err => {
                        alert("Lỗi khi sao chép logs: " + err);
                    });
                }

                const inputField = document.getElementById('cmd-input');
                const suggestBox = document.getElementById('autocomplete-box');

                inputField.addEventListener('input', function() {
                    let text = this.value;
                    if (text.startsWith('/')) text = text.substring(1);
                    if (!text) {
                        closeAutocomplete();
                        return;
                    }

                    const filtered = commandList.filter(c => c.startsWith(text.toLowerCase()));
                    if (filtered.length > 0) {
                        suggestBox.innerHTML = "";
                        filtered.forEach((cmd, idx) => {
                            const div = document.createElement('div');
                            div.className = "suggest-item";
                            div.innerText = (inputField.value.startsWith('/') ? '/' : '') + cmd;
                            div.addEventListener('click', function() {
                                inputField.value = div.innerText;
                                inputField.focus();
                                closeAutocomplete();
                            });
                            suggestBox.appendChild(div);
                        });
                        suggestBox.style.display = "block";
                    } else {
                        closeAutocomplete();
                    }
                    selectedSuggestIndex = -1;
                });

                inputField.addEventListener('keydown', function(e) {
                    const items = suggestBox.querySelectorAll('.suggest-item');
                    if (suggestBox.style.display === "block" && items.length > 0) {
                        if (e.key === "ArrowDown") {
                            e.preventDefault();
                            selectedSuggestIndex = (selectedSuggestIndex + 1) % items.length;
                            updateSelection(items);
                        } else if (e.key === "ArrowUp") {
                            e.preventDefault();
                            selectedSuggestIndex = (selectedSuggestIndex - 1 + items.length) % items.length;
                            updateSelection(items);
                        } else if (e.key === "Enter" && selectedSuggestIndex > -1) {
                            e.preventDefault();
                            items[selectedSuggestIndex].click();
                        } else if (e.key === "Tab" || e.key === "ArrowRight") {
                            e.preventDefault();
                            if (selectedSuggestIndex === -1) selectedSuggestIndex = 0;
                            inputField.value = items[selectedSuggestIndex].innerText;
                            closeAutocomplete();
                        }
                    } else if (e.key === "Enter") {
                        sendCmd();
                    }
                });

                function updateSelection(items) {
                    items.forEach((item, idx) => {
                        if (idx === selectedSuggestIndex) {
                            item.classList.add('selected');
                            item.scrollIntoView({ block: 'nearest' });
                        } else {
                            item.classList.remove('selected');
                        }
                    });
                }

                function closeAutocomplete() {
                    suggestBox.style.display = "none";
                }

                document.addEventListener('click', function(e) {
                    if (e.target !== inputField) closeAutocomplete();
                });
                setInterval(fetchLogs, 1500);
                fetchLogs();
            </script>
            {% endif %}

            {% if active_tab == 'files' %}
            <div class="fm-layout">
                <div class="card">
                    <h3>📁 Explorer: /data/{{ subpath }}</h3>
                    
                    <div class="fm-toolbar">
                        <div class="toolbar-left">
                            <button class="btn-tool" onclick="openCreateFolderModal()">➕ Thư mục</button>
                            <input type="text" id="download-url" class="input-text-style" style="width: 220px;" placeholder="Dán link tải file / GitHub...">
                            <input type="password" id="github-token" class="input-text-style" style="width: 120px;" placeholder="GitHub Token (Nếu có)">
                            <button class="btn-tool" style="background:#17a2b8;" onclick="downloadFromUrl()">🌐 Tải từ Link</button>
                        </div>

                        <div class="toolbar-right">
                            <form action="/api/fm/upload" method="POST" enctype="multipart/form-data" id="upload-form" style="display:flex; align-items:center; gap:5px;">
                                <input type="hidden" name="subpath" value="{{ subpath }}">
                                <input type="file" name="file" id="file-uploader-input" onchange="document.getElementById('upload-form').submit();" style="display: none;">
                                <button type="button" class="btn-tool" style="background:#007bff; padding: 6px 14px;" onclick="document.getElementById('file-uploader-input').click();" title="Upload File">📤</button>
                            </form>
                        </div>
                    </div>

                    <div class="table-wrapper">
                        <table class="fm-table">
                            <thead>
                                <tr>
                                    <th>Tên Tệp/Thư Mục</th>
                                    <th style="width: 90px;">Kích Thước</th>
                                    <th style="width: 260px; text-align: right;">Hành Động</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for item in items %}
                                <tr>
                                    <td>
                                        {% if item.is_dir and item.is_parent_link %}
                                            <a href="{{ item.path }}" class="file-link dir">↩️ {{ item.name }}</a>
                                        {% elif item.is_dir %}
                                            <a href="{{ item.path }}" class="file-link dir">📁 {{ item.name }}</a>
                                        {% else %}
                                            <a href="{{ item.path }}" class="file-link">📄 {{ item.name }}</a>
                                        {% endif %}
                                    </td>
                                    <td><span style="color:var(--text-muted);">{{ item.size }}</span></td>
                                    <td style="text-align: right;">
                                        <div class="actions">
                                            {% if not item.is_parent_link %}
                                                {% if item.is_dir %}
                                                    <button class="btn-action btn-zip" onclick="backupFolder('{{ item.raw_path }}', '{{ item.name }}')">Backup</button>
                                                {% else %}
                                                    <button class="btn-action btn-hash" onclick="openChecksumModal('{{ item.raw_path }}', '{{ item.name }}')">SHA</button>
                                                    <a href="/api/fm/download/{{ item.raw_path }}" class="btn-action btn-dl" target="_blank">Tải</a>
                                                    {% if item.name.endswith('.zip') %}
                                                        <button class="btn-action btn-unzip" onclick="unzipFile('{{ item.raw_path }}')">Nén</button>
                                                    {% endif %}
                                                {% endif %}
                                                <button class="btn-action btn-ren" onclick="openRenameModal('{{ item.raw_path }}', '{{ item.name }}')">Sửa</button>
                                                <button class="btn-action btn-del" onclick="openDeleteModal('{{ item.raw_path }}', {{ 'true' if item.is_dir else 'false' }})">Xóa</button>
                                            {% endif %}
                                        </div>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="card">
                    <h3>📝 Biên Tập Văn Bản</h3>
                    {% if file_content is not none %}
                        <div class="editor-wrapper">
                            <p style="margin: 0 0 10px 0; font-size:13px; color:var(--text-muted);">Đang xem file: <strong style="color: var(--link-color);">/data/{{ edit_file_path }}</strong></p>
                            <form action="/api/fm/save" method="POST" style="flex: 1; display: flex; flex-direction: column; overflow: hidden;">
                                <input type="hidden" name="subpath" value="{{ edit_file_path }}">
                                <textarea id="editor-text" name="content">{{ file_content }}</textarea>
                                <button type="submit" class="btn-save">💾 Lưu thay đổi</button>
                            </form>
                        </div>
                    {% else %}
                        <p style="color: var(--text-dark-gray); text-align: center; padding-top: 150px; font-size:14px;">Bấm trực tiếp vào tên một file cấu hình hoặc văn bản để biên tập dữ liệu trực tuyến.</p>
                    {% endif %}
                </div>
            </div>

            <div id="inlineCustomModal" class="custom-modal-overlay" onclick="closeInlineModal(event)">
                <div class="custom-modal-box" id="modal-box-content"></div>
            </div>
            
            <script>
                function showInlineModal(htmlContent) {
                    const modal = document.getElementById('inlineCustomModal');
                    document.getElementById('modal-box-content').innerHTML = htmlContent;
                    modal.style.display = 'flex';
                }

                function closeInlineModal(e) {
                    if (e && e.target.id !== 'inlineCustomModal') return;
                    document.getElementById('inlineCustomModal').style.display = 'none';
                }
                
                function forceCloseModal() {
                    document.getElementById('inlineCustomModal').style.display = 'none';
                }

                function openCreateFolderModal() {
                    const html = `
                        <h4 class="custom-modal-title">➕ Tạo Thư Mục Mới</h4>
                        <div class="custom-modal-body">
                            <label>Nhập tên thư mục cần tạo:</label>
                            <input type="text" id="modal-folder-name" class="input-text-style" placeholder="Tên thư mục..." autofocus>
                        </div>
                        <div class="custom-modal-footer">
                            <button class="btn-tool" style="background:#6c757d;" onclick="forceCloseModal()">Hủy</button>
                            <button class="btn-tool" onclick="submitCreateFolder()">Xác nhận</button>
                        </div>
                    `;
                    showInlineModal(html);
                }

                function submitCreateFolder() {
                    const name = document.getElementById('modal-folder-name').value.trim();
                    if(!name) return alert("Vui lòng nhập tên thư mục!");
                    
                    fetch('/api/fm/mkdir', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ subpath: '{{ subpath }}', folder_name: name })
                    }).then(res => res.json()).then(data => {
                        if(data.status === 'success') location.reload();
                        else showStatusModal("Lỗi hệ thống", data.message, "error");
                    });
                }

                function openRenameModal(oldPath, oldName) {
                    const html = `
                        <h4 class="custom-modal-title">✏️ Đổi Tên Mục Dữ Liệu</h4>
                        <div class="custom-modal-body">
                            <label>Nhập tên mới:</label>
                            <input type="text" id="modal-rename-name" class="input-text-style" value="${oldName}" autofocus>
                        </div>
                        <div class="custom-modal-footer">
                            <button class="btn-tool" style="background:#6c757d;" onclick="forceCloseModal()">Hủy</button>
                            <button class="btn-tool" onclick="submitRenameItem('${oldPath}')">Thay đổi</button>
                        </div>
                    `;
                    showInlineModal(html);
                }

                function submitRenameItem(oldPath) {
                    const newName = document.getElementById('modal-rename-name').value.trim();
                    if(!newName) return;
                    fetch('/api/fm/rename', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ old_path: oldPath, new_name: newName })
                    }).then(res => res.json()).then(data => {
                        if(data.status === 'success') location.href = "/files/{{ subpath }}";
                        else showStatusModal("Lỗi đổi tên", data.message, "error");
                    });
                }

                function openDeleteModal(path, isDir) {
                    const msg = isDir ? "CẢNH BÁO: Hành động này sẽ xóa sạch thư mục?" : "Bạn có chắc chắn muốn xóa tệp tin này?";
                    const html = `
                        <h4 class="custom-modal-title" style="color:#dc3545;">⚠️ Xác Nhận Xóa</h4>
                        <div class="custom-modal-body">
                            <p>${msg}</p>
                            <p style="font-size:12px; color:var(--text-muted); font-family:monospace;">Mục: ${path}</p>
                        </div>
                        <div class="custom-modal-footer">
                            <button class="btn-tool" style="background:#6c757d;" onclick="forceCloseModal()">Hủy</button>
                            <button class="btn-tool" style="background:#dc3545;" onclick="submitDeleteItem('${path}')">Xóa ngay</button>
                        </div>
                    `;
                    showInlineModal(html);
                }

                function submitDeleteItem(path) {
                    fetch('/api/fm/delete', { 
                        method: 'DELETE',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ filepath: path })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'success') location.reload();
                        else showStatusModal("Lỗi xóa", data.message, "error");
                    });
                }

                function openChecksumModal(path, name) {
                    const html = `
                        <h4 class="custom-modal-title">🔍 Kiểm Tra Checksum SHA-256</h4>
                        <div class="custom-modal-body">
                            <p>Kiểm tra tính toàn vẹn của file: <strong>${name}</strong></p>
                            <label>Dán mã SHA-256 đối chiếu chuẩn:</label>
                            <input type="text" id="modal-checksum-input" class="input-text-style" placeholder="Nhập chuỗi băm 64 ký tự..." autofocus>
                        </div>
                        <div class="custom-modal-footer">
                            <button class="btn-tool" style="background:#6c757d;" onclick="forceCloseModal()">Hủy</button>
                            <button class="btn-tool" onclick="submitVerifyChecksum('${path}')">Kiểm tra</button>
                        </div>
                    `;
                    showInlineModal(html);
                }

                function submitVerifyChecksum(path) {
                    const expectedChecksum = document.getElementById('modal-checksum-input').value.trim();
                    if (!expectedChecksum) return;

                    showInlineModal(`
                        <h4 class="custom-modal-title">⚙️ Đang Tính Toán Checksum</h4>
                        <div class="custom-modal-body">
                            <p>Hệ thống đang quét cấu trúc dữ liệu tệp tin và đối chiếu mã băm...</p>
                        </div>
                    `);

                    fetch('/api/fm/checksum', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ filepath: path, expected_checksum: expectedChecksum.toLowerCase() })
                    })
                    .then(res => res.json())
                    .then(data => {
                        let colorTitle = data.status === 'success' ? '#28a745' : '#dc3545';
                        let prefix = data.status === 'success' ? '✅' : '❌';
                        const resHtml = `
                            <h4 class="custom-modal-title" style="color:${colorTitle};">${prefix} Kết Quả Đối Chiếu</h4>
                            <div class="custom-modal-body">
                                <p><strong>${data.message}</strong></p>
                                <p style="font-size:12px; margin-bottom:5px;">Mã SHA-256 thực tế trên đĩa:</p>
                                <div class="modal-log-area" style="color:#00ff00;">${data.calculated}</div>
                            </div>
                            <div class="custom-modal-footer">
                                <button class="btn-tool" onclick="forceCloseModal()">Đóng</button>
                            </div>
                        `;
                        showInlineModal(resHtml);
                    })
                    .catch(err => showStatusModal("Lỗi", err, "error"));
                }

                function showStatusModal(title, text, type="success") {
                    let titleColor = type === 'success' ? '#28a745' : '#dc3545';
                    const html = `
                        <h4 class="custom-modal-title" style="color:${titleColor};">${title}</h4>
                        <div class="custom-modal-body">
                            <p>${text}</p>
                        </div>
                        <div class="custom-modal-footer">
                            <button class="btn-tool" onclick="forceCloseModal()">Đóng</button>
                        </div>
                    `;
                    showInlineModal(html);
                }

                function downloadFromUrl() {
                    const urlInput = document.getElementById('download-url');
                    const tokenInput = document.getElementById('github-token');
                    const urlStr = urlInput.value.trim();
                    const tokenStr = tokenInput.value.trim();
                    if (!urlStr) return;

                    let logTexts = "Đang kết nối tới máy chủ tải file...\\n";
                    showInlineModal(`
                        <h4 class="custom-modal-title">🌐 Tiến Trình Tải File Trực Tuyến</h4>
                        <div class="custom-modal-body">
                            <div class="modal-log-area" id="modal-download-logs">${logTexts}</div>
                        </div>
                        <div class="custom-modal-footer" id="modal-download-footer">
                            <button class="btn-tool" style="background:#6c757d;" disabled>Đang chạy...</button>
                        </div>
                    `);

                    const logBox = document.getElementById('modal-download-logs');
                    
                    setTimeout(() => {
                        logTexts += "Đang lấy thông tin kích thước...\\n";
                        logBox.innerText = logTexts;
                    }, 800);

                    fetch('/api/fm/download-from-url', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ subpath: '{{ subpath }}', url: urlStr, token: tokenStr })
                    })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'success') {
                            logTexts += `Tải hoàn tất thành công!\\n`;
                            logBox.innerText = logTexts;

                            let isZipFile = urlStr.split('?')[0].endsWith('.zip') && !data.message.includes('đã giải nén');

                            if (isZipFile) {
                                logTexts += `\\nPhát hiện tệp nén .ZIP! Bạn có muốn giải nén tự động không?\\n`;
                                logBox.innerText = logTexts;
                                const cleanUrlName = urlStr.split('?')[0].split('/').pop();
                                const fileRawPath = ('{{ subpath }}' ? '{{ subpath }}/' : '') + cleanUrlName;

                                document.getElementById('modal-download-footer').innerHTML = `
                                    <button class="btn-tool" style="background:#fd7e14;" onclick="triggerInlineUnzip('${fileRawPath}')">🔓 Giải nén luôn</button>
                                    <button class="btn-tool" style="background:#28a745;" onclick="location.reload()">Bỏ qua & Đóng</button>
                                `;
                            } else {
                                document.getElementById('modal-download-footer').innerHTML = `
                                    <button class="btn-tool" onclick="location.reload()">ĐỒNG Ý & ĐÓNG</button>
                                `;
                            }
                        } else {
                            logTexts += `❌ THẤT BẠI: ${data.message}\\n`;
                            logBox.innerText = logTexts;
                            document.getElementById('modal-download-footer').innerHTML = `
                                <button class="btn-tool" style="background:#dc3545;" onclick="forceCloseModal()">Đóng</button>
                            `;
                        }
                    })
                    .catch(err => {
                        logTexts += `❌ LỖI KẾT NỐI: ${err}\\n`;
                        logBox.innerText = logTexts;
                        document.getElementById('modal-download-footer').innerHTML = `
                            <button class="btn-tool" style="background:#dc3545;" onclick="forceCloseModal()">Đóng</button>
                        `;
                    });
                }

                function triggerInlineUnzip(path) {
                    const logBox = document.getElementById('modal-download-logs');
                    logBox.innerText = logBox.innerText + "\\nĐang tiến hành giải nén...\\n";
                    
                    fetch('/api/fm/unzip', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ filepath: path })
                    }).then(res => res.json()).then(data => {
                        if(data.status === 'success') {
                            logBox.innerText = logBox.innerText + "Đã giải nén toàn bộ tệp tin thành công!\\n";
                        } else {
                            logBox.innerText = logBox.innerText + `Lỗi giải nén: ${data.message}\\n`;
                        }
                        document.getElementById('modal-download-footer').innerHTML = `
                            <button class="btn-tool" onclick="location.reload()">ĐÓNG</button>
                        `;
                    });
                }

                function backupFolder(dirPath, folderName) {
                    showInlineModal(`
                        <h4 class="custom-modal-title">📦 Tiến Trình Backup</h4>
                        <div class="custom-modal-body">
                            <p>Hệ thống đang tiến hành nén thư mục <strong>${folderName}</strong>...</p>
                        </div>
                    `);
                    fetch('/api/fm/backup', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ folder_path: dirPath, folder_name: folderName })
                    }).then(res => res.json()).then(data => {
                        if(data.status === 'success') {
                            showStatusModal("Thành công", "Đã tạo bản sao lưu ZIP thành công!", "success");
                            setTimeout(() => location.reload(), 1200);
                        } else showStatusModal("Lỗi sao lưu", data.message, "error");
                    });
                }

                function unzipFile(path) {
                    showInlineModal(`
                        <h4 class="custom-modal-title">🔓 Tiến Trình Giải Nén</h4>
                        <div class="custom-modal-body">
                            <p>Đang tiến hành giải nén tệp tin...</p>
                        </div>
                    `);
                    fetch('/api/fm/unzip', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ filepath: path })
                    }).then(res => res.json()).then(data => {
                        if(data.status === 'success') {
                            showStatusModal("Thành công", "Đã rã nén toàn bộ gói dữ liệu!", "success");
                            setTimeout(() => location.reload(), 1200);
                        } else showStatusModal("Lỗi giải nén", data.message, "error");
                    });
                }
            </script>
            {% endif %}
        </div>

        <script>
            function applyThemeEngine() {
                const mode = localStorage.getItem('panel-theme-mode') || 'dark';
                document.querySelectorAll('.theme-btn').forEach(btn => btn.classList.remove('active'));
                const targetBtn = document.getElementById('theme-' + mode);
                if(targetBtn) targetBtn.classList.add('active');

                if (mode === 'auto') {
                    const currentHour = new Date().getHours();
                    if (currentHour >= 6 && currentHour < 18) {
                        document.documentElement.setAttribute('data-theme', 'light');
                    } else {
                        document.documentElement.setAttribute('data-theme', 'dark');
                    }
                } else {
                    document.documentElement.setAttribute('data-theme', mode);
                }
                if (typeof renderLogs === "function") renderLogs();
            }

            function changeThemeMode(newMode) {
                localStorage.setItem('panel-theme-mode', newMode);
                applyThemeEngine();
            }

            applyThemeEngine();
            setInterval(() => {
                if(localStorage.getItem('panel-theme-mode') === 'auto') applyThemeEngine();
            }, 60000);

            function measureBrowserPing() {
                const startTime = performance.now();
                fetch('/api/ping')
                    .then(res => res.json())
                    .then(data => {
                        const endTime = performance.now();
                        const pingTime = Math.round(endTime - startTime);
                        const pingElem = document.getElementById('ping-display');
                        if (pingElem) {
                            pingElem.innerText = pingTime + " ms";
                            if (pingTime < 80) pingElem.style.color = "#28a745";
                            else if (pingTime < 200) pingElem.style.color = "#ffca28";
                            else pingElem.style.color = "#dc3545";
                        }
                    })
                    .catch(err => {
                        const pingElem = document.getElementById('ping-display');
                        if (pingElem) {
                            pingElem.innerText = "Lỗi";
                            pingElem.style.color = "#dc3545";
                        }
                    });
            }
            measureBrowserPing();
            setInterval(measureBrowserPing, 5000);
        </script>
    </body>
    </html>
    """
    return render_template_string(main_html, active_tab=active_tab, stats=stats_data, items=formatted_items, subpath=subpath, file_content=file_content, edit_file_path=edit_file_path)


# --- CÁC API PHỤ TRỢ FILE MANAGER ---

@app.route("/api/fm/download-from-url", methods=["POST"])
def fm_download_from_url():
    subpath = request.json.get("subpath", "")
    url = request.json.get("url", "").strip()
    token = request.json.get("token", "").strip()
    
    if not url:
        return jsonify({"status": "error", "message": "Đường dẫn URL trống!"})
        
    target_dir = os.path.join(BASE_DATA_DIR, subpath)
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return jsonify({"status": "error", "message": "Thư mục đích không hợp lệ!"})

    github_api_url = None
    if "github.com" in url and "/artifacts/" in url:
        match = re.search(r"github\.com/([^/]+)/([^/]+)/actions/runs/[^/]+/artifacts/(\d+)", url)
        if match:
            owner, repo, artifact_id = match.groups()
            github_api_url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/zip"

    try:
        clean_url = url.split('?')[0]
        is_direct_jar = clean_url.endswith('.jar')

        if github_api_url:
            filename = f"github_artifact_{int(time.time())}.zip"
            download_url = github_api_url
        else:
            filename = os.path.basename(clean_url)
            if not filename or '.' not in filename:
                filename = f"downloaded_file_{int(time.time())}.jar" if is_direct_jar else f"downloaded_file_{int(time.time())}.zip"
            download_url = url
            
        destination_path = os.path.join(target_dir, filename)
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        if token:
            headers['Authorization'] = f"Bearer {token}"

        req = urllib.request.Request(download_url, headers=headers)
        with urllib.request.urlopen(req) as response, open(destination_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)

        is_zip = False
        try:
            is_zip = zipfile.is_zipfile(destination_path)
        except Exception:
            pass

        if is_zip:
            if is_direct_jar or filename.endswith('.jar'):
                return jsonify({"status": "success", "message": f"Đã tải file '{filename}' thành công!"})

            extracted_jars = []
            with zipfile.ZipFile(destination_path, 'r') as zip_ref:
                for zip_info in zip_ref.infolist():
                    if zip_info.filename.endswith('.jar'):
                        base_jar_name = os.path.basename(zip_info.filename)
                        if base_jar_name:
                            target_jar_path = os.path.join(target_dir, base_jar_name)
                            with zip_ref.open(zip_info) as source, open(target_jar_path, "wb") as target_file:
                                shutil.copyfileobj(source, target_file)
                            extracted_jars.append(base_jar_name)
            
            os.remove(destination_path)
            if extracted_jars:
                return jsonify({"status": "success", "message": f"Đã giải nén các plugin: {', '.join(extracted_jars)}"})
            else:
                return jsonify({"status": "error", "message": "Không tìm thấy file .jar trong file ZIP."})

        return jsonify({"status": "success", "message": f"Đã tải file '{filename}' thành công!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/fm/checksum", methods=["POST"])
def fm_checksum():
    filepath = request.json.get("filepath", "")
    expected_checksum = request.json.get("expected_checksum", "").strip().lower()
    full_path = os.path.join(BASE_DATA_DIR, filepath)
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return jsonify({"status": "error", "message": "Tập tin không hợp lệ"})

    try:
        sha256_hash = hashlib.sha256()
        with open(full_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        calculated_sha = sha256_hash.hexdigest().lower()

        if calculated_sha == expected_checksum:
            return jsonify({"status": "success", "message": "Mã SHA-256 trùng khớp hoàn hảo.", "calculated": calculated_sha})
        else:
            return jsonify({"status": "mismatch", "message": "Mã checksum KHÔNG trùng khớp!", "calculated": calculated_sha})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "calculated": ""})


@app.route("/api/fm/upload", methods=["POST"])
def fm_upload():
    subpath = request.form.get("subpath", "")
    target_dir = os.path.join(BASE_DATA_DIR, subpath)
    if "file" not in request.files:
        return "Yêu cầu không hợp lệ", 400
    file = request.files["file"]
    if file.filename == "":
        return "Chưa chọn file", 400
    if file:
        file.save(os.path.join(target_dir, file.filename))
    return redirect(f"/files/{subpath}" if subpath else "/files")


@app.route("/api/fm/download/<path:filepath>")
def fm_download(filepath):
    full_path = os.path.join(BASE_DATA_DIR, filepath)
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return "Tệp tin không tồn tại", 404
    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True)


@app.route("/api/fm/save", methods=["POST"])
def fm_save():
    subpath = request.form.get("subpath", "")
    content = request.form.get("content", "")
    full_path = os.path.join(BASE_DATA_DIR, subpath)
    if os.path.exists(full_path) and os.path.isfile(full_path):
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            parent_dir = os.path.dirname(subpath)
            return redirect(f"/files/{parent_dir}" if parent_dir else "/files")
        except Exception as e:
            return f"Không thể ghi: {e}", 500
    return "Không tìm thấy file", 404


@app.route("/api/fm/mkdir", methods=["POST"])
def fm_mkdir():
    subpath = request.json.get("subpath", "")
    folder_name = request.json.get("folder_name", "").strip()
    if not folder_name:
        return jsonify({"status": "error", "message": "Tên không hợp lệ"})
    target_dir = os.path.join(BASE_DATA_DIR, subpath, folder_name)
    try:
        if os.path.exists(target_dir):
            return jsonify({"status": "error", "message": "Thư mục đã tồn tại!"})
        os.makedirs(target_dir, exist_ok=True)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/fm/backup", methods=["POST"])
def fm_backup():
    folder_path = request.json.get("folder_path", "")
    folder_name = request.json.get("folder_name", "").strip()
    target_dir = os.path.join(BASE_DATA_DIR, folder_path)
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return jsonify({"status": "error", "message": "Thư mục không tồn tại"})
        
    zip_name = f"{folder_name}_backup_{datetime.datetime.now().strftime('%d%m%Y_%H%M%S')}.zip"
    zip_path = os.path.join(os.path.dirname(target_dir), zip_name)
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(target_dir):
                for file in files:
                    full_file_path = os.path.join(root, file)
                    arcname = os.path.join(folder_name, os.path.relpath(full_file_path, target_dir))
                    zipf.write(full_file_path, arcname)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/fm/unzip", methods=["POST"])
def fm_unzip():
    filepath = request.json.get("filepath", "")
    full_zip_path = os.path.join(BASE_DATA_DIR, filepath)
    if not os.path.exists(full_zip_path) or not os.path.isfile(full_zip_path):
        return jsonify({"status": "error", "message": "File nén không tồn tại"})
    try:
        with zipfile.ZipFile(full_zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.dirname(full_zip_path))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/fm/rename", methods=["POST"])
def fm_rename():
    old_path = request.json.get("old_path", "")
    new_name = request.json.get("new_name", "").strip()
    if not old_path or not new_name:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu"})
    full_old_path = os.path.join(BASE_DATA_DIR, old_path)
    full_new_path = os.path.join(os.path.dirname(full_old_path), new_name)
    try:
        if os.path.exists(full_new_path):
            return jsonify({"status": "error", "message": "Tên mới đã tồn tại"})
        os.rename(full_old_path, full_new_path)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/fm/delete", methods=["DELETE"])
def fm_delete():
    filepath = request.json.get("filepath", "")
    full_path = os.path.join(BASE_DATA_DIR, filepath)
    try:
        if os.path.exists(full_path):
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            return jsonify({"status": "success"})
        return jsonify({"status": "error", "message": "Không tìm thấy mục cần xóa"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


# --- ĐIỀU HƯỚNG LUỒNG KHỞI ĐỘNG HỆ THỐNG ---

threading.Thread(target=fetch_server_info, daemon=True).start()
threading.Thread(target=run_paper, daemon=True).start()
threading.Thread(target=run_playit, daemon=True).start()
threading.Thread(target=monitor_java, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860)