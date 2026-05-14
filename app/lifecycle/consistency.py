from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentLifecycleEvent
from app.lifecycle.events import (
    EVENT_DOCUMENT_CLEANED,
    EVENT_DOCUMENT_RETRY_COMPLETED,
    EVENT_DOCUMENT_RETRY_REQUESTED,
    EVENT_DOCUMENT_RETRY_STARTED,
)
from app.lifecycle.validation import LifecycleTransitionError, validate_transition
from app.storage import get_storage_service


SEVERITY_PASS = "PASS"
SEVERITY_WARNING = "WARNING"
SEVERITY_ERROR = "ERROR"
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_ORDER = {
    SEVERITY_PASS: 0,
    SEVERITY_WARNING: 1,
    SEVERITY_ERROR: 2,
    SEVERITY_CRITICAL: 3,
}


@dataclass(frozen=True)
class LifecycleConsistencyCheck:
    code: str
    severity: str
    passed: bool
    summary: str
    details: str | None = None


@dataclass(frozen=True)
class LifecycleConsistencyResult:
    document_id: int
    status: str
    summary: str
    current_projection_state: str | None
    expected_projection_state: str | None
    last_stateful_event_id: int | None
    last_stateful_event_type: str | None
    event_count: int
    has_retry_chain: bool
    checks: list[LifecycleConsistencyCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status": self.status,
            "summary": self.summary,
            "current_projection_state": self.current_projection_state,
            "expected_projection_state": self.expected_projection_state,
            "last_stateful_event_id": self.last_stateful_event_id,
            "last_stateful_event_type": self.last_stateful_event_type,
            "event_count": self.event_count,
            "has_retry_chain": self.has_retry_chain,
            "checks": [asdict(check) for check in self.checks],
        }


def _max_severity(checks: list[LifecycleConsistencyCheck]) -> str:
    if not checks:
        return SEVERITY_PASS
    return max(checks, key=lambda check: SEVERITY_ORDER[check.severity]).severity


def _summary_for(status: str, checks: list[LifecycleConsistencyCheck]) -> str:
    if status == SEVERITY_PASS:
        return "Projection matches lifecycle history"
    first_failure = next((check for check in checks if not check.passed), None)
    if first_failure is not None:
        return first_failure.summary
    return "Lifecycle consistency requires operational review"


def _check_projection(document: Document, timeline: list[DocumentLifecycleEvent]) -> LifecycleConsistencyCheck:
    stateful_events = [event for event in timeline if event.to_state is not None]
    last_stateful_event = stateful_events[-1] if stateful_events else None
    expected_state = last_stateful_event.to_state if last_stateful_event is not None else document.lifecycle_state
    passed = document.lifecycle_state == expected_state
    return LifecycleConsistencyCheck(
        code="projection_matches_last_stateful_event",
        severity=SEVERITY_PASS if passed else SEVERITY_ERROR,
        passed=passed,
        summary="Projection matches lifecycle history" if passed else "Current lifecycle state does not match the last stateful event",
        details=None if passed else f"current={document.lifecycle_state} expected={expected_state}",
    )


def _check_transitions(timeline: list[DocumentLifecycleEvent]) -> list[LifecycleConsistencyCheck]:
    checks: list[LifecycleConsistencyCheck] = []
    for event in timeline:
        if event.to_state is None:
            continue
        try:
            validate_transition(event.from_state, event.to_state, event.event_type)
        except LifecycleTransitionError as exc:
            checks.append(
                LifecycleConsistencyCheck(
                    code="invalid_transition_history",
                    severity=SEVERITY_CRITICAL,
                    passed=False,
                    summary="Lifecycle history contains an invalid transition",
                    details=f"event_id={event.id} {exc}",
                )
            )
            break
    if not checks:
        checks.append(
            LifecycleConsistencyCheck(
                code="transition_history_valid",
                severity=SEVERITY_PASS,
                passed=True,
                summary="Lifecycle transition history is valid",
            )
        )
    return checks


def _check_retry_chain(timeline: list[DocumentLifecycleEvent]) -> list[LifecycleConsistencyCheck]:
    retry_events = [
        event
        for event in timeline
        if event.event_type in {EVENT_DOCUMENT_RETRY_REQUESTED, EVENT_DOCUMENT_RETRY_STARTED, EVENT_DOCUMENT_RETRY_COMPLETED}
    ]
    if not retry_events:
        return [
            LifecycleConsistencyCheck(
                code="retry_chain_not_present",
                severity=SEVERITY_PASS,
                passed=True,
                summary="No retry chain recorded",
            )
        ]

    checks: list[LifecycleConsistencyCheck] = []
    by_correlation: dict[str, list[DocumentLifecycleEvent]] = {}
    for event in retry_events:
        correlation_id = event.correlation_id or "missing"
        by_correlation.setdefault(correlation_id, []).append(event)

    for correlation_id, events in by_correlation.items():
        event_types = [event.event_type for event in events]
        if correlation_id == "missing":
            checks.append(
                LifecycleConsistencyCheck(
                    code="retry_chain_missing_correlation_id",
                    severity=SEVERITY_ERROR,
                    passed=False,
                    summary="Retry chain is missing correlation_id",
                    details=f"events={event_types}",
                )
            )
            continue

        if EVENT_DOCUMENT_RETRY_STARTED in event_types and EVENT_DOCUMENT_RETRY_REQUESTED not in event_types:
            checks.append(
                LifecycleConsistencyCheck(
                    code="retry_started_without_request",
                    severity=SEVERITY_ERROR,
                    passed=False,
                    summary="Retry started without a matching retry request",
                    details=f"correlation_id={correlation_id}",
                )
            )
        if EVENT_DOCUMENT_RETRY_COMPLETED in event_types and EVENT_DOCUMENT_RETRY_STARTED not in event_types:
            checks.append(
                LifecycleConsistencyCheck(
                    code="retry_completed_without_start",
                    severity=SEVERITY_ERROR,
                    passed=False,
                    summary="Retry completed without a matching retry start",
                    details=f"correlation_id={correlation_id}",
                )
            )

    if not checks:
        checks.append(
            LifecycleConsistencyCheck(
                code="retry_chain_valid",
                severity=SEVERITY_PASS,
                passed=True,
                summary="Retry chain is internally consistent",
            )
        )
    return checks


def _check_retention_and_cleanup(
    document: Document, timeline: list[DocumentLifecycleEvent], settings=None
) -> list[LifecycleConsistencyCheck]:
    checks: list[LifecycleConsistencyCheck] = []
    if document.lifecycle_state == "retained":
        if not document.source_file_present:
            checks.append(
                LifecycleConsistencyCheck(
                    code="retained_without_source",
                    severity=SEVERITY_ERROR,
                    passed=False,
                    summary="Document is marked retained but no source file is recorded as present",
                    details=f"document_id={document.id}",
                )
            )
        elif settings is not None and document.storage_key:
            storage = get_storage_service(settings)
            if not storage.has_document(document.storage_key):
                checks.append(
                    LifecycleConsistencyCheck(
                        code="retained_storage_missing",
                        severity=SEVERITY_CRITICAL,
                        passed=False,
                        summary="Document is marked retained but the retained source file is missing",
                        details=f"storage_key={document.storage_key}",
                    )
                )
    if document.lifecycle_state == "cleaned":
        if document.source_file_present:
            checks.append(
                LifecycleConsistencyCheck(
                    code="cleaned_with_source_present",
                    severity=SEVERITY_CRITICAL,
                    passed=False,
                    summary="Document is marked cleaned but source file is still marked present",
                    details=f"document_id={document.id}",
                )
            )
        has_clean_event = any(event.event_type == EVENT_DOCUMENT_CLEANED for event in timeline)
        if not has_clean_event:
            checks.append(
                LifecycleConsistencyCheck(
                    code="cleaned_without_lifecycle_event",
                    severity=SEVERITY_WARNING,
                    passed=False,
                    summary="Document is marked cleaned but no cleanup lifecycle event was recorded",
                    details=f"document_id={document.id}",
                )
            )
    if not checks:
        checks.append(
            LifecycleConsistencyCheck(
                code="retention_cleanup_consistent",
                severity=SEVERITY_PASS,
                passed=True,
                summary="Retention and cleanup lifecycle signals are consistent",
            )
        )
    return checks


def _check_missing_history(document: Document, timeline: list[DocumentLifecycleEvent]) -> LifecycleConsistencyCheck:
    if timeline:
        return LifecycleConsistencyCheck(
            code="history_present",
            severity=SEVERITY_PASS,
            passed=True,
            summary="Lifecycle history is present",
        )
    return LifecycleConsistencyCheck(
        code="history_missing",
        severity=SEVERITY_WARNING,
        passed=False,
        summary="Document has no lifecycle history yet",
        details=f"current_state={document.lifecycle_state}",
    )


def _get_document_timeline(session: Session, document_id: int) -> list[DocumentLifecycleEvent]:
    statement = (
        select(DocumentLifecycleEvent)
        .where(DocumentLifecycleEvent.document_id == document_id)
        .order_by(DocumentLifecycleEvent.occurred_at.asc(), DocumentLifecycleEvent.id.asc())
    )
    return session.execute(statement).scalars().all()


def validate_document_consistency(
    session: Session, document_id: int, *, settings=None
) -> LifecycleConsistencyResult | None:
    document = session.get(Document, document_id)
    if document is None:
        return None

    timeline = _get_document_timeline(session, document_id)
    stateful_events = [event for event in timeline if event.to_state is not None]
    last_stateful_event = stateful_events[-1] if stateful_events else None
    expected_state = last_stateful_event.to_state if last_stateful_event is not None else document.lifecycle_state

    checks: list[LifecycleConsistencyCheck] = []
    checks.append(_check_missing_history(document, timeline))
    checks.append(_check_projection(document, timeline))
    checks.extend(_check_transitions(timeline))
    checks.extend(_check_retry_chain(timeline))
    checks.extend(_check_retention_and_cleanup(document, timeline, settings=settings))

    status = _max_severity(checks)
    return LifecycleConsistencyResult(
        document_id=document_id,
        status=status,
        summary=_summary_for(status, checks),
        current_projection_state=document.lifecycle_state,
        expected_projection_state=expected_state,
        last_stateful_event_id=last_stateful_event.id if last_stateful_event is not None else None,
        last_stateful_event_type=last_stateful_event.event_type if last_stateful_event is not None else None,
        event_count=len(timeline),
        has_retry_chain=any(event.correlation_id and "retry:" in event.correlation_id for event in timeline),
        checks=checks,
    )
