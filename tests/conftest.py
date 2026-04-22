import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
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
    input_dir.mkdir()
    processed_dir.mkdir()
    error_dir.mkdir()

    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "olre_db")
    monkeypatch.setenv("POSTGRES_USER", "olre_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "olre_password")
    monkeypatch.setenv("MARIADB_HOST", "127.0.0.1")
    monkeypatch.setenv("MARIADB_PORT", "3306")
    monkeypatch.setenv("MARIADB_DB", "hr")
    monkeypatch.setenv("MARIADB_USER", "hr_user")
    monkeypatch.setenv("MARIADB_PASSWORD", "hr_password")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("SESSION_MAX_AGE_SECONDS", "28800")
    monkeypatch.setenv("INPUT_DIR", str(input_dir))
    monkeypatch.setenv("PROCESSED_DIR", str(processed_dir))
    monkeypatch.setenv("ERROR_DIR", str(error_dir))

    import app.config as config_module
    import app.main as main_module

    importlib.reload(config_module)
    importlib.reload(main_module)

    postgres_engine = create_sqlite_engine()
    mariadb_engine = create_sqlite_engine()

    Base.metadata.create_all(postgres_engine)
    with mariadb_engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE personnel (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    prefix TEXT NULL,
                    fname TEXT NULL,
                    lname TEXT NULL
                )
                """
            )
        )

    with TestClient(main_module.app) as test_client:
        test_client.app.state.postgres_engine.dispose()
        test_client.app.state.mariadb_engine.dispose()
        test_client.app.state.postgres_engine = postgres_engine
        test_client.app.state.mariadb_engine = mariadb_engine
        yield test_client

    postgres_engine.dispose()
    mariadb_engine.dispose()
