from app.config import get_settings


def test_readyz_checks_database_and_runtime_paths(client):
    response = client.get("/readyz")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database_backend"] == "sqlite"
    assert payload["database_ping"] is True
    assert payload["details"] == {}
    assert payload["writable_paths"]["input_dir"] is True
    assert payload["writable_paths"]["processed_dir"] is True
    assert payload["writable_paths"]["error_dir"] is True
    assert payload["writable_paths"]["runtime_tmp_dir"] is True
    assert payload["writable_paths"]["failed_retained_dir"] is True
    assert payload["writable_paths"]["database_dir"] is True


def test_default_settings_match_docker_sqlite_runtime(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("INPUT_DIR", raising=False)
    monkeypatch.delenv("PROCESSED_DIR", raising=False)
    monkeypatch.delenv("ERROR_DIR", raising=False)
    monkeypatch.delenv("QR_DEBUG_DIR", raising=False)
    monkeypatch.delenv("RUNTIME_TMP_DIR", raising=False)
    monkeypatch.delenv("FAILED_RETAINED_DIR", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)

    settings = get_settings()

    assert settings.app_port == 8000
    assert settings.resolved_database_url == "sqlite:////app/data/olre.sqlite3"
    assert settings.input_path.as_posix() == "/app/data/input"
    assert settings.processed_path.as_posix() == "/app/data/processed"
    assert settings.error_path.as_posix() == "/app/data/error"
    assert settings.qr_debug_path.as_posix() == "/app/data/debug/qr"
    assert settings.runtime_tmp_path.as_posix() == "/app/data/runtime/tmp"
    assert settings.failed_retained_path.as_posix() == "/app/data/runtime/failed-retained"

    get_settings.cache_clear()
