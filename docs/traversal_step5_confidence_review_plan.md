# Step 5 Plan: Confidence-Gated Traversal Review

This document defines a planning-only design for OLRE Step 5.

Scope for this phase:

- design the confidence-gated traversal review layer
- preserve operator trust and auditability
- reduce manual review workload for obvious safe cases

Non-goals for this phase:

- no downloader execution
- no URL following
- no recursive traversal
- no child document creation
- no background traversal worker
- no HTML crawling
- no AI semantic traversal

## Product Intent

Step 5 should classify traversal candidates into four operational queues:

- `AUTO_ELIGIBLE`
- `REVIEW_REQUIRED`
- `BLOCKED`
- `UNCERTAIN`

The purpose is not to auto-fetch anything. It is to pre-sort candidates so operator effort is spent on exceptions instead of every reference.

## Current Architecture Fit

Step 5 should build on the existing reference-level pipeline rather than introducing a parallel traversal subsystem.

Current anchors:

- [DocumentReference](D:/home/github/official-letter-reference-extractor/app/db/models.py:111) already stores reference-level extraction and destination classification state.
- [create_document_reference](D:/home/github/official-letter-reference-extractor/app/batch/service.py:174) is the natural insertion point for initializing Step 5 planning fields.
- [extract_references_from_pdf](D:/home/github/official-letter-reference-extractor/app/batch/reference_extraction.py:320) already provides page number, source type, raw reference, OCR/QR issue context, and no-reference signaling.
- [classify_destination](D:/home/github/official-letter-reference-extractor/app/batch/destination_classification.py:41) already performs lightweight offline-safe destination typing and should remain one input into confidence scoring.
- [get_references](D:/home/github/official-letter-reference-extractor/app/services/results_service.py:133) and [results.html](D:/home/github/official-letter-reference-extractor/app/web/templates/results.html:1) already expose reference-level operational data for UI reuse.

This means Step 5 can stay deterministic and service-layer oriented without coupling fetch behavior into extraction.

## Recommended Data Model

Use a hybrid model:

1. Store current traversal planning state directly on `document_references`.
2. Store operator actions and transitions in a new append-only history table.

Reasoning:

- the current queue needs fast filtering and grouping from one row per reference
- operator actions must remain auditable without destructive overwrite
- this matches OLRE's storage and diagnostics rules better than keeping only mutable state or only event history

### Add to `document_references`

Recommended columns:

- `confidence_score INTEGER NULL`
- `risk_level TEXT NOT NULL DEFAULT 'MEDIUM'`
- `recommended_action TEXT NOT NULL DEFAULT 'REVIEW_REQUIRED'`
- `review_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'`
- `review_reason TEXT NULL`
- `evidence_summary TEXT NULL`
- `operator_decision TEXT NULL`
- `operator_note TEXT NULL`
- `reviewed_at DATETIME NULL`

Recommended indexes:

- `ix_document_references_recommended_action`
- `ix_document_references_review_status`
- `ix_document_references_risk_level`
- optional composite index on `recommended_action, review_status`

Recommended enum-like allowed values:

- `risk_level`: `LOW`, `MEDIUM`, `HIGH`, `BLOCKED`
- `recommended_action`: `AUTO_ELIGIBLE`, `REVIEW_REQUIRED`, `BLOCKED`, `UNCERTAIN`
- `review_status`: `NOT_REQUIRED`, `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `SKIPPED`

### New append-only table

Create `reference_traversal_reviews`.

Suggested columns:

- `id`
- `traversal_id`
- `review_status`
- `operator_decision`
- `operator_note`
- `reviewed_at`
- `created_at`
- `acted_by`
- `event_type`
- `event_detail`

Suggested foreign key:

- `traversal_id -> document_references.id`

Why a separate table is still needed even with fields on `document_references`:

- operator actions must remain append-only
- future approval/rejection cycles need history
- lifecycle metrics should not depend on parsing free-text logs

## Lifecycle Event Model

Do not overload `processing_logs` for the canonical Step 5 audit trail. It can still mirror important messages, but Step 5 needs structured review history.

Suggested event types:

- `TRAVERSAL_CONFIDENCE_EVALUATED`
- `TRAVERSAL_AUTO_ELIGIBLE`
- `TRAVERSAL_REVIEW_REQUIRED`
- `TRAVERSAL_BLOCKED_BY_POLICY`
- `TRAVERSAL_MARKED_UNCERTAIN`
- `TRAVERSAL_OPERATOR_APPROVED`
- `TRAVERSAL_OPERATOR_REJECTED`
- `TRAVERSAL_OPERATOR_SKIPPED`

Recommended rule:

- every state evaluation writes one structured event row
- every operator action writes one structured event row
- mutable fields on `document_references` reflect the latest current state only

## Confidence Model

### Score bands

- `80-100`: high confidence
- `50-79`: medium confidence
- `0-49`: low confidence

### Deterministic scoring inputs

Base scoring should come only from evidence already available offline:

- source type: `text`, `ocr`, `qr`
- count of candidate references on the document/page
- whether typed URL and QR agree or conflict
- URL parse validity
- scheme type
- host class
- destination classification
- QR failure evidence
- extraction issue presence
- invalid/corrupted PDF evidence
- page-level provenance

### Suggested scoring rubric

Start from `0` and add/subtract deterministically:

- `+45` if `raw_reference` is a syntactically valid `http` or `https` URL from native text
- `+35` if QR decode produced a syntactically valid `http` or `https` URL
- `+15` if `final_url` equals `raw_reference`
- `+10` if destination classification is `government` or `document`
- `+5` if only one candidate exists for the document
- `-15` if source is OCR-only
- `-20` if source requires redirect interpretation or shortlink logic
- `-25` if multiple independent candidates exist in the same document
- `-25` if QR and typed URL disagree
- `-30` if visible QR evidence exists without decode
- `-40` if URL is malformed or unsupported
- `-100` if invalid/corrupted PDF

Clamp final score to `0..100`.

This intentionally favors explainability over statistical cleverness.

## Risk Model

Risk should be derived separately from confidence.

Suggested rules:

- `BLOCKED` when unsupported scheme, private IP, loopback, link-local, malformed target, invalid PDF, or explicit policy rejection is present
- `HIGH` when destination is unresolved, redirect-like, shortlink-based, multi-candidate, or conflict-heavy
- `MEDIUM` when candidate is valid but still needs operator confirmation
- `LOW` only when evidence is deterministic and the target is ordinary `http/https` with no red flags

### Required offline-safe host checks

Before any future fetch phase, Step 5 should evaluate:

- private IPv4 ranges
- IPv6 loopback
- IPv6 link-local
- localhost
- direct loopback names
- malformed hosts

This logic belongs in a new pure function, not in fetch code.

## Recommended Action Rules

### `AUTO_ELIGIBLE`

Assign only when all are true:

- deterministic typed URL or QR decode exists
- scheme is `http` or `https`
- URL is syntactically valid
- target is not private IP, loopback, or link-local
- no unsupported scheme
- no broken-QR evidence
- no invalid file evidence
- no multi-target conflict
- `confidence_score >= 80`
- `risk_level = LOW`

Set:

- `recommended_action = AUTO_ELIGIBLE`
- `review_status = NOT_REQUIRED`

### `REVIEW_REQUIRED`

Assign when any are true:

- `confidence_score` is `50..79`
- redirect-like URL is present
- shortlink is present
- multiple QR or URL candidates exist
- QR and typed URL disagree
- destination type cannot be confirmed safely offline
- extraction came from weaker OCR/scan evidence but still produced a candidate

Set:

- `recommended_action = REVIEW_REQUIRED`
- `review_status = PENDING_REVIEW`

### `BLOCKED`

Assign when any are true:

- unsupported scheme
- private IP
- loopback
- link-local
- malformed URL
- dangerous or impossible target
- invalid/corrupted PDF
- explicit policy rejection

Set:

- `recommended_action = BLOCKED`
- `review_status = NOT_REQUIRED`

### `UNCERTAIN`

Assign when any are true:

- no confident QR decode
- no typed URL
- image quality is too poor
- evidence is incomplete
- offline-safe analysis cannot classify safely

Set:

- `recommended_action = UNCERTAIN`
- `review_status = PENDING_REVIEW`

## Evidence Summary Rules

`evidence_summary` should stay short and operator-friendly.

Good examples:

- `Page 1 typed URL matched a valid https government host`
- `QR decoded on page 2 but target is a shortlink`
- `Two conflicting traversal candidates found across pages 1 and 3`
- `Visible QR region detected but payload was not decoded`
- `PDF could not be opened; invalid artifact`

`review_reason` should explain the queue placement, not repeat every raw fact.

Good examples:

- `Shortlink requires operator review`
- `Unsupported scheme blocked by policy`
- `No deterministic traversal candidate was confirmed offline`

## Service Layer Design

Introduce a new planning service, for example:

- `app/services/traversal_review_service.py`

Recommended responsibilities:

- compute `confidence_score`
- compute `risk_level`
- compute `recommended_action`
- generate `evidence_summary`
- update current planning fields on `document_references`
- write append-only review history rows

Recommended pure-function helpers:

- `score_reference_candidate(reference, document_context, issues) -> int`
- `assign_risk_level(reference, score, evidence_flags) -> str`
- `assign_recommended_action(reference, score, risk_level, evidence_flags) -> str`
- `build_review_reason(...) -> str`
- `build_evidence_summary(...) -> str`

Recommended orchestration entrypoint:

- `evaluate_reference_traversal_review(session, reference_id, context)`

Important boundary:

- this service must not fetch URLs
- this service must not create child documents
- this service must not enqueue traversal jobs

## Batch Pipeline Integration

Step 5 should run after extraction and after any existing destination classification, but before any future fetch phase.

Suggested sequence inside the current pipeline:

1. extract references
2. persist `DocumentReference`
3. classify destination offline if possible
4. evaluate confidence/risk/recommended action
5. persist current planning state
6. write append-only lifecycle/review event

This keeps Step 5 entirely offline-safe.

## UI Plan

Create a dedicated page:

- `/ops/traversal`

Do not overload `/results` as the main review queue. Keep `/results` as broad reference reporting and use `/ops/traversal` for action-oriented review.

### Page sections

Grouped queues:

1. auto-eligible
2. needs review
3. blocked
4. uncertain

### Per-row display

- document name
- page number
- extracted URL or evidence label
- confidence score
- risk level
- recommended action
- review reason
- evidence summary
- current review status

### Filters

Suggested filters:

- recommended action
- review status
- risk level
- source type
- processing status
- file name
- domain
- date range

### Metrics panel

Add summary cards:

- total candidates
- auto-eligible count
- review-required count
- blocked count
- uncertain count
- approved count
- rejected count
- skipped count

Add analytics:

- estimated manual review reduction
- top review reasons
- top blocked reasons
- confidence distribution

Estimated manual review reduction formula:

- `(auto_eligible_count / total_candidates) * 100`

This is simple, explainable, and useful for pilot reporting.

## Operator Actions

Only `REVIEW_REQUIRED` and `UNCERTAIN` normally need operator action.

Supported actions:

- approve
- reject
- skip
- add note

Behavior:

- `APPROVED` updates current row state and writes `TRAVERSAL_OPERATOR_APPROVED`
- `REJECTED` updates current row state and writes `TRAVERSAL_OPERATOR_REJECTED`
- `SKIPPED` updates current row state and writes `TRAVERSAL_OPERATOR_SKIPPED`
- no action in Step 5 may trigger fetch, download, child document creation, or traversal execution

Recommended current-state updates:

- approve: `review_status = APPROVED`, `operator_decision = APPROVED`
- reject: `review_status = REJECTED`, `operator_decision = REJECTED`, `recommended_action = BLOCKED`
- skip: `review_status = SKIPPED`, `operator_decision = SKIPPED`

## API / Route Plan

Add routes alongside existing operational routes in [routes_operations.py](D:/home/github/official-letter-reference-extractor/app/web/routes_operations.py:1).

Suggested routes:

- `GET /ops/traversal`
- `POST /ops/traversal/{reference_id}/approve`
- `POST /ops/traversal/{reference_id}/reject`
- `POST /ops/traversal/{reference_id}/skip`
- optional `POST /ops/traversal/{reference_id}/note`

Keep them form-post friendly to match the current server-rendered UI style.

## Migration Plan

Recommended migration sequence:

1. add Step 5 current-state columns to `document_references`
2. add indexes for queue filtering
3. create `reference_traversal_reviews`
4. backfill current rows conservatively

Backfill policy:

- if a reference has no strong evidence yet, default to `REVIEW_REQUIRED` or `UNCERTAIN`
- do not infer `AUTO_ELIGIBLE` aggressively during migration
- invalid or malformed references may backfill to `BLOCKED`

This respects the project's backward-compatibility rule.

## Test Plan

### Unit tests

Add new unit coverage for:

- confidence scoring
- risk assignment
- recommended action assignment
- unsupported scheme blocked
- private IP blocked
- loopback blocked
- link-local blocked
- broken QR becomes `UNCERTAIN` or `REVIEW_REQUIRED` based on evidence
- duplicate candidate handling
- multi-candidate review requirement
- invalid PDF blocked or uncertain per policy decision

### Integration tests

Add integration coverage for:

- reference gets Step 5 fields after processing
- `/ops/traversal` groups rows into the four queues correctly
- approve/reject/skip writes append-only review event rows
- Step 5 does not download or follow URLs
- no child document is created
- no network call is made

### Regression constraints

Keep explicit tests that Step 5 remains planning-only:

- no invocation of URL resolution code during review evaluation
- no traversal worker starts
- no recursive extraction beyond the original PDF

## Recommended File-Level Rollout

Planning-only target files for a later implementation:

- [app/db/models.py](D:/home/github/official-letter-reference-extractor/app/db/models.py:111)
- `migrations/versions/<new_step5_revision>.py`
- `app/services/traversal_review_service.py`
- [app/services/results_service.py](D:/home/github/official-letter-reference-extractor/app/services/results_service.py:1)
- [app/services/analytics_service.py](D:/home/github/official-letter-reference-extractor/app/services/analytics_service.py:1)
- [app/services/ui_views.py](D:/home/github/official-letter-reference-extractor/app/services/ui_views.py:1)
- [app/web/routes_operations.py](D:/home/github/official-letter-reference-extractor/app/web/routes_operations.py:1)
- `app/web/templates/ops_traversal.html`
- [app/web/templates/base.html](D:/home/github/official-letter-reference-extractor/app/web/templates/base.html:1)
- [app/i18n/th.py](D:/home/github/official-letter-reference-extractor/app/i18n/th.py:1)
- `app/i18n/en.py`
- new tests under `tests/integration/` and `tests/unit/`

## Recommended Rollout Order

1. schema and append-only review table
2. pure scoring/risk/action service
3. pipeline evaluation write-path
4. read/query service for `/ops/traversal`
5. operator action routes
6. UI and metrics
7. integration and regression test hardening

This sequence keeps risk low and preserves runtime stability.

## Acceptance Mapping

The design passes the requested acceptance criteria only if implementation follows these rules:

- Step 5 remains planning-only in behavior
- no downloader behavior is introduced
- no network traversal is introduced
- no recursive behavior is introduced
- candidates are visibly separated into `AUTO_ELIGIBLE`, `REVIEW_REQUIRED`, `BLOCKED`, `UNCERTAIN`
- operator review is exception-based, not mandatory for all references
- every operator action is auditable in append-only history
- confidence, risk, and recommended action are visible in UI and query outputs
- tests explicitly prove no fetch, download, or child-document creation occurs

## Recommended Product Decision

For OLRE, the safest design is:

- current queue state on `document_references`
- append-only operator and lifecycle history in `reference_traversal_reviews`
- conservative scoring
- `AUTO_ELIGIBLE` reserved for only the clearest low-risk cases

That gives the product the intended commercial shape:

- automation for obvious cases
- human review for exceptions
- auditability for everything
