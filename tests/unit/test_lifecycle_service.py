from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Document
from app.lifecycle import (
    ACTOR_BATCH_PROCESSOR,
    EVENT_DOCUMENT_EXTRACTION_COMPLETED,
    EVENT_DOCUMENT_PROCESSING_STARTED,
    EVENT_DOCUMENT_QUEUED,
    EVENT_DOCUMENT_VALIDATED,
    STATE_EXTRACTED,
    STATE_PROCESSING,
    STATE_QUEUED,
    STATE_UPLOADED,
    STATE_VALIDATED,
    get_document_timeline,
    record_non_state_event,
    transition_document_state,
    validate_document_lifecycle_consistency,
)


def test_transition_document_state_appends_history_and_updates_projection():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        from sqlalchemy.orm import Session

        session = Session(bind=connection)
        document = Document(
            original_file_name="sample.pdf",
            content_hash="hash-1",
            file_size_bytes=100,
            processing_status="pending",
            lifecycle_state=STATE_UPLOADED,
        )
        session.add(document)
        session.flush()

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
            event_type=EVENT_DOCUMENT_VALIDATED,
            to_state=STATE_VALIDATED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )
        record_non_state_event(
            session,
            document=document,
            event_type="DOCUMENT_RETRY_REQUESTED",
            actor_source="retry_service",
            correlation_id="retry:test-chain",
        )
        transition_document_state(
            session,
            document=document,
            event_type=EVENT_DOCUMENT_EXTRACTION_COMPLETED,
            to_state=STATE_EXTRACTED,
            actor_source=ACTOR_BATCH_PROCESSOR,
        )

        timeline = get_document_timeline(session, document.id)
        consistency = validate_document_lifecycle_consistency(session, document.id)

        assert [event.event_type for event in timeline] == [
            EVENT_DOCUMENT_QUEUED,
            EVENT_DOCUMENT_PROCESSING_STARTED,
            EVENT_DOCUMENT_VALIDATED,
            "DOCUMENT_RETRY_REQUESTED",
            EVENT_DOCUMENT_EXTRACTION_COMPLETED,
        ]
        assert document.lifecycle_state == STATE_EXTRACTED
        assert consistency["ok"] is True
