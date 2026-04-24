from __future__ import annotations

import httpx
from sqlalchemy import inspect
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.models import DocumentReference
from app.logging_config import get_logger


logger = get_logger(__name__)

USER_AGENT = "OLRE/0.1 URL Resolver"
TIMEOUT_SECONDS = 5.0
MAX_RESOLUTION_ATTEMPTS = 2


def is_http_url(url: str | None) -> bool:
    try:
        if not isinstance(url, str):
            return False

        normalized = url.strip().lower()
        if not normalized:
            return False

        return normalized.startswith("http://") or normalized.startswith("https://")
    except Exception:
        return False


def resolve_url(raw_url: str) -> dict:
    if not is_http_url(raw_url):
        return {
            "raw_url": raw_url,
            "final_url": None,
            "status": "failed",
            "http_status_code": None,
            "error": "Invalid URL",
            "attempts": 0,
        }

    last_error: str | None = None

    for attempt in range(1, MAX_RESOLUTION_ATTEMPTS + 1):
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=TIMEOUT_SECONDS,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = client.get(raw_url)

            final_url = str(response.url) if response.url else None
            if 400 <= response.status_code <= 599:
                return {
                    "raw_url": raw_url,
                    "final_url": final_url,
                    "status": "failed",
                    "http_status_code": response.status_code,
                    "error": f"HTTP status {response.status_code}",
                    "attempts": attempt,
                }

            return {
                "raw_url": raw_url,
                "final_url": final_url,
                "status": "resolved",
                "http_status_code": response.status_code,
                "error": None,
                "attempts": attempt,
            }
        except Exception as exc:
            last_error = str(exc)

    return {
        "raw_url": raw_url,
        "final_url": None,
        "status": "failed",
        "http_status_code": None,
        "error": last_error,
        "attempts": MAX_RESOLUTION_ATTEMPTS,
    }


def has_column(session: Session, table_name: str, column_name: str) -> bool:
    bind = session.get_bind()
    if bind is None:
        return False

    inspector = inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(column["name"] == column_name for column in columns)


def _resolve_references(session: Session, references: list[DocumentReference], *, document_id: int | None) -> dict:
    statement_scope = f"document_id={document_id}" if document_id is not None else "document_id=all"
    persist_http_status = has_column(session, DocumentReference.__tablename__, "http_status")

    summary = {
        "seen": len(references),
        "resolved": 0,
        "failed": 0,
        "skipped": 0,
    }

    logger.info("[URL_RESOLVE_START] %s refs=%s", statement_scope, len(references))
    if not persist_http_status:
        logger.info("[URL_RESOLVE_SCHEMA] http_status column not found, skipping persistence")

    for reference in references:
        if not is_http_url(reference.raw_reference):
            summary["skipped"] += 1
            logger.info(
                "[URL_RESOLVE_SKIP] reference_id=%s reason=not_http_url",
                reference.id,
            )
            continue

        result = resolve_url(reference.raw_reference)
        for attempt in range(1, result["attempts"] + 1):
            logger.info(
                "[URL_RESOLVE_ATTEMPT] reference_id=%s attempt=%s raw_url=%s",
                reference.id,
                attempt,
                reference.raw_reference,
            )
        reference.final_url = result["final_url"]
        reference.resolution_status = result["status"]
        if persist_http_status:
            reference.http_status = result["http_status_code"]
        # TODO: add migration to support http_status column

        if result["status"] == "resolved":
            summary["resolved"] += 1
            logger.info(
                "[URL_RESOLVE_DONE] reference_id=%s final_url=%s status=%s http_status=%s attempts=%s",
                reference.id,
                reference.final_url,
                reference.resolution_status,
                result["http_status_code"],
                result["attempts"],
            )
        else:
            summary["failed"] += 1
            logger.warning(
                "[URL_RESOLVE_FAIL] reference_id=%s error=%s attempts=%s",
                reference.id,
                result["error"],
                result["attempts"],
            )

    session.flush()
    logger.info(
        "[URL_RESOLVE_SUMMARY] document_id=%s seen=%s resolved=%s failed=%s skipped=%s",
        document_id,
        summary["seen"],
        summary["resolved"],
        summary["failed"],
        summary["skipped"],
    )
    return summary


def resolve_pending_references(session: Session) -> dict:
    statement: Select[tuple[DocumentReference]] = select(DocumentReference).where(
        DocumentReference.resolution_status == "pending",
    )
    references = session.execute(statement).scalars().all()
    return _resolve_references(session, references, document_id=None)


def resolve_document_references(session: Session, document_id: int) -> dict:
    statement: Select[tuple[DocumentReference]] = select(DocumentReference).where(
        DocumentReference.document_id == document_id,
        DocumentReference.resolution_status == "pending",
    )
    references = session.execute(statement).scalars().all()
    return _resolve_references(session, references, document_id=document_id)
