from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

from app.config import BASE_DIR, Settings


PACKAGE_NAME = "official-letter-reference-extractor"
DEFAULT_RELEASE_METADATA_FILE = BASE_DIR / "config" / "release.json"


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    name: str
    channel: str
    release_date: str
    status: str
    note: str
    highlights: list[str]


def get_release_info(settings: Settings) -> ReleaseInfo:
    metadata_file = _load_release_file(settings.release_metadata_file)

    return ReleaseInfo(
        version=_first_value(
            settings.release_app_version,
            metadata_file.get("version"),
            _package_version(),
            "unknown",
        ),
        name=_first_value(settings.release_name, metadata_file.get("name"), "Development"),
        channel=_first_value(settings.release_channel, metadata_file.get("channel"), settings.app_env),
        release_date=_first_value(settings.release_date, metadata_file.get("release_date"), "unknown"),
        status=_first_value(settings.release_status, metadata_file.get("status"), "Development build"),
        note=_first_value(settings.release_note, metadata_file.get("note"), ""),
        highlights=_first_highlights(settings.release_highlights, metadata_file.get("highlights")),
    )


def _load_release_file(configured_path: str | None) -> dict[str, Any]:
    path = Path(configured_path) if configured_path else DEFAULT_RELEASE_METADATA_FILE
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    return data if isinstance(data, dict) else {}


def _package_version() -> str | None:
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return None


def _first_value(*values: object) -> str:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
        elif value is not None:
            return str(value)
    return ""


def _first_highlights(env_value: str | None, file_value: object) -> list[str]:
    env_highlights = _parse_highlights_env(env_value)
    if env_highlights:
        return env_highlights
    return _parse_highlights_file(file_value)


def _parse_highlights_env(value: str | None) -> list[str]:
    if not value or not value.strip():
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def _parse_highlights_file(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return _parse_highlights_env(value)
    return []
