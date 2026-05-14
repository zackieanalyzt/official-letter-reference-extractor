from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ops.runtime import build_runtime_snapshot, redact_database_target


def test_redact_database_target_hides_password():
    masked = redact_database_target("postgresql+psycopg://olre-user:super-secret@example.com:5432/olre")

    assert "super-secret" not in masked
    assert "***" in masked


def test_runtime_snapshot_reports_counts_without_exposing_secret(client):
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
                    (1, NULL, 'retained.pdf', 'hash-retained', 100, 'failed', 'retained', 1, 'retain_failed_only', 1, 0, 0),
                    (2, NULL, 'cleaned.pdf', 'hash-cleaned', 100, 'failed', 'cleaned', 1, 'retain_failed_only', 0, 1, 0)
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
                    (10, 1, 'DOCUMENT_RETAINED', 'failed', 'retained', '2026-05-14 10:00:00', 'retention_service', 'doc:1', 'op:1', NULL, '{}', NULL, NULL),
                    (11, 2, 'DOCUMENT_CLEANED', 'retained', 'cleaned', '2026-05-14 10:05:00', 'retention_service', 'doc:2', 'op:2', NULL, '{}', NULL, NULL)
                """
            )
        )
        session.commit()

    client.app.state.settings.database_url = "postgresql+psycopg://olre-user:super-secret@example.com:5432/olre"

    with Session(client.app.state.database_engine) as session:
        snapshot = build_runtime_snapshot(session, client.app.state.settings, client.app.state.database_engine)

    payload = snapshot.to_dict()
    assert payload["document_count"] == 2
    assert payload["lifecycle_event_count"] == 2
    assert payload["retained_document_count"] == 1
    assert payload["cleaned_document_count"] == 1
    assert payload["failed_document_count"] == 2
    assert payload["active_database_backend"] == "sqlite"
    assert "super-secret" not in payload["configured_database_target"]
    assert any(path["name"] == "storage_root" for path in payload["paths"])
