from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.batch.destination_classification import SHORT_URL_HOSTS
from app.db.models import Document, DocumentReference, ReferenceTraversalReview


RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_BLOCKED = "BLOCKED"

ACTION_AUTO_ELIGIBLE = "AUTO_ELIGIBLE"
ACTION_REVIEW_REQUIRED = "REVIEW_REQUIRED"
ACTION_BLOCKED = "BLOCKED"
ACTION_UNCERTAIN = "UNCERTAIN"

STATUS_NOT_REQUIRED = "NOT_REQUIRED"
STATUS_PENDING_REVIEW = "PENDING_REVIEW"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_SKIPPED = "SKIPPED"

DECISION_APPROVED = "APPROVED"
DECISION_REJECTED = "REJECTED"
DECISION_SKIPPED = "SKIPPED"
DECISION_NOTED = "NOTED"


@dataclass(frozen=True)
class TraversalEvidenceFlags:
    has_typed_http: bool
    has_qr_http: bool
    has_ocr_http: bool
    has_valid_http_candidate: bool
    has_unsupported_scheme: bool
    has_malformed_url: bool
    has_private_ip: bool
    has_loopback: bool
    has_link_local: bool
    is_shortlink: bool
    is_redirect_like: bool
    has_multi_target_conflict: bool
    has_qr_text_disagreement: bool
    has_uncertain_destination: bool
    has_weak_ocr_or_scan_evidence: bool
    has_no_confident_reference: bool
    has_invalid_pdf_evidence: bool
    has_broken_qr_evidence: bool


@dataclass(frozen=True)
class TraversalReviewSnapshot:
    confidence_score: int
    risk_level: str
    recommended_action: str
    review_status: str
    review_reason: str
    evidence_summary: str
    flags: TraversalEvidenceFlags


@dataclass(frozen=True)
class TraversalQueueRow:
    reference_id: int
    document_id: int
    filename: str
    page_number: int | None
    raw_reference: str | None
    source_type: str | None
    reference_class: str | None
    confidence_score: int | None
    risk_level: str
    recommended_action: str
    review_status: str
    review_reason: str | None
    evidence_summary: str | None
    operator_decision: str | None
    operator_note: str | None
    reviewed_at: datetime | None


def _candidate_value(reference: DocumentReference) -> str | None:
    return (reference.final_url or reference.raw_reference or "").strip() or None


def _normalized_candidate(reference: DocumentReference) -> str | None:
    value = _candidate_value(reference)
    return value.lower() if value else None


def _parsed_url(value: str | None):
    if not value:
        return None
    try:
        return urlparse(value.strip())
    except Exception:
        return None


def _is_http_scheme(value: str | None) -> bool:
    parsed = _parsed_url(value)
    return bool(parsed and parsed.scheme.lower() in {"http", "https"})


def _is_syntactically_valid_http_url(value: str | None) -> bool:
    parsed = _parsed_url(value)
    return bool(parsed and parsed.scheme.lower() in {"http", "https"} and parsed.netloc.strip())


def _normalized_host(value: str | None) -> str | None:
    parsed = _parsed_url(value)
    if not parsed:
        return None
    host = (parsed.hostname or "").strip().lower()
    return host or None


def _host_ip(value: str | None):
    host = _normalized_host(value)
    if not host:
        return None
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


def _is_private_ip(value: str | None) -> bool:
    ip = _host_ip(value)
    return bool(ip and ip.is_private and not ip.is_loopback and not ip.is_link_local)


def _is_loopback(value: str | None) -> bool:
    host = _normalized_host(value)
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    ip = _host_ip(value)
    return bool(ip and ip.is_loopback)


def _is_link_local(value: str | None) -> bool:
    ip = _host_ip(value)
    return bool(ip and ip.is_link_local)


def _has_unsupported_scheme(value: str | None) -> bool:
    parsed = _parsed_url(value)
    if not parsed or not parsed.scheme:
        return False
    return parsed.scheme.lower() not in {"http", "https"}


def _is_malformed_url(value: str | None) -> bool:
    parsed = _parsed_url(value)
    if not parsed:
        return bool(value)
    if parsed.scheme.lower() in {"http", "https"} and not parsed.netloc.strip():
        return True
    return False


def _is_shortlink(value: str | None) -> bool:
    host = _normalized_host(value)
    return bool(host and host in SHORT_URL_HOSTS)


def _is_redirect_like(reference: DocumentReference) -> bool:
    value = _candidate_value(reference)
    if not value:
        return False
    lowered = value.lower()
    if _is_shortlink(value):
        return True
    if reference.destination_type == "redirect":
        return True
    return any(token in lowered for token in ("redirect", "url=", "target=", "return=", "dest="))


def _document_candidate_context(document: Document) -> tuple[set[str], set[str], set[str]]:
    typed_http: set[str] = set()
    qr_http: set[str] = set()
    all_http: set[str] = set()
    for item in document.references:
        candidate = _normalized_candidate(item)
        if not _is_syntactically_valid_http_url(candidate):
            continue
        all_http.add(candidate)
        if item.source_type == "qr":
            qr_http.add(candidate)
        elif item.source_type in {"text", "ocr"}:
            typed_http.add(candidate)
    return typed_http, qr_http, all_http


def build_evidence_flags(reference: DocumentReference, document: Document) -> TraversalEvidenceFlags:
    candidate = _candidate_value(reference)
    typed_http, qr_http, all_http = _document_candidate_context(document)
    valid_http = _is_syntactically_valid_http_url(candidate)
    has_typed_http = reference.source_type == "text" and valid_http
    has_qr_http = reference.source_type == "qr" and valid_http
    has_ocr_http = reference.source_type == "ocr" and valid_http
    has_no_confident_reference = not valid_http
    has_multi_target_conflict = len(all_http) > 1
    has_qr_text_disagreement = bool(qr_http and typed_http and qr_http != typed_http)
    has_weak_ocr_or_scan_evidence = reference.source_type == "ocr" or (
        reference.source_type == "qr" and not valid_http
    )
    has_uncertain_destination = valid_http and reference.destination_type is None
    has_broken_qr_evidence = reference.source_type == "qr" and not valid_http

    return TraversalEvidenceFlags(
        has_typed_http=has_typed_http,
        has_qr_http=has_qr_http,
        has_ocr_http=has_ocr_http,
        has_valid_http_candidate=valid_http,
        has_unsupported_scheme=_has_unsupported_scheme(candidate),
        has_malformed_url=_is_malformed_url(candidate),
        has_private_ip=_is_private_ip(candidate),
        has_loopback=_is_loopback(candidate),
        has_link_local=_is_link_local(candidate),
        is_shortlink=_is_shortlink(candidate),
        is_redirect_like=_is_redirect_like(reference),
        has_multi_target_conflict=has_multi_target_conflict,
        has_qr_text_disagreement=has_qr_text_disagreement,
        has_uncertain_destination=has_uncertain_destination,
        has_weak_ocr_or_scan_evidence=has_weak_ocr_or_scan_evidence,
        has_no_confident_reference=has_no_confident_reference,
        has_invalid_pdf_evidence=document.processing_error_type == "INVALID_PDF",
        has_broken_qr_evidence=has_broken_qr_evidence,
    )


def score_reference_candidate(reference: DocumentReference, document: Document, flags: TraversalEvidenceFlags) -> int:
    score = 0
    candidate = _candidate_value(reference)

    if flags.has_typed_http:
        score += 45
    if flags.has_qr_http:
        score += 35
    if reference.final_url and reference.raw_reference and reference.final_url == reference.raw_reference:
        score += 15
    if reference.destination_type in {"government", "document"}:
        score += 10
    if not flags.has_multi_target_conflict and flags.has_valid_http_candidate:
        score += 5
    if flags.has_ocr_http:
        score -= 15
    if flags.is_shortlink or flags.is_redirect_like:
        score -= 20
    if flags.has_multi_target_conflict:
        score -= 25
    if flags.has_qr_text_disagreement:
        score -= 25
    if flags.has_broken_qr_evidence:
        score -= 30
    if flags.has_unsupported_scheme or flags.has_malformed_url:
        score -= 40
    if flags.has_invalid_pdf_evidence:
        score -= 100
    if flags.has_private_ip or flags.has_loopback or flags.has_link_local:
        score -= 40
    if flags.has_uncertain_destination:
        score -= 10
    if flags.has_no_confident_reference and candidate:
        score += 10

    return max(0, min(100, score))


def assign_risk_level(reference: DocumentReference, score: int, flags: TraversalEvidenceFlags) -> str:
    if (
        flags.has_unsupported_scheme
        or flags.has_malformed_url
        or flags.has_private_ip
        or flags.has_loopback
        or flags.has_link_local
        or flags.has_invalid_pdf_evidence
    ):
        return RISK_BLOCKED
    if (
        flags.is_shortlink
        or flags.is_redirect_like
        or flags.has_multi_target_conflict
        or flags.has_qr_text_disagreement
        or flags.has_uncertain_destination
        or flags.has_broken_qr_evidence
    ):
        return RISK_HIGH
    if score >= 80 and flags.has_valid_http_candidate and reference.source_type in {"text", "qr"}:
        return RISK_LOW
    return RISK_MEDIUM


def assign_recommended_action(reference: DocumentReference, score: int, risk_level: str, flags: TraversalEvidenceFlags) -> str:
    if risk_level == RISK_BLOCKED:
        return ACTION_BLOCKED
    if (
        flags.has_valid_http_candidate
        and reference.source_type in {"text", "qr"}
        and not flags.has_private_ip
        and not flags.has_loopback
        and not flags.has_link_local
        and not flags.has_unsupported_scheme
        and not flags.has_broken_qr_evidence
        and not flags.has_invalid_pdf_evidence
        and not flags.has_multi_target_conflict
        and score >= 80
        and risk_level == RISK_LOW
    ):
        return ACTION_AUTO_ELIGIBLE
    if (
        score >= 50
        or flags.is_shortlink
        or flags.is_redirect_like
        or flags.has_multi_target_conflict
        or flags.has_qr_text_disagreement
        or flags.has_uncertain_destination
        or flags.has_weak_ocr_or_scan_evidence
    ):
        return ACTION_REVIEW_REQUIRED
    return ACTION_UNCERTAIN


def build_review_reason(reference: DocumentReference, risk_level: str, action: str, flags: TraversalEvidenceFlags) -> str:
    if flags.has_invalid_pdf_evidence:
        return "Invalid or corrupted PDF is blocked by policy."
    if flags.has_unsupported_scheme:
        return "Unsupported scheme is blocked by policy."
    if flags.has_private_ip:
        return "Private IP targets are blocked by policy."
    if flags.has_loopback:
        return "Loopback targets are blocked by policy."
    if flags.has_link_local:
        return "Link-local targets are blocked by policy."
    if flags.has_malformed_url:
        return "Malformed URL is blocked by policy."
    if flags.is_shortlink:
        return "Shortlink requires operator review."
    if flags.is_redirect_like:
        return "Redirect-like URL requires operator review."
    if flags.has_multi_target_conflict:
        return "Multiple traversal candidates require operator review."
    if flags.has_qr_text_disagreement:
        return "QR and typed URL candidates disagree."
    if flags.has_uncertain_destination:
        return "Destination type could not be confirmed safely offline."
    if flags.has_broken_qr_evidence:
        return "QR evidence is incomplete or not decoded confidently."
    if action == ACTION_AUTO_ELIGIBLE and risk_level == RISK_LOW:
        return "Deterministic low-risk traversal candidate."
    if action == ACTION_UNCERTAIN:
        return "Offline-safe analysis could not classify confidently."
    if reference.source_type == "ocr":
        return "OCR-derived candidate requires operator review."
    return "Candidate requires operator review."


def build_evidence_summary(reference: DocumentReference, document: Document, flags: TraversalEvidenceFlags) -> str:
    candidate = _candidate_value(reference)
    if flags.has_invalid_pdf_evidence:
        return "Document failed PDF validation before safe traversal planning."
    if flags.has_multi_target_conflict:
        return f"Multiple candidate references were detected in {document.original_file_name}."
    if flags.has_qr_text_disagreement:
        return "Typed URL and QR candidates disagree within the same document."
    if flags.has_broken_qr_evidence:
        return f"QR-derived value on page {reference.page_number} did not produce a confident http/https candidate."
    if candidate and flags.has_valid_http_candidate:
        return (
            f"Page {reference.page_number} {reference.source_type} candidate: {candidate}"
        )
    if candidate:
        return f"Page {reference.page_number} candidate: {candidate}"
    return f"Page {reference.page_number} has incomplete traversal evidence."


def build_review_snapshot(reference: DocumentReference, document: Document) -> TraversalReviewSnapshot:
    flags = build_evidence_flags(reference, document)
    score = score_reference_candidate(reference, document, flags)
    risk_level = assign_risk_level(reference, score, flags)
    action = assign_recommended_action(reference, score, risk_level, flags)
    review_status = STATUS_NOT_REQUIRED if action in {ACTION_AUTO_ELIGIBLE, ACTION_BLOCKED} else STATUS_PENDING_REVIEW
    reason = build_review_reason(reference, risk_level, action, flags)
    evidence = build_evidence_summary(reference, document, flags)
    return TraversalReviewSnapshot(
        confidence_score=score,
        risk_level=risk_level,
        recommended_action=action,
        review_status=review_status,
        review_reason=reason,
        evidence_summary=evidence,
        flags=flags,
    )


def _create_review_event(
    session: Session,
    *,
    reference_id: int,
    review_status: str,
    operator_decision: str | None,
    operator_note: str | None,
    event_type: str,
    event_detail: str | None,
    acted_by: str | None,
    reviewed_at: datetime | None = None,
) -> ReferenceTraversalReview:
    review = ReferenceTraversalReview(
        traversal_id=reference_id,
        review_status=review_status,
        operator_decision=operator_decision,
        operator_note=operator_note,
        reviewed_at=reviewed_at,
        acted_by=acted_by,
        event_type=event_type,
        event_detail=event_detail,
    )
    session.add(review)
    session.flush()
    return review


def evaluate_reference_traversal_review(session: Session, reference_id: int) -> TraversalReviewSnapshot:
    reference = session.get(DocumentReference, reference_id)
    if reference is None or reference.document is None:
        raise ValueError(f"DocumentReference not found: {reference_id}")

    snapshot = build_review_snapshot(reference, reference.document)
    reference.confidence_score = snapshot.confidence_score
    reference.risk_level = snapshot.risk_level
    reference.recommended_action = snapshot.recommended_action
    reference.review_status = snapshot.review_status
    reference.review_reason = snapshot.review_reason
    reference.evidence_summary = snapshot.evidence_summary
    if snapshot.review_status == STATUS_NOT_REQUIRED:
        reference.operator_decision = None
        reference.reviewed_at = None
    _create_review_event(
        session,
        reference_id=reference.id,
        review_status=reference.review_status,
        operator_decision=None,
        operator_note=None,
        event_type="TRAVERSAL_CONFIDENCE_EVALUATED",
        event_detail=f"score={snapshot.confidence_score} risk={snapshot.risk_level} action={snapshot.recommended_action}",
        acted_by="system",
    )
    queue_event_type = {
        ACTION_AUTO_ELIGIBLE: "TRAVERSAL_AUTO_ELIGIBLE",
        ACTION_REVIEW_REQUIRED: "TRAVERSAL_REVIEW_REQUIRED",
        ACTION_BLOCKED: "TRAVERSAL_BLOCKED_BY_POLICY",
        ACTION_UNCERTAIN: "TRAVERSAL_MARKED_UNCERTAIN",
    }[snapshot.recommended_action]
    _create_review_event(
        session,
        reference_id=reference.id,
        review_status=reference.review_status,
        operator_decision=None,
        operator_note=None,
        event_type=queue_event_type,
        event_detail=snapshot.review_reason,
        acted_by="system",
    )
    session.flush()
    return snapshot


def evaluate_document_traversal_reviews(session: Session, document_id: int) -> list[TraversalReviewSnapshot]:
    statement: Select[tuple[DocumentReference]] = select(DocumentReference).where(
        DocumentReference.document_id == document_id
    )
    references = session.execute(statement).scalars().all()
    return [evaluate_reference_traversal_review(session, reference.id) for reference in references]


def apply_operator_review_action(
    session: Session,
    *,
    reference_id: int,
    action: str,
    operator_note: str | None,
    acted_by: str | None,
) -> DocumentReference:
    reference = session.get(DocumentReference, reference_id)
    if reference is None:
        raise ValueError(f"DocumentReference not found: {reference_id}")

    now = datetime.now(UTC)
    normalized_note = (operator_note or "").strip() or None

    if action == DECISION_APPROVED:
        reference.review_status = STATUS_APPROVED
        reference.operator_decision = DECISION_APPROVED
        reference.reviewed_at = now
        if normalized_note:
            reference.operator_note = normalized_note
        event_type = "TRAVERSAL_OPERATOR_APPROVED"
    elif action == DECISION_REJECTED:
        reference.review_status = STATUS_REJECTED
        reference.operator_decision = DECISION_REJECTED
        reference.recommended_action = ACTION_BLOCKED
        reference.risk_level = RISK_BLOCKED
        reference.reviewed_at = now
        if normalized_note:
            reference.operator_note = normalized_note
        event_type = "TRAVERSAL_OPERATOR_REJECTED"
    elif action == DECISION_SKIPPED:
        reference.review_status = STATUS_SKIPPED
        reference.operator_decision = DECISION_SKIPPED
        reference.reviewed_at = now
        if normalized_note:
            reference.operator_note = normalized_note
        event_type = "TRAVERSAL_OPERATOR_SKIPPED"
    elif action == DECISION_NOTED:
        if normalized_note:
            reference.operator_note = normalized_note
        reference.reviewed_at = now
        event_type = "TRAVERSAL_OPERATOR_NOTED"
    else:
        raise ValueError(f"Unsupported operator action: {action}")

    _create_review_event(
        session,
        reference_id=reference.id,
        review_status=reference.review_status,
        operator_decision=reference.operator_decision,
        operator_note=normalized_note,
        event_type=event_type,
        event_detail=normalized_note,
        acted_by=acted_by,
        reviewed_at=reference.reviewed_at,
    )
    session.flush()
    return reference


def list_traversal_queue(
    session: Session,
    *,
    recommended_action: str | None = None,
    review_status: str | None = None,
) -> dict:
    statement = (
        select(
            DocumentReference.id.label("reference_id"),
            DocumentReference.document_id,
            Document.original_file_name.label("filename"),
            DocumentReference.page_number,
            DocumentReference.raw_reference,
            DocumentReference.source_type,
            DocumentReference.reference_class,
            DocumentReference.confidence_score,
            DocumentReference.risk_level,
            DocumentReference.recommended_action,
            DocumentReference.review_status,
            DocumentReference.review_reason,
            DocumentReference.evidence_summary,
            DocumentReference.operator_decision,
            DocumentReference.operator_note,
            DocumentReference.reviewed_at,
        )
        .select_from(DocumentReference)
        .join(Document, DocumentReference.document_id == Document.id)
    )
    if recommended_action:
        statement = statement.where(DocumentReference.recommended_action == recommended_action)
    if review_status:
        statement = statement.where(DocumentReference.review_status == review_status)
    rows = session.execute(
        statement.order_by(
            DocumentReference.recommended_action.asc(),
            DocumentReference.confidence_score.desc(),
            DocumentReference.id.desc(),
        )
    ).all()

    queue_rows = [
        TraversalQueueRow(
            reference_id=row.reference_id,
            document_id=row.document_id,
            filename=row.filename,
            page_number=row.page_number,
            raw_reference=row.raw_reference,
            source_type=row.source_type,
            reference_class=row.reference_class,
            confidence_score=row.confidence_score,
            risk_level=row.risk_level,
            recommended_action=row.recommended_action,
            review_status=row.review_status,
            review_reason=row.review_reason,
            evidence_summary=row.evidence_summary,
            operator_decision=row.operator_decision,
            operator_note=row.operator_note,
            reviewed_at=row.reviewed_at,
        )
        for row in rows
    ]
    grouped = {
        ACTION_AUTO_ELIGIBLE: [row for row in queue_rows if row.recommended_action == ACTION_AUTO_ELIGIBLE],
        ACTION_REVIEW_REQUIRED: [row for row in queue_rows if row.recommended_action == ACTION_REVIEW_REQUIRED],
        ACTION_BLOCKED: [row for row in queue_rows if row.recommended_action == ACTION_BLOCKED],
        ACTION_UNCERTAIN: [row for row in queue_rows if row.recommended_action == ACTION_UNCERTAIN],
    }
    reason_rows = session.execute(
        select(DocumentReference.review_reason, func.count(DocumentReference.id))
        .where(DocumentReference.review_reason.is_not(None))
        .group_by(DocumentReference.review_reason)
        .order_by(func.count(DocumentReference.id).desc(), DocumentReference.review_reason.asc())
    ).all()
    blocked_reason_rows = session.execute(
        select(DocumentReference.review_reason, func.count(DocumentReference.id))
        .where(DocumentReference.recommended_action == ACTION_BLOCKED, DocumentReference.review_reason.is_not(None))
        .group_by(DocumentReference.review_reason)
        .order_by(func.count(DocumentReference.id).desc(), DocumentReference.review_reason.asc())
    ).all()
    distribution_rows = session.execute(
        select(DocumentReference.confidence_score, func.count(DocumentReference.id))
        .group_by(DocumentReference.confidence_score)
        .order_by(DocumentReference.confidence_score.asc())
    ).all()
    counts = {
        "total_candidates": len(queue_rows),
        "auto_eligible_count": len(grouped[ACTION_AUTO_ELIGIBLE]),
        "review_required_count": len(grouped[ACTION_REVIEW_REQUIRED]),
        "blocked_count": len(grouped[ACTION_BLOCKED]),
        "uncertain_count": len(grouped[ACTION_UNCERTAIN]),
        "approved_count": sum(1 for row in queue_rows if row.review_status == STATUS_APPROVED),
        "rejected_count": sum(1 for row in queue_rows if row.review_status == STATUS_REJECTED),
        "skipped_count": sum(1 for row in queue_rows if row.review_status == STATUS_SKIPPED),
    }
    counts["estimated_manual_review_reduction"] = round(
        (counts["auto_eligible_count"] / counts["total_candidates"]) * 100, 2
    ) if counts["total_candidates"] else 0.0
    return {
        "rows": queue_rows,
        "grouped": grouped,
        "counts": counts,
        "top_review_reasons": [
            {"reason": row[0], "count": row[1]}
            for row in reason_rows
        ],
        "top_blocked_reasons": [
            {"reason": row[0], "count": row[1]}
            for row in blocked_reason_rows
        ],
        "confidence_distribution": [
            {"score": row[0], "count": row[1]}
            for row in distribution_rows
        ],
    }
