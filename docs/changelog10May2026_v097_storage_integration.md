# OLRE v0.9.7 Storage Integration

Release-Grade Changelog and Engineering Handoff

Date: `2026-05-10`  
Branch: `hardening/storage-integration-and-operational-qa`  
Target Tag: `v0.9.7-storage-integration`

---

## Objective

This phase completed the transition from prototype-era direct filesystem handling toward a centralized, auditable storage execution model.

The goal of v0.9.7 was operational stabilization, not feature expansion and not architectural reinvention.

Primary objectives:

- move filesystem execution behind storage modules
- keep policy in service layer
- preserve processing semantics
- reduce hidden path coupling
- make cleanup behavior more deterministic
- preserve retry behavior and lifecycle correctness
- maintain compatibility-first migration behavior

---

## Architectural Boundary Rule

The explicit architectural invariant for this phase is:

Raw filesystem operations are allowed only inside:

- `app/storage/*`
- narrowly justified runtime/bootstrap utilities such as `app/runtime.py` and `app/db/sqlite_backup.py`

Raw filesystem operations are not allowed inside:

- `app/services/*`
- `app/web/routes_*`
- `app/batch/*`

Exception policy:

- low-level adapters may remain when tightly coupled to third-party libraries or file-shaped interfaces
- such exceptions must be intentional, documented, and limited

This rule is now also reflected in the audit matrix:

- [docs/v0.9.7_storage_integration_audit_matrix.md](/Users/chin/official-letter-reference-extractor/docs/v0.9.7_storage_integration_audit_matrix.md)

---

## Files Changed

Primary refactor files:

- [app/storage/service.py](/Users/chin/official-letter-reference-extractor/app/storage/service.py)
- [app/services/process_batch.py](/Users/chin/official-letter-reference-extractor/app/services/process_batch.py)
- [app/services/retry_service.py](/Users/chin/official-letter-reference-extractor/app/services/retry_service.py)
- [app/services/retention_service.py](/Users/chin/official-letter-reference-extractor/app/services/retention_service.py)
- [app/web/routes_operations.py](/Users/chin/official-letter-reference-extractor/app/web/routes_operations.py)
- [app/services/ui_views.py](/Users/chin/official-letter-reference-extractor/app/services/ui_views.py)
- [app/batch/qr_debug.py](/Users/chin/official-letter-reference-extractor/app/batch/qr_debug.py)
- [app/services/inbox_paths.py](/Users/chin/official-letter-reference-extractor/app/services/inbox_paths.py)

Supporting documents added:

- [docs/v0.9.7_storage_integration_audit_matrix.md](/Users/chin/official-letter-reference-extractor/docs/v0.9.7_storage_integration_audit_matrix.md)
- [docs/v0.9.7_storage_integration_checklist.md](/Users/chin/official-letter-reference-extractor/docs/v0.9.7_storage_integration_checklist.md)
- [docs/status10May2026_v097_storage_integration_progress.md](/Users/chin/official-letter-reference-extractor/docs/status10May2026_v097_storage_integration_progress.md)

---

## Storage Modules Added

Internal storage decomposition introduced in this phase:

- [app/storage/document_storage.py](/Users/chin/official-letter-reference-extractor/app/storage/document_storage.py)
- [app/storage/export_storage.py](/Users/chin/official-letter-reference-extractor/app/storage/export_storage.py)
- [app/storage/debug_storage.py](/Users/chin/official-letter-reference-extractor/app/storage/debug_storage.py)
- [app/storage/temp_storage.py](/Users/chin/official-letter-reference-extractor/app/storage/temp_storage.py)
- [app/storage/path_resolver.py](/Users/chin/official-letter-reference-extractor/app/storage/path_resolver.py)
- [app/storage/types.py](/Users/chin/official-letter-reference-extractor/app/storage/types.py)

Important constraint preserved:

- `LocalStorageService` remains a thin facade
- storage implementation responsibilities are separated internally
- no generic backend registry or artifact framework was introduced

---

## Services Refactored

### `process_batch`

[app/services/process_batch.py](/Users/chin/official-letter-reference-extractor/app/services/process_batch.py) now:

- uses storage-backed temp working copies
- uses storage-backed inbox listing/bootstrap
- avoids direct `shutil.copy2` and direct `unlink` in the main batch/retry execution path
- preserves extraction ordering, fingerprint timing, and retry semantics

### `retry_service`

[app/services/retry_service.py](/Users/chin/official-letter-reference-extractor/app/services/retry_service.py) now:

- reads retained source via `storage_key` first
- falls back to legacy path only when needed
- no longer performs raw path existence checks directly in business logic

### `retention_service`

[app/services/retention_service.py](/Users/chin/official-letter-reference-extractor/app/services/retention_service.py) now:

- keeps lifecycle policy in service layer
- routes deletion/discovery execution through storage layer
- adds deterministic cleanup summaries
- preserves compatibility with legacy path-based rows

### `routes_operations` and inbox/UI flows

[app/web/routes_operations.py](/Users/chin/official-letter-reference-extractor/app/web/routes_operations.py) and [app/services/ui_views.py](/Users/chin/official-letter-reference-extractor/app/services/ui_views.py) now:

- route upload/delete through storage methods
- avoid raw file writes and deletes in route handlers
- use storage-backed inbox enumeration

### `qr_debug`

[app/batch/qr_debug.py](/Users/chin/official-letter-reference-extractor/app/batch/qr_debug.py) now:

- persists debug images and JSON through storage helpers
- no longer performs direct debug artifact writes in business-layer code

---

## Compatibility Policy

This phase remained compatibility-first.

Migration policy:

- write both where needed
- read prefer `storage_key`
- fallback legacy path

The following fields were intentionally preserved during v0.9.7:

- `moved_to_path`
- `last_source_path`
- `source_file_path`

They were not aggressively removed because:

- legacy rows must remain operational
- retry and cleanup flows still need compatibility support
- storage integration must stabilize before schema simplification

---

## Remaining Accepted Exceptions

The following remaining filesystem-related exceptions were reviewed and classified.

### [app/batch/fingerprint.py](/Users/chin/official-letter-reference-extractor/app/batch/fingerprint.py)

Classification:

- `allowed low-level adapter`

Reason:

- computes SHA-256 and file metadata from a concrete working file
- tightly coupled to file-shaped input
- now operates on storage-provided or workflow-provided temp/local files
- not business-layer artifact lifecycle execution

### [app/batch/pdf_validation.py](/Users/chin/official-letter-reference-extractor/app/batch/pdf_validation.py)

Classification:

- `allowed low-level adapter`

Reason:

- thin validation adapter around `fitz.open(file_path)`
- part of PDF library interaction, not policy or lifecycle logic
- extraction semantics intentionally preserved in this phase

### [app/batch/reference_extraction.py](/Users/chin/official-letter-reference-extractor/app/batch/reference_extraction.py)

Classification:

- `allowed low-level adapter`

Reason:

- extraction engine consumes a concrete PDF file path through PyMuPDF
- changing this now would risk behavioral drift in OCR/QR processing
- deferred intentionally to avoid mixing storage refactor with extraction semantics changes

### [app/services/inbox_paths.py](/Users/chin/official-letter-reference-extractor/app/services/inbox_paths.py)

Classification:

- `legacy compatibility fallback`

Reason:

- now reduced to a thin wrapper over storage facade inbox root
- retained only to avoid breaking existing imports/tests during compatibility-first migration
- does not perform filesystem execution itself

Additional narrow path-only usages remain in a few places:

- filename suffix/name parsing in route/debug code
- `storage.resolve_storage_key(...)` return value used for handoff into low-level adapters

Classification:

- `path parsing only, no filesystem execution`

These are considered acceptable in v0.9.7 because they do not reintroduce direct business-layer file operations.

---

## Path Resolver Leakage Review

The storage integration pass specifically reviewed whether business/service/web layers were resolving paths only to perform their own file operations.

Current result:

- main artifact lifecycle paths no longer perform raw `open`, `unlink`, `copy`, or directory creation in service/web layers
- route/service layers request storage operations rather than executing raw filesystem mutations themselves
- the remaining path exposures are limited to:
- compatibility wrappers
- logging/context display
- handoff to low-level adapters that still require file-shaped input

Conclusion:

- no hidden path-resolver leakage remains in the main artifact lifecycle execution paths

---

## Cleanup Safety

Retention cleanup now follows the intended high-risk infrastructure pattern in simplified deterministic form.

Implemented model:

1. discover candidates
2. validate lifecycle safety
3. validate not-processing
4. validate reference safety
5. dry-run/report capability
6. execute deletion through storage layer
7. structured deletion report/log

What is concretely implemented in [app/services/retention_service.py](/Users/chin/official-letter-reference-extractor/app/services/retention_service.py):

- candidate discovery by expired ingestion/debug/export/temp state
- skip behavior for actively processing documents
- skip behavior when retained-source reference is missing
- `dry_run` support
- storage-layer deletion execution
- structured cleanup summaries with deterministic counters

Example summary shape:

```json
{
  "cleanup_type": "retained_sources",
  "candidates": 42,
  "failed_sources_deleted": 39,
  "ingestions_reconciled": 39,
  "skipped_processing": 2,
  "skipped_missing_reference": 1
}
```

Explicitly deferred:

- quarantine/trash behavior

Reason for deferral:

- useful for future safety hardening
- not required to achieve v0.9.7 operational stabilization
- would expand scope beyond the intended integration phase

---

## Tests Run

### Full test suite

Command:

```bash
APP_ENV=testing uv run pytest
```

Result:

```text
79 passed
```

Warnings:

- 5 non-blocking SWIG-related deprecation warnings remain

### Ruff

Command:

```bash
APP_ENV=development uv run ruff check app tests migrations
```

Result:

```text
All checks passed!
```

### Targeted operational QA

Also verified during this phase:

- retry flow
- QR debug flow
- storage hardening flow
- batch flow
- UI flow

Result:

```text
55 passed
```

---

## Known Limitations

Accepted limitations after v0.9.7:

- extraction internals still consume concrete file paths through low-level adapters
- compatibility path fields remain in active support
- quarantine/trash cleanup mode is deferred
- `uv.lock` repository policy is still unresolved at architecture level
- non-blocking SWIG warnings remain present in test output

These are acceptable because they do not block the intended phase outcome:

- operational stabilization

---

## Worktree Policy

Two items were explicitly reviewed as potentially unrelated to the v0.9.7 phase commit.

### `uv.lock`

Recommended policy for this phase:

- leave it untracked with explanation

Reason:

- lockfile policy for this repository is still undecided
- it is not required to represent the v0.9.7 storage integration change itself
- including it now would mix workflow policy with infrastructure refactor

### `docs/changelog09May2026_runtime_profile_hardening.md`

Recommended policy for this phase:

- keep it out of the v0.9.7 phase commit unless separately intended

Reason:

- it belongs to prior runtime-profile documentation history
- it is not part of the storage integration implementation boundary
- mixing it would reduce commit clarity

---

## Recommended Next Phase

Recommended next phase after v0.9.7:

- storage lifecycle consolidation and cleanup safety refinement

Suggested focus:

- deprecate legacy path fields once operational stability is proven
- consider quarantine/trash behavior for non-production cleanup safety
- continue reducing compatibility wrappers
- revisit whether extraction-file adapters need further encapsulation after storage integration has fully stabilized

---

## Final Assessment

v0.9.7 should be considered a successful storage integration phase.

It achieved the intended outcome:

- operational stabilization

without crossing into:

- architectural reinvention

The main artifact lifecycle paths now execute through storage modules rather than raw business-layer filesystem handling, while full test coverage still passes and runtime behavior remains stable.
