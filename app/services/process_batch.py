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
from app.batch.fingerprint import FileFingerprint, build_file_fingerprint
from app.batch.pdf_validation import validate_pdf_readable
from app.batch.reference_extraction import ExtractionIssue, extract_references_from_pdf
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
    get_latest_home_batch_summary,
    mark_document_failed,
    mark_document_ingestion_status,
    mark_document_processing,
    mark_document_processed,
    set_document_processing_issue,
)
from app.batch.url_resolution import resolve_document_references
from app.config import Settings
from app.db.models import Document, DocumentIngestion, DocumentReference
from app.db.session import get_session_factory
from app.lifecycle import (
    ACTOR_RETRY_SERVICE,
    ACTOR_BATCH_PROCESSOR,
    EVENT_DOCUMENT_DUPLICATE_REUSED,
    EVENT_DOCUMENT_EXTRACTION_COMPLETED,
    EVENT_DOCUMENT_FAILED,
    EVENT_DOCUMENT_PROCESSING_STARTED,
    EVENT_DOCUMENT_QUEUED,
    EVENT_DOCUMENT_RETAINED,
    EVENT_DOCUMENT_RETRY_COMPLETED,
    EVENT_DOCUMENT_RETRY_STARTED,
    EVENT_DOCUMENT_RESOLUTION_COMPLETED,
    EVENT_DOCUMENT_UPLOADED,
    EVENT_DOCUMENT_VALIDATED,
    STATE_EXTRACTED,
    STATE_FAILED,
    STATE_PROCESSING,
    STATE_QUEUED,
    STATE_RETAINED,
    STATE_RESOLVED,
    STATE_UPLOADED,
    STATE_VALIDATED,
    document_has_lifecycle_history,
    record_lifecycle_event,
    record_non_state_event,
    transition_document_state,
)
from app.logging_config import get_logger
from app.services.retention_service import (
    apply_source_retention_for_failure,
    apply_source_retention_for_success,
    reconcile_document_source_flags,
)
from app.storage import get_storage_service


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


def _correlation_id_for(document_id: int, batch_run_id: int) -> str:
    return f"document:{document_id}:batch:{batch_run_id}"


def _operation_id_for(ingestion_id: int) -> str:
    return f"ingestion:{ingestion_id}"


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
    correlation_id: str,
    operation_id: str,
) -> None:
    try:
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_PROCESSING_STARTED,
            to_state=STATE_PROCESSING,
            actor_source=ACTOR_BATCH_PROCESSOR,
            correlation_id=correlation_id,
            operation_id=operation_id,
            batch_run_id=batch_run_id,
        )
        mark_document_processing(session, document)
        validate_pdf_readable(fingerprint.path)
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_VALIDATED,
            to_state=STATE_VALIDATED,
            actor_source=ACTOR_BATCH_PROCESSOR,
            correlation_id=correlation_id,
            operation_id=operation_id,
            batch_run_id=batch_run_id,
            metadata={"uploaded_file_name": fingerprint.original_file_name},
        )
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
        retention = apply_source_retention_for_failure(
            fingerprint.path,
            settings,
            content_hash=fingerprint.content_hash,
            mime_type=fingerprint.mime_type,
        )
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
        document.sha256 = fingerprint.content_hash
        document.mime_type = fingerprint.mime_type
        document.storage_key = retention.storage_key
        document.storage_backend = settings.storage_backend
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
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_FAILED,
            to_state=STATE_FAILED,
            actor_source=ACTOR_BATCH_PROCESSOR,
            correlation_id=correlation_id,
            operation_id=operation_id,
            batch_run_id=batch_run_id,
            metadata={"step": "pdf_validation"},
            error_type=INVALID_PDF,
            error_detail=str(exc),
        )
        if retention.source_file_present:
            transition_document_state(
                session,
                document=document,
                event_type=EVENT_DOCUMENT_RETAINED,
                to_state=STATE_RETAINED,
                actor_source=ACTOR_BATCH_PROCESSOR,
                correlation_id=correlation_id,
                operation_id=operation_id,
                batch_run_id=batch_run_id,
                metadata={"reason": "failed_source_retained"},
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
            "destination_type": ref.destination_type,
            "destination_host": ref.destination_host,
            "requires_user_action": ref.requires_user_action,
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
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_EXTRACTION_COMPLETED,
            to_state=STATE_EXTRACTED,
            actor_source=ACTOR_BATCH_PROCESSOR,
            correlation_id=correlation_id,
            operation_id=operation_id,
            batch_run_id=batch_run_id,
            metadata={"page_count": page_count, "reference_count": inserted_count},
        )
        error_type, error_detail = _select_document_issue(extraction_issues)
        if not references and error_type is None:
            error_type = UNKNOWN_ERROR
            error_detail = "No references found"
        set_document_processing_issue(session, document, error_type=error_type, error_detail=error_detail)
        document.original_file_name = fingerprint.original_file_name
        document.sha256 = fingerprint.content_hash
        document.mime_type = fingerprint.mime_type
        document.file_size_bytes = fingerprint.file_size_bytes
        document.extraction_version = settings.extraction_version
        resolve_document_references(session, document.id, settings=settings)

        retention = apply_source_retention_for_success(
            fingerprint.path,
            settings,
            reused_cached=False,
            content_hash=fingerprint.content_hash,
            mime_type=fingerprint.mime_type,
        )
        mark_document_processed(
            session,
            document,
            retention.retained_path,
            extraction_version=settings.extraction_version,
            source_file_present=retention.source_file_present,
            retry_requires_reupload=retention.retry_requires_reupload,
            processing_error_type=error_type,
            processing_error_detail=error_detail,
        )
        document.storage_key = retention.storage_key
        document.storage_backend = settings.storage_backend
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
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_RESOLUTION_COMPLETED,
            to_state=STATE_RESOLVED,
            actor_source=ACTOR_BATCH_PROCESSOR,
            correlation_id=correlation_id,
            operation_id=operation_id,
            batch_run_id=batch_run_id,
            metadata={"reference_count": inserted_count, "used_cached_result": False},
            error_type=error_type,
            error_detail=error_detail,
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
            new_ref.destination_type = ref["destination_type"]
            new_ref.destination_host = ref["destination_host"]
            new_ref.requires_user_action = ref["requires_user_action"]
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
        retention = apply_source_retention_for_failure(
            fingerprint.path,
            settings,
            content_hash=fingerprint.content_hash,
            mime_type=fingerprint.mime_type,
        )
        if ingestion.force_reprocess_requested and previous_state["processing_status"] == "processed":
            document.retention_mode = settings.file_retention_mode
            document.last_ingestion_used_cached_result = False
            document.source_file_present = retention.source_file_present
            document.retry_requires_reupload = retention.retry_requires_reupload
            document.last_source_path = retention.retained_path
            document.source_deleted_at = None if retention.source_file_present else datetime.now(UTC)
            document.lifecycle_state = "retained" if retention.source_file_present else "failed"
            document.storage_key = retention.storage_key or document.storage_key
            document.storage_backend = settings.storage_backend
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
            document.sha256 = fingerprint.content_hash
            document.mime_type = fingerprint.mime_type
            document.storage_key = retention.storage_key
            document.storage_backend = settings.storage_backend
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
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_FAILED,
            to_state=STATE_FAILED,
            actor_source=ACTOR_BATCH_PROCESSOR,
            correlation_id=correlation_id,
            operation_id=operation_id,
            batch_run_id=batch_run_id,
            metadata={"step": "document_processing"},
            error_type=UNKNOWN_ERROR,
            error_detail=str(exc),
        )
        if retention.source_file_present:
            transition_document_state(
                session,
                document=document,
                event_type=EVENT_DOCUMENT_RETAINED,
                to_state=STATE_RETAINED,
                actor_source=ACTOR_BATCH_PROCESSOR,
                correlation_id=correlation_id,
                operation_id=operation_id,
                batch_run_id=batch_run_id,
                metadata={"reason": "failed_source_retained"},
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
        mime_type=fingerprint.mime_type,
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
    storage = get_storage_service(settings)
    runtime_dirs = storage.ensure_runtime_directories()
    input_dir = runtime_dirs["inbox"]

    force_reprocess = settings.default_force_reprocess if force_reprocess is None else force_reprocess
    pdf_files = storage.list_inbox_pdf_files()
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
            reusable_cached_document = (
                existing_document
                if _can_reuse_cached_result(
                    existing_document,
                    settings=settings,
                    force_reprocess=force_reprocess,
                )
                else None
            )
            document = reusable_cached_document or existing_document
            is_new_document = document is None
            if document is None:
                document = create_or_get_document_row(
                    session,
                    original_file_name=fingerprint.original_file_name,
                    content_hash=fingerprint.content_hash,
                    file_size_bytes=fingerprint.file_size_bytes,
                    mime_type=fingerprint.mime_type,
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
            correlation_id = _correlation_id_for(document.id, batch_run.id)
            operation_id = _operation_id_for(ingestion.id)

            if is_new_document and not document_has_lifecycle_history(session, document.id):
                record_lifecycle_event(
                    session,
                    document_id=document.id,
                    event_type=EVENT_DOCUMENT_UPLOADED,
                    from_state=None,
                    to_state=STATE_UPLOADED,
                    actor_source=ACTOR_BATCH_PROCESSOR,
                    correlation_id=correlation_id,
                    operation_id=operation_id,
                    batch_run_id=batch_run.id,
                    metadata={"uploaded_file_name": fingerprint.original_file_name},
                )

            if reusable_cached_document is not None:
                duplicate_files_skipped += 1
                record_non_state_event(
                    session,
                    document=document,
                    event_type=EVENT_DOCUMENT_DUPLICATE_REUSED,
                    actor_source=ACTOR_BATCH_PROCESSOR,
                    correlation_id=correlation_id,
                    operation_id=operation_id,
                    batch_run_id=batch_run.id,
                    metadata={"uploaded_file_name": fingerprint.original_file_name},
                )
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
                transition_document_state(
                    session,
                    document=document,
                    event_type=EVENT_DOCUMENT_QUEUED,
                    to_state=STATE_QUEUED,
                    actor_source=ACTOR_BATCH_PROCESSOR,
                    correlation_id=correlation_id,
                    operation_id=operation_id,
                    batch_run_id=batch_run.id,
                    metadata={"uploaded_file_name": fingerprint.original_file_name},
                )
                _process_document_from_source(
                    session,
                    batch_run_id=batch_run.id,
                    document=document,
                    ingestion=ingestion,
                    fingerprint=fingerprint,
                    settings=settings,
                    correlation_id=correlation_id,
                    operation_id=operation_id,
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
    correlation_id: str | None = None,
) -> BatchProcessSummary:
    session_factory = get_session_factory(database_engine)
    storage = get_storage_service(settings)
    temp_source_path = storage.create_temp_working_copy(source_path)
    fingerprint = build_file_fingerprint(temp_source_path)
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
        lifecycle_correlation_id = correlation_id or _correlation_id_for(canonical_document.id, batch_run.id)
        operation_id = _operation_id_for(ingestion.id)
        failed_files = 0
        total_processed = 0
        try:
            record_non_state_event(
                session,
                document=canonical_document,
                event_type=EVENT_DOCUMENT_RETRY_STARTED,
                actor_source=ACTOR_RETRY_SERVICE,
                correlation_id=lifecycle_correlation_id,
                operation_id=operation_id,
                batch_run_id=batch_run.id,
                metadata={"triggered_by": triggered_by, "force_reprocess": force_reprocess},
            )
            transition_document_state(
                session,
                document=canonical_document,
                event_type=EVENT_DOCUMENT_QUEUED,
                to_state=STATE_QUEUED,
                actor_source=ACTOR_RETRY_SERVICE,
                correlation_id=lifecycle_correlation_id,
                operation_id=operation_id,
                batch_run_id=batch_run.id,
                metadata={"triggered_by": triggered_by, "force_reprocess": force_reprocess},
            )
            _process_document_from_source(
                session,
                batch_run_id=batch_run.id,
                document=canonical_document,
                ingestion=ingestion,
                fingerprint=fingerprint,
                settings=settings,
                correlation_id=lifecycle_correlation_id,
                operation_id=operation_id,
            )
            total_processed = 1
            if force_reprocess:
                ingestion.ingestion_status = "forced_reprocess"
            if source_path.exists() and not canonical_document.source_file_present and canonical_document.storage_key:
                storage.delete_document(canonical_document.storage_key)
            record_non_state_event(
                session,
                document=canonical_document,
                event_type=EVENT_DOCUMENT_RETRY_COMPLETED,
                actor_source=ACTOR_RETRY_SERVICE,
                correlation_id=lifecycle_correlation_id,
                operation_id=operation_id,
                batch_run_id=batch_run.id,
                metadata={"triggered_by": triggered_by, "force_reprocess": force_reprocess, "success": True},
            )
            session.commit()
        except Exception:
            failed_files = 1
            storage.delete_temp_file(temp_source_path)
            record_non_state_event(
                session,
                document=canonical_document,
                event_type=EVENT_DOCUMENT_RETRY_COMPLETED,
                actor_source=ACTOR_RETRY_SERVICE,
                correlation_id=lifecycle_correlation_id,
                operation_id=operation_id,
                batch_run_id=batch_run.id,
                metadata={"triggered_by": triggered_by, "force_reprocess": force_reprocess, "success": False},
            )
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
