# OLRE Project Status Handoff

Date: `2026-05-08`

## Current Project State

OLRE has successfully transitioned from:

- prototype/runtime experiment

to:

- deployable operational system

Current maturity:

```text
Operational Beta
Deployment-Hardening Phase
```

Core runtime models now verified:

- Python venv runtime
- Docker runtime
- SQLite-first deployment
- Debian 13 deployment
- Public operational mode

---

## Current Runtime Architecture

### Runtime Stack

- FastAPI
- Uvicorn
- SQLite
- Alembic
- Docker Compose
- Python 3.11/3.13 compatible runtime
- Thai-first operational UI

### Deployment Model

Current official deployment direction:

```text
SQLite-first
single-container
low-friction deployment
```

NOT:

- PostgreSQL-first
- MariaDB auth-first
- multi-container DB stack

---

## Verified Runtime Environments

### Local Runtime

Verified:

- venv runtime
- pytest
- alembic migrations
- upload/batch/results flow

### Debian 13 Runtime

Verified:

- uvicorn runtime
- SQLite persistence
- runtime cleanup
- Thai UI
- wide operational layout

### Docker Runtime

Verified successfully:

```bash
docker compose up -d --build
```

Verified:

- container startup
- healthcheck
- persistent volume
- SQLite runtime
- startup migrations
- browser access
- operational UI
- LAN access
- restart persistence

Container status:

```text
STATUS = healthy
```

---

## Current Runtime Defaults

### `.env`

```env
APP_PORT=7777
ENABLE_AUTH=false
APP_LANG=th
DATABASE_URL=sqlite:///data/olre.sqlite3
```

### Docker Runtime

Docker runtime currently uses:

```env
DATABASE_URL=sqlite:////app/data/olre.sqlite3
```

Persistent runtime volume:

```text
/app/data
```

---

## Major Milestones Completed

### SQLite-first Runtime

Completed:

- `DATABASE_URL` single source of truth
- SQLite runtime verification
- runtime path validation
- startup cleanup verification

### Wide Operational UI

Implemented:

- workspace-wide layout
- responsive operational tables
- improved URL visibility
- wide dashboard/results/imports/export pages

### Docker Packaging

Implemented:

- `Dockerfile`
- `docker-compose.yml`
- startup script
- persistent volumes
- runtime healthcheck
- runtime dependency packaging
- deployment documentation

Verified:

- `docker compose build`
- `docker compose up -d --build`
- health endpoint
- persistence across restart

---

## QR Extraction Enhancements

### Lower-left QR Improvements

Enhanced targeted QR detection strategies:

- `bottom_left_deep`
- `lower_left_25_percent`
- `lower_left_30_percent`
- `qr_label_region`
- `left_band_40_65_percent`
- `left_band_45_70_percent`
- `left_lower_mid_35_percent`
- `qr_label_band`

Additional focused passes:

- adaptive threshold
- low contrast adaptive threshold
- upscaled_3x
- upscaled_4x

Purpose:

Improve real-world scanned government document QR extraction where:

- QR is small
- QR is blurry
- QR is image-only
- QR is positioned left middle-lower
- QR is not truly in lower 25% of the page

---

## QR Debug Improvements

QR debug metadata now includes:

- `strategy_name`
- `zone`
- `variant`
- `crop_bounds`
- `decode_status`
- success/fail state

Debug persistence optimized:

- focused regions only
- successful decodes prioritized

Debug UI now shows:

- crop coordinates
- strategy used
- decode state

---

## Destination Classification

Implemented lightweight URL destination classification.

Supported classifications:

| Type | Meaning |
|---|---|
| `form` | Google Forms / operational forms |
| `document` | Google Drive / Docs / PDF |
| `government` | `.go.th` / `.gov` / `.gov.th` |
| `redirect` | known short URL redirect |
| `external` | generic external site |

Stored fields:

- `destination_type`
- `destination_host`
- `requires_user_action`

Results UI improvements:

- destination badges
- operational hints
- user-action-required chip
- host display

Purpose:

Avoid user confusion where:

- QR extraction succeeded
- but destination is a manual Google Form

---

## Testing Status

### Integration Tests

Verified:

```text
46 passed
```

Coverage includes:

- QR debug flow
- batch flow
- UI flow
- Google Form classification
- lower-left QR detection
- OCR-disabled runtime behavior

### Alembic

Verified:

```text
20260508_0009_add_destination_classification
```

Migration applied successfully.

---

## Docker Runtime Verification

Verified on Debian server:

```bash
docker compose down
docker compose up -d --build
curl http://localhost:7777/healthz
docker compose ps
```

Verified output:

```json
{"status":"ok","database_backend":"sqlite"}
```

Container state:

```text
healthy
```

Browser UI access verified successfully.

---

## Current Git Workflow

Recommended workflow:

### Local

```text
develop
test
commit
push
```

### Server

```text
git pull
docker compose up -d --build
verify runtime
```

DO NOT:

- edit production code directly on server

GitHub is now the source of truth.

---

## Current Tags

Verified tags:

```text
v0.9.5-beta-runtime-stable
v0.9.5-docker-beta
```

---

## Current Known Issues

### 1. `DATABASE_URL` Consistency

Current runtime logs still show:

```text
sqlite:///data/olre.sqlite3
```

while Docker runtime uses:

```text
sqlite:////app/data/olre.sqlite3
```

Needs future cleanup for absolute-path consistency.

### 2. Windows CRLF Warnings

Current Windows Git warnings:

```text
LF will be replaced by CRLF
```

Not currently blocking runtime.

### 3. Long UTF-8 Filename Warnings

Observed occasionally on Linux:

```text
File name too long
```

Likely related to:

- Thai filenames
- path depth
- UTF-8 handling

Future recommendation:

- content-addressable storage strategy

---

## Suggested Next Phase

Recommended next branch:

```bash
git checkout -b hardening/runtime-profiles-backup-and-storage
```

Focus areas:

- `.env` separation
- runtime isolation
- backup/restore verification
- SQLite WAL-safe backup
- storage strategy
- path consistency
- operational cleanup
- persistence documentation

---

## Recommended Future Architecture Direction

Possible future modules:

- OLRE Core
- OLRE Resolver
- OLRE Analytics
- OLRE UI

Potential future capabilities:

- broken link monitoring
- domain analytics
- inter-agency reference analysis
- suspicious URL scoring
- operational metrics dashboard

---

## Current Overall Assessment

Current OLRE state:

```text
Deployable operational document intelligence system
```

No longer:

- prototype
- dev-only tool
- workstation-only runtime

Current strengths:

- reproducible deployment
- operational persistence
- Docker runtime
- structured runtime validation
- operational UI
- QR intelligence improvements
- destination awareness
- production-oriented architecture direction
