# SQLite Runtime Guide

OLRE v0.9.4 supports SQLite as the default lightweight runtime database. This is the recommended path for local use, small teams, demos, and future public container packaging.

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
DATABASE_URL=sqlite:////app/data/olre.sqlite3
ENABLE_AUTH=false
OCR_ENABLED=false
QR_DEBUG_EXPORT=false
```

`DATABASE_URL` is the source of truth. When it is set to SQLite, OLRE must not attempt a PostgreSQL connection.

## Initialize Database

```powershell
python -m alembic upgrade head
python -m alembic current
```

Expected:

```text
20260503_0007 (head)
```

## Start App

```powershell
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/imports
```

If port 8000 is stuck, use another port:

```powershell
python -m uvicorn app.main:app --reload --port 8021
```

## Confirm Runtime Backend

Open:

```text
http://127.0.0.1:8000/healthz
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
python -c "import sqlite3; con=sqlite3.connect('/app/data/olre.sqlite3'); print(con.execute('select id, original_file_name from documents').fetchall()); con.close()"
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
Remove-Item /app/data/olre.sqlite3,/app/data/olre.sqlite3-wal,/app/data/olre.sqlite3-shm -ErrorAction SilentlyContinue
python -m alembic upgrade head
```

Do not delete the database in real use unless you already have a backup.

## Known Limits

SQLite has a single-writer model. It is reliable for light workloads, but long-running batch jobs and multiple concurrent users can still contend for writes. PostgreSQL remains the recommended backend for heavier production use.
