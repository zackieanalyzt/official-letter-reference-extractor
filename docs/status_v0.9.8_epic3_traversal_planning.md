# OLRE v0.9.8 Epic 3 Phase 2A - Traversal Planning Runtime

Date: 2026-05-20
Status: implemented as planning runtime only

## 1. Scope Implemented

Epic 3 Phase 2A implements traversal planning, persistence, policy evaluation, and visibility for already-extracted document references.

This phase intentionally stops before downloading or following linked documents.

Implemented:

- `reference_traversals` table and ORM model
- migration `20260519_0012_add_reference_traversals.py`
- traversal URL classifier
- traversal policy evaluator
- traversal security helpers
- traversal planner
- planning persistence with idempotent update behavior
- traversal lifecycle events for planning outcomes
- document-level traversal JSON/API visibility
- document-level traversal server-rendered page
- ops-level traversal summary API
- no-network traversal tests

## 2. Routes Added

Document traversal JSON:

```text
GET /documents/{document_id}/traversal
```

Document traversal page:

```text
GET /documents/{document_id}/traversal/view
```

Ops traversal summary:

```text
GET /ops/traversal
```

The `/results` UI links document rows to the traversal view.

## 3. Runtime Guarantees

Phase 2A is planning-only.

Guaranteed non-goals in the implementation:

- no downloader
- no network traversal
- no child document creation
- no recursive processing
- no background traversal worker
- no HTML crawling
- no automatic traversal execution
- no internet-dependent tests

`TRAVERSAL_ENABLED=false` remains the default. When disabled, eligible references can still be planned and recorded as skipped by policy, but no traversal action is executed.

## 4. Configuration

Relevant settings:

```env
TRAVERSAL_ENABLED=false
TRAVERSAL_MAX_DEPTH=1
TRAVERSAL_MAX_DOCUMENTS_PER_BATCH=20
TRAVERSAL_ALLOWED_CONTENT_TYPES=application/pdf
TRAVERSAL_TIMEOUT_SECONDS=15
TRAVERSAL_MAX_DOWNLOAD_MB=20
TRAVERSAL_ALLOWED_DOMAINS=
TRAVERSAL_BLOCK_PRIVATE_IPS=true
TRAVERSAL_STORAGE_DIR=/app/data/runtime/linked-documents
```

The storage directory is present for runtime readiness and future staging design. Phase 2A does not download files into it.

## 5. Planning Behavior

The planner evaluates already-extracted `document_references` only.

Candidate URL selection:

```text
document_references.final_url
-> fallback to document_references.raw_reference
```

The planner records:

- parent document ID
- source reference ID
- raw URL
- resolved URL
- traversal depth
- traversal status
- target type
- policy decision
- policy reason
- optional error fields

Planning is idempotent for the same parent/source/raw URL combination.

## 6. Lifecycle Integration

Phase 2A emits planning lifecycle events only:

- `TRAVERSAL_CANDIDATE_DETECTED`
- `TRAVERSAL_SKIPPED`
- `TRAVERSAL_DEPTH_LIMIT_REACHED`

These events are non-state traversal events. They do not replace or mutate the core document lifecycle state machine.

## 7. Operator Visibility

Document-level visibility shows:

- traversal planning summary
- source reference
- raw/resolved URL
- target type
- traversal status
- policy decision and reason
- depth
- child document placeholder, currently always null

Ops-level visibility summarizes:

- total traversal rows
- counts by traversal status
- counts by policy decision
- counts by target type

## 8. Verification

Targeted test coverage includes:

- classifier behavior
- policy decisions
- private/local address blocking
- depth limit behavior
- planning persistence
- idempotent planning
- lifecycle planning events
- traversal API/page rendering
- ops summary
- no network-client imports in traversal modules
- migration/table/index presence

Reported full-suite state after this phase:

```text
ruff passed
pytest 121 passed, 6 warnings
```

## 9. Next Operational Validation

Before any downloader phase, validate Phase 2A on the Linux controlled-pilot server:

- rebuild and deploy the container
- run `alembic upgrade head`
- confirm `reference_traversals` exists
- open `/documents/{id}/traversal/view` for documents with references
- open `/documents/{id}/traversal`
- open `/ops/traversal`
- confirm no network/download side effects
- confirm no child documents are created
- confirm lifecycle consistency remains stable
- confirm `/ops/runtime` reports traversal storage readiness

Only after this validation should a future Phase 2B downloader proposal be considered.
