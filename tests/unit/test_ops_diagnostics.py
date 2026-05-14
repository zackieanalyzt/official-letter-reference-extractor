from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ops.diagnostics import build_lifecycle_consistency_summary


def test_lifecycle_consistency_summary_aggregates_severities(client):
    with Session(client.app.state.database_engine) as session:
        session.execute(
            text(
                """
                INSERT INTO documents (
                    id, batch_run_id, original_file_name, content_hash, file_size_bytes,
                    processing_status, lifecycle_state, extraction_version, retention_mode,
                    source_file_present, retry_requires_reupload, last_ingestion_used_cached_result
                )
                VALUES
                    (1, NULL, 'pass.pdf', 'hash-pass', 100, 'processed', 'resolved', 1, 'retain_failed_only', 0, 1, 0),
                    (2, NULL, 'warning.pdf', 'hash-warning', 100, 'processed', 'uploaded', 1, 'retain_failed_only', 0, 1, 0),
                    (3, NULL, 'error.pdf', 'hash-error', 100, 'failed', 'retained', 1, 'retain_failed_only', 0, 1, 0),
                    (4, NULL, 'critical.pdf', 'hash-critical', 100, 'failed', 'cleaned', 1, 'retain_failed_only', 1, 0, 0)
                """
            )
        )
        session.execute(
            text(
                """
                INSERT INTO document_lifecycle_events (
                    id, document_id, event_type, from_state, to_state, occurred_at,
                    actor_source, correlation_id, operation_id, batch_run_id, metadata_json,
                    error_type, error_detail
                )
                VALUES
                    (10, 1, 'DOCUMENT_UPLOADED', NULL, 'uploaded', '2026-05-14 10:00:00', 'batch_processor', 'doc:1', 'op:1', NULL, '{}', NULL, NULL),
                    (11, 1, 'DOCUMENT_QUEUED', 'uploaded', 'queued', '2026-05-14 10:01:00', 'batch_processor', 'doc:1', 'op:2', NULL, '{}', NULL, NULL),
                    (12, 1, 'DOCUMENT_PROCESSING_STARTED', 'queued', 'processing', '2026-05-14 10:02:00', 'batch_processor', 'doc:1', 'op:3', NULL, '{}', NULL, NULL),
                    (13, 1, 'DOCUMENT_VALIDATED', 'processing', 'validated', '2026-05-14 10:03:00', 'batch_processor', 'doc:1', 'op:4', NULL, '{}', NULL, NULL),
                    (14, 1, 'DOCUMENT_EXTRACTION_COMPLETED', 'validated', 'extracted', '2026-05-14 10:04:00', 'batch_processor', 'doc:1', 'op:5', NULL, '{}', NULL, NULL),
                    (15, 1, 'DOCUMENT_RESOLUTION_COMPLETED', 'extracted', 'resolved', '2026-05-14 10:05:00', 'batch_processor', 'doc:1', 'op:6', NULL, '{}', NULL, NULL),
                    (16, 3, 'DOCUMENT_RETAINED', 'failed', 'retained', '2026-05-14 10:06:00', 'retention_service', 'doc:3', 'op:7', NULL, '{}', NULL, NULL),
                    (17, 4, 'DOCUMENT_CLEANED', 'retained', 'cleaned', '2026-05-14 10:07:00', 'retention_service', 'doc:4', 'op:8', NULL, '{}', NULL, NULL)
                """
            )
        )
        session.commit()

    with Session(client.app.state.database_engine) as session:
        summary = build_lifecycle_consistency_summary(
            session,
            settings=client.app.state.settings,
            scan_limit=10,
            sample_limit=10,
        )

    payload = summary.to_dict()
    assert payload["total_documents"] == 4
    assert payload["scanned_documents"] == 4
    assert payload["pass_count"] == 1
    assert payload["warning_count"] == 1
    assert payload["error_count"] == 1
    assert payload["critical_count"] == 1
    assert {sample["document_id"] for sample in payload["samples"]} == {2, 3, 4}
    assert {item["code"] for item in payload["top_issue_codes"]} >= {
        "history_missing",
        "retained_without_source",
        "cleaned_with_source_present",
    }
