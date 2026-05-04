# OLRE v0.9.4 Release Notes

Tag:

```text
v0.9.4-sqlite-runtime-option
```

Commit:

```text
60ef66f feat: add SQLite runtime database option
```

## Summary

v0.9.4 adds SQLite as a real runtime database option while keeping PostgreSQL support. The goal is easier local installation and simpler future public/container distribution.

## What Changed

- Added `DATABASE_URL` as the database source of truth.
- Added SQLite runtime support:

```env
DATABASE_URL=sqlite:///data/olre.sqlite3
```

- Kept PostgreSQL runtime support:

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
```

- Added central database engine/session wiring.
- Added SQLite PRAGMAs:
  - `journal_mode=WAL`
  - `foreign_keys=ON`
  - `busy_timeout=5000`
- Updated Alembic migration compatibility for SQLite.
- Added `/healthz` database backend reporting:

```json
{
  "status": "ok",
  "database_backend": "sqlite"
}
```

## Verified Behavior

- SQLite migration reaches `20260503_0007 (head)`.
- App starts with SQLite.
- Upload and batch process write to `data/olre.sqlite3`.
- `/results` displays SQLite-backed documents.
- CSV, Markdown, and Excel exports work.
- Dashboard and quality pages work.
- QR debug artifacts work.
- PostgreSQL compatibility remains available.

## Important Operational Note

If `DATABASE_URL` is set to SQLite, OLRE should not attempt PostgreSQL connection. Use `/healthz` to confirm the active backend.

## Known Limits

SQLite is best for small/simple deployments. Use PostgreSQL for heavier concurrent writes or centralized production operations.
