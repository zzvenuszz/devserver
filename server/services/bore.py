"""Publish the panel and Minecraft TCP ports through bore.pub."""
import os
import re
import shutil
import subprocess
import time

from server.config import BASE_DATA_DIR, Config, state
from server.utils import add_log
from server.utils.logger import parse_and_add_raw_log


_ADDRESS_RE = re.compile(r"\blistening at (bore\.pub:\d+)(?:\s|$)", re.IGNORECASE)


def _run_tunnel(name, local_port):
    address_attr = f"{name}_public_address"
    while True:
        command = [
            "bore", "local", str(local_port),
            "--local-host", "127.0.0.1", "--to", "bore.pub"
        ]
        add_log(f"Starting bore.pub tunnel for {name} (local port {local_port})...", "bore")
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            state.bore_processes[name] = process
            setattr(state, address_attr, None)
            for line in process.stdout:
                line = line.rstrip()
                parse_and_add_raw_log(f"[BORE] [{name}] {line}")
                match = _ADDRESS_RE.search(line)
                if match:
                    address = match.group(1)
                    setattr(state, address_attr, address)
                    add_log(f"bore.pub {name} address: {address}", "bore")
            code = process.wait()
            add_log(f"bore.pub tunnel {name} exited ({code}); retrying in 5 seconds", "error")
        except Exception as exc:
            setattr(state, address_attr, None)
            add_log(f"Unable to start bore.pub tunnel for {name}: {exc}", "error")
        time.sleep(5)


def run_bore():
    """Run separate unauthenticated bore.pub tunnels for panel and Minecraft."""
    if not shutil.which("bore"):
        add_log("bore client is missing; install bore-cli to publish ports", "error")
        return

    minecraft_port = Config.MINECRAFT_PORT
    properties_path = os.path.join(BASE_DATA_DIR, "server.properties")
    if not os.getenv("MINECRAFT_PORT"):
        try:
            with open(properties_path, encoding="utf-8") as properties:
                for line in properties:
                    if line.startswith("server-port="):
                        minecraft_port = int(line.split("=", 1)[1].strip())
                        break
        except (OSError, ValueError):
            pass

    tunnels = (
        ("panel", Config.PORT),
        ("minecraft", minecraft_port),
    )
    import threading
    for name, port in tunnels:
        threading.Thread(target=_run_tunnel, args=(name, port), daemon=True).start()
