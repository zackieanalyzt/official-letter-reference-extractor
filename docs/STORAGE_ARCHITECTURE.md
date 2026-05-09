# Storage Architecture

OLRE v0.9.6 introduces a storage-hardening foundation for deterministic, safer document persistence.

## Design Goals

- deterministic physical storage identity
- filename safety
- path-length safety
- content deduplication
- future storage backend abstraction
- compatibility with SQLite-first single-node deployment

## Core Rule

Original filenames are metadata.

Physical storage identity is derived from SHA-256 content hashes.

## Content-Addressable Layout

Document blobs are stored under the configured storage root:

```text
data/storage/sha256/ab/cd/<sha256>.pdf
```

or in Docker:

```text
/app/data/storage/sha256/ab/cd/<sha256>.pdf
```

### Why this layout

- prevents giant flat directories
- avoids collisions from duplicate filenames
- avoids long original filename dependency
- keeps storage keys deterministic
- supports future migration to object storage

## Metadata Separation

The `documents` table now separates human-visible and storage-level concerns:

| Field | Meaning |
|---|---|
| `original_file_name` | user-visible filename |
| `content_hash` | existing content identity field for backward compatibility |
| `sha256` | explicit SHA-256 metadata |
| `storage_key` | relative content-addressable storage location |
| `storage_backend` | current backend, default `localfs` |
| `mime_type` | optional MIME metadata |
| `file_size_bytes` | operational size metadata |
| `lifecycle_state` | storage lifecycle state |

## Storage Service Layer

Storage behavior is now centered on `app.storage.service.LocalStorageService`.

Current supported operations:

- `save_document(...)`
- `open_document(...)`
- `delete_document(...)`
- `save_debug_artifact(...)`
- `create_export(...)`
- `list_retained_failures()`

This is the first step toward removing raw path manipulation from business logic.

## Runtime Directories

Profile-aware roots now include:

- `INPUT_DIR`
- `PROCESSED_DIR`
- `ERROR_DIR`
- `QR_DEBUG_DIR`
- `RUNTIME_TMP_DIR`
- `FAILED_RETAINED_DIR`
- `STORAGE_ROOT`
- `EXPORT_DIR`
- `BACKUP_DIR`

`STORAGE_ROOT` is now the canonical root for retained content-addressable document blobs.

## Dedupe Behavior

When two uploaded files have identical bytes:

- they share the same SHA-256
- they resolve to the same content-addressable `storage_key`
- duplicate blob storage is avoided

Original filenames remain preserved in metadata and UI output.

## Internal Filename Handling

Filename utilities now exist for internal operational artifacts:

- `normalize_filename(...)`
- `truncate_safe_filename(...)`
- `build_storage_key(...)`

These helpers are intended for internal safety, not for changing user-visible document names.

## Migration Notes

The storage-hardening foundation adds new metadata but preserves backward compatibility where practical:

- existing `content_hash` remains usable
- existing `moved_to_path` remains available for operational compatibility
- older rows may not have populated `storage_key` values until reprocessed or newly ingested

## Operational Verification

Useful checks:

```bash
python -m alembic upgrade head
python -m pytest tests/integration/test_storage_hardening.py
python -m app.cli.backup_sqlite
python -m app.cli.verify_backup
```
