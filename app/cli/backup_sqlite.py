from __future__ import annotations

import argparse
from pathlib import Path

from app.config import get_settings
from app.db.sqlite_backup import backup_sqlite_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a WAL-safe OLRE SQLite backup using SQLite's backup API.")
    parser.add_argument("--output", dest="output", default=None, help="Optional destination path for the backup file.")
    args = parser.parse_args()

    settings = get_settings()
    destination = Path(args.output) if args.output else None
    result = backup_sqlite_database(settings, destination=destination)
    print(f"backup_created={result.backup_path}")
    print(f"source_database={result.source_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
