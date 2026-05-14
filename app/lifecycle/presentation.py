from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.db.models import Document, DocumentLifecycleEvent
from app.lifecycle.consistency import LifecycleConsistencyResult, SEVERITY_ERROR, SEVERITY_PASS, SEVERITY_WARNING
from app.lifecycle.events import (
    EVENT_DOCUMENT_CLEANED,
    EVENT_DOCUMENT_DUPLICATE_REUSED,
    EVENT_DOCUMENT_EXPORTED,
    EVENT_DOCUMENT_EXTRACTION_COMPLETED,
    EVENT_DOCUMENT_FAILED,
    EVENT_DOCUMENT_PROCESSING_STARTED,
    EVENT_DOCUMENT_QUEUED,
    EVENT_DOCUMENT_RETAINED,
    EVENT_DOCUMENT_RESOLUTION_COMPLETED,
    EVENT_DOCUMENT_RETRY_COMPLETED,
    EVENT_DOCUMENT_RETRY_REQUESTED,
    EVENT_DOCUMENT_RETRY_STARTED,
    EVENT_DOCUMENT_UPLOADED,
    EVENT_DOCUMENT_VALIDATED,
)
from app.lifecycle.taxonomy import event_family_for


EVENT_LABEL_KEYS = {
    EVENT_DOCUMENT_UPLOADED: "lifecycle_event_uploaded",
    EVENT_DOCUMENT_QUEUED: "lifecycle_event_queued",
    EVENT_DOCUMENT_PROCESSING_STARTED: "lifecycle_event_processing_started",
    EVENT_DOCUMENT_VALIDATED: "lifecycle_event_validated",
    EVENT_DOCUMENT_EXTRACTION_COMPLETED: "lifecycle_event_extraction_completed",
    EVENT_DOCUMENT_RESOLUTION_COMPLETED: "lifecycle_event_resolution_completed",
    EVENT_DOCUMENT_FAILED: "lifecycle_event_failed",
    EVENT_DOCUMENT_RETAINED: "lifecycle_event_retained",
    EVENT_DOCUMENT_CLEANED: "lifecycle_event_cleaned",
    EVENT_DOCUMENT_RETRY_REQUESTED: "lifecycle_event_retry_requested",
    EVENT_DOCUMENT_RETRY_STARTED: "lifecycle_event_retry_started",
    EVENT_DOCUMENT_RETRY_COMPLETED: "lifecycle_event_retry_completed",
    EVENT_DOCUMENT_DUPLICATE_REUSED: "lifecycle_event_duplicate_reused",
    EVENT_DOCUMENT_EXPORTED: "lifecycle_event_exported",
}

EVENT_DEFAULT_LABELS = {
    EVENT_DOCUMENT_UPLOADED: "Uploaded",
    EVENT_DOCUMENT_QUEUED: "Queued",
    EVENT_DOCUMENT_PROCESSING_STARTED: "Processing started",
    EVENT_DOCUMENT_VALIDATED: "Validated",
    EVENT_DOCUMENT_EXTRACTION_COMPLETED: "Extraction completed",
    EVENT_DOCUMENT_RESOLUTION_COMPLETED: "Resolution completed",
    EVENT_DOCUMENT_FAILED: "Failed",
    EVENT_DOCUMENT_RETAINED: "Source retained",
    EVENT_DOCUMENT_CLEANED: "Source cleaned",
    EVENT_DOCUMENT_RETRY_REQUESTED: "Retry requested",
    EVENT_DOCUMENT_RETRY_STARTED: "Retry started",
    EVENT_DOCUMENT_RETRY_COMPLETED: "Retry completed",
    EVENT_DOCUMENT_DUPLICATE_REUSED: "Duplicate reused",
    EVENT_DOCUMENT_EXPORTED: "Exported",
}


@dataclass(frozen=True)
class LifecycleEventPresentation:
    label_key: str
    label: str
    narrative_key: str
    narrative: str
    family: str
    severity: str
    metadata_summary: str | None


@dataclass(frozen=True)
class LifecycleEventView:
    id: int
    event_type: str
    occurred_at: str
    from_state: str | None
    to_state: str | None
    actor_source: str
    correlation_id: str | None
    operation_id: str | None
    batch_run_id: int | None
    metadata: dict[str, Any]
    error_type: str | None
    error_detail: str | None
    presentation: LifecycleEventPresentation

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["presentation"] = asdict(self.presentation)
        return data


@dataclass(frozen=True)
class LifecycleEventGroupView:
    correlation_id: str
    title_key: str
    title: str
    items: list[LifecycleEventView]

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "title_key": self.title_key,
            "title": self.title,
            "items": [item.to_dict() for item in self.items],
        }


def _severity_for_event(event: DocumentLifecycleEvent) -> str:
    if event.event_type == EVENT_DOCUMENT_FAILED:
        return SEVERITY_ERROR
    if event.event_type == EVENT_DOCUMENT_CLEANED:
        return SEVERITY_WARNING
    if event.event_type in {EVENT_DOCUMENT_RETRY_REQUESTED, EVENT_DOCUMENT_RETRY_STARTED}:
        return SEVERITY_WARNING
    return SEVERITY_PASS


def _metadata_summary(event: DocumentLifecycleEvent) -> str | None:
    metadata = event.metadata_json or {}
    if event.event_type == EVENT_DOCUMENT_EXTRACTION_COMPLETED:
        page_count = metadata.get("page_count")
        reference_count = metadata.get("reference_count")
        if page_count is not None and reference_count is not None:
            return f"{page_count} pages, {reference_count} references"
    if event.event_type == EVENT_DOCUMENT_RESOLUTION_COMPLETED:
        reference_count = metadata.get("reference_count")
        if reference_count is not None:
            return f"{reference_count} references resolved"
    if event.event_type == EVENT_DOCUMENT_FAILED:
        if event.error_type:
            return event.error_type
        return metadata.get("step")
    if event.event_type == EVENT_DOCUMENT_RETRY_COMPLETED:
        success = metadata.get("success")
        if success is True:
            return "Retry completed successfully"
        if success is False:
            return "Retry completed with failure"
    if event.event_type in {EVENT_DOCUMENT_RETAINED, EVENT_DOCUMENT_CLEANED}:
        return metadata.get("reason") or metadata.get("cleanup_type")
    return None


def _narrative_for_event(event: DocumentLifecycleEvent) -> tuple[str, str]:
    metadata = event.metadata_json or {}
    if event.event_type == EVENT_DOCUMENT_FAILED:
        step = metadata.get("step")
        if step == "pdf_validation":
            return "lifecycle_narrative_failed_validation", "PDF validation failed"
        if step == "document_processing":
            return "lifecycle_narrative_failed_processing", "Document processing failed"
        return "lifecycle_narrative_failed_generic", "Document processing failed"
    if event.event_type == EVENT_DOCUMENT_RETRY_COMPLETED:
        if metadata.get("success") is True:
            return "lifecycle_narrative_retry_completed_success", "Retry completed successfully"
        if metadata.get("success") is False:
            return "lifecycle_narrative_retry_completed_failure", "Retry completed with failure"
    if event.event_type == EVENT_DOCUMENT_RETAINED:
        return "lifecycle_narrative_retained", "Source retained for recovery"
    if event.event_type == EVENT_DOCUMENT_CLEANED:
        return "lifecycle_narrative_cleaned", "Source cleaned after retention policy"
    return "lifecycle_narrative_default", EVENT_DEFAULT_LABELS.get(event.event_type, event.event_type)


def build_event_presentation(event: DocumentLifecycleEvent) -> LifecycleEventPresentation:
    label = EVENT_DEFAULT_LABELS.get(event.event_type, event.event_type)
    label_key = EVENT_LABEL_KEYS.get(event.event_type, "lifecycle_event_unknown")
    narrative_key, narrative = _narrative_for_event(event)
    return LifecycleEventPresentation(
        label_key=label_key,
        label=label,
        narrative_key=narrative_key,
        narrative=narrative,
        family=event_family_for(event.event_type),
        severity=_severity_for_event(event),
        metadata_summary=_metadata_summary(event),
    )


def build_timeline_views(events: list[DocumentLifecycleEvent]) -> list[LifecycleEventView]:
    return [
        LifecycleEventView(
            id=event.id,
            event_type=event.event_type,
            occurred_at=event.occurred_at.isoformat(),
            from_state=event.from_state,
            to_state=event.to_state,
            actor_source=event.actor_source,
            correlation_id=event.correlation_id,
            operation_id=event.operation_id,
            batch_run_id=event.batch_run_id,
            metadata=event.metadata_json or {},
            error_type=event.error_type,
            error_detail=event.error_detail,
            presentation=build_event_presentation(event),
        )
        for event in events
    ]


def build_timeline_groups(items: list[LifecycleEventView]) -> list[LifecycleEventGroupView]:
    if not items:
        return []

    groups: list[LifecycleEventGroupView] = []
    current_correlation = items[0].correlation_id or f"timeline-{items[0].id}"
    current_items: list[LifecycleEventView] = []

    def append_group(correlation_id: str, grouped_items: list[LifecycleEventView]) -> None:
        is_retry_chain = any(item.presentation.family == "retry" for item in grouped_items)
        title_key = "lifecycle_group_retry_chain" if is_retry_chain else "lifecycle_group_processing_chain"
        title = "Retry chain" if is_retry_chain else "Processing chain"
        groups.append(
            LifecycleEventGroupView(
                correlation_id=correlation_id,
                title_key=title_key,
                title=title,
                items=list(grouped_items),
            )
        )

    for item in items:
        item_correlation = item.correlation_id or f"timeline-{item.id}"
        if current_items and item_correlation != current_correlation:
            append_group(current_correlation, current_items)
            current_items = []
            current_correlation = item_correlation
        current_items.append(item)

    if current_items:
        append_group(current_correlation, current_items)
    return groups


def build_document_lifecycle_payload(
    document: Document,
    *,
    events: list[DocumentLifecycleEvent],
    consistency: LifecycleConsistencyResult,
) -> dict[str, Any]:
    timeline = build_timeline_views(events)
    groups = build_timeline_groups(timeline)
    return {
        "document_id": document.id,
        "filename": document.original_file_name,
        "current_state": document.lifecycle_state,
        "consistency": consistency.to_dict(),
        "events": [item.to_dict() for item in timeline],
        "timeline": [item.to_dict() for item in timeline],
        "groups": [group.to_dict() for group in groups],
    }
