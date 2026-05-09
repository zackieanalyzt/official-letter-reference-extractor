# OLRE v0.9.6 Storage Hardening

Date: `2026-05-10`

Branch: `hardening/runtime-profiles-backup-and-storage`

Milestone: `v0.9.6-storage-hardening`

## Summary

This phase hardens OLRE from a runtime-aware application into an application with a safer document persistence foundation.

The main storage risks addressed were:

- Docker/local path drift already solved in v0.9.5, but storage behavior was still path-fragile
- original filenames were still too important operationally
- retained source files still depended too much on raw filesystem naming
- cleanup behavior was too narrow
- WAL-safe backup guidance existed only in docs, not tooling

## Implemented

### Storage metadata foundation

Added document metadata fields for storage hardening:

- `sha256`
- `storage_key`
- `storage_backend`
- `mime_type`
- `lifecycle_state`

Migration:

```text
20260509_0010_storage_hardening_foundation
```

### Content-addressable storage foundation

Introduced deterministic storage key generation:

```text
sha256/ab/cd/<sha256>.pdf
```

This is now the preferred physical storage identity model for retained document blobs.

### Storage abstraction layer

Introduced `LocalStorageService` with APIs for:

- saving documents
- opening documents
- deleting documents
- saving debug artifacts
- creating export artifacts

### Filename safety helpers

Added internal-only helpers:

- `normalize_filename(...)`
- `truncate_safe_filename(...)`
- `build_storage_key(...)`

### Retention framework expansion

Added cleanup functions for:

- runtime tmp
- QR debug artifacts
- failed retained sources
- export artifacts

`dry_run` behavior is now supported for retention cleanup logic.

### Storage lifecycle modeling

Introduced explicit lifecycle states:

- `uploaded`
- `processing`
- `processed`
- `failed`
- `retained`
- `archived`
- `deleted`

### SQLite backup tooling

Added executable backup and verification commands:

```bash
python -m app.cli.backup_sqlite
python -m app.cli.verify_backup
```

These use the SQLite backup API and `integrity_check` instead of unsafe live file-copy logic.

## Verification

Validated during implementation:

- `uv run ruff check app tests migrations`
- targeted runtime/storage pytest suite
- content-addressable path generation
- duplicate-content storage dedupe
- export retention cleanup
- retained failure cleanup
- SQLite backup/verify round trip

Targeted suite result:

```text
40 passed
```

## Operational Impact

OLRE now has a much stronger foundation for:

- long Thai filename safety
- deduplicated retained blobs
- runtime artifact cleanup
- retry-aware source retention
- future object storage migration
- safer operational backup routines

## Remaining Debt

Still pending for the next storage-focused iteration:

- deeper migration away from `moved_to_path`
- stronger export artifact integration in download routes
- broader lifecycle UI exposure
- content-addressable treatment for all retained artifact categories
- final lockfile policy for `uv.lock`

## Recommended Next Validation

Run:

```bash
python -m alembic upgrade head
uv run ruff check app tests migrations
uv run pytest
python -m app.cli.backup_sqlite
python -m app.cli.verify_backup
```
