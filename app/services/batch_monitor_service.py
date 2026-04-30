from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import BatchRun, Document, DocumentReference


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%d/%m/%Y %H:%M")


def _format_duration(started_at: datetime | None, finished_at: datetime | None) -> str:
    if not started_at or not finished_at:
        return "-"
    duration = finished_at - started_at
    total_seconds = int(duration.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def list_batch_runs(session: Session, page: int = 1, page_size: int = 20) -> dict:
    safe_page = max(page, 1)
    safe_page_size = max(page_size, 1)
    offset = (safe_page - 1) * safe_page_size

    total = session.execute(select(func.count(BatchRun.id))).scalar_one()
    rows = session.execute(
        select(BatchRun)
        .order_by(BatchRun.started_at.desc(), BatchRun.id.desc())
        .limit(safe_page_size)
        .offset(offset)
    ).scalars()

    items = [
        {
            "batch_run_id": row.id,
            "started_at": _format_datetime(row.started_at),
            "finished_at": _format_datetime(row.finished_at),
            "status": row.status,
            "total_files_seen": row.total_files_seen,
            "total_files_processed": row.total_files_processed,
            "total_files_duplicate": row.duplicate_files_skipped,
            "total_files_error": row.failed_files,
            "total_references_found": row.total_references_found,
            "duration": _format_duration(row.started_at, row.finished_at),
            "triggered_by": row.triggered_by,
        }
        for row in rows
    ]

    return {
        "items": items,
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "has_prev": safe_page > 1,
        "has_next": offset + safe_page_size < total,
    }


def get_batch_run_detail(session: Session, batch_run_id: int) -> dict | None:
    batch_run = session.execute(select(BatchRun).where(BatchRun.id == batch_run_id)).scalar_one_or_none()
    if batch_run is None:
        return None

    document_rows = session.execute(
        select(
            Document.id,
            Document.original_file_name,
            Document.content_hash,
            Document.processing_status,
            Document.processing_error_type,
            func.count(DocumentReference.id).label("reference_count"),
        )
        .select_from(Document)
        .outerjoin(DocumentReference, DocumentReference.document_id == Document.id)
        .where(Document.batch_run_id == batch_run_id)
        .group_by(
            Document.id,
            Document.original_file_name,
            Document.content_hash,
            Document.processing_status,
            Document.processing_error_type,
        )
        .order_by(Document.id.desc())
    ).all()

    return {
        "batch": {
            "batch_run_id": batch_run.id,
            "started_at": _format_datetime(batch_run.started_at),
            "finished_at": _format_datetime(batch_run.finished_at),
            "status": batch_run.status,
            "triggered_by": batch_run.triggered_by,
            "total_files_seen": batch_run.total_files_seen,
            "total_files_processed": batch_run.total_files_processed,
            "total_files_duplicate": batch_run.duplicate_files_skipped,
            "total_files_error": batch_run.failed_files,
            "total_references_found": batch_run.total_references_found,
            "duration": _format_duration(batch_run.started_at, batch_run.finished_at),
        },
        "documents": [
            {
                "document_id": row.id,
                "filename": row.original_file_name,
                "content_hash": row.content_hash,
                "processing_status": row.processing_status,
                "processing_error_type": row.processing_error_type,
                "reference_count": row.reference_count,
            }
            for row in document_rows
        ],
    }
