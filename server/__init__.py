"""
VnMine Panel - Flask Application Factory
"""
from flask import Flask
from server.config import Config
from server.routes import auth_bp, console_bp, main_bp, fm_bp, monitor_bp


def create_app():
    """Tạo và cấu hình Flask app"""
    app = Flask(__name__)
    
    # Load config
    app.config.from_object(Config)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(console_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(fm_bp)
    app.register_blueprint(monitor_bp)
    
    return app
