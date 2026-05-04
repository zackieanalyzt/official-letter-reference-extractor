# OLRE Troubleshooting

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

Expected baseline:

```text
20260503_0007
```

## SQLite Quick Start

Use this in `.env`:

```env
DATABASE_URL=sqlite:///data/olre.sqlite3
```

Then run:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

If the database needs to be recreated during testing, stop the server and remove:

```text
data/olre.sqlite3
data/olre.sqlite3-wal
data/olre.sqlite3-shm
```

Then rerun migration.

## SQLite Database Is Locked

Close duplicate server processes or tools that hold the database. OLRE enables WAL and `busy_timeout=5000`, but SQLite still has a single-writer model.

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
