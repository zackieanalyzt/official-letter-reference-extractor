from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from app.storage.path_resolver import ensure_directory, relative_to_root
from app.storage.paths import truncate_safe_filename
from app.storage.types import StoredArtifact


class DebugStorage:
    def __init__(self, root: Path):
        self.root = ensure_directory(root)

    def save_artifact(self, *, filename: str, content: bytes, subdir: str | None = None) -> StoredArtifact:
        target_root = self.root if not subdir else ensure_directory(self.root / subdir)
        safe_name = truncate_safe_filename(filename)
        destination = target_root / safe_name
        destination.write_bytes(content)
        return StoredArtifact(
            storage_key=relative_to_root(destination, self.root),
            absolute_path=destination,
            created=True,
        )

    def write_json(self, relative_name: str, payload: dict[str, Any]) -> Path:
        destination = self.root / truncate_safe_filename(relative_name)
        destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return destination

    def read_json(self, relative_name: str) -> dict[str, Any] | None:
        path = self.root / truncate_safe_filename(relative_name)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def iter_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(path for path in self.root.glob("*") if path.is_file())

    def list_expired_files(self, *, cutoff: datetime) -> list[Path]:
        return [
            path for path in self.iter_files() if datetime.fromtimestamp(path.stat().st_mtime, tz=cutoff.tzinfo) <= cutoff
        ]

    def delete_file(self, path: Path, *, missing_ok: bool = True) -> bool:
        if not path.exists():
            return False if not missing_ok else False
        path.unlink(missing_ok=missing_ok)
        return True
