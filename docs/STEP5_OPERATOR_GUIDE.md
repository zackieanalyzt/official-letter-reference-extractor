# Step 5 Operator Guide

This guide explains how to use the traversal review queue at `/ops/traversal`.

## What `/ops/traversal` Is

`/ops/traversal` is the review screen for extracted reference candidates.

It does not download anything.
It does not follow links.
It does not create child documents.

Its job is to help you sort candidates into:

- safe enough for future skip-review handling
- needs human review
- blocked by policy or target safety
- still too uncertain

## What The Queues Mean

### `AUTO_ELIGIBLE`

Meaning:

- the reference looks structurally safe and consistent
- it is likely a good candidate for future automation
- it still does not trigger any download in Step 5

Think of this as:

- “probably safe enough to not require manual review later”

### `REVIEW_REQUIRED`

Meaning:

- the system found a plausible reference
- but something about it still needs human judgment

Common reasons:

- shortlink
- redirect-like target
- multiple candidates
- OCR-derived evidence
- moderate confidence

### `BLOCKED`

Meaning:

- the system found a concrete reason this candidate should not proceed

Examples:

- malformed URL
- unsupported scheme
- loopback or private address
- invalid PDF evidence

### `UNCERTAIN`

Meaning:

- the system does not have enough evidence to classify confidently

Examples:

- QR-like evidence without a clear decode
- weak scan quality
- no typed URL
- incomplete evidence

## What `confidence_score` Means

`confidence_score` is a numeric estimate from `0` to `100`.

General interpretation:

- `80-100`: strong evidence
- `50-79`: usable but still review-worthy
- `0-49`: weak or incomplete evidence

Higher score does not mean the system downloaded or verified the target. It only means the offline evidence was stronger.

## What `risk_level` Means

`risk_level` tells you how careful the system thinks future traversal should be.

- `LOW`: ordinary, stable-looking candidate
- `MEDIUM`: plausible but not trustless
- `HIGH`: redirect, ambiguity, conflict, or weak evidence
- `BLOCKED`: should not proceed under current policy

## What `review_status` Means

- `NOT_REQUIRED`: no operator action is expected right now
- `PENDING_REVIEW`: waiting for human decision
- `APPROVED`: operator accepted the candidate for future traversal consideration
- `REJECTED`: operator rejected the candidate
- `SKIPPED`: operator intentionally left the candidate ignored for now

## How To Use The Actions

### Approve

Use when:

- the candidate looks valid
- the evidence summary makes sense
- you are comfortable allowing it to remain a future traversal candidate

Important:

- approve does not download anything in Step 5

### Reject

Use when:

- the candidate should not be used later
- the evidence is misleading or inappropriate
- policy or safety concerns apply

Reject is stronger than skip. It moves the current state toward blocked handling.

### Skip

Use when:

- you do not want to approve or reject yet
- the candidate can wait
- it should remain visible in history without becoming accepted

### Add Note

Use notes to record operator context such as:

- why the candidate was approved
- why it was rejected
- what evidence looked suspicious
- what follow-up may be needed later

## Why Some References Stay Uncertain

Not every document contains a clean typed URL or a decodable QR code. Some scanned documents are too weak, too noisy, or too incomplete for safe classification.

`UNCERTAIN` is intentional. It means the system is refusing to fake certainty.

## Why The System Does Not Auto-Download Yet

Step 5 is a review and governance layer, not a crawler.

That means:

- no fetching
- no recursive traversal
- no child-document creation

This protects operator trust while the organization learns which cases are actually safe to automate later.

## Practical Review Approach

Good operating habit:

1. check the recommended action
2. read the evidence summary
3. check the confidence score and risk level
4. approve only when the candidate is understandable and appropriate
5. reject when policy or safety concerns are clear
6. skip when a decision should wait

The system is designed so you do not have to review every reference equally. Your time should go mostly to `REVIEW_REQUIRED` and `UNCERTAIN`.
