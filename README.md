# Official Letter Reference Extractor (OLRE)

OLRE is a FastAPI web application for importing official-letter PDFs, extracting references from text, QR codes, and optional OCR, resolving URLs, reviewing quality, and exporting results for reporting.

## v0.9.5 Runtime Direction

OLRE now targets a SQLite-first Docker runtime with zero external database setup:

- Default runtime database: `sqlite:////app/data/olre.sqlite3`
- Runtime paths: everything lives under `/app/data`
- Default web port: `8000`
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
-> filesystem data directories under /app/data
```

Runtime files are stored under `/app/data/input`, `/app/data/processed`, `/app/data/error`, and optionally `/app/data/debug/qr`. These directories are ignored by git and must not be committed.

## Quick Start with Docker

```powershell
docker build -t olre .
docker run --rm -p 8000:8000 -v olre_data:/app/data olre
```

Open:

```text
http://127.0.0.1:8000/imports
```

Or use Compose:

```powershell
docker compose up --build
```

## Quick Start on Windows

SQLite is the default runtime:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
copy .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

In `.env`, keep:

```env
DATABASE_URL=sqlite:////app/data/olre.sqlite3
```

Open:

```text
http://127.0.0.1:8000/imports
```

For OCR and pyzbar QR fallback:

```powershell
python -m pip install -e ".[dev,ocr,qr]"
```

Tesseract OCR and zbar are native Windows runtimes and still need separate installation. See the setup docs below.

## Important Environment Variables

- `DATABASE_URL=sqlite:////app/data/olre.sqlite3` uses the default SQLite runtime.
- `ENABLE_AUTH=false` runs the public non-OAuth version.
- `APP_TOKEN=` optionally protects `POST /batch/process` with `X-API-KEY`.
- `APP_LANG=th` sets the default UI language when no cookie exists.
- `INPUT_DIR=/app/data/input` stores pending PDFs.
- `PROCESSED_DIR=/app/data/processed` stores processed PDFs.
- `ERROR_DIR=/app/data/error` stores failed PDFs.
- `QR_DEBUG_EXPORT=false` enables or disables QR debug artifacts.
- `QR_FALLBACK_DECODER=none` keeps pyzbar fallback disabled by default.
- `OCR_ENABLED=false` keeps OCR disabled until Tesseract is installed.

## Run Tests and Lint

```powershell
python -m pytest
python -m ruff check app tests migrations
python -m alembic current
```

## Export Formats

OLRE supports:

- CSV: `/exports/csv`
- Markdown: `/exports/markdown`
- Excel: `/exports/excel`

Exports preserve filters passed from `/results`.

## Documentation

- [Windows installation](docs/INSTALL_WINDOWS.md)
- [SQLite runtime guide](docs/SQLITE_RUNTIME.md)
- [Thai user manual](docs/USER_MANUAL_TH.md)
- [Admin guide](docs/ADMIN_GUIDE.md)
- [Backup and restore](docs/BACKUP_RESTORE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
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

Confirm the active database backend with:

```text
http://127.0.0.1:8000/healthz
```

SQLite mode should return:

```json
{"status":"ok","database_backend":"sqlite"}
```
