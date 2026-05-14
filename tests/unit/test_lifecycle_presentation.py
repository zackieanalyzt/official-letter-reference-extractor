from datetime import UTC, datetime

from app.db.models import DocumentLifecycleEvent
from app.lifecycle.events import (
    EVENT_DOCUMENT_FAILED,
    EVENT_DOCUMENT_RETRY_REQUESTED,
    EVENT_DOCUMENT_RETRY_STARTED,
)
from app.lifecycle.presentation import build_event_presentation, build_timeline_groups, build_timeline_views


def test_build_event_presentation_summarizes_failure_step():
    event = DocumentLifecycleEvent(
        id=1,
        document_id=1,
        event_type=EVENT_DOCUMENT_FAILED,
        from_state="processing",
        to_state="failed",
        occurred_at=datetime.now(UTC),
        actor_source="batch_processor",
        correlation_id="document:1:batch:1",
        operation_id="ingestion:1",
        batch_run_id=1,
        metadata_json={"step": "pdf_validation"},
        error_type="INVALID_PDF",
        error_detail="broken file",
    )

    presentation = build_event_presentation(event)

    assert presentation.label == "Failed"
    assert presentation.metadata_summary == "INVALID_PDF"
    assert presentation.narrative == "PDF validation failed"


def test_build_timeline_groups_keeps_retry_chain_together():
    events = [
        DocumentLifecycleEvent(
            id=1,
            document_id=1,
            event_type=EVENT_DOCUMENT_RETRY_REQUESTED,
            from_state="failed",
            to_state=None,
            occurred_at=datetime.now(UTC),
            actor_source="retry_service",
            correlation_id="retry:1",
            operation_id="op-1",
            batch_run_id=1,
            metadata_json={"mode": "retry_failed_document"},
            error_type=None,
            error_detail=None,
        ),
        DocumentLifecycleEvent(
            id=2,
            document_id=1,
            event_type=EVENT_DOCUMENT_RETRY_STARTED,
            from_state="failed",
            to_state=None,
            occurred_at=datetime.now(UTC),
            actor_source="retry_service",
            correlation_id="retry:1",
            operation_id="op-2",
            batch_run_id=2,
            metadata_json={"triggered_by": "retry_extraction"},
            error_type=None,
            error_detail=None,
        ),
    ]

    groups = build_timeline_groups(build_timeline_views(events))

    assert len(groups) == 1
    assert groups[0].title == "Retry chain"
