"""
File Manager Routes - API cho quản lý file
"""
import os
import re
import zipfile
import hashlib
import shutil
import time
import urllib.request
from flask import Blueprint, jsonify, request, send_from_directory, redirect
from server.config import state, Config, BASE_DATA_DIR
from server.utils import add_log
from server.utils.file_ops import (
    list_directory, calculate_sha256, create_backup_zip, 
    unzip_file, is_zip_file
)

fm_bp = Blueprint('file_manager', __name__)


@fm_bp.route("/api/fm/download-from-url", methods=["POST"])
def fm_download_from_url():
    """Tải file từ URL (hỗ trợ GitHub artifacts)"""
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


@fm_bp.route("/api/fm/checksum", methods=["POST"])
def fm_checksum():
    """Kiểm tra SHA-256 checksum của file"""
    filepath = request.json.get("filepath", "")
    expected_checksum = request.json.get("expected_checksum", "").strip().lower()
    
    calculated = calculate_sha256(filepath)
    
    if not calculated:
        return jsonify({"status": "error", "message": "Tập tin không hợp lệ", "calculated": ""})

    if calculated == expected_checksum:
        return jsonify({"status": "success", "message": "Mã SHA-256 trùng khớp hoàn hảo.", "calculated": calculated})
    else:
        return jsonify({"status": "mismatch", "message": "Mã checksum KHÔNG trùng khớp!", "calculated": calculated})


@fm_bp.route("/api/fm/upload", methods=["POST"])
def fm_upload():
    """Upload file"""
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


@fm_bp.route("/api/fm/download/<path:filepath>")
def fm_download(filepath):
    """Download file"""
    base_path = request.json.get("base_path", "").strip()
    if base_path and os.path.isdir(base_path):
        full_path = os.path.join(base_path, filepath)
    else:
        full_path = os.path.join(BASE_DATA_DIR, filepath)
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return "Tệp tin không tồn tại", 404
    
    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True)


@fm_bp.route("/api/fm/save", methods=["POST"])
def fm_save():
    """Lưu nội dung file (text editor)"""
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


@fm_bp.route("/api/fm/mkdir", methods=["POST"])
def fm_mkdir():
    """Tạo thư mục mới"""
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


@fm_bp.route("/api/fm/backup", methods=["POST"])
def fm_backup():
    """Tạo backup ZIP của thư mục"""
    folder_path = request.json.get("folder_path", "")
    folder_name = request.json.get("folder_name", "").strip()
    
    base_path = request.json.get("base_path", "").strip()
    zip_name = create_backup_zip(folder_path, folder_name, base_dir=base_path if base_path else None)
    
    if zip_name:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Không thể tạo backup"})


@fm_bp.route("/api/fm/unzip", methods=["POST"])
def fm_unzip():
    """Giải nén file ZIP"""
    filepath = request.json.get("filepath", "")
    
    base_path = request.json.get("base_path", "").strip()
    success = unzip_file(filepath, base_dir=base_path if base_path else None)
    
    if success:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Không thể giải nén file"})


@fm_bp.route("/api/fm/rename", methods=["POST"])
def fm_rename():
    """Đổi tên file/thư mục"""
    old_path = request.json.get("old_path", "")
    new_name = request.json.get("new_name", "").strip()
    
    if not old_path or not new_name:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu"})
    
    base_path = request.json.get("base_path", "").strip()
    if base_path and os.path.isdir(base_path):
        full_old_path = os.path.join(base_path, old_path)
    else:
        full_old_path = os.path.join(BASE_DATA_DIR, old_path)
    full_new_path = os.path.join(os.path.dirname(full_old_path), new_name)
    
    try:
        if os.path.exists(full_new_path):
            return jsonify({"status": "error", "message": "Tên mới đã tồn tại"})
        os.rename(full_old_path, full_new_path)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@fm_bp.route("/api/fm/delete", methods=["DELETE"])
def fm_delete():
    """Xóa file/thư mục"""
    filepath = request.json.get("filepath", "")
    base_path = request.json.get("base_path", "").strip()
    if base_path and os.path.isdir(base_path):
        full_path = os.path.join(base_path, filepath)
    else:
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