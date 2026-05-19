from sqlalchemy import text

from app.db.session import get_session_factory
from app.traversal.planner import plan_document_traversal


def _seed_traversal_document(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (
                    id, batch_run_id, original_file_name, content_hash, file_size_bytes,
                    processing_status, lifecycle_state, extraction_version, retention_mode,
                    source_file_present, retry_requires_reupload, last_ingestion_used_cached_result
                )
                VALUES (
                    301, NULL, 'traversal-parent.pdf', 'hash-traversal-parent', 100,
                    'processed', 'resolved', 1, 'retain_failed_only',
                    0, 1, 0
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_references (
                    id, document_id, page_number, source_type, reference_class,
                    raw_reference, final_url, resolution_status, http_status,
                    resolution_error_type, resolution_error_detail
                )
                VALUES
                    (401, 301, 1, 'qr', 'url', 'https://short.example/raw', 'https://example.go.th/child.pdf', 'resolved', 200, NULL, NULL),
                    (402, 301, 2, 'text', 'url', 'https://example.go.th/page.html', 'https://example.go.th/page.html', 'resolved', 200, NULL, NULL),
                    (403, 301, 3, 'text', 'url', 'http://127.0.0.1/secret.pdf', 'http://127.0.0.1/secret.pdf', 'resolved', 200, NULL, NULL)
                """
            )
        )


def _count_rows(engine, table_name: str) -> int:
    with engine.begin() as connection:
        return connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()


def test_planner_creates_rows_without_downloader_or_child_documents(client):
    _seed_traversal_document(client.app.state.postgres_engine)
    session_factory = get_session_factory(client.app.state.postgres_engine)

    with session_factory() as session:
        summary = plan_document_traversal(
            session,
            document_id=301,
            settings=client.app.state.settings,
        )
        session.commit()

    assert summary is not None
    assert summary.created == 3
    assert _count_rows(client.app.state.postgres_engine, "documents") == 1

    with client.app.state.postgres_engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT source_reference_id, target_type, traversal_status, policy_decision, policy_reason,
                       child_document_id
                FROM reference_traversals
                ORDER BY source_reference_id
                """
            )
        ).mappings().all()

    assert rows[0]["target_type"] == "pdf_url"
    assert rows[0]["traversal_status"] == "SKIPPED_BY_POLICY"
    assert rows[0]["policy_reason"] == "traversal_disabled"
    assert rows[0]["child_document_id"] is None
    assert rows[1]["target_type"] == "html_page"
    assert rows[1]["traversal_status"] == "UNSUPPORTED"
    assert rows[2]["policy_reason"] == "loopback_blocked"


def test_planner_prevents_duplicate_rows(client):
    _seed_traversal_document(client.app.state.postgres_engine)
    session_factory = get_session_factory(client.app.state.postgres_engine)

    with session_factory() as session:
        first = plan_document_traversal(session, document_id=301, settings=client.app.state.settings)
        second = plan_document_traversal(session, document_id=301, settings=client.app.state.settings)
        session.commit()

    assert first is not None
    assert second is not None
    assert first.created == 3
    assert second.created == 0
    assert second.unchanged == 3
    assert _count_rows(client.app.state.postgres_engine, "reference_traversals") == 3


def test_planner_can_emit_non_state_lifecycle_events(client):
    _seed_traversal_document(client.app.state.postgres_engine)
    session_factory = get_session_factory(client.app.state.postgres_engine)

    with session_factory() as session:
        plan_document_traversal(
            session,
            document_id=301,
            settings=client.app.state.settings,
            emit_lifecycle_events=True,
        )
        session.commit()

    with client.app.state.postgres_engine.begin() as connection:
        event_types = connection.execute(
            text(
                """
                SELECT event_type
                FROM document_lifecycle_events
                WHERE document_id = 301
                ORDER BY id
                """
            )
        ).scalars().all()

    assert event_types == [
        "TRAVERSAL_SKIPPED",
        "TRAVERSAL_SKIPPED",
        "TRAVERSAL_SKIPPED",
    ]


def test_traversal_api_and_ops_summary(client):
    _seed_traversal_document(client.app.state.postgres_engine)

    document_response = client.get("/documents/301/traversal")
    ops_response = client.get("/ops/traversal")
    page_response = client.get("/documents/301/traversal/view")

    assert document_response.status_code == 200
    assert ops_response.status_code == 200
    assert page_response.status_code == 200

    document_payload = document_response.json()
    ops_payload = ops_response.json()

    assert document_payload["document_id"] == 301
    assert document_payload["planning_summary"]["created"] == 3
    assert len(document_payload["traversals"]) == 3
    assert ops_payload["total"] == 3
    assert ops_payload["by_status"]["SKIPPED_BY_POLICY"] == 2
    assert ops_payload["by_status"]["UNSUPPORTED"] == 1
    assert "แผน Traversal" in page_response.text
