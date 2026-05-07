import inspect
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.batch.error_types import (
    DUPLICATE_CONTENT,
    INVALID_PDF,
    NO_REFERENCE_FOUND,
    OCR_FAIL,
    OCR_NOT_AVAILABLE,
    QR_EXTRACTION_FAIL,
    TEXT_EXTRACTION_FAIL,
    UNKNOWN_ERROR,
)
from app.batch.file_ops import ensure_directory
from app.batch.fingerprint import FileFingerprint, build_file_fingerprint
from app.batch.pdf_validation import validate_pdf_readable
from app.batch.reference_extraction import ExtractionIssue, extract_references_from_pdf
from app.batch.scanner import discover_pdf_files
from app.batch.service import (
    HomeBatchSummary,
    count_batch_references,
    create_batch_run,
    create_document_ingestion,
    create_document_reference,
    create_or_get_document_row,
    create_processing_log,
    finalize_batch_run,
    find_document_by_hash,
    find_processed_document_by_hash,
    get_latest_home_batch_summary,
    mark_document_failed,
    mark_document_ingestion_status,
    mark_document_processed,
    set_document_processing_issue,
)
from app.batch.url_resolution import resolve_document_references
from app.config import Settings
from app.db.models import Document, DocumentIngestion, DocumentReference
from app.db.session import get_session_factory
from app.logging_config import get_logger
from app.services.inbox_paths import get_inbox_path
from app.services.retention_service import (
    apply_source_retention_for_failure,
    apply_source_retention_for_success,
    reconcile_document_source_flags,
)


logger = get_logger(__name__)


DOCUMENT_ERROR_PRIORITY = {
    INVALID_PDF: 100,
    OCR_NOT_AVAILABLE: 80,
    OCR_FAIL: 70,
    TEXT_EXTRACTION_FAIL: 60,
    QR_EXTRACTION_FAIL: 50,
    NO_REFERENCE_FOUND: 40,
    UNKNOWN_ERROR: 10,
}


@dataclass
class BatchProcessSummary:
    batch_run_id: int
    total_files_seen: int
    total_files_processed: int
    duplicate_files_skipped: int
    failed_files: int
    total_references_found: int
    status: str


def _select_document_issue(issues: list[ExtractionIssue]) -> tuple[str | None, str | None]:
    selected_type = None
    selected_message = None
    selected_priority = -1

    for issue in issues:
        priority = DOCUMENT_ERROR_PRIORITY.get(issue.error_type, 0)
        if priority > selected_priority:
            selected_type = issue.error_type
            selected_message = issue.message
            selected_priority = priority

    return selected_type, selected_message


def _replace_document_references(session: Session, document: Document, references: list) -> int:
    session.query(DocumentReference).filter(DocumentReference.document_id == document.id).delete()
    persisted_reference_keys: set[tuple[int, str, str]] = set()
    for reference in references:
        reference_key = (reference.page_number, reference.source_type, reference.raw_reference)
        if reference_key in persisted_reference_keys:
            continue
        persisted_reference_keys.add(reference_key)
        create_document_reference(
            session,
            document_id=document.id,
            page_number=reference.page_number,
            source_type=reference.source_type,
            reference_class=reference.reference_class,
            raw_reference=reference.raw_reference,
        )
    return len(persisted_reference_keys)


def _can_reuse_cached_result(
    document: Document | None,
    *,
    settings: Settings,
    force_reprocess: bool,
) -> bool:
    if document is None:
        return False
    if force_reprocess:
        return False
    return (
        document.processing_status == "processed"
        and document.extraction_version == settings.extraction_version
    )


def _process_document_from_source(
    session: Session,
    *,
    batch_run_id: int,
    document: Document,
    ingestion: DocumentIngestion,
    fingerprint: FileFingerprint,
    settings: Settings,
) -> None:
    try:
        validate_pdf_readable(fingerprint.path)
    except Exception as exc:
        error_message = f"[PDF_VALIDATION_FAILED] PDF validation failed: {exc}"
        logger.exception("PDF validation failed file=%s", fingerprint.path)
        create_processing_log(
            session,
            level="ERROR",
            step_name="pdf_validation",
            message=error_message,
            batch_run_id=batch_run_id,
            document_id=document.id,
        )
        retention = apply_source_retention_for_failure(fingerprint.path, settings)
        mark_document_failed(
            session,
            document,
            error_message,
            retention.retained_path,
            error_type=INVALID_PDF,
            error_detail=str(exc),
            source_file_present=retention.source_file_present,
            retry_requires_reupload=retention.retry_requires_reupload,
        )
        mark_document_ingestion_status(
            session,
            ingestion,
            ingestion_status="failed",
            used_cached_result=False,
            source_file_path=retention.retained_path,
            source_file_present=retention.source_file_present,
            retry_source_available=retention.retry_source_available,
            cleanup_due_at=retention.cleanup_due_at,
            error_type=INVALID_PDF,
            error_detail=str(exc),
        )
        reconcile_document_source_flags(session, document.id)
        raise

    previous_state = {
        "page_count": document.page_count,
        "document_number": document.document_number,
        "processing_status": document.processing_status,
        "processing_error": document.processing_error,
        "processing_error_type": document.processing_error_type,
        "processing_error_detail": document.processing_error_detail,
        "processed_at": document.processed_at,
        "extraction_version": document.extraction_version,
    }
    previous_references = [
        {
            "page_number": ref.page_number,
            "source_type": ref.source_type,
            "reference_class": ref.reference_class,
            "raw_reference": ref.raw_reference,
            "final_url": ref.final_url,
            "resolution_status": ref.resolution_status,
            "http_status": ref.http_status,
            "resolution_error_type": ref.resolution_error_type,
            "resolution_error_detail": ref.resolution_error_detail,
        }
        for ref in list(document.references)
    ]

    try:
        references: list = []
        extraction_issues: list[ExtractionIssue] = []
        extraction_signature = inspect.signature(extract_references_from_pdf)
        extraction_kwargs = {}
        if "settings" in extraction_signature.parameters:
            extraction_kwargs["settings"] = settings
        if "document_id" in extraction_signature.parameters:
            extraction_kwargs["document_id"] = document.id
        references, extraction_issues, page_count = extract_references_from_pdf(
            fingerprint.path,
            **extraction_kwargs,
        )
        document.page_count = page_count

        for issue in extraction_issues:
            message = f"[{issue.error_type}] {issue.message}"
            if issue.page_number is not None:
                message = f"{message} page={issue.page_number}"
            create_processing_log(
                session,
                level="WARNING",
                step_name=issue.step_name,
                message=message,
                batch_run_id=batch_run_id,
                document_id=document.id,
            )

        inserted_count = _replace_document_references(session, document, references)
        logger.info("[DB_INSERT] file=%s document_id=%s inserted=%s", fingerprint.path, document.id, inserted_count)
        error_type, error_detail = _select_document_issue(extraction_issues)
        if not references and error_type is None:
            error_type = UNKNOWN_ERROR
            error_detail = "No references found"
        set_document_processing_issue(session, document, error_type=error_type, error_detail=error_detail)
        document.original_file_name = fingerprint.original_file_name
        document.file_size_bytes = fingerprint.file_size_bytes
        document.extraction_version = settings.extraction_version
        resolve_document_references(session, document.id, settings=settings)

        retention = apply_source_retention_for_success(
            fingerprint.path,
            settings,
            reused_cached=False,
            content_hash=fingerprint.content_hash,
        )
        mark_document_processed(
            session,
            document,
            retention.retained_path,
            extraction_version=settings.extraction_version,
            source_file_present=retention.source_file_present,
            retry_requires_reupload=retention.retry_requires_reupload,
        )
        document.retention_mode = settings.file_retention_mode
        document.last_ingestion_used_cached_result = False
        document.batch_run_id = batch_run_id
        mark_document_ingestion_status(
            session,
            ingestion,
            ingestion_status="processed_fresh",
            used_cached_result=False,
            source_file_path=retention.retained_path,
            source_file_present=retention.source_file_present,
            retry_source_available=retention.retry_source_available,
            cleanup_due_at=retention.cleanup_due_at,
        )
        reconcile_document_source_flags(session, document.id)
    except Exception as exc:
        logger.exception("Document processing failed file=%s", fingerprint.path)
        session.query(DocumentReference).filter(DocumentReference.document_id == document.id).delete()
        document.page_count = previous_state["page_count"]
        document.document_number = previous_state["document_number"]
        document.processing_status = previous_state["processing_status"]
        document.processing_error = previous_state["processing_error"]
        document.processing_error_type = previous_state["processing_error_type"]
        document.processing_error_detail = previous_state["processing_error_detail"]
        document.processed_at = previous_state["processed_at"]
        document.extraction_version = previous_state["extraction_version"]
        for ref in previous_references:
            new_ref = create_document_reference(
                session,
                document_id=document.id,
                page_number=ref["page_number"],
                source_type=ref["source_type"],
                reference_class=ref["reference_class"],
                raw_reference=ref["raw_reference"],
            )
            new_ref.final_url = ref["final_url"]
            new_ref.resolution_status = ref["resolution_status"]
            new_ref.http_status = ref["http_status"]
            new_ref.resolution_error_type = ref["resolution_error_type"]
            new_ref.resolution_error_detail = ref["resolution_error_detail"]

        error_message = f"[DOCUMENT_PROCESSING_FAILED] Document processing failed: {exc}"
        create_processing_log(
            session,
            level="ERROR",
            step_name="document_processing",
            message=error_message,
            batch_run_id=batch_run_id,
            document_id=document.id,
        )
        retention = apply_source_retention_for_failure(fingerprint.path, settings)
        if ingestion.force_reprocess_requested and previous_state["processing_status"] == "processed":
            document.retention_mode = settings.file_retention_mode
            document.last_ingestion_used_cached_result = False
            document.source_file_present = retention.source_file_present
            document.retry_requires_reupload = retention.retry_requires_reupload
            document.last_source_path = retention.retained_path
            document.source_deleted_at = None if retention.source_file_present else datetime.now(UTC)
        else:
            mark_document_failed(
                session,
                document,
                error_message,
                retention.retained_path,
                error_type=UNKNOWN_ERROR,
                error_detail=str(exc),
                source_file_present=retention.source_file_present,
                retry_requires_reupload=retention.retry_requires_reupload,
            )
            document.retention_mode = settings.file_retention_mode
            document.last_ingestion_used_cached_result = False
        mark_document_ingestion_status(
            session,
            ingestion,
            ingestion_status="failed",
            used_cached_result=False,
            source_file_path=retention.retained_path,
            source_file_present=retention.source_file_present,
            retry_source_available=retention.retry_source_available,
            cleanup_due_at=retention.cleanup_due_at,
            error_type=UNKNOWN_ERROR,
            error_detail=str(exc),
        )
        reconcile_document_source_flags(session, document.id)
        raise


def _reuse_cached_document(
    session: Session,
    *,
    batch_run_id: int,
    document: Document,
    ingestion: DocumentIngestion,
    fingerprint: FileFingerprint,
    settings: Settings,
) -> None:
    retention = apply_source_retention_for_success(
        fingerprint.path,
        settings,
        reused_cached=True,
        content_hash=fingerprint.content_hash,
    )
    document.last_ingestion_used_cached_result = True
    document.retention_mode = settings.file_retention_mode
    mark_document_ingestion_status(
        session,
        ingestion,
        ingestion_status="reused_cached",
        used_cached_result=True,
        source_file_path=retention.retained_path,
        source_file_present=retention.source_file_present,
        retry_source_available=retention.retry_source_available,
        cleanup_due_at=retention.cleanup_due_at,
    )
    reconcile_document_source_flags(session, document.id)
    create_processing_log(
        session,
        level="INFO",
        step_name="duplicate_skip",
        message=(
            f"[{DUPLICATE_CONTENT}] Duplicate reused for content hash "
            f"{fingerprint.content_hash} extraction_version={document.extraction_version}"
        ),
        batch_run_id=batch_run_id,
        document_id=document.id,
    )


def run_batch_registration(
    settings: Settings,
    database_engine,
    *,
    triggered_by: str,
    force_reprocess: bool | None = None,
) -> BatchProcessSummary:
    input_dir = get_inbox_path(settings)
    ensure_directory(settings.processed_path)
    ensure_directory(settings.error_path)
    ensure_directory(settings.failed_retained_path)

    force_reprocess = settings.default_force_reprocess if force_reprocess is None else force_reprocess
    pdf_files = discover_pdf_files(input_dir)
    logger.info(
        "Batch start triggered_by=%s inbox_path=%s files_seen=%s force_reprocess=%s",
        triggered_by,
        input_dir,
        len(pdf_files),
        force_reprocess,
    )

    session_factory = get_session_factory(database_engine)
    duplicate_files_skipped = 0
    total_files_processed = 0
    failed_files = 0

    with session_factory() as session:
        batch_run = create_batch_run(session, triggered_by=triggered_by)
        session.commit()

        for file_path in pdf_files:
            fingerprint = build_file_fingerprint(file_path)
            existing_document = find_document_by_hash(session, fingerprint.content_hash)
            document = create_or_get_document_row(
                session,
                original_file_name=fingerprint.original_file_name,
                content_hash=fingerprint.content_hash,
                file_size_bytes=fingerprint.file_size_bytes,
                extraction_version=settings.extraction_version,
                retention_mode=settings.file_retention_mode,
            )
            ingestion = create_document_ingestion(
                session,
                document_id=document.id,
                batch_run_id=batch_run.id,
                uploaded_file_name=fingerprint.original_file_name,
                retention_mode_used=settings.file_retention_mode,
                force_reprocess_requested=force_reprocess,
                source_file_path=str(file_path),
            )

            if _can_reuse_cached_result(existing_document, settings=settings, force_reprocess=force_reprocess):
                duplicate_files_skipped += 1
                _reuse_cached_document(
                    session,
                    batch_run_id=batch_run.id,
                    document=document,
                    ingestion=ingestion,
                    fingerprint=fingerprint,
                    settings=settings,
                )
                session.commit()
                continue

            try:
                _process_document_from_source(
                    session,
                    batch_run_id=batch_run.id,
                    document=document,
                    ingestion=ingestion,
                    fingerprint=fingerprint,
                    settings=settings,
                )
                total_files_processed += 1
                if force_reprocess and existing_document is not None:
                    ingestion.ingestion_status = "forced_reprocess"
                session.commit()
            except Exception:
                failed_files += 1
                session.commit()

        status = "completed_with_errors" if failed_files else "completed"
        total_references_found = count_batch_references(session, batch_run.id)
        finalize_batch_run(
            session,
            batch_run,
            total_files_seen=len(pdf_files),
            total_files_processed=total_files_processed,
            duplicate_files_skipped=duplicate_files_skipped,
            failed_files=failed_files,
            total_references_found=total_references_found,
            status=status,
        )
        session.commit()

        return BatchProcessSummary(
            batch_run_id=batch_run.id,
            total_files_seen=len(pdf_files),
            total_files_processed=total_files_processed,
            duplicate_files_skipped=duplicate_files_skipped,
            failed_files=failed_files,
            total_references_found=total_references_found,
            status=status,
        )


def process_single_document_from_retained_source(
    settings: Settings,
    database_engine,
    *,
    document: Document,
    source_path: Path,
    triggered_by: str,
    force_reprocess: bool,
) -> BatchProcessSummary:
    session_factory = get_session_factory(database_engine)
    fingerprint = build_file_fingerprint(source_path)
    with session_factory() as session:
        batch_run = create_batch_run(session, triggered_by=triggered_by)
        session.commit()
        canonical_document = session.get(Document, document.id)
        ingestion = create_document_ingestion(
            session,
            document_id=canonical_document.id,
            batch_run_id=batch_run.id,
            uploaded_file_name=fingerprint.original_file_name,
            retention_mode_used=settings.file_retention_mode,
            force_reprocess_requested=force_reprocess,
            source_file_path=str(source_path),
        )
        failed_files = 0
        total_processed = 0
        try:
            _process_document_from_source(
                session,
                batch_run_id=batch_run.id,
                document=canonical_document,
                ingestion=ingestion,
                fingerprint=fingerprint,
                settings=settings,
            )
            total_processed = 1
            if force_reprocess:
                ingestion.ingestion_status = "forced_reprocess"
            session.commit()
        except Exception:
            failed_files = 1
            session.commit()
        total_references_found = count_batch_references(session, batch_run.id)
        finalize_batch_run(
            session,
            batch_run,
            total_files_seen=1,
            total_files_processed=total_processed,
            duplicate_files_skipped=0,
            failed_files=failed_files,
            total_references_found=total_references_found,
            status="completed_with_errors" if failed_files else "completed",
        )
        session.commit()
        return BatchProcessSummary(
            batch_run_id=batch_run.id,
            total_files_seen=1,
            total_files_processed=total_processed,
            duplicate_files_skipped=0,
            failed_files=failed_files,
            total_references_found=total_references_found,
            status="completed_with_errors" if failed_files else "completed",
        )


def fetch_home_batch_summary(database_engine) -> HomeBatchSummary | None:
    session_factory = get_session_factory(database_engine)
    with session_factory() as session:
        return get_latest_home_batch_summary(session)
