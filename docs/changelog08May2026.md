# OLRE Project Status Handoff

Date: 2026-05-08

## Current Runtime Status

OLRE v0.9.5 development/testing environment is now successfully running on:

* Debian 13 server
* Python venv runtime
* SQLite-first deployment model
* FastAPI + Uvicorn
* No Docker dependency yet
* ENABLE_AUTH=false public mode

Both local and Debian server runtime verification have been completed.

---

# Server Environment

## Server Path

```bash
/opt/official-letter-reference-extractor
```

## Runtime

```bash
python3.13
venv
sqlite:///data/olre.sqlite3
```

## Runtime Start Command

```bash
source .venv/bin/activate

python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 7777
```

---

# Important Environment Notes

## .env Runtime

Current production-style runtime uses:

```env
APP_PORT=7777
DATABASE_URL=sqlite:///data/olre.sqlite3
ENABLE_AUTH=false
APP_LANG=th
```

---

# Verification Completed Successfully

## Core Runtime

* FastAPI startup OK
* SQLite migrations OK
* Runtime path validation OK
* Cleanup startup sweep OK
* Thai UI OK
* Wide operational layout OK

---

# Functional Verification Completed

## Upload Flow

Verified:

* PDF upload
* Inbox listing
* Batch processing
* File retention behavior

---

## QR Extraction

Verified:

* Image-only PDF flow
* OCR disabled mode
* QR extraction without Tesseract
* Multi-reference extraction

---

## URL Resolution

Verified:

* Google Drive URLs
* Google Forms URLs
* Redirect handling
* Structured resolution logging

Known external SSL issue:

```text
shorten.moph.go.th
```

returns incomplete certificate chain.

This is NOT considered an OLRE application bug.

Current behavior is acceptable because:

* extraction succeeds
* URL is preserved
* structured error is logged
* user can still manually open the link

Decision:
DO NOT disable SSL verification globally.

---

# UI Workspace Widening Completed

Implemented wider responsive operational workspace layout.

Pages widened:

* /imports
* /batch
* /results
* /quality
* /dashboard
* /exports

Implementation details:

* `.workspace-wide`
* `min(92vw, 1720px)`
* improved operational table spacing
* improved URL visibility
* responsive preserved

Server verification completed successfully.

---

# Testing Status

## Local pytest

Current result:

```text
63 passed
1 failed
```

Known failing test:

```text
tests/integration/test_runtime_readiness.py
```

Reason:
`.env` now uses:

```env
APP_PORT=7777
```

but test still expects:

```python
8000
```

This is currently considered:

* non-blocking
* test isolation issue
* not a runtime failure

---

# Linux Runtime Discovery

Debian runtime required additional packages:

```bash
apt install -y python3.13-venv
apt install -y libxcb1 libgl1
```

These are important for future Docker packaging.

---

# Git Workflow Established

Recommended workflow:

## Local

```text
develop
test
commit
push
```

## Server

```text
git pull
runtime verify
```

GitHub is now considered the source of truth.

Avoid editing production/server code directly.

---

# Current Known Issues

## 1. Runtime readiness test

Expected:

```python
app_port == 8000
```

Actual:

```python
7777
```

Needs future test isolation cleanup.

---

## 2. Long filename warnings on server

Example:

```text
File name too long
```

Occurs in:

```text
data/processed/
```

Does not currently affect runtime behavior.

Likely related to:

* terminal/git path display
* UTF-8 Thai filenames
* Linux path length handling

No immediate action required.

---

# Suggested Next Phase

## Recommended next milestone

```text
v0.9.5 Docker SQLite-first packaging
```

Suggested goals:

* zero-setup runtime
* Dockerfile hardening
* docker-compose verification
* persistent SQLite volume
* runtime dependency packaging
* deployment documentation
* optional systemd service
* production startup script

---

# Suggested Future Improvements

## Runtime/Test

* isolate pytest from `.env`
* `.env.test`
* configurable runtime test expectations

## UI

* favicon
* optional sticky filters
* optional table column resize
* optional dark mode

## URL Resolution

Possible future enhancement:

```text
SSL_CERTIFICATE_VERIFY_FAILED
```

as structured error subtype instead of generic resolution fail.

Do NOT bypass SSL verification globally.

---

# Current Overall Assessment

Current state is now beyond prototype stage.

OLRE currently has:

* stable SQLite runtime
* verified Debian deployment
* operational UI
* reporting/export flows
* structured error handling
* responsive operational workspace
* production-style runtime validation

Project status:

```text
Operational beta / deployment-hardening phase
```
