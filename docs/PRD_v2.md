# PRD — Official Letter Reference Extractor (OLRE)
Version: 2.0  
Status: Draft for implementation  
Target environment: LAN on Debian physical server

---

## 1. Executive Summary

Official Letter Reference Extractor (OLRE) is an internal web application that scans batches of official-letter PDFs, extracts QR code payloads and URLs/short URLs, resolves final destination URLs when possible, and presents the results in a searchable table. The system is designed for LAN-only deployment, manual batch execution, and moderate daily volume.

The primary business value is reducing manual work: staff no longer need to open each PDF individually or use a mobile phone to scan QR codes. Instead, the system processes the folder contents and produces a normalized result set with one row per reference found.

---

## 2. Problem Statement

Current pain points:

- Official letters arrive as PDF files in varying formats.
- Files may contain QR codes, short URLs, or embedded full URLs.
- Staff must inspect files manually to find external references.
- QR codes are often accessed via mobile phone, which is inefficient for desk-based work.
- File names are inconsistent and cannot be relied on for document identification.
- There is no structured result table that consolidates extracted references across files.

---

## 3. Product Vision

Provide a practical internal tool that:

1. Processes all PDFs in a designated input folder.
2. Finds references regardless of QR location on the page.
3. Works with mixed PDF types: text-layer PDFs and image-based scans.
4. Outputs normalized results with one row per detected reference.
5. Moves processed files to a processed folder.
6. Uses existing infrastructure where possible:
   - PostgreSQL on the Debian server for application data
   - MariaDB on the LAN for username/password authentication

---

## 4. Product Goals

### 4.1 Primary Goals
- Eliminate the need to manually inspect every PDF for QR/URL references.
- Allow staff to access referenced documents directly from a PC.
- Build a reusable and auditable internal record of extracted references.
- Support approximately 50 PDF files/day, average 5 pages/file.

### 4.2 Secondary Goals
- Provide export to CSV and Markdown.
- Provide a simple usage log through login records.
- Support later extension to OCR fallback tuning, scheduler support, and dashboarding.

### 4.3 Non-Goals (Phase 1 / v1 Implementation)
- Public internet deployment
- Reverse proxy sub-path support
- Automated schedule execution
- Deep analytics dashboard
- Full DMS / records-management workflow
- SSO / LDAP / OAuth integration
- Automatic ingestion from external e-saraban APIs

---

## 5. Users and Stakeholders

### 5.1 Primary Users
- Records / correspondence staff
- Administrative staff
- IT / Digital Health team

### 5.2 Secondary Users
- Managers who want to inspect referenced attachments
- System administrator / developer

### 5.3 Stakeholders
- Project owner
- IT operations
- Data / DB administrators
- End-user department representatives

---

## 6. Assumptions and Constraints

### 6.1 Known Assumptions
- PDFs are received online and placed into a designated folder manually or via existing internal workflow.
- Files are processed by manual batch trigger.
- A document may contain zero, one, or multiple references.
- A reference may come from:
  - QR payload
  - text-layer URL
- QR payloads that are not URLs must still be stored.
- Final URLs should be shown even if they require login to access.
- File names are not reliable identifiers.

### 6.2 Technical Constraints
- Runs in LAN only.
- App runs in container(s).
- Main application data must use existing PostgreSQL on physical Debian.
- Login must use username/password stored in an existing MariaDB database on the LAN.
- Maximum concurrent users expected: <= 10.

---

## 7. User Stories

### US-01 Batch processing
As a staff user, I want to point the system at a folder of PDFs and process all pending files, so that I do not need to open and inspect each file manually.

### US-02 One row per reference
As a user, I want the result table to show one row per detected reference, so I can clearly see all references even when multiple are found in one document.

### US-03 Document number extraction
As a user, I want the system to extract the document reference suffix after `/`, such as `ว 6176`, and normalize it to `ว6176`, so I can identify the official letter more easily.

### US-04 QR location independence
As a user, I want the system to detect QR codes anywhere on any page, so the result is not dependent on document layout.

### US-05 Raw payload retention
As a user, I want non-URL QR payloads to still be stored, so nothing potentially useful is discarded.

### US-06 Final URL resolution
As a user, I want short URLs to be resolved to final destination URLs, so I can open the actual attachment page directly.

### US-07 Export
As a user, I want to export the results to CSV and Markdown, so I can report or reuse the results externally.

### US-08 Processed-file handling
As an operator, I want processed PDFs moved to a processed folder, so the input folder remains clean and repeated scanning is controlled.

### US-09 Reprocessing by changed content
As an operator, I want a file with the same name but changed content to be treated as a new file, so the system does not incorrectly skip updated documents.

### US-10 Login and usage tracking
As the project owner, I want users to log in with existing organizational credentials, so I can observe actual interest and usage patterns.

---

## 8. Functional Scope

### 8.1 In Scope
- Folder-based PDF discovery
- Manual batch trigger
- PDF text extraction
- QR detection anywhere on page
- URL extraction from text layer
- Final URL resolution for URL-like references
- Storage of raw references and resolved URL
- Document-number extraction and normalization
- Move processed files
- Result table UI
- CSV export
- Markdown export
- Login using existing MariaDB user table
- Application audit log / usage log

### 8.2 Out of Scope
- OCR-first pipeline for every file
- Automatic scheduler
- Public deployment
- SSO
- Role-based workflow approval
- Document preview rendering in-browser
- Full-text search beyond basic filters

---

## 9. Core Workflow

1. Operator places PDF files into input folder.
2. User logs in to the web application.
3. User clicks “Process batch”.
4. System enumerates files in input folder.
5. For each file:
   - compute file fingerprint
   - register processing job
   - extract text layer
   - scan each page for QR code(s)
   - extract URL patterns from text
   - normalize extracted document number
   - resolve final URL when applicable
   - persist one record per reference
   - move file to processed folder
6. User views results table.
7. User exports CSV or Markdown if needed.

---

## 10. Functional Requirements

### FR-01 Input folder scanning
The system shall scan a configured input folder for PDF files.

### FR-02 Manual execution
The system shall provide a manual batch trigger from the UI and/or admin endpoint.

### FR-03 File identity
The system shall treat files with the same filename but different content as different processing inputs.

### FR-04 File fingerprint
The system shall compute a fingerprint using at minimum:
- file hash
- file size
- modification timestamp
- original file name

### FR-05 PDF support
The system shall support PDFs that contain:
- text layer
- scanned page images
- mixed text/image pages

### FR-06 QR detection
The system shall detect QR codes anywhere on any page and shall not rely on fixed page coordinates.

### FR-07 Multi-reference support
The system shall support zero to many references per document.

### FR-08 URL extraction from text
The system shall extract full URLs and short URLs from PDF text content using regex/pattern matching.

### FR-09 Raw payload retention
The system shall store QR payloads even when they are not valid URLs.

### FR-10 URL resolution
When a reference is URL-like, the system shall attempt to resolve its final destination URL.

### FR-11 Resolution fallback
If a URL cannot be resolved, the system shall keep the original reference value and record the resolution status.

### FR-12 Final URL display
If a final URL exists, it shall be shown in the result table as a clickable link.

### FR-13 Document number extraction
The system shall extract the relevant document number suffix after `/` from the official letter identifier.

### FR-14 Document number normalization
The system shall normalize extracted values such that `ว 6176` becomes `ว6176`.

### FR-15 One row per reference
The result table shall display one row per detected reference.

### FR-16 Processed folder move
After processing completes for a file, the system shall move the file to the processed folder.

### FR-17 Failure isolation
If processing fails for one file, the system shall continue processing remaining files.

### FR-18 Result export
The system shall export results as:
- CSV
- Markdown

### FR-19 Authentication
The system shall authenticate users against the existing MariaDB credential source.

### FR-20 Usage logging
The system shall record login events and major user actions for basic adoption tracking.

---

## 11. Non-Functional Requirements

### NFR-01 Deployment
The system must be deployable in Docker on Debian Linux within the LAN.

### NFR-02 Database integration
The system must use native PostgreSQL on the physical Debian server for application data.

### NFR-03 Moderate scale
The system should comfortably support the expected workload of ~50 files/day with average ~5 pages/file.

### NFR-04 Reliability
A single bad file must not abort the whole batch.

### NFR-05 Maintainability
The codebase should be separated into clear modules:
- auth
- ingestion
- extraction
- resolver
- persistence
- UI/API

### NFR-06 Observability
The application should emit structured logs and keep per-file processing status.

### NFR-07 Performance target
The system should aim for average processing time per typical file within an acceptable operational window, with practical target:
- common case: <= 10 seconds/file
- acceptable upper range for heavier scanned PDFs: <= 30 seconds/file

### NFR-08 Security
The app should be accessible only within the LAN and protected by login.

### NFR-09 Data traceability
The system should preserve enough metadata to audit:
- when a file was processed
- what references were found
- how URL resolution ended
- who triggered processing/export

---

## 12. Success Metrics

### Operational Metrics
- >= 90% of URL-like references are extracted successfully in representative documents
- >= 85% of QR references are detected in representative documents before OCR tuning
- 100% of processed files are moved to processed folder unless error occurs
- 0 full-batch aborts due to a single-file failure

### Adoption Metrics
- Number of unique logins per week
- Number of batch runs per week
- Number of exports per week

### Quality Metrics
- False-positive rate of document-number extraction remains low enough for practical use
- Low incidence of duplicate or skipped files caused by fingerprint errors

---

## 13. Open Questions / Pending Clarifications

1. Which MariaDB table and fields will be used for username/password authentication?
2. What password format is stored there? (plain text / MD5 / bcrypt / Argon2 / custom)
3. Which exact regex variants should be supported for document number extraction beyond `.../ว 6176`?
4. Should document number extraction search only page 1 first, then fallback to all pages, or all pages immediately?
5. When URL resolution fails, which status label is preferred in UI:
   - `raw_only`
   - `resolve_failed`
   - `unreachable`
6. Should duplicate raw references inside the same document be collapsed or stored per occurrence?

---

## 14. Proposed Product Name

Preferred product name:
- **Official Letter Reference Extractor**

Short internal code name:
- **OLRE**

Alternative names:
- GovLetter Link Extractor
- Saraban Reference Extractor
- Letter QR Resolver
