# OLRE v0.9.3 Browser QA Checklist

Date: 2026-05-04

Status legend:

- `[ ]` Not tested
- `[x]` Passed
- `[!]` Issue found
- `[-]` Not applicable in current environment

## Test Environment

- OS: Windows
- Server command: `python -m uvicorn app.main:app --reload`
- Install command: `python -m pip install -e ".[dev]"`
- Database: PostgreSQL runtime expected; automated tests use SQLite in-memory
- Public mode: `ENABLE_AUTH=false`
- OCR default: `OCR_ENABLED=false`
- QR fallback default: `QR_FALLBACK_DECODER=none`
- QA note: in-app browser automation was unavailable in this environment due to `Access is denied`; HTTP-level QA was completed against the running server. Visual click-by-click browser inspection is documented as `SKIPPED` for this environment.

## Visual Page QA Matrix

| Page | Result | Evidence | Issue | Fix |
| --- | --- | --- | --- | --- |
| `/dashboard` | SKIPPED | Browser automation failed with `Access is denied`; HTTP GET returned 200 and no raw labels. | No visual browser surface was available to Codex. | Manual human browser review should be done before tag if strict visual QA is required. |
| `/results` | SKIPPED | Browser automation failed with `Access is denied`; HTTP GET returned 200 and no raw labels. | No visual browser surface was available to Codex. | Manual human browser review should be done before tag if strict visual QA is required. |
| `/quality` | SKIPPED | Browser automation failed with `Access is denied`; HTTP GET returned 200 and no raw labels. | No visual browser surface was available to Codex. | Manual human browser review should be done before tag if strict visual QA is required. |
| `/exports` | SKIPPED | Browser automation failed with `Access is denied`; HTTP GET returned 200 and no raw labels. | No visual browser surface was available to Codex. | Manual human browser review should be done before tag if strict visual QA is required. |
| `/imports` | SKIPPED | Browser automation failed with `Access is denied`; HTTP GET returned 200 and no raw labels. | No visual browser surface was available to Codex. | Manual human browser review should be done before tag if strict visual QA is required. |
| `/batch` | SKIPPED | Browser automation failed with `Access is denied`; HTTP GET returned 200 and no raw labels. | No visual browser surface was available to Codex. | Manual human browser review should be done before tag if strict visual QA is required. |
| `/batch/runs` | SKIPPED | Browser automation failed with `Access is denied`; HTTP GET returned 200 and no raw labels. | No visual browser surface was available to Codex. | Manual human browser review should be done before tag if strict visual QA is required. |
| `/debug/document/1` | SKIPPED | Browser automation failed with `Access is denied`; HTTP GET returned 200 and no raw labels. | No visual browser surface was available to Codex. | Manual human browser review should be done before tag if strict visual QA is required. |

## Page Load Smoke Test

- [x] `/dashboard` loads without 500
- [x] `/results` loads without 500
- [x] `/quality` loads without 500
- [x] `/exports` loads without 500
- [x] `/imports` loads without 500
- [x] `/batch` loads without 500
- [x] `/batch/runs` loads without 500
- [x] `/debug/document/{id}` loads or returns a readable not-found/empty-debug state

## Navigation and Localization

- [ ] Main navigation links point to the correct pages
- [x] Thai labels render correctly
- [x] English labels render correctly
- [x] Language switcher changes Thai to English
- [x] Language switcher changes English to Thai
- [x] Language switch keeps the user on the current page
- [x] No raw template text such as `{{ labels.xxx }}` appears

## Results and Export

- [x] `/results` filter by filename works
- [x] `/results` filter by processing status works
- [x] `/results` filter by source type works
- [x] `/results` filter by domain works
- [x] Filtered CSV export preserves query filters
- [x] Filtered Markdown export preserves query filters
- [x] Filtered Excel export preserves query filters
- [x] Excel export opens successfully in Excel/LibreOffice-compatible parser

## Dashboard and Quality

- [x] `/dashboard` shows KPI cards
- [x] `/dashboard` shows domain analytics
- [x] `/dashboard` shows source summary
- [x] `/dashboard` shows daily trend
- [x] `/quality` shows zero-reference documents
- [x] `/quality` shows failed documents
- [x] `/quality` shows OCR failed/image-only signals when applicable
- [x] `/quality` shows failed URL resolution signals when applicable

## Import and Batch Flow

- [x] `/imports` uploads a PDF
- [x] Non-PDF upload is rejected with readable message
- [x] `/batch` shows pending file count
- [x] `/batch/process` processes pending PDFs
- [x] `/batch/runs` shows batch run history
- [x] `/batch/runs/{id}` shows batch run detail
- [x] Public non-OAuth mode works without login
- [x] If `APP_TOKEN` is empty, `/batch/process` works without `X-API-KEY`
- [x] If `APP_TOKEN` is set, `/batch/process` requires correct `X-API-KEY`

## QR Debug and Retry

- [x] With `QR_DEBUG_EXPORT=true`, processing creates debug PNG artifacts
- [x] With `QR_DEBUG_EXPORT=true`, processing creates JSON sidecar
- [x] `/debug/document/{id}` displays debug attempts
- [x] Missing debug artifacts show a readable empty/not-found state
- [x] Retry failed document queues file back to input when source exists
- [ ] Retry failed document shows readable error when source file is missing

## OCR Runtime

- [x] With `OCR_ENABLED=false`, image-only PDFs do not crash batch
- [x] With `OCR_ENABLED=true` and missing Tesseract, batch does not crash
- [x] Missing Tesseract is logged as OCR runtime unavailable
- [x] OCR failure appears in results/quality without traceback
- [-] With Tesseract installed, OCR can extract text from image-only PDF

## pyzbar/zbar Fallback

- [x] Default `QR_FALLBACK_DECODER=none` keeps OpenCV path working
- [x] `QR_FALLBACK_DECODER=pyzbar` does not crash when pyzbar/zbar is unavailable
- [x] pyzbar unavailable state is logged clearly
- [-] With pyzbar/zbar installed, fallback can decode a QR that OpenCV misses

## QA Notes

Use this section during manual QA:

```text
Run started:
2026-05-04 12:17 Asia/Bangkok
Run finished:
2026-05-04 12:34 Asia/Bangkok
Tester:
Codex
Browser:
In-app browser unavailable due to Access is denied; HTTP-level QA via Invoke-WebRequest/httpx/urllib
Dataset:
Existing PostgreSQL runtime data plus generated runtime-only QA files:
- data/qa_upload_sample_v093.pdf
- data/qa_ocr_missing_v093.pdf
- data/qa_retry_invalid_v093.pdf

Runtime evidence:
- Upload route accepted qa_upload_sample_v093.pdf and saved it to data/input.
- Batch processed qa_upload_sample_v093.pdf and moved it to data/processed.
- Results filter /results?filename=qa_upload_sample_v093 returned the document and https://example.com/olre-v093.
- QR debug with QR_DEBUG_EXPORT=true created data/debug/qr/doc_21.json and doc_21_page_1_*.png artifacts.
- /debug/document/21 returned 200 and displayed artifact references.
- Excel export with filename filter opened successfully with sheets Summary, Documents, References, Domains, Errors.
- APP_TOKEN empty allowed POST /batch/process.
- APP_TOKEN=dev-test-token rejected missing and wrong X-API-KEY with 401, and accepted the correct token with 200.
- OCR_ENABLED=true without pytesseract/Pillow did not crash; document id 22 was processed with OCR_NOT_AVAILABLE.
- QR_FALLBACK_DECODER=pyzbar without pyzbar returned no values and did not crash.
- Invalid PDF retry test created failed document id 23, then POST /documents/23/retry returned 303 /imports and queued the file back to data/input.

Issues found:
- In-app browser automation failed with `Access is denied`, so visual click-by-click QA remains skipped in this environment.
- Real installed Tesseract OCR extraction is skipped because pytesseract/Pillow are not installed in the [dev] environment and native Tesseract availability was not confirmed.
- Real installed zbar/pyzbar decode is skipped because pyzbar is not installed in the [dev] environment and native zbar availability was not confirmed.

Manual QA result:
- HTTP/RUNTIME PASS; VISUAL BROWSER SKIPPED
```
