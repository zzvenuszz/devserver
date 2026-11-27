"""PaperMC version discovery and persistent server JAR downloads."""
import hashlib
import json
import os
import re
import threading
import urllib.request
import zipfile

from server.config import BASE_DATA_DIR, Config
from server.utils import add_log


API_ROOT = "https://fill.papermc.io/v3/projects/paper"
VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+){1,2}$")
_download_lock = threading.Lock()


def _api_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": Config.PAPERMC_USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise RuntimeError(payload.get("message", "PaperMC API returned an error"))
    return payload


def get_paper_versions():
    """Return all Minecraft versions currently published by PaperMC, newest first."""
    payload = _api_json(API_ROOT)
    grouped_versions = payload.get("versions", {})
    versions = {
        version
        for group in grouped_versions.values()
        for version in group
        if isinstance(version, str)
        and VERSION_PATTERN.fullmatch(version)
        and tuple(map(int, version.split("."))) >= (1, 8)
    }
    if not versions:
        raise RuntimeError("PaperMC did not return any available versions")
    return sorted(versions, key=lambda value: tuple(map(int, value.split("."))), reverse=True)


def get_latest_paper_version():
    return get_paper_versions()[0]


def paper_jar_path(version):
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("Phiên bản Minecraft không hợp lệ")
    return os.path.join(BASE_DATA_DIR, f"paper-{version}.jar")


def _remove_old_server_jars():
    """Remove previous root server JARs and the old panel-managed cache."""
    removed = []
    for name in os.listdir(BASE_DATA_DIR):
        path = os.path.join(BASE_DATA_DIR, name)
        if os.path.isfile(path) and name.lower().endswith(".jar"):
            os.remove(path)
            removed.append(path)

    old_cache = os.path.join(BASE_DATA_DIR, "servers")
    if os.path.isdir(old_cache):
        for root, _, files in os.walk(old_cache):
            for name in files:
                if name.lower().endswith(".jar"):
                    path = os.path.join(root, name)
                    os.remove(path)
                    removed.append(path)
    return removed


def find_server_jar(selected_version=""):
    """Find a server JAR by inspecting its contents, even if it was renamed."""
    server_markers = (
        "io/papermc/paperclip/paperclip.class",
        "io/papermc/paperclip/main.class",
        "org/bukkit/craftbukkit/main.class",
        "net/minecraft/bundler/main.class",
        "net/minecraft/server/main.class",
    )
    candidates = []
    root_level_jars = []
    for root, _, files in os.walk(BASE_DATA_DIR):
        for name in files:
            if not name.lower().endswith(".jar"):
                continue
            path = os.path.join(root, name)
            if root == BASE_DATA_DIR:
                root_level_jars.append(path)
            try:
                with zipfile.ZipFile(path) as archive:
                    entries = {entry.lower() for entry in archive.namelist()}
                    if any(marker in entries for marker in server_markers):
                        candidates.append(path)
            except (OSError, zipfile.BadZipFile):
                continue

    preferred_name = f"paper-{selected_version}.jar".lower() if selected_version else ""
    preferred = [path for path in candidates if os.path.basename(path).lower() == preferred_name]
    if preferred:
        preferred_root = [path for path in preferred if os.path.dirname(path) == BASE_DATA_DIR]
        if len(preferred_root) == 1:
            return preferred_root[0]
        if len(preferred) == 1:
            return preferred[0]
    if len(candidates) == 1:
        return candidates[0]
    named_root_jars = [
        path for path in root_level_jars
        if any(marker in os.path.basename(path).lower() for marker in ("paper", "server", "spigot", "craftbukkit"))
    ]
    if not candidates and len(named_root_jars) == 1:
        return named_root_jars[0]
    if not candidates and len(root_level_jars) == 1 and os.path.getsize(root_level_jars[0]) >= 1024 * 1024:
        return root_level_jars[0]
    if not candidates:
        raise FileNotFoundError("Không tìm thấy server JAR trong /data")
    raise RuntimeError(
        "Tìm thấy nhiều server JAR, không thể tự chọn: "
        + ", ".join(os.path.relpath(path, BASE_DATA_DIR) for path in candidates)
    )


def java_executable_for_version(version):
    """Choose the Paper-recommended Java major version when bundled in Docker."""
    parts = tuple(map(int, version.split(".")))
    if parts[0] == 1 and parts[1] <= 11:
        major = 8
    elif parts[0] == 1 and (parts[1] < 16 or (parts[1] == 16 and len(parts) > 2 and parts[2] < 5)):
        major = 11
    elif parts[0] == 1 and parts[1] <= 19:
        major = 17
    elif parts[0] == 1:
        major = 21
    else:
        major = 25
    configured_home = os.getenv(f"JAVA_{major}_HOME", f"/opt/java/jdk{major}")
    candidate = os.path.join(configured_home, "bin", "java")
    return candidate if os.path.isfile(candidate) else "java"


def ensure_paper_jar(version):
    """Return a persistent JAR path, downloading the latest stable build if absent."""
    with _download_lock:
        return _ensure_paper_jar(version)


def _ensure_paper_jar(version):
    destination = paper_jar_path(version)
    if os.path.isfile(destination) and os.path.getsize(destination) > 0:
        return destination

    available_versions = get_paper_versions()
    if version not in available_versions:
        raise ValueError(f"PaperMC không hỗ trợ phiên bản {version}")

    builds = _api_json(f"{API_ROOT}/versions/{version}/builds")
    stable_builds = [build for build in builds if build.get("channel") == "STABLE"]
    if not stable_builds:
        raise RuntimeError(f"PaperMC chưa có bản STABLE cho Minecraft {version}")
    build = max(stable_builds, key=lambda entry: int(entry.get("id", 0)))
    download = build.get("downloads", {}).get("server:default")
    if not download or not download.get("url"):
        raise RuntimeError(f"PaperMC không cung cấp server JAR cho Minecraft {version}")

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    temporary_path = destination + ".download"
    request = urllib.request.Request(
        download["url"], headers={"User-Agent": Config.PAPERMC_USER_AGENT}
    )
    digest = hashlib.sha256()
    try:
        removed_jars = _remove_old_server_jars()
        if removed_jars:
            add_log(f"Đã xóa {len(removed_jars)} JAR server cũ trước khi tải phiên bản {version}.", "system")
        with urllib.request.urlopen(request, timeout=60) as response, open(temporary_path, "wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)

        expected_hash = download.get("checksums", {}).get("sha256")
        if expected_hash and digest.hexdigest().lower() != expected_hash.lower():
            raise RuntimeError("SHA-256 của file tải về không khớp với PaperMC")
        if os.path.getsize(temporary_path) == 0:
            raise RuntimeError("PaperMC trả về file JAR rỗng")
        os.replace(temporary_path, destination)
    except Exception:
        try:
            os.remove(temporary_path)
        except OSError:
            pass
        raise

    return destination
