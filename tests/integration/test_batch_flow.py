from pathlib import Path

import fitz
from sqlalchemy import text

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
        SELECT original_file_name, file_size_bytes, processing_status, moved_to_path
        FROM documents
        """
    )
    assert document_row["original_file_name"] == "letter-002.pdf"
    assert document_row["file_size_bytes"] > 0
    assert document_row["processing_status"] == "processed"
    assert document_row["moved_to_path"] is not None


def test_duplicate_content_skip_does_not_create_new_processed_record(client):
    input_dir = Path(client.app.state.settings.input_dir)
    processed_dir = Path(client.app.state.settings.processed_dir)

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

    original_pdf_path = processed_dir / "letter-a.pdf"
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
    assert len(list(processed_dir.glob("letter-*.pdf"))) == 2


def test_same_filename_different_content_treated_as_new(client):
    input_dir = Path(client.app.state.settings.input_dir)
    processed_dir = Path(client.app.state.settings.processed_dir)

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
    assert len(list(processed_dir.glob("same*.pdf"))) == 2


def test_processed_file_moved_to_processed_dir(client):
    input_dir = Path(client.app.state.settings.input_dir)
    processed_dir = Path(client.app.state.settings.processed_dir)
    source_path = input_dir / "move-me.pdf"
    create_valid_pdf(source_path, "move to processed")

    run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="alice",
    )

    assert not source_path.exists()
    assert len(list(processed_dir.glob("move-me*.pdf"))) == 1


def test_fake_pdf_marked_failed_and_moved_to_error(client):
    input_dir = Path(client.app.state.settings.input_dir)
    error_dir = Path(client.app.state.settings.error_dir)
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
        SELECT processing_status, processing_error, moved_to_path
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
    assert document_row["processing_error"].startswith("PDF validation failed:")
    assert not source_path.exists()
    assert len(list(error_dir.glob("fake*.pdf"))) == 1
    assert log_row["step_name"] == "pdf_validation"
    assert log_row["message"].startswith("PDF validation failed:")


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
