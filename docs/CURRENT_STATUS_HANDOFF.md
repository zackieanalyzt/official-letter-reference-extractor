# OLRE Current Status and Handoff

Date: 2026-05-20
Branch: `release/v0.9.8-controlled-pilot`
Maturity: controlled operational pilot

## Executive Summary

Official Letter Reference Extractor (OLRE) is now beyond a prototype utility. It is a SQLite-first, single-node, server-rendered operational application for importing official PDFs, extracting QR/URL references, resolving references, exporting structured results, and preserving operational provenance.

The current release recommendation remains:

```text
Ready for controlled pilot use.
Not recommended for broad unattended rollout yet.
```

OLRE's strategic direction is:

```text
Operational Document Intelligence Platform
```

It is not an AI-first crawler platform.

## Operating Principles

All major changes should be reviewed against these principles:

- deterministic behavior preserved
- append-only history preserved where lifecycle/audit events are involved
- provenance preserved or improved
- operator visibility improved in practical ways
- complexity did not grow faster than operational trust
- taxonomy and naming consistency improved

Preferred system posture:

```text
trust first
complexity later
```

## Current Runtime Model

Current baseline runtime:

```text
SQLite-first
single-node
server-rendered operational application
Docker single-container deployment
default runtime port 7777
```

Typical Linux deployment path:

```text
/opt/official-letter-reference-extractor
```

PostgreSQL remains a possible future/heavier deployment profile, but the controlled-pilot baseline is SQLite-first.

## Implemented Capability Summary

Core extraction and operations:

- PDF batch import
- QR extraction
- URL extraction
- URL resolution
- duplicate detection
- retry handling
- export system
- quality reporting
- operational dashboards
- Thai/English UI

Lifecycle Registry, completed in v0.9.8 Epic 1:

- lifecycle event taxonomy
- lifecycle metadata conventions
- append-only lifecycle events
- lifecycle consistency validation
- lifecycle visibility UI/API
- lifecycle timeline rendering
- retry chain grouping
- cleanup lifecycle completion
- lifecycle governance ADR/docs

The key lifecycle invariant is:

```text
documents.lifecycle_state = materialized operational projection
document_lifecycle_events = append-only source of truth
```

Runtime/Ops Visibility, completed in v0.9.8 Epic 2:

- runtime introspection APIs
- orphan detection
- lifecycle consistency summary
- operational diagnostics
- server-rendered ops pages
- storage consistency reporting
- readiness/runtime validation

Key routes:

```text
/ops
/ops/runtime
/ops/storage/orphans
/ops/lifecycle/consistency-summary
```

Release identity layer:

- centralized release metadata system
- dynamic release information panel
- environment/config-driven release metadata
- release visibility on landing page
- Thai/English release labels

Release strings must not be hardcoded in templates.

## Epic 3 Current Status

Epic 3 is Recursive Linked Document Extraction, but the approved shape is controlled reference traversal, not crawling.

Completed:

- Phase 1: docs-only traversal architecture freeze
- Phase 2A: traversal planning runtime

Phase 2A added planning-only runtime support:

- `reference_traversals` model and migration
- traversal classifier
- traversal policy layer
- traversal security checks
- traversal planner
- traversal planning persistence
- traversal lifecycle planning events
- traversal policy config
- traversal visibility APIs/UI

Key traversal routes:

```text
/documents/{id}/traversal
/documents/{id}/traversal/view
/ops/traversal
```

Current traversal guarantees:

- no downloader
- no URL following for traversal
- no child document creation
- no recursive processing
- no background traversal worker
- no HTML crawling
- no network-dependent traversal tests
- traversal remains planning-only

Default traversal config:

```env
TRAVERSAL_ENABLED=false
TRAVERSAL_MAX_DEPTH=1
```

## Traversal Boundary

OLRE traversal is:

```text
controlled
bounded
deterministic
policy-driven
operator-visible
provenance-preserving
```

OLRE traversal is not:

```text
general internet crawler
autonomous scraping platform
recursive web spider
AI knowledge graph engine
```

Implemented/planned guardrails:

- max depth = 1 by default
- private IP blocking
- loopback blocking
- link-local blocking
- multicast/non-routable blocking
- unsupported scheme rejection
- content-type restrictions
- deterministic policy evaluation
- provenance invariants
- no automatic recursion

## Production Readiness State

Latest documented production-readiness validation:

```text
docs/production_readiness_validation_v0.9.8.md
```

Validation summary:

- batch workflows verified
- exports verified
- lifecycle/ops verified
- corrupted PDF handling verified
- duplicate ingestion reference-count fix implemented
- no full-batch abort observed

Reported verification state after traversal planning runtime:

```text
ruff passed
pytest 121 passed, 6 warnings
```

Residual operational risk estimate:

```text
~5-6%
```

Main remaining risks:

- real-world corpus variance
- edge-case document numbering
- runtime/performance variance
- limited field feedback from pilot operators

## Immediate Next Step

Do not jump to AI/RAG/distributed systems yet.

Immediate priority:

```text
Operational validation of traversal planning runtime
```

Validation checklist:

- deploy latest `release/v0.9.8-controlled-pilot` branch on Linux server
- rebuild container
- run database migration
- verify traversal UI/API
- confirm traversal remains inert
- confirm no downloader side effects
- confirm no child document creation
- confirm lifecycle/ops remain stable
- collect pilot operator feedback

## Explicitly Deferred

Not approved yet:

- automatic recursive traversal
- downloader execution runtime
- background traversal workers
- event bus
- distributed queues
- object storage migration
- HTML crawling
- AI semantic traversal
- vector database
- RAG
- autonomous ingestion
- microservices
- telemetry stack

## Recommended New-Chat Starting Point

Start by reading:

1. `docs/CURRENT_STATUS_HANDOFF.md`
2. `docs/TRAVERSAL_ARCHITECTURE.md`
3. `docs/TRAVERSAL_POLICY.md`
4. `docs/status_v0.9.8_epic3_traversal_planning.md`
5. `docs/production_readiness_validation_v0.9.8.md`

Then inspect the current code before planning further work. The next work should validate Phase 2A operationally before implementing any downloader or recursive behavior.
