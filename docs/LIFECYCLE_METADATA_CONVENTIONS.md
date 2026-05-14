# Lifecycle Metadata Conventions

## Purpose

This document constrains `document_lifecycle_events.metadata_json` so it remains small, readable, and operationally useful.

`metadata_json` is not a dumping ground for arbitrary payloads.

## Rules

- Only top-level scalar operational keys are allowed.
- Keys must be event-family-specific.
- Unknown keys should be filtered by the lifecycle helper layer.
- Large blobs, raw OCR payloads, stack traces, and nested debugging payloads are not allowed.

## Allowed Keys By Event

### `DOCUMENT_UPLOADED`

- `uploaded_file_name`
- `triggered_by`

### `DOCUMENT_QUEUED`

- `uploaded_file_name`
- `triggered_by`
- `force_reprocess`

### `DOCUMENT_PROCESSING_STARTED`

- `triggered_by`
- `force_reprocess`

### `DOCUMENT_VALIDATED`

- `uploaded_file_name`

### `DOCUMENT_EXTRACTION_COMPLETED`

- `page_count`
- `reference_count`

### `DOCUMENT_RESOLUTION_COMPLETED`

- `reference_count`
- `used_cached_result`

### `DOCUMENT_FAILED`

- `step`
- `reason`

### `DOCUMENT_RETAINED`

- `reason`
- `retention_mode`
- `storage_backend`
- `storage_key_present`

### `DOCUMENT_CLEANED`

- `cleanup_type`
- `reason`
- `cleanup_trigger`
- `storage_key_present_before`

### `DOCUMENT_RETRY_REQUESTED`

- `mode`

### `DOCUMENT_RETRY_STARTED`

- `triggered_by`
- `force_reprocess`

### `DOCUMENT_RETRY_COMPLETED`

- `triggered_by`
- `force_reprocess`
- `success`

### `DOCUMENT_DUPLICATE_REUSED`

- `uploaded_file_name`

### `DOCUMENT_EXPORTED`

- `export_type`

## Operational Guidance

- Put durable meaning in `event_type`, `from_state`, `to_state`, `actor_source`, and error fields first.
- Use metadata only for small contextual facts that help operators interpret an event.
- Use `error_type` and `error_detail` for failure semantics instead of inventing metadata keys.
