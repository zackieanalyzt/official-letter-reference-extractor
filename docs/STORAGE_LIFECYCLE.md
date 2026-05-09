# Storage Lifecycle

OLRE v0.9.6 introduces explicit storage lifecycle modeling for documents.

## Lifecycle States

Current lifecycle states:

- `uploaded`
- `processing`
- `processed`
- `failed`
- `retained`
- `archived`
- `deleted`

## Meaning

### `uploaded`

Document row exists and the file has been registered, but processing is not yet complete.

### `processing`

The document is actively being processed.

### `processed`

Reference extraction completed successfully.

### `failed`

Processing failed and no retained source file is currently available for retry.

### `retained`

Processing failed and a retained source blob is still available.

### `archived`

Reserved for future archive workflows.

### `deleted`

The retained source lifecycle ended and the source blob is no longer available.

## Current Transition Rules

Typical transitions:

```text
uploaded -> processing -> processed
uploaded -> processing -> retained
retained -> deleted
failed -> retained
```

`processing_status` still captures extraction outcome, while `lifecycle_state` focuses on storage and recoverability.

## Why This Matters

Before v0.9.6, source availability was implicit in a mix of fields:

- `moved_to_path`
- `source_file_present`
- `last_source_path`
- `retry_requires_reupload`

Those fields still exist, but `lifecycle_state` makes the storage story easier to reason about operationally.

## Retry Compatibility

Retry logic still depends on an available retained source path.

When retained content is cleaned up:

- `source_file_present` becomes false
- `retry_requires_reupload` becomes true
- `lifecycle_state` becomes `deleted`

## Future Direction

This lifecycle model is intentionally simple for the SQLite-first single-node phase.

Future work can extend it toward:

- archive workflows
- alternative storage backends
- explicit blob reference tables
- lifecycle event auditing
