# Cấu Trúc Module - VnMine Panel

Tài liệu này mô tả cấu trúc module sau khi refactor từ file `app.py` đơn lẻ thành các module có tổ chức.

## 📁 Cấu Trúc Thư Mục

```
server/
├── __init__.py              # Flask App Factory
├── config.py                # Cấu hình tập trung
├── routes/
│   ├── __init__.py
│   ├── auth.py              # Login/Logout routes
│   ├── console.py           # Console & command APIs
│   ├── main.py              # Main index route
│   └── file_manager.py      # File manager routes & APIs
├── services/
│   ├── __init__.py
│   ├── minecraft.py         # Paper server management
│   ├── playit.py            # Playit tunnel service
│   ├── monitor.py           # System monitoring
│   └── server_info.py       # IP/location fetching
├── utils/
│   ├── __init__.py
│   ├── logger.py            # Logging system
│   └── file_ops.py          # File operations helper
└── templates/
    └── index.html           # Main HTML template
```

## 🎯 Mục Đích Refactor

1. **Dễ phát triển**: Mỗi module có trách nhiệm rõ ràng
2. **Dễ debug**: Có thể kiểm tra từng component độc lập
3. **Dễ test**: Có thể test từng service/route riêng biệt
4. **Dễ triển khai**: Cấu trúc rõ ràng, dễ bảo trì
5. **Scalable**: Dễ thêm tính năng mới

## 📋 Mô Tả Các Module

### Config (`config.py`)
- Cấu hình Flask app
- Global state management
- Constants và settings

### Services (`services/`)
- **minecraft.py**: Quản lý Paper MC server, gửi lệnh
- **playit.py**: Quản lý Playit tunnel
- **monitor.py**: Giám sát RAM/CPU
- **server_info.py**: Lấy IP/location máy chủ

### Utils (`utils/`)
- **logger.py**: Hệ thống logging với phân loại
- **file_ops.py**: Các hàm xử lý file (ZIP, checksum, backup)

### Routes (`routes/`)
- **auth.py**: Đăng nhập/đăng xuất
- **console.py**: API logs và gửi lệnh
- **main.py**: Trang chính và file manager UI
- **file_manager.py**: 10 endpoints cho file operations

## 🚀 Cách Chạy

```bash
# Chạy trực tiếp
python3 app.py

# Hoặc với Gunicorn (production)
gunicorn -w 4 -b 0.0.0.0:7860 app:app
```

## 🔧 Cấu Hình

- Port: Biến môi trường `PORT` (mặc định 7860)
- Admin password: Biến môi trường `ADMIN_PASS`
- Playit key: Biến môi trường `PLAYIT_SECRET_KEY`

## 📝 Ghi Chú

- Template HTML được tách ra file riêng `server/templates/index.html`
- Sử dụng Flask Blueprints để tổ chức routes
- Global state được quản lý tập trung trong `config.py`