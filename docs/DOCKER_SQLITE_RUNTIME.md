# Docker SQLite Runtime Guide

OLRE v0.9.5 Docker packaging is intentionally a SQLite-first, single-container runtime. It keeps the public operational deployment model simple:

- one OLRE container
- one persistent Docker volume mounted at `/app/data`
- no PostgreSQL
- no MariaDB
- no Redis
- no Celery
- no external worker or queue service

## Prerequisites

- Docker Engine with Docker Compose plugin
- Port `7777` available on the host

Optional runtime features:

- Tesseract OCR is not required for container startup
- zbar/pyzbar is not required for container startup
- OCR and QR fallback remain optional follow-up runtime choices

## Default Docker Runtime Profile

The Docker runtime defaults are:

```env
APP_PORT=7777
APP_LANG=th
ENABLE_AUTH=false
DATABASE_URL=sqlite:////app/data/olre.sqlite3
INPUT_DIR=/app/data/input
PROCESSED_DIR=/app/data/processed
ERROR_DIR=/app/data/error
QR_DEBUG_DIR=/app/data/debug/qr
RUNTIME_TMP_DIR=/app/data/runtime/tmp
FAILED_RETAINED_DIR=/app/data/runtime/failed-retained
```

The named volume `olre_data` is mounted to `/app/data`, so these paths persist across container restarts.

## Build and Run

Build the image:

```powershell
docker compose build
```

Start the runtime:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:7777
```

## Health Check Verification

Check process health and active database backend:

```powershell
curl http://localhost:7777/healthz
```

Expected:

```json
{"status":"ok","database_backend":"sqlite"}
```

You can also inspect container health:

```powershell
docker compose ps
```

## Upload and Batch Verification

1. Open `http://localhost:7777/imports`
2. Upload one or more PDF files
3. Open `http://localhost:7777/batch`
4. Start a batch run
5. Confirm data appears in:

- `/results`
- `/dashboard`
- `/quality`
- `/exports`

## Persistence Verification

Start detached:

```powershell
docker compose up -d
```

Stop containers without deleting data:

```powershell
docker compose down
```

Start again:

```powershell
docker compose up -d
```

Verify persistence:

- previously uploaded PDFs still exist in the inbox, processed, or retained runtime directories as expected
- previously generated exports still remain under `/app/data`
- `/healthz` still returns SQLite
- previously processed data still appears in `/results`

## Inspect Logs

```powershell
docker compose logs -f
```

Or for the OLRE service only:

```powershell
docker compose logs -f olre
```

## Safe Stop and Removal

Stop and remove containers but keep data:

```powershell
docker compose down
```

This does not remove the named volume.

Remove containers and volume intentionally:

```powershell
docker compose down -v
```

Use `-v` only when you intentionally want to delete the SQLite database and persisted runtime files.

## Backup and Restore Note

The Docker volume contains:

```text
/app/data/olre.sqlite3
/app/data/olre.sqlite3-wal
/app/data/olre.sqlite3-shm
/app/data/input
/app/data/processed
/app/data/error
/app/data/debug/qr
/app/data/runtime
```

For SQLite backup safety, include the database file and any WAL sidecars. See also:

- [Backup and restore guide](BACKUP_RESTORE.md)

If you prefer file-level backup visibility, you may replace the named volume with a bind mount such as `./data:/app/data` in Compose for your own deployment workflow.

## Troubleshooting Native Libraries

This image includes the shared libraries commonly needed by the verified runtime stack:

- `libgl1`
- `libglib2.0-0`
- `libsm6`
- `libxext6`
- `libxrender1`
- `libxcb1`

If OpenCV or PyMuPDF startup logs mention missing `libGL` or `libxcb`, rebuild the image without cache:

```powershell
docker compose build --no-cache
docker compose up
```

If you see errors like `ImportError: libGL.so.1` or `ImportError: libxcb.so.1`, confirm you are running the image built from this repository version and not an older cached image.

## Design Scope

This v0.9.5 Docker milestone intentionally does not include:

- PostgreSQL-first deployment
- MariaDB auth-first deployment
- multi-container database deployment
- Redis
- Celery
- external workers

Those can be added later as separate deployment profiles. This milestone is specifically the low-friction SQLite-first runtime that matches the verified non-Docker operational behavior.
