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
│   ├── bore.py              # bore.pub TCP tunnels
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
- **bore.py**: Mở tunnel Minecraft qua bore.pub khi được bật trong panel (mặc định tắt)
- **paper.py**: Lấy danh sách phiên bản PaperMC, tải server JAR và kiểm tra SHA-256
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
- bore.pub: Không cần tài khoản hoặc khóa; chỉ công khai cổng Minecraft (`MINECRAFT_PORT`, mặc định `25565`) khi bật nút trong panel. Panel không được tunnel qua bore.pub.
- Minecraft: Bộ chọn Paper lấy phiên bản trực tiếp từ PaperMC; server JAR tải về `/data`, phiên bản đã chọn lưu trong `/data/panel/settings.json`. Trước lượt tải JAR mới, panel xóa JAR ở gốc `/data` và cache server cũ; JAR plugin trong `/data/plugins` được giữ lại. Nút khởi chạy dò JAR server theo nội dung, không phụ thuộc tên file.
- Java: Docker kèm Java 8, 11, 17, 21 và 25 để chạy các thế hệ Paper tương ứng

## 📝 Ghi Chú

- Template HTML được tách ra file riêng `server/templates/index.html`
- Sử dụng Flask Blueprints để tổ chức routes
- Global state được quản lý tập trung trong `config.py`
