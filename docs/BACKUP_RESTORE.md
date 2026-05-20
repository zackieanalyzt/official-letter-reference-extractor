# Backup and Restore Guide

OLRE v0.9.7 continues the v0.9.6 SQLite backup model and clarifies it in the context of storage boundary integration. Backup remains SQLite-first, WAL-safe, and operationally conservative.

## Scope

This guide applies to the SQLite-first OLRE runtime.

Current preferred backup method:

```bash
python -m app.cli.backup_sqlite
```

Current preferred verification method:

```bash
python -m app.cli.verify_backup
```

Both commands assume the active runtime profile and `DATABASE_URL` already point to the correct SQLite database.

Runtime profile note:

- `development` / `testing` typically use `sqlite:///data/olre.sqlite3`
- `docker` / `production` typically use `sqlite:////app/data/olre.sqlite3`

## Why This Changed

OLRE runs SQLite in WAL mode. That means the live database state may be spread across:

- `.sqlite3`
- `-wal`
- `-shm`

Direct file copying while OLRE is running is operationally risky. v0.9.6 therefore uses the SQLite backup API for a consistent live backup.

## Backup Command

Default destination:

- `data/backups` in `development` / `testing`
- `/app/data/backups` in `docker` / `production`

Run:

```bash
python -m app.cli.backup_sqlite
```

Example output:

```text
backup_created=/app/data/backups/olre_20260510T010203Z.sqlite3
source_database=/app/data/olre.sqlite3
```

To choose an explicit path:

```bash
python -m app.cli.backup_sqlite --output data/backups/olre_manual.sqlite3
```

## Backup Verification

Verify the newest backup:

```bash
python -m app.cli.verify_backup
```

Verify a specific file:

```bash
python -m app.cli.verify_backup --backup-path data/backups/olre_manual.sqlite3
```

Verification checks:

- backup file exists
- `PRAGMA integrity_check`
- non-system table count

Expected result:

```text
integrity_check=ok
```

## Recommended Backup Set

### Required

- SQLite backup file created by `app.cli.backup_sqlite`
- storage root:
  - `data/storage` or `/app/data/storage`

### Optional but recommended

- exports directory when export artifacts are operationally important
- debug artifacts only when investigating QR extraction issues
- runtime configuration awareness so the correct profile-specific backup location is understood before restore

### Not recommended as primary backup mechanism

- copying live `.sqlite3`, `-wal`, `-shm` files directly while OLRE is running

## Restore Workflow

Stop OLRE first.

Restore by replacing the runtime database file with a verified backup copy, then validate:

```bash
python -m alembic current
python -m app.cli.verify_backup --backup-path data/backups/olre_manual.sqlite3
python -m uvicorn app.main:app --host 0.0.0.0 --port 7777
```

If the runtime database path is `data/olre.sqlite3`, place the verified backup file there before restart.

## Operational Verification

After restore:

1. Open `/healthz`
2. Open `/readyz`
3. Confirm expected document counts in the UI
4. Confirm storage root still contains the expected retained blobs
5. Confirm retained-source retry behavior still works when operationally important

## Storage Boundary Reminder

As of `release/v0.9.8-controlled-pilot`:

- raw filesystem execution should live in `app/storage/*` or approved low-level adapters
- storage identity is increasingly `storage_key`-first
- compatibility fallback for legacy path fields still exists and should be preserved during restore validation
- traversal planning metadata lives in the database; linked-document downloader artifacts are not yet produced in the current planning-only runtime

Compatibility-first policy remains:

- write both
- read prefer `storage_key`
- fallback legacy path

Fields still intentionally retained for compatibility:

- `moved_to_path`
- `last_source_path`
- `source_file_path`

## Retention Guidance

Suggested baseline:

- daily backups for 7 days
- weekly backups for 4 weeks
- monthly backups for 6-12 months when documents are operationally important

Backup retention should be managed separately from OLRE runtime artifact retention.

## Cleanup Safety Note

Retention cleanup and backup retention are different concerns.

Current OLRE cleanup model is:

1. discover candidates
2. validate lifecycle safety
3. validate not-processing
4. validate reference safety
5. dry-run/report capability
6. execute deletion through storage layer
7. structured cleanup summary/log

Quarantine/trash behavior is intentionally deferred after `v0.9.7`.
