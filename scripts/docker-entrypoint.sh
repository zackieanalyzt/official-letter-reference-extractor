#!/bin/sh
set -eu

python -m app.runtime validate
python -m alembic upgrade head

exec python -m uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-8000}"
