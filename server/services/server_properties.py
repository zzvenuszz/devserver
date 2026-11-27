"""Typed editing helpers for the persistent Minecraft server.properties file."""
import os
import re
import tempfile

from server.config import BASE_DATA_DIR


PROPERTIES_PATH = os.path.join(BASE_DATA_DIR, "server.properties")
DEFAULT_PROPERTIES = {
    "allow-flight": "false",
    "allow-nether": "true",
    "difficulty": "easy",
    "enable-command-block": "false",
    "enable-query": "false",
    "enable-rcon": "false",
    "enable-status": "true",
    "gamemode": "survival",
    "generate-structures": "true",
    "hardcore": "false",
    "level-name": "world",
    "max-players": "20",
    "motd": "A Minecraft Server",
    "online-mode": "false",
    "pvp": "true",
    "server-ip": "",
    "server-port": "25565",
    "simulation-distance": "10",
    "spawn-protection": "16",
    "view-distance": "10",
    "white-list": "false",
}

ENUM_OPTIONS = {
    "difficulty": ["peaceful", "easy", "normal", "hard"],
    "gamemode": ["survival", "creative", "adventure", "spectator"],
    "level-type": [
        "normal", "flat", "large_biomes", "amplified", "single_biome_surface",
        "buffet", "default_1_1", "customized", "minecraft:normal", "minecraft:flat",
        "minecraft:large_biomes", "minecraft:amplified", "minecraft:single_biome_surface",
    ],
    "region-file-compression": ["deflate", "lz4", "none", "gzip"],
}

BOOLEAN_DESCRIPTIONS = {
    "accept-transfers": "Cho phép người chơi được chuyển tới server này bằng lệnh hoặc gói transfer.",
    "allow-flight": "Không kick người chơi nếu server phát hiện họ đang bay trong chế độ sinh tồn.",
    "allow-nether": "Cho phép tạo và vào Nether.",
    "broadcast-console-to-ops": "Gửi kết quả lệnh console tới các operator đang online.",
    "broadcast-rcon-to-ops": "Gửi kết quả lệnh RCON tới các operator đang online.",
    "debug": "Bật thông tin debug chi tiết của server.",
    "enable-code-of-conduct": "Hiển thị quy tắc ứng xử từ thư mục codeofconduct cho người chơi.",
    "enable-command-block": "Cho phép command block thực thi lệnh.",
    "enable-jmx-monitoring": "Mở các số liệu tick của server qua JMX.",
    "enable-query": "Bật giao thức GameSpy4 để công cụ bên ngoài truy vấn thông tin server.",
    "enable-rcon": "Bật điều khiển console từ xa qua RCON.",
    "enable-status": "Cho server xuất hiện online trong danh sách multiplayer và trả lời truy vấn trạng thái.",
    "enforce-secure-profile": "Chỉ cho phép người chơi có khóa profile được Mojang ký kết nối.",
    "enforce-whitelist": "Kick người chơi không nằm trong whitelist.",
    "force-gamemode": "Đưa người chơi về gamemode mặc định mỗi khi họ vào server.",
    "generate-structures": "Tạo công trình tự nhiên như làng và đền trong thế giới mới.",
    "hardcore": "Bật chế độ hardcore; người chơi chuyển sang spectator khi chết.",
    "hide-online-players": "Ẩn danh sách người chơi trong gói trạng thái server.",
    "log-ips": "Ghi địa chỉ IP người chơi vào log server.",
    "management-server-enabled": "Bật giao thức quản lý Minecraft để công cụ bên ngoài điều khiển server.",
    "management-server-tls-enabled": "Yêu cầu TLS cho giao thức quản lý Minecraft.",
    "online-mode": "Xác thực tài khoản với dịch vụ Minecraft. Tắt chế độ này cho phép kết nối không xác thực.",
    "pvp": "Cho phép người chơi gây sát thương cho người chơi khác.",
    "prevent-proxy-connections": "Từ chối kết nối có thông tin nhà mạng khác với máy chủ xác thực Mojang.",
    "require-resource-pack": "Bắt buộc người chơi chấp nhận resource pack của server.",
    "sync-chunk-writes": "Ghi chunk đồng bộ xuống đĩa; Paper mặc định có thể bỏ qua cài đặt này.",
    "use-native-transport": "Dùng network transport gốc trên Linux để cải thiện hiệu năng mạng.",
    "white-list": "Chỉ cho phép người chơi có tên trong whitelist tham gia.",
}

NUMBER_DESCRIPTIONS = {
    "chat-spam-threshold-seconds": "Ngưỡng chống spam chat; đặt 0 để tắt.",
    "command-spam-threshold-seconds": "Ngưỡng chống spam lệnh; đặt 0 để tắt.",
    "entity-broadcast-range-percentage": "Tầm gửi entity tới người chơi, tính theo phần trăm mặc định (10–1000).",
    "function-permission-level": "Cấp quyền mặc định cho lệnh trong datapack function (1–4).",
    "management-server-port": "Cổng giao thức quản lý Minecraft; 0 để chọn cổng tự động.",
    "max-chained-neighbor-updates": "Giới hạn cập nhật khối dây chuyền liên tiếp; số âm để bỏ giới hạn.",
    "max-players": "Số người chơi tối đa được phép online cùng lúc.",
    "max-tick-time": "Thời gian tick tối đa tính bằng mili giây trước khi watchdog dừng server; -1 để tắt watchdog.",
    "max-world-size": "Bán kính tối đa của vùng thế giới được tạo.",
    "network-compression-threshold": "Số byte tối thiểu của gói tin trước khi nén; số âm để tắt nén.",
    "op-permission-level": "Cấp quyền mặc định cho operator (0–4).",
    "pause-when-empty-seconds": "Số giây chờ trước khi tạm dừng khi không có người chơi; -1 để tắt.",
    "player-idle-timeout": "Kick người chơi đứng yên sau số phút này; 0 để tắt.",
    "query.port": "Cổng dùng cho giao thức GameSpy4 query.",
    "rate-limit": "Số gói tin tối đa mỗi giây trước khi người chơi bị kick; 0 để tắt.",
    "rcon.port": "Cổng dùng cho RCON.",
    "server-port": "Cổng TCP Minecraft mà server lắng nghe.",
    "simulation-distance": "Khoảng cách mô phỏng entity, tính bằng chunk (3–32).",
    "spawn-protection": "Bán kính bảo vệ khu vực spawn; 0 để tắt.",
    "status-heartbeat-interval": "Chu kỳ gửi heartbeat của giao thức quản lý; 0 để tắt.",
    "text-filtering-version": "Phiên bản định dạng cho cấu hình lọc chat.",
    "view-distance": "Khoảng cách chunk server gửi tới người chơi; ảnh hưởng tải mạng và RAM.",
}

TEXT_DESCRIPTIONS = {
    "bug-report-link": "URL mở từ nút báo lỗi trong menu liên kết server.",
    "generator-settings": "Chuỗi JSON tùy chỉnh cách tạo thế giới.",
    "initial-disabled-packs": "Danh sách datapack ngăn tự bật khi tạo thế giới, phân tách bằng dấu phẩy.",
    "initial-enabled-packs": "Danh sách datapack bật khi tạo thế giới, phân tách bằng dấu phẩy.",
    "level-name": "Tên thư mục thế giới được tải và lưu trên đĩa.",
    "level-seed": "Seed tạo thế giới; để trống để chọn ngẫu nhiên.",
    "management-server-host": "Địa chỉ bind của giao thức quản lý Minecraft.",
    "management-server-secret": "Mã bí mật xác thực giao thức quản lý Minecraft.",
    "management-server-tls-keystore": "Đường dẫn tới TLS keystore cho giao thức quản lý.",
    "management-server-tls-keystore-password": "Mật khẩu TLS keystore; có thể cấu hình qua biến môi trường hoặc JVM.",
    "motd": "Dòng giới thiệu hiển thị dưới tên server trong danh sách multiplayer. Tối đa 59 ký tự.",
    "rcon.password": "Mật khẩu kết nối RCON; chỉ đặt khi đã bật enable-rcon.",
    "resource-pack": "URL tải resource pack của server.",
    "resource-pack-id": "UUID định danh resource pack.",
    "resource-pack-prompt": "Thông báo hiển thị khi yêu cầu người chơi tải resource pack.",
    "resource-pack-sha1": "SHA-1 của resource pack để người chơi kiểm tra file tải về.",
    "server-ip": "Địa chỉ IP bind. Để trống để lắng nghe trên mọi giao diện mạng.",
    "text-filtering-config": "Đường dẫn file cấu hình lọc nội dung chat; để trống để tắt.",
}

ENUM_LABELS = {
    "difficulty": "Độ khó",
    "gamemode": "Chế độ chơi mặc định",
    "level-type": "Kiểu tạo thế giới",
    "region-file-compression": "Nén file vùng",
}

NUMBER_BOUNDS = {
    "entity-broadcast-range-percentage": (10, 1000),
    "function-permission-level": (1, 4),
    "management-server-port": (0, 65535),
    "max-players": (1, 1000000),
    "max-tick-time": (-1, 2147483647),
    "max-world-size": (1, 29999984),
    "chat-spam-threshold-seconds": (0, 2147483647),
    "command-spam-threshold-seconds": (0, 2147483647),
    "network-compression-threshold": (-2147483648, 2147483647),
    "op-permission-level": (0, 4),
    "pause-when-empty-seconds": (-1, 2147483647),
    "player-idle-timeout": (0, 2147483647),
    "query.port": (1, 65535),
    "rcon.port": (1, 65535),
    "status-heartbeat-interval": (0, 2147483647),
    "server-port": (1, 65535),
    "simulation-distance": (3, 32),
    "spawn-protection": (0, 2147483647),
    "view-distance": (3, 32),
    "text-filtering-version": (0, 1),
}

TEXT_LENGTHS = {
    "motd": 59,
    "level-name": 255,
    "server-ip": 255,
    "management-server-host": 255,
    "management-server-secret": 40,
    "management-server-tls-keystore-password": 1024,
    "rcon.password": 1024,
    "resource-pack": 2048,
    "resource-pack-prompt": 256,
    "resource-pack-sha1": 40,
    "bug-report-link": 2048,
}


def ensure_server_properties():
    """Create defaults or add the requested offline/whitelist defaults if absent."""
    os.makedirs(BASE_DATA_DIR, exist_ok=True)
    if not os.path.exists(PROPERTIES_PATH):
        lines = [f"{key}={value}" for key, value in DEFAULT_PROPERTIES.items()]
        _atomic_write("\n".join(lines) + "\n")
        return

    with open(PROPERTIES_PATH, "r", encoding="utf-8", errors="replace") as source:
        lines = source.read().splitlines()
    existing = {key for line in lines if (key := _property_key(line)) is not None}
    added = [f"{key}={DEFAULT_PROPERTIES[key]}" for key in ("white-list", "online-mode") if key not in existing]
    if added:
        lines.extend(added)
        _atomic_write("\n".join(lines) + "\n")


def _property_key(line):
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", "!")) or "=" not in stripped:
        return None
    key = stripped.split("=", 1)[0].strip()
    return key or None


def _property_metadata(key, value):
    if key in BOOLEAN_DESCRIPTIONS:
        return {
            "type": "boolean",
            "label": key,
            "description": BOOLEAN_DESCRIPTIONS.get(key, "Bật hoặc tắt cài đặt này."),
            "maxLength": 5,
        }
    if key in ENUM_OPTIONS:
        options = ENUM_OPTIONS[key]
        if value and value not in options:
            options = [*options, value]
        return {
            "type": "enum",
            "label": ENUM_LABELS.get(key, key),
            "description": TEXT_DESCRIPTIONS.get(key, "Chọn một giá trị được server hỗ trợ."),
            "options": options,
            "maxLength": 128,
        }
    if key in NUMBER_DESCRIPTIONS:
        minimum, maximum = NUMBER_BOUNDS.get(key, (-2147483648, 2147483647))
        return {
            "type": "number",
            "label": key,
            "description": NUMBER_DESCRIPTIONS.get(key, "Giá trị số của cài đặt này."),
            "min": minimum,
            "max": maximum,
            "maxLength": 16,
        }
    if key in TEXT_DESCRIPTIONS:
        return {
            "type": "text",
            "label": key,
            "description": TEXT_DESCRIPTIONS[key],
            "maxLength": TEXT_LENGTHS.get(key, 1024),
        }
    if value.lower() in ("true", "false"):
        return {
            "type": "boolean",
            "label": key,
            "description": "Bật hoặc tắt cài đặt này.",
            "maxLength": 5,
        }
    if re.fullmatch(r"-?\d+", value):
        minimum, maximum = NUMBER_BOUNDS.get(key, (-2147483648, 2147483647))
        return {
            "type": "number",
            "label": key,
            "description": "Giá trị số của cài đặt này.",
            "min": minimum,
            "max": maximum,
            "maxLength": 16,
        }
    return {
        "type": "text",
        "label": key,
        "description": TEXT_DESCRIPTIONS.get(key, "Cài đặt dạng văn bản. Có thể để trống nếu server cho phép."),
        "maxLength": TEXT_LENGTHS.get(key, 1024),
    }


def get_server_properties():
    ensure_server_properties()
    entries = {}
    with open(PROPERTIES_PATH, "r", encoding="utf-8", errors="replace") as source:
        for line in source:
            key = _property_key(line)
            if key is None:
                continue
            value = line.strip().split("=", 1)[1]
            entries[key] = {"key": key, "value": value, **_property_metadata(key, value)}
    return list(entries.values())


def _atomic_write(content):
    directory = os.path.dirname(PROPERTIES_PATH)
    fd, temporary_path = tempfile.mkstemp(prefix="server.properties.", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, PROPERTIES_PATH)
    except Exception:
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise


def save_server_properties(values):
    ensure_server_properties()
    submitted = {}
    for item in values:
        key = str(item.get("key", ""))
        value = str(item.get("value", ""))
        if not re.fullmatch(r"[A-Za-z0-9._-]+", key):
            raise ValueError(f"Tên cài đặt không hợp lệ: {key}")
        if "\n" in value or "\r" in value:
            raise ValueError(f"Giá trị của {key} không được chứa xuống dòng")
        metadata = _property_metadata(key, value)
        if len(value) > metadata["maxLength"]:
            raise ValueError(f"Giá trị {key} vượt quá {metadata['maxLength']} ký tự")
        if metadata["type"] == "boolean" and value.lower() not in ("true", "false"):
            raise ValueError(f"{key} chỉ nhận true hoặc false")
        if metadata["type"] == "number":
            try:
                number = int(value)
            except ValueError as exc:
                raise ValueError(f"{key} phải là số nguyên") from exc
            if not metadata["min"] <= number <= metadata["max"]:
                raise ValueError(f"{key} phải nằm trong khoảng {metadata['min']} đến {metadata['max']}")
        if metadata["type"] == "enum" and value not in metadata["options"]:
            raise ValueError(f"Giá trị {value} không hợp lệ cho {key}")
        submitted[key] = value.lower() if metadata["type"] == "boolean" else value

    with open(PROPERTIES_PATH, "r", encoding="utf-8", errors="replace") as source:
        original_lines = source.read().splitlines()
    saved_keys = set()
    updated_lines = []
    for line in original_lines:
        key = _property_key(line)
        if key in submitted:
            updated_lines.append(f"{key}={submitted[key]}")
            saved_keys.add(key)
        else:
            updated_lines.append(line)
    for key, value in submitted.items():
        if key not in saved_keys:
            updated_lines.append(f"{key}={value}")
    _atomic_write("\n".join(updated_lines) + "\n")
    return get_server_properties()
