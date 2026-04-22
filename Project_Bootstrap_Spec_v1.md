# Project Bootstrap Spec v1 — Official Letter Reference Extractor (OLRE)

Version: 1.0  
Status: Ready to bootstrap repository  
Target stack: FastAPI + PostgreSQL + MariaDB auth + PyMuPDF + OpenCV  
Deployment target: Docker on Debian physical server (LAN only)

---

## 1. Project Identity

### Recommended repository name
`official-letter-reference-extractor`

### Short internal name
`olre`

### Suggested branch strategy
- `main` = production-ready
- `develop` = integration branch
- feature branches:
  - `feature/bootstrap`
  - `feature/auth-mariadb`
  - `feature/postgres-schema`
  - `feature/pdf-extraction`
  - `feature/qr-detection`
  - `feature/url-resolution`
  - `feature/export`
  - `feature/web-ui`

---

## 2. Bootstrap Goal

Create a working project skeleton that can:

1. run as a FastAPI app
2. connect to PostgreSQL
3. connect to MariaDB
4. load configuration from environment variables
5. render a login page
6. expose health endpoints
7. prepare directories and module boundaries for later implementation

This bootstrap phase does **not** need to complete the full business logic yet.  
It needs to establish a clean, stable foundation.

---

## 3. Target Repository Layout

```text
official-letter-reference-extractor/
├─ README.md
├─ .gitignore
├─ .env.example
├─ docker-compose.yml
├─ Dockerfile
├─ pyproject.toml
├─ alembic.ini
├─ docs/
│  ├─ PRD_v2.md
│  ├─ PRP_v2.md
│  ├─ SRS_v2.md
│  └─ Project_Bootstrap_Spec_v1.md
├─ migrations/
│  ├─ env.py
│  └─ versions/
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ config.py
│  ├─ logging_config.py
│  ├─ dependencies.py
│  ├─ db/
│  │  ├─ __init__.py
│  │  ├─ postgres.py
│  │  ├─ mariadb.py
│  │  ├─ base.py
│  │  └─ models.py
│  ├─ auth/
│  │  ├─ __init__.py
│  │  ├─ service.py
│  │  ├─ schemas.py
│  │  └─ session.py
│  ├─ batch/
│  │  ├─ __init__.py
│  │  ├─ service.py
│  │  ├─ scanner.py
│  │  └─ file_ops.py
│  ├─ extraction/
│  │  ├─ __init__.py
│  │  ├─ pdf_reader.py
│  │  ├─ qr_detector.py
│  │  ├─ url_extractor.py
│  │  ├─ docno_extractor.py
│  │  └─ normalizer.py
│  ├─ resolver/
│  │  ├─ __init__.py
│  │  ├─ service.py
│  │  └─ classifier.py
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ process_document.py
│  │  └─ export_service.py
│  ├─ web/
│  │  ├─ __init__.py
│  │  ├─ routes_auth.py
│  │  ├─ routes_home.py
│  │  ├─ routes_batch.py
│  │  ├─ routes_results.py
│  │  └─ templates/
│  │     ├─ base.html
│  │     ├─ login.html
│  │     ├─ home.html
│  │     └─ results.html
│  ├─ api/
│  │  ├─ __init__.py
│  │  └─ routes.py
│  └─ static/
│     └─ css/
│        └─ app.css
├─ tests/
│  ├─ __init__.py
│  ├─ conftest.py
│  ├─ unit/
│  ├─ integration/
│  └─ fixtures/
└─ scripts/
   ├─ dev_run.sh
   └─ smoke_test.py
```

---

## 4. Technology Decisions

### Backend
- Python 3.11
- FastAPI
- Uvicorn

### Templates/UI
- Jinja2
- HTMX (optional from first iteration)
- simple CSS, no SPA

### Database
- SQLAlchemy 2.x
- PostgreSQL driver:
  - `psycopg[binary]` or `psycopg2-binary`
- MariaDB/MySQL driver:
  - `pymysql`

### PDF / QR / URL
- PyMuPDF
- OpenCV
- httpx

### Validation / Settings
- Pydantic v2
- pydantic-settings

### Sessions / Security
- signed cookie session or server-side session abstraction
- pass-through auth check against MariaDB source

### Migration
- Alembic

### Quality
- pytest
- ruff
- black (optional if preferred)
- mypy (optional for later)

---

## 5. Bootstrap Deliverables

At the end of bootstrap, the repo should contain:

### D1. App startup
- `uvicorn app.main:app --reload` works locally
- `/healthz` returns healthy JSON
- `/readyz` verifies app can start and at least load config

### D2. Configuration
- `app/config.py` centralizes environment config
- `.env.example` documents all required variables

### D3. Database wiring
- PostgreSQL connection factory
- MariaDB connection factory
- a simple DB ping method for each

### D4. Basic web pages
- `/login`
- `/`
- static base layout
- placeholder home page after login

### D5. Logging
- structured logging to stdout
- request logging basic middleware
- app startup/shutdown logs

### D6. Dockerization
- Dockerfile
- docker-compose.yml
- mounted folders for input/processed/error

### D7. Test scaffold
- at least one smoke test
- one config-loading test
- one DB module import test

---

## 6. Minimum File Contents Expected

### 6.1 `pyproject.toml`
Must include:
- project metadata
- dependencies
- dev dependencies
- pytest config
- ruff config (if used)

Suggested dependencies:
- fastapi
- uvicorn[standard]
- jinja2
- sqlalchemy
- psycopg[binary]
- pymysql
- pydantic
- pydantic-settings
- python-multipart
- itsdangerous
- httpx
- pymupdf
- opencv-python-headless

Suggested dev dependencies:
- pytest
- pytest-cov
- ruff

### 6.2 `app/config.py`
Must define application settings class for:
- app host/port/env
- postgres
- mariadb
- directories
- secret key
- logging
- URL resolver timeout

### 6.3 `app/main.py`
Must:
- create FastAPI app
- register routers
- mount static files
- configure templates
- expose `/healthz` and `/readyz`

### 6.4 `app/db/postgres.py`
Must:
- build SQLAlchemy engine
- expose session factory
- support test connection/ping

### 6.5 `app/db/mariadb.py`
Must:
- build SQLAlchemy engine or a read-only connector
- expose test connection/ping
- prepare for auth query integration

### 6.6 `app/web/routes_auth.py`
Must:
- GET login page
- POST login placeholder
- support future DB auth implementation
- return useful validation errors

### 6.7 `Dockerfile`
Must:
- use Python 3.11-slim
- install system dependencies for OpenCV/PyMuPDF if needed
- copy project
- install dependencies
- run uvicorn

### 6.8 `docker-compose.yml`
Must:
- run app container
- map port 8080:8080
- mount:
  - `/srv/olre/input`
  - `/srv/olre/processed`
  - `/srv/olre/error`

---

## 7. Environment Variables

Create `.env.example` with:

```env
APP_NAME=Official Letter Reference Extractor
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8080
SECRET_KEY=change-me-to-a-long-random-secret
LOG_LEVEL=INFO

POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=olre
POSTGRES_USER=olre_user
POSTGRES_PASSWORD=change-me

MARIADB_HOST=127.0.0.1
MARIADB_PORT=3306
MARIADB_DB=attendance_db
MARIADB_USER=readonly_user
MARIADB_PASSWORD=change-me

INPUT_DIR=/data/input
PROCESSED_DIR=/data/processed
ERROR_DIR=/data/error

URL_RESOLVE_TIMEOUT_SECONDS=15
PDF_RENDER_DPI=250
OCR_ENABLED=false
```

---

## 8. Initial README Contents

`README.md` should contain at minimum:

1. project purpose
2. stack summary
3. local run instructions
4. docker run instructions
5. env setup
6. current implementation status
7. roadmap

Suggested opening:

```md
# Official Letter Reference Extractor (OLRE)

Internal LAN web application for scanning official-letter PDFs, extracting QR payloads and URLs, resolving final URLs, and presenting one row per reference.
```

---

## 9. Bootstrap Acceptance Criteria

Bootstrap is complete when:

- project can be installed
- app starts without crashing
- login page renders
- config loads from environment
- PostgreSQL ping endpoint/service works
- MariaDB ping endpoint/service works
- Docker build succeeds
- Docker container starts on port 8080
- repository structure is clean and documented

---

## 10. Recommended Initial PostgreSQL Model Stubs

Create model stubs only at bootstrap stage:

- `BatchRun`
- `Document`
- `DocumentReference`
- `UserAudit`
- `ProcessingLog`

Fields may be skeletal at first, but names should match SRS where possible.

---

## 11. Suggested First Migration

First migration should create these tables:

- `batch_runs`
- `documents`
- `document_references`
- `users_audit`
- `processing_logs`

Do not wait too long to introduce migrations.  
Schema drift becomes free-range chaos surprisingly fast.

---

## 12. Recommended First Codex Prompt

Use this prompt in the repo root after copying docs into `docs/`:

```text
Read docs/PRD_v2.md, docs/PRP_v2.md, docs/SRS_v2.md, and docs/Project_Bootstrap_Spec_v1.md.

Bootstrap a clean FastAPI project for Official Letter Reference Extractor (OLRE) with:
- Python 3.11
- app/main.py
- app/config.py
- app/logging_config.py
- app/db/postgres.py
- app/db/mariadb.py
- app/web/routes_auth.py
- app/web/routes_home.py
- Jinja2 templates for base.html, login.html, home.html
- SQLAlchemy 2.x setup
- Alembic initialization files
- Dockerfile
- docker-compose.yml
- pyproject.toml
- .env.example
- README.md
- minimal tests

Requirements:
- use environment-based config
- add /healthz and /readyz
- create placeholder login POST flow without final auth logic
- keep code modular and documented
- do not implement full business logic yet
- make the project runnable
```

---

## 13. Recommended Second Codex Prompt

After bootstrap succeeds:

```text
Implement PostgreSQL models and Alembic migration for:
- batch_runs
- documents
- document_references
- users_audit
- processing_logs

Follow docs/SRS_v2.md exactly where applicable.
Use SQLAlchemy 2.x declarative models.
Add unit tests for model imports and metadata creation.
```

---

## 14. Recommended Third Codex Prompt

After DB models succeed:

```text
Implement MariaDB-backed authentication integration.

Requirements:
- read MariaDB connection settings from app/config.py
- create an auth service module
- do not hardcode schema names
- make table/column names configurable for now
- provide a placeholder password verification adapter
- build GET /login and POST /login with session creation
- log login success/failure to users_audit in PostgreSQL
- keep the code ready for final password-hash integration once schema is confirmed
```

---

## 15. Questions to Lock Before Full Auth Implementation

These are the most important pending questions.

### Q1. MariaDB auth source
- Database name?
- Table name?
- Username column?
- Password column?
- Active/inactive flag column?
- Display name column if any?

### Q2. Password storage
- Plain text?
- MD5?
- SHA1?
- bcrypt?
- Argon2?
- custom legacy scheme?

Without this, auth implementation is guesswork wearing a tie.

### Q3. Login policy
- All users in that table can log in?
- Or only selected staff?
- Need role column now or later?

### Q4. Session behavior
- Session timeout after how long?
- Example default suggestion: 8 hours

---

## 16. Questions to Lock Before Extraction Implementation

### Q5. Document number patterns
Currently confirmed example:
- `ลพ 0033.02/ว 6176` -> `ว6176`

Need more examples:
- `/1234`
- `/ด่วนที่สุด 123`
- `/กค 12`
- `/วช 88`
- `/อก 14`
- `/123/2569` (if any)

### Q6. Search scope for doc number
Should extraction:
- search page 1 first, then fallback all pages
- or search all pages immediately

Recommendation:
- page 1 first
- fallback all pages if not found

### Q7. Duplicate references in same file
If the same URL appears twice in one PDF:
- store both occurrences
- or store once per document

Recommendation:
- store once per document + page
- optional dedupe identical same-page duplicates

### Q8. Resolution failure label
Preferred UI status:
- `resolved`
- `raw_only`
- `resolve_failed`
- `non_url`

Recommendation:
- use all four

---

## 17. Local Development Commands

Suggested commands:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
uvicorn app.main:app --reload
```

Windows PowerShell equivalent:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .
uvicorn app.main:app --reload
```

---

## 18. Suggested Git Commit Sequence

### Commit 1
`docs: add PRD PRP SRS and bootstrap spec`

### Commit 2
`chore: bootstrap FastAPI project structure`

### Commit 3
`feat: add config loading and health endpoints`

### Commit 4
`feat: add postgres and mariadb connection modules`

### Commit 5
`feat: add login page and auth placeholders`

### Commit 6
`feat: add initial postgres schema and migrations`

### Commit 7
`test: add smoke tests for startup and config`

---

## 19. Immediate Next Step

The next practical move is:

1. create repo `official-letter-reference-extractor`
2. copy the v2 docs + this bootstrap spec into `docs/`
3. run the first Codex bootstrap prompt
4. send me:
   - generated file tree
   - `pyproject.toml`
   - `app/main.py`
   - `app/config.py`
   - `docker-compose.yml`

Then I will review and tighten it before you continue.

---

## 20. Definition of Ready for Coding

You are ready to begin coding when all of these are true:

- repo created
- docs committed
- bootstrap prompt prepared
- Python version chosen
- target Debian host confirmed
- PostgreSQL access credentials ready
- MariaDB read-only credentials ready
- folder paths decided:
  - input
  - processed
  - error

Once those are in place, implementation can start cleanly instead of improvising into a swamp.
