from pathlib import Path

import fitz
from sqlalchemy import text

from app.services.process_batch import run_batch_registration


def create_valid_pdf(path: Path, text_content: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text_content)
    document.save(path)
    document.close()


def fetch_one(engine, query: str):
    with engine.connect() as connection:
        return connection.execute(text(query)).mappings().first()


def fetch_all(engine, query: str):
    with engine.connect() as connection:
        return connection.execute(text(query)).mappings().all()


def seed_traversal_rows(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (
                    id, batch_run_id, original_file_name, content_hash, file_size_bytes, page_count,
                    document_number, processing_status, processing_error, processing_error_type,
                    processing_error_detail, processed_at, moved_to_path, extraction_version,
                    retention_mode, source_file_present, source_deleted_at, last_source_path,
                    retry_requires_reupload, last_ingestion_used_cached_result
                )
                VALUES
                    (1, NULL, 'auto.pdf', 'hash-auto', 100, 1, NULL, 'processed', NULL, NULL, NULL, '2026-05-22 10:00:00', NULL, 1, 'retain_failed_only', 0, NULL, NULL, 0, 0),
                    (2, NULL, 'review.pdf', 'hash-review', 100, 1, NULL, 'processed', NULL, NULL, NULL, '2026-05-22 10:05:00', NULL, 1, 'retain_failed_only', 0, NULL, NULL, 0, 0),
                    (3, NULL, 'blocked.pdf', 'hash-blocked', 100, 1, NULL, 'processed', NULL, NULL, NULL, '2026-05-22 10:10:00', NULL, 1, 'retain_failed_only', 0, NULL, NULL, 0, 0),
                    (4, NULL, 'uncertain.pdf', 'hash-uncertain', 100, 1, NULL, 'processed', NULL, NULL, NULL, '2026-05-22 10:15:00', NULL, 1, 'retain_failed_only', 0, NULL, NULL, 0, 0)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_references (
                    id, document_id, page_number, source_type, reference_class, raw_reference,
                    final_url, resolution_status, destination_type, destination_host,
                    requires_user_action, http_status, resolution_error_type, resolution_error_detail,
                    confidence_score, risk_level, recommended_action, review_status,
                    review_reason, evidence_summary, operator_decision, operator_note, reviewed_at
                )
                VALUES
                    (1, 1, 1, 'text', 'url', 'https://moph.go.th/a', 'https://moph.go.th/a', 'resolved', 'government', 'moph.go.th', 0, 200, NULL, NULL, 90, 'LOW', 'AUTO_ELIGIBLE', 'NOT_REQUIRED', 'Deterministic low-risk traversal candidate.', 'Page 1 text candidate: https://moph.go.th/a', NULL, NULL, NULL),
                    (2, 2, 1, 'qr', 'qr', 'https://bit.ly/demo', 'https://bit.ly/demo', 'resolved', 'redirect', 'bit.ly', 0, 200, NULL, NULL, 55, 'HIGH', 'REVIEW_REQUIRED', 'PENDING_REVIEW', 'Shortlink requires operator review.', 'Page 1 qr candidate: https://bit.ly/demo', NULL, NULL, NULL),
                    (3, 3, 1, 'text', 'url', 'http://127.0.0.1/admin', 'http://127.0.0.1/admin', 'resolved', 'external', '127.0.0.1', 0, 200, NULL, NULL, 0, 'BLOCKED', 'BLOCKED', 'NOT_REQUIRED', 'Loopback targets are blocked by policy.', 'Page 1 text candidate: http://127.0.0.1/admin', NULL, NULL, NULL),
                    (4, 4, 1, 'qr', 'qr', 'DOC:6176', NULL, 'pending', NULL, NULL, NULL, NULL, NULL, NULL, 10, 'MEDIUM', 'UNCERTAIN', 'PENDING_REVIEW', 'Offline-safe analysis could not classify confidently.', 'Page 1 candidate: DOC:6176', NULL, NULL, NULL)
                """
            )
        )
    return engine


def test_references_receive_step5_fields_after_processing(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "step5.pdf", "Reference https://moph.go.th/report")

    def fake_resolve_url(raw_url: str, *, settings):
        return {
            "raw_url": raw_url,
            "final_url": raw_url,
            "status": "resolved",
            "http_status_code": 200,
            "error": None,
            "error_type": None,
            "attempts": 1,
        }

    monkeypatch.setattr("app.batch.url_resolution.resolve_url", fake_resolve_url)

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT confidence_score, risk_level, recommended_action, review_status, review_reason, evidence_summary
        FROM document_references
        ORDER BY id DESC
        """,
    )

    assert row["confidence_score"] is not None
    assert row["risk_level"] is not None
    assert row["recommended_action"] is not None
    assert row["review_status"] is not None
    assert row["review_reason"]
    assert row["evidence_summary"]


def test_ops_traversal_groups_queues_correctly(client):
    seed_traversal_rows(client.app.state.postgres_engine)

    response = client.get("/ops/traversal")

    assert response.status_code == 200
    assert "AUTO_ELIGIBLE" in response.text
    assert "REVIEW_REQUIRED" in response.text
    assert "BLOCKED" in response.text
    assert "UNCERTAIN" in response.text
    assert "auto.pdf" in response.text
    assert "review.pdf" in response.text
    assert "blocked.pdf" in response.text
    assert "uncertain.pdf" in response.text


def test_operator_actions_create_append_only_review_rows(client, monkeypatch):
    seed_traversal_rows(client.app.state.postgres_engine)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("network resolution must not run during operator review actions")

    monkeypatch.setattr("app.batch.url_resolution.resolve_url", fail_if_called)

    approve_response = client.post("/ops/traversal/2/approve")
    reject_response = client.post("/ops/traversal/4/reject")
    skip_response = client.post("/ops/traversal/4/skip")
    note_response = client.post("/ops/traversal/4/note", data={"operator_note": "operator note"})

    assert approve_response.status_code == 200
    assert reject_response.status_code == 200
    assert skip_response.status_code == 200
    assert note_response.status_code == 200

    reference_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT review_status, operator_decision, operator_note
        FROM document_references
        WHERE id = 4
        """
    )
    history_rows = fetch_all(
        client.app.state.postgres_engine,
        """
        SELECT traversal_id, review_status, operator_decision, event_type
        FROM reference_traversal_reviews
        ORDER BY id
        """
    )
    document_count = fetch_one(
        client.app.state.postgres_engine,
        "SELECT COUNT(*) AS total_documents FROM documents",
    )

    assert reference_row["review_status"] in {"REJECTED", "SKIPPED"}
    assert reference_row["operator_note"] == "operator note"
    assert len(history_rows) == 4
    assert {row["event_type"] for row in history_rows} == {
        "TRAVERSAL_OPERATOR_APPROVED",
        "TRAVERSAL_OPERATOR_REJECTED",
        "TRAVERSAL_OPERATOR_SKIPPED",
        "TRAVERSAL_OPERATOR_NOTED",
    }
    assert document_count["total_documents"] == 4
