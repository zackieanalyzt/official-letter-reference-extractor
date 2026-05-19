import json

from app.config import Settings
from app.release import get_release_info


RELEASE_ENV_VARS = [
    "OLRE_RELEASE_METADATA_FILE",
    "OLRE_APP_VERSION",
    "OLRE_RELEASE_NAME",
    "OLRE_RELEASE_DATE",
    "OLRE_RELEASE_CHANNEL",
    "OLRE_RELEASE_STATUS",
    "OLRE_RELEASE_NOTE",
    "OLRE_RELEASE_HIGHLIGHTS",
]


def clear_release_env(monkeypatch):
    for env_var in RELEASE_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


def test_release_metadata_default_is_deterministic(monkeypatch):
    clear_release_env(monkeypatch)
    settings = Settings(_env_file=None)

    release_info = get_release_info(settings)

    assert release_info.version
    assert release_info.name == "Development"
    assert release_info.channel == settings.app_env
    assert release_info.release_date == "unknown"
    assert release_info.status == "Development build"
    assert release_info.note == ""
    assert release_info.highlights == []


def test_release_metadata_reads_config_file_when_env_missing(monkeypatch, tmp_path):
    clear_release_env(monkeypatch)
    release_file = tmp_path / "release.json"
    release_file.write_text(
        json.dumps(
            {
                "version": "9.9.9",
                "name": "File Release",
                "channel": "pilot",
                "release_date": "2026-05-19",
                "status": "Ready",
                "note": "File note",
                "highlights": ["One", "Two"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OLRE_RELEASE_METADATA_FILE", str(release_file))
    settings = Settings(_env_file=None)

    release_info = get_release_info(settings)

    assert release_info.version == "9.9.9"
    assert release_info.name == "File Release"
    assert release_info.channel == "pilot"
    assert release_info.release_date == "2026-05-19"
    assert release_info.status == "Ready"
    assert release_info.note == "File note"
    assert release_info.highlights == ["One", "Two"]


def test_release_metadata_env_overrides_config_file(monkeypatch, tmp_path):
    clear_release_env(monkeypatch)
    release_file = tmp_path / "release.json"
    release_file.write_text(
        json.dumps(
            {
                "version": "file-version",
                "name": "File Release",
                "channel": "file-channel",
                "release_date": "2026-01-01",
                "status": "File status",
                "note": "File note",
                "highlights": ["File Highlight"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OLRE_RELEASE_METADATA_FILE", str(release_file))
    monkeypatch.setenv("OLRE_APP_VERSION", "env-version")
    monkeypatch.setenv("OLRE_RELEASE_NAME", "Env Release")
    monkeypatch.setenv("OLRE_RELEASE_DATE", "2026-05-19")
    monkeypatch.setenv("OLRE_RELEASE_CHANNEL", "env-channel")
    monkeypatch.setenv("OLRE_RELEASE_STATUS", "Env status")
    monkeypatch.setenv("OLRE_RELEASE_NOTE", "Env note")
    monkeypatch.setenv("OLRE_RELEASE_HIGHLIGHTS", "Env One| Env Two |")
    settings = Settings(_env_file=None)

    release_info = get_release_info(settings)

    assert release_info.version == "env-version"
    assert release_info.name == "Env Release"
    assert release_info.channel == "env-channel"
    assert release_info.release_date == "2026-05-19"
    assert release_info.status == "Env status"
    assert release_info.note == "Env note"
    assert release_info.highlights == ["Env One", "Env Two"]


def test_missing_release_metadata_file_does_not_break(monkeypatch, tmp_path):
    clear_release_env(monkeypatch)
    monkeypatch.setenv("OLRE_RELEASE_METADATA_FILE", str(tmp_path / "missing.json"))
    settings = Settings(_env_file=None)

    release_info = get_release_info(settings)

    assert release_info.name == "Development"
    assert release_info.status == "Development build"
