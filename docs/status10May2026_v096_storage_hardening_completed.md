# OLRE Project Status — v0.9.6 Storage Hardening Completed

Date: `2026-05-10`

Branch: `hardening/runtime-profiles-backup-and-storage`

Latest Commit:
`596f327 feat: add storage hardening foundation`

Latest Tag Candidate:
`v0.9.6-storage-hardening`

---

## Current Project State

OLRE has now completed two major operational architecture phases:

1. Runtime Profile Hardening (`v0.9.5`)
2. Storage Hardening Foundation (`v0.9.6`)

The project has transitioned from:

```text
prototype-style runtime assumptions
```

toward:

```text
runtime-aware + operationally safe document persistence architecture
```

The system is no longer just a PDF-processing web application.

It now has:

- deterministic runtime profiles
- deterministic storage identity
- content-addressable retained blobs
- lifecycle-aware cleanup
- WAL-safe SQLite backup tooling
- operational retention strategy
- runtime-safe path handling

---

## Runtime Architecture Status

Completed previously in v0.9.5:

- profile-aware runtime behavior
- `development`
- `testing`
- `docker`
- `production`

Resolved earlier issues around:

- `/app/data/...` fallback misuse on local macOS runtime
- `.env` contamination of pytest
- unstable runtime defaults
- Docker assumptions leaking into local development

Key runtime behavior:

| Profile | Storage Root | SQLite |
|---|---|---|
| `development` | `data/...` | `sqlite:///data/olre.sqlite3` |
| `testing` | `data/...` | `sqlite:///data/olre.sqlite3` |
| `docker` | `/app/data/...` | `sqlite:////app/data/olre.sqlite3` |
| `production` | `/app/data/...` | container-style defaults |

---

## v0.9.6 Storage Hardening

### Main Architectural Goal

Reduce operational risk from:

- long Thai filenames
- UTF-8 path issues
- filename collisions
- path-length instability
- weak retention lifecycle
- unsafe SQLite backup handling

---

## Major Features Added

### 1. Content-Addressable Storage

Retained document blobs now use SHA-256-based storage keys.

Example:

```text
data/storage/sha256/ab/cd/<sha256>.pdf
```

This reduces:

- filename dependency
- duplicate blob storage
- path-length risk
- unsafe raw filename usage

### 2. Storage Metadata Foundation

Added new document metadata fields:

- `sha256`
- `storage_key`
- `storage_backend`
- `mime_type`
- `lifecycle_state`

Migration:

```text
20260509_0010_storage_hardening_foundation
```

### 3. Storage Abstraction Layer

Introduced:

```python
LocalStorageService
```

with APIs for:

- save/open/delete document blobs
- save debug artifacts
- create export artifacts
- retained blob handling

Goal:

reduce direct raw filesystem coupling in business logic.

### 4. Filename Safety Helpers

Added internal utilities:

```python
normalize_filename(...)
truncate_safe_filename(...)
build_storage_key(...)
```

These are operational-only helpers.

Original filenames remain preserved for UI/export usage.

### 5. Retention Framework

Implemented cleanup support for:

| Artifact | Retention |
|---|---|
| QR debug artifacts | 7 days |
| runtime tmp | 24 hours |
| retained failed sources | 30 days |
| exports | 14 days |

Added:

- dry-run cleanup
- lifecycle-aware cleanup
- structured cleanup logging

### 6. Storage Lifecycle Modeling

Introduced explicit lifecycle states:

```text
uploaded
processing
processed
failed
retained
archived
deleted
```

Lifecycle is now easier to reason about operationally.

### 7. WAL-Safe SQLite Backup Tooling

Added executable backup commands:

```bash
python -m app.cli.backup_sqlite
python -m app.cli.verify_backup
```

Using:

- SQLite backup API
- integrity verification
- WAL-safe handling

Avoids unsafe live file-copy workflows.

---

## Verification Completed

Local verification executed successfully on macOS:

### Alembic

```bash
APP_ENV=development python -m alembic upgrade head
```

Passed.

### Ruff

```bash
APP_ENV=development ruff check app tests migrations
```

Passed.

### Pytest

```bash
APP_ENV=testing pytest
```

Result:

```text
79 passed, 5 warnings
```

Warnings are currently limited to third-party SWIG deprecation warnings.

No functional failures.

### SQLite Backup Verification

```bash
APP_ENV=development python -m app.cli.backup_sqlite
APP_ENV=development python -m app.cli.verify_backup
```

Result:

```text
integrity_check=ok
```

Backup/verify flow confirmed operational.

---

## Git Status

Committed:

```text
596f327 feat: add storage hardening foundation
```

`.gitignore` updated to exclude:

```text
data/backups/
```

Current unresolved workflow decision:

```text
uv.lock
```

still untracked and pending policy decision.

---

## Current Technical Debt

Still remaining after v0.9.6:

### Storage

- `moved_to_path` still partially used
- not all artifact categories are content-addressable yet
- export download routes still partially coupled to filesystem assumptions

### Lifecycle

- lifecycle states not fully exposed in UI/admin views
- no lifecycle audit history yet

### Storage Backend

- storage abstraction still `localfs`-only
- no blob reference table yet
- no object-storage backend yet

### Operational

- no automated scheduled backup rotation yet
- no storage metrics dashboard yet
- no disk-pressure monitoring yet

### Tooling

- `uv.lock` policy unresolved

---

## Recommended Next Phase

Recommended next milestone:

```text
v0.9.7-storage-integration-and-operational-qa
```

Focus should NOT be large new features.

Focus SHOULD be:

- integrating storage abstraction everywhere
- removing remaining raw path coupling
- backup/restore drills
- operational QA
- lifecycle visibility
- cleanup observability
- storage metrics
- safer export/download integration

---

## Important Architectural Direction

Current strategy remains intentionally conservative:

- SQLite-first
- single-node operational architecture
- predictable runtime behavior
- boring infrastructure
- maintainable operational design

Avoid introducing:

- Kubernetes
- distributed queues
- microservices
- premature orchestration complexity

The project is currently succeeding because complexity remains controlled.

---

## Operational Assessment

OLRE is now approaching:

```text
stateful operational application maturity
```

rather than:

```text
prototype PDF-processing application
```

The architecture now has:

- reproducible runtime behavior
- reproducible storage identity
- deterministic cleanup behavior
- deterministic backup handling
- runtime-profile awareness
- lifecycle-aware persistence

This is a substantial operational maturity improvement over earlier phases.
