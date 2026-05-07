# OLRE Windows Installation

## 1. Install Python

Install Python 3.11 or newer from the official Python installer. During installation, enable:

```text
Add python.exe to PATH
```

Verify:

```powershell
python --version
```

## 2. Clone the Repository

```powershell
git clone <repo-url>
cd official-letter-reference-extractor
```

If `git` is not recognized, install Git for Windows and choose `Use Git from the Windows Command Prompt`.

## 3. Create and Activate venv

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Windows uses `.venv\Scripts\activate`, not `venv\bin\Activate`.

## 4. Install Dependencies

For normal development:

```powershell
python -m pip install -e ".[dev]"
```

For OCR and pyzbar QR fallback testing:

```powershell
python -m pip install -e ".[dev,ocr,qr]"
```

`pytesseract` and `pyzbar` Python packages are optional. Tesseract and zbar native runtimes still need separate installation.

## 5. Configure Environment

```powershell
copy .env.example .env
```

For the SQLite-first runtime, keep:

```env
DATABASE_URL=sqlite:////app/data/olre.sqlite3
```

Local Windows overrides are still allowed if you want the database under the repository instead of `/app/data`, for example:

```env
DATABASE_URL=sqlite:///data/olre.sqlite3
INPUT_DIR=data/input
PROCESSED_DIR=data/processed
ERROR_DIR=data/error
QR_DEBUG_DIR=data/debug/qr
```

For public mode:

```env
ENABLE_AUTH=false
APP_TOKEN=
APP_LANG=th
```

Keep OCR disabled until Tesseract is installed:

```env
OCR_ENABLED=false
```

## 6. Run Database Migration

```powershell
python -m alembic upgrade head
python -m alembic current
```

The expected baseline head is:

```text
20260503_0007
```

## 7. Start Server

```powershell
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/imports
```

Check active database backend:

```text
http://127.0.0.1:8000/healthz
```

For SQLite, expected output includes:

```json
{"database_backend":"sqlite"}
```

## Common Windows Issues

- `uvicorn is not recognized`: use `python -m uvicorn app.main:app --reload`.
- `ModuleNotFoundError: fastapi`: rerun `python -m pip install -e ".[dev]"`.
- `ModuleNotFoundError: openpyxl`: rerun `python -m pip install -e ".[dev]"`.
- `tesseract is not installed or not in PATH`: install Tesseract and update PATH, or keep `OCR_ENABLED=false`.
- `pyzbar` import works but decode fails: install zbar native runtime for Windows.
- SQLite database file is missing: run `python -m alembic upgrade head`; OLRE creates `data/olre.sqlite3` during migration.
- SQLite database is locked: close other app instances and retry. OLRE enables WAL and `busy_timeout=5000` for normal small-office use.
- Browser keeps loading on `localhost:8000`: check whether an old server process is stuck on port 8000. Use another port temporarily:

```powershell
python -m uvicorn app.main:app --reload --port 8021
```
