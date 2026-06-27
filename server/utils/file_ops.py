"""
File operations helper - Các hàm xử lý file phục vụ cho File Manager
"""
import os
import zipfile
import hashlib
import shutil
from datetime import datetime
from server.config import BASE_DATA_DIR


def get_file_info(filepath):
    """
    Lấy thông tin chi tiết của file/thư mục
    
    Args:
        filepath: Đường dẫn tương đối trong BASE_DATA_DIR
        
    Returns:
        dict: Thông tin file (name, is_dir, size, mtime, path)
    """
    full_path = os.path.join(BASE_DATA_DIR, filepath)
    
    if not os.path.exists(full_path):
        return None
    
    is_directory = os.path.isdir(full_path)
    
    try:
        stat_info = os.stat(full_path)
        size_val = f"{stat_info.st_size // 1024} KB" if not is_directory else "Folder"
        time_val = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        size_val = "Unknown"
        time_val = "Unknown"
    
    return {
        "name": os.path.basename(filepath) if filepath else "",
        "is_dir": is_directory,
        "size": size_val,
        "mtime": time_val,
        "path": filepath
    }


def list_directory(subpath=""):
    """
    Liệt kê nội dung thư mục
    
    Args:
        subpath: Đường dẫn con trong BASE_DATA_DIR
        
    Returns:
        list: Danh sách các mục trong thư mục
    """
    target_dir = os.path.join(BASE_DATA_DIR, subpath)
    
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return []
    
    try:
        dir_items = os.listdir(target_dir)
    except Exception:
        return []
    
    formatted_items = []
    
    # Thêm link quay lại thư mục cha
    if subpath:
        parent = os.path.dirname(subpath)
        parent_url = f"/files/{parent}" if parent and parent != subpath else "/files"
        formatted_items.append({
            "name": ".. (Thư mục cha)",
            "is_dir": True,
            "is_parent_link": True,
            "path": parent_url,
            "size": "-",
            "mtime": "-"
        })
    
    # Thêm các item trong thư mục
    for item in sorted(dir_items):
        item_path = os.path.join(subpath, item) if subpath else item
        full_path = os.path.join(BASE_DATA_DIR, item_path)
        is_directory = os.path.isdir(full_path)
        
        try:
            stat_info = os.stat(full_path)
            size_val = f"{stat_info.st_size // 1024} KB" if not is_directory else "Folder"
            time_val = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            size_val = "Unknown"
            time_val = "Unknown"
        
        formatted_items.append({
            "name": item,
            "is_dir": is_directory,
            "is_parent_link": False,
            "path": f"/files/{item_path}",
            "raw_path": item_path,
            "size": size_val,
            "mtime": time_val
        })
    
    return formatted_items


def calculate_sha256(filepath):
    """
    Tính toán SHA-256 checksum của file
    
    Args:
        filepath: Đường dẫn tương đối trong BASE_DATA_DIR
        
    Returns:
        str: SHA-256 hash hoặc error message
    """
    full_path = os.path.join(BASE_DATA_DIR, filepath)
    
    if not os.path.exists(full_path) or os.path.isdir(full_path):
        return None
    
    try:
        sha256_hash = hashlib.sha256()
        with open(full_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest().lower()
    except Exception as e:
        return None


def create_backup_zip(folder_path, folder_name, base_dir=None):
    """
    Tạo file backup ZIP của thư mục
    
    Args:
        folder_path: Đường dẫn thư mục cần backup
        folder_name: Tên thư mục (đặt tên cho file zip)
        
    Returns:
        str: Đường dẫn file zip đã tạo hoặc None nếu lỗi
    """
    if base_dir and os.path.isdir(base_dir):
        target_dir = os.path.join(base_dir, folder_path)
    else:
        target_dir = os.path.join(BASE_DATA_DIR, folder_path)
    
    if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
        return None
    
    zip_name = f"{folder_name}_backup_{datetime.now().strftime('%d%m%Y_%H%M%S')}.zip"
    zip_path = os.path.join(os.path.dirname(target_dir), zip_name)
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(target_dir):
                for file in files:
                    full_file_path = os.path.join(root, file)
                    arcname = os.path.join(folder_name, os.path.relpath(full_file_path, target_dir))
                    zipf.write(full_file_path, arcname)
        return zip_name
    except Exception as e:
        return None


def unzip_file(filepath, base_dir=None):
    """
    Giải nén file ZIP
    
    Args:
        filepath: Đường dẫn file ZIP
        
    Returns:
        bool: True nếu thành công, False nếu lỗi
    """
    if base_dir and os.path.isdir(base_dir):
        full_zip_path = os.path.join(base_dir, filepath)
    else:
        full_zip_path = os.path.join(BASE_DATA_DIR, filepath)
    
    if not os.path.exists(full_zip_path) or not os.path.isfile(full_zip_path):
        return False
    
    try:
        with zipfile.ZipFile(full_zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.dirname(full_zip_path))
        return True
    except Exception as e:
        return False


def list_directory_from(path):
    """
    Liệt kê nội dung thư mục từ absolute path (không dùng BASE_DATA_DIR)
    
    Args:
        path: Đường dẫn tuyệt đối đến thư mục cần liệt kê
        
    Returns:
        list: Danh sách các mục trong thư mục
    """
    if not os.path.exists(path) or not os.path.isdir(path):
        return []
    
    try:
        dir_items = os.listdir(path)
    except Exception:
        return []
    
    formatted_items = []
    is_absolute_mode = True
    
    # Thêm link quay lại thư mục cha
    parent = os.path.dirname(path)
    if parent and parent != path:
        formatted_items.append({
            "name": ".. (Thư mục cha)",
            "is_dir": True,
            "is_parent_link": True,
            "path": f"/files?path={parent}",
            "raw_path": parent,
            "size": "-",
            "mtime": "-",
            "is_absolute_mode": True
        })
    
    # Thêm các item trong thư mục
    for item in sorted(dir_items):
        full_path = os.path.join(path, item)
        is_directory = os.path.isdir(full_path)
        
        try:
            stat_info = os.stat(full_path)
            size_val = f"{stat_info.st_size // 1024} KB" if not is_directory else "Folder"
            time_val = datetime.fromtimestamp(stat_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            size_val = "Unknown"
            time_val = "Unknown"
        
        file_link = f"/files?path={full_path}"
        formatted_items.append({
            "name": item,
            "is_dir": is_directory,
            "is_parent_link": False,
            "path": file_link,
            "raw_path": full_path,
            "full_path": full_path,
            "size": size_val,
            "mtime": time_val,
            "is_absolute_mode": True
        })
    
    return formatted_items


def is_zip_file(filepath):
    """
    Kiểm tra file có phải ZIP không
    
    Args:
        filepath: Đường dẫn file
        
    Returns:
        bool: True nếu là file ZIP
    """
    full_path = os.path.join(BASE_DATA_DIR, filepath)
    try:
        return zipfile.is_zipfile(full_path)
    except Exception:
        return False