from __future__ import annotations

import shutil
from pathlib import Path

from app.storage.path_resolver import ensure_directory, relative_to_root, resolve_under_root
from app.storage.paths import build_storage_key, normalize_filename
from app.storage.types import StoredArtifact


class DocumentStorage:
    def __init__(self, root: Path):
        self.root = ensure_directory(root)

    def resolve_storage_key(self, storage_key: str) -> Path:
        return resolve_under_root(self.root, storage_key)

    def save_document(
        self,
        source_path: Path,
        *,
        original_filename: str,
        sha256: str,
        mime_type: str | None = None,
    ) -> StoredArtifact:
        suffix = Path(normalize_filename(original_filename)).suffix or _suffix_from_mime_type(mime_type)
        storage_key = build_storage_key(sha256, suffix=suffix or ".pdf")
        destination = self.resolve_storage_key(storage_key)
        ensure_directory(destination.parent)
        if destination.exists():
            return StoredArtifact(storage_key=storage_key, absolute_path=destination, created=False)
        shutil.copy2(source_path, destination)
        return StoredArtifact(storage_key=storage_key, absolute_path=destination, created=True)

    def open_document(self, storage_key: str, mode: str = "rb"):
        return self.resolve_storage_key(storage_key).open(mode)

    def exists(self, storage_key: str) -> bool:
        return self.resolve_storage_key(storage_key).exists()

    def delete_document(self, storage_key: str, *, missing_ok: bool = True) -> bool:
        path = self.resolve_storage_key(storage_key)
        if not path.exists():
            return False if not missing_ok else False
        path.unlink()
        self._prune_empty_parent_dirs(path.parent, stop_at=self.root)
        return True

    def list_retained_failures(self) -> list[Path]:
        return sorted(self.root.glob("sha256/*/*/*"))

    def storage_key_for_absolute_path(self, absolute_path: Path) -> str | None:
        try:
            return relative_to_root(absolute_path, self.root)
        except ValueError:
            return None

    def _prune_empty_parent_dirs(self, start_dir: Path, *, stop_at: Path) -> None:
        current = start_dir
        while current != stop_at and current.exists():
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent


def _suffix_from_mime_type(mime_type: str | None) -> str:
    if mime_type == "application/pdf":
        return ".pdf"
    return ".bin"
