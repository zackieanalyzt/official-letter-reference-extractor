# OLRE v0.9.7 Storage Integration Progress Status

Date: `2026-05-10`  
Branch: `hardening/storage-integration-and-operational-qa`  
Target Tag: `v0.9.7-storage-integration`

## Current Status

The storage integration phase has completed its initial stabilization pass.

The codebase now has:

- an explicit storage integration audit matrix
- a workstream-driven implementation checklist
- decomposed storage internals behind a thin `LocalStorageService` facade
- storage-backed integration for batch, retry, retention cleanup, inbox upload/delete, and QR debug persistence
- targeted operational QA passing on the highest-risk integration areas

## What Changed

### 1. Storage internals decomposed

The previous monolithic storage implementation was split into internal modules:

- `app/storage/document_storage.py`
- `app/storage/debug_storage.py`
- `app/storage/export_storage.py`
- `app/storage/temp_storage.py`
- `app/storage/path_resolver.py`
- `app/storage/types.py`

`LocalStorageService` remains a thin facade and central entrypoint.

### 2. Batch and retry integration updated

Refactors completed in:

- `app/services/process_batch.py`
- `app/services/retry_service.py`

Key effects:

- temp working copies now route through storage
- retained source lookups prefer `storage_key`
- legacy path fallback remains available
- processing semantics were preserved

### 3. Retention and cleanup execution moved toward storage layer

Refactors completed in:

- `app/services/retention_service.py`

Key effects:

- direct file deletion logic was reduced in service layer
- cleanup now relies on storage-backed candidate discovery and deletion helpers
- structured cleanup summaries were added
- compatibility-first fallback remains in place for legacy path-based rows

### 4. Route/debug boundary cleanup completed

Refactors completed in:

- `app/web/routes_operations.py`
- `app/services/ui_views.py`
- `app/batch/qr_debug.py`

Key effects:

- inbox upload/delete now route through storage service methods
- inbox listing now uses storage-backed inbox enumeration
- QR debug artifacts now persist through storage helpers rather than direct file writes

## Verification Results

### Ruff

Command:

```bash
uv run ruff check app tests migrations
```

Result:

```text
All checks passed!
```

### Targeted operational QA

Command set included:

```bash
uv run pytest tests/integration/test_retry_flow.py tests/integration/test_qr_debug_flow.py tests/integration/test_storage_hardening.py tests/integration/test_batch_flow.py tests/integration/test_ui_flow.py
```

Result:

```text
55 passed
```

Observed warnings:

- non-blocking SWIG-related deprecation warnings remain present

## Architectural Outcome So Far

This pass materially improves the storage boundary without changing OCR/QR extraction semantics.

The system is now closer to the intended v0.9.7 end-state:

- business logic no longer performs the main filesystem execution directly
- retained artifact identity is increasingly `storage_key`-first
- cleanup execution is more centrally auditable
- retry flows remain operational
- operational simplicity was preserved

## Remaining Follow-Up

The next step for this phase should be a final release-grade changelog/handoff document after any additional QA or minor cleanup is completed.

Recommended closeout focus:

- full-suite pytest if desired for final release confidence
- final codebase audit for any remaining narrow compatibility exceptions
- release handoff document for `v0.9.7-storage-integration`
