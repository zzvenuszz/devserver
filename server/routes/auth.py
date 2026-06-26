"""
Authentication Routes - Login/Logout
"""
from flask import Blueprint, render_template_string, request, redirect, session
import os
from server.config import Config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Trang đăng nhập quản trị"""
    correct_password = os.getenv("ADMIN_PASS")
    if not correct_password:
        return """
        <body style="font-family:sans-serif; background:#1e1e24; color:#fff; padding:50px; text-align:center;">
            <h2 style="color:#ff3333;">⚠️ LỖI BẢO MẬT KHỞI CHẠY</h2>
            <p>Bạn chưa cài đặt biến môi trường <strong>ADMIN_PASS</strong> trong mục Settings của Hugging Face Space!</p>
        </body>
        """

    error_msg = ""
    if request.method == "POST":
        input_pass = request.form.get("password", "")
        if input_pass == correct_password:
            session["logged_in"] = True
            session.permanent = True 
            return redirect("/")
        else:
            error_msg = "Mật khẩu quản trị không chính xác!"

    login_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>VnMine Panel Login</title>
        <meta charset="utf-8">
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #121214; color: #e0e0e6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .login-card { background: #1e1e24; padding: 30px; border-radius: 8px; width: 100%; max-width: 360px; text-align: center; border: 1px solid #333; }
            h2 { color: #4caf50; margin-bottom: 20px; }
            input[type="password"] { width: 100%; padding: 12px; background: #111; border: 1px solid #444; color: white; border-radius: 4px; box-sizing: border-box; margin-bottom: 15px; text-align: center; }
            button { width: 100%; background: #4caf50; color: white; border: none; padding: 12px; border-radius: 4px; font-weight: bold; cursor: pointer; }
            .error { color: #ff3333; font-size: 13px; margin-bottom: 15px; text-align: left; background: rgba(255,51,51,0.1); padding: 8px; border-radius: 4px; border-left: 3px solid #ff3333; }
        </style>
    </head>
    <body>
        <div class="login-card">
            <h2>🧱 VnMine Panel Pro</h2>
            {% if error_msg %}<div class="error">{{ error_msg }}</div>{% endif %}
            <form method="POST">
                <input type="password" name="password" placeholder="Nhập mật khẩu quản trị..." required autofocus>
                <button type="submit">XÁC THỰC</button>
            </form>
        </div>
    </body>
    </html>
    """
    return render_template_string(login_html, error_msg=error_msg)


@auth_bp.route("/logout")
def logout():
    """Đăng xuất"""
    session.clear()
    return redirect("/login")