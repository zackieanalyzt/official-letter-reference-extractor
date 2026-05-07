from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.batch.file_ops import build_destination_path, ensure_directory
from app.db.models import Document, DocumentIngestion
from app.logging_config import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class SourceRetentionOutcome:
    retained_path: str | None
    source_file_present: bool
    retry_source_available: bool
    cleanup_due_at: datetime | None
    retry_requires_reupload: bool


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _delete_file_if_exists(path: Path) -> bool:
    if not path.exists():
        return False
    path.unlink()
    return True


def _retain_failed_source(file_path: Path, settings) -> Path:
    destination_dir = ensure_directory(settings.failed_retained_path)
    destination = build_destination_path(destination_dir, file_path.name, "failedretained")
    if destination.resolve() == file_path.resolve():
        return destination
    file_path.replace(destination)
    return destination


def _retain_processed_source(file_path: Path, settings, content_hash: str) -> Path:
    destination_dir = ensure_directory(settings.processed_path)
    destination = build_destination_path(destination_dir, file_path.name, content_hash)
    if destination.resolve() == file_path.resolve():
        return destination
    file_path.replace(destination)
    return destination


def apply_source_retention_for_success(
    file_path: Path, settings, *, reused_cached: bool, content_hash: str
) -> SourceRetentionOutcome:
    mode = settings.file_retention_mode
    if reused_cached and settings.source_delete_on_cache_reuse:
        _delete_file_if_exists(file_path)
        return SourceRetentionOutcome(None, False, False, None, True)

    if mode == "retain_source":
        retained_path = _retain_processed_source(file_path, settings, content_hash)
        return SourceRetentionOutcome(str(retained_path), True, True, None, False)

    _delete_file_if_exists(file_path)
    return SourceRetentionOutcome(None, False, False, None, True)


def apply_source_retention_for_failure(file_path: Path, settings) -> SourceRetentionOutcome:
    mode = settings.file_retention_mode
    if mode == "immediate_ephemeral":
        _delete_file_if_exists(file_path)
        return SourceRetentionOutcome(None, False, False, None, True)

    retained_path = _retain_failed_source(file_path, settings)
    cleanup_due_at = _utcnow() + timedelta(hours=settings.failed_source_retention_hours)
    return SourceRetentionOutcome(str(retained_path), True, True, cleanup_due_at, False)


def reconcile_document_source_flags(session: Session, document_id: int) -> None:
    ingestions = session.execute(
        select(DocumentIngestion).where(DocumentIngestion.document_id == document_id)
    ).scalars().all()
    document = session.get(Document, document_id)
    if document is None:
        return

    retained = [ing for ing in ingestions if ing.source_file_present and ing.source_file_path]
    latest_retained = retained[-1] if retained else None
    document.source_file_present = bool(latest_retained)
    document.retry_requires_reupload = not bool(latest_retained)
    document.last_source_path = latest_retained.source_file_path if latest_retained else None
    document.source_deleted_at = None if latest_retained else _utcnow()
    session.flush()


def run_retention_cleanup(session: Session, settings) -> dict[str, int]:
    now = _utcnow()
    summary = {"failed_sources_deleted": 0, "debug_deleted": 0, "temp_deleted": 0, "ingestions_reconciled": 0}

    expired_ingestions = session.execute(
        select(DocumentIngestion).where(
            DocumentIngestion.source_file_present.is_(True),
            DocumentIngestion.cleanup_due_at.is_not(None),
            DocumentIngestion.cleanup_due_at <= now,
        )
    ).scalars().all()

    affected_document_ids: set[int] = set()
    for ingestion in expired_ingestions:
        if ingestion.source_file_path:
            deleted = _delete_file_if_exists(Path(ingestion.source_file_path))
            if deleted:
                summary["failed_sources_deleted"] += 1
        ingestion.source_file_present = False
        ingestion.retry_source_available = False
        ingestion.source_deleted_at = now
        affected_document_ids.add(ingestion.document_id)

    debug_dir = ensure_directory(settings.qr_debug_path)
    debug_cutoff = now - timedelta(hours=settings.qr_debug_retention_hours)
    if debug_dir.exists():
        for path in debug_dir.glob("*"):
            if path.is_file() and datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) <= debug_cutoff:
                path.unlink(missing_ok=True)
                summary["debug_deleted"] += 1

    temp_dir = ensure_directory(settings.runtime_tmp_path)
    temp_cutoff = now - timedelta(hours=settings.temp_file_max_age_hours)
    if temp_dir.exists():
        for path in temp_dir.glob("*"):
            if path.is_file() and datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) <= temp_cutoff:
                path.unlink(missing_ok=True)
                summary["temp_deleted"] += 1

    present_ingestions = session.execute(
        select(DocumentIngestion).where(DocumentIngestion.source_file_present.is_(True))
    ).scalars().all()
    for ingestion in present_ingestions:
        if ingestion.source_file_path and not Path(ingestion.source_file_path).exists():
            ingestion.source_file_present = False
            ingestion.retry_source_available = False
            ingestion.source_deleted_at = now
            affected_document_ids.add(ingestion.document_id)

    for document_id in affected_document_ids:
        reconcile_document_source_flags(session, document_id)
        summary["ingestions_reconciled"] += 1

    session.flush()
    return summary
