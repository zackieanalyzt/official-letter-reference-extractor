from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.batch.file_ops import build_destination_path, ensure_directory
from app.config import Settings
from app.db.models import Document
from app.services.inbox_paths import get_inbox_path


@dataclass(frozen=True)
class RetryResult:
    success: bool
    reason: str
    destination_path: str | None = None


def _candidate_paths(document: Document, settings: Settings) -> list[Path]:
    paths: list[Path] = []
    if document.moved_to_path:
        paths.append(Path(document.moved_to_path))
    paths.extend(
        [
            settings.error_path / document.original_file_name,
            settings.processed_path / document.original_file_name,
            settings.input_path / document.original_file_name,
        ]
    )
    return paths


def retry_failed_document(session, settings: Settings, document_id: int) -> RetryResult:
    document = session.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if document is None:
        return RetryResult(False, "not_found")
    if document.processing_status != "failed":
        return RetryResult(False, "not_failed")

    source_path = next((path for path in _candidate_paths(document, settings) if path.exists()), None)
    if source_path is None:
        return RetryResult(False, "source_file_missing")

    inbox_path = get_inbox_path(settings)
    ensure_directory(inbox_path)
    destination_path = build_destination_path(
        inbox_path,
        document.original_file_name,
        document.content_hash,
    )
    shutil.copy2(source_path, destination_path)
    return RetryResult(True, "queued", str(destination_path))
