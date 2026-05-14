from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentLifecycleEvent
from app.ops.schemas import PathAccessSnapshot, RuntimeSnapshot


def _utcnow() -> datetime:
    return datetime.now(UTC)


def redact_database_target(database_url: str) -> str:
    url = make_url(database_url)
    return url.render_as_string(hide_password=True)


def _path_snapshot(name: str, path: Path) -> PathAccessSnapshot:
    exists = path.exists()
    return PathAccessSnapshot(
        name=name,
        path=str(path.resolve()),
        exists=exists,
        readable=exists and os.access(path, os.R_OK),
        writable=exists and os.access(path, os.W_OK),
    )


def build_runtime_snapshot(session: Session, settings, engine: Engine) -> RuntimeSnapshot:
    inspector = inspect(engine)
    lifecycle_table_available = inspector.has_table("document_lifecycle_events")

    document_count = session.execute(select(func.count(Document.id))).scalar_one()
    lifecycle_event_count = 0
    if lifecycle_table_available:
        lifecycle_event_count = session.execute(select(func.count(DocumentLifecycleEvent.id))).scalar_one()

    paths = [
        _path_snapshot("input_dir", settings.input_path),
        _path_snapshot("processed_dir", settings.processed_path),
        _path_snapshot("error_dir", settings.error_path),
        _path_snapshot("qr_debug_dir", settings.qr_debug_path),
        _path_snapshot("runtime_tmp_dir", settings.runtime_tmp_path),
        _path_snapshot("failed_retained_dir", settings.failed_retained_path),
        _path_snapshot("storage_root", settings.storage_root_path),
        _path_snapshot("export_dir", settings.export_path),
        _path_snapshot("backup_dir", settings.backup_path),
    ]

    return RuntimeSnapshot(
        app_env=settings.app_env,
        storage_backend=settings.storage_backend,
        configured_database_backend=make_url(settings.resolved_database_url).get_backend_name(),
        active_database_backend=engine.dialect.name,
        configured_database_target=redact_database_target(settings.resolved_database_url),
        lifecycle_table_available=lifecycle_table_available,
        document_count=document_count,
        lifecycle_event_count=lifecycle_event_count,
        retained_document_count=session.execute(
            select(func.count(Document.id)).where(Document.lifecycle_state == "retained")
        ).scalar_one(),
        cleaned_document_count=session.execute(
            select(func.count(Document.id)).where(Document.lifecycle_state == "cleaned")
        ).scalar_one(),
        failed_document_count=session.execute(
            select(func.count(Document.id)).where(Document.processing_status == "failed")
        ).scalar_one(),
        captured_at=_utcnow(),
        paths=paths,
    )
