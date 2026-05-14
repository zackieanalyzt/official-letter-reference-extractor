# SQLite Runtime Guide

OLRE v0.9.7 keeps SQLite as the default lightweight runtime database and now pairs it with explicit runtime profiles plus storage boundary integration. This remains the recommended path for local use, small teams, demos, and simple operational deployments.

## When to Use SQLite

Use SQLite when:

- You want the simplest setup.
- OLRE runs on one machine or one container.
- Write concurrency is low.
- Backup can be file-based.
- You do not want to manage PostgreSQL.

Use PostgreSQL when:

- Many users will process documents at the same time.
- You need centralized database administration.
- You already run managed PostgreSQL.
- You expect heavier concurrent writes.

## Configuration

In `.env`:

```env
APP_ENV=development
DATABASE_URL=sqlite:///data/olre.sqlite3
ENABLE_AUTH=false
OCR_ENABLED=false
QR_DEBUG_EXPORT=false
```

`DATABASE_URL` is the source of truth. When it is set to SQLite, OLRE must not attempt a PostgreSQL connection.

Docker/runtime profile note:

```env
APP_ENV=docker
DATABASE_URL=sqlite:////app/data/olre.sqlite3
```

## Initialize Database

```powershell
python -m alembic upgrade head
python -m alembic current
```

Expected current head:

```text
head
```

## Start App

```powershell
python -m uvicorn app.main:app --reload --port 7777
```

Open:

```text
http://127.0.0.1:7777/imports
```

If port 8000 is stuck, use another port:

```powershell
python -m uvicorn app.main:app --reload --port 8021
```

## Confirm Runtime Backend

Open:

```text
http://127.0.0.1:7777/healthz
```

Expected:

```json
{
  "status": "ok",
  "database_backend": "sqlite"
}
```

## Confirm Data Is in SQLite

```powershell
python -c "import sqlite3; con=sqlite3.connect('data/olre.sqlite3'); print(con.execute('select id, original_file_name from documents').fetchall()); con.close()"
```

After upload and batch processing, the new document should appear in this query.

## Runtime PRAGMAs

OLRE enables:

```text
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

This improves integrity and small-team usability while keeping SQLite simple.

## Reset SQLite During Testing

Stop the server first, then remove:

```powershell
Remove-Item data/olre.sqlite3,data/olre.sqlite3-wal,data/olre.sqlite3-shm -ErrorAction SilentlyContinue
python -m alembic upgrade head
```

Do not delete the database in real use unless you already have a backup.

## Storage Boundary Reminder

As of `v0.9.7-storage-integration`, SQLite runtime operations coexist with a centralized storage boundary:

- raw filesystem execution should live in `app/storage/*` or approved low-level adapters
- business/service/web layers should request artifact operations rather than manipulating filesystem paths directly

This guide describes runtime usage, not a return to path-centric business logic.

## Latest Verification

Latest verification commands:

```bash
APP_ENV=testing uv run pytest
APP_ENV=development uv run ruff check app tests migrations
```

Latest results:

- `79 passed`
- `All checks passed`

## Known Limits

SQLite has a single-writer model. It is reliable for light workloads, but long-running batch jobs and multiple concurrent users can still contend for writes. PostgreSQL remains the recommended backend for heavier production use.
