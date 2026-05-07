from pathlib import Path
from types import SimpleNamespace

import fitz
import httpx
from sqlalchemy import text

from app.batch import url_resolution
from app.batch.error_types import INVALID_PDF, URL_HTTP_ERROR, URL_TIMEOUT
from app.batch.reference_extraction import ExtractedReference
from app.services.batch_monitor_service import get_batch_run_detail, list_batch_runs
from app.services.process_batch import fetch_home_batch_summary, run_batch_registration


def create_valid_pdf(path: Path, text_content: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text_content)
    document.save(path)
    document.close()


def create_fake_pdf(path: Path) -> None:
    path.write_bytes(b"not a real pdf file")


def fetch_one(engine, query: str):
    with engine.connect() as connection:
        return connection.execute(text(query)).mappings().first()


def fetch_all(engine, query: str):
    with engine.connect() as connection:
        return connection.execute(text(query)).mappings().all()


def fetch_references(engine):
    return fetch_all(
        engine,
        """
        SELECT page_number, source_type, reference_class, raw_reference, resolution_status, final_url,
               resolution_error_type, resolution_error_detail
        FROM document_references
        ORDER BY id
        """,
    )


def test_batch_run_row_created(client):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "letter-001.pdf", "batch run test")

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    assert summary.batch_run_id >= 1
    batch_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT triggered_by, total_files_seen, total_files_processed,
               duplicate_files_skipped, failed_files, status
        FROM batch_runs
        """
    )
    assert batch_row["triggered_by"] == "alice"
    assert batch_row["total_files_seen"] == 1
    assert batch_row["total_files_processed"] == 1
    assert batch_row["duplicate_files_skipped"] == 0
    assert batch_row["failed_files"] == 0
    assert batch_row["status"] == "completed"


def test_documents_row_created_for_valid_pdf(client):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "letter-002.pdf", "document row")

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    document_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT original_file_name, file_size_bytes, processing_status, moved_to_path, source_file_present
        FROM documents
        """
    )
    assert document_row["original_file_name"] == "letter-002.pdf"
    assert document_row["file_size_bytes"] > 0
    assert document_row["processing_status"] == "processed"
    assert document_row["moved_to_path"] is None
    assert document_row["source_file_present"] == 0


def test_duplicate_content_skip_does_not_create_new_processed_record(client):
    input_dir = Path(client.app.state.settings.input_dir)

    create_valid_pdf(input_dir / "letter-a.pdf", "same content")
    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    original_processed_count = len(
        fetch_all(
            client.app.state.postgres_engine,
            "SELECT id FROM documents WHERE processing_status = 'processed'",
        )
    )

    original_pdf_path = input_dir / "letter-a.pdf"
    create_valid_pdf(original_pdf_path, "same content")
    duplicate_source = input_dir / "letter-b.pdf"
    duplicate_source.write_bytes(original_pdf_path.read_bytes())

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    processed_rows = fetch_all(
        client.app.state.postgres_engine,
        "SELECT id, original_file_name, processing_status FROM documents ORDER BY id",
    )
    assert len(processed_rows) == original_processed_count
    assert summary.duplicate_files_skipped == 1
    assert summary.total_files_processed == 0
    assert not duplicate_source.exists()
    ingestion_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT ingestion_status, used_cached_result
        FROM document_ingestions
        ORDER BY id DESC
        """,
    )
    assert ingestion_row["ingestion_status"] == "reused_cached"
    assert ingestion_row["used_cached_result"] == 1


def test_same_filename_different_content_treated_as_new(client):
    input_dir = Path(client.app.state.settings.input_dir)

    create_valid_pdf(input_dir / "same.pdf", "first content")
    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    create_valid_pdf(input_dir / "same.pdf", "second content")
    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    document_rows = fetch_all(
        client.app.state.postgres_engine,
        "SELECT id, original_file_name, content_hash FROM documents ORDER BY id",
    )
    assert len(document_rows) == 2
    assert document_rows[0]["original_file_name"] == "same.pdf"
    assert document_rows[1]["original_file_name"] == "same.pdf"
    assert document_rows[0]["content_hash"] != document_rows[1]["content_hash"]


def test_processed_file_deleted_after_success_under_default_retention(client):
    input_dir = Path(client.app.state.settings.input_dir)
    source_path = input_dir / "move-me.pdf"
    create_valid_pdf(source_path, "move to processed")

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    assert not source_path.exists()
    document_row = fetch_one(
        client.app.state.postgres_engine,
        "SELECT source_file_present, moved_to_path FROM documents ORDER BY id DESC",
    )
    assert document_row["source_file_present"] == 0
    assert document_row["moved_to_path"] is None


def test_fake_pdf_marked_failed_and_moved_to_error(client):
    input_dir = Path(client.app.state.settings.input_dir)
    failed_retained_dir = Path(client.app.state.settings.failed_retained_dir)
    source_path = input_dir / "fake.pdf"
    create_fake_pdf(source_path)

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    document_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT processing_status, processing_error, processing_error_type, moved_to_path
        FROM documents
        """
    )
    log_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT step_name, message
        FROM processing_logs
        WHERE step_name = 'pdf_validation'
        ORDER BY id DESC
        """
    )

    assert summary.failed_files == 1
    assert summary.total_files_processed == 0
    assert summary.status == "completed_with_errors"
    assert document_row["processing_status"] == "failed"
    assert document_row["processing_error"]
    assert document_row["processing_error_type"] == INVALID_PDF
    assert document_row["processing_error"].startswith("[PDF_VALIDATION_FAILED] PDF validation failed:")
    assert not source_path.exists()
    assert len(list(failed_retained_dir.glob("fake*.pdf"))) == 1
    assert log_row["step_name"] == "pdf_validation"
    assert log_row["message"].startswith("[PDF_VALIDATION_FAILED] PDF validation failed:")


def test_batch_summary_reflects_duplicate_and_failed_counts(client):
    input_dir = Path(client.app.state.settings.input_dir)
    processed_dir = Path(client.app.state.settings.processed_dir)

    create_valid_pdf(input_dir / "valid.pdf", "batch summary valid")
    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    duplicate_source = input_dir / "duplicate.pdf"
    duplicate_source.write_bytes((processed_dir / "valid.pdf").read_bytes())
    create_fake_pdf(input_dir / "invalid.pdf")

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )
    latest_summary = fetch_home_batch_summary(client.app.state.postgres_engine)

    assert summary.total_files_seen == 2
    assert summary.total_files_processed == 0
    assert summary.duplicate_files_skipped == 1
    assert summary.failed_files == 1
    assert summary.status == "completed_with_errors"

    assert latest_summary is not None
    assert latest_summary.total_files_seen == 2
    assert latest_summary.total_files_processed == 0
    assert latest_summary.duplicate_files_skipped == 1
    assert latest_summary.failed_files == 1


def test_text_url_reference_persisted_from_pdf_text(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "text-url.pdf", "Reference https://example.com/files/12345")

    def fake_resolve_url(raw_url: str):
        return {
            "raw_url": raw_url,
            "final_url": "https://resolved.example.com/files/12345",
            "status": "resolved",
            "http_status_code": 200,
            "error": None,
            "attempts": 1,
        }

    monkeypatch.setattr("app.batch.url_resolution.resolve_url", fake_resolve_url)

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_rows = fetch_references(client.app.state.postgres_engine)
    assert len(reference_rows) == 1
    assert reference_rows[0]["page_number"] == 1
    assert reference_rows[0]["source_type"] == "text"
    assert reference_rows[0]["reference_class"] == "url"
    assert reference_rows[0]["raw_reference"] == "https://example.com/files/12345"
    assert reference_rows[0]["resolution_status"] == "resolved"
    assert reference_rows[0]["final_url"] == "https://resolved.example.com/files/12345"


def test_short_url_reference_classified_from_pdf_text(client):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "short-url.pdf", "Short link https://bit.ly/olre-ref")

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_rows = fetch_references(client.app.state.postgres_engine)
    assert len(reference_rows) == 1
    assert reference_rows[0]["source_type"] == "text"
    assert reference_rows[0]["reference_class"] == "url"
    assert reference_rows[0]["raw_reference"] == "https://bit.ly/olre-ref"


def test_qr_url_reference_persisted(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "qr-url.pdf", "qr url placeholder")

    def fake_extract_references_from_pdf(_file_path):
        return (
            [
                ExtractedReference(
                    page_number=1,
                    source_type="qr",
                    reference_class="qr",
                    raw_reference="https://t.co/olre-qr",
                )
            ],
            [],
            1,
        )

    monkeypatch.setattr(
        "app.services.process_batch.extract_references_from_pdf",
        fake_extract_references_from_pdf,
    )

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_rows = fetch_references(client.app.state.postgres_engine)
    assert len(reference_rows) == 1
    assert reference_rows[0]["source_type"] == "qr"
    assert reference_rows[0]["reference_class"] == "qr"
    assert reference_rows[0]["raw_reference"] == "https://t.co/olre-qr"


def test_non_url_qr_reference_persisted(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "qr-non-url.pdf", "qr non-url placeholder")

    def fake_extract_references_from_pdf(_file_path):
        return (
            [
                ExtractedReference(
                    page_number=1,
                    source_type="qr",
                    reference_class="qr",
                    raw_reference="DOC:6176",
                )
            ],
            [],
            1,
        )

    monkeypatch.setattr(
        "app.services.process_batch.extract_references_from_pdf",
        fake_extract_references_from_pdf,
    )

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_rows = fetch_references(client.app.state.postgres_engine)
    assert len(reference_rows) == 1
    assert reference_rows[0]["source_type"] == "qr"
    assert reference_rows[0]["reference_class"] == "qr"
    assert reference_rows[0]["raw_reference"] == "DOC:6176"


def test_duplicate_reference_suppression(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "duplicate-reference.pdf", "duplicate placeholder")

    duplicate_reference = ExtractedReference(
        page_number=1,
        source_type="qr",
        reference_class="qr",
        raw_reference="https://example.com/dup",
    )

    def fake_extract_references_from_pdf(_file_path):
        return ([duplicate_reference, duplicate_reference], [], 1)

    monkeypatch.setattr(
        "app.services.process_batch.extract_references_from_pdf",
        fake_extract_references_from_pdf,
    )

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_rows = fetch_references(client.app.state.postgres_engine)
    batch_row = fetch_one(
        client.app.state.postgres_engine,
        "SELECT total_references_found, status FROM batch_runs ORDER BY id DESC",
    )

    assert summary.status == "completed"
    assert len(reference_rows) == 1
    assert reference_rows[0]["raw_reference"] == "https://example.com/dup"
    assert batch_row["total_references_found"] == 1


def test_pending_http_reference_resolved_after_insert(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "resolve-url.pdf", "Reference https://example.com/resolve-me")

    def fake_resolve_url(raw_url: str):
        return {
            "raw_url": raw_url,
            "final_url": "https://final.example.com/destination",
            "status": "resolved",
            "http_status_code": 200,
            "error": None,
            "attempts": 1,
        }

    monkeypatch.setattr("app.batch.url_resolution.resolve_url", fake_resolve_url)

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT raw_reference, final_url, resolution_status
        FROM document_references
        ORDER BY id DESC
        """,
    )

    assert reference_row["raw_reference"] == "https://example.com/resolve-me"
    assert reference_row["final_url"] == "https://final.example.com/destination"
    assert reference_row["resolution_status"] == "resolved"


def test_force_reprocess_rebuilds_existing_hash_when_requested(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "force.pdf", "Reference https://example.com/original")
    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    create_valid_pdf(input_dir / "force.pdf", "Reference https://example.com/original")

    def fake_extract_references_from_pdf(_file_path, **_kwargs):
        return (
            [
                ExtractedReference(
                    page_number=1,
                    source_type="text",
                    reference_class="url",
                    raw_reference="https://example.com/forced",
                )
            ],
            [],
            1,
        )

    monkeypatch.setattr(
        "app.services.process_batch.extract_references_from_pdf",
        fake_extract_references_from_pdf,
    )

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
        force_reprocess=True,
    )

    assert summary.total_files_processed == 1
    reference_rows = fetch_references(client.app.state.postgres_engine)
    assert len(reference_rows) == 1
    assert reference_rows[0]["raw_reference"] == "https://example.com/forced"
    ingestion_row = fetch_one(
        client.app.state.postgres_engine,
        "SELECT ingestion_status, force_reprocess_requested FROM document_ingestions ORDER BY id DESC",
    )
    assert ingestion_row["ingestion_status"] == "forced_reprocess"
    assert ingestion_row["force_reprocess_requested"] == 1


def test_pending_http_reference_404_does_not_break_batch(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "resolve-404.pdf", "Reference https://example.com/missing")

    def fake_resolve_url(raw_url: str):
        return {
            "raw_url": raw_url,
            "final_url": "https://example.com/missing",
            "status": "failed",
            "http_status_code": 404,
            "error": "HTTP status 404",
            "attempts": 1,
        }

    monkeypatch.setattr("app.batch.url_resolution.resolve_url", fake_resolve_url)

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT final_url, resolution_status
        FROM document_references
        ORDER BY id DESC
        """,
    )
    document_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT processing_status
        FROM documents
        ORDER BY id DESC
        """,
    )

    assert summary.total_files_processed == 1
    assert document_row["processing_status"] == "processed"
    assert reference_row["final_url"] == "https://example.com/missing"
    assert reference_row["resolution_status"] == "failed"
    assert fetch_one(
        client.app.state.postgres_engine,
        "SELECT resolution_error_type FROM document_references ORDER BY id DESC",
    )["resolution_error_type"] == URL_HTTP_ERROR


def test_pending_http_reference_timeout_does_not_break_batch(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "resolve-timeout.pdf", "Reference https://example.com/timeout")

    def fake_resolve_url(raw_url: str):
        return {
            "raw_url": raw_url,
            "final_url": None,
            "status": "failed",
            "http_status_code": None,
            "error": "timed out",
            "attempts": 2,
        }

    monkeypatch.setattr("app.batch.url_resolution.resolve_url", fake_resolve_url)

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT final_url, resolution_status, resolution_error_type
        FROM document_references
        ORDER BY id DESC
        """,
    )
    document_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT processing_status
        FROM documents
        ORDER BY id DESC
        """,
    )

    assert summary.total_files_processed == 1
    assert document_row["processing_status"] == "processed"
    assert reference_row["final_url"] is None
    assert reference_row["resolution_status"] == "failed"
    assert reference_row["resolution_error_type"] == URL_TIMEOUT


def test_non_http_reference_skipped_without_network_call(client, monkeypatch, caplog):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "skip-non-http.pdf", "qr non-url placeholder")

    def fake_extract_references_from_pdf(_file_path):
        return (
            [
                ExtractedReference(
                    page_number=1,
                    source_type="qr",
                    reference_class="qr",
                    raw_reference="DOC:6176",
                )
            ],
            [],
            1,
        )

    def fail_if_called(_raw_url: str):
        raise AssertionError("resolve_url should not be called for non-http references")

    monkeypatch.setattr(
        "app.services.process_batch.extract_references_from_pdf",
        fake_extract_references_from_pdf,
    )
    monkeypatch.setattr("app.batch.url_resolution.resolve_url", fail_if_called)

    with caplog.at_level("INFO"):
        summary = run_batch_registration(
            client.app.state.settings,
            client.app.state.postgres_engine,
            triggered_by="alice",
        )

    reference_row = fetch_one(
        client.app.state.postgres_engine,
        """
        SELECT raw_reference, final_url, resolution_status
        FROM document_references
        ORDER BY id DESC
        """,
    )

    assert summary.total_files_processed == 1
    assert reference_row["raw_reference"] == "DOC:6176"
    assert reference_row["final_url"] is None
    assert reference_row["resolution_status"] == "pending"
    assert "[URL_RESOLVE_SKIP]" in caplog.text


def test_ocr_fallback_extracts_url_from_low_text_pdf(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "ocr-fallback.pdf", "")

    monkeypatch.setattr(
        "app.batch.reference_extraction.extract_text_with_ocr_if_needed",
        lambda _page, _page_number, _existing_text, _settings: {
            "used_ocr": True,
            "text": "Visit https://ocr.example.com/form",
            "char_count": 34,
            "engine": "tesseract",
            "error": None,
            "error_type": None,
        },
    )
    monkeypatch.setattr(
        "app.batch.url_resolution.resolve_url",
        lambda raw_url: {
            "raw_url": raw_url,
            "final_url": raw_url,
            "status": "resolved",
            "http_status_code": 200,
            "error": None,
            "attempts": 1,
        },
    )

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_rows = fetch_references(client.app.state.postgres_engine)
    assert len(reference_rows) == 1
    assert reference_rows[0]["source_type"] == "ocr"
    assert reference_rows[0]["reference_class"] == "url"
    assert reference_rows[0]["raw_reference"] == "https://ocr.example.com/form"

    assert reference_rows[0]["resolution_error_type"] is None


def test_ocr_disabled_does_not_crash_and_qr_still_works(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "ocr-disabled.pdf", "")
    client.app.state.settings.ocr_enabled = False

    monkeypatch.setattr(
        "app.batch.reference_extraction.detect_qr_values_from_page",
        lambda _page: ["DOC:6176"],
    )

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    reference_rows = fetch_references(client.app.state.postgres_engine)
    assert len(reference_rows) == 1
    assert reference_rows[0]["source_type"] == "qr"
    assert reference_rows[0]["raw_reference"] == "DOC:6176"


def test_ocr_unavailable_is_classified_without_failing_batch(client, monkeypatch):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "ocr-unavailable.pdf", "")

    monkeypatch.setattr(
        "app.batch.reference_extraction.extract_text_with_ocr_if_needed",
        lambda _page, _page_number, _existing_text, _settings: {
            "used_ocr": True,
            "text": "",
            "char_count": 0,
            "engine": "tesseract",
            "error": "tesseract missing",
            "error_type": "OCR_NOT_AVAILABLE",
        },
    )

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    document_row = fetch_one(
        client.app.state.postgres_engine,
        "SELECT processing_status, processing_error_type FROM documents ORDER BY id DESC",
    )
    assert summary.total_files_processed == 1
    assert document_row["processing_status"] == "processed"
    assert document_row["processing_error_type"] == "OCR_NOT_AVAILABLE"


def test_batch_monitor_service_returns_runs_and_detail(client):
    input_dir = Path(client.app.state.settings.input_dir)
    create_valid_pdf(input_dir / "batch-monitor.pdf", "Reference https://example.com/monitor")

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    with client.app.state.postgres_engine.begin() as connection:
        batch_run_id = connection.execute(text("SELECT id FROM batch_runs ORDER BY id DESC")).scalar_one()

    from app.db.postgres import create_postgres_session_factory

    session_factory = create_postgres_session_factory(client.app.state.postgres_engine)
    with session_factory() as session:
        runs = list_batch_runs(session, page=1, page_size=20)
        detail = get_batch_run_detail(session, batch_run_id)

    assert runs["items"]
    assert runs["items"][0]["batch_run_id"] == batch_run_id
    assert detail is not None
    assert detail["batch"]["batch_run_id"] == batch_run_id
    assert detail["documents"]


def test_resolve_url_success_on_first_attempt(monkeypatch):
    attempts = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, raw_url):
            attempts.append(raw_url)

            class Response:
                status_code = 200
                url = "https://final.example.com/redirected"

            return Response()

    monkeypatch.setattr(url_resolution.httpx, "Client", FakeClient)

    settings = SimpleNamespace(
        url_resolve_timeout_seconds=5.0,
        url_resolve_max_attempts=2,
        url_resolve_user_agent="OLRE Test",
    )
    result = url_resolution.resolve_url("https://example.com/start", settings=settings)

    assert result == {
        "raw_url": "https://example.com/start",
        "final_url": "https://final.example.com/redirected",
        "status": "resolved",
        "http_status_code": 200,
        "error": None,
        "error_type": None,
        "attempts": 1,
    }
    assert attempts == ["https://example.com/start"]


def test_is_http_url_handles_invalid_values_safely():
    assert url_resolution.is_http_url("https://example.com/path")
    assert url_resolution.is_http_url("  http://example.com/path  ")
    assert not url_resolution.is_http_url(None)
    assert not url_resolution.is_http_url("")
    assert not url_resolution.is_http_url("   ")
    assert not url_resolution.is_http_url("ftp://example.com/path")
    assert not url_resolution.is_http_url(123)  # type: ignore[arg-type]


def test_resolve_url_marks_http_404_as_failed(monkeypatch):
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, _raw_url):
            class Response:
                status_code = 404
                url = "https://example.com/missing"

            return Response()

    monkeypatch.setattr(url_resolution.httpx, "Client", FakeClient)

    settings = SimpleNamespace(
        url_resolve_timeout_seconds=5.0,
        url_resolve_max_attempts=2,
        url_resolve_user_agent="OLRE Test",
    )
    result = url_resolution.resolve_url("https://example.com/missing", settings=settings)

    assert result == {
        "raw_url": "https://example.com/missing",
        "final_url": "https://example.com/missing",
        "status": "failed",
        "http_status_code": 404,
        "error": "HTTP status 404",
        "error_type": URL_HTTP_ERROR,
        "attempts": 1,
    }


def test_resolve_url_retries_timeout_and_fails(monkeypatch):
    attempts = []

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, raw_url):
            attempts.append(raw_url)
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(url_resolution.httpx, "Client", FakeClient)

    settings = SimpleNamespace(
        url_resolve_timeout_seconds=5.0,
        url_resolve_max_attempts=2,
        url_resolve_user_agent="OLRE Test",
    )
    result = url_resolution.resolve_url("https://example.com/timeout", settings=settings)

    assert result == {
        "raw_url": "https://example.com/timeout",
        "final_url": None,
        "status": "failed",
        "http_status_code": None,
        "error": "timed out",
        "error_type": URL_TIMEOUT,
        "attempts": 2,
    }
    assert attempts == [
        "https://example.com/timeout",
        "https://example.com/timeout",
    ]
