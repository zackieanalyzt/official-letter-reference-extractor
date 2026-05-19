import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db import models  # noqa: F401


def create_sqlite_engine():
    return create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    database_path = tmp_path / "olre.sqlite3"
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    error_dir = tmp_path / "error"
    runtime_tmp_dir = tmp_path / "runtime" / "tmp"
    failed_retained_dir = tmp_path / "runtime" / "failed-retained"
    storage_root = tmp_path / "storage"
    export_dir = tmp_path / "exports"
    backup_dir = tmp_path / "backups"
    traversal_storage_dir = tmp_path / "runtime" / "linked-documents"
    qr_debug_dir = tmp_path / "debug" / "qr"
    input_dir.mkdir()
    processed_dir.mkdir()
    error_dir.mkdir()
    runtime_tmp_dir.mkdir(parents=True)
    failed_retained_dir.mkdir(parents=True)
    storage_root.mkdir(parents=True)
    export_dir.mkdir(parents=True)
    backup_dir.mkdir(parents=True)
    traversal_storage_dir.mkdir(parents=True)

    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("ENABLE_AUTH", "false")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "28800")
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("PROCESSED_DIR", str(processed_dir))
    monkeypatch.setenv("ERROR_DIR", str(error_dir))
    monkeypatch.setenv("OCR_ENABLED", "true")
    monkeypatch.setenv("OCR_ENGINE", "tesseract")
    monkeypatch.setenv("OCR_LANG", "eng")
    monkeypatch.setenv("OCR_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("OCR_MIN_TEXT_CHARS", "20")
    monkeypatch.setenv("OCR_DPI_SCALE", "3")
    monkeypatch.setenv("OCR_PAGE_SEGMENTATION_MODE", "6")
    monkeypatch.setenv("QR_DEBUG_EXPORT", "false")
    monkeypatch.setenv("QR_DEBUG_DIR", str(qr_debug_dir))
    monkeypatch.setenv("QR_FALLBACK_DECODER", "none")
    monkeypatch.setenv("URL_RESOLVE_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("URL_RESOLVE_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("URL_RESOLVE_USER_AGENT", "OLRE Test")
    monkeypatch.setenv("STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("EXPORT_DIR", str(export_dir))
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("FILE_RETENTION_MODE", "retain_failed_only")
    monkeypatch.setenv("SUCCESS_SOURCE_RETENTION_HOURS", "0")
    monkeypatch.setenv("FAILED_SOURCE_RETENTION_HOURS", "720")
    monkeypatch.setenv("SOURCE_DELETE_ON_CACHE_REUSE", "true")
    monkeypatch.setenv("QR_DEBUG_RETENTION_HOURS", "168")
    monkeypatch.setenv("EXPORT_RETENTION_HOURS", "336")
    monkeypatch.setenv("CLEANUP_ENABLED", "false")
    monkeypatch.setenv("CLEANUP_INTERVAL_MINUTES", "60")
    monkeypatch.setenv("CLEANUP_STARTUP_SWEEP", "false")
    monkeypatch.setenv("DEFAULT_FORCE_REPROCESS", "false")
    monkeypatch.setenv("EXTRACTION_VERSION", "1")
    monkeypatch.setenv("TEMP_FILE_MAX_AGE_HOURS", "24")
    monkeypatch.setenv("RUNTIME_TMP_DIR", str(runtime_tmp_dir))
    monkeypatch.setenv("FAILED_RETAINED_DIR", str(failed_retained_dir))
    monkeypatch.setenv("TRAVERSAL_ENABLED", "false")
    monkeypatch.setenv("TRAVERSAL_MAX_DEPTH", "1")
    monkeypatch.setenv("TRAVERSAL_MAX_DOCUMENTS_PER_BATCH", "20")
    monkeypatch.setenv("TRAVERSAL_ALLOWED_CONTENT_TYPES", "application/pdf")
    monkeypatch.setenv("TRAVERSAL_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("TRAVERSAL_MAX_DOWNLOAD_MB", "20")
    monkeypatch.setenv("TRAVERSAL_ALLOWED_DOMAINS", "")
    monkeypatch.setenv("TRAVERSAL_BLOCK_PRIVATE_IPS", "true")
    monkeypatch.setenv("TRAVERSAL_STORAGE_DIR", str(traversal_storage_dir))

    import app.config as config_module
    import app.main as main_module

    importlib.reload(config_module)
    importlib.reload(main_module)

    postgres_engine = create_sqlite_engine()
    Base.metadata.create_all(postgres_engine)

    with TestClient(main_module.app) as test_client:
        test_client.app.state.database_engine.dispose()
        test_client.app.state.database_engine = postgres_engine
        test_client.app.state.postgres_engine = postgres_engine
        test_client.app.state.database_backend = "sqlite"
        yield test_client

    postgres_engine.dispose()
