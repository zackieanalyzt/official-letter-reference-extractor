from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentReference


DEFAULT_PAGE_SIZE = 20


@dataclass(frozen=True)
class ResultsReferenceRow:
    document_id: int
    filename: str
    page_number: int | None
    reference_class: str | None
    source_type: str | None
    raw_reference: str | None
    final_url: str | None
    resolution_status: str | None
    processing_status: str
    processing_error_type: str | None
    resolution_error_type: str | None
    retryable: bool
    created_at: datetime | None


def _normalize_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_date_bound(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    normalized = _normalize_filter(value)
    if not normalized:
        return None
    parsed_date = datetime.fromisoformat(normalized).date()
    return datetime.combine(parsed_date, time.max if end_of_day else time.min)


def _build_reference_statement(
    *,
    search: str | None,
    status: str | None,
    source_type: str | None,
    filename: str | None = None,
    processing_status: str | None = None,
    processing_error_type: str | None = None,
    resolution_error_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    domain: str | None = None,
    include_unreferenced_documents: bool = False,
) -> Select:
    statement = (
        select(
            DocumentReference.id.label("reference_id"),
            Document.id.label("document_id"),
            Document.original_file_name.label("filename"),
            DocumentReference.page_number,
            DocumentReference.reference_class,
            DocumentReference.source_type,
            DocumentReference.raw_reference,
            DocumentReference.final_url,
            DocumentReference.resolution_status,
            Document.processing_status,
            Document.processing_error_type,
            DocumentReference.resolution_error_type,
            Document.processed_at.label("created_at"),
        )
        .select_from(Document)
    )
    if include_unreferenced_documents:
        statement = statement.outerjoin(DocumentReference, DocumentReference.document_id == Document.id)
    else:
        statement = statement.join(DocumentReference, DocumentReference.document_id == Document.id)

    normalized_status = _normalize_filter(status)
    if normalized_status:
        statement = statement.where(DocumentReference.resolution_status == normalized_status)

    normalized_source_type = _normalize_filter(source_type)
    if normalized_source_type:
        statement = statement.where(DocumentReference.source_type == normalized_source_type)

    normalized_filename = _normalize_filter(filename)
    if normalized_filename:
        statement = statement.where(func.lower(Document.original_file_name).like(f"%{normalized_filename.lower()}%"))

    normalized_processing_status = _normalize_filter(processing_status)
    if normalized_processing_status:
        statement = statement.where(Document.processing_status == normalized_processing_status)

    normalized_processing_error_type = _normalize_filter(processing_error_type)
    if normalized_processing_error_type:
        statement = statement.where(Document.processing_error_type == normalized_processing_error_type)

    normalized_resolution_error_type = _normalize_filter(resolution_error_type)
    if normalized_resolution_error_type:
        statement = statement.where(DocumentReference.resolution_error_type == normalized_resolution_error_type)

    parsed_date_from = _parse_date_bound(date_from)
    if parsed_date_from:
        statement = statement.where(Document.processed_at >= parsed_date_from)

    parsed_date_to = _parse_date_bound(date_to, end_of_day=True)
    if parsed_date_to:
        statement = statement.where(Document.processed_at <= parsed_date_to)

    normalized_domain = _normalize_filter(domain)
    if normalized_domain:
        domain_pattern = f"%{normalized_domain.lower()}%"
        statement = statement.where(
            or_(
                func.lower(DocumentReference.raw_reference).like(domain_pattern),
                func.lower(func.coalesce(DocumentReference.final_url, "")).like(domain_pattern),
            )
        )

    normalized_search = _normalize_filter(search)
    if normalized_search:
        pattern = f"%{normalized_search.lower()}%"
        statement = statement.where(
            or_(
                func.lower(Document.original_file_name).like(pattern),
                func.lower(DocumentReference.raw_reference).like(pattern),
                func.lower(func.coalesce(DocumentReference.final_url, "")).like(pattern),
            )
        )

    return statement


def get_references(
    session: Session,
    *,
    search: str | None,
    status: str | None,
    source_type: str | None,
    filename: str | None = None,
    processing_status: str | None = None,
    processing_error_type: str | None = None,
    resolution_error_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    domain: str | None = None,
    limit: int,
    offset: int,
) -> dict:
    base_statement = _build_reference_statement(
        search=search,
        status=status,
        source_type=source_type,
        filename=filename,
        processing_status=processing_status,
        processing_error_type=processing_error_type,
        resolution_error_type=resolution_error_type,
        date_from=date_from,
        date_to=date_to,
        domain=domain,
        include_unreferenced_documents=True,
    )

    total = session.execute(
        select(func.count()).select_from(base_statement.order_by(None).subquery())
    ).scalar_one()

    rows = session.execute(
        base_statement.order_by(DocumentReference.id.desc()).limit(limit).offset(offset)
    ).all()

    return {
        "rows": [
            ResultsReferenceRow(
                document_id=row.document_id,
                filename=row.filename,
                page_number=row.page_number,
                reference_class=row.reference_class,
                source_type=row.source_type,
                raw_reference=row.raw_reference,
                final_url=row.final_url,
                resolution_status=row.resolution_status,
                processing_status=row.processing_status,
                processing_error_type=row.processing_error_type,
                resolution_error_type=row.resolution_error_type,
                retryable=row.processing_status == "failed",
                created_at=row.created_at,
            )
            for row in rows
        ],
        "total": total,
    }


def iter_references(
    session: Session,
    *,
    search: str | None,
    status: str | None,
    source_type: str | None,
    filename: str | None = None,
    processing_status: str | None = None,
    processing_error_type: str | None = None,
    resolution_error_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    domain: str | None = None,
):
    statement = _build_reference_statement(
        search=search,
        status=status,
        source_type=source_type,
        filename=filename,
        processing_status=processing_status,
        processing_error_type=processing_error_type,
        resolution_error_type=resolution_error_type,
        date_from=date_from,
        date_to=date_to,
        domain=domain,
    ).order_by(Document.original_file_name.asc(), DocumentReference.page_number.asc(), DocumentReference.id.asc())

    return session.execute(statement.execution_options(yield_per=200))


def get_reference_summary(
    session: Session,
    *,
    search: str | None,
    status: str | None,
    source_type: str | None,
    filename: str | None = None,
    processing_status: str | None = None,
    processing_error_type: str | None = None,
    resolution_error_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    domain: str | None = None,
) -> dict:
    base_statement = _build_reference_statement(
        search=search,
        status=status,
        source_type=source_type,
        filename=filename,
        processing_status=processing_status,
        processing_error_type=processing_error_type,
        resolution_error_type=resolution_error_type,
        date_from=date_from,
        date_to=date_to,
        domain=domain,
    ).subquery()

    totals = session.execute(
        select(
            func.count().label("total_references"),
            func.count(func.distinct(base_statement.c.document_id)).label("total_documents"),
            func.sum(
                case(
                    (base_statement.c.resolution_status == "resolved", 1),
                    else_=0,
                )
            ).label("resolved"),
            func.sum(
                case(
                    (base_statement.c.resolution_status == "failed", 1),
                    else_=0,
                )
            ).label("failed"),
        ).select_from(base_statement)
    ).one()

    return {
        "total_documents": totals.total_documents or 0,
        "total_references": totals.total_references or 0,
        "resolved": totals.resolved or 0,
        "failed": totals.failed or 0,
    }
