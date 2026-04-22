from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.batch.file_ops import ensure_directory, move_file_to_directory
from app.batch.fingerprint import FileFingerprint, build_file_fingerprint
from app.batch.pdf_validation import validate_pdf_readable
from app.batch.scanner import discover_pdf_files
from app.batch.service import (
    HomeBatchSummary,
    create_batch_run,
    create_document_row,
    create_processing_log,
    finalize_batch_run,
    find_processed_document_by_hash,
    get_latest_home_batch_summary,
    mark_document_failed,
    mark_document_processed,
)
from app.config import Settings
from app.db.postgres import create_postgres_session_factory
from app.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class BatchProcessSummary:
    batch_run_id: int
    total_files_seen: int
    total_files_processed: int
    duplicate_files_skipped: int
    failed_files: int
    status: str


def process_registered_document(
    session: Session,
    *,
    batch_run_id: int,
    fingerprint: FileFingerprint,
    processed_dir,
    error_dir,
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
        error_message = f"PDF validation failed: {exc}"
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
        mark_document_failed(session, document, error_message, str(moved_to_error))
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
        error_message = f"Processed move failed: {exc}"
        logger.exception("Processed move failed file=%s", fingerprint.path)
        create_processing_log(
            session,
            level="ERROR",
            step_name="file_move",
            message=error_message,
            batch_run_id=batch_run_id,
            document_id=document.id,
        )
        moved_to_error = move_file_to_directory(
            fingerprint.path,
            error_dir,
            fingerprint.content_hash,
        )
        mark_document_failed(session, document, error_message, str(moved_to_error))
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


def run_batch_registration(settings: Settings, postgres_engine, *, triggered_by: str) -> BatchProcessSummary:
    input_dir = ensure_directory(settings.input_path)
    processed_dir = ensure_directory(settings.processed_path)
    error_dir = ensure_directory(settings.error_path)

    logger.info("Resolved INPUT_DIR=%s exists=%s", input_dir, input_dir.exists())
    logger.info("Resolved PROCESSED_DIR=%s exists=%s", processed_dir, processed_dir.exists())
    logger.info("Resolved ERROR_DIR=%s exists=%s", error_dir, error_dir.exists())

    pdf_files = discover_pdf_files(input_dir)
    logger.info(
        "Batch start triggered_by=%s files_seen=%s files=%s",
        triggered_by,
        len(pdf_files),
        [str(path) for path in pdf_files],
    )

    session_factory = create_postgres_session_factory(postgres_engine)
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
                            "Duplicate skipped for content hash "
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
                            "Duplicate skipped but move to processed failed; "
                            f"moved to error: {moved_to_error}"
                        ),
                        batch_run_id=batch_run.id,
                    )
                    session.commit()
                    logger.info("File moved to error file=%s destination=%s", file_path, moved_to_error)
                continue

            try:
                process_registered_document(
                    session,
                    batch_run_id=batch_run.id,
                    fingerprint=fingerprint,
                    processed_dir=processed_dir,
                    error_dir=error_dir,
                )
                session.commit()
                total_files_processed += 1
            except Exception:
                failed_files += 1
                session.commit()

        status = "completed_with_errors" if failed_files else "completed"
        finalize_batch_run(
            session,
            batch_run,
            total_files_seen=len(pdf_files),
            total_files_processed=total_files_processed,
            duplicate_files_skipped=duplicate_files_skipped,
            failed_files=failed_files,
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
            status=status,
        )


def fetch_home_batch_summary(postgres_engine) -> HomeBatchSummary | None:
    session_factory = create_postgres_session_factory(postgres_engine)
    with session_factory() as session:
        return get_latest_home_batch_summary(session)