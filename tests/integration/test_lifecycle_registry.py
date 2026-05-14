import importlib

import fitz
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.config import get_settings
from app.db.session import get_session_factory
from app.services.process_batch import run_batch_registration


def _create_valid_pdf(path, text_content: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text_content)
    document.save(path)
    document.close()


def _fetch_event_types(engine, document_id: int) -> list[str]:
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT event_type
                FROM document_lifecycle_events
                WHERE document_id = :document_id
                ORDER BY occurred_at, id
                """
            ),
            {"document_id": document_id},
        ).scalars()
        return list(rows)


def _seed_failed_document(engine, *, document_id: int, source_path):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (
                    id, batch_run_id, original_file_name, content_hash, file_size_bytes,
                    processing_status, processing_error, processing_error_type, processing_error_detail,
                    processed_at, lifecycle_state, moved_to_path, extraction_version, retention_mode,
                    source_file_present, last_source_path, retry_requires_reupload, last_ingestion_used_cached_result
                )
                VALUES (
                    :document_id, NULL, 'retry-source.pdf', :content_hash, 100,
                    'failed', 'bad pdf', 'INVALID_PDF', 'broken file',
                    '2026-04-24 10:00:00', 'failed', :moved_to_path, 1, 'retain_failed_only',
                    :source_file_present, :last_source_path, :retry_requires_reupload, 0
                )
                """
            ),
            {
                "document_id": document_id,
                "content_hash": f"hash-{document_id}",
                "moved_to_path": str(source_path) if source_path else None,
                "last_source_path": str(source_path) if source_path else None,
                "source_file_present": 1 if source_path else 0,
                "retry_requires_reupload": 0 if source_path else 1,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO document_ingestions (
                    document_id, batch_run_id, uploaded_file_name, uploaded_at, ingestion_status,
                    used_cached_result, force_reprocess_requested, retention_mode_used, source_file_path,
                    source_file_present, cleanup_due_at, retry_source_available, error_type, error_detail
                )
                VALUES (
                    :document_id, NULL, 'retry-source.pdf', '2026-04-24 10:00:00', 'failed',
                    0, 0, 'retain_failed_only', :source_file_path,
                    :source_file_present, '2026-04-30 10:00:00', :retry_source_available, 'INVALID_PDF', 'broken file'
                )
                """
            ),
            {
                "document_id": document_id,
                "source_file_path": str(source_path) if source_path else None,
                "source_file_present": 1 if source_path else 0,
                "retry_source_available": 1 if source_path else 0,
            },
        )


def test_lifecycle_migration_creates_event_table(monkeypatch, tmp_path):
    database_path = tmp_path / "migration.sqlite3"
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    import app.config as config_module

    importlib.reload(config_module)

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    import sqlite3

    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
        index_names = {
            row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
        }

    assert "document_lifecycle_events" in table_names
    assert "ix_document_lifecycle_events_document_occurred" in index_names
    assert "ix_document_lifecycle_events_event_occurred" in index_names


def test_batch_flow_emits_lifecycle_history(client):
    input_dir = client.app.state.settings.input_path
    _create_valid_pdf(input_dir / "lifecycle-success.pdf", "Reference https://example.com/ok")

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="lifecycle-test",
    )

    with client.app.state.postgres_engine.begin() as connection:
        document_row = connection.execute(
            text("SELECT id, lifecycle_state FROM documents ORDER BY id DESC LIMIT 1")
        ).mappings().one()

    event_types = _fetch_event_types(client.app.state.postgres_engine, document_row["id"])

    assert summary.total_files_processed == 1
    assert document_row["lifecycle_state"] == "resolved"
    assert event_types == [
        "DOCUMENT_UPLOADED",
        "DOCUMENT_QUEUED",
        "DOCUMENT_PROCESSING_STARTED",
        "DOCUMENT_VALIDATED",
        "DOCUMENT_EXTRACTION_COMPLETED",
        "DOCUMENT_RESOLUTION_COMPLETED",
    ]


def test_failed_batch_flow_emits_failure_history(client):
    source_path = client.app.state.settings.input_path / "broken.pdf"
    source_path.write_bytes(b"not a pdf")

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="lifecycle-failure-test",
    )

    with client.app.state.postgres_engine.begin() as connection:
        document_row = connection.execute(
            text("SELECT id, lifecycle_state FROM documents ORDER BY id DESC LIMIT 1")
        ).mappings().one()

    event_types = _fetch_event_types(client.app.state.postgres_engine, document_row["id"])

    assert document_row["lifecycle_state"] == "retained"
    assert event_types == [
        "DOCUMENT_UPLOADED",
        "DOCUMENT_QUEUED",
        "DOCUMENT_PROCESSING_STARTED",
        "DOCUMENT_FAILED",
        "DOCUMENT_RETAINED",
    ]


def test_lifecycle_route_returns_ordered_json(client):
    input_dir = client.app.state.settings.input_path
    _create_valid_pdf(input_dir / "timeline.pdf", "Reference https://example.com/timeline")
    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="timeline-test",
    )

    with client.app.state.postgres_engine.begin() as connection:
        document_id = connection.execute(text("SELECT id FROM documents ORDER BY id DESC LIMIT 1")).scalar_one()

    response = client.get(f"/documents/{document_id}/lifecycle")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document_id
    assert payload["current_state"] == "resolved"
    assert payload["consistency"]["status"] == "PASS"
    assert [event["event_type"] for event in payload["timeline"]] == [
        "DOCUMENT_UPLOADED",
        "DOCUMENT_QUEUED",
        "DOCUMENT_PROCESSING_STARTED",
        "DOCUMENT_VALIDATED",
        "DOCUMENT_EXTRACTION_COMPLETED",
        "DOCUMENT_RESOLUTION_COMPLETED",
    ]
    assert payload["groups"][0]["title"] == "Processing chain"


def test_lifecycle_consistency_route_returns_structured_status(client):
    input_dir = client.app.state.settings.input_path
    _create_valid_pdf(input_dir / "consistency.pdf", "Reference https://example.com/consistency")
    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="consistency-route-test",
    )

    with client.app.state.postgres_engine.begin() as connection:
        document_id = connection.execute(text("SELECT id FROM documents ORDER BY id DESC LIMIT 1")).scalar_one()

    response = client.get(f"/documents/{document_id}/lifecycle/consistency")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == document_id
    assert payload["consistency"]["status"] == "PASS"


def test_retry_flow_emits_retry_lifecycle_events(client):
    source_path = client.app.state.settings.failed_retained_path / "retry-source.pdf"
    source_path.write_bytes(b"failed pdf bytes")
    _seed_failed_document(client.app.state.postgres_engine, document_id=901, source_path=source_path)

    session_factory = get_session_factory(client.app.state.database_engine)
    with session_factory() as session:
        from app.lifecycle import (
            ACTOR_BATCH_PROCESSOR,
            EVENT_DOCUMENT_FAILED,
            STATE_FAILED,
            record_lifecycle_event,
        )

        record_lifecycle_event(
            session,
            document_id=901,
            event_type=EVENT_DOCUMENT_FAILED,
            from_state="processing",
            to_state=STATE_FAILED,
            actor_source=ACTOR_BATCH_PROCESSOR,
            metadata={"seeded": True},
        )
        session.commit()

    response = client.post("/documents/901/retry", follow_redirects=False)

    assert response.status_code == 303
    event_types = _fetch_event_types(client.app.state.postgres_engine, 901)
    assert "DOCUMENT_RETRY_REQUESTED" in event_types
    assert "DOCUMENT_RETRY_STARTED" in event_types
    assert "DOCUMENT_RETRY_COMPLETED" in event_types
