# Tesseract OCR Setup on Windows

OLRE can use OCR for image-only PDFs when text extraction returns too little text. OCR is optional and should stay disabled until Tesseract is installed.

## Install Tesseract

1. Download and install a Windows Tesseract OCR build.
2. Install to the default path when possible:

```text
C:\Program Files\Tesseract-OCR
```

3. Include Thai and English language data if you need both languages.

## Add PATH

Add this directory to the Windows `PATH` environment variable:

```text
C:\Program Files\Tesseract-OCR
```

Open a new PowerShell window and verify:

```powershell
tesseract --version
```

If this command does not work, OLRE OCR should remain disabled.

## Install Python OCR Extra

Inside the project venv:

```powershell
python -m pip install -e ".[dev,ocr]"
```

## Configure `.env`

```env
OCR_ENABLED=true
OCR_ENGINE=tesseract
OCR_LANG=tha+eng
OCR_TIMEOUT_SECONDS=30
OCR_MIN_TEXT_CHARS=25
OCR_DPI_SCALE=3
OCR_PAGE_SEGMENTATION_MODE=6
```

Use `OCR_LANG=eng` if Thai language data is not installed.

## Test with an Image-only PDF

1. Put an image-only PDF in `data/input`.
2. Start the server:

```powershell
python -m uvicorn app.main:app --reload
```

3. Open `/batch` and process.
4. Open `/results` and check for `source_type=ocr`.
5. Open `/quality` and confirm OCR failed/image-only documents are reflected correctly.

## Expected Graceful Failure

If Tesseract is missing, OLRE should:

- log an OCR runtime warning,
- mark the document with an OCR error such as `OCR_NOT_AVAILABLE`,
- continue batch processing,
- show a readable error in results/quality reports instead of a traceback.

Disable OCR again if the runtime is not ready:

```env
OCR_ENABLED=false
```
