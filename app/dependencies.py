from fastapi import Request

from app.auth.session import SessionManager
from app.config import Settings, get_settings


def get_app_settings() -> Settings:
    return get_settings()


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager

