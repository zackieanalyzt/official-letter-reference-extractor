# OLRE Troubleshooting

Current stable milestone/tag:

```text
release/v0.9.8-controlled-pilot
```

Quick architecture reminder:

- `v0.9.5` runtime determinism
- `v0.9.6` storage identity and lifecycle foundation
- `v0.9.7` storage boundary integration
- `v0.9.8` lifecycle registry, ops visibility, release identity, traversal planning runtime

For the current handoff, start with `docs/CURRENT_STATUS_HANDOFF.md`.

## `git is not recognized`

Install Git for Windows and choose `Use Git from the Windows Command Prompt`.

Verify:

```powershell
git --version
```

## venv Activate Path Is Wrong

Wrong on Windows:

```powershell
venv\bin\Activate
```

Correct:

```powershell
.venv\Scripts\activate
```

## `uvicorn is not recognized`

Use module execution:

```powershell
python -m uvicorn app.main:app --reload
```

If it still fails:

```powershell
python -m pip install -e ".[dev]"
```

## `ModuleNotFoundError: fastapi`

Install project dependencies:

```powershell
python -m pip install -e ".[dev]"
```

## `ModuleNotFoundError: openpyxl`

`openpyxl` is required for Excel export:

```powershell
python -m pip install -e ".[dev]"
```

## Alembic Schema Mismatch

If the app errors with missing database columns, run:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Expected:

```text
repository head
```

## SQLite Quick Start

Use this in `.env`:

```env
APP_ENV=development
DATABASE_URL=sqlite:///data/olre.sqlite3
```

Then run:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 7777
```

If the database needs to be recreated during testing, stop the server and remove:

```text
data/olre.sqlite3
data/olre.sqlite3-wal
data/olre.sqlite3-shm
```

Then rerun migration.

## Docker Runtime Does Not Start

Build and run the Docker profile directly:

```powershell
docker compose build
docker compose up
```

Expected host URL:

```text
http://127.0.0.1:8000
```

Expected health check:

```powershell
curl http://localhost:8000/healthz
```

If startup fails, inspect logs:

```powershell
docker compose logs -f
```

## Docker `libGL.so.1` or `libxcb.so.1` Error

Rebuild the image without cache:

```powershell
docker compose build --no-cache
docker compose up
```

This repository's Docker image includes `libgl1`, `libglib2.0-0`, `libsm6`, `libxext6`, `libxrender1`, and `libxcb1` for OpenCV and PyMuPDF runtime compatibility.

## Docker Data Did Not Persist

The Compose file uses the named volume `olre_data` mounted at `/app/data`.

Check:

```powershell
docker compose ps
docker volume ls
```

Do not use this unless you intend to delete the database and runtime files:

```powershell
docker compose down -v
```

Safe stop that keeps data:

```powershell
docker compose down
docker compose up -d
```

Then verify:

```powershell
curl http://localhost:8000/healthz
docker compose logs --tail 100
```

## Docker Runtime Unexpectedly Uses Non-SQLite Database

Check the container health response:

```powershell
curl http://localhost:8000/healthz
```

Expected:

```json
{"status":"ok","database_backend":"sqlite"}
```

The Docker runtime in this repository is intended to run with:

```env
DATABASE_URL=sqlite:////app/data/olre.sqlite3
ENABLE_AUTH=false
APP_LANG=th
```

## App Still Writes to PostgreSQL

Check `/healthz`:

```text
http://127.0.0.1:8000/healthz
```

If it does not show `"database_backend":"sqlite"`, confirm `.env` contains:

```env
APP_ENV=development
DATABASE_URL=sqlite:///data/olre.sqlite3
```

Restart the server after changing `.env`.

Then confirm data is in SQLite:

```powershell
python -c "import sqlite3; con=sqlite3.connect('data/olre.sqlite3'); print(con.execute('select id, original_file_name from documents').fetchall()); con.close()"
```

## SQLite Database Is Locked

Close duplicate server processes or tools that hold the database. OLRE enables WAL and `busy_timeout=5000`, but SQLite still has a single-writer model.

## Browser Hangs on `localhost:8000`

If `/healthz` times out and the browser keeps loading, an old server process may be stuck on port 8000.

Check:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
```

Use another port temporarily:

```powershell
python -m uvicorn app.main:app --reload --port 8021
```

Open:

```text
http://127.0.0.1:8021/imports
```

## Storage Boundary Confusion

If a refactor or local patch starts manipulating paths directly in service or route code, stop and review the storage boundary rule.

Operational rule:

- raw filesystem execution should live in `app/storage/*` or approved low-level adapters
- business/service/web layers should request artifact operations instead of opening, deleting, or copying files directly

Accepted low-level exceptions in `v0.9.7`:

- `app/batch/fingerprint.py`
- `app/batch/pdf_validation.py`
- `app/batch/reference_extraction.py`
- `app/services/inbox_paths.py`

If a new change falls outside those boundaries, it should usually be moved into the storage layer.

## Cleanup Safety Verification

Retention cleanup is high-risk infrastructure. Before trusting cleanup changes, verify that the implementation still follows this model:

1. discover candidates
2. validate lifecycle safety
3. validate not-processing
4. validate reference safety
5. dry-run/report capability
6. execute deletion through storage layer
7. structured cleanup summary/log

Quarantine/trash behavior is intentionally deferred after the current controlled-pilot release.

## Latest Verification Commands

```bash
APP_ENV=testing uv run pytest
APP_ENV=development uv run ruff check app tests migrations
```

Latest verified results:

- `121 passed, 6 warnings` after traversal planning runtime handoff
- `All checks passed`

## `processing_error_type does not exist`

The database is behind the ORM. Run migrations:

```powershell
python -m alembic upgrade head
```

## Tesseract Not Found

Typical error:

```text
OCR_FAIL: tesseract is not installed or it's not in your PATH
```

Fix:

1. Install Tesseract OCR.
2. Add `C:\Program Files\Tesseract-OCR` to PATH.
3. Verify `tesseract --version`.
4. Set `OCR_ENABLED=true`.

Until then, keep:

```env
OCR_ENABLED=false
```

## pyzbar/zbar Missing

If `QR_FALLBACK_DECODER=pyzbar` but zbar runtime is missing, OLRE should log QR fallback unavailable and continue with OpenCV behavior.

Use:

```env
QR_FALLBACK_DECODER=none
```

until zbar is installed.

## Excel Export Error

Reinstall dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Then test:

```text
/exports/excel
```

## Debug Image Does Not Show

Check:

```env
QR_DEBUG_EXPORT=true
QR_DEBUG_DIR=data/debug/qr
```

Then process a document again. Existing documents will not have debug artifacts unless they were processed while debug export was enabled.

## QR Exists but OLRE Still Does Not Detect It

This can happen with real scanned government letters even when the QR is valid.

Typical pattern:

- the PDF is image-only or mostly scanned
- the QR is physically small
- the QR sits in the left half of the page
- the QR is lower than the body text, but not deep enough to fall into the bottom 25 percent of the page
- the page has large white margins, so full-page QR detection must find a small code in a very large image

Observed real-world example:

- a scanned official letter placed the QR in the lower-left operational area with a nearby `QRcode` label
- the QR was valid, but a deep bottom-left crop alone could still miss it because the code sat higher than the crop start

Why it fails:

- full-page OpenCV decode may miss a small QR in a large scanned page
- deep lower-left crops such as lower 25 percent or lower 30 percent may start below the actual QR position

What OLRE now does:

- keeps full-page multi-pass QR detection
- adds left-middle-lower targeted crops such as `left_band_40_65_percent`, `left_band_45_70_percent`, `left_lower_mid_35_percent`, and `qr_label_band`
- adds adaptive-threshold and upscale passes for those focused left-side regions

If a document still fails:

1. Enable QR debug:

```env
QR_DEBUG_EXPORT=true
```

2. Reprocess the document.

3. Open the QR debug page and inspect these strategies first:

- `left_band_40_65_percent`
- `left_band_45_70_percent`
- `left_lower_mid_35_percent`
- `qr_label_band`
- `bottom_left_deep`

4. Confirm whether the QR is fully inside the recorded crop bounds.

If the QR is visible in debug crops but decode still fails, the remaining cause is usually image quality:

- low contrast
- blur
- scan compression artifacts
- insufficient quiet zone around the QR

## Upload Succeeds but Batch Does Not See File

Check:

- `INPUT_DIR` points to the same directory used by `/imports`.
- The file extension is `.pdf`.
- The file was not already moved to `data/processed` as a duplicate.

## `/batch/process` Returns Unauthorized

If `APP_TOKEN` is set, send:

```text
X-API-KEY: <APP_TOKEN>
```

For local unguarded use:

```env
APP_TOKEN=
```
