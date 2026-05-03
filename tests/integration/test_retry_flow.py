from pathlib import Path

from sqlalchemy import text


def _seed_failed_document(engine, *, document_id: int, moved_to_path: Path, content_hash: str = "hash-retry"):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (
                    id,
                    batch_run_id,
                    original_file_name,
                    content_hash,
                    file_size_bytes,
                    page_count,
                    document_number,
                    processing_status,
                    processing_error,
                    processing_error_type,
                    processing_error_detail,
                    processed_at,
                    moved_to_path
                )
                VALUES (
                    :document_id,
                    NULL,
                    'retry-source.pdf',
                    :content_hash,
                    100,
                    1,
                    NULL,
                    'failed',
                    'bad pdf',
                    'INVALID_PDF',
                    'broken file',
                    '2026-04-24 10:00:00',
                    :moved_to_path
                )
                """
            ),
            {
                "document_id": document_id,
                "content_hash": content_hash,
                "moved_to_path": str(moved_to_path),
            },
        )


def test_retry_failed_document_copies_file_to_inbox_and_preserves_old_record(client):
    source_path = Path(client.app.state.settings.error_dir) / "retry-source.pdf"
    source_path.write_bytes(b"failed pdf bytes")
    _seed_failed_document(client.app.state.postgres_engine, document_id=501, moved_to_path=source_path)

    response = client.post("/documents/501/retry", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/imports"
    retried_path = Path(client.app.state.settings.input_dir) / "retry-source.pdf"
    assert retried_path.exists()
    assert source_path.exists()

    with client.app.state.postgres_engine.connect() as connection:
        row = connection.execute(
            text("SELECT processing_status FROM documents WHERE id = 501")
        ).mappings().one()
    assert row["processing_status"] == "failed"


def test_retry_failed_document_renames_on_collision(client):
    source_path = Path(client.app.state.settings.error_dir) / "retry-source.pdf"
    source_path.write_bytes(b"failed pdf bytes")
    existing_inbox_path = Path(client.app.state.settings.input_dir) / "retry-source.pdf"
    existing_inbox_path.write_bytes(b"existing bytes")
    _seed_failed_document(
        client.app.state.postgres_engine,
        document_id=502,
        moved_to_path=source_path,
        content_hash="abcdef123456",
    )

    response = client.post("/documents/502/retry", follow_redirects=False)

    assert response.status_code == 303
    assert existing_inbox_path.read_bytes() == b"existing bytes"
    assert (Path(client.app.state.settings.input_dir) / "retry-source_abcdef12.pdf").exists()


def test_results_show_failed_document_without_references_and_retry_button(client):
    source_path = Path(client.app.state.settings.error_dir) / "retry-source.pdf"
    source_path.write_bytes(b"failed pdf bytes")
    _seed_failed_document(client.app.state.postgres_engine, document_id=503, moved_to_path=source_path)

    response = client.get("/results?processing_status=failed")

    assert response.status_code == 200
    assert "retry-source.pdf" in response.text
    assert "/documents/503/retry" in response.text
    assert "INVALID_PDF" in response.text
