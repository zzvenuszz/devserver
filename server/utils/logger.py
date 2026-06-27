"""
Logging system - Quản lý logs với phân loại
"""
import datetime
import re
from server.config import state, Config


def add_log(msg, log_type="system"):
    """
    Phân loại log có cấu trúc để frontend dễ dàng lọc và tô màu
    
    Args:
        msg: Nội dung log message
        log_type: Loại log (system, monitor, playit, error, command, chat, plugins)
    """
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "time": timestamp,
        "type": log_type,
        "text": msg.strip()
    }
    print(f"[{log_type.upper()}] {msg.strip()}")
    state.logs.append(log_entry)
    
    # Giới hạn số lượng logs
    if len(state.logs) > Config.MAX_LOGS:
        state.logs.pop(0)


def parse_and_add_raw_log(line):
    """
    Phân tích tối ưu dựa trên dữ liệu log thực tế để phân loại chính xác vào các tab
    
    Args:
        line: Dòng log raw từ process output
    """
    line_str = line.strip()
    if not line_str:
        return

    # Loại bỏ ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    line_str = ansi_escape.sub('', line_str)

    log_type = "system"

    # Phân loại dựa trên nội dung
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

    # Parse Minecraft metrics from log
    try:
        from server.services.monitor import parse_tps_from_log, parse_mspt_from_log, parse_players_from_log
        parse_tps_from_log(line_str)
        parse_mspt_from_log(line_str)
        parse_players_from_log(line_str)
    except Exception:
        pass
