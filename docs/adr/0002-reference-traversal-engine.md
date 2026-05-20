# ADR 0002: Reference Traversal Engine Foundation

## Status

Accepted for Epic 3 Phase 1. Extended by Epic 3 Phase 2A traversal planning runtime.

## Context

OLRE extracts references from official-letter PDFs through text, QR codes, URL resolution, and destination classification. Some extracted references point to downstream PDFs or downloadable official documents. Operators need a way to understand and eventually process those linked documents while preserving provenance and safety.

**OLRE traversal is not a crawler.**

The system must support controlled linked-document traversal from references that OLRE has already extracted. It must not become an internet crawler, HTML scraping platform, distributed document graph, autonomous ingestion system, or search engine.

The main architectural risk is implementing a downloader before the provenance model, policy boundary, and security guardrails are reviewed. That would pull OLRE toward uncontrolled crawling behavior.

## Decision

Build Epic 3 Phase 1 as a docs-only architecture foundation for a future Reference Traversal Engine, then implement Phase 2A as planning runtime only.

Phase 1 locked:

- controlled linked-document traversal terminology
- proposed `reference_traversals` persistence model
- traversal status taxonomy
- provenance invariant
- centralized policy defaults
- security boundary
- storage model
- lifecycle and visibility design
- Phase 2 implementation sequence

Phase 1 did not add runtime behavior.

Phase 2A adds:

- `reference_traversals` persistence
- traversal classifier
- traversal policy/security checks
- traversal planner
- traversal lifecycle planning events
- read-only document and ops visibility

Phase 2A does not add downloader behavior, URL following for traversal, recursive processing, background jobs, child document creation, or HTML crawling.

## Provenance Invariant

Every linked document candidate must trace back to exactly one `parent_document_id` and one `source_reference_id`.

No child document may be created through traversal without a known parent document and source reference. Provenance is mandatory, not optional metadata.

## Policy Defaults

Future traversal must start from strict defaults:

```env
TRAVERSAL_ENABLED=false
TRAVERSAL_MAX_DEPTH=1
```

Traversal must not run automatically by default.

## Security Boundary

Future traversal must:

- block private IP targets
- block loopback targets
- block link-local targets
- block unsupported schemes
- enforce timeout
- enforce file size cap
- enforce content type
- support optional domain allowlist
- avoid HTML link expansion

Only controlled linked-document traversal from already-extracted references is in scope.

## Non-Goals

Phase 1 did not include, and Phase 2A still does not include:

- downloader
- URL following
- recursive processing
- background job
- event bus
- auto traversal
- HTML crawling
- internet-dependent tests
- child document creation

The broader Epic 3 also does not aim to create:

- unrestricted recursive crawling
- distributed document graph system
- semantic AI graph
- vector database workflow
- autonomous web scraping platform

## Consequences

Positive:

- Architecture, provenance, and security can be reviewed before network side effects exist.
- OLRE keeps its current strength: predictable operational intelligence.
- Future implementation can be tested without internet dependency.
- Operators will get auditable traversal status rather than hidden downloads.

Tradeoffs:

- Phase 2A still does not deliver linked-document downloading.
- Runtime now has planning records and visibility, so future downloader work must preserve existing planning/provenance semantics.
- Some target types, especially HTML pages, remain unsupported even if they contain PDF links.

## Phase 2B Entry Criteria

Downloader/runtime execution may begin only when:

- Phase 2A is deployed and operationally validated on the Linux pilot server
- `reference_traversals` migration is applied successfully
- traversal UI/API are reviewed by operators
- no downloader side effects are observed
- no child document creation is observed
- lifecycle/ops consistency remains stable after traversal planning
- the controlled pilot branch remains stable

## Downloader Rule

If a future phase adds a downloader, it must be:

```text
manual single-depth operator-triggered traversal
```

It must not be automatic recursive crawl behavior. It must remain policy-gated, disabled by default, bounded to depth 1, and observable by operators.

## Related Documents

- `docs/TRAVERSAL_ARCHITECTURE.md`
- `docs/TRAVERSAL_POLICY.md`
- `docs/LIFECYCLE_EVENT_TAXONOMY.md`
- `docs/LIFECYCLE_METADATA_CONVENTIONS.md`
