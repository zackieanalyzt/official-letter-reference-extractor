from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models import BatchRun, Document, DocumentReference


@dataclass(frozen=True)
class DomainSummaryRow:
    domain: str
    total_references: int
    resolved_count: int
    failed_count: int
    success_rate: float
    text_count: int
    qr_count: int
    ocr_count: int


def normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if not candidate.lower().startswith(("http://", "https://")):
        return None

    parsed = urlparse(candidate)
    domain = (parsed.netloc or "").lower().strip()
    if "@" in domain:
        domain = domain.rsplit("@", 1)[-1]
    if domain.startswith("www."):
        domain = domain[4:]
    return domain.rstrip("/") or None


def _percent(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def get_dashboard_summary(session: Session) -> dict:
    document_totals = session.execute(
        select(
            func.count(Document.id).label("total_documents"),
            func.sum(case((Document.processing_status == "processed", 1), else_=0)).label(
                "processed_documents"
            ),
            func.sum(case((Document.processing_status == "failed", 1), else_=0)).label(
                "failed_documents"
            ),
        )
    ).one()
    reference_totals = session.execute(
        select(
            func.count(DocumentReference.id).label("total_references"),
            func.sum(case((DocumentReference.resolution_status == "resolved", 1), else_=0)).label(
                "resolved_urls"
            ),
            func.sum(case((DocumentReference.resolution_status == "failed", 1), else_=0)).label(
                "failed_urls"
            ),
            func.sum(case((DocumentReference.source_type == "qr", 1), else_=0)).label("qr_count"),
            func.sum(case((DocumentReference.source_type == "text", 1), else_=0)).label("text_count"),
            func.sum(case((DocumentReference.source_type == "ocr", 1), else_=0)).label("ocr_count"),
        )
    ).one()
    duplicate_documents = session.execute(
        select(func.coalesce(func.sum(BatchRun.duplicate_files_skipped), 0))
    ).scalar_one()

    total_documents = document_totals.total_documents or 0
    total_references = reference_totals.total_references or 0
    resolved_urls = reference_totals.resolved_urls or 0
    failed_urls = reference_totals.failed_urls or 0

    qr_documents = session.execute(
        select(func.count(func.distinct(DocumentReference.document_id))).where(
            DocumentReference.source_type == "qr"
        )
    ).scalar_one()
    ocr_documents = session.execute(
        select(func.count(func.distinct(DocumentReference.document_id))).where(
            DocumentReference.source_type == "ocr"
        )
    ).scalar_one()

    return {
        "total_documents": total_documents,
        "total_references": total_references,
        "processed_documents": document_totals.processed_documents or 0,
        "failed_documents": document_totals.failed_documents or 0,
        "duplicate_documents": duplicate_documents or 0,
        "resolved_urls": resolved_urls,
        "failed_urls": failed_urls,
        "qr_count": reference_totals.qr_count or 0,
        "text_count": reference_totals.text_count or 0,
        "ocr_count": reference_totals.ocr_count or 0,
        "broken_link_rate": _percent(failed_urls, resolved_urls + failed_urls),
        "ocr_usage_rate": _percent(ocr_documents or 0, total_documents),
        "qr_detection_rate": _percent(qr_documents or 0, total_documents),
    }


def get_domain_summary(session: Session, limit: int = 25) -> list[DomainSummaryRow]:
    rows = session.execute(
        select(
            DocumentReference.raw_reference,
            DocumentReference.final_url,
            DocumentReference.resolution_status,
            DocumentReference.source_type,
        )
    ).all()

    summary: dict[str, dict] = {}
    for row in rows:
        domain = normalize_domain(row.final_url) or normalize_domain(row.raw_reference)
        if domain is None:
            continue
        item = summary.setdefault(
            domain,
            {
                "total_references": 0,
                "resolved_count": 0,
                "failed_count": 0,
                "source_counts": Counter(),
            },
        )
        item["total_references"] += 1
        item["source_counts"][row.source_type] += 1
        if row.resolution_status == "resolved":
            item["resolved_count"] += 1
        elif row.resolution_status == "failed":
            item["failed_count"] += 1

    domain_rows = [
        DomainSummaryRow(
            domain=domain,
            total_references=item["total_references"],
            resolved_count=item["resolved_count"],
            failed_count=item["failed_count"],
            success_rate=_percent(item["resolved_count"], item["resolved_count"] + item["failed_count"]),
            text_count=item["source_counts"]["text"],
            qr_count=item["source_counts"]["qr"],
            ocr_count=item["source_counts"]["ocr"],
        )
        for domain, item in summary.items()
    ]
    return sorted(domain_rows, key=lambda item: item.total_references, reverse=True)[:limit]


def get_reference_source_summary(session: Session) -> list[dict]:
    rows = session.execute(
        select(DocumentReference.source_type, func.count(DocumentReference.id))
        .group_by(DocumentReference.source_type)
        .order_by(func.count(DocumentReference.id).desc())
    ).all()
    return [{"source_type": row[0], "count": row[1]} for row in rows]


def get_error_summary(session: Session, limit: int = 10) -> dict:
    processing_errors = session.execute(
        select(
            Document.processing_error_type,
            func.count(Document.id).label("count"),
        )
        .where(Document.processing_error_type.is_not(None))
        .group_by(Document.processing_error_type)
        .order_by(func.count(Document.id).desc())
        .limit(limit)
    ).all()
    resolution_errors = session.execute(
        select(
            DocumentReference.resolution_error_type,
            func.count(DocumentReference.id).label("count"),
        )
        .where(DocumentReference.resolution_error_type.is_not(None))
        .group_by(DocumentReference.resolution_error_type)
        .order_by(func.count(DocumentReference.id).desc())
        .limit(limit)
    ).all()
    recent_failed_documents = session.execute(
        select(
            Document.id,
            Document.original_file_name,
            Document.processing_error_type,
            Document.processing_error_detail,
            Document.processed_at,
        )
        .where(Document.processing_status == "failed")
        .order_by(Document.processed_at.desc(), Document.id.desc())
        .limit(limit)
    ).all()
    recent_failed_references = session.execute(
        select(
            DocumentReference.id,
            DocumentReference.document_id,
            DocumentReference.raw_reference,
            DocumentReference.final_url,
            DocumentReference.resolution_error_type,
            DocumentReference.resolution_error_detail,
        )
        .where(DocumentReference.resolution_status == "failed")
        .order_by(DocumentReference.id.desc())
        .limit(limit)
    ).all()

    return {
        "processing_errors": [
            {"error_type": row.processing_error_type, "count": row.count} for row in processing_errors
        ],
        "resolution_errors": [
            {"error_type": row.resolution_error_type, "count": row.count} for row in resolution_errors
        ],
        "recent_failed_documents": [
            {
                "document_id": row.id,
                "filename": row.original_file_name,
                "error_type": row.processing_error_type,
                "error_detail": row.processing_error_detail,
                "processed_at": row.processed_at,
            }
            for row in recent_failed_documents
        ],
        "recent_failed_references": [
            {
                "reference_id": row.id,
                "document_id": row.document_id,
                "raw_reference": row.raw_reference,
                "final_url": row.final_url,
                "error_type": row.resolution_error_type,
                "error_detail": row.resolution_error_detail,
            }
            for row in recent_failed_references
        ],
    }


def get_daily_document_trend(session: Session, limit: int = 30) -> list[dict]:
    document_rows = session.execute(
        select(
            Document.id,
            Document.processing_status,
            Document.processed_at,
        ).where(Document.processed_at.is_not(None))
    ).all()
    reference_rows = session.execute(
        select(
            Document.processed_at,
            DocumentReference.resolution_status,
        )
        .select_from(DocumentReference)
        .join(Document, DocumentReference.document_id == Document.id)
        .where(Document.processed_at.is_not(None))
    ).all()

    trend: dict[date, dict] = defaultdict(
        lambda: {
            "documents": 0,
            "references": 0,
            "failed_documents": 0,
            "resolved_urls": 0,
        }
    )
    for row in document_rows:
        day = row.processed_at.date()
        trend[day]["documents"] += 1
        if row.processing_status == "failed":
            trend[day]["failed_documents"] += 1
    for row in reference_rows:
        day = row.processed_at.date()
        trend[day]["references"] += 1
        if row.resolution_status == "resolved":
            trend[day]["resolved_urls"] += 1

    return [
        {"date": day.isoformat(), **values}
        for day, values in sorted(trend.items(), key=lambda item: item[0], reverse=True)[:limit]
    ]


def get_quality_report(session: Session) -> dict:
    references_per_document = (
        select(
            DocumentReference.document_id.label("document_id"),
            func.count(DocumentReference.id).label("reference_count"),
        )
        .group_by(DocumentReference.document_id)
        .subquery()
    )
    zero_reference_documents = session.execute(
        select(Document.id, Document.original_file_name, Document.processing_status)
        .outerjoin(references_per_document, references_per_document.c.document_id == Document.id)
        .where(func.coalesce(references_per_document.c.reference_count, 0) == 0)
        .order_by(Document.id.desc())
        .limit(20)
    ).all()
    image_only_documents = session.execute(
        select(Document.id, Document.original_file_name, Document.processing_error_type)
        .where(Document.processing_error_type == "NO_REFERENCE_FOUND")
        .order_by(Document.id.desc())
        .limit(20)
    ).all()
    ocr_failed_documents = session.execute(
        select(Document.id, Document.original_file_name, Document.processing_error_type)
        .where(Document.processing_error_type.like("OCR%"))
        .order_by(Document.id.desc())
        .limit(20)
    ).all()
    failed_documents = session.execute(
        select(Document.id, Document.original_file_name, Document.processing_error_type)
        .where(Document.processing_status == "failed")
        .order_by(Document.id.desc())
        .limit(20)
    ).all()
    failed_references = session.execute(
        select(DocumentReference.id, DocumentReference.document_id, DocumentReference.raw_reference)
        .where(DocumentReference.resolution_status == "failed")
        .order_by(DocumentReference.id.desc())
        .limit(20)
    ).all()
    duplicate_documents = session.execute(
        select(Document.content_hash, func.count(Document.id).label("count"))
        .group_by(Document.content_hash)
        .having(func.count(Document.id) > 1)
        .order_by(func.count(Document.id).desc())
        .limit(20)
    ).all()
    missing_page_count = session.execute(
        select(Document.id, Document.original_file_name)
        .where(Document.page_count.is_(None))
        .order_by(Document.id.desc())
        .limit(20)
    ).all()
    missing_resolved_url = session.execute(
        select(DocumentReference.id, DocumentReference.document_id, DocumentReference.raw_reference)
        .where(DocumentReference.final_url.is_(None))
        .order_by(DocumentReference.id.desc())
        .limit(20)
    ).all()

    return {
        "zero_reference_documents": zero_reference_documents,
        "image_only_documents": image_only_documents,
        "ocr_failed_documents": ocr_failed_documents,
        "failed_documents": failed_documents,
        "failed_references": failed_references,
        "duplicate_documents": duplicate_documents,
        "missing_page_count": missing_page_count,
        "missing_resolved_url": missing_resolved_url,
    }
