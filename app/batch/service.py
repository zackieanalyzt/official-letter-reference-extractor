from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.models import BatchRun, Document, DocumentReference, ProcessingLog


@dataclass
class HomeBatchSummary:
    batch_run_id: int
    status: str
    total_files_seen: int
    total_files_processed: int
    duplicate_files_skipped: int
    total_references_found: int
    finished_at: datetime | None
    failed_files: int


def create_batch_run(session: Session, triggered_by: str) -> BatchRun:
    batch_run = BatchRun(triggered_by=triggered_by, status="running")
    session.add(batch_run)
    session.flush()
    return batch_run


def finalize_batch_run(
    session: Session,
    batch_run: BatchRun,
    *,
    total_files_seen: int,
    total_files_processed: int,
    duplicate_files_skipped: int,
    failed_files: int,
    total_references_found: int,
    status: str,
) -> BatchRun:
    batch_run.total_files_seen = total_files_seen
    batch_run.total_files_processed = total_files_processed
    batch_run.duplicate_files_skipped = duplicate_files_skipped
    batch_run.failed_files = failed_files
    batch_run.total_references_found = total_references_found
    batch_run.status = status
    batch_run.finished_at = datetime.now(UTC)
    session.flush()
    return batch_run


def find_processed_document_by_hash(session: Session, content_hash: str) -> Document | None:
    statement: Select[tuple[Document]] = select(Document).where(
        Document.content_hash == content_hash,
        Document.processing_status == "processed",
    )
    return session.execute(statement).scalar_one_or_none()


def create_document_row(
    session: Session,
    *,
    batch_run_id: int,
    original_file_name: str,
    content_hash: str,
    file_size_bytes: int,
) -> Document:
    document = Document(
        batch_run_id=batch_run_id,
        original_file_name=original_file_name,
        content_hash=content_hash,
        file_size_bytes=file_size_bytes,
        processing_status="processing",
    )
    session.add(document)
    session.flush()
    return document


def mark_document_processed(session: Session, document: Document, moved_to_path: str) -> Document:
    document.processing_status = "processed"
    document.processing_error = None
    document.processed_at = datetime.now(UTC)
    document.moved_to_path = moved_to_path
    session.flush()
    return document


def mark_document_failed(
    session: Session,
    document: Document,
    error_message: str,
    moved_to_path: str,
    *,
    error_type: str | None = None,
    error_detail: str | None = None,
) -> Document:
    document.processing_status = "failed"
    document.processing_error = error_message
    document.processing_error_type = error_type
    document.processing_error_detail = error_detail
    document.moved_to_path = moved_to_path
    session.flush()
    return document


def set_document_processing_issue(
    session: Session,
    document: Document,
    *,
    error_type: str | None,
    error_detail: str | None,
) -> Document:
    document.processing_error_type = error_type
    document.processing_error_detail = error_detail
    session.flush()
    return document


def create_document_reference(
    session: Session,
    *,
    document_id: int,
    page_number: int,
    source_type: str,
    reference_class: str,
    raw_reference: str,
) -> DocumentReference:
    reference = DocumentReference(
        document_id=document_id,
        page_number=page_number,
        source_type=source_type,
        reference_class=reference_class,
        raw_reference=raw_reference,
        final_url=None,
        resolution_status="pending",
        http_status=None,
        resolution_error_type=None,
        resolution_error_detail=None,
    )
    session.add(reference)
    session.flush()
    return reference


def create_processing_log(
    session: Session,
    *,
    level: str,
    step_name: str,
    message: str,
    batch_run_id: int | None = None,
    document_id: int | None = None,
) -> ProcessingLog:
    log_row = ProcessingLog(
        batch_run_id=batch_run_id,
        document_id=document_id,
        level=level,
        step_name=step_name,
        message=message,
    )
    session.add(log_row)
    session.flush()
    return log_row


def get_latest_home_batch_summary(session: Session) -> HomeBatchSummary | None:
    latest_batch = session.execute(
        select(BatchRun).order_by(BatchRun.started_at.desc(), BatchRun.id.desc()).limit(1)
    ).scalar_one_or_none()
    if not latest_batch:
        return None

    return HomeBatchSummary(
        batch_run_id=latest_batch.id,
        status=latest_batch.status,
        total_files_seen=latest_batch.total_files_seen,
        total_files_processed=latest_batch.total_files_processed,
        duplicate_files_skipped=latest_batch.duplicate_files_skipped,
        total_references_found=latest_batch.total_references_found,
        finished_at=latest_batch.finished_at,
        failed_files=latest_batch.failed_files,
    )


def count_batch_references(session: Session, batch_run_id: int) -> int:
    return session.execute(
        select(func.count(DocumentReference.id))
        .select_from(DocumentReference)
        .join(Document, DocumentReference.document_id == Document.id)
        .where(Document.batch_run_id == batch_run_id)
    ).scalar_one()
