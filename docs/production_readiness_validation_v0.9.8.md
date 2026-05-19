# OLRE v0.9.8 Production Readiness Validation Report

Date: 2026-05-19  
Branch: `codex/v0.9.8-epic2-runtime-introspection`  
Validation mode: production-readiness validation only

## 1. Executive Summary

OLRE was validated against the v0.9.8 lifecycle/ops maturity goal using a local SQLite development runtime, browser workflow checks, HTTP endpoint checks, export checks, lifecycle consistency checks, and a realistic mixed batch of 13 PDF inputs.

Release metadata for deployments should be provided through environment variables or
`config/release.json`; the UI release panel must not hardcode release strings in templates.
Recommended controlled-pilot values:

```env
OLRE_APP_VERSION=0.9.8
OLRE_RELEASE_NAME=Controlled Pilot
OLRE_RELEASE_DATE=2026-05-19
OLRE_RELEASE_CHANNEL=controlled-pilot
OLRE_RELEASE_STATUS=Ready for controlled pilot use
OLRE_RELEASE_NOTE=Not recommended for broad unattended rollout yet.
OLRE_RELEASE_HIGHLIGHTS=Lifecycle Registry|Lifecycle Visibility|Runtime/Ops readiness validation
```

Result:

- Release recommendation: **ready for controlled pilot use, not broad unattended rollout yet**
- Unresolved verified critical bugs: **0**
- Known automated-test critical failures: **0**
- Residual production-readiness risk: **~5-6%**, reduced from the previous ~10% estimate
- Verification after code change:
  - `APP_ENV=development uv run ruff check app tests migrations` -> **All checks passed**
  - `APP_ENV=testing uv run pytest` -> **100 passed, 6 warnings**

One production-readiness bug was found and fixed during validation:

- Batch reference summary over-counted references when a reused/duplicate ingestion pointed to the same document in the same batch. The count now uses distinct reference IDs and has a regression test.

## 2. Browser QA Results

| Area | Result | Evidence / Notes |
| --- | --- | --- |
| `/imports` | PASS | Upload endpoint accepted 13 PDFs. Browser page rendered 13 pending files with sane table status and delete actions. |
| `/batch` | PASS | Batch completed with `completed_with_errors`: 13 seen, 11 processed, 1 duplicate skipped, 1 corrupted failed. No full-batch abort. |
| `/results` | PASS | Results page rendered, filters rendered, failed-resolution filter worked. Rows mapped to extracted text/QR references. |
| `/exports` | PASS | Export page rendered counts and filters. CSV, Markdown, and Excel endpoints returned usable files. |
| `/exports/csv` | PASS | CSV downloaded, 1,036 bytes, header and reference rows valid. |
| `/exports/markdown` | PASS | Markdown downloaded, 2,004 bytes, report summary rendered. |
| `/exports/excel` | PASS | Excel downloaded, 9,672 bytes, opened with `openpyxl`; sheets: Summary, Documents, References, Domains, Errors. |
| `/quality` | WARNING | Page rendered without server error. The "ไม่มีข้อมูลอ้างอิง" section includes both the true no-reference PDF and the corrupted failed PDF, which is technically explainable but can confuse operators. |
| `/documents/2/lifecycle/view` | PASS | Timeline rendered, ordered, grouped, and consistency checks were readable. |
| `/documents/2/lifecycle/consistency` | PASS | JSON returned `PASS` with projection matching lifecycle history. |
| `/ops` | PASS | Runtime, path, storage, and lifecycle overview rendered and was usable for support. |
| `/ops/runtime` | PASS | JSON showed development profile, SQLite active backend, lifecycle table available, writable runtime paths. |
| `/ops/storage/orphans` | PASS | JSON showed no unreferenced, missing, retained-missing, cleaned-present, or source-reference orphan issues after validation batch. |
| `/ops/lifecycle/consistency-summary` | PASS | JSON showed 12 scanned documents, 12 PASS, 0 WARNING/ERROR/CRITICAL. |

Endpoint status check:

```text
/imports 200
/batch 200
/results 200
/exports 200
/quality 200
/ops 200
/documents/2/lifecycle/view 200
/documents/2/lifecycle/consistency 200
/ops/runtime 200
/ops/storage/orphans 200
/ops/lifecycle/consistency-summary 200
```

## 3. Sample Batch QA Results

Sample set:

| Required Type | Covered By |
| --- | --- |
| text-layer PDF | `01_text_layer_reference.pdf` |
| scanned PDF | `10_scanned_pdf_with_qr.pdf` |
| QR bottom-left | `02_qr_bottom_left.pdf` |
| QR bottom-center | `03_qr_bottom_center.pdf` |
| QR bottom-right | `04_qr_bottom_right.pdf` |
| multiple QR references | `05_multiple_qr_references.pdf` |
| shortened URLs | `06_shortened_url_text.pdf` |
| invalid/broken URLs | `07_invalid_broken_url_text.pdf` |
| QR with non-URL payload | `04_qr_bottom_right.pdf`, `05_multiple_qr_references.pdf` |
| corrupted PDF | `13_corrupted.pdf` |
| no-reference PDF | `08_no_reference.pdf` |
| multi-page PDF | `09_multi_page_mixed.pdf` |

Operational metrics:

| Metric | Result |
| --- | --- |
| Files seen | 13 |
| Processed successfully | 11 |
| Duplicate skipped | 1 |
| Failed documents | 1 |
| Stored document rows | 12 |
| Stored reference rows | 12 |
| Batch status | `completed_with_errors` |
| Batch duration | ~10m 21s |
| Zero-reference documents | 1 true no-reference document plus 1 corrupted failed document with zero references |
| Retry count | 0 during validation |
| Lifecycle consistency summary | 12 PASS, 0 WARNING, 0 ERROR, 0 CRITICAL |
| Orphan summary | all orphan counters 0 |
| Export generation | CSV, Markdown, Excel all succeeded |

Validation answers:

- Batch completed: **yes**
- One bad PDF aborted the whole batch: **no**
- Lifecycle history remained coherent: **yes**
- References duplicated incorrectly: **no persisted duplicate reference rows found**
- One-row-per-reference preserved: **yes for stored references**
- Exports remained usable: **yes**
- Failed documents explainable: **yes, corrupted PDF was retained with `INVALID_PDF`**
- Consistency checks sane: **yes**

Observed warnings:

- Self-referential validation URLs such as `http://127.0.0.1:7777/healthz` timed out during synchronous batch processing because the app was busy serving the batch request. This is a validation-artifact warning and also a useful reminder that URL resolution remains synchronous.
- QR-heavy synthetic PDFs took tens of seconds each because multiple QR strategies continue running even after early successful detection. This is not a correctness failure, but it is a production performance risk to watch with real scanned documents.
- Non-URL QR payloads were retained correctly, but their `resolution_status` remained `pending`, which can confuse operators because no URL resolution is actually needed.

## 4. Lifecycle & Ops Findings

Live validation:

- Processed documents ended in `resolved` lifecycle state.
- Corrupted PDF ended in `retained` lifecycle state with retained source available.
- Lifecycle events were append-only and ordered.
- `/ops/lifecycle/consistency-summary` reported all live validation documents as PASS.
- `/ops/storage/orphans` reported no retained/missing or orphan artifacts.

Drift simulation results using isolated in-memory validation data:

| Scenario | Validator Result |
| --- | --- |
| valid projection | PASS |
| projection mismatch | ERROR |
| missing lifecycle history | WARNING |
| invalid transition | CRITICAL |
| retained-but-missing-file | CRITICAL |
| cleaned without cleanup event | ERROR overall, with cleanup-event warning present |
| cleaned while source marked present | CRITICAL |
| retry completed without retry start | ERROR |

This confirms the lifecycle validator separates `PASS`, `WARNING`, `ERROR`, and `CRITICAL` coherently for the target operational drift cases.

## 5. Critical Issues Found

Unresolved critical issues:

```text
0
```

No system-breaking issue was verified during validation. The corrupted PDF case failed safely, was retained, and did not abort the batch.

## 6. Major Bugs / Readiness Gaps

Fixed during validation:

- **Major bug fixed:** batch `total_references_found` over-counted when multiple ingestions in the same batch referenced the same document. Fixed by counting distinct `DocumentReference.id`; regression test added.

Remaining major readiness gaps:

- **Document-number extraction appears absent or not wired into the current pipeline.** Validation samples containing `/ว ...` produced `document_number = None`, and code search found no active extraction assignment beyond state restore handling. This does not block QR/URL extraction, but it is a PRD-level gap before broad release.
- **Performance risk on QR-heavy/scanned documents.** The 13-file sample took ~10m 21s, partly due to synthetic QR strategy cost and URL timeouts. Real-world LAN samples should be timed before broad rollout.

## 7. Known Limitations

- Default runtime remains synchronous and SQLite-first.
- URL resolution timeout/failure is expected for unavailable domains and network-restricted environments.
- Non-URL QR payloads are stored, but currently look like `pending` resolution items rather than a clearer `non_url`/`raw_only` terminal state.
- Quality page zero-reference section can include failed corrupted PDFs because they have no references; status is visible, but the grouping may confuse operators.
- OCR remains disabled unless native Tesseract runtime is installed and configured.
- Current validation used realistic generated samples plus local runtime data, not a full hospital production corpus.

## 8. Recommended Fixes

Before broad rollout:

- Implement or wire document-number extraction and add tests for Thai official-letter patterns such as `ลพ 0033.02/ว 6176` -> `ว6176`.
- Change non-URL QR payload resolution status from long-lived `pending` to a clearer terminal status such as `non_url` or `raw_only`, with migration/backfill guidance if needed.
- Review quality grouping so invalid/corrupted PDFs do not look like ordinary no-reference documents.
- Profile QR detection to avoid unnecessary expensive variants after sufficient confident detection, or document expected scanned-PDF processing time.

For controlled pilot:

- Use 20-50 real incoming PDFs from the actual operator workflow.
- Track average processing time per file, failed count, no-reference count, URL timeout count, and operator confusion points.
- Review `/ops` and lifecycle pages with the support/operator role after the first real batch.

## 9. Release Readiness Recommendation

Recommendation:

```text
Proceed to controlled pilot for v0.9.8 lifecycle/ops maturity.
Do not declare broad production release until document-number extraction and real-corpus timing are validated.
```

Rationale:

- Core batch processing survived mixed-quality inputs.
- A corrupted PDF did not abort the batch.
- QR/text extraction stored usable reference rows.
- Exports worked.
- Lifecycle and ops diagnostics were coherent and support-readable.
- No unresolved critical bug remains.
- Residual risk is now concentrated in real-corpus variance, document-number extraction, and performance tuning rather than lifecycle/ops correctness.
