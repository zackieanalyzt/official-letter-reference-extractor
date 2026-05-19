# OLRE Epic 3: Reference Traversal Engine Architecture

## Position

**OLRE traversal is not a crawler.**

Epic 3 introduces controlled linked-document traversal for official-letter references that OLRE has already extracted from PDFs through QR codes, short URLs, direct PDF URLs, or other downloadable references. It must not discover arbitrary web links, expand HTML pages, run autonomous crawling, or behave like a search engine.

Phase 1 is architecture lock-in only. It does not add downloader code, URL following, recursive processing, background jobs, migrations, runtime models, public endpoints, or runtime behavior.

The target capability for later phases is:

```text
PDF A
-> extract QR/URL
-> resolve URL
-> identify linked PDF candidate
-> operator-triggered single-depth traversal
-> preserve provenance and policy decision
```

## Design Principles

Traversal must remain:

- deterministic
- append-only where events are recorded
- auditable
- policy-controlled
- operator-visible
- bounded

The system optimizes for operational trust, traceability, and predictable behavior. It does not optimize for maximum recursion.

## Core Concepts

- **Traversable reference**: an extracted `document_references` row whose raw or resolved URL is eligible for controlled traversal planning.
- **Linked document candidate**: a downstream document target derived from one extracted reference.
- **Parent document**: the source `documents` row that contained the reference.
- **Child document**: a later `documents` row created from a linked document candidate, if traversal is manually executed in a future phase.
- **Traversal provenance**: the audit chain tying a candidate or child document back to the exact parent document and source reference.
- **Traversal policy**: centralized rules that decide whether a candidate may be planned, skipped, rejected, or later downloaded.
- **Traversal depth**: the number of controlled link hops from an originally imported document.

## Provenance Invariant

Every linked document candidate must trace back to exactly one `parent_document_id` and one `source_reference_id`.

There must be no child document or traversal candidate with unknown origin. If a downstream file is ever imported in a later phase, the system must always answer:

```text
Which parent document produced this child?
Which extracted reference produced this child?
Which policy decision allowed or blocked traversal?
```

## Traversable Reference Classification

Traversal planning starts only from already-extracted references. It must not parse HTML pages or discover additional links.

| Target type | Traversable | Phase 1 meaning |
| --- | --- | --- |
| `pdf_url` | yes | Direct PDF URL candidate |
| `known_short_url` | maybe | Candidate only after policy checks; no follow in Phase 1 |
| `html_page` | no | Unsupported; no HTML crawling or link expansion |
| `image_url` | no | Unsupported |
| `malformed_url` | no | Unsupported |
| `unsupported_scheme` | no | Unsupported |
| `unknown` | no | Unsupported until explicitly classified |

Candidate source URL should prefer `document_references.final_url` when available, otherwise `document_references.raw_reference`.

## Traversal Status Taxonomy

The proposed status model is:

| Status | Meaning |
| --- | --- |
| `NOT_FOLLOWED` | Candidate identified but no traversal action has been taken |
| `QUEUED` | Future manual traversal was requested but not yet executed |
| `SKIPPED_BY_POLICY` | Policy rejected the candidate |
| `UNSUPPORTED` | Target type, scheme, content type, or URL shape is unsupported |
| `DOWNLOADED` | Future phase downloaded the linked document |
| `DUPLICATE` | Future phase detected an existing document by SHA-256 |
| `PROCESSED` | Future phase processed the linked document through OLRE |
| `FAILED` | Future phase attempted traversal and failed |
| `DEPTH_LIMIT_REACHED` | Traversal would exceed the configured depth limit |

Phase 1 only documents this taxonomy. It does not emit these statuses at runtime.

## Proposed Persistence Model

Phase 2 should add one primary provenance table rather than a graph subsystem:

```text
reference_traversals
```

Proposed fields:

| Field | Purpose |
| --- | --- |
| `id` | Primary key |
| `parent_document_id` | Source `documents.id` |
| `source_reference_id` | Source `document_references.id` |
| `child_document_id` | Linked `documents.id`, nullable until a child exists |
| `raw_url` | Reference URL before resolution or normalization |
| `resolved_url` | Final URL used for classification/planning, nullable |
| `traversal_depth` | Hop depth from the original imported document |
| `traversal_status` | Status from the traversal taxonomy |
| `target_type` | Classification such as `pdf_url` or `known_short_url` |
| `content_type` | Observed content type in future phases, nullable |
| `content_length_bytes` | Observed size in future phases, nullable |
| `policy_decision` | `allowed`, `blocked`, `unsupported`, or `not_evaluated` |
| `policy_reason` | Human-readable policy reason, nullable |
| `error_type` | Stable error code, nullable |
| `error_detail` | Operator-readable error detail, nullable |
| `created_at` | Creation timestamp |
| `updated_at` | Last update timestamp |

Proposed indexes:

- `(parent_document_id, traversal_depth)`
- `(source_reference_id)`
- `(child_document_id)`
- `(traversal_status)`
- unique `(parent_document_id, source_reference_id, resolved_url)` where supported by the active database backend

The table should not replace `document_references`; it adds traversal planning and provenance on top of already-extracted references.

## Lifecycle Additions

Proposed non-state lifecycle event additions for a later implementation phase:

- `TRAVERSAL_CANDIDATE_DETECTED`
- `TRAVERSAL_SKIPPED`
- `TRAVERSAL_DEPTH_LIMIT_REACHED`
- `LINKED_DOCUMENT_DOWNLOADED`
- `LINKED_DOCUMENT_DUPLICATE`
- `TRAVERSAL_FAILED`

These should be classified under a new lifecycle family such as `traversal`. They should not mutate the document lifecycle state unless a later design explicitly introduces stateful traversal transitions.

Recommended metadata for traversal lifecycle events:

- `traversal_id`
- `parent_document_id`
- `source_reference_id`
- `child_document_id`
- `traversal_depth`
- `traversal_status`
- `target_type`
- `policy_decision`
- `policy_reason`

## Visibility Design

Future visibility endpoints should be read-only unless Phase 2 explicitly adds a manual action endpoint.

Proposed endpoints:

```text
GET /documents/{id}/traversal
GET /ops/traversal
```

`GET /documents/{id}/traversal` should show:

- parent document metadata
- each source reference considered for traversal
- resolved URL if known
- target classification
- policy decision and reason
- traversal status
- child document link if one exists

`GET /ops/traversal` should show:

- candidate counts by status
- candidates blocked by policy reason
- depth-limit counts
- duplicate linked document counts
- failed traversal counts in future phases

Minimal UI should be server-rendered and table/tree oriented, for example:

```text
Document A
|- QR #1 -> PDF candidate
|  status: NOT_FOLLOWED
|- QR #2 -> unsupported
|  status: UNSUPPORTED
|- QR #3 -> blocked by policy
   status: SKIPPED_BY_POLICY
```

No graph visualization framework is required.

## Storage Model

Future linked-document files must use a controlled runtime area, for example:

```text
/app/data/runtime/linked-documents
```

or local development equivalent:

```text
data/runtime/linked-documents
```

Linked downloads must not be written directly into the normal import inbox. A future Phase 2 downloader should place temporary linked files in traversal storage, fingerprint them, apply policy, detect duplicates, and only then create or associate document records.

## Phase 2 Entry Criteria

Phase 2 may start only when:

- Phase 1 docs are reviewed
- security guardrails are approved
- provenance model is approved
- policy config defaults are approved
- there is no objection to the proposed schema
- the controlled pilot branch remains stable

## Phase 2 Implementation Sequence

Phase 2 should implement **manual single-depth operator-triggered traversal** only. It must not implement automatic recursive crawling.

Recommended sequence:

1. Add traversal settings with `TRAVERSAL_ENABLED=false` and `TRAVERSAL_MAX_DEPTH=1`.
2. Add migration and ORM model for `reference_traversals`.
3. Add classifier and policy services without downloader side effects.
4. Add plan creation from existing resolved references.
5. Add read-only `/documents/{id}/traversal` and `/ops/traversal` visibility.
6. Add minimal server-rendered traversal UI.
7. Add manual operator action for depth-1 traversal only, still default disabled.
8. Add downloader behind the manual action and policy gates.
9. Add no-internet tests using mocks or local fixtures only.

## Phase 1 Non-Goals

Phase 1 does not include:

- downloader
- URL following
- recursive processing
- background jobs
- event bus
- auto traversal
- HTML crawling
- internet-dependent tests
- migration
- runtime model
- public runtime behavior

