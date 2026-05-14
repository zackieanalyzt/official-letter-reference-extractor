from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentLifecycleEvent
from app.lifecycle.consistency import validate_document_consistency
from app.lifecycle.metadata import normalize_event_metadata
from app.lifecycle.projection import apply_lifecycle_projection
from app.lifecycle.taxonomy import require_known_event_type
from app.lifecycle.validation import validate_transition


def record_lifecycle_event(
    session: Session,
    *,
    document_id: int,
    event_type: str,
    from_state: str | None,
    to_state: str | None,
    actor_source: str,
    correlation_id: str | None = None,
    operation_id: str | None = None,
    batch_run_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    error_type: str | None = None,
    error_detail: str | None = None,
    occurred_at: datetime | None = None,
) -> DocumentLifecycleEvent:
    require_known_event_type(event_type)
    event = DocumentLifecycleEvent(
        document_id=document_id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        occurred_at=occurred_at or datetime.now(UTC),
        actor_source=actor_source,
        correlation_id=correlation_id,
        operation_id=operation_id,
        batch_run_id=batch_run_id,
        metadata_json=normalize_event_metadata(event_type, metadata),
        error_type=error_type,
        error_detail=error_detail,
    )
    session.add(event)
    session.flush()
    return event


def transition_document_state(
    session: Session,
    *,
    document: Document,
    event_type: str,
    to_state: str,
    actor_source: str,
    correlation_id: str | None = None,
    operation_id: str | None = None,
    batch_run_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    error_type: str | None = None,
    error_detail: str | None = None,
    occurred_at: datetime | None = None,
) -> DocumentLifecycleEvent:
    from_state = document.lifecycle_state
    validate_transition(from_state, to_state, event_type)
    event = record_lifecycle_event(
        session,
        document_id=document.id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        actor_source=actor_source,
        correlation_id=correlation_id,
        operation_id=operation_id,
        batch_run_id=batch_run_id,
        metadata=metadata,
        error_type=error_type,
        error_detail=error_detail,
        occurred_at=occurred_at,
    )
    apply_lifecycle_projection(document, to_state)
    session.flush()
    return event


def record_non_state_event(
    session: Session,
    *,
    document: Document,
    event_type: str,
    actor_source: str,
    correlation_id: str | None = None,
    operation_id: str | None = None,
    batch_run_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    error_type: str | None = None,
    error_detail: str | None = None,
    occurred_at: datetime | None = None,
) -> DocumentLifecycleEvent:
    return record_lifecycle_event(
        session,
        document_id=document.id,
        event_type=event_type,
        from_state=document.lifecycle_state,
        to_state=None,
        actor_source=actor_source,
        correlation_id=correlation_id,
        operation_id=operation_id,
        batch_run_id=batch_run_id,
        metadata=metadata,
        error_type=error_type,
        error_detail=error_detail,
        occurred_at=occurred_at,
    )


def get_document_timeline(session: Session, document_id: int) -> list[DocumentLifecycleEvent]:
    statement = (
        select(DocumentLifecycleEvent)
        .where(DocumentLifecycleEvent.document_id == document_id)
        .order_by(DocumentLifecycleEvent.occurred_at.asc(), DocumentLifecycleEvent.id.asc())
    )
    return session.execute(statement).scalars().all()


def document_has_lifecycle_history(session: Session, document_id: int) -> bool:
    statement = select(func.count(DocumentLifecycleEvent.id)).where(DocumentLifecycleEvent.document_id == document_id)
    return bool(session.execute(statement).scalar_one())


def validate_document_lifecycle_consistency(session: Session, document_id: int) -> dict[str, Any]:
    result = validate_document_consistency(session, document_id)
    if result is None:
        return {"ok": False, "reason": "document_not_found", "document_id": document_id}

    payload = result.to_dict()
    payload["ok"] = result.status == "PASS"
    payload["current_state"] = result.current_projection_state
    payload["expected_state"] = result.expected_projection_state
    payload["last_event_id"] = result.last_stateful_event_id
    return payload
