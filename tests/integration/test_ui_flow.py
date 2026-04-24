import io
from pathlib import Path

import fitz
from sqlalchemy import text

from app.services.inbox_paths import get_inbox_path


def authenticate_client(client, username: str = "alice", display_name: str = "OLRE User"):
    token = client.app.state.session_manager.create_session(username=username, display_name=display_name)
    client.cookies.set("olre_session", token)


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
                    processed_at,
                    moved_to_path
                )
                VALUES
                    (1, NULL, 'alpha-letter.pdf', 'hash-alpha', 100, 2, NULL, 'processed', NULL, '2026-04-24 10:00:00', '/processed/alpha-letter.pdf'),
                    (2, NULL, 'beta-scan.pdf', 'hash-beta', 120, 1, NULL, 'processed', NULL, '2026-04-24 11:00:00', '/processed/beta-scan.pdf')
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
                    http_status
                )
                VALUES
                    (1, 1, 1, 'text', 'url', 'https://example.com/raw-alpha', 'https://example.com/final-alpha', 'resolved', 200),
                    (2, 1, 2, 'text', 'url', 'https://example.com/missing', 'https://example.com/missing', 'failed', 404),
                    (3, 2, 1, 'image', 'qr', 'DOC:6176', NULL, 'pending', NULL)
                """
            )
        )


def test_home_navigation_rendered_in_thai(client):
    authenticate_client(client)

    response = client.get("/")

    assert response.status_code == 200
    assert "/imports" in response.text
    assert "/batch" in response.text
    assert "/results" in response.text
    assert "/exports" in response.text


def test_imports_page_supports_multiple_pdf_uploads(client):
    authenticate_client(client)

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
    authenticate_client(client)

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
    authenticate_client(client)
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/results")

    assert response.status_code == 200
    assert "Extracted References" in response.text
    assert "alpha-letter.pdf" in response.text
    assert "beta-scan.pdf" in response.text


def test_results_filtering_works(client):
    authenticate_client(client)
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/results?status=failed&source_type=text")

    assert response.status_code == 200
    assert "alpha-letter.pdf" in response.text
    assert "https://example.com/missing" in response.text
    assert "DOC:6176" not in response.text


def test_results_search_works(client):
    authenticate_client(client)
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/results?search=beta-scan")

    assert response.status_code == 200
    assert "beta-scan.pdf" in response.text
    assert "DOC:6176" in response.text
    assert "alpha-letter.pdf" not in response.text


def test_csv_export_returns_filtered_rows(client):
    authenticate_client(client)
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
    authenticate_client(client)
    seed_reference_rows(client.app.state.postgres_engine)

    response = client.get("/exports/markdown?source_type=image")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    body = response.text
    assert "# OLRE Extraction Report" in body
    assert "## Summary" in body
    assert "## Details" in body
    assert "### File: beta-scan.pdf" in body
    assert "| Page | Type | Raw | Final | Status |" in body
    assert "| 1 | qr | DOC:6176 |  | pending |" in body
