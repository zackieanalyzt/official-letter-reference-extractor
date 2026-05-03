from fastapi import Header, HTTPException

from app.config import get_settings


def verify_token(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if settings.app_token and x_api_key != settings.app_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
