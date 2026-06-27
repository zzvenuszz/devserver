"""
Main Routes - Trang chính và File Manager UI
"""
import os
from flask import Blueprint, render_template, request
from server.config import state, Config, BASE_DATA_DIR
from server.services.minecraft import is_server_running
from server.services.monitor import get_server_stats
from server.utils.file_ops import list_directory, get_file_info, list_directory_from

main_bp = Blueprint('main', __name__)


@main_bp.route("/")
@main_bp.route("/files")
@main_bp.route("/files/<path:subpath>")
@main_bp.route("/monitor")
@main_bp.route("/terminal")
def index(subpath=""):
    """Trang chính - Console, File Manager & Monitor"""
    if request.path.startswith("/monitor"):
        active_tab = "monitor"
    elif request.path.startswith("/terminal"):
        active_tab = "terminal"
    elif request.path.startswith("/files"):
        active_tab = "files"
    else:
        active_tab = "console"

    # Hỗ trợ browse absolute path qua query parameter ?path=
    browse_path = request.args.get("path", "").strip()

    file_content = None
    edit_file_path = ""
    dir_items = []
    current_path = BASE_DATA_DIR  # Default path
    formatted_items = []

    if active_tab == "files":
        if browse_path and os.path.isdir(browse_path):
            # Browse absolute path
            current_path = browse_path
            formatted_items = list_directory_from(browse_path)
        elif browse_path and os.path.isfile(browse_path):
            # View file content from absolute path
            current_path = os.path.dirname(browse_path)
            edit_file_path = browse_path
            try:
                with open(browse_path, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()
            except Exception as e:
                file_content = f"Không thể đọc nội dung file: {e}"
            # Also list the parent directory
            formatted_items = list_directory_from(current_path)
        elif subpath:
            # Browse relative path under BASE_DATA_DIR
            target_dir = os.path.join(BASE_DATA_DIR, subpath)
            current_path = os.path.join(BASE_DATA_DIR, subpath)

            # Security check
            if not os.path.abspath(target_dir).startswith(os.path.abspath(BASE_DATA_DIR)):
                return "Bị từ chối truy cập vùng dữ liệu an toàn!", 403

            if os.path.exists(target_dir):
                if os.path.isfile(target_dir):
                    edit_file_path = subpath
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

            formatted_items = list_directory(subpath)
        else:
            # Default: /data/
            current_path = BASE_DATA_DIR
            try:
                dir_items = os.listdir(BASE_DATA_DIR)
            except Exception:
                dir_items = []
            formatted_items = list_directory("")

    # Lấy stats server
    stats_data = get_server_stats()

    # Render template
    return render_template(
        'index.html',
        active_tab=active_tab,
        stats=stats_data,
        items=formatted_items,
        subpath=subpath,
        file_content=file_content,
        edit_file_path=edit_file_path,
        current_path=current_path
    )
