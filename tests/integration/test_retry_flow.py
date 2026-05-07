from pathlib import Path

from sqlalchemy import text


def _seed_failed_document(
    engine,
    *,
    document_id: int,
    source_path: Path | None,
    content_hash: str = "hash-retry",
):
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
                    moved_to_path,
                    extraction_version,
                    retention_mode,
                    source_file_present,
                    source_deleted_at,
                    last_source_path,
                    retry_requires_reupload,
                    last_ingestion_used_cached_result
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
                    :moved_to_path,
                    1,
                    'retain_failed_only',
                    :source_file_present,
                    NULL,
                    :last_source_path,
                    :retry_requires_reupload,
                    0
                )
                """
            ),
            {
                "document_id": document_id,
                "content_hash": content_hash,
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
                    document_id,
                    batch_run_id,
                    uploaded_file_name,
                    uploaded_at,
                    ingestion_status,
                    used_cached_result,
                    force_reprocess_requested,
                    retention_mode_used,
                    source_file_path,
                    source_file_present,
                    source_deleted_at,
                    cleanup_due_at,
                    retry_source_available,
                    error_type,
                    error_detail
                )
                VALUES (
                    :document_id,
                    NULL,
                    'retry-source.pdf',
                    '2026-04-24 10:00:00',
                    'failed',
                    0,
                    0,
                    'retain_failed_only',
                    :source_file_path,
                    :source_file_present,
                    NULL,
                    '2026-04-30 10:00:00',
                    :retry_source_available,
                    'INVALID_PDF',
                    'broken file'
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


def test_retry_failed_document_redirects_to_batch_when_source_exists(client):
    source_path = Path(client.app.state.settings.failed_retained_dir) / "retry-source.pdf"
    source_path.write_bytes(b"failed pdf bytes")
    _seed_failed_document(client.app.state.postgres_engine, document_id=501, source_path=source_path)

    response = client.post("/documents/501/retry", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/batch"
    assert source_path.exists()


def test_retry_failed_document_requires_reupload_when_source_missing(client):
    _seed_failed_document(client.app.state.postgres_engine, document_id=502, source_path=None)

    response = client.post("/documents/502/retry", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/results?retry_status=requires_reupload"


def test_results_show_failed_document_retry_status_and_actions(client):
    source_path = Path(client.app.state.settings.failed_retained_dir) / "retry-source.pdf"
    source_path.write_bytes(b"failed pdf bytes")
    _seed_failed_document(client.app.state.postgres_engine, document_id=503, source_path=source_path)

    response = client.get("/results?processing_status=failed")

    assert response.status_code == 200
    assert "retry-source.pdf" in response.text
    assert "/documents/503/retry" in response.text
    assert "/documents/503/retry-resolution" in response.text
    assert "/documents/503/force-reprocess" in response.text
