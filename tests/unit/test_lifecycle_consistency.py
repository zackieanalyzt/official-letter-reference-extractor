from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Document
from app.lifecycle import (
    ACTOR_BATCH_PROCESSOR,
    EVENT_DOCUMENT_FAILED,
    EVENT_DOCUMENT_PROCESSING_STARTED,
    EVENT_DOCUMENT_QUEUED,
    EVENT_DOCUMENT_RETRY_COMPLETED,
    EVENT_DOCUMENT_UPLOADED,
    STATE_FAILED,
    STATE_PROCESSING,
    STATE_QUEUED,
    STATE_UPLOADED,
    record_lifecycle_event,
    record_non_state_event,
    transition_document_state,
)
from app.lifecycle.consistency import SEVERITY_ERROR, SEVERITY_PASS, validate_document_consistency


def _build_session():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    connection = engine.connect()
    from sqlalchemy.orm import Session

    return Session(bind=connection), connection


def test_lifecycle_consistency_passes_for_valid_projection():
    session, connection = _build_session()
    try:
        document = Document(
            original_file_name="sample.pdf",
            content_hash="hash-pass",
            file_size_bytes=10,
            processing_status="pending",
            lifecycle_state=STATE_UPLOADED,
        )
        session.add(document)
        session.flush()
        record_lifecycle_event(
            session,
            document_id=document.id,
            event_type=EVENT_DOCUMENT_UPLOADED,
            from_state=None,
            to_state=STATE_UPLOADED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_QUEUED,
            to_state=STATE_QUEUED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_PROCESSING_STARTED,
            to_state=STATE_PROCESSING,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )

        result = validate_document_consistency(session, document.id)

        assert result is not None
        assert result.status == SEVERITY_PASS
    finally:
        connection.close()


def test_lifecycle_consistency_detects_projection_mismatch():
    session, connection = _build_session()
    try:
        document = Document(
            original_file_name="sample.pdf",
            content_hash="hash-mismatch",
            file_size_bytes=10,
            processing_status="failed",
            lifecycle_state=STATE_UPLOADED,
        )
        session.add(document)
        session.flush()
        record_lifecycle_event(
            session,
            document_id=document.id,
            event_type=EVENT_DOCUMENT_UPLOADED,
            from_state=None,
            to_state=STATE_UPLOADED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_QUEUED,
            to_state=STATE_QUEUED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_PROCESSING_STARTED,
            to_state=STATE_PROCESSING,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_FAILED,
            to_state=STATE_FAILED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        document.lifecycle_state = STATE_PROCESSING
        session.flush()

        result = validate_document_consistency(session, document.id)

        assert result is not None
        assert result.status == SEVERITY_ERROR
        assert any(check.code == "projection_matches_last_stateful_event" and not check.passed for check in result.checks)
    finally:
        connection.close()


def test_lifecycle_consistency_detects_retry_chain_gap():
    session, connection = _build_session()
    try:
        document = Document(
            original_file_name="sample.pdf",
            content_hash="hash-retry-gap",
            file_size_bytes=10,
            processing_status="failed",
            lifecycle_state=STATE_FAILED,
        )
        session.add(document)
        session.flush()
        record_lifecycle_event(
            session,
            document_id=document.id,
            event_type=EVENT_DOCUMENT_UPLOADED,
            from_state=None,
            to_state=STATE_UPLOADED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        record_lifecycle_event(
            session,
            document_id=document.id,
            event_type=EVENT_DOCUMENT_FAILED,
            from_state=STATE_PROCESSING,
            to_state=STATE_FAILED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        record_non_state_event(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_RETRY_COMPLETED,
            actor_source="retry_service",
            correlation_id="retry:123",
            metadata={"success": False},
        )

        result = validate_document_consistency(session, document.id)

        assert result is not None
        assert any(check.code == "retry_completed_without_start" and not check.passed for check in result.checks)
    finally:
        connection.close()
