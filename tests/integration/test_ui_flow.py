import io
from pathlib import Path

import fitz
from sqlalchemy import text

from app.i18n.th import LABELS
from app.services.inbox_paths import get_inbox_path


def build_pdf_bytes(text_content: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text_content)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def fetch_one(engine, query: str):
    with engine.connect() as connection:
        return connection.execute(text(query)).mappings().first()


def seed_reference_rows(engine):
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
                VALUES
                    (1, NULL, 'alpha-letter.pdf', 'hash-alpha', 100, 2, NULL, 'processed', NULL, NULL, NULL, '2026-04-24 10:00:00', NULL, 1, 'retain_failed_only', 0, '2026-04-24 10:01:00', NULL, 1, 0),
                    (2, NULL, 'beta-scan.pdf', 'hash-beta', 120, 1, NULL, 'processed', NULL, NULL, NULL, '2026-04-24 11:00:00', NULL, 1, 'retain_failed_only', 0, '2026-04-24 11:01:00', NULL, 1, 0)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_references (
                    id,
                    document_id,
                    page_number,
                    source_type,
                    reference_class,
                    raw_reference,
                    final_url,
                    resolution_status,
                    http_status,
                    resolution_error_type,
                    resolution_error_detail
                )
                VALUES
                    (1, 1, 1, 'text', 'url', 'https://example.com/raw-alpha', 'https://example.com/final-alpha', 'resolved', 200, NULL, NULL),
                    (2, 1, 2, 'text', 'url', 'https://example.com/missing', 'https://example.com/missing', 'failed', 404, 'URL_HTTP_ERROR', 'HTTP status 404'),
                    (3, 2, 1, 'qr', 'qr', 'DOC:6176', NULL, 'pending', NULL, NULL, NULL)
                """
            )
        )


def test_home_navigation_rendered_in_thai(client):
    response = client.get("/", follow_redirects=True)

    assert response.status_code == 200
    assert "/imports" in response.text
    assert "/batch" in response.text
    assert "/results" in response.text
    assert "/exports" in response.text


def test_imports_page_supports_multiple_pdf_uploads(client):
    response = client.post(
        "/imports/upload",
        files=[
            ("files", ("letter-001.pdf", io.BytesIO(build_pdf_bytes("file 1")), "application/pdf")),
            ("files", ("letter-002.pdf", io.BytesIO(build_pdf_bytes("file 2")), "application/pdf")),
        ],
    )

    assert response.status_code == 200
    assert "letter-001.pdf" in response.text
    assert "letter-002.pdf" in response.text


def test_upload_to_batch_uses_same_inbox_directory(client):
    upload_response = client.post(
        "/imports/upload",
        files=[
            (
                "files",
                ("batch-source.pdf", io.BytesIO(build_pdf_bytes("See https://example.com/olre")), "application/pdf"),
            ),
        ],
    )

    assert upload_response.status_code == 200

    inbox_dir = get_inbox_path(client.app.state.settings)
    uploaded_file = inbox_dir / "batch-source.pdf"
    assert uploaded_file.exists()
    assert uploaded_file.parent == Path(client.app.state.settings.input_dir).resolve()

    batch_response = client.post("/batch/process")
    assert batch_response.status_code == 200

    batch_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT total_files_seen, total_files_processed, total_references_found, status
        FROM batch_runs
        ORDER BY id DESC
        """,
    )
    document_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT original_file_name, processing_status
        FROM documents
        ORDER BY id DESC
        """,
    )

    assert batch_row["total_files_seen"] > 0
    assert batch_row["total_files_processed"] > 0
    assert batch_row["status"] in {"completed", "completed_with_errors"}
    assert document_row["original_file_name"] == "batch-source.pdf"
    assert document_row["processing_status"] == "processed"


def test_results_page_loads(client):
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/results")

    assert response.status_code == 200
    assert LABELS["results_title"] in response.text
    assert "alpha-letter.pdf" in response.text
    assert "beta-scan.pdf" in response.text


def test_results_filtering_works(client):
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/results?status=failed&source_type=text")

    assert response.status_code == 200
    assert "alpha-letter.pdf" in response.text
    assert "https://example.com/missing" in response.text
    assert "DOC:6176" not in response.text


def test_results_search_works(client):
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/results?search=beta-scan")

    assert response.status_code == 200
    assert "beta-scan.pdf" in response.text
    assert "DOC:6176" in response.text
    assert "alpha-letter.pdf" not in response.text


def test_csv_export_returns_filtered_rows(client):
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/exports/csv?status=resolved")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="olre-results.csv"' in response.headers["content-disposition"]
    body = response.text
    assert "document_id,filename,page_number,reference_class,source_type,raw_reference,final_url,resolution_status" in body
    assert "alpha-letter.pdf" in body
    assert "https://example.com/final-alpha" in body
    assert "beta-scan.pdf" not in body


def test_markdown_export_format_is_valid(client):
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/exports/markdown?source_type=qr")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    body = response.text
    assert "# OLRE Extraction Report" in body
    assert "## Summary" in body
    assert "## Details" in body
    assert "### File: beta-scan.pdf" in body
    assert "| Page | Type | Raw | Final | Status |" in body
    assert "| 1 | qr | DOC:6176 |  | pending |" in body


def test_batch_page_shows_monitoring_and_error_intelligence(client):
    with client.app.state.postgres_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO batch_runs (
                    id,
                    triggered_by,
                    started_at,
                    finished_at,
                    status,
                    total_files_seen,
                    total_files_processed,
                    duplicate_files_skipped,
                    failed_files,
                    total_references_found
                )
                VALUES
                    (1, 'alice', '2026-04-24 09:00:00', '2026-04-24 09:05:00', 'completed_with_errors', 3, 2, 0, 1, 4)
                """
            )
        )
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
                VALUES
                    (1, 1, 'scan-001.pdf', 'hash-scan-001', 100, 1, NULL, 'processed', NULL, 'OCR_NOT_AVAILABLE', 'tesseract missing', '2026-04-24 09:05:00', NULL, 1, 'retain_failed_only', 0, '2026-04-24 09:06:00', NULL, 1, 0)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_ingestions (
                    id, document_id, batch_run_id, uploaded_file_name, uploaded_at, ingestion_status,
                    used_cached_result, force_reprocess_requested, retention_mode_used, source_file_path,
                    source_file_present, source_deleted_at, cleanup_due_at, retry_source_available,
                    error_type, error_detail
                )
                VALUES
                    (1, 1, 1, 'scan-001.pdf', '2026-04-24 09:00:00', 'processed_fresh',
                     0, 0, 'retain_failed_only', NULL, 0, '2026-04-24 09:06:00', NULL, 0,
                     NULL, NULL)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO processing_logs (
                    id,
                    batch_run_id,
                    document_id,
                    level,
                    step_name,
                    message,
                    created_at
                )
                VALUES
                    (1, 1, 1, 'WARNING', 'reference_ocr', '[OCR_TIMEOUT] OCR exceeded timeout of 30 seconds', '2026-04-24 09:03:00')
                """
            )
        )

    response = client.get("/batch")

    assert response.status_code == 200
    assert LABELS["batch_monitor"] in response.text
    assert LABELS["error_intelligence"] in response.text
    assert "OCR_TIMEOUT" in response.text
    assert "scan-001.pdf" in response.text


def test_batch_run_pages_render(client):
    with client.app.state.postgres_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO batch_runs (
                    id,
                    triggered_by,
                    started_at,
                    finished_at,
                    status,
                    total_files_seen,
                    total_files_processed,
                    duplicate_files_skipped,
                    failed_files,
                    total_references_found
                )
                VALUES
                    (1, 'alice', '2026-04-24 09:00:00', '2026-04-24 09:05:00', 'completed_with_errors', 3, 2, 1, 1, 4)
                """
            )
        )
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
                VALUES
                    (1, 1, 'invalid.pdf', 'hash-invalid', 99, 1, NULL, 'failed', 'bad pdf', 'INVALID_PDF', 'broken file', '2026-04-24 09:05:00', '/error/invalid.pdf', 1, 'retain_failed_only', 1, NULL, '/error/invalid.pdf', 0, 0)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_ingestions (
                    id, document_id, batch_run_id, uploaded_file_name, uploaded_at, ingestion_status,
                    used_cached_result, force_reprocess_requested, retention_mode_used, source_file_path,
                    source_file_present, source_deleted_at, cleanup_due_at, retry_source_available,
                    error_type, error_detail
                )
                VALUES
                    (1, 1, 1, 'invalid.pdf', '2026-04-24 09:00:00', 'failed',
                     0, 0, 'retain_failed_only', '/error/invalid.pdf', 1, NULL,
                     '2026-04-30 09:00:00', 1, 'INVALID_PDF', 'broken file')
                """
            )
        )

    list_response = client.get("/batch/runs")
    detail_response = client.get("/batch/runs/1")

    assert list_response.status_code == 200
    assert "#1" in list_response.text
    assert detail_response.status_code == 200
    assert "INVALID_PDF" in detail_response.text
    assert "invalid.pdf" in detail_response.text
