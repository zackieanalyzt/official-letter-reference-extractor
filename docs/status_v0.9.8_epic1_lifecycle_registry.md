# OLRE v0.9.8 Epic 1 — Lifecycle Registry

## Phase 1 Foundation + Phase 2 Lifecycle Visibility & Consistency

Date: 2026-05-14

## 1. Executive Summary

Epic 1 changed OLRE from a system that had operational status spread across current document fields, retry behavior, retention side effects, and logs into a system with:

- operational memory
- append-only lifecycle history
- document-level lifecycle visibility
- consistency-verifiable lifecycle infrastructure

Phase 1 established the lifecycle registry foundation:

- append-only lifecycle events
- lifecycle state projection
- transition validation
- helper layer
- same-transaction lifecycle correctness
- main flow and retry flow integration

Phase 2 made that lifecycle memory operationally usable:

- readable timeline narrative
- document-level consistency validation
- retention/cleanup lifecycle completion
- server-rendered lifecycle page
- governance documents for taxonomy and metadata

The result is still intentionally simple:

- synchronous
- SQLite-compatible
- document-level
- deterministic
- audit-oriented

This is not an event bus, telemetry stack, replay engine, or distributed lifecycle platform.

## 2. Current Branch / Version Context

- Current branch at time of writing: `hardening/runtime-profiles-backup-and-storage`
- Base milestone before lifecycle work: `v0.9.7-storage-integration`
- Target milestone for this work: `v0.9.8 Epic 1 — Lifecycle Registry`
- Lifecycle migration id: `20260510_0011_add_document_lifecycle_events`
- Document date: `2026-05-14`

Note:

The branch name at the tagged milestone does not fully describe the logical milestone. Lifecycle work for `v0.9.8` is represented by the tag `v0.9.8-epic1-lifecycle-registry` and should be reviewed as the Epic 1 lifecycle handoff baseline.

## 3. Architectural Principle

Core principle:

```text
documents.lifecycle_state = materialized operational projection
document_lifecycle_events = append-only source of truth
```

Interpretation:

- `document_lifecycle_events` stores committed operational history.
- `documents.lifecycle_state` exists for efficient query/UI access.
- lifecycle history must not be overwritten or treated as mutable status logging.
- lifecycle writes are correctness-critical, not optional logging.

Operational implications:

- if the main operation fails, the lifecycle write must not remain committed by itself
- if the lifecycle write fails, the operational mutation must not commit without it
- lifecycle history should remain usable for audit, replay reasoning, debugging, and timeline visibility later

## 4. Phase 1 — Lifecycle Registry Foundation

Phase 1 implemented the lifecycle foundation layer.

Delivered:

- Alembic migration for lifecycle table
- `document_lifecycle_events` table
- ORM model
- `app/lifecycle` module
- lifecycle states, events, and constants
- transition validation
- lifecycle service helpers
- projection update policy
- main processing flow integration
- retry flow integration
- JSON timeline API

Key behavior added in Phase 1:

- events are appended during processing
- retry chain operations are recorded
- lifecycle projection is updated through helper logic
- same-transaction correctness is enforced

Primary files changed in Phase 1:

- `app/lifecycle/__init__.py`
- `app/lifecycle/events.py`
- `app/lifecycle/states.py`
- `app/lifecycle/service.py`
- `app/lifecycle/validation.py`
- `app/lifecycle/projection.py`
- `app/db/models.py`
- `app/services/process_batch.py`
- `app/services/retry_service.py`
- `app/web/routes_operations.py`
- `migrations/versions/20260510_0011_add_document_lifecycle_events.py`
- `tests/unit/test_lifecycle_validation.py`
- `tests/unit/test_lifecycle_service.py`
- `tests/integration/test_lifecycle_registry.py`

## 5. Phase 2 — Lifecycle Visibility & Consistency

Phase 2 extended the foundation into an operator-usable lifecycle layer.

Delivered:

- lifecycle presentation layer
- operator-readable timeline
- server-rendered lifecycle page
- consistency validator
- `PASS/WARNING/ERROR/CRITICAL` severity model
- taxonomy governance
- metadata governance
- cleanup lifecycle completion
- extended lifecycle API
- Thai/English labels for lifecycle visibility

Primary files changed in Phase 2:

- `app/lifecycle/taxonomy.py`
- `app/lifecycle/metadata.py`
- `app/lifecycle/consistency.py`
- `app/lifecycle/presentation.py`
- `app/services/retention_service.py`
- `app/web/routes_operations.py`
- `app/web/templates/document_lifecycle.html`
- `app/web/templates/results.html`
- `app/i18n/en.py`
- `app/i18n/th.py`
- `docs/LIFECYCLE_EVENT_TAXONOMY.md`
- `docs/LIFECYCLE_METADATA_CONVENTIONS.md`
- `docs/adr/0001-lifecycle-registry.md`
- `tests/unit/test_lifecycle_consistency.py`
- `tests/unit/test_lifecycle_presentation.py`
- `tests/integration/test_ui_flow.py`
- `tests/integration/test_storage_hardening.py`

## 6. New Runtime Behavior

New behavior introduced by Epic 1:

- lifecycle events are emitted during document processing
- retry chains are correlated by `correlation_id`
- cleanup success emits `DOCUMENT_CLEANED` only after successful delete plus projection update
- timeline API now includes raw timeline data, presentation data, and consistency data
- lifecycle consistency can detect projection drift
- metadata is filtered through centralized conventions before write
- ad-hoc event names are controlled through centralized taxonomy
- lifecycle visibility is available in a server-rendered document page

Important runtime properties preserved:

- append-only history remains untouched by presentation logic
- lifecycle ordering remains deterministic: `occurred_at ASC`, then `id ASC`
- lifecycle write path remains synchronous
- no background daemon, event bus, or automatic reconciliation was introduced

## 7. Lifecycle Event Examples

### Successful document

```text
DOCUMENT_UPLOADED
DOCUMENT_QUEUED
DOCUMENT_PROCESSING_STARTED
DOCUMENT_VALIDATED
DOCUMENT_EXTRACTION_COMPLETED
DOCUMENT_RESOLUTION_COMPLETED
```

### Failed retained document

```text
DOCUMENT_UPLOADED
DOCUMENT_QUEUED
DOCUMENT_PROCESSING_STARTED
DOCUMENT_FAILED
DOCUMENT_RETAINED
```

### Retry chain

```text
DOCUMENT_FAILED
DOCUMENT_RETRY_REQUESTED
DOCUMENT_RETRY_STARTED
DOCUMENT_QUEUED
DOCUMENT_PROCESSING_STARTED
DOCUMENT_VALIDATED
DOCUMENT_EXTRACTION_COMPLETED
DOCUMENT_RESOLUTION_COMPLETED
DOCUMENT_RETRY_COMPLETED
```

### Cleaned retained document

```text
DOCUMENT_RETAINED
DOCUMENT_CLEANED
```

## 8. API / UI Added

Endpoints added or extended:

### `GET /documents/{id}/lifecycle`

Purpose:

- return document lifecycle timeline as JSON
- include raw timeline fields
- include presentation fields
- include grouped timeline chains
- include consistency result

### `GET /documents/{id}/lifecycle/consistency`

Purpose:

- return document-level consistency result only
- useful for focused support/debug checks
- avoids requiring the full timeline payload when only consistency is needed

### `GET /documents/{id}/lifecycle/view`

Purpose:

- render lifecycle history in server-rendered UI
- show current lifecycle state
- show consistency badge/status
- show readable event narrative
- show retry chain grouping
- show retention/cleanup visibility

UI behavior added:

- lifecycle timeline page
- consistency badge/status
- readable narrative per event
- retry chain grouping by `correlation_id`
- cleanup/retention visibility
- expandable raw metadata/details when present

## 9. Consistency Validation Model

Severity model:

### `PASS`

Meaning:

- projection matches lifecycle history
- no significant anomalies found

### `WARNING`

Meaning:

- unusual condition
- not immediately dangerous
- often legacy or partial-history condition

Example:

- old document with little or no lifecycle history

### `ERROR`

Meaning:

- operational inconsistency that reduces trust or diagnosis quality

Examples:

- projection mismatch
- incomplete retry chain
- retained state without usable source markers

### `CRITICAL`

Meaning:

- high-risk contradiction
- audit/recovery concern
- persisted history is impossible or strongly inconsistent

Examples:

- invalid transition history
- cleaned state while source is still marked present
- retained state with source expected but storage artifact missing

Current validator checks include:

- projection mismatch
- invalid transition history
- incomplete retry chain
- missing `correlation_id` in retry chains
- retained state without usable source
- cleaned state contradiction
- cleaned state without cleanup lifecycle event

## 10. Governance Documents Added

### `docs/LIFECYCLE_EVENT_TAXONOMY.md`

Purpose:

- freeze approved lifecycle event names
- define event families
- define allowed actors
- document severity semantics

### `docs/LIFECYCLE_METADATA_CONVENTIONS.md`

Purpose:

- constrain `metadata_json`
- define allowed keys per event
- prevent uncontrolled metadata growth
- keep metadata small and operational

### `docs/adr/0001-lifecycle-registry.md`

Purpose:

- record the architectural decision behind lifecycle registry
- explain why append-only history and projection separation were chosen
- document non-goals such as event bus or replay platform behavior

## 11. Verification Results

Latest verification:

```bash
APP_ENV=development uv run ruff check app tests migrations
```

Result:

```text
All checks passed!
```

And:

```bash
APP_ENV=testing uv run pytest
```

Result:

```text
94 passed
```

Relevant targeted lifecycle set also passed:

```bash
APP_ENV=testing uv run pytest \
  tests/unit/test_lifecycle_validation.py \
  tests/unit/test_lifecycle_service.py \
  tests/unit/test_lifecycle_consistency.py \
  tests/unit/test_lifecycle_presentation.py \
  tests/integration/test_lifecycle_registry.py \
  tests/integration/test_storage_hardening.py \
  tests/integration/test_ui_flow.py
```

Result:

```text
32 passed
```

## 12. Git Status / Commit Preparation Notes

Current worktree characteristics at the tagged Epic 1 handoff:

- contains Phase 1 lifecycle foundation changes
- contains Phase 2 lifecycle visibility/consistency changes
- still contains docs-only changes from previous rounds
- was not originally prepared as a clean, isolated Epic 1 sequence before handoff writing

Observed worktree includes:

- lifecycle code changes
- lifecycle docs/governance files
- earlier docs updates in files such as `README.md`, `docs/changelog.md`, `docs/ADMIN_GUIDE.md`, and related runtime/storage docs

Recommended commit breakdown:

```text
commit 1: feat: add lifecycle registry foundation
commit 2: feat: add lifecycle visibility and consistency checks
commit 3: docs: document lifecycle registry governance
commit 4: docs: update v0.9.8 status and changelog
```

Practical advice:

- separate pre-existing docs-only changes from lifecycle feature changes before commit if possible
- keep migration + model + lifecycle core together
- keep Phase 2 presentation/consistency/cleanup changes together
- keep governance/status docs in a docs-focused commit if a clean split is still practical

## 13. Known Limitations / Risks

Current limitations:

- not yet field-tested with real operators in day-to-day workflow
- no system-wide dashboard exists yet
- no runtime introspection dashboard exists yet
- no orphan detection/reporting foundation beyond document-level checks
- consistency validation is still document-level first
- metadata governance needs ongoing discipline to remain effective
- no stress test yet for high-volume lifecycle event growth or concurrent write pressure
- old documents may have empty lifecycle history because adoption is forward-only

Additional risk notes:

- current branch naming and logical milestone are misaligned
- worktree contains mixed historical changes, so commit hygiene matters
- consistency validation is read-only and intentionally conservative; it does not repair data

## 14. Recommended Next Steps

### Immediate

- prepare clean commit scope
- do a manual browser walkthrough of lifecycle page
- review lifecycle UI wording with operator perspective
- decide commit/tag strategy for `v0.9.8`
- update changelog/release notes

### Next Epic Candidate

```text
v0.9.8 Epic 2 — Runtime Introspection & Orphan/Consistency Reporting Foundation
```

Still avoid for now:

- distributed queues
- event bus
- telemetry stack
- dashboard platform
- semantic AI
- vector search

## 15. Handoff Summary for New Chat

Use this summary to start a new chat quickly:

```text
OLRE v0.9.8 Epic 1 Lifecycle Registry is implemented in two phases.

Completed:
- Phase 1 foundation: append-only lifecycle registry, lifecycle helpers, transition validation, projection model, main flow + retry integration, JSON lifecycle API
- Phase 2 visibility/consistency: presentation layer, consistency validator, cleanup lifecycle completion, lifecycle HTML page, metadata/taxonomy governance docs, Thai/English lifecycle labels

Verified:
- APP_ENV=development uv run ruff check app tests migrations -> All checks passed
- APP_ENV=testing uv run pytest -> 94 passed
- targeted lifecycle test set -> 32 passed

Current risks / limits:
- worktree still contains mixed changes from earlier rounds
- no field testing with operators yet
- consistency validation is document-level first
- old documents may have empty lifecycle history
- no dashboard/orphan-reporting layer yet

Recommended next step:
- prepare clean commit breakdown
- manual browser walkthrough
- then move to v0.9.8 Epic 2: Runtime Introspection & Orphan/Consistency Reporting Foundation
```
