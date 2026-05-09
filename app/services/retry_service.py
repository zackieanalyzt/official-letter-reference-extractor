from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.batch.url_resolution import re_resolve_document_references
from app.db.models import Document
from app.services.process_batch import process_single_document_from_retained_source


@dataclass(frozen=True)
class RetryResult:
    success: bool
    reason: str
    destination_path: str | None = None
    batch_run_id: int | None = None


def _source_path_for_document(document: Document) -> Path | None:
    if document.last_source_path:
        path = Path(document.last_source_path)
        if path.exists():
            return path
    return None


def retry_failed_document(session, settings, database_engine, document_id: int) -> RetryResult:
    document = session.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if document is None:
        return RetryResult(False, "not_found")
    if document.processing_status != "failed":
        return RetryResult(False, "not_failed")

    source_path = _source_path_for_document(document)
    if source_path is None:
        document.retry_requires_reupload = True
        document.source_file_present = False
        if document.processing_status == "failed":
            document.lifecycle_state = "deleted"
        session.flush()
        return RetryResult(False, "requires_reupload")

    summary = process_single_document_from_retained_source(
        settings,
        database_engine,
        document=document,
        source_path=source_path,
        triggered_by="retry_extraction",
        force_reprocess=False,
    )
    return RetryResult(True, "queued", str(source_path), summary.batch_run_id)


def force_reprocess_document(session, settings, database_engine, document_id: int) -> RetryResult:
    document = session.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if document is None:
        return RetryResult(False, "not_found")

    source_path = _source_path_for_document(document)
    if source_path is None:
        document.retry_requires_reupload = True
        document.source_file_present = False
        if document.processing_status == "failed":
            document.lifecycle_state = "deleted"
        session.flush()
        return RetryResult(False, "requires_reupload")

    summary = process_single_document_from_retained_source(
        settings,
        database_engine,
        document=document,
        source_path=source_path,
        triggered_by="force_reprocess",
        force_reprocess=True,
    )
    return RetryResult(True, "reprocessed", str(source_path), summary.batch_run_id)


def retry_document_resolution(session, settings, document_id: int) -> RetryResult:
    document = session.execute(select(Document).where(Document.id == document_id)).scalar_one_or_none()
    if document is None:
        return RetryResult(False, "not_found")

    re_resolve_document_references(session, document.id, settings=settings)
    return RetryResult(True, "resolution_retried")
