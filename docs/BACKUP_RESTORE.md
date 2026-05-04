# Backup and Restore Guide

OLRE stores data in the database and runtime directories. Back up both.

## What to Back Up

For SQLite:

```text
data/olre.sqlite3
data/olre.sqlite3-wal
data/olre.sqlite3-shm
data/input/
data/processed/
data/error/
data/debug/
```

For PostgreSQL:

```text
PostgreSQL database dump
data/input/
data/processed/
data/error/
data/debug/
```

## SQLite Backup

Preferred, if `sqlite3` CLI is installed:

```powershell
New-Item -ItemType Directory -Force backup
sqlite3 data\olre.sqlite3 ".backup 'backup\olre.sqlite3'"
```

File-copy fallback:

```powershell
New-Item -ItemType Directory -Force backup
Copy-Item data\olre.sqlite3 backup\
Copy-Item data\olre.sqlite3-wal backup\ -ErrorAction SilentlyContinue
Copy-Item data\olre.sqlite3-shm backup\ -ErrorAction SilentlyContinue
```

For a cleaner file-copy backup, stop the server before copying.

## SQLite Restore

Stop OLRE first.

```powershell
Copy-Item backup\olre.sqlite3 data\olre.sqlite3 -Force
Copy-Item backup\olre.sqlite3-wal data\olre.sqlite3-wal -Force -ErrorAction SilentlyContinue
Copy-Item backup\olre.sqlite3-shm data\olre.sqlite3-shm -Force -ErrorAction SilentlyContinue
python -m alembic current
```

Then start OLRE again.

## PostgreSQL Backup

```powershell
pg_dump -h <host> -U <user> -d <database> -F c -f backup\olre.backup
```

## PostgreSQL Restore

Stop OLRE first.

```powershell
pg_restore -h <host> -U <user> -d <database> --clean backup\olre.backup
python -m alembic current
```

## Retention Guidance

For small local use:

- Keep daily backups for 7 days.
- Keep weekly backups for 4 weeks.
- Keep monthly backups for 6-12 months if documents are important.

QR debug artifacts can grow quickly. Keep `QR_DEBUG_EXPORT=false` unless troubleshooting.
