from __future__ import annotations

from datetime import datetime
import shutil
from pathlib import Path
from uuid import uuid4

from app.storage.path_resolver import ensure_directory


class TempStorage:
    def __init__(self, root: Path):
        self.root = ensure_directory(root)

    def create_working_copy(self, source_path: Path) -> Path:
        destination = self.root / f"{uuid4().hex}-{source_path.name}"
        shutil.copy2(source_path, destination)
        return destination

    def delete(self, path: Path, *, missing_ok: bool = True) -> bool:
        if not path.exists():
            return False if not missing_ok else False
        path.unlink(missing_ok=missing_ok)
        return True

    def iter_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(path for path in self.root.glob("*") if path.is_file())

    def list_expired_files(self, *, cutoff: datetime) -> list[Path]:
        return [
            path for path in self.iter_files() if datetime.fromtimestamp(path.stat().st_mtime, tz=cutoff.tzinfo) <= cutoff
        ]
