from pathlib import Path

from app.batch.file_ops import ensure_directory
from app.config import Settings


def get_inbox_path(settings: Settings) -> Path:
    return ensure_directory(settings.input_path).resolve()
