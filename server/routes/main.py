"""
Main Routes - Trang chính và File Manager UI
"""
import os
from flask import Blueprint, render_template, request
from server.config import state, Config, BASE_DATA_DIR
from server.services.minecraft import is_server_running
from server.services.monitor import get_server_stats
from server.utils.file_ops import list_directory, get_file_info

main_bp = Blueprint('main', __name__)


@main_bp.route("/")
@main_bp.route("/files")
@main_bp.route("/files/<path:subpath>")
@main_bp.route("/monitor")
def index(subpath=""):
    """Trang chính - Console, File Manager & Monitor"""
    if request.path.startswith("/monitor"):
        active_tab = "monitor"
    elif request.path.startswith("/files"):
        active_tab = "files"
    else:
        active_tab = "console"
    target_dir = os.path.join(BASE_DATA_DIR, subpath)
    file_content = None
    edit_file_path = ""
    dir_items = []

    # Security check - đảm bảo không truy cập ngoài BASE_DATA_DIR
    if not os.path.abspath(target_dir).startswith(os.path.abspath(BASE_DATA_DIR)):
        return "Bị từ chối truy cập vùng dữ liệu an toàn!", 403

    # Xử lý đường dẫn
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

    # Format items cho template
    formatted_items = list_directory(subpath)

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
        edit_file_path=edit_file_path
    )
