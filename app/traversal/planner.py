from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Document, DocumentReference, ReferenceTraversal
from app.lifecycle.events import (
    ACTOR_TRAVERSAL_PLANNER,
    EVENT_TRAVERSAL_CANDIDATE_DETECTED,
    EVENT_TRAVERSAL_DEPTH_LIMIT_REACHED,
    EVENT_TRAVERSAL_SKIPPED,
)
from app.lifecycle.service import record_non_state_event
from app.traversal.classifier import classify_reference_url
from app.traversal.policy import evaluate_traversal_policy
from app.traversal.schemas import (
    POLICY_ALLOWED,
    STATUS_DEPTH_LIMIT_REACHED,
    TraversalPlanSummary,
    TraversalSummary,
)


def _candidate_url(reference: DocumentReference) -> str:
    return (reference.final_url or reference.raw_reference or "").strip()


def plan_document_traversal(
    session: Session,
    *,
    document_id: int,
    settings: Settings,
    traversal_depth: int = 1,
    emit_lifecycle_events: bool = False,
) -> TraversalPlanSummary | None:
    document = session.get(Document, document_id)
    if document is None:
        return None

    references = session.execute(
        select(DocumentReference)
        .where(DocumentReference.document_id == document_id)
        .order_by(DocumentReference.id.asc())
    ).scalars()

    created = 0
    updated = 0
    unchanged = 0

    for reference in references:
        candidate_url = _candidate_url(reference)
        classification = classify_reference_url(candidate_url)
        policy = evaluate_traversal_policy(
            classification,
            settings=settings,
            traversal_depth=traversal_depth,
        )

        existing = session.execute(
            select(ReferenceTraversal).where(
                ReferenceTraversal.parent_document_id == document_id,
                ReferenceTraversal.source_reference_id == reference.id,
                ReferenceTraversal.raw_url == candidate_url,
            )
        ).scalar_one_or_none()

        values = {
            "resolved_url": classification.candidate_url,
            "traversal_depth": traversal_depth,
            "traversal_status": policy.traversal_status,
            "target_type": classification.target_type,
            "policy_decision": policy.policy_decision,
            "policy_reason": policy.policy_reason,
            "error_type": None if policy.policy_decision == POLICY_ALLOWED else policy.policy_reason,
            "error_detail": None if policy.policy_decision == POLICY_ALLOWED else policy.policy_reason,
        }

        if existing is None:
            traversal = ReferenceTraversal(
                parent_document_id=document_id,
                source_reference_id=reference.id,
                raw_url=candidate_url,
                **values,
            )
            session.add(traversal)
            session.flush()
            created += 1
            if emit_lifecycle_events:
                _record_planning_event(session, document=document, traversal=traversal)
        else:
            changed = False
            for field_name, field_value in values.items():
                if getattr(existing, field_name) != field_value:
                    setattr(existing, field_name, field_value)
                    changed = True
            if changed:
                updated += 1
            else:
                unchanged += 1

    session.flush()
    return TraversalPlanSummary(
        document_id=document_id,
        created=created,
        updated=updated,
        unchanged=unchanged,
        total=created + updated + unchanged,
    )


def _record_planning_event(
    session: Session,
    *,
    document: Document,
    traversal: ReferenceTraversal,
) -> None:
    metadata = {
        "traversal_id": traversal.id,
        "parent_document_id": traversal.parent_document_id,
        "source_reference_id": traversal.source_reference_id,
        "traversal_depth": traversal.traversal_depth,
        "traversal_status": traversal.traversal_status,
        "target_type": traversal.target_type,
        "policy_decision": traversal.policy_decision,
        "policy_reason": traversal.policy_reason,
    }
    if traversal.traversal_status == STATUS_DEPTH_LIMIT_REACHED:
        event_type = EVENT_TRAVERSAL_DEPTH_LIMIT_REACHED
    elif traversal.policy_decision == POLICY_ALLOWED:
        event_type = EVENT_TRAVERSAL_CANDIDATE_DETECTED
    else:
        event_type = EVENT_TRAVERSAL_SKIPPED

    record_non_state_event(
        session,
        document=document,
        event_type=event_type,
        actor_source=ACTOR_TRAVERSAL_PLANNER,
        correlation_id=f"doc:{document.id}",
        operation_id=f"traversal:{traversal.id}",
        metadata=metadata,
        error_type=traversal.error_type,
        error_detail=traversal.error_detail,
    )


def list_document_traversals(session: Session, document_id: int) -> list[dict]:
    rows = session.execute(
        select(ReferenceTraversal, DocumentReference)
        .join(DocumentReference, ReferenceTraversal.source_reference_id == DocumentReference.id)
        .where(ReferenceTraversal.parent_document_id == document_id)
        .order_by(ReferenceTraversal.id.asc())
    ).all()
    return [_traversal_payload(traversal, reference) for traversal, reference in rows]


def build_document_traversal_payload(
    session: Session,
    *,
    document_id: int,
    settings: Settings,
) -> dict | None:
    summary = plan_document_traversal(session, document_id=document_id, settings=settings)
    if summary is None:
        return None
    session.flush()
    return {
        "document_id": document_id,
        "planning_summary": asdict(summary),
        "traversals": list_document_traversals(session, document_id),
    }


def build_ops_traversal_summary(session: Session) -> TraversalSummary:
    total = session.execute(select(func.count(ReferenceTraversal.id))).scalar_one()
    return TraversalSummary(
        total=total,
        by_status=_count_by(session, ReferenceTraversal.traversal_status),
        by_policy_decision=_count_by(session, ReferenceTraversal.policy_decision),
        by_target_type=_count_by(session, ReferenceTraversal.target_type),
    )


def _count_by(session: Session, column) -> dict[str, int]:
    rows = session.execute(select(column, func.count(ReferenceTraversal.id)).group_by(column)).all()
    return {str(key): count for key, count in rows}


def _traversal_payload(
    traversal: ReferenceTraversal,
    reference: DocumentReference,
) -> dict:
    return {
        "id": traversal.id,
        "parent_document_id": traversal.parent_document_id,
        "source_reference_id": traversal.source_reference_id,
        "child_document_id": traversal.child_document_id,
        "raw_url": traversal.raw_url,
        "resolved_url": traversal.resolved_url,
        "traversal_depth": traversal.traversal_depth,
        "traversal_status": traversal.traversal_status,
        "target_type": traversal.target_type,
        "content_type": traversal.content_type,
        "content_length_bytes": traversal.content_length_bytes,
        "policy_decision": traversal.policy_decision,
        "policy_reason": traversal.policy_reason,
        "error_type": traversal.error_type,
        "error_detail": traversal.error_detail,
        "source_type": reference.source_type,
        "reference_class": reference.reference_class,
        "page_number": reference.page_number,
    }

