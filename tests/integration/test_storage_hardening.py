import sqlite3
from os import utime
from pathlib import Path

from sqlalchemy import text

from app.batch.file_ops import ensure_directory
from app.config import Settings
from app.db.base import Base
from app.db.models import BatchRun, Document
from app.db.sqlite_backup import backup_sqlite_database, verify_sqlite_backup
from app.db.engine import create_database_engine, create_session_factory
from app.services.process_batch import run_batch_registration
from app.services.retention_service import cleanup_expired_exports, run_retention_cleanup
from app.storage import build_storage_key, get_storage_service, normalize_filename, truncate_safe_filename


def _build_isolated_settings(monkeypatch, tmp_path) -> Settings:
    for env_var in (
        "APP_ENV",
        "ENVIRONMENT",
        "DATABASE_URL",
        "INPUT_DIR",
        "PROCESSED_DIR",
        "ERROR_DIR",
        "QR_DEBUG_DIR",
        "RUNTIME_TMP_DIR",
        "FAILED_RETAINED_DIR",
        "STORAGE_ROOT",
        "EXPORT_DIR",
        "BACKUP_DIR",
    ):
        monkeypatch.delenv(env_var, raising=False)

    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'olre.sqlite3').as_posix()}")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("EXPORT_DIR", str(tmp_path / "exports"))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("QR_DEBUG_DIR", str(tmp_path / "qr-debug"))
    monkeypatch.setenv("RUNTIME_TMP_DIR", str(tmp_path / "runtime" / "tmp"))
    monkeypatch.setenv("FAILED_RETAINED_DIR", str(tmp_path / "runtime" / "failed-retained"))
    return Settings(_env_file=None)


def _create_fake_pdf(path: Path) -> None:
    path.write_bytes(b"not-a-real-pdf")


def test_storage_key_generation_uses_sha256_fanout():
    sha256 = "abcdef1234567890" * 4

    storage_key = build_storage_key(sha256, suffix=".pdf")

    assert storage_key == f"sha256/ab/cd/{sha256}.pdf"


def test_filename_normalization_handles_long_thai_names():
    original_name = ("ขอความอนุเคราะห์ประชาสัมพันธ์ศูนย์พัฒนาการเมืองภาคพลเมือง" * 4) + ".pdf"

    normalized = normalize_filename("  " + original_name + "  ")
    truncated = truncate_safe_filename(original_name, max_bytes=96)

    assert normalized.endswith(".pdf")
    assert "  " not in normalized
    assert len(truncated.encode("utf-8")) <= 96
    assert truncated.endswith(".pdf")


def test_storage_service_deduplicates_duplicate_content_with_different_filenames(monkeypatch, tmp_path):
    settings = _build_isolated_settings(monkeypatch, tmp_path)
    storage = get_storage_service(settings)
    source_a = tmp_path / "หนังสือเวียนยาวมาก.pdf"
    source_b = tmp_path / "duplicate-name.pdf"
    payload = b"same-pdf-content"
    source_a.write_bytes(payload)
    source_b.write_bytes(payload)
    sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    first = storage.save_document(source_a, original_filename=source_a.name, sha256=sha256, mime_type="application/pdf")
    second = storage.save_document(source_b, original_filename=source_b.name, sha256=sha256, mime_type="application/pdf")

    assert first.storage_key == second.storage_key
    assert first.absolute_path == second.absolute_path
    assert first.created is True
    assert second.created is False
    assert first.absolute_path.read_bytes() == payload


def test_export_retention_cleanup_removes_expired_exports(monkeypatch, tmp_path):
    settings = _build_isolated_settings(monkeypatch, tmp_path)
    storage = get_storage_service(settings)
    artifact = storage.create_export(suggested_name="รายงานผลลัพธ์", content=b"demo", suffix=".txt")
    stale_timestamp = 946684800

    artifact.absolute_path.touch()
    artifact.absolute_path.chmod(0o644)
    utime(artifact.absolute_path, (stale_timestamp, stale_timestamp))

    summary = cleanup_expired_exports(settings, dry_run=False)

    assert summary["exports_deleted"] == 1
    assert not artifact.absolute_path.exists()


def test_sqlite_backup_and_verify_round_trip(monkeypatch, tmp_path):
    settings = _build_isolated_settings(monkeypatch, tmp_path)
    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        batch = BatchRun(triggered_by="backup-test", status="completed")
        session.add(batch)
        session.flush()
        session.add(
            Document(
                batch_run_id=batch.id,
                original_file_name="backup.pdf",
                content_hash="hash-backup",
                sha256="hash-backup",
                file_size_bytes=12,
                processing_status="processed",
                lifecycle_state="processed",
            )
        )
        session.commit()

    result = backup_sqlite_database(settings)
    verification = verify_sqlite_backup(result.backup_path)

    assert result.backup_path.exists()
    assert verification["integrity_check"] == "ok"
    with sqlite3.connect(result.backup_path) as connection:
        document_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    assert document_count == 1
    engine.dispose()


def test_failed_document_retention_uses_content_addressable_storage_and_cleanup(client):
    input_dir = ensure_directory(Path(client.app.state.settings.input_dir))
    storage_root = Path(client.app.state.settings.storage_root)
    source_path = input_dir / "เอกสารปลอมยาวมากมากมาก.pdf"
    _create_fake_pdf(source_path)

    summary = run_batch_registration(
        client.app.state.settings,
        client.app.state.postgres_engine,
        triggered_by="storage-hardening-test",
    )

    assert summary.failed_files == 1
    with client.app.state.postgres_engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, storage_key, moved_to_path, lifecycle_state
                FROM documents
                ORDER BY id DESC
                LIMIT 1
                """
            )
        ).mappings().one()
        assert row["storage_key"].startswith("sha256/")
        retained_path = storage_root / row["storage_key"]
        assert retained_path.exists()
        assert row["moved_to_path"] == str(retained_path)
        assert row["lifecycle_state"] == "retained"
        connection.execute(
            text("UPDATE document_ingestions SET cleanup_due_at = '2000-01-01 00:00:00' WHERE document_id = :document_id"),
            {"document_id": row["id"]},
        )

    session = create_session_factory(client.app.state.postgres_engine)()
    try:
        dry_run_summary = run_retention_cleanup(session, client.app.state.settings, dry_run=True)
    finally:
        session.close()
    assert dry_run_summary["failed_sources_deleted"] == 1
    assert retained_path.exists()

    session = create_session_factory(client.app.state.postgres_engine)()
    try:
        cleanup_summary = run_retention_cleanup(session, client.app.state.settings, dry_run=False)
        session.commit()
    finally:
        session.close()

    assert cleanup_summary["failed_sources_deleted"] == 1
    assert not retained_path.exists()
    with client.app.state.postgres_engine.begin() as connection:
        lifecycle_state = connection.execute(
            text("SELECT lifecycle_state FROM documents ORDER BY id DESC LIMIT 1")
        ).scalar_one()
    assert lifecycle_state == "deleted"
