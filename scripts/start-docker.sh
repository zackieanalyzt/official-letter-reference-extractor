#!/bin/sh
set -eu

mkdir -p \
  "${INPUT_DIR:-/app/data/input}" \
  "${PROCESSED_DIR:-/app/data/processed}" \
  "${ERROR_DIR:-/app/data/error}" \
  "${QR_DEBUG_DIR:-/app/data/debug/qr}" \
  "${RUNTIME_TMP_DIR:-/app/data/runtime/tmp}" \
  "${FAILED_RETAINED_DIR:-/app/data/runtime/failed-retained}"

python - <<'PY'
from sqlalchemy.engine import make_url

from app.config import get_settings
from app.runtime import get_database_storage_path, get_runtime_paths

settings = get_settings()
url = make_url(settings.resolved_database_url)
database_path = get_database_storage_path(settings)

print("OLRE Docker runtime summary")
print(f"  app_env={settings.app_env}")
print(f"  app_lang={settings.app_lang}")
print(f"  enable_auth={settings.enable_auth}")
print(f"  host={settings.app_host}")
print(f"  port={settings.app_port}")
print(f"  database_backend={url.get_backend_name()}")
if database_path is not None:
    print(f"  database_path={database_path}")
else:
    print("  database_path=(non-sqlite or in-memory)")
for name, path in get_runtime_paths(settings).items():
    print(f"  {name}={path}")
print(f"  ocr_enabled={settings.ocr_enabled}")
print(f"  qr_fallback_decoder={settings.qr_fallback_decoder}")
PY

python -m app.runtime validate
python -m alembic upgrade head

exec python -m uvicorn app.main:app --host "${APP_HOST:-0.0.0.0}" --port "${APP_PORT:-7777}"
