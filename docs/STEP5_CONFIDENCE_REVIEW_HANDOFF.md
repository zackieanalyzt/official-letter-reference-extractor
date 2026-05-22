# Step 5 Confidence Review Handoff

This document is the high-level handoff for the OLRE traversal review system after Step 5.

Step 5 exists because Steps 1-4 proved that traversal references in real Thai government PDFs are not clean enough for naive automation. The corpus contained broken QR codes, redirect-style targets, multiple QR candidates in the same packet, duplicate references under different filenames, weak scan quality, and invalid PDF artifacts. A fully manual approval workflow would slow operators down too much, but fully automatic traversal would erode trust. Step 5 was added to create a controlled middle layer: obvious cases can be pre-sorted, risky cases can be isolated, and every decision stays auditable.

## Why Confidence-Gated Review Exists

Steps 1-4 revealed several operational truths:

- not every extracted reference deserves the same treatment
- some references are structurally safe enough to skip future manual review
- some are risky enough to block before any fetch phase exists
- some remain too incomplete for safe classification
- manual review should be reserved for exceptions, not every document

The design therefore became confidence-gated rather than fully manual approval. OLRE now separates references into `AUTO_ELIGIBLE`, `REVIEW_REQUIRED`, `BLOCKED`, and `UNCERTAIN` before any future fetch behavior is considered.

## Why OLRE Remains Planning-Only

Step 5 does not perform downloader execution, URL following, recursive traversal, child document creation, or background traversal work. This remains intentional.

Reasons:

- the corpus still contains enough ambiguity that fetch automation would be hard to explain
- operator trust depends on seeing why a candidate was sorted into a queue before any external action is taken
- the system needs governance and audit discipline before network behavior expands

`AUTO_ELIGIBLE` does not mean auto-download. It means the candidate is likely safe enough to skip manual review later when a controlled fetch sandbox is introduced. Step 5 is still a planning and queueing layer, not a traversal executor.

## Why `BLOCKED` And `UNCERTAIN` Are Different

`BLOCKED` means the system found a concrete reason not to allow later traversal. Examples include unsupported schemes, malformed targets, loopback/private/link-local addresses, or invalid/corrupted PDFs.

`UNCERTAIN` means the system does not yet have enough evidence to classify confidently. It is not a policy rejection. It is an evidence insufficiency state.

This distinction matters operationally:

- `BLOCKED` should usually stop the candidate from future fetch phases unless a human overrides policy intentionally
- `UNCERTAIN` should remain visible for operator review or better evidence later

## Append-Only Review Philosophy

Step 5 separates current state from audit history.

- `document_references` stores the latest operational state
- `reference_traversal_reviews` stores append-only review and lifecycle events

This keeps the queue fast to query while preserving history for audit, troubleshooting, and future policy refinement. Operator actions are not destructive history rewrites.

## Architecture Overview

```text
DocumentReference
  ↓
TraversalReviewService
  ↓
confidence_score / risk_level / recommended_action
  ↓
/ops/traversal queue
  ↓
append-only review events
```

Current flow:

```text
Document
  ↓
Reference Extraction
  ↓
Destination Classification (existing offline-safe layer)
  ↓
Traversal Review Service
  ↓
Queue Placement
  ↓
Operator Exception Review
```

## Current Maturity

After Step 5, OLRE can now:

- persist confidence/risk/recommended action on each reference
- place references into operational queues
- expose `/ops/traversal` for human review
- record append-only approve/reject/skip/note events
- keep review exception-based instead of mandatory for all candidates

What it still does not do:

- fetch anything
- follow links
- traverse recursively
- create child documents
- run a traversal worker in the background

## Operator Review Philosophy

Operator review is exception handling, not the primary workflow.

Intended operational model:

- low-risk obvious cases become visible as `AUTO_ELIGIBLE`
- ambiguous but plausible cases become `REVIEW_REQUIRED`
- structurally unsafe or policy-rejected cases become `BLOCKED`
- evidence-poor cases remain `UNCERTAIN`

This reduces manual workload without pretending the system is already a crawler or autonomous agent.

## Current Limitations

- scoring is deterministic and conservative, not learned from production outcomes
- some scan-quality problems still collapse into `UNCERTAIN`
- broken QR evidence remains common enough that offline confidence can be limited
- queue decisions depend on extracted evidence already present in OLRE; Step 5 does not improve the raw extraction layer by itself
- `/ops/traversal` is intentionally a review console, not a fetch console

## Next-Phase Recommendations

- introduce a controlled single-depth fetch sandbox only after Step 5 queue behavior is stable
- add richer queue metrics and operator reporting once review volume is observed in practice
- refine review heuristics with actual operator feedback, but keep rules explainable
- preserve the distinction between policy block, uncertain evidence, and review-required ambiguity
- continue resisting generic crawler behavior; OLRE should stay document-governed and operator-auditable

## Practical Handoff Summary

Future developers should assume:

- Step 5 is the governance layer before any future traversal execution
- trust and explainability are more important than aggressive automation
- `AUTO_ELIGIBLE` is a future-readiness signal, not permission to fetch now
- append-only review events are part of the product contract
- planning-only boundaries are intentional and should not be bypassed casually
