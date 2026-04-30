from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.batch.fingerprint import compute_sha256
from app.batch.service import HomeBatchSummary, get_latest_home_batch_summary
from app.config import Settings
from app.db.models import BatchRun, Document, DocumentReference, ProcessingLog
from app.db.postgres import create_postgres_session_factory
from app.logging_config import get_logger
from app.services.inbox_paths import get_inbox_path


logger = get_logger(__name__)


@dataclass(frozen=True)
class InboxFileItem:
    index: int
    file_name: str
    file_size_bytes: int
    file_size_label: str
    uploaded_at: str
    status: str


@dataclass(frozen=True)
class ResultsRow:
    index: int
    document_id: int
    original_file_name: str
    page_number: int
    source_type: str
    reference_class: str
    raw_reference: str
    resolution_status: str
    processed_at: str


@dataclass(frozen=True)
class ExportSummary:
    processed_documents: int
    total_references: int
    latest_batch: HomeBatchSummary | None


@dataclass(frozen=True)
class BatchHistoryItem:
    batch_run_id: int
    triggered_by: str
    status: str
    total_files_seen: int
    total_files_processed: int
    duplicate_files_skipped: int
    failed_files: int
    total_references_found: int
    started_at: str
    finished_at: str


@dataclass(frozen=True)
class ErrorInsightItem:
    created_at: str
    level: str
    code: str
    step_name: str
    document_name: str
    message: str


BATCH_STATUS_LABELS = {
    "completed": "Completed",
    "completed_with_errors": "Completed with errors",
    "running": "Running",
}
SOURCE_TYPE_LABELS = {
    "text": "Text",
    "qr": "QR",
    "image": "Image / QR",
    "ocr": "OCR",
}
REFERENCE_CLASS_LABELS = {
    "url": "URL",
    "short_url": "Short URL",
    "non_url": "Non-URL",
    "qr": "QR",
}
RESOLUTION_STATUS_LABELS = {
    "raw_only": "Raw only",
    "pending": "Pending",
    "resolved": "Resolved",
    "failed": "Failed",
}
INBOX_STATUS_ERROR = "Error"
INBOX_STATUS_DUPLICATE = "Duplicate"
INBOX_STATUS_PENDING = "Pending"


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.astimezone().strftime("%d/%m/%Y %H:%M")


def format_file_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    unit = units[0]
    for next_unit in units:
        unit = next_unit
        if size < 1024 or next_unit == units[-1]:
            break
        size /= 1024
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"


def _fetch_processed_hashes(session: Session) -> set[str]:
    statement: Select[tuple[str]] = select(Document.content_hash).where(Document.processing_status == "processed")
    return set(session.execute(statement).scalars().all())


def translate_batch_status(status: str) -> str:
    return BATCH_STATUS_LABELS.get(status, status)


def translate_source_type(source_type: str) -> str:
    return SOURCE_TYPE_LABELS.get(source_type, source_type)


def translate_reference_class(reference_class: str) -> str:
    return REFERENCE_CLASS_LABELS.get(reference_class, reference_class)


def translate_resolution_status(resolution_status: str) -> str:
    return RESOLUTION_STATUS_LABELS.get(resolution_status, resolution_status)


def localize_batch_summary(batch_summary):
    if batch_summary is None:
        return None
    batch_summary.status = translate_batch_status(batch_summary.status)
    return batch_summary


def _extract_issue_code(message: str) -> str:
    if message.startswith("[") and "]" in message:
        return message[1 : message.index("]")]
    return "UNCATEGORIZED"


def _strip_issue_code(message: str) -> str:
    if message.startswith("[") and "] " in message:
        return message.split("] ", 1)[1]
    return message


def list_inbox_files(settings: Settings, postgres_engine) -> list[InboxFileItem]:
    input_dir = get_inbox_path(settings)
    session_factory = create_postgres_session_factory(postgres_engine)
    with session_factory() as session:
        processed_hashes = _fetch_processed_hashes(session)

    files = sorted(
        [path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    logger.info(
        "Inbox listing path=%s files_found=%s files=%s",
        input_dir,
        len(files),
        [path.name for path in files],
    )

    inbox_items: list[InboxFileItem] = []
    for index, file_path in enumerate(files, start=1):
        file_stat = file_path.stat()
        try:
            content_hash = compute_sha256(file_path)
        except Exception:
            status = INBOX_STATUS_ERROR
        else:
            status = INBOX_STATUS_DUPLICATE if content_hash in processed_hashes else INBOX_STATUS_PENDING

        inbox_items.append(
            InboxFileItem(
                index=index,
                file_name=file_path.name,
                file_size_bytes=file_stat.st_size,
                file_size_label=format_file_size(file_stat.st_size),
                uploaded_at=format_datetime(datetime.fromtimestamp(file_stat.st_mtime)),
                status=status,
            )
        )
    return inbox_items


def count_pending_inbox_files(settings: Settings, postgres_engine) -> int:
    return sum(1 for item in list_inbox_files(settings, postgres_engine) if item.status == INBOX_STATUS_PENDING)


def fetch_latest_batch(postgres_engine) -> HomeBatchSummary | None:
    session_factory = create_postgres_session_factory(postgres_engine)
    with session_factory() as session:
        return localize_batch_summary(get_latest_home_batch_summary(session))


def fetch_recent_batches(postgres_engine, *, limit: int = 10) -> list[BatchHistoryItem]:
    session_factory = create_postgres_session_factory(postgres_engine)
    with session_factory() as session:
        rows = session.execute(
            select(BatchRun).order_by(BatchRun.started_at.desc(), BatchRun.id.desc()).limit(limit)
        ).scalars()
        return [
            BatchHistoryItem(
                batch_run_id=row.id,
                triggered_by=row.triggered_by,
                status=translate_batch_status(row.status),
                total_files_seen=row.total_files_seen,
                total_files_processed=row.total_files_processed,
                duplicate_files_skipped=row.duplicate_files_skipped,
                failed_files=row.failed_files,
                total_references_found=row.total_references_found,
                started_at=format_datetime(row.started_at),
                finished_at=format_datetime(row.finished_at),
            )
            for row in rows
        ]


def fetch_recent_error_insights(postgres_engine, *, limit: int = 20) -> list[ErrorInsightItem]:
    session_factory = create_postgres_session_factory(postgres_engine)
    with session_factory() as session:
        rows = session.execute(
            select(ProcessingLog, Document.original_file_name)
            .select_from(ProcessingLog)
            .outerjoin(Document, ProcessingLog.document_id == Document.id)
            .where(ProcessingLog.level.in_(("WARNING", "ERROR")))
            .order_by(ProcessingLog.created_at.desc(), ProcessingLog.id.desc())
            .limit(limit)
        ).all()

    return [
        ErrorInsightItem(
            created_at=format_datetime(row.ProcessingLog.created_at),
            level=row.ProcessingLog.level,
            code=_extract_issue_code(row.ProcessingLog.message),
            step_name=row.ProcessingLog.step_name,
            document_name=row.original_file_name or "-",
            message=_strip_issue_code(row.ProcessingLog.message),
        )
        for row in rows
    ]


def fetch_results_rows(postgres_engine, *, limit: int = 200) -> list[ResultsRow]:
    session_factory = create_postgres_session_factory(postgres_engine)
    with session_factory() as session:
        rows = session.execute(
            select(
                DocumentReference.document_id,
                Document.original_file_name,
                DocumentReference.page_number,
                DocumentReference.source_type,
                DocumentReference.reference_class,
                DocumentReference.raw_reference,
                DocumentReference.resolution_status,
                Document.processed_at,
            )
            .select_from(DocumentReference)
            .join(Document, DocumentReference.document_id == Document.id)
            .order_by(DocumentReference.id.desc())
            .limit(limit)
        ).all()

    return [
        ResultsRow(
            index=index,
            document_id=row.document_id,
            original_file_name=row.original_file_name,
            page_number=row.page_number,
            source_type=translate_source_type(row.source_type),
            reference_class=translate_reference_class(row.reference_class),
            raw_reference=row.raw_reference,
            resolution_status=translate_resolution_status(row.resolution_status),
            processed_at=format_datetime(row.processed_at),
        )
        for index, row in enumerate(rows, start=1)
    ]


def fetch_export_summary(postgres_engine) -> ExportSummary:
    session_factory = create_postgres_session_factory(postgres_engine)
    with session_factory() as session:
        processed_documents = session.execute(
            select(func.count(Document.id)).where(Document.processing_status == "processed")
        ).scalar_one()
        total_references = session.execute(select(func.count(DocumentReference.id))).scalar_one()
        latest_batch = get_latest_home_batch_summary(session)

    return ExportSummary(
        processed_documents=processed_documents,
        total_references=total_references,
        latest_batch=localize_batch_summary(latest_batch),
    )


def safe_inbox_file_path(settings: Settings, file_name: str) -> Path | None:
    input_root = get_inbox_path(settings)
    candidate = (input_root / file_name).resolve()
    if candidate.parent != input_root or not candidate.exists():
        return None
    return candidate
