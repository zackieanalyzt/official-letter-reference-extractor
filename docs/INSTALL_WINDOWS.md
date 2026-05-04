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

Edit `.env` and set PostgreSQL connection values:

```env
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=olre_db
POSTGRES_USER=olre_user
POSTGRES_PASSWORD=change-me
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

The expected v0.9.3 baseline head is:

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

## Common Windows Issues

- `uvicorn is not recognized`: use `python -m uvicorn app.main:app --reload`.
- `ModuleNotFoundError: fastapi`: rerun `python -m pip install -e ".[dev]"`.
- `ModuleNotFoundError: openpyxl`: rerun `python -m pip install -e ".[dev]"`.
- `tesseract is not installed or not in PATH`: install Tesseract and update PATH, or keep `OCR_ENABLED=false`.
- `pyzbar` import works but decode fails: install zbar native runtime for Windows.
