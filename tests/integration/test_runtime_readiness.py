from pathlib import Path

import pytest

from app.config import BASE_DIR, Settings


PROFILE_CONTROLLED_ENV_VARS = (
    "APP_ENV",
    "ENVIRONMENT",
    "APP_PORT",
    "DATABASE_URL",
    "POSTGRES_DSN",
    "INPUT_DIR",
    "PROCESSED_DIR",
    "ERROR_DIR",
    "QR_DEBUG_DIR",
    "RUNTIME_TMP_DIR",
    "FAILED_RETAINED_DIR",
)


def clear_profile_env(monkeypatch) -> None:
    for env_var in PROFILE_CONTROLLED_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


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


@pytest.mark.parametrize("profile_name", ["development", "testing"])
def test_local_profiles_resolve_local_data_paths(monkeypatch, profile_name):
    clear_profile_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", profile_name)

    settings = Settings(_env_file=None)

    assert settings.app_env == profile_name
    assert settings.app_port == 7777
    assert settings.resolved_database_url == "sqlite:///data/olre.sqlite3"
    assert settings.input_path == (BASE_DIR / "data" / "input").resolve()
    assert settings.processed_path == (BASE_DIR / "data" / "processed").resolve()
    assert settings.error_path == (BASE_DIR / "data" / "error").resolve()
    assert settings.qr_debug_path == (BASE_DIR / "data" / "qr-debug").resolve()
    assert settings.runtime_tmp_path == (BASE_DIR / "data" / "runtime" / "tmp").resolve()
    assert settings.failed_retained_path == (BASE_DIR / "data" / "runtime" / "failed-retained").resolve()


def test_docker_profile_resolves_app_data_paths(monkeypatch):
    clear_profile_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "docker")

    settings = Settings(_env_file=None)

    assert settings.app_env == "docker"
    assert settings.app_port == 8000
    assert settings.resolved_database_url == "sqlite:////app/data/olre.sqlite3"
    assert settings.input_path == Path("/app/data/input")
    assert settings.processed_path == Path("/app/data/processed")
    assert settings.error_path == Path("/app/data/error")
    assert settings.qr_debug_path == Path("/app/data/qr-debug")
    assert settings.runtime_tmp_path == Path("/app/data/runtime/tmp")
    assert settings.failed_retained_path == Path("/app/data/runtime/failed-retained")


def test_explicit_env_vars_override_profile_defaults(monkeypatch):
    clear_profile_env(monkeypatch)
    monkeypatch.setenv("APP_ENV", "docker")
    monkeypatch.setenv("APP_PORT", "9911")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///custom/olre.sqlite3")
    monkeypatch.setenv("INPUT_DIR", "custom/input")
    monkeypatch.setenv("PROCESSED_DIR", "custom/processed")
    monkeypatch.setenv("ERROR_DIR", "custom/error")
    monkeypatch.setenv("QR_DEBUG_DIR", "custom/qr-debug")
    monkeypatch.setenv("RUNTIME_TMP_DIR", "custom/runtime/tmp")
    monkeypatch.setenv("FAILED_RETAINED_DIR", "custom/runtime/failed-retained")

    settings = Settings(_env_file=None)

    assert settings.app_env == "docker"
    assert settings.app_port == 9911
    assert settings.resolved_database_url == "sqlite:///custom/olre.sqlite3"
    assert settings.input_path == (BASE_DIR / "custom" / "input").resolve()
    assert settings.processed_path == (BASE_DIR / "custom" / "processed").resolve()
    assert settings.error_path == (BASE_DIR / "custom" / "error").resolve()
    assert settings.qr_debug_path == (BASE_DIR / "custom" / "qr-debug").resolve()
    assert settings.runtime_tmp_path == (BASE_DIR / "custom" / "runtime" / "tmp").resolve()
    assert settings.failed_retained_path == (BASE_DIR / "custom" / "runtime" / "failed-retained").resolve()


def test_default_settings_do_not_read_local_env_file(monkeypatch, tmp_path):
    clear_profile_env(monkeypatch)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "APP_ENV=docker",
                "APP_PORT=9555",
                "DATABASE_URL=sqlite:////tmp/polluted.sqlite3",
                "INPUT_DIR=/tmp/polluted/input",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.app_port == 7777
    assert settings.resolved_database_url == "sqlite:///data/olre.sqlite3"
    assert settings.input_path == (BASE_DIR / "data" / "input").resolve()
