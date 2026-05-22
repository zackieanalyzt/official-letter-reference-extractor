# Architecture: Traversal Review

This document is the technical deep-dive for OLRE's traversal review architecture after Step 5.

## Purpose

Traversal review exists to classify extracted references before any network-enabled traversal phase is introduced. It does not fetch URLs. It does not recurse. It does not create child documents.

The design goal is to make later traversal governance possible without losing operator trust.

## Traversal Lifecycle Model

```text
Document
  ↓
Reference Extraction
  ↓
DocumentReference row created
  ↓
Existing destination classification / resolution metadata
  ↓
TraversalReviewService evaluates evidence
  ↓
confidence_score / risk_level / recommended_action / review_status
  ↓
/ops/traversal queue placement
  ↓
append-only review event rows
```

Current-state storage:

- `document_references`

Append-only audit storage:

- `reference_traversal_reviews`

## Queue State Definitions

### `AUTO_ELIGIBLE`

Meaning:

- low-risk
- deterministic enough for future skip-review behavior
- still not auto-downloaded in Step 5

Typical example:

- typed `https` reference from native text
- syntactically valid
- not private/loopback/link-local
- no multi-target conflict
- no broken QR evidence
- confidence score high enough

### `REVIEW_REQUIRED`

Meaning:

- candidate exists
- evidence is plausible
- operator should confirm because risk or ambiguity still matters

Typical example:

- shortlink
- redirect-like target
- OCR-derived URL
- multiple candidates
- QR/text disagreement

### `BLOCKED`

Meaning:

- later traversal should not proceed without explicit policy change

Typical example:

- unsupported scheme
- malformed URL
- private IP
- loopback target
- link-local target
- invalid/corrupted PDF artifact

### `UNCERTAIN`

Meaning:

- insufficient evidence to classify confidently
- not blocked by policy, but not safe enough to treat as reviewable structured target

Typical example:

- QR-looking evidence without deterministic decode
- no typed URL
- weak scan quality
- incomplete offline-safe evidence

## Scoring And Risk Heuristics

Step 5 uses deterministic heuristics rather than statistical models.

Important signals:

- source type: `text`, `qr`, `ocr`
- HTTP/HTTPS syntactic validity
- destination type
- shortlink / redirect-like behavior
- multi-candidate conflict
- QR/text disagreement
- broken QR evidence
- invalid PDF evidence
- private, loopback, and link-local target detection

High-level scoring intent:

- reward direct typed or QR-decoded HTTP/HTTPS evidence
- reward stable destination classification
- penalize redirect-like behavior
- penalize multiple candidates and disagreement
- heavily penalize malformed, blocked, or invalid-file conditions

Risk intent:

- `LOW` only for strong deterministic cases
- `MEDIUM` for ordinary but not yet trustless cases
- `HIGH` for ambiguity, conflict, redirect, or weak evidence
- `BLOCKED` for concrete policy or target-safety violations

## Recommended Action Decision Matrix

```text
Valid deterministic http/https + low risk + no conflict
  → AUTO_ELIGIBLE

Valid candidate but shortlink / redirect / OCR / medium confidence / conflict
  → REVIEW_REQUIRED

Unsupported scheme / malformed target / private IP / loopback / link-local / invalid PDF
  → BLOCKED

No confident candidate / weak scan evidence / incomplete offline-safe evidence
  → UNCERTAIN
```

## Audit And Event Philosophy

Why append-only matters:

- operators need a durable review trail
- future governance changes need historical context
- queue state can change, but prior decisions must stay visible

Current pattern:

- `document_references` holds latest values
- `reference_traversal_reviews` records evaluation and operator events

Important event categories:

- confidence evaluated
- queue placed
- operator approved
- operator rejected
- operator skipped
- operator noted

## Why Planning-Only Matters

Planning-only is not an incomplete state by accident. It is a deliberate governance boundary.

Reasons:

- real-world evidence quality is still inconsistent
- fetch behavior multiplies operational risk quickly
- recursive traversal would blur provenance and create child-document lifecycle complexity too early
- commercial trust depends on explainable sorting before network behavior grows

## Why Recursive Traversal Is Deferred

Recursive traversal is intentionally deferred because:

- a single reference can already be ambiguous
- later child documents introduce storage, retention, and audit expansion
- multiple QR and redirect-chain patterns are still common
- the system would start behaving like a crawler unless strict boundaries exist first

OLRE is not intended to become a generic crawler platform.

## Real-World Findings From Steps 3-4

These architecture decisions were shaped by corpus evidence:

- broken QR prevalence: visible QR regions often existed without reliable decode
- redirect-chain prevalence: some references pointed to redirect-oriented hosts instead of stable document URLs
- multiple QR prevalence: a single operational letter could expose multiple traversal candidates
- invalid PDF artifacts: not every inbound PDF was structurally readable
- low-confidence scan behavior: cover memos and washed-out scans often hid the real signal on later pages or image-only regions

These findings justify conservative queue placement.

## Examples

### Example: `AUTO_ELIGIBLE`

```text
Page 1 typed URL
https://moph.go.th/notice.pdf
Direct https target
No conflict
No blocked host pattern
```

Result:

- high confidence
- low risk
- `AUTO_ELIGIBLE`

### Example: `REVIEW_REQUIRED`

```text
QR decoded to https://bit.ly/example
Valid target shape, but shortlink
```

Result:

- medium confidence
- high or medium review risk
- `REVIEW_REQUIRED`

### Example: `BLOCKED`

```text
Typed URL resolves to http://127.0.0.1/admin
```

Result:

- blocked host category
- `BLOCKED`

### Example: `UNCERTAIN`

```text
Page shows QR-like evidence but no deterministic payload
No typed URL available
```

Result:

- insufficient evidence
- `UNCERTAIN`

## Operational Summary

Traversal review is a governance layer, not a network execution layer.

Its job is to:

- make queue placement reproducible
- reduce manual review workload for obvious cases
- isolate risky and incomplete evidence
- preserve auditability for every operator decision
