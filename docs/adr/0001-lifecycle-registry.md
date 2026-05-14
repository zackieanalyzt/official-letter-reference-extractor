# ADR 0001: Lifecycle Registry

## Status

Accepted

## Context

OLRE needs an operational memory system that supports auditability, deterministic diagnosis, retry traceability, and future lifecycle visibility without becoming an event-sourcing platform or distributed telemetry system.

## Decision

- `document_lifecycle_events` is append-only operational history.
- `documents.lifecycle_state` is a materialized operational projection.
- Lifecycle writes are correctness-critical and must occur in the same transaction as the operational mutation they describe.
- Timeline ordering is deterministic: `occurred_at ASC`, then `id ASC`.
- Lifecycle visibility is document-level first.
- Consistency validation is synchronous and read-only in the current phase.
- Cleanup success becomes a lifecycle fact only after successful deletion and projection update.
- Cleanup failures remain structured operational logs in this phase.

## Consequences

### Positive

- Operational history remains auditable.
- Support can diagnose document-level behavior without reconstructing state from mixed tables.
- Retry, retention, and cleanup become traceable.
- Future UI and reporting can build on stable lifecycle contracts.

### Negative

- Lifecycle integration adds more write-path discipline.
- Current lifecycle visibility remains document-level and intentionally conservative.
- Legacy documents may have partial or missing lifecycle history until forward adoption fills gaps.

## Non-Goals

- distributed event buses
- event replay engines
- telemetry platforms
- auto-repair or automatic reconciliation
