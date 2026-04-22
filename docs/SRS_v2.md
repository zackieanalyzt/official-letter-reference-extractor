# SRS — Software Requirements Specification for Official Letter Reference Extractor (OLRE)
Version: 2.0  
Status: Implementation-ready draft

---

## 1. Introduction

### 1.1 Purpose
This document defines the software requirements for OLRE, an internal LAN web application for processing official-letter PDFs, extracting QR payloads and text URLs, resolving final URLs, and presenting the results in a structured, exportable table.

### 1.2 Scope
OLRE shall:
- authenticate users against an existing MariaDB credential source
- process PDF files from a configured folder
- detect QR references anywhere in each PDF page
- extract URL-like strings from text
- normalize document-number suffixes
- resolve final URLs
- store and present one result row per reference
- move processed files after handling
- export results to CSV and Markdown

### 1.3 Definitions
- **Reference**: any extracted QR payload or URL-like text found in a PDF
- **Raw reference**: the unmodified detected value
- **Final URL**: the resolved destination after following redirects, if applicable
- **Document number**: normalized official-letter suffix after `/`
- **Input folder**: directory holding PDFs pending processing
- **Processed folder**: directory where processed files are moved
- **Error folder**: directory for files that fail fatally (recommended)

---

## 2. Overall Description

### 2.1 Product Perspective
OLRE is a standalone internal application that integrates with:
- PostgreSQL for application data
- MariaDB for authentication
- LAN file system folders for ingestion and archival movement

### 2.2 User Classes
- **Standard user**: can log in, run batch, view results, export results
- **Operator/admin-lite**: same as standard user plus can re-run failed items and view system logs
- true RBAC is not required in first implementation

### 2.3 Operating Environment
- Debian physical server on LAN
- Dockerized application
- external/native PostgreSQL
- external/native MariaDB
- mounted directories for file handling

### 2.4 Constraints
- manual batch only
- LAN only
- no sub-path requirement
- <= 10 concurrent users expected
- mixed PDF input quality
- filenames unreliable for identification

---

## 3. System Features

### 3.1 Authentication

#### 3.1.1 Description
Users shall log in with username/password that are validated against an existing MariaDB-based user store.

#### 3.1.2 Functional Requirements
- The system shall provide a login form.
- The system shall validate credentials against configured MariaDB tables/fields.
- The system shall create an authenticated session on success.
- The system shall reject invalid credentials.
- The system shall log login success/failure events.

#### 3.1.3 Pending external dependency
The exact MariaDB table, field names, and password hashing scheme must be confirmed before implementation.

---

### 3.2 Batch Processing Trigger

#### 3.2.1 Description
An authenticated user shall be able to trigger processing of all eligible PDF files in the input folder.

#### 3.2.2 Functional Requirements
- The system shall expose a “Process batch” action in the UI.
- The system shall enumerate PDF files in the input folder.
- The system shall process each eligible file sequentially in initial implementation.
- The system shall continue processing remaining files if one file fails.

---

### 3.3 File Registration and Identity

#### 3.3.1 Description
The system shall register each file before processing and determine whether it represents a new input.

#### 3.3.2 Functional Requirements
- The system shall compute a content hash for each file.
- The system shall store metadata including:
  - original filename
  - full path at intake
  - file size
  - modification time
  - content hash
- Files with same filename but different content hash shall be treated as new files.
- Files with identical fingerprint already completed may be skipped or marked duplicate according to implementation policy.

---

### 3.4 PDF Parsing

#### 3.4.1 Description
The system shall read PDFs page by page and access both text content and page imagery.

#### 3.4.2 Functional Requirements
- The system shall detect page count.
- The system shall extract text from text-layer pages.
- The system shall render pages to images for QR detection.
- The system shall record page-level context for extracted references.

---

### 3.5 QR Detection

#### 3.5.1 Description
QR codes may appear in arbitrary page positions. The system shall scan the full page and not depend on fixed locations.

#### 3.5.2 Functional Requirements
- The system shall scan every page for QR codes.
- The system shall support zero, one, or multiple QR results per page.
- The system shall save:
  - raw payload
  - page number
  - source type = `qr`
- The system should attempt multiple image variants when initial QR detection fails.

#### 3.5.3 Recommended algorithm
- render page
- detect/decode full-page QR
- retry with preprocessing if needed

---

### 3.6 Text URL Extraction

#### 3.6.1 Description
The system shall identify URLs and short URLs from PDF text.

#### 3.6.2 Functional Requirements
- The system shall inspect extracted text from each page.
- The system shall detect URL-like values using regex/pattern matching.
- The system shall save:
  - raw reference
  - page number
  - source type = `text_url`

#### 3.6.3 Detection scope
At minimum:
- `http://...`
- `https://...`
- common short-link formats

---

### 3.7 Reference Classification

#### 3.7.1 Description
Each detected reference shall be classified for downstream processing.

#### 3.7.2 Allowed classifications
- `url`
- `short_url`
- `non_url_payload`
- `unknown`

#### 3.7.3 Functional Requirements
- QR payloads that are not URLs shall still be stored.
- Text-extracted URL-like values shall be classified as `url` or `short_url` when possible.

---

### 3.8 Final URL Resolution

#### 3.8.1 Description
For URL-like references, the system shall attempt to obtain the final target URL.

#### 3.8.2 Functional Requirements
- The system shall attempt redirect resolution.
- The system shall save:
  - raw reference
  - final URL, if resolved
  - resolution status
  - HTTP status, if available
- If resolution fails, the system shall still preserve the raw reference.
- A URL requiring login should still be displayed if known.

#### 3.8.3 Suggested statuses
- `resolved`
- `raw_only`
- `resolve_failed`
- `non_url`

---

### 3.9 Document Number Extraction

#### 3.9.1 Description
The system shall derive a document number from official-letter notation.

#### 3.9.2 Current business rule
Given a string such as:
- `ลพ 0033.02/ว 6176`

The desired document number is:
- `ว6176`

#### 3.9.3 Functional Requirements
- The system shall search relevant text for official-letter identifiers.
- The system shall extract suffix content after `/`.
- The system shall normalize whitespace out of the extracted suffix.
- The system shall store the normalized value with the document record.

#### 3.9.4 Pending clarification
Additional real-world patterns beyond `.../ว 6176` are not yet finalized and should be expanded using sample documents.

---

### 3.10 Result Table

#### 3.10.1 Description
The UI shall present one row per reference found.

#### 3.10.2 Minimum columns
- processing date/time
- original file name
- document number
- source type
- raw reference
- final URL
- page number
- resolution status

#### 3.10.3 Functional Requirements
- final URL shall be clickable when present
- empty final URL shall not break row rendering
- rows shall be sortable by newest processing first

---

### 3.11 File Movement

#### 3.11.1 Description
Processed files shall be moved out of the input folder.

#### 3.11.2 Functional Requirements
- successful files shall be moved to processed folder
- fatally failed files should be moved to error folder
- movement actions shall be logged
- filename collisions in destination folders shall be handled safely

---

### 3.12 Export

#### 3.12.1 Description
Users shall be able to export result data.

#### 3.12.2 Functional Requirements
- export CSV
- export Markdown
- export should respect active filters if implemented
- exported output should contain one row per reference

---

### 3.13 Audit Logging

#### 3.13.1 Description
Basic traceability is required.

#### 3.13.2 Functional Requirements
The system shall log:
- login success/failure
- batch start/end
- per-file processing outcome
- export actions
- major errors

---

## 4. External Interface Requirements

### 4.1 User Interface

#### 4.1.1 Login page
Fields:
- username
- password

Actions:
- submit
- error display

#### 4.1.2 Home / dashboard
Displays:
- total processed documents
- total references found
- last batch status
- process-batch button

#### 4.1.3 Results page
Displays:
- table of references
- filters (optional minimal)
- export buttons

#### 4.1.4 Document detail page
Displays:
- file metadata
- extracted document number
- all references for the document
- processing log summary

---

### 4.2 Software Interfaces

#### 4.2.1 PostgreSQL
Purpose:
- primary application data store

#### 4.2.2 MariaDB
Purpose:
- credential validation source

#### 4.2.3 Filesystem
Purpose:
- input folder
- processed folder
- error folder

#### 4.2.4 HTTP network access
Purpose:
- resolve URL redirects

---

## 5. Data Requirements

### 5.1 Logical Data Model

#### 5.1.1 `users_audit`
Tracks application usage events.

Suggested fields:
- id
- username
- action
- action_detail
- ip_address
- created_at

#### 5.1.2 `documents`
One row per ingested file.

Suggested fields:
- id
- original_file_name
- original_path
- content_hash
- file_size_bytes
- modified_at
- page_count
- document_number
- processing_status
- processing_error
- processed_at
- moved_to_path
- created_at
- updated_at

#### 5.1.3 `document_references`
One row per detected reference.

Suggested fields:
- id
- document_id
- page_number
- source_type
- reference_class
- raw_reference
- final_url
- resolution_status
- http_status
- created_at

#### 5.1.4 `batch_runs`
Tracks each manual run.

Suggested fields:
- id
- triggered_by
- started_at
- finished_at
- status
- total_files_seen
- total_files_processed
- total_references_found
- notes

#### 5.1.5 `processing_logs`
Optional detailed technical logs.

Suggested fields:
- id
- batch_run_id
- document_id
- level
- step_name
- message
- created_at

---

## 6. Suggested PostgreSQL DDL (Starter Draft)

```sql
CREATE TABLE batch_runs (
    id BIGSERIAL PRIMARY KEY,
    triggered_by VARCHAR(255) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    total_files_seen INTEGER NOT NULL DEFAULT 0,
    total_files_processed INTEGER NOT NULL DEFAULT 0,
    total_references_found INTEGER NOT NULL DEFAULT 0,
    notes TEXT NULL
);

CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    batch_run_id BIGINT NULL REFERENCES batch_runs(id) ON DELETE SET NULL,
    original_file_name TEXT NOT NULL,
    original_path TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    modified_at TIMESTAMPTZ NULL,
    page_count INTEGER NULL,
    document_number VARCHAR(255) NULL,
    processing_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    processing_error TEXT NULL,
    processed_at TIMESTAMPTZ NULL,
    moved_to_path TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_documents_content_hash
    ON documents(content_hash);

CREATE INDEX ix_documents_document_number
    ON documents(document_number);

CREATE INDEX ix_documents_processing_status
    ON documents(processing_status);

CREATE TABLE document_references (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    reference_class VARCHAR(50) NOT NULL,
    raw_reference TEXT NOT NULL,
    final_url TEXT NULL,
    resolution_status VARCHAR(50) NOT NULL DEFAULT 'raw_only',
    http_status INTEGER NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_document_references_document_id
    ON document_references(document_id);

CREATE INDEX ix_document_references_source_type
    ON document_references(source_type);

CREATE TABLE users_audit (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    action_detail TEXT NULL,
    ip_address VARCHAR(64) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE processing_logs (
    id BIGSERIAL PRIMARY KEY,
    batch_run_id BIGINT NULL REFERENCES batch_runs(id) ON DELETE SET NULL,
    document_id BIGINT NULL REFERENCES documents(id) ON DELETE CASCADE,
    level VARCHAR(20) NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 7. API Requirements

### 7.1 Web-first principle
The application is primarily a web app. API endpoints may exist for internal use and future automation.

### 7.2 Suggested endpoints

#### Auth
- `GET /login`
- `POST /login`
- `POST /logout`

#### Batch
- `POST /batch/process`
- `GET /batch/runs`
- `GET /batch/runs/{id}`

#### Results
- `GET /results`
- `GET /documents/{id}`
- `GET /exports/csv`
- `GET /exports/markdown`

#### Health/Admin
- `GET /healthz`
- `GET /readyz`

---

## 8. Processing Logic Requirements

### 8.1 Batch flow
For each file:
1. register document
2. extract text
3. derive document number
4. scan QR
5. extract text URLs
6. classify references
7. resolve final URL for URL-like values
8. persist rows
9. move file
10. update status

### 8.2 Failure behavior
- Per-file failure shall not abort the batch.
- The file status shall be marked appropriately.
- The reason shall be logged.

### 8.3 Duplicate behavior
- Exact duplicate content hash may be skipped or marked duplicate.
- Same filename with different content hash must be processed as new.

---

## 9. Security Requirements

### 9.1 Authentication
- username/password required
- session-based authentication acceptable
- password must not be re-stored in PostgreSQL

### 9.2 Authorization
- simple authenticated-access model acceptable for first release

### 9.3 Secrets handling
- DB credentials and secret keys must come from environment variables or Docker secrets
- no secrets hardcoded in repository

### 9.4 Network
- app shall bind only on internal host/network as configured
- no public exposure assumed

---

## 10. Performance Requirements

### 10.1 Target load
- around 50 files/day
- average 5 pages/file
- <= 10 concurrent users

### 10.2 Performance targets
- login response should feel immediate under normal LAN conditions
- results table should load in acceptable time for typical dataset sizes
- batch processing should complete without blocking future page loads excessively

Initial implementation may process synchronously if practical; move to background worker only if operationally necessary.

---

## 11. Reliability and Recovery

### 11.1 Logging
Structured logs should be produced to stdout and, optionally, persisted in DB for selected events.

### 11.2 Restart behavior
Application restarts should not corrupt already persisted batch/document/reference records.

### 11.3 Partial failures
If URL resolution fails but extraction succeeds:
- raw reference must still be saved
- file should not be marked completely failed solely because resolution failed

---

## 12. Deployment Requirements

### 12.1 Dockerfile
Application shall be containerized.

### 12.2 Compose
A `docker-compose.yml` should at minimum define:
- app service
- mounted folders
- environment variables

Since PostgreSQL and MariaDB are external/native, they need not be containerized here.

### 12.3 Example compose
```yaml
services:
  app:
    build: .
    container_name: olre-app
    ports:
      - "8080:8080"
    environment:
      APP_ENV: production
      APP_HOST: 0.0.0.0
      APP_PORT: 8080
      POSTGRES_HOST: ${POSTGRES_HOST}
      POSTGRES_PORT: ${POSTGRES_PORT}
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      MARIADB_HOST: ${MARIADB_HOST}
      MARIADB_PORT: ${MARIADB_PORT}
      MARIADB_DB: ${MARIADB_DB}
      MARIADB_USER: ${MARIADB_USER}
      MARIADB_PASSWORD: ${MARIADB_PASSWORD}
      INPUT_DIR: /data/input
      PROCESSED_DIR: /data/processed
      ERROR_DIR: /data/error
      SECRET_KEY: ${SECRET_KEY}
    volumes:
      - /srv/olre/input:/data/input
      - /srv/olre/processed:/data/processed
      - /srv/olre/error:/data/error
    restart: unless-stopped
```

---

## 13. Acceptance Criteria

The system is accepted when all of the following are true:

1. A user can log in using existing MariaDB-backed credentials.
2. A user can manually trigger a batch from the UI.
3. The app processes PDFs from the input folder.
4. QR payloads are detected from arbitrary page positions.
5. URL-like strings are extracted from text content.
6. One row per reference is stored and rendered in results.
7. Final URLs are resolved when possible.
8. Non-URL QR payloads are still stored.
9. Processed files are moved to the processed folder.
10. CSV and Markdown exports work.
11. The app runs in Docker on the Debian server within the LAN.

---

## 14. Outstanding Clarifications Required Before Coding Auth Module

1. MariaDB hostname/database name
2. target user table name
3. username column name
4. password column name
5. active/inactive column if any
6. password hash algorithm
7. any salt/legacy scheme
8. permission to read from that DB using application account

Without these, the auth module cannot be finished reliably.

---

## 15. Recommended Immediate Next Steps

1. Create repository
2. Commit PRD/PRP/SRS to `docs/`
3. Confirm MariaDB auth schema
4. Generate project skeleton
5. Implement PostgreSQL models + migrations
6. Implement login flow
7. Implement single-file process pipeline
8. Expand to full batch
