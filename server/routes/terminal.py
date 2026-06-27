"""
Terminal Routes - REST-based PTY terminal
"""
import os
import pty
import select
import signal
import termios
import struct
import fcntl
import time
from flask import Blueprint, jsonify, request

terminal_bp = Blueprint('terminal', __name__)

# Store terminal sessions
TERMINAL_WORK_DIR = os.path.abspath("/home/user/app")
if not os.path.exists(TERMINAL_WORK_DIR):
    TERMINAL_WORK_DIR = os.path.abspath(".")

terminal_session = {
    "master_fd": None,
    "slave_fd": None,
    "child_pid": None,
    "buffer": b"",
    "started": False,
    "cols": 80,
    "rows": 24
}


def set_winsize(fd, rows, cols):
    """Set terminal window size"""
    try:
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except Exception:
        pass


@terminal_bp.route("/api/terminal/start", methods=["POST"])
def terminal_start():
    """Start a new terminal session (bash)"""
    global terminal_session

    if terminal_session["started"]:
        terminal_stop_internal()

    try:
        master_fd, slave_fd = pty.openpty()

        data = request.get_json(silent=True) or {}
        cols = int(data.get("cols", 80))
        rows = int(data.get("rows", 24))
        set_winsize(master_fd, rows, cols)

        pid = os.fork()
        if pid == 0:  # Child
            os.close(master_fd)
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            os.chdir(TERMINAL_WORK_DIR)
            os.environ["TERM"] = "xterm-256color"
            os.environ["HOME"] = os.path.expanduser("~")
            os.environ["SHELL"] = "/bin/bash"
            os.execve("/bin/bash", ["/bin/bash", "--login"], os.environ)
            os._exit(1)

        # Parent
        os.close(slave_fd)
        terminal_session["master_fd"] = master_fd
        terminal_session["child_pid"] = pid
        terminal_session["buffer"] = b""
        terminal_session["started"] = True
        terminal_session["cols"] = cols
        terminal_session["rows"] = rows

        os.write(master_fd, b"\n")
        time.sleep(0.1)

        return jsonify({"status": "success", "message": "Terminal started"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@terminal_bp.route("/api/terminal/input", methods=["POST"])
def terminal_input():
    """Send input to terminal"""
    if not terminal_session["started"]:
        return jsonify({"status": "error", "message": "Terminal not started"})

    data = request.get_json(silent=True) or {}
    input_text = data.get("input", "")

    try:
        os.write(terminal_session["master_fd"], input_text.encode("utf-8"))
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@terminal_bp.route("/api/terminal/output", methods=["GET"])
def terminal_output():
    """Get terminal output (polling)"""
    if not terminal_session["started"]:
        return jsonify({"status": "error", "message": "Terminal not started", "output": ""})

    try:
        while True:
            r, _, _ = select.select([terminal_session["master_fd"]], [], [], 0.01)
            if r:
                data = os.read(terminal_session["master_fd"], 4096)
                if not data:
                    terminal_cleanup()
                    break
                terminal_session["buffer"] += data
            else:
                break
    except (OSError, ValueError):
        terminal_cleanup()
    except Exception:
        pass

    output = terminal_session["buffer"]
    terminal_session["buffer"] = b""

    is_alive = terminal_session["started"]
    if is_alive:
        try:
            pid, status = os.waitpid(terminal_session["child_pid"], os.WNOHANG)
            if pid > 0:
                is_alive = False
                terminal_cleanup()
        except Exception:
            pass

    return jsonify({
        "status": "success",
        "output": output.decode("utf-8", errors="replace"),
        "alive": is_alive
    })


@terminal_bp.route("/api/terminal/resize", methods=["POST"])
def terminal_resize():
    """Resize terminal"""
    if not terminal_session["started"]:
        return jsonify({"status": "error", "message": "Terminal not started"})

    data = request.get_json(silent=True) or {}
    cols = int(data.get("cols", 80))
    rows = int(data.get("rows", 24))

    try:
        set_winsize(terminal_session["master_fd"], rows, cols)
        terminal_session["cols"] = cols
        terminal_session["rows"] = rows
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@terminal_bp.route("/api/terminal/stop", methods=["POST"])
def terminal_stop():
    """Stop terminal session"""
    terminal_stop_internal()
    return jsonify({"status": "success", "message": "Terminal stopped"})


def terminal_stop_internal():
    """Internal cleanup"""
    global terminal_session
    if terminal_session["started"]:
        try:
            if terminal_session["child_pid"]:
                os.kill(terminal_session["child_pid"], signal.SIGHUP)
                time.sleep(0.1)
                os.kill(terminal_session["child_pid"], signal.SIGKILL)
        except Exception:
            pass
        terminal_cleanup()


def terminal_cleanup():
    """Clean up terminal resources"""
    global terminal_session
    try:
        if terminal_session["master_fd"] is not None:
            os.close(terminal_session["master_fd"])
    except Exception:
        pass
    terminal_session["master_fd"] = None
    terminal_session["slave_fd"] = None
    terminal_session["child_pid"] = None
    terminal_session["buffer"] = b""
    terminal_session["started"] = False