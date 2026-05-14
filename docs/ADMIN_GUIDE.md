# OLRE Admin Guide

Current stable milestone/tag:

```text
v0.9.7-storage-integration
```

Architecture progression:

- `v0.9.5` runtime determinism
- `v0.9.6` storage identity and lifecycle foundation
- `v0.9.7` storage boundary integration

Detailed handoff:

- [v0.9.7 storage integration handoff](changelog10May2026_v097_storage_integration.md)

## Runtime Mode

Public mode:

```env
ENABLE_AUTH=false
```

When auth is disabled, `/login` and `/logout` are not mounted and MariaDB session integration is not used.

## Health Check

Open:

```text
/healthz
```

Example SQLite response:

```json
{"status":"ok","database_backend":"sqlite"}
```

Use this to confirm OLRE is using the intended database backend before uploading real documents.

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

Local development/testing profile defaults:

```env
INPUT_DIR=data/input
PROCESSED_DIR=data/processed
ERROR_DIR=data/error
QR_DEBUG_DIR=data/qr-debug
```

These directories contain runtime data and must not be committed.

Docker/production profile defaults:

```env
INPUT_DIR=/app/data/input
PROCESSED_DIR=/app/data/processed
ERROR_DIR=/app/data/error
QR_DEBUG_DIR=/app/data/qr-debug
STORAGE_ROOT=/app/data/storage
EXPORT_DIR=/app/data/exports
BACKUP_DIR=/app/data/backups
```

## Storage Boundary Rule

Operational rule:

- raw filesystem execution should live in `app/storage/*` or approved low-level adapters
- business/service/web layers should request artifact operations instead of manipulating filesystem paths directly

Current storage module layout:

- `app/storage/document_storage.py`
- `app/storage/debug_storage.py`
- `app/storage/export_storage.py`
- `app/storage/temp_storage.py`
- `app/storage/path_resolver.py`
- `app/storage/types.py`
- `app/storage/service.py` as the thin facade

Compatibility-first policy:

- write both
- read prefer `storage_key`
- fallback legacy path

Compatibility fields that should not be removed casually:

- `moved_to_path`
- `last_source_path`
- `source_file_path`

## Database

Default lightweight runtime database is SQLite:

```env
DATABASE_URL=sqlite:////app/data/olre.sqlite3
```

Local development/testing default:

```env
APP_ENV=development
DATABASE_URL=sqlite:///data/olre.sqlite3
```

Default runtime paths:

```env
INPUT_DIR=/app/data/input
PROCESSED_DIR=/app/data/processed
ERROR_DIR=/app/data/error
QR_DEBUG_DIR=/app/data/qr-debug
```

PostgreSQL remains a future profile note rather than a default runtime dependency:

```env
# DATABASE_URL=postgresql+psycopg://olre_user:change-me@127.0.0.1:5432/olre_db
```

Run migration:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Expected:

```text
repository head
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
QR_DEBUG_DIR=data/qr-debug
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

See [Backup and Restore Guide](BACKUP_RESTORE.md) for command examples.

Minimum backup set:

- SQLite database files or PostgreSQL database dump
- `data/input`
- `data/storage`
- `data/exports` when export artifacts are operationally important
- `data/qr-debug` if debug artifacts must be retained

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

Cleanup logging now also uses deterministic structured summaries for retained-source, debug, export, and temp cleanup paths.

## Accepted Low-Level Exceptions

The following remain intentionally accepted in v0.9.7:

- `app/batch/fingerprint.py`
- `app/batch/pdf_validation.py`
- `app/batch/reference_extraction.py`
- `app/services/inbox_paths.py`

Classification:

- low-level adapters for file-shaped library interaction
- compatibility wrapper for inbox path import stability

These are documented exceptions, not hidden business-layer filesystem coupling.

## Cleanup Model

Current retention cleanup model:

1. discover candidates
2. validate lifecycle safety
3. validate not-processing
4. validate reference safety
5. dry-run/report capability
6. execute deletion through storage layer
7. structured cleanup summary/log

Quarantine/trash behavior is intentionally deferred and is not part of v0.9.7.

## Operational Verification

Latest verified commands:

```bash
APP_ENV=testing uv run pytest
APP_ENV=development uv run ruff check app tests migrations
```

Latest results:

- `79 passed`
- `All checks passed`

## Next Recommended Phase

Suggested next phase:

```text
v0.9.8-observability-and-lifecycle-visibility
```

Suggested scope:

- lifecycle visibility
- storage metrics
- cleanup observability
- retry visibility
- failed document analytics
- retention status visibility
- soft orphan detection
- admin/runtime operational introspection

Explicit non-goals:

- object storage
- distributed storage
- Kubernetes
- microservices
- queue orchestration
- blob registry/reference counting unless future operational pain justifies it

## SQLite Runtime Notes

OLRE enables these SQLite pragmas through SQLAlchemy when `DATABASE_URL` uses SQLite:

```text
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

SQLite is suitable for single-user, small-office, or simple public container deployments. Use PostgreSQL for heavier concurrent writes, centralized operations, or existing managed database infrastructure.
