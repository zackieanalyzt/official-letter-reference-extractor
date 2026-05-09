# Retention Policy

OLRE v0.9.6 formalizes runtime artifact retention to reduce uncontrolled storage growth.

## Retention Targets

| Artifact Type | Default Retention |
|---|---|
| QR debug artifacts | 7 days |
| runtime tmp | 24 hours |
| failed retained sources | 30 days |
| export artifacts | 14 days |

## Configuration

Retention is controlled through environment variables:

| Variable | Default |
|---|---|
| `QR_DEBUG_RETENTION_HOURS` | `168` |
| `TEMP_FILE_MAX_AGE_HOURS` | `24` |
| `FAILED_SOURCE_RETENTION_HOURS` | `720` |
| `EXPORT_RETENTION_HOURS` | `336` |

## Cleanup Functions

Current cleanup entry points:

- `cleanup_runtime_tmp(...)`
- `cleanup_expired_exports(...)`
- `cleanup_old_debug_artifacts(...)`
- `cleanup_retained_failures(...)`
- `run_retention_cleanup(...)`

## Safety Model

Cleanup behavior aims to be boring and predictable:

- file deletion only
- no destructive directory pruning outside managed roots
- dry-run support
- structured logging

## Dry Run

Retention cleanup functions accept `dry_run=True`.

Dry run means:

- count what would be deleted
- do not remove files
- do not persist lifecycle cleanup mutations

## Cleanup Scheduling

OLRE still performs cleanup from the application cleanup loop controlled by:

- `CLEANUP_ENABLED`
- `CLEANUP_INTERVAL_MINUTES`
- `CLEANUP_STARTUP_SWEEP`

## Operational Recommendation

Use startup sweep in low-volume single-node environments.

For busier environments, keep the interval explicit and review logs to confirm:

- expired failed sources are being removed
- debug artifact growth stays bounded
- export artifacts do not accumulate forever

## Verification

Recommended check:

```bash
python -m pytest tests/integration/test_storage_hardening.py
```

Relevant assertions now cover:

- dry-run retention behavior
- export cleanup
- retained failed source cleanup
- lifecycle state updates after cleanup
