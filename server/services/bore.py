"""Publish the Minecraft TCP port through bore.pub when requested."""
import os
import re
import shutil
import subprocess
import threading

from server.config import BASE_DATA_DIR, Config, state
from server.utils import add_log
from server.utils.logger import parse_and_add_raw_log


_ADDRESS_RE = re.compile(r"\blistening at (bore\.pub:\d+)(?:\s|$)", re.IGNORECASE)
_lock = threading.RLock()
_stop_event = threading.Event()
_worker = None


def _minecraft_port():
    port = Config.MINECRAFT_PORT
    properties_path = os.path.join(BASE_DATA_DIR, "server.properties")
    if not os.getenv("MINECRAFT_PORT"):
        try:
            with open(properties_path, encoding="utf-8") as properties:
                for line in properties:
                    if line.startswith("server-port="):
                        port = int(line.split("=", 1)[1].strip())
                        break
        except (OSError, ValueError):
            pass
    return port


def _run_tunnel():
    while not _stop_event.is_set():
        command = [
            "bore", "local", str(_minecraft_port()),
            "--local-host", "127.0.0.1", "--to", "bore.pub"
        ]
        add_log(f"Starting bore.pub tunnel for Minecraft (local port {_minecraft_port()})...", "bore")
        process = None
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            with _lock:
                state.bore_processes["minecraft"] = process
                state.minecraft_public_address = None
            for line in process.stdout:
                line = line.rstrip()
                parse_and_add_raw_log(f"[BORE] [minecraft] {line}")
                match = _ADDRESS_RE.search(line)
                if match and not _stop_event.is_set():
                    address = match.group(1)
                    with _lock:
                        state.minecraft_public_address = address
                    add_log(f"bore.pub Minecraft address: {address}", "bore")
            code = process.wait()
            if not _stop_event.is_set():
                add_log(f"bore.pub Minecraft tunnel exited ({code}); retrying in 5 seconds", "error")
        except Exception as exc:
            if not _stop_event.is_set():
                add_log(f"Unable to start bore.pub Minecraft tunnel: {exc}", "error")
        finally:
            with _lock:
                if state.bore_processes.get("minecraft") is process:
                    state.bore_processes.pop("minecraft", None)
                if _stop_event.is_set():
                    state.minecraft_public_address = None
        if not _stop_event.wait(5):
            continue
    with _lock:
        state.bore_processes.pop("minecraft", None)
        state.minecraft_public_address = None
    add_log("bore.pub Minecraft tunnel stopped", "bore")


def set_bore_enabled(enabled):
    """Start or stop the Minecraft tunnel. The caller persists the setting."""
    global _worker
    enabled = bool(enabled)
    with _lock:
        state.bore_enabled = enabled
        if enabled:
            if not shutil.which("bore"):
                state.bore_enabled = False
                raise RuntimeError("bore client is missing")
            _stop_event.clear()
            if _worker is not None and _worker.is_alive():
                return
            _worker = threading.Thread(target=_run_tunnel, daemon=True, name="bore-minecraft")
            _worker.start()
            return

        _stop_event.set()
        process = state.bore_processes.get("minecraft")
        state.minecraft_public_address = None
    if process and process.poll() is None:
        process.terminate()


def run_bore():
    """Restore the configured tunnel state at startup; disabled by default."""
    if getattr(state, "bore_enabled", False):
        try:
            set_bore_enabled(True)
        except RuntimeError as exc:
            add_log(f"Unable to start bore.pub tunnel: {exc}", "error")
