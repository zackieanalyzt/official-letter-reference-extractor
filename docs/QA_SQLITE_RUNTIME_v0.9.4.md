# OLRE v0.9.4 SQLite Runtime QA

Date: 2026-05-04

Status legend:

- `[ ]` Not tested
- `[x]` Passed
- `[!]` Issue found
- `[-]` Skipped or not available

## Test Configuration

```env
DATABASE_URL=sqlite:///data/olre.sqlite3
ENABLE_AUTH=false
OCR_ENABLED=false
QR_DEBUG_EXPORT=true
QR_DEBUG_DIR=data/debug/qr
```

## SQLite Migration

- [x] Remove old SQLite files before migration:

```powershell
Remove-Item data\olre.sqlite3,data\olre.sqlite3-wal,data\olre.sqlite3-shm -ErrorAction SilentlyContinue
```

- [x] Run migration:

```powershell
$env:DATABASE_URL="sqlite:///data/olre.sqlite3"
python -m alembic upgrade head
python -m alembic current
```

Expected:

```text
20260503_0007 (head)
```

## Runtime Smoke

- [x] Start app with SQLite:

```powershell
$env:DATABASE_URL="sqlite:///data/olre.sqlite3"
python -m uvicorn app.main:app --reload
```

- [x] `/healthz` returns 200
- [x] `/dashboard` loads
- [x] `/imports` loads
- [x] Upload PDF through imports
- [x] `/batch/process` processes the uploaded PDF
- [x] `/results` shows the uploaded PDF
- [x] CSV export works
- [x] Markdown export works
- [x] Excel export opens
- [x] `/quality` loads
- [x] `QR_DEBUG_EXPORT=true` creates `data/debug/qr/*.png`
- [x] `QR_DEBUG_EXPORT=true` creates `data/debug/qr/*.json`
- [x] `/debug/document/{id}` displays debug artifacts

## SQLite PRAGMAs

- [x] `PRAGMA foreign_keys` returns `1`
- [x] `PRAGMA busy_timeout` returns `5000`
- [x] `PRAGMA journal_mode` returns `wal`

## PostgreSQL Compatibility

- [x] With PostgreSQL `DATABASE_URL=postgresql+psycopg://...`, `python -m alembic current` returns `20260503_0007 (head)`
- [x] `python -m pytest` passes in normal test mode

## Automated Verification

- [x] `python -m pip install -e ".[dev]"`
- [x] `python -m pytest`
- [x] `python -m ruff check app tests migrations`

## Result Notes

```text
SQLite migration result:
PASS - `DATABASE_URL=sqlite:///data/olre.sqlite3 python -m alembic upgrade head` created schema through `20260503_0007 (head)`.
SQLite PRAGMAs verified: `foreign_keys=1`, `busy_timeout=5000`, `journal_mode=wal`.

SQLite runtime QA result:
PASS - App started on SQLite at port 8010. `/healthz`, `/dashboard`, `/imports`, upload, `/batch/process`, `/results`, CSV/Markdown/Excel export, `/quality`, QR debug artifacts, and `/debug/document/2` passed.

PostgreSQL compatibility result:
PASS - Existing `.env` PostgreSQL mode returned `20260503_0007 (head)`, and the full pytest suite passed in normal test mode.
Final automated verification: `python -m pip install -e ".[dev]"` passed, `python -m pytest` passed with 61 tests, and `python -m ruff check app tests migrations` passed.

Issues:
None found in SQLite runtime smoke.

Known limitations:
SQLite has a single-writer model. It is recommended for small/simple deployments; PostgreSQL remains the better target for heavier concurrent writes.
```
