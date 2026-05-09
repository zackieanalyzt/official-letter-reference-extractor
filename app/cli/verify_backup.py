from __future__ import annotations

import argparse
from pathlib import Path

from app.config import get_settings
from app.db.sqlite_backup import verify_sqlite_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify an OLRE SQLite backup using integrity_check.")
    parser.add_argument("--backup-path", required=False, help="Path to the backup file. Defaults to the newest backup.")
    args = parser.parse_args()

    settings = get_settings()
    if args.backup_path:
        backup_path = Path(args.backup_path)
    else:
        backup_candidates = sorted(settings.backup_path.glob("*.sqlite3"))
        if not backup_candidates:
            raise FileNotFoundError(f"No backup files found in {settings.backup_path}")
        backup_path = backup_candidates[-1]

    result = verify_sqlite_backup(backup_path)
    print(f"backup_path={result['backup_path']}")
    print(f"integrity_check={result['integrity_check']}")
    print(f"table_count={result['table_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
