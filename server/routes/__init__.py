"""Routes module"""
from .auth import auth_bp
from .console import console_bp
from .main import main_bp
from .file_manager import fm_bp

__all__ = ['auth_bp', 'console_bp', 'main_bp', 'fm_bp']