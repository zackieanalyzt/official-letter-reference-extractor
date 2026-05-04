import inspect
from dataclasses import dataclass

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
from app.batch.file_ops import ensure_directory, move_file_to_directory
from app.batch.fingerprint import FileFingerprint, build_file_fingerprint
from app.batch.pdf_validation import validate_pdf_readable
from app.batch.reference_extraction import ExtractionIssue, extract_references_from_pdf
from app.batch.scanner import discover_pdf_files
from app.batch.url_resolution import resolve_document_references
from app.batch.service import (
    HomeBatchSummary,
    count_batch_references,
    create_batch_run,
    create_document_row,
    create_document_reference,
    create_processing_log,
    finalize_batch_run,
    find_processed_document_by_hash,
    get_latest_home_batch_summary,
    mark_document_failed,
    mark_document_processed,
    set_document_processing_issue,
)
from app.config import Settings
from app.db.session import get_session_factory
from app.logging_config import get_logger
from app.services.inbox_paths import get_inbox_path


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


def process_registered_document(
    session: Session,
    *,
    batch_run_id: int,
    fingerprint: FileFingerprint,
    processed_dir,
    error_dir,
    settings: Settings,
) -> None:
    document = create_document_row(
        session,
        batch_run_id=batch_run_id,
        original_file_name=fingerprint.original_file_name,
        content_hash=fingerprint.content_hash,
        file_size_bytes=fingerprint.file_size_bytes,
    )

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
        moved_to_error = move_file_to_directory(
            fingerprint.path,
            error_dir,
            fingerprint.content_hash,
        )
        mark_document_failed(
            session,
            document,
            error_message,
            str(moved_to_error),
            error_type=INVALID_PDF,
            error_detail=str(exc),
        )
        create_processing_log(
            session,
            level="INFO",
            step_name="file_move",
            message=f"File moved to error: {moved_to_error}",
            batch_run_id=batch_run_id,
            document_id=document.id,
        )
        logger.info("File moved to error file=%s destination=%s", fingerprint.path, moved_to_error)
        raise

    try:
        references: list = []
        extraction_issues: list = []
        persisted_reference_keys: set[tuple[int, str, str]] = set()
        try:
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
        except Exception as exc:
            logger.exception("Reference extraction failed file=%s", fingerprint.path)
            create_processing_log(
                session,
                level="ERROR",
                step_name="reference_extraction",
                message=f"[REFERENCE_EXTRACTION_FAILED] Reference extraction failed: {exc}",
                batch_run_id=batch_run_id,
                document_id=document.id,
            )
            references = []
            extraction_issues = []

        for issue in extraction_issues:
            if issue.page_number is None:
                message = f"[{issue.error_type}] {issue.message}"
            else:
                message = f"[{issue.error_type}] {issue.message} page={issue.page_number}"
            create_processing_log(
                session,
                level="WARNING",
                step_name=issue.step_name,
                message=message,
                batch_run_id=batch_run_id,
                document_id=document.id,
            )

        for reference in references:
            reference_key = (
                reference.page_number,
                reference.source_type,
                reference.raw_reference,
            )
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
        logger.info(
            "[DB_INSERT] file=%s document_id=%s inserted=%s",
            fingerprint.path,
            document.id,
            len(persisted_reference_keys),
        )
        error_type, error_detail = _select_document_issue(extraction_issues)
        if not references and error_type is None:
            error_type = UNKNOWN_ERROR
            error_detail = "No references found"
        set_document_processing_issue(
            session,
            document,
            error_type=error_type,
            error_detail=error_detail,
        )
        try:
            resolve_document_references(session, document.id, settings=settings)
        except Exception as exc:
            logger.exception("URL resolution failed document_id=%s file=%s", document.id, fingerprint.path)
            create_processing_log(
                session,
                level="ERROR",
                step_name="url_resolution",
                message=f"[URL_RESOLUTION_FAILED] URL resolution failed: {exc}",
                batch_run_id=batch_run_id,
                document_id=document.id,
            )

        moved_path = move_file_to_directory(
            fingerprint.path,
            processed_dir,
            fingerprint.content_hash,
        )
        mark_document_processed(session, document, str(moved_path))
        create_processing_log(
            session,
            level="INFO",
            step_name="file_move",
            message=f"File moved to processed: {moved_path}",
            batch_run_id=batch_run_id,
            document_id=document.id,
        )
        logger.info("File moved to processed file=%s destination=%s", fingerprint.path, moved_path)
    except Exception as exc:
        error_message = f"[DOCUMENT_PROCESSING_FAILED] Document processing failed: {exc}"
        logger.exception("Document processing failed file=%s", fingerprint.path)
        create_processing_log(
            session,
            level="ERROR",
            step_name="document_processing",
            message=error_message,
            batch_run_id=batch_run_id,
            document_id=document.id,
        )
        moved_to_error = move_file_to_directory(
            fingerprint.path,
            error_dir,
            fingerprint.content_hash,
        )
        mark_document_failed(
            session,
            document,
            error_message,
            str(moved_to_error),
            error_type=UNKNOWN_ERROR,
            error_detail=str(exc),
        )
        create_processing_log(
            session,
            level="INFO",
            step_name="file_move",
            message=f"File moved to error: {moved_to_error}",
            batch_run_id=batch_run_id,
            document_id=document.id,
        )
        logger.info("File moved to error file=%s destination=%s", fingerprint.path, moved_to_error)
        raise


def run_batch_registration(settings: Settings, database_engine, *, triggered_by: str) -> BatchProcessSummary:
    input_dir = get_inbox_path(settings)
    processed_dir = ensure_directory(settings.processed_path)
    error_dir = ensure_directory(settings.error_path)

    logger.info("Resolved INPUT_DIR=%s exists=%s", input_dir, input_dir.exists())
    logger.info("Resolved PROCESSED_DIR=%s exists=%s", processed_dir, processed_dir.exists())
    logger.info("Resolved ERROR_DIR=%s exists=%s", error_dir, error_dir.exists())

    pdf_files = discover_pdf_files(input_dir)
    logger.info(
        "Batch start triggered_by=%s inbox_path=%s files_seen=%s files=%s",
        triggered_by,
        input_dir,
        len(pdf_files),
        [str(path) for path in pdf_files],
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
            duplicate_document = find_processed_document_by_hash(session, fingerprint.content_hash)
            if duplicate_document:
                duplicate_files_skipped += 1
                try:
                    moved_path = move_file_to_directory(file_path, processed_dir, fingerprint.content_hash)
                    create_processing_log(
                        session,
                        level="INFO",
                        step_name="duplicate_skip",
                        message=(
                            f"[{DUPLICATE_CONTENT}] Duplicate skipped for content hash "
                            f"{fingerprint.content_hash}; moved to processed: {moved_path}"
                        ),
                        batch_run_id=batch_run.id,
                    )
                    session.commit()
                    logger.info(
                        "File skipped as duplicate file=%s existing_document_id=%s moved_to=%s",
                        file_path,
                        duplicate_document.id,
                        moved_path,
                    )
                except Exception:
                    failed_files += 1
                    logger.exception("Duplicate file move failed file=%s", file_path)
                    moved_to_error = move_file_to_directory(file_path, error_dir, fingerprint.content_hash)
                    create_processing_log(
                        session,
                        level="ERROR",
                        step_name="duplicate_skip",
                        message=(
                            "[DUPLICATE_MOVE_FAILED] Duplicate skipped but move to processed failed; "
                            f"moved to error: {moved_to_error}"
                        ),
                        batch_run_id=batch_run.id,
                    )
                    session.commit()
                    logger.info("File moved to error file=%s destination=%s", file_path, moved_to_error)
                continue

            try:
                process_registered_document(
                    # reference extraction stays synchronous inside the existing per-file flow
                    session,
                    batch_run_id=batch_run.id,
                    fingerprint=fingerprint,
                    processed_dir=processed_dir,
                    error_dir=error_dir,
                    settings=settings,
                )
                session.commit()
                total_files_processed += 1
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

        logger.info(
            "Batch finish batch_run_id=%s status=%s processed=%s skipped=%s failed=%s",
            batch_run.id,
            status,
            total_files_processed,
            duplicate_files_skipped,
            failed_files,
        )

        return BatchProcessSummary(
            batch_run_id=batch_run.id,
            total_files_seen=len(pdf_files),
            total_files_processed=total_files_processed,
            duplicate_files_skipped=duplicate_files_skipped,
            failed_files=failed_files,
            total_references_found=total_references_found,
            status=status,
        )


def fetch_home_batch_summary(database_engine) -> HomeBatchSummary | None:
    session_factory = get_session_factory(database_engine)
    with session_factory() as session:
        return get_latest_home_batch_summary(session)
