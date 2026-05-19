from __future__ import annotations

from typing import Any

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
    EVENT_TRAVERSAL_CANDIDATE_DETECTED,
    EVENT_TRAVERSAL_DEPTH_LIMIT_REACHED,
    EVENT_TRAVERSAL_SKIPPED,
)
from app.lifecycle.taxonomy import require_known_event_type


ALLOWED_METADATA_KEYS: dict[str, set[str]] = {
    EVENT_DOCUMENT_UPLOADED: {"uploaded_file_name", "triggered_by"},
    EVENT_DOCUMENT_QUEUED: {"uploaded_file_name", "triggered_by", "force_reprocess"},
    EVENT_DOCUMENT_PROCESSING_STARTED: {"triggered_by", "force_reprocess"},
    EVENT_DOCUMENT_VALIDATED: {"uploaded_file_name"},
    EVENT_DOCUMENT_EXTRACTION_COMPLETED: {"page_count", "reference_count"},
    EVENT_DOCUMENT_RESOLUTION_COMPLETED: {"reference_count", "used_cached_result"},
    EVENT_DOCUMENT_FAILED: {"step", "reason"},
    EVENT_DOCUMENT_RETAINED: {"reason", "retention_mode", "storage_backend", "storage_key_present"},
    EVENT_DOCUMENT_CLEANED: {"cleanup_type", "reason", "cleanup_trigger", "storage_key_present_before"},
    EVENT_DOCUMENT_RETRY_REQUESTED: {"mode"},
    EVENT_DOCUMENT_RETRY_STARTED: {"triggered_by", "force_reprocess"},
    EVENT_DOCUMENT_RETRY_COMPLETED: {"triggered_by", "force_reprocess", "success"},
    EVENT_DOCUMENT_DUPLICATE_REUSED: {"uploaded_file_name"},
    EVENT_DOCUMENT_EXPORTED: {"export_type"},
    EVENT_TRAVERSAL_CANDIDATE_DETECTED: {
        "traversal_id",
        "parent_document_id",
        "source_reference_id",
        "traversal_depth",
        "traversal_status",
        "target_type",
        "policy_decision",
        "policy_reason",
    },
    EVENT_TRAVERSAL_SKIPPED: {
        "traversal_id",
        "parent_document_id",
        "source_reference_id",
        "traversal_depth",
        "traversal_status",
        "target_type",
        "policy_decision",
        "policy_reason",
    },
    EVENT_TRAVERSAL_DEPTH_LIMIT_REACHED: {
        "traversal_id",
        "parent_document_id",
        "source_reference_id",
        "traversal_depth",
        "traversal_status",
        "target_type",
        "policy_decision",
        "policy_reason",
    },
}


def normalize_event_metadata(event_type: str, metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    require_known_event_type(event_type)
    if not metadata:
        return None

    allowed_keys = ALLOWED_METADATA_KEYS.get(event_type, set())
    normalized = {key: metadata[key] for key in allowed_keys if key in metadata}
    return normalized or None
