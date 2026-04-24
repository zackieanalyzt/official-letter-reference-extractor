from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentReference


DEFAULT_PAGE_SIZE = 20


@dataclass(frozen=True)
class ResultsReferenceRow:
    document_id: int
    filename: str
    page_number: int
    reference_class: str
    source_type: str
    raw_reference: str
    final_url: str | None
    resolution_status: str
    created_at: datetime | None


def _normalize_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_reference_statement(
    *,
    search: str | None,
    status: str | None,
    source_type: str | None,
) -> Select:
    statement = (
        select(
            DocumentReference.id.label("reference_id"),
            DocumentReference.document_id,
            Document.original_file_name.label("filename"),
            DocumentReference.page_number,
            DocumentReference.reference_class,
            DocumentReference.source_type,
            DocumentReference.raw_reference,
            DocumentReference.final_url,
            DocumentReference.resolution_status,
            Document.processed_at.label("created_at"),
        )
        .select_from(DocumentReference)
        .join(Document, DocumentReference.document_id == Document.id)
    )

    normalized_status = _normalize_filter(status)
    if normalized_status:
        statement = statement.where(DocumentReference.resolution_status == normalized_status)

    normalized_source_type = _normalize_filter(source_type)
    if normalized_source_type:
        statement = statement.where(DocumentReference.source_type == normalized_source_type)

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
    limit: int,
    offset: int,
) -> dict:
    base_statement = _build_reference_statement(
        search=search,
        status=status,
        source_type=source_type,
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
):
    statement = _build_reference_statement(
        search=search,
        status=status,
        source_type=source_type,
    ).order_by(Document.original_file_name.asc(), DocumentReference.page_number.asc(), DocumentReference.id.asc())

    return session.execute(statement.execution_options(yield_per=200))


def get_reference_summary(
    session: Session,
    *,
    search: str | None,
    status: str | None,
    source_type: str | None,
) -> dict:
    base_statement = _build_reference_statement(
        search=search,
        status=status,
        source_type=source_type,
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
