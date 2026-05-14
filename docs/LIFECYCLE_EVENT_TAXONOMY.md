# Lifecycle Event Taxonomy

## Core Principle

```text
documents.lifecycle_state = materialized operational projection
document_lifecycle_events = append-only source of truth
```

States are durable operational projections.

Events are append-only operational facts.

## States

- `uploaded`
- `queued`
- `processing`
- `validated`
- `extracted`
- `resolved`
- `retained`
- `cleaned`
- `failed`

## Event Families

- `progress`
- `failure`
- `retry`
- `retention`
- `cleanup`
- `duplicate`
- `export`

## Approved Event Types

### Progress

- `DOCUMENT_UPLOADED`
- `DOCUMENT_QUEUED`
- `DOCUMENT_PROCESSING_STARTED`
- `DOCUMENT_VALIDATED`
- `DOCUMENT_EXTRACTION_COMPLETED`
- `DOCUMENT_RESOLUTION_COMPLETED`

### Failure

- `DOCUMENT_FAILED`

### Retry

- `DOCUMENT_RETRY_REQUESTED`
- `DOCUMENT_RETRY_STARTED`
- `DOCUMENT_RETRY_COMPLETED`

### Retention

- `DOCUMENT_RETAINED`

### Cleanup

- `DOCUMENT_CLEANED`

### Duplicate

- `DOCUMENT_DUPLICATE_REUSED`

### Export

- `DOCUMENT_EXPORTED`

## Approved Actors

- `batch_processor`
- `retry_service`
- `retention_service`
- `api`

## Severity Semantics

- `PASS`: expected and consistent
- `WARNING`: unusual but not immediately dangerous
- `ERROR`: operational inconsistency likely affects diagnosis or recovery confidence
- `CRITICAL`: audit or recovery risk, or persisted lifecycle history is impossible under approved rules

## Change Discipline

- Do not invent ad-hoc event names in service code.
- Event names must come from centralized constants.
- Any rename or semantic change requires documentation and architecture review.
