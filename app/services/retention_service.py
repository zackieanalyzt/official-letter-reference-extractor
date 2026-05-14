from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentIngestion
from app.lifecycle import (
    ACTOR_RETENTION_SERVICE,
    EVENT_DOCUMENT_CLEANED,
    STATE_CLEANED,
    transition_document_state,
)
from app.logging_config import get_logger
from app.storage import get_storage_service


logger = get_logger(__name__)


@dataclass(frozen=True)
class SourceRetentionOutcome:
    retained_path: str | None
    storage_key: str | None
    source_file_present: bool
    retry_source_available: bool
    cleanup_due_at: datetime | None
    retry_requires_reupload: bool
    deleted_count: int = 0


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _retain_source(file_path: Path, settings, *, content_hash: str, mime_type: str | None) -> SourceRetentionOutcome:
    storage = get_storage_service(settings)
    stored = storage.save_document(
        file_path,
        original_filename=file_path.name,
        sha256=content_hash,
        mime_type=mime_type,
    )
    storage.delete_legacy_path(file_path)
    return SourceRetentionOutcome(
        retained_path=str(stored.absolute_path),
        storage_key=stored.storage_key,
        source_file_present=True,
        retry_source_available=True,
        cleanup_due_at=None,
        retry_requires_reupload=False,
    )


def apply_source_retention_for_success(
    file_path: Path, settings, *, reused_cached: bool, content_hash: str, mime_type: str | None
) -> SourceRetentionOutcome:
    mode = settings.file_retention_mode
    storage = get_storage_service(settings)
    if reused_cached and settings.source_delete_on_cache_reuse:
        storage.delete_legacy_path(file_path)
        return SourceRetentionOutcome(None, None, False, False, None, True)

    if mode == "retain_source":
        return _retain_source(file_path, settings, content_hash=content_hash, mime_type=mime_type)

    storage.delete_legacy_path(file_path)
    return SourceRetentionOutcome(None, None, False, False, None, True)


def apply_source_retention_for_failure(
    file_path: Path, settings, *, content_hash: str, mime_type: str | None
) -> SourceRetentionOutcome:
    mode = settings.file_retention_mode
    storage = get_storage_service(settings)
    if mode == "immediate_ephemeral":
        storage.delete_legacy_path(file_path)
        return SourceRetentionOutcome(None, None, False, False, None, True)

    retained = _retain_source(file_path, settings, content_hash=content_hash, mime_type=mime_type)
    cleanup_due_at = _utcnow() + timedelta(hours=settings.failed_source_retention_hours)
    return SourceRetentionOutcome(
        retained_path=retained.retained_path,
        storage_key=retained.storage_key,
        source_file_present=True,
        retry_source_available=True,
        cleanup_due_at=cleanup_due_at,
        retry_requires_reupload=False,
    )


def reconcile_document_source_flags(session: Session, document_id: int, *, update_lifecycle_state: bool = True) -> None:
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
    if update_lifecycle_state:
        if latest_retained is None and document.processing_status == "failed":
            document.lifecycle_state = "cleaned"
        elif latest_retained is not None and document.processing_status == "failed":
            document.lifecycle_state = "retained"
        elif document.processing_status == "processed":
            document.lifecycle_state = "resolved"
    session.flush()


def cleanup_retained_failures(session: Session, settings, *, dry_run: bool = False) -> dict[str, int]:
    now = _utcnow()
    summary = {
        "cleanup_type": "retained_sources",
        "candidates": 0,
        "failed_sources_deleted": 0,
        "ingestions_reconciled": 0,
        "skipped_processing": 0,
        "skipped_missing_reference": 0,
    }
    storage = get_storage_service(settings)

    expired_ingestions = session.execute(
        select(DocumentIngestion).where(
            DocumentIngestion.source_file_present.is_(True),
            DocumentIngestion.cleanup_due_at.is_not(None),
            DocumentIngestion.cleanup_due_at <= now,
        )
    ).scalars().all()

    affected_document_ids: dict[int, dict[str, object]] = {}
    for ingestion in expired_ingestions:
        summary["candidates"] += 1
        document = session.get(Document, ingestion.document_id)
        if document is not None and document.processing_status == "processing":
            summary["skipped_processing"] += 1
            continue

        deleted = False
        preferred_storage_key = document.storage_key if document is not None else None
        if preferred_storage_key:
            if dry_run:
                deleted = storage.has_document(preferred_storage_key)
            else:
                deleted = storage.delete_document(preferred_storage_key)
        elif ingestion.source_file_path:
            if dry_run:
                deleted = storage.legacy_path_exists_str(ingestion.source_file_path)
            else:
                deleted = storage.delete_legacy_path_str(ingestion.source_file_path)
        else:
            summary["skipped_missing_reference"] += 1

        if deleted:
            summary["failed_sources_deleted"] += 1
        if dry_run:
            continue
        ingestion.source_file_present = False
        ingestion.retry_source_available = False
        ingestion.source_deleted_at = now
        if ingestion.document_id not in affected_document_ids:
            affected_document_ids[ingestion.document_id] = {
                "storage_key_present_before": bool(preferred_storage_key),
                "previous_state": document.lifecycle_state if document is not None else None,
            }

    for document_id, context in affected_document_ids.items():
        document = session.get(Document, document_id)
        previous_state = context["previous_state"]
        reconcile_document_source_flags(session, document_id, update_lifecycle_state=False)
        if (
            document is not None
            and document.processing_status == "failed"
            and not document.source_file_present
            and previous_state in {"retained", "failed"}
        ):
            transition_document_state(
                session,
                document=document,
                event_type=EVENT_DOCUMENT_CLEANED,
                to_state=STATE_CLEANED,
                actor_source=ACTOR_RETENTION_SERVICE,
                metadata={
                    "cleanup_type": "retained_sources",
                    "reason": "retention_expired",
                    "cleanup_trigger": "run_retention_cleanup",
                    "storage_key_present_before": context["storage_key_present_before"],
                },
            )
        summary["ingestions_reconciled"] += 1

    session.flush()
    logger.info("[RETENTION_CLEANUP_FAILED] dry_run=%s summary=%s", dry_run, summary)
    return summary


def cleanup_old_debug_artifacts(settings, *, dry_run: bool = False) -> dict[str, int]:
    now = _utcnow()
    summary = {"cleanup_type": "debug_artifacts", "candidates": 0, "debug_deleted": 0}
    storage = get_storage_service(settings)
    debug_cutoff = now - timedelta(hours=settings.qr_debug_retention_hours)
    for path in storage.list_expired_debug_files(cutoff=debug_cutoff):
        summary["candidates"] += 1
        if not dry_run:
            storage.delete_debug_file(path)
        summary["debug_deleted"] += 1
    logger.info("[RETENTION_CLEANUP_DEBUG] dry_run=%s summary=%s", dry_run, summary)
    return summary


def cleanup_runtime_tmp(settings, *, dry_run: bool = False) -> dict[str, int]:
    now = _utcnow()
    summary = {"cleanup_type": "runtime_tmp", "candidates": 0, "temp_deleted": 0}
    storage = get_storage_service(settings)
    temp_cutoff = now - timedelta(hours=settings.temp_file_max_age_hours)
    for path in storage.list_expired_temp_files(cutoff=temp_cutoff):
        summary["candidates"] += 1
        if not dry_run:
            storage.delete_temp_file(path)
        summary["temp_deleted"] += 1
    logger.info("[RETENTION_CLEANUP_TMP] dry_run=%s summary=%s", dry_run, summary)
    return summary


def cleanup_expired_exports(settings, *, dry_run: bool = False) -> dict[str, int]:
    now = _utcnow()
    summary = {"cleanup_type": "exports", "candidates": 0, "exports_deleted": 0}
    storage = get_storage_service(settings)
    export_cutoff = now - timedelta(hours=settings.export_retention_hours)
    for path in storage.list_expired_export_files(cutoff=export_cutoff):
        summary["candidates"] += 1
        if not dry_run:
            storage.delete_export_file(path)
        summary["exports_deleted"] += 1
    logger.info("[RETENTION_CLEANUP_EXPORTS] dry_run=%s summary=%s", dry_run, summary)
    return summary


def run_retention_cleanup(session: Session, settings, *, dry_run: bool = False) -> dict[str, int]:
    summary = {"failed_sources_deleted": 0, "debug_deleted": 0, "temp_deleted": 0, "exports_deleted": 0, "ingestions_reconciled": 0}

    failed_summary = cleanup_retained_failures(session, settings, dry_run=dry_run)
    debug_summary = cleanup_old_debug_artifacts(settings, dry_run=dry_run)
    temp_summary = cleanup_runtime_tmp(settings, dry_run=dry_run)
    export_summary = cleanup_expired_exports(settings, dry_run=dry_run)

    summary.update(failed_summary)
    summary.update(debug_summary)
    summary.update(temp_summary)
    summary.update(export_summary)

    if dry_run:
        logger.info("[RETENTION_CLEANUP] dry_run=%s summary=%s", dry_run, summary)
        return summary

    present_ingestions = session.execute(
        select(DocumentIngestion).where(DocumentIngestion.source_file_present.is_(True))
    ).scalars().all()
    storage = get_storage_service(settings)
    affected_document_ids: set[int] = set()
    for ingestion in present_ingestions:
        has_source = False
        document = session.get(Document, ingestion.document_id)
        preferred_storage_key = document.storage_key if document is not None else None
        if preferred_storage_key:
            has_source = storage.has_document(preferred_storage_key)
        elif ingestion.source_file_path:
            has_source = storage.legacy_path_exists_str(ingestion.source_file_path)
        if ingestion.source_file_path and not has_source:
            ingestion.source_file_present = False
            ingestion.retry_source_available = False
            ingestion.source_deleted_at = _utcnow()
            affected_document_ids.add(ingestion.document_id)

    for document_id in affected_document_ids:
        reconcile_document_source_flags(session, document_id)
        summary["ingestions_reconciled"] += 1

    session.flush()
    logger.info("[RETENTION_CLEANUP] dry_run=%s summary=%s", dry_run, summary)
    return summary
