from pathlib import Path

from app.config import Settings
from app.storage import get_storage_service


def get_inbox_path(settings: Settings) -> Path:
    return get_storage_service(settings).inbox_root.resolve()
