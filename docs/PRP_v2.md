# PRP — Project Realization Plan for Official Letter Reference Extractor (OLRE)
Version: 2.0  
Status: Implementation planning draft

---

## 1. Project Objective

Deliver a production-usable internal web application on the LAN that scans PDF official letters from a folder, extracts QR payloads and URLs, resolves final URLs, stores results in PostgreSQL, authenticates users via existing MariaDB credentials, and supports manual batch processing with exports.

---

## 2. Delivery Strategy

The implementation should prioritize:

1. Correctness over excessive architectural complexity
2. Simplicity of deployment on Debian server
3. Reuse of existing databases
4. Clear separation of modules for future expansion
5. Fast path to working MVP that is still maintainable

This is not a case for premature microservices. A modular monolith is the right first implementation.

---

## 3. Recommended Repository Name

### Preferred repo name
`official-letter-reference-extractor`

### Good short alternative
`olre`

### Other acceptable alternatives
- `saraban-reference-extractor`
- `letter-qr-url-extractor`
- `gov-letter-link-resolver`

### Recommendation
Use:

`official-letter-reference-extractor`

Reason:
- readable
- explicit
- Git-friendly
- still short enough for Docker image naming and CI use

---

## 4. Recommended Architecture

### 4.1 High-Level Style
**Modular monolith** with clear boundaries:

- Web/API layer
- Auth integration layer
- Batch orchestration layer
- PDF extraction layer
- URL resolution layer
- Persistence layer

### 4.2 Runtime Components
For initial deployment, recommend two containers:

1. `app`
   - FastAPI app
   - server-rendered UI
   - API
   - batch processing logic
2. `worker` (optional in v2)
   - initially can be merged into app
   - separate later if batch work grows

Because manual batch is the only requirement right now, a single app container is acceptable for v1 implementation.

---

## 5. Technology Choices

### 5.1 Backend
- Python 3.11+
- FastAPI

### 5.2 Rendering/UI
- Jinja2 templates
- HTMX for low-complexity interactivity
- optional Alpine.js for small UI behavior

Reason:
- avoids SPA overhead
- fast to build with Codex/OpenAI tooling
- easy to maintain internally

### 5.3 PDF/Text/Image Processing
- PyMuPDF (`fitz`) for PDF reading and rendering
- OpenCV for QR detection
- regex extraction for URL/text parsing
- optional OCR fallback later:
  - Tesseract OCR
  - or PaddleOCR if later quality demands it

### 5.4 Database
- PostgreSQL (existing native instance on Debian)

### 5.5 Authentication Source
- Existing MariaDB on LAN
- application uses read-only auth query against the designated user table

### 5.6 HTTP / URL Resolution
- `httpx` preferred
- redirect-follow support
- timeout control
- optional HEAD-first then GET fallback

### 5.7 File Handling
- mounted input folder
- mounted processed folder
- optional error folder

### 5.8 Containerization
- Docker Compose for the app service
- PostgreSQL and MariaDB remain external/native

---

## 6. Delivery Phases

### Phase 0 — Discovery / Lock Critical Unknowns
Must complete before full implementation:
- identify MariaDB auth schema
- verify password hashing method
- collect 20–30 sample PDFs
- confirm document-number regex patterns
- confirm folder paths and permissions
- confirm whether OCR fallback is required in MVP or v1.1

### Phase 1 — Working MVP
Deliver:
- login
- batch process button
- folder scan
- PDF text extraction
- QR detection anywhere
- URL extraction
- final URL resolution
- PostgreSQL persistence
- result table
- processed-folder move
- CSV and Markdown export

### Phase 2 — Hardening
Deliver:
- per-file retry
- better failure statuses
- duplicate handling options
- richer logs
- admin page for batch/job history
- improved document number extraction
- initial OCR fallback for selected failures

### Phase 3 — Operational Improvements
Deliver:
- performance tuning
- optional background queue
- scheduler if needed
- usage dashboard
- alerting / notification for repeated failures

---

## 7. Work Breakdown Structure (WBS)

### 7.1 Foundation
- create repo
- initialize Python project
- establish environment/config strategy
- set up lint/test tooling
- create Dockerfile and compose

### 7.2 Auth integration
- inspect MariaDB schema
- implement login query
- verify password comparison
- add session management
- add login/logout and user audit log

### 7.3 Persistence layer
- define PostgreSQL schema
- implement migrations
- create ORM models or SQL layer
- add repository/service abstraction

### 7.4 Batch ingestion
- scan input folder
- compute fingerprints
- register documents/jobs
- move processed/error files

### 7.5 Extraction engine
- text extraction from PDF
- page rendering
- QR scanning across all pages
- URL extraction from text
- raw payload classification
- document number extraction/normalization

### 7.6 URL resolution
- resolve final URL
- track resolution status
- store raw + final

### 7.7 UI/API
- login page
- dashboard/home page
- batch trigger
- results table
- file detail page
- exports

### 7.8 Testing
- unit tests
- service tests
- sample-file regression tests
- auth integration tests
- end-to-end smoke test

### 7.9 Deployment
- Docker build
- environment variables
- network access config
- logs
- backup considerations

---

## 8. Proposed Project Structure

```text
official-letter-reference-extractor/
├─ README.md
├─ .env.example
├─ docker-compose.yml
├─ Dockerfile
├─ pyproject.toml
├─ alembic.ini
├─ migrations/
├─ docs/
│  ├─ PRD.md
│  ├─ PRP.md
│  └─ SRS.md
├─ app/
│  ├─ main.py
│  ├─ config.py
│  ├─ logging.py
│  ├─ db/
│  │  ├─ postgres.py
│  │  ├─ mariadb.py
│  │  ├─ models.py
│  │  └─ repositories/
│  ├─ auth/
│  │  ├─ service.py
│  │  ├─ schemas.py
│  │  └─ sessions.py
│  ├─ batch/
│  │  ├─ service.py
│  │  ├─ scanner.py
│  │  └─ file_ops.py
│  ├─ extraction/
│  │  ├─ pdf_reader.py
│  │  ├─ qr_detector.py
│  │  ├─ url_extractor.py
│  │  ├─ docno_extractor.py
│  │  └─ normalizer.py
│  ├─ resolver/
│  │  ├─ service.py
│  │  └─ classifiers.py
│  ├─ services/
│  │  ├─ process_document.py
│  │  └─ export_service.py
│  ├─ web/
│  │  ├─ routes_auth.py
│  │  ├─ routes_batch.py
│  │  ├─ routes_results.py
│  │  └─ templates/
│  ├─ api/
│  │  └─ routes.py
│  └─ static/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
└─ scripts/
   ├─ seed_sample_data.py
   └─ run_batch.py
```

---

## 9. Environment Strategy

### 9.1 Required environment variables
```env
APP_NAME=Official Letter Reference Extractor
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8080
SECRET_KEY=change-me
SESSION_COOKIE_NAME=olre_session

POSTGRES_HOST=...
POSTGRES_PORT=5432
POSTGRES_DB=olre
POSTGRES_USER=...
POSTGRES_PASSWORD=...

MARIADB_HOST=...
MARIADB_PORT=3306
MARIADB_DB=...
MARIADB_USER=...
MARIADB_PASSWORD=...

INPUT_DIR=/data/input
PROCESSED_DIR=/data/processed
ERROR_DIR=/data/error

URL_RESOLVE_TIMEOUT_SECONDS=15
PDF_RENDER_DPI=250
LOG_LEVEL=INFO
```

### 9.2 Optional environment variables
```env
OCR_ENABLED=false
BATCH_MAX_FILES_PER_RUN=500
```

---

## 10. Batch Processing Strategy

### 10.1 Discovery
On manual batch execution:
- enumerate all `*.pdf` in input folder
- sort deterministically (for reproducibility)
- skip files already registered by identical fingerprint
- process changed-content same-name files as new inputs

### 10.2 Fingerprint strategy
Recommended:
- SHA-256 of file content
- file size
- modified time
- original file name

Primary uniqueness should rely on **content hash**, not filename.

### 10.3 File movement
After processing:
- success -> move to processed folder
- fatal processing failure -> move to error folder (recommended)
- preserve original filename if possible
- if name collision occurs in processed folder, append timestamp/hash suffix

---

## 11. Extraction Strategy

### 11.1 Text extraction
Use PyMuPDF to:
- read text from each page
- preserve page number context

### 11.2 QR extraction
For every page:
- render page to image
- run QR detection over the full page
- attempt multi-QR detection
- if no result, optionally run preprocessed variants

### 11.3 Reference extraction sources
References originate from:
- text URLs found in page text
- QR payloads detected from page images

### 11.4 URL classification
A reference should be classified as:
- `url`
- `short_url`
- `non_url_payload`
- `invalid_or_unknown`

### 11.5 Final URL resolution
For URL-like values:
- attempt resolution
- follow redirects
- save final URL if obtained
- if not obtained, keep raw reference and save failure status

### 11.6 Document number extraction
Initial rule:
- extract suffix after `/` from relevant official-letter notation
- normalize whitespace removal inside the extracted suffix
- example:
  - raw: `ลพ 0033.02/ว 6176`
  - stored document number: `ว6176`

---

## 12. UI Delivery Plan

### 12.1 Pages
- `/login`
- `/`
- `/batch`
- `/results`
- `/documents/{id}`
- `/exports`

### 12.2 Minimum UX
- simple table-first design
- status badges
- “Process batch” button
- row count summary
- clickable final URL
- export actions
- batch summary after run

### 12.3 Why not SPA
Because:
- lower complexity
- lower maintenance cost
- faster path to usable system
- easier for a small internal app

---

## 13. Testing Plan

### 13.1 Unit tests
- document number normalization
- URL regex extraction
- URL classifier
- resolver fallback logic

### 13.2 Integration tests
- PostgreSQL persistence
- MariaDB auth query
- folder scanning behavior
- processed-folder move logic

### 13.3 Fixture-based extraction tests
Use a curated set of PDFs:
- text-layer PDF with URL
- text-layer PDF with QR
- scanned PDF with QR
- PDF with multiple references
- PDF with non-URL QR payload
- malformed PDF

### 13.4 End-to-end smoke test
- log in
- run batch
- verify rows created
- export CSV
- export Markdown

---

## 14. Risks and Mitigations

### Risk 1: Mixed PDF quality
**Risk:** image-based scans degrade extraction quality  
**Mitigation:** start with QR detection + text extraction; add OCR fallback later

### Risk 2: Unknown MariaDB password format
**Risk:** auth cannot be completed quickly  
**Mitigation:** resolve schema and hashing method first in Phase 0

### Risk 3: URL resolution issues
**Risk:** some links require login or block automated requests  
**Mitigation:** preserve raw reference; show final URL only when resolved; never discard raw value

### Risk 4: Overcomplicated first release
**Risk:** system becomes slower to ship than the actual business need  
**Mitigation:** use modular monolith, server-rendered UI, manual batch only

---

## 15. Recommended First Sprint

### Sprint goal
Deliver a vertical slice that proves the system end-to-end.

### Sprint scope
- repo bootstrap
- config loading
- PostgreSQL connection
- MariaDB test query
- login page
- input folder scan
- PDF registration
- process single PDF manually
- store raw references
- render basic results page

This is the right first sprint because it validates the hardest cross-system dependencies early.

---

## 16. Codex / Pair-Development Recommendation

Since development will be done together with Codex:
- keep modules small and testable
- write clear docstrings
- define fixtures early
- generate tests alongside code, not later
- keep prompts task-scoped, e.g. “implement qr_detector.py with OpenCV and PyMuPDF integration plus unit-testable API”

Recommended workflow:
1. create repo
2. commit docs and skeleton
3. generate config/db/auth modules
4. implement extraction pipeline
5. wire web routes
6. add exports
7. harden with tests

---

## 17. Definition of Done (v1 implementation)

The implementation is done when:

- user can log in with existing MariaDB-backed credentials
- user can trigger batch processing from UI
- app scans all PDFs in input folder
- app extracts references from QR/text
- app stores one row per reference
- app resolves final URL when possible
- app moves processed files
- user can export CSV and Markdown
- app runs in Docker on Debian LAN host
- basic logs and audit records exist
