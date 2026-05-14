from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.batch.url_resolution import re_resolve_document_references
from app.db.models import Document
from app.lifecycle import ACTOR_RETRY_SERVICE, EVENT_DOCUMENT_RETRY_REQUESTED, record_non_state_event
from app.services.process_batch import process_single_document_from_retained_source
from app.storage import get_storage_service


@dataclass(frozen=True)
class RetryResult:
    success: bool
    reason: str
    destination_path: str | None = None
    batch_run_id: int | None = None


def _source_path_for_document(document: Document, settings) -> Path | None:
    storage = get_storage_service(settings)
    if document.storage_key and storage.has_document(document.storage_key):
        return storage.resolve_storage_key(document.storage_key)
    return storage.existing_legacy_path(document.last_source_path)


def retry_failed_document(session, settings, database_engine, document_id: int) -> RetryResult:
    document = session.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if document is None:
        return RetryResult(False, "not_found")
    if document.processing_status != "failed":
        return RetryResult(False, "not_failed")

    source_path = _source_path_for_document(document, settings)
    if source_path is None:
        document.retry_requires_reupload = True
        document.source_file_present = False
        if document.processing_status == "failed":
            document.lifecycle_state = "failed"
        session.flush()
        return RetryResult(False, "requires_reupload")

    correlation_id = f"retry:{document.id}:{uuid4().hex}"
    record_non_state_event(
        session,
        document=document,
        event_type=EVENT_DOCUMENT_RETRY_REQUESTED,
        actor_source=ACTOR_RETRY_SERVICE,
        correlation_id=correlation_id,
        metadata={"mode": "retry_failed_document"},
    )
    summary = process_single_document_from_retained_source(
        settings,
        database_engine,
        document=document,
        source_path=source_path,
        triggered_by="retry_extraction",
        force_reprocess=False,
        correlation_id=correlation_id,
    )
    return RetryResult(True, "queued", str(source_path), summary.batch_run_id)


def force_reprocess_document(session, settings, database_engine, document_id: int) -> RetryResult:
    document = session.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if document is None:
        return RetryResult(False, "not_found")

    source_path = _source_path_for_document(document, settings)
    if source_path is None:
        document.retry_requires_reupload = True
        document.source_file_present = False
        if document.processing_status == "failed":
            document.lifecycle_state = "failed"
        session.flush()
        return RetryResult(False, "requires_reupload")

    correlation_id = f"retry:{document.id}:{uuid4().hex}"
    record_non_state_event(
        session,
        document=document,
        event_type=EVENT_DOCUMENT_RETRY_REQUESTED,
        actor_source=ACTOR_RETRY_SERVICE,
        correlation_id=correlation_id,
        metadata={"mode": "force_reprocess_document"},
    )
    summary = process_single_document_from_retained_source(
        settings,
        database_engine,
        document=document,
        source_path=source_path,
        triggered_by="force_reprocess",
        force_reprocess=True,
        correlation_id=correlation_id,
    )
    return RetryResult(True, "reprocessed", str(source_path), summary.batch_run_id)


def retry_document_resolution(session, settings, document_id: int) -> RetryResult:
    document = session.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if document is None:
        return RetryResult(False, "not_found")

    re_resolve_document_references(session, document.id, settings=settings)
    return RetryResult(True, "resolution_retried")
