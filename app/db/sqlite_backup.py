from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.batch.file_ops import ensure_directory
from app.runtime import get_database_storage_path


@dataclass(frozen=True)
class BackupResult:
    source_path: Path
    backup_path: Path


def backup_sqlite_database(settings, *, destination: Path | None = None) -> BackupResult:
    source_path = get_database_storage_path(settings)
    if source_path is None:
        raise ValueError("SQLite backup is only supported when DATABASE_URL uses a file-based SQLite database.")

    backup_root = ensure_directory(settings.backup_path)
    target_path = destination or backup_root / f"olre_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.sqlite3"
    ensure_directory(target_path.parent)

    with sqlite3.connect(source_path) as source_connection:
        with sqlite3.connect(target_path) as target_connection:
            source_connection.backup(target_connection)
    return BackupResult(source_path=source_path, backup_path=target_path)


def verify_sqlite_backup(backup_path: Path) -> dict[str, str | int]:
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    with sqlite3.connect(backup_path) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        table_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
    return {
        "backup_path": str(backup_path),
        "integrity_check": str(integrity),
        "table_count": int(table_count),
    }
