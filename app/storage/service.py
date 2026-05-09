from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.batch.file_ops import ensure_directory
from app.storage.paths import build_storage_key, normalize_filename, truncate_safe_filename


@dataclass(frozen=True)
class StoredArtifact:
    storage_key: str
    absolute_path: Path
    created: bool


class LocalStorageService:
    def __init__(self, settings):
        self.settings = settings
        self.storage_root = ensure_directory(settings.storage_root_path)
        self.debug_root = ensure_directory(settings.qr_debug_path)
        self.export_root = ensure_directory(settings.export_path)

    def resolve_storage_key(self, storage_key: str) -> Path:
        return (self.storage_root / storage_key).resolve()

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

    def delete_document(self, storage_key: str, *, missing_ok: bool = True) -> bool:
        path = self.resolve_storage_key(storage_key)
        if not path.exists():
            return False if not missing_ok else False
        path.unlink()
        self._prune_empty_parent_dirs(path.parent, stop_at=self.storage_root)
        return True

    def save_debug_artifact(
        self,
        *,
        filename: str,
        content: bytes,
        subdir: str | None = None,
    ) -> StoredArtifact:
        target_root = self.debug_root if not subdir else ensure_directory(self.debug_root / subdir)
        safe_name = truncate_safe_filename(filename)
        destination = target_root / safe_name
        destination.write_bytes(content)
        return StoredArtifact(
            storage_key=str(destination.relative_to(self.debug_root)),
            absolute_path=destination,
            created=True,
        )

    def create_export(
        self,
        *,
        suggested_name: str,
        content: bytes,
        suffix: str,
    ) -> StoredArtifact:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        safe_name = truncate_safe_filename(f"{Path(suggested_name).stem}_{timestamp}{suffix}")
        destination = ensure_directory(self.export_root) / safe_name
        destination.write_bytes(content)
        return StoredArtifact(
            storage_key=str(destination.relative_to(self.export_root)),
            absolute_path=destination,
            created=True,
        )

    def list_retained_failures(self) -> list[Path]:
        return sorted(self.storage_root.glob("sha256/*/*/*"))

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


def get_storage_service(settings) -> LocalStorageService:
    return LocalStorageService(settings)
