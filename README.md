# Official Letter Reference Extractor (OLRE)

OLRE is a FastAPI web application for importing official-letter PDFs, extracting references from text, QR codes, and optional OCR, resolving URLs, reviewing quality, and exporting results for reporting.

## Current Stable Milestone

Current stable milestone/tag:

```text
v0.9.7-storage-integration
```

Architecture progression to date:

- `v0.9.5` runtime determinism
- `v0.9.6` storage identity and lifecycle foundation
- `v0.9.7` storage boundary integration

Detailed phase handoff:

- [v0.9.7 storage integration handoff](docs/changelog10May2026_v097_storage_integration.md)

## Runtime Direction

OLRE now targets a SQLite-first Docker runtime with zero external database setup:

- Default runtime database: `sqlite:////app/data/olre.sqlite3`
- Docker runtime paths: everything lives under `/app/data`
- Local development profile defaults: repo-local `data/...`
- Default Docker web port: `8000`
- Default local development web port: `7777`
- Container startup: validate paths, run Alembic migrations, start app
- `/healthz`: lightweight process health
- `/readyz`: database ping plus writable runtime path checks

PostgreSQL and MariaDB remain future profile notes only. They are not required for the default runtime.

## Current Features

- Public non-OAuth mode with optional `APP_TOKEN` guard for batch processing.
- PDF import inbox and batch processing.
- Text, QR, and optional OCR reference extraction.
- URL resolution with structured resolution errors.
- Results search and filtering.
- CSV, Markdown, and Excel export.
- Dashboard KPI, domain analytics, daily trend, and error analytics.
- Quality report for zero-reference, failed, duplicate, OCR, and broken-link cases.
- QR debug artifact export and debug UI.
- Retry failed documents.
- Thai UI with Thai-English language switcher.

## Architecture

```text
FastAPI routes
-> service layer
-> SQLAlchemy models
-> SQLite database
-> storage facade
-> storage modules / approved low-level adapters
```

Storage boundary rule:

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

Compatibility fields intentionally retained:

- `moved_to_path`
- `last_source_path`
- `source_file_path`

## Quick Start with Docker

```powershell
docker compose build
docker compose up --build
```

Open:

```text
http://127.0.0.1:8000
```

Verify health:

```powershell
curl http://localhost:8000/healthz
```

Expected:

```json
{"status":"ok","database_backend":"sqlite"}
```

The Docker runtime is intentionally SQLite-first, single-container, and public-mode by default:

- `ENABLE_AUTH=false`
- `APP_LANG=th`
- `DATABASE_URL=sqlite:////app/data/olre.sqlite3`
- Named Docker volume `olre_data` mounted at `/app/data`

Full guide:

- [Docker SQLite runtime guide](docs/DOCKER_SQLITE_RUNTIME.md)

## Quick Start on Windows venv

SQLite is the default runtime:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
copy .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 7777
```

In `.env`, keep:

```env
APP_ENV=development
DATABASE_URL=sqlite:///data/olre.sqlite3
```

Open:

```text
http://127.0.0.1:7777/imports
```

For OCR and pyzbar QR fallback:

```powershell
python -m pip install -e ".[dev,ocr,qr]"
```

Tesseract OCR and zbar are native Windows runtimes and still need separate installation. See the setup docs below.

## Important Environment Variables

- `APP_ENV=development` uses repo-local `data/...` defaults.
- `APP_ENV=docker` uses `/app/data/...` defaults.
- `DATABASE_URL=sqlite:////app/data/olre.sqlite3` is the default Docker SQLite runtime.
- `DATABASE_URL=sqlite:///data/olre.sqlite3` is the default local development/testing SQLite runtime.
- `ENABLE_AUTH=false` runs the public non-OAuth version.
- `APP_TOKEN=` optionally protects `POST /batch/process` with `X-API-KEY`.
- `APP_LANG=th` sets the default UI language when no cookie exists.
- `APP_PORT=8000` is the Docker Compose default for this repository.
- `INPUT_DIR=/app/data/input` stores pending PDFs.
- `PROCESSED_DIR=/app/data/processed` stores processed PDFs.
- `ERROR_DIR=/app/data/error` stores failed PDFs.
- `QR_DEBUG_EXPORT=false` enables or disables QR debug artifacts.
- `QR_FALLBACK_DECODER=none` keeps pyzbar fallback disabled by default.
- `OCR_ENABLED=false` keeps OCR disabled until Tesseract is installed.

## Run Tests and Lint

```powershell
APP_ENV=testing uv run pytest
APP_ENV=development uv run ruff check app tests migrations
python -m alembic current
```

Latest verification status:

- `APP_ENV=testing uv run pytest` -> `79 passed`
- `APP_ENV=development uv run ruff check app tests migrations` -> `All checks passed`

## Export Formats

OLRE supports:

- CSV: `/exports/csv`
- Markdown: `/exports/markdown`
- Excel: `/exports/excel`

Exports preserve filters passed from `/results`.

## Documentation

- [Docker SQLite runtime guide](docs/DOCKER_SQLITE_RUNTIME.md)
- [Windows installation](docs/INSTALL_WINDOWS.md)
- [SQLite runtime guide](docs/SQLITE_RUNTIME.md)
- [Thai user manual](docs/USER_MANUAL_TH.md)
- [Admin guide](docs/ADMIN_GUIDE.md)
- [Backup and restore](docs/BACKUP_RESTORE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [v0.9.7 storage integration handoff](docs/changelog10May2026_v097_storage_integration.md)
- [Tesseract OCR setup](docs/TESSERACT_WINDOWS_SETUP.md)
- [pyzbar/zbar setup](docs/PYZBAR_ZBAR_WINDOWS_SETUP.md)
- [v0.9.3 browser QA checklist](docs/QA_BROWSER_CHECKLIST_v0.9.3.md)
- [v0.9.4 SQLite runtime QA](docs/QA_SQLITE_RUNTIME_v0.9.4.md)
- [v0.9.4 release notes](docs/RELEASE_NOTES_v0.9.4.md)

## Database Note

The default runtime is SQLite only. PostgreSQL and MariaDB are future profile notes, not default runtime requirements.

SQLite backup should include the database file and any WAL sidecars:

```text
/app/data/olre.sqlite3
/app/data/olre.sqlite3-wal
/app/data/olre.sqlite3-shm
```

Confirm the active database backend with Docker:

```text
http://127.0.0.1:8000/healthz
```

SQLite mode should return:

```json
{"status":"ok","database_backend":"sqlite"}
```
