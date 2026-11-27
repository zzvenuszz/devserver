"""PaperMC version discovery and persistent server JAR downloads."""
import hashlib
import json
import os
import re
import threading
import urllib.request

from server.config import BASE_DATA_DIR, Config


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
    return os.path.join(BASE_DATA_DIR, "servers", f"paper-{version}.jar")


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
