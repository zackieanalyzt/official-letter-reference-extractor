# OLRE Admin Guide

## Runtime Mode

Public mode:

```env
ENABLE_AUTH=false
```

When auth is disabled, `/login` and `/logout` are not mounted and MariaDB session integration is not used.

## APP_TOKEN

`APP_TOKEN` optionally protects `POST /batch/process`.

```env
APP_TOKEN=change-me
```

Clients must send:

```text
X-API-KEY: change-me
```

Leave `APP_TOKEN=` empty for unguarded local/public lightweight use.

## Language

```env
APP_LANG=th
```

Language resolution order:

1. cookie `lang`
2. `APP_LANG`

Supported values are `th` and `en`.

## Data Directories

```env
INPUT_DIR=data/input
PROCESSED_DIR=data/processed
ERROR_DIR=data/error
QR_DEBUG_DIR=data/debug/qr
```

These directories contain runtime data and must not be committed.

## Database

Default lightweight runtime database is SQLite:

```env
DATABASE_URL=sqlite:///data/olre.sqlite3
```

PostgreSQL remains supported:

```env
DATABASE_URL=postgresql+psycopg://olre_user:change-me@127.0.0.1:5432/olre_db
```

Legacy PostgreSQL variables are still supported when `DATABASE_URL` is not set:

```env
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=olre_db
POSTGRES_USER=olre_user
POSTGRES_PASSWORD=change-me
```

Run migration:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Expected baseline head:

```text
20260503_0007
```

## OCR Config

```env
OCR_ENABLED=false
OCR_ENGINE=tesseract
OCR_LANG=tha+eng
OCR_TIMEOUT_SECONDS=30
OCR_MIN_TEXT_CHARS=25
OCR_DPI_SCALE=3
OCR_PAGE_SEGMENTATION_MODE=6
```

Keep `OCR_ENABLED=false` until Tesseract OCR is installed and `tesseract --version` works.

If OCR runtime is missing, OLRE should not crash. It records an OCR error such as `OCR_NOT_AVAILABLE` and continues batch processing.

## QR Debug Config

```env
QR_DEBUG_EXPORT=false
QR_DEBUG_DIR=data/debug/qr
```

Enable only during troubleshooting because debug image files can grow quickly.

## QR Fallback Config

```env
QR_FALLBACK_DECODER=none
```

Supported values:

- `none`
- `pyzbar`

`pyzbar` is optional and requires both the Python package and zbar native runtime.

## Backup Guidance

Minimum backup set:

- SQLite database files or PostgreSQL database dump
- `data/input`
- `data/processed`
- `data/error`
- `data/debug/qr` if debug artifacts must be retained

SQLite backup files:

```text
data/olre.sqlite3
data/olre.sqlite3-wal
data/olre.sqlite3-shm
```

If `sqlite3` CLI is available, prefer:

```powershell
sqlite3 data\olre.sqlite3 ".backup 'backup\olre.sqlite3'"
```

Suggested PostgreSQL backup:

```powershell
pg_dump -h <host> -U <user> -d <db> -F c -f olre.backup
```

Suggested restore:

```powershell
pg_restore -h <host> -U <user> -d <db> --clean olre.backup
```

## Logging

Current logs include request path, batch events, document IDs, extraction steps, OCR failures, QR fallback events, and URL resolution results. For production, consider adding structured JSON logs with request ID, batch run ID, document ID, and duration.

## SQLite Runtime Notes

OLRE enables these SQLite pragmas through SQLAlchemy when `DATABASE_URL` uses SQLite:

```text
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

SQLite is suitable for single-user, small-office, or simple public container deployments. Use PostgreSQL for heavier concurrent writes, centralized operations, or existing managed database infrastructure.
