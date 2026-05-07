from __future__ import annotations

import argparse
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.engine import Engine, make_url

from app.config import Settings, get_settings, resolve_path
from app.db.engine import ping_database
from app.logging_config import get_logger


logger = get_logger(__name__)


@dataclass
class ReadinessReport:
    ok: bool
    database_backend: str
    database_ping: bool
    writable_paths: dict[str, bool]
    details: dict[str, str]


def _check_writable_directory(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path, prefix=".olre-write-check-", delete=True) as handle:
        handle.write(b"ok")
        handle.flush()
        os.fsync(handle.fileno())
    return True


def get_runtime_paths(settings: Settings) -> dict[str, Path]:
    return {
        "input_dir": settings.input_path,
        "processed_dir": settings.processed_path,
        "error_dir": settings.error_path,
        "qr_debug_dir": settings.qr_debug_path,
        "runtime_tmp_dir": settings.runtime_tmp_path,
        "failed_retained_dir": settings.failed_retained_path,
    }


def get_database_storage_path(settings: Settings) -> Path | None:
    database_url = settings.resolved_database_url
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in (None, "", ":memory:"):
        return None

    path = Path(url.database)
    if path.is_absolute():
        return path
    return resolve_path(str(path))


def validate_runtime_paths(settings: Settings) -> dict[str, str]:
    validated: dict[str, str] = {}

    for name, path in get_runtime_paths(settings).items():
        _check_writable_directory(path)
        validated[name] = str(path.resolve())

    database_path = get_database_storage_path(settings)
    if database_path is not None:
        _check_writable_directory(database_path.parent)
        validated["database_dir"] = str(database_path.parent.resolve())
        validated["database_file"] = str(database_path.resolve())

    return validated


def build_readiness_report(settings: Settings, engine: Engine) -> ReadinessReport:
    writable_paths: dict[str, bool] = {}
    details: dict[str, str] = {}

    try:
        ping_database(engine)
        database_ping = True
    except Exception as exc:  # pragma: no cover - covered by route behavior
        database_ping = False
        details["database"] = str(exc)

    for name, path in get_runtime_paths(settings).items():
        try:
            _check_writable_directory(path)
            writable_paths[name] = True
        except Exception as exc:  # pragma: no cover - covered by route behavior
            writable_paths[name] = False
            details[name] = str(exc)

    database_path = get_database_storage_path(settings)
    if database_path is not None:
        try:
            _check_writable_directory(database_path.parent)
            writable_paths["database_dir"] = True
        except Exception as exc:  # pragma: no cover - covered by route behavior
            writable_paths["database_dir"] = False
            details["database_dir"] = str(exc)

    ok = database_ping and all(writable_paths.values())
    return ReadinessReport(
        ok=ok,
        database_backend=make_url(settings.resolved_database_url).get_backend_name(),
        database_ping=database_ping,
        writable_paths=writable_paths,
        details=details,
    )


def validate_startup(settings: Settings | None = None) -> dict[str, str]:
    current_settings = settings or get_settings()
    validated_paths = validate_runtime_paths(current_settings)
    logger.info("[RUNTIME_VALIDATED] paths=%s", validated_paths)
    return validated_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OLRE runtime directories and database path.")
    parser.add_argument("command", nargs="?", default="validate")
    args = parser.parse_args()
    if args.command != "validate":
        parser.error(f"Unsupported command: {args.command}")

    validate_startup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
