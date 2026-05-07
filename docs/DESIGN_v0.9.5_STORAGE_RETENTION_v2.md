# OLRE v0.9.5-pre Design Proposal v2

## Storage, Retention, Reuse, and Runtime Strategy

Status: Design phase only  
Implementation status: Not implemented  
Purpose: Revised proposal after design review approval with required clarifications

---

## 1. Decision Summary

This v2 proposal locks the missing details requested in review.

The approved direction remains:

> OLRE should be a document reference intelligence system, not a permanent PDF archive.

### Core operating model

- OLRE retains extraction intelligence long-term
- original PDFs are retained only according to explicit retention policy
- hash-based reuse is first-class
- retry behavior is retention-aware
- Docker runtime is optimized for SQLite-first, low-storage, low-ops deployment

### New clarifications added in v2

1. exact default retention config values are now locked
2. duplicate upload behavior now includes normal reuse and force reprocess
3. cache reuse rules now include `extraction_version`
4. MVP schema is separated from future schema
5. cleanup execution mechanism is defined
6. `debug_artifacts` table status is clarified

---

## 2. Product Identity and Storage Philosophy

### Recommended role of OLRE

OLRE should not primarily function as a document archive.

OLRE should function as:

> a document reference extraction and intelligence system with configurable source retention

### Long-term value OLRE should preserve

- `sha256` content hash
- extracted references
- resolved URLs
- document number
- page count
- processing outcomes
- analytics
- quality signals
- batch history
- operational audit trail

### Data OLRE should not retain by default

- original PDF forever
- processed/error folder copies forever
- QR debug PNGs forever
- temporary upload files after business value has been extracted

### Why this remains the correct direction

This direction best matches:

- lower disk usage
- smaller backups
- lower privacy exposure
- better fit for commercial deployment
- simpler Docker volume behavior
- sustainable SQLite-first runtime

---

## 3. Locked Default Retention Configuration

This section locks the exact default values for MVP.

## 3.1 Default policy name

Recommended default policy name:

`retain_failed_only`

Meaning:

- successful source files are deleted after successful processing is finalized
- failed source files are retained temporarily
- debug artifacts are disabled by default and short-lived when enabled

## 3.2 Locked default config values

These should be treated as the exact MVP defaults unless changed by product decision:

```env
FILE_RETENTION_MODE=retain_failed_only
SUCCESS_SOURCE_RETENTION_HOURS=0
FAILED_SOURCE_RETENTION_HOURS=168
SOURCE_DELETE_ON_CACHE_REUSE=true
QR_DEBUG_EXPORT=false
QR_DEBUG_RETENTION_HOURS=72
CLEANUP_ENABLED=true
CLEANUP_INTERVAL_MINUTES=60
CLEANUP_STARTUP_SWEEP=true
DEFAULT_FORCE_REPROCESS=false
EXTRACTION_VERSION=1
```

Interpretation:

- `SUCCESS_SOURCE_RETENTION_HOURS=0`
  - delete immediately after successful finalize
- `FAILED_SOURCE_RETENTION_HOURS=168`
  - keep failed source for 7 days
- `SOURCE_DELETE_ON_CACHE_REUSE=true`
  - duplicate uploads that reuse cache should have uploaded temp/source deleted immediately after finalize
- `QR_DEBUG_RETENTION_HOURS=72`
  - 3 days when QR debug is enabled
- `CLEANUP_INTERVAL_MINUTES=60`
  - cleanup job runs hourly
- `EXTRACTION_VERSION=1`
  - current extraction pipeline version for cache compatibility

## 3.3 Non-default supported modes in MVP

MVP should support only these retention modes:

1. `retain_source`
2. `retain_failed_only`
3. `immediate_ephemeral`

Not in MVP:

- grace-period-per-success custom variants as separate named modes
- advanced per-user/per-tenant retention

Reason:

This keeps the implementation surface small while still covering the important operational profiles.

---

## 4. Duplicate Upload Behavior

This section now locks exact duplicate semantics.

## 4.1 Primary duplicate identity

Document sameness is defined by:

- `sha256(content bytes)`

Filename is not identity.

Implications:

- same filename + different bytes = new document
- different filename + same bytes = duplicate of same document

## 4.2 Duplicate upload default behavior

Default behavior on duplicate upload:

```text
upload
-> compute sha256
-> find canonical processed document with same hash
-> compare extraction_version
-> if reusable:
     reuse existing extraction results
     create new ingestion record
     do not re-extract by default
-> apply retention policy to uploaded source
```

### User-visible behavior

When cache reuse occurs, UI should show:

- "This file was already processed previously."
- "Existing extraction results were reused."

Batch history should still record the event as a new ingestion.

## 4.3 Duplicate upload with force reprocess

MVP must support a manual force-reprocess path.

Definition:

`force_reprocess=true` means:

- ignore normal hash reuse decision
- create a new processing attempt
- re-run extraction using current extraction pipeline
- replace canonical extraction outputs for that hash if successful

### Recommended usage

Use force reprocess when:

- extraction logic changed
- operator believes previous extraction quality was poor
- operator wants to rebuild results intentionally

### UI wording

MVP UX can expose this in a simple way:

- normal upload path: auto reuse if possible
- document/batch action: "Force reprocess"

### Important safeguard

Force reprocess should be explicit, never automatic.

## 4.4 Duplicate upload metrics

MVP should track these outcomes distinctly:

- `processed_fresh`
- `reused_cached`
- `forced_reprocess`
- `failed`

This preserves analytics and operational clarity.

---

## 5. Cache Reuse Rules with `extraction_version`

This section now defines exact reuse conditions.

## 5.1 Why `extraction_version` is needed

Hash alone is not enough for safe reuse forever.

If the extraction pipeline changes materially, the same PDF may produce better or different outputs.

Therefore cache reuse must consider:

- document hash
- canonical processing status
- extraction version compatibility

## 5.2 Reuse rule

MVP reuse is allowed only if all are true:

1. same `content_hash`
2. canonical document status is `processed`
3. canonical document `extraction_version == current EXTRACTION_VERSION`
4. upload was not marked `force_reprocess=true`

If any condition fails:

- process fresh

## 5.3 Locked MVP behavior

MVP uses exact-match rule only:

```text
reuse only when extraction_version matches exactly
```

No semantic compatibility matrix in MVP.

## 5.4 Canonical overwrite rule

If force reprocess succeeds:

- canonical document for that hash should be updated to current extraction output
- `extraction_version` becomes current version
- prior ingestion history remains preserved

If force reprocess fails:

- canonical last good extraction should remain intact
- failed ingestion is recorded separately

This protects analytics integrity.

---

## 6. MVP Schema vs Future Schema

This section separates implementation expectations clearly.

## 6.1 MVP schema direction

MVP should keep schema change surface modest.

### Existing `documents` table

MVP should extend `documents` with:

- `extraction_version` integer or string, non-null with default
- `retention_mode` nullable or non-null with default
- `source_file_present` boolean, non-null default false
- `source_deleted_at` nullable
- `last_source_path` nullable
- `retry_requires_reupload` boolean, non-null default false

Suggested MVP meaning:

- `last_source_path`
  - last known physical path if a retained source exists
- `source_file_present`
  - whether a retained source currently exists
- `retry_requires_reupload`
  - true when extraction retry is impossible without new upload

### New MVP table: `document_ingestions`

MVP should add this table now.

Suggested fields:

- `id`
- `document_id`
- `batch_run_id`
- `uploaded_file_name`
- `uploaded_at`
- `ingestion_status`
- `used_cached_result`
- `force_reprocess_requested`
- `retention_mode_used`
- `source_file_path`
- `source_file_present`
- `source_deleted_at`
- `cleanup_due_at`
- `retry_source_available`
- `error_type`
- `error_detail`

### Why `document_ingestions` is MVP, not future

Without it, OLRE cannot cleanly separate:

- canonical intelligence
- each upload event
- retention result
- cache reuse event
- retry availability

That separation is required for the approved direction, so it belongs in MVP.

## 6.2 Future schema

Future schema can add:

- dedicated `debug_artifacts` table
- compatibility matrix for `extraction_version`
- cleanup job audit table
- per-tenant or per-policy override tables
- reference provenance per ingestion
- retention exception flags

These are useful but not required for the first delivery of the new retention model.

---

## 7. Is `debug_artifacts` Table MVP or Future

This is now explicitly decided.

Decision:

> `debug_artifacts` table is a future-phase feature, not MVP.

### MVP behavior for debug artifacts

MVP should:

- keep current filesystem-based debug artifact storage
- apply retention policy using file timestamps and naming convention
- purge files directly from filesystem

### Why not MVP

Adding `document_ingestions` is already a meaningful schema change.

Adding `debug_artifacts` table immediately would increase blast radius without being necessary to achieve the approved runtime/storage direction.

### Future upgrade path

If debug lifecycle needs richer audit later:

- add `debug_artifacts` table
- link to `document_id` and `ingestion_id`
- track `expires_at` and `purged_at`

For now, filesystem cleanup is enough.

---

## 8. Cleanup Execution Mechanism

This section locks the MVP cleanup execution model.

## 8.1 MVP cleanup mechanism

MVP should use an in-app cleanup worker plus startup sweep.

### Exact mechanism

1. startup sweep
- run once when app starts
- clean expired failed-source files
- clean expired debug artifacts
- clean orphan temp files older than a safety threshold

2. recurring in-app cleanup loop
- runs every `CLEANUP_INTERVAL_MINUTES`
- same cleanup categories as startup sweep

### Why this is the MVP choice

- simplest operational model for Docker SQLite-first deployments
- zero external scheduler requirement
- easiest for small-office and single-container users

## 8.2 What cleanup should process in MVP

Cleanup categories:

1. expired retained failed source files
2. expired QR debug files
3. orphan temp files older than a fixed threshold

Recommended orphan temp threshold:

```env
TEMP_FILE_MAX_AGE_HOURS=24
```

## 8.3 Cleanup state updates

When cleanup deletes a retained source:

- update `document_ingestions.source_file_present=false`
- set `document_ingestions.source_deleted_at`
- update `documents.source_file_present=false` only if no retained source remains
- set `documents.retry_requires_reupload=true` when applicable

## 8.4 Future cleanup model

Future deployment profiles may optionally move cleanup to:

- external cron
- sidecar maintenance container
- orchestrator scheduled job

But not in MVP.

---

## 9. Runtime File Lifecycle v2

## 9.1 First-time upload

```text
upload
-> save to temp path
-> compute sha256
-> create ingestion row
-> no reusable canonical document
-> extract references
-> resolve URLs
-> mark canonical processed
-> set extraction_version=current
-> apply retention policy
-> finalize ingestion
```

## 9.2 Duplicate upload with reuse

```text
upload
-> save to temp path
-> compute sha256
-> create ingestion row
-> canonical document found
-> extraction_version matches
-> force_reprocess=false
-> mark ingestion used_cached_result=true
-> skip extraction
-> delete uploaded source immediately if default policy says so
-> finalize ingestion
```

## 9.3 Duplicate upload with force reprocess

```text
upload or action
-> force_reprocess=true
-> compute sha256
-> create ingestion row
-> ignore reuse path
-> run extraction using current pipeline
-> if success:
     replace canonical extraction result
   else:
     keep previous canonical good state
-> apply retention policy
-> finalize ingestion
```

## 9.4 Failed extraction

```text
upload
-> temp
-> compute sha256
-> create ingestion row
-> extraction fails
-> retain source under failed retention policy
-> mark retry_source_available=true
-> cleanup_due_at = uploaded_at + 168h
-> finalize failed ingestion
```

## 9.5 Retry flow

```text
retry extraction requested
-> if retained source exists:
     process from retained source
   else:
     return retry_requires_reupload
```

## 9.6 URL-resolution-only retry

```text
retry resolution requested
-> no source PDF required
-> re-run URL resolution on stored references
```

This should be treated separately from extraction retry.

---

## 10. Retry Semantics v2

This is now explicitly locked for MVP.

## 10.1 Two retry types

MVP should distinguish:

1. `retry_extraction`
2. `retry_resolution`

## 10.2 `retry_extraction`

Allowed only when:

- retained source file exists

Otherwise result should be:

- `retry_requires_reupload`

## 10.3 `retry_resolution`

Allowed when:

- references already exist in DB

No source file required.

## 10.4 UI messaging

When extraction retry is impossible:

- "The original PDF is no longer stored."
- "To process this document again, please upload the file again."

When retained source exists:

- "Retry from stored file"

For URL-only retry:

- "Retry URL resolution"

---

## 11. QR Debug Artifact Strategy v2

Decision for MVP:

- `QR_DEBUG_EXPORT=false` by default
- filesystem-based debug storage remains in MVP
- no `debug_artifacts` table in MVP
- debug cleanup is done by in-app cleanup worker

### Locked default values

```env
QR_DEBUG_EXPORT=false
QR_DEBUG_RETENTION_HOURS=72
```

### MVP cleanup rule

If debug export is enabled:

- keep PNG/JSON artifacts for 72 hours
- remove by age during startup sweep and hourly cleanup loop

### User/admin guidance

- debug artifacts are operational aids
- not part of long-term retained business data

---

## 12. UI / UX Requirements v2

MVP should add clear user-facing messaging for:

### Reused cached result

- "This file was already processed previously."
- "Existing extraction results were reused."

### Force reprocess

- "Force reprocess will run extraction again using the current processing logic."

### Source deleted

- "The original PDF is no longer stored."

### Retry requires re-upload

- "To process this document again, please upload the file again."

### Retry available

- "A stored source file is still available for retry."

### Debug retention

- "Debug files are temporary and may be removed automatically."

---

## 13. Operational and Commercial Position

The direction remains strongly recommended.

### Benefits

- lower storage growth
- smaller backups
- stronger privacy minimization
- better commercial viability
- easier Docker SQLite-first runtime

### Main tradeoff

The biggest intentional tradeoff is:

> retry extraction becomes conditional on source retention

That is acceptable if:

- policy is explicit
- UX is clear
- failed files are temporarily retained
- force reprocess is supported when source exists

---

## 14. Docker and Runtime Implications

This design should still happen before final Docker runtime packaging.

### Why

The following are affected directly:

- runtime path structure
- cleanup model
- backup guidance
- readiness assumptions
- volume growth behavior

### Docker implication for MVP

The runtime should be designed around:

```text
/app/data/
  olre.sqlite3
  runtime/
    tmp/
    failed-retained/
  debug/
    qr/
```

This is more aligned with ephemeral/default deletion than legacy `input/processed/error` semantics.

### Readiness implication

Future `/readyz` expectations should check:

- DB ping
- writable DB path
- writable temp path
- writable failed-retained path
- writable debug path only if debug export enabled

---

## 15. Migration Strategy v2

Migration remains non-destructive by default.

## 15.1 MVP migration steps

1. add retention fields to `documents`
2. add `document_ingestions`
3. mark existing rows as legacy-retained
4. scan existing stored paths and set presence flags
5. keep existing files untouched unless admin deletes them later

## 15.2 Legacy mapping rule

Existing files should be treated as:

- retained by legacy policy
- retry-capable if the file still exists

## 15.3 Destructive cleanup

Not part of migration.

If legacy cleanup is desired later:

- do it via explicit admin workflow
- show counts and impact before delete

---

## 16. MVP Scope vs Future Scope Summary

## MVP

- exact default retention config values locked
- `retain_source`, `retain_failed_only`, `immediate_ephemeral`
- hash reuse with exact `extraction_version` match
- explicit force reprocess support
- `document_ingestions` table
- retention metadata on `documents`
- in-app startup sweep plus hourly cleanup loop
- filesystem-based QR debug retention cleanup
- retry split into extraction vs resolution

## Future

- `debug_artifacts` table
- external cleanup scheduler profiles
- semantic version compatibility rules for reuse
- per-tenant/per-user retention profiles
- richer cleanup audit tables
- advanced policy UI

---

## 17. Final Recommendation

Proceed to implementation planning only after approving these locked v2 decisions:

1. default retention mode = `retain_failed_only`
2. success source retention = immediate delete
3. failed source retention = 168 hours
4. debug retention = 72 hours when enabled
5. duplicate uploads reuse cache only when `extraction_version` matches exactly
6. force reprocess is explicit and supported in MVP
7. `document_ingestions` is MVP
8. `debug_artifacts` table is future, not MVP
9. cleanup is in-app in MVP with startup sweep + hourly loop

If these are accepted, the design is specific enough to break into implementation tasks without reopening the architecture again.

---

## 18. Implementation-Planning Addendum

This addendum records the final planning details required before implementation starts.

## 18.1 Canonical Reference Replacement Rule for Force Reprocess

Force reprocess operates on the canonical document identified by `content_hash`.

### Rule

If `force_reprocess=true` and processing succeeds:

- replace the canonical extraction output for that hash
- delete existing `document_references` rows for that canonical document
- insert the newly extracted `document_references`
- update canonical `documents` fields such as:
  - `page_count`
  - `document_number`
  - `processing_status`
  - `processing_error_type`
  - `processing_error_detail`
  - `processed_at`
  - `extraction_version`

If `force_reprocess=true` and processing fails:

- preserve the previous last-good canonical extraction data
- record the failed ingestion separately
- do not destroy existing reference intelligence

### Reason

This avoids losing good intelligence due to a failed replacement attempt while still allowing the canonical record to be refreshed intentionally.

## 18.2 Required DB Constraints and Indexes

### MVP required constraints

#### `documents`

- unique index on `content_hash`
- non-null `extraction_version`
- non-null `retention_mode`
- non-null `source_file_present`
- non-null `retry_requires_reupload`

#### `document_ingestions`

- primary key on `id`
- foreign key to `documents.id`
- optional foreign key to `batch_runs.id`
- non-null `uploaded_file_name`
- non-null `ingestion_status`
- non-null `used_cached_result`
- non-null `force_reprocess_requested`
- non-null `retention_mode_used`
- non-null `source_file_present`
- non-null `retry_source_available`

### MVP required indexes

#### `documents`

- unique `uq_documents_content_hash`
- index on `processing_status`
- index on `document_number`
- index on `processed_at`
- index on `source_file_present`
- index on `retry_requires_reupload`

#### `document_ingestions`

- index on `document_id`
- index on `batch_run_id`
- index on `uploaded_at`
- index on `ingestion_status`
- index on `used_cached_result`
- index on `cleanup_due_at`
- index on `source_file_present`
- index on `retry_source_available`

### Existing `document_references`

Keep current uniqueness at minimum:

- unique per `document_id`, `page_number`, `raw_reference`, `source_type`

This remains valid under canonical replacement because replacement rebuilds the canonical set.

## 18.3 Transaction and Recovery Behavior for DB + Filesystem Operations

The system cannot make DB and filesystem fully atomic, so the implementation should use a staged, recoverable pattern.

### Required behavior

1. create/update DB intent first
2. perform filesystem action second
3. persist final DB state third
4. on failure, mark state explicitly and preserve recoverability

### Recommended pattern

#### Upload / normal processing

```text
create ingestion row -> flush
process file -> build extracted result in memory
write canonical DB changes in transaction -> commit
apply retention filesystem action
update source presence / cleanup metadata -> commit
```

#### Failure during filesystem delete/move

If DB commit succeeded but delete failed:

- keep canonical processing result
- mark ingestion for cleanup retry
- mark file as still present
- do not fail the canonical extraction result

#### Failure during canonical replacement

If force reprocess fails before canonical replacement commit:

- leave old canonical document state unchanged
- failed ingestion records the error

If filesystem retention cleanup fails after successful canonical replacement:

- canonical result remains updated
- cleanup is deferred and retried later

### Crash recovery requirements

Startup sweep must reconcile:

- orphan temp files
- source files whose DB says they should have been deleted
- ingestion rows with stale `source_file_present=true` but missing file

## 18.4 Exact Routes and UI Actions to Add or Change

### Routes to change

#### `POST /imports/upload`

Add support for:

- optional `force_reprocess` flag for upload workflow

Default:

- `force_reprocess=false`

#### `POST /documents/{document_id}/retry`

Change semantics to:

- retry extraction only if retained source exists
- otherwise redirect with `retry_status=requires_reupload`

#### `POST /documents/{document_id}/retry-resolution`

New route in MVP:

- retries URL resolution from stored references
- no source PDF required

#### `POST /documents/{document_id}/force-reprocess`

New route in MVP:

- only works if retained source exists
- otherwise redirect with `force_reprocess_status=requires_reupload`

### UI actions to change

#### Imports page

Add:

- a simple "Force reprocess duplicates" checkbox for upload submit

#### Results page

Add per-document/row signals:

- cached result reused
- original PDF retained or deleted
- retry extraction available or requires re-upload

Add actions:

- `Retry from stored file`
- `Retry URL resolution`
- `Force reprocess`

Action visibility rules:

- `Retry from stored file` only when retained source exists and document is failed
- `Retry URL resolution` when references exist
- `Force reprocess` only when retained source exists

## 18.5 Concrete Acceptance Criteria and Test Cases

### Acceptance criteria

1. first-time upload processes normally and canonical intelligence is stored
2. duplicate upload with same hash and matching `extraction_version` reuses cached result by default
3. duplicate upload with `force_reprocess=true` re-runs extraction
4. force reprocess success replaces canonical references
5. force reprocess failure preserves previous canonical references
6. successful processing under default policy deletes source file immediately
7. failed processing under default policy retains source file and sets cleanup deadline
8. retry extraction works only when retained source exists
9. retry extraction without source redirects with `requires_reupload`
10. retry URL resolution works without source file
11. cleanup startup sweep removes expired failed-source files
12. cleanup startup sweep removes expired debug artifacts when enabled
13. cleanup reconciliation updates DB flags when file is already missing
14. analytics, exports, quality report, and dashboard still work after reuse and retention cleanup

### Minimum MVP test cases

#### Reuse and force reprocess

- upload new PDF -> processed fresh
- upload same PDF again -> reused cached
- upload same PDF with force reprocess -> processed fresh and canonical updated
- force reprocess failure -> canonical references remain unchanged

#### Retention

- processed document source deleted immediately under default policy
- failed document source retained
- failed document source deleted after cleanup once expired

#### Retry

- retry failed with retained source succeeds
- retry failed without source returns `requires_reupload`
- retry resolution works without source

#### Cleanup

- startup cleanup removes expired debug files
- startup cleanup removes orphan temp files older than threshold
- hourly cleanup updates DB flags for deleted files

#### Regression

- results page still renders documents with no references
- CSV/Markdown/Excel exports still succeed
- dashboard counts remain correct for reused cached ingestions
