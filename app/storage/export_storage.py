from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.storage.path_resolver import ensure_directory, relative_to_root
from app.storage.paths import truncate_safe_filename
from app.storage.types import StoredArtifact


class ExportStorage:
    def __init__(self, root: Path):
        self.root = ensure_directory(root)

    def create_export(self, *, suggested_name: str, content: bytes, suffix: str) -> StoredArtifact:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        safe_name = truncate_safe_filename(f"{Path(suggested_name).stem}_{timestamp}{suffix}")
        destination = ensure_directory(self.root) / safe_name
        destination.write_bytes(content)
        return StoredArtifact(
            storage_key=relative_to_root(destination, self.root),
            absolute_path=destination,
            created=True,
        )

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
