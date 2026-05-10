from __future__ import annotations

import shutil
from pathlib import Path

from app.config import resolve_path
from app.storage.debug_storage import DebugStorage
from app.storage.document_storage import DocumentStorage
from app.storage.export_storage import ExportStorage
from app.storage.path_resolver import ensure_directory, reserve_unique_filename
from app.storage.temp_storage import TempStorage
from app.storage.types import StoredArtifact


class LocalStorageService:
    """Thin facade over concrete local storage helpers."""

    def __init__(self, settings):
        self.settings = settings
        self.document_storage = DocumentStorage(_settings_path(settings, "storage_root_path", "storage_root", "data/storage"))
        self.debug_storage = DebugStorage(_settings_path(settings, "qr_debug_path", "qr_debug_dir", "data/qr-debug"))
        self.export_storage = ExportStorage(_settings_path(settings, "export_path", "export_dir", "data/exports"))
        self.temp_storage = TempStorage(_settings_path(settings, "runtime_tmp_path", "runtime_tmp_dir", "data/runtime/tmp"))
        self.inbox_root = ensure_directory(_settings_path(settings, "input_path", "input_dir", "data/input"))

    @property
    def storage_root(self) -> Path:
        return self.document_storage.root

    @property
    def debug_root(self) -> Path:
        return self.debug_storage.root

    @property
    def export_root(self) -> Path:
        return self.export_storage.root

    def ensure_runtime_directories(self) -> dict[str, Path]:
        return {
            "inbox": ensure_directory(self.settings.input_path),
            "processed": ensure_directory(self.settings.processed_path),
            "error": ensure_directory(self.settings.error_path),
            "failed_retained": ensure_directory(self.settings.failed_retained_path),
            "storage": ensure_directory(self.settings.storage_root_path),
            "exports": ensure_directory(self.settings.export_path),
            "backups": ensure_directory(self.settings.backup_path),
            "debug": ensure_directory(self.settings.qr_debug_path),
            "runtime_tmp": ensure_directory(self.settings.runtime_tmp_path),
        }

    def resolve_storage_key(self, storage_key: str) -> Path:
        return self.document_storage.resolve_storage_key(storage_key)

    def save_document(
        self,
        source_path: Path,
        *,
        original_filename: str,
        sha256: str,
        mime_type: str | None = None,
    ) -> StoredArtifact:
        return self.document_storage.save_document(
            source_path,
            original_filename=original_filename,
            sha256=sha256,
            mime_type=mime_type,
        )

    def open_document(self, storage_key: str, mode: str = "rb"):
        return self.document_storage.open_document(storage_key, mode)

    def has_document(self, storage_key: str) -> bool:
        return self.document_storage.exists(storage_key)

    def delete_document(self, storage_key: str, *, missing_ok: bool = True) -> bool:
        return self.document_storage.delete_document(storage_key, missing_ok=missing_ok)

    def storage_key_for_absolute_path(self, absolute_path: Path) -> str | None:
        return self.document_storage.storage_key_for_absolute_path(absolute_path)

    def save_debug_artifact(
        self,
        *,
        filename: str,
        content: bytes,
        subdir: str | None = None,
    ) -> StoredArtifact:
        return self.debug_storage.save_artifact(filename=filename, content=content, subdir=subdir)

    def write_debug_json(self, relative_name: str, payload: dict) -> Path:
        return self.debug_storage.write_json(relative_name, payload)

    def read_debug_json(self, relative_name: str) -> dict | None:
        return self.debug_storage.read_json(relative_name)

    def list_debug_files(self) -> list[Path]:
        return self.debug_storage.iter_files()

    def list_expired_debug_files(self, *, cutoff) -> list[Path]:
        return self.debug_storage.list_expired_files(cutoff=cutoff)

    def delete_debug_file(self, path: Path, *, missing_ok: bool = True) -> bool:
        return self.debug_storage.delete_file(path, missing_ok=missing_ok)

    def create_export(
        self,
        *,
        suggested_name: str,
        content: bytes,
        suffix: str,
    ) -> StoredArtifact:
        return self.export_storage.create_export(suggested_name=suggested_name, content=content, suffix=suffix)

    def list_export_files(self) -> list[Path]:
        return self.export_storage.iter_files()

    def list_expired_export_files(self, *, cutoff) -> list[Path]:
        return self.export_storage.list_expired_files(cutoff=cutoff)

    def delete_export_file(self, path: Path, *, missing_ok: bool = True) -> bool:
        return self.export_storage.delete_file(path, missing_ok=missing_ok)

    def list_retained_failures(self) -> list[Path]:
        return self.document_storage.list_retained_failures()

    def create_temp_working_copy(self, source_path: Path) -> Path:
        return self.temp_storage.create_working_copy(source_path)

    def delete_temp_file(self, path: Path, *, missing_ok: bool = True) -> bool:
        return self.temp_storage.delete(path, missing_ok=missing_ok)

    def list_temp_files(self) -> list[Path]:
        return self.temp_storage.iter_files()

    def list_expired_temp_files(self, *, cutoff) -> list[Path]:
        return self.temp_storage.list_expired_files(cutoff=cutoff)

    def reserve_inbox_path(self, filename: str) -> Path:
        return reserve_unique_filename(self.inbox_root, filename)

    def save_upload_to_inbox(self, *, filename: str, fileobj) -> Path:
        destination = self.reserve_inbox_path(filename)
        with destination.open("wb") as output_file:
            shutil.copyfileobj(fileobj, output_file, length=1024 * 1024)
        return destination.resolve()

    def list_inbox_pdf_files(self) -> list[Path]:
        if not self.inbox_root.exists():
            return []
        return sorted(
            [path for path in self.inbox_root.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"],
            key=lambda item: item.name.lower(),
        )

    def delete_inbox_file(self, filename: str) -> bool:
        path = self.inbox_root / filename
        if not path.exists():
            return False
        path.unlink(missing_ok=True)
        return True

    def legacy_path_exists(self, path: Path) -> bool:
        return path.exists()

    def delete_legacy_path(self, path: Path, *, missing_ok: bool = True) -> bool:
        if not path.exists():
            return False if not missing_ok else False
        path.unlink(missing_ok=missing_ok)
        return True

    def existing_legacy_path(self, path_str: str | None) -> Path | None:
        if not path_str:
            return None
        path = Path(path_str)
        if path.exists():
            return path
        return None

    def legacy_path_exists_str(self, path_str: str | None) -> bool:
        return self.existing_legacy_path(path_str) is not None

    def delete_legacy_path_str(self, path_str: str | None, *, missing_ok: bool = True) -> bool:
        path = self.existing_legacy_path(path_str)
        if path is None:
            return False if not missing_ok else False
        path.unlink(missing_ok=missing_ok)
        return True


def get_storage_service(settings) -> LocalStorageService:
    return LocalStorageService(settings)


def _settings_path(settings, path_attr: str, raw_attr: str, fallback: str) -> Path:
    resolved = getattr(settings, path_attr, None)
    if resolved is not None:
        return Path(resolved)
    raw_value = getattr(settings, raw_attr, None)
    if raw_value is not None:
        return resolve_path(str(raw_value))
    return resolve_path(fallback)
