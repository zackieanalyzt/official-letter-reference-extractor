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
    input_dir = tmp_path / "input"
    processed_dir = tmp_path / "processed"
    error_dir = tmp_path / "error"
    qr_debug_dir = tmp_path / "debug" / "qr"
    input_dir.mkdir()
    processed_dir.mkdir()
    error_dir.mkdir()

    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "olre_db")
    monkeypatch.setenv("POSTGRES_USER", "olre_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "olre_password")
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
