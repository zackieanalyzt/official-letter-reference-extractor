# Backup and Restore Guide

OLRE v0.9.6 introduces executable SQLite backup utilities and moves the recommended backup workflow away from unsafe raw file-copy procedures.

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

## Retention Guidance

Suggested baseline:

- daily backups for 7 days
- weekly backups for 4 weeks
- monthly backups for 6-12 months when documents are operationally important

Backup retention should be managed separately from OLRE runtime artifact retention.
