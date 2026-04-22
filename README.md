# Official Letter Reference Extractor (OLRE)

Internal LAN web application for scanning official-letter PDFs, extracting references, and presenting normalized results.

Current status: bootstrap project with FastAPI, Jinja2 templates, SQLAlchemy wiring, Alembic setup, and auth/session skeleton.

## Run Migrations

Set the PostgreSQL environment variables first:

```powershell
$env:POSTGRES_HOST="192.168.100.170"
$env:POSTGRES_PORT="5432"
$env:POSTGRES_DB="olre_db"
$env:POSTGRES_USER="your_user"
$env:POSTGRES_PASSWORD="your_password"
```

Then run:

```powershell
alembic upgrade head
```
