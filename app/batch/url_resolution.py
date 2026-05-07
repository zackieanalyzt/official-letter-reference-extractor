from __future__ import annotations

import inspect

import httpx
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.batch.error_types import URL_HTTP_ERROR, URL_RESOLUTION_FAIL, URL_TIMEOUT
from app.db.models import DocumentReference
from app.logging_config import get_logger


logger = get_logger(__name__)


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


def resolve_url(raw_url: str, *, settings) -> dict:
    if not is_http_url(raw_url):
        return {
            "raw_url": raw_url,
            "final_url": None,
            "status": "failed",
            "http_status_code": None,
            "error": "Invalid URL",
            "error_type": URL_RESOLUTION_FAIL,
            "attempts": 0,
        }

    last_error: str | None = None
    last_error_type = URL_RESOLUTION_FAIL

    for attempt in range(1, settings.url_resolve_max_attempts + 1):
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=settings.url_resolve_timeout_seconds,
                headers={"User-Agent": settings.url_resolve_user_agent},
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
                    "error_type": URL_HTTP_ERROR,
                    "attempts": attempt,
                }

            return {
                "raw_url": raw_url,
                "final_url": final_url,
                "status": "resolved",
                "http_status_code": response.status_code,
                "error": None,
                "error_type": None,
                "attempts": attempt,
            }
        except httpx.TimeoutException as exc:
            last_error = str(exc)
            last_error_type = URL_TIMEOUT
        except Exception as exc:
            last_error = str(exc)
            last_error_type = URL_RESOLUTION_FAIL

    return {
        "raw_url": raw_url,
        "final_url": None,
        "status": "failed",
        "http_status_code": None,
        "error": last_error,
        "error_type": last_error_type,
        "attempts": settings.url_resolve_max_attempts,
    }


def infer_resolution_error_type(*, http_status_code: int | None, error: str | None) -> str | None:
    if http_status_code is not None and 400 <= http_status_code <= 599:
        return URL_HTTP_ERROR
    if error:
        normalized = error.lower()
        if "timed out" in normalized or "timeout" in normalized:
            return URL_TIMEOUT
        return URL_RESOLUTION_FAIL
    return None


def _resolve_references(session: Session, references: list[DocumentReference], *, document_id: int | None, settings) -> dict:
    statement_scope = f"document_id={document_id}" if document_id is not None else "document_id=all"
    summary = {
        "seen": len(references),
        "resolved": 0,
        "failed": 0,
        "skipped": 0,
    }

    logger.info("[URL_RESOLVE_START] %s refs=%s", statement_scope, len(references))

    for reference in references:
        if not is_http_url(reference.raw_reference):
            summary["skipped"] += 1
            logger.info("[URL_RESOLVE_SKIP] reference_id=%s reason=not_http_url", reference.id)
            continue

        resolve_signature = inspect.signature(resolve_url)
        if "settings" in resolve_signature.parameters:
            result = resolve_url(reference.raw_reference, settings=settings)
        else:
            result = resolve_url(reference.raw_reference)
        for attempt in range(1, result["attempts"] + 1):
            logger.info(
                "[URL_RESOLVE_ATTEMPT] reference_id=%s attempt=%s raw_url=%s",
                reference.id,
                attempt,
                reference.raw_reference,
            )
        error_type = result.get("error_type")
        if error_type is None:
            error_type = infer_resolution_error_type(
                http_status_code=result.get("http_status_code"),
                error=result.get("error"),
            )

        reference.final_url = result["final_url"]
        reference.resolution_status = result["status"]
        reference.http_status = result.get("http_status_code")
        reference.resolution_error_type = error_type
        reference.resolution_error_detail = result.get("error")

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
                "[URL_RESOLVE_FAIL] reference_id=%s error_type=%s error=%s attempts=%s",
                reference.id,
                error_type,
                result.get("error"),
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


def resolve_pending_references(session: Session, *, settings) -> dict:
    statement: Select[tuple[DocumentReference]] = select(DocumentReference).where(
        DocumentReference.resolution_status == "pending",
    )
    references = session.execute(statement).scalars().all()
    return _resolve_references(session, references, document_id=None, settings=settings)


def resolve_document_references(session: Session, document_id: int, *, settings) -> dict:
    statement: Select[tuple[DocumentReference]] = select(DocumentReference).where(
        DocumentReference.document_id == document_id,
        DocumentReference.resolution_status == "pending",
    )
    references = session.execute(statement).scalars().all()
    return _resolve_references(session, references, document_id=document_id, settings=settings)


def re_resolve_document_references(session: Session, document_id: int, *, settings) -> dict:
    statement: Select[tuple[DocumentReference]] = select(DocumentReference).where(
        DocumentReference.document_id == document_id,
    )
    references = session.execute(statement).scalars().all()
    for reference in references:
        if is_http_url(reference.raw_reference):
            reference.resolution_status = "pending"
            reference.final_url = None
            reference.http_status = None
            reference.resolution_error_type = None
            reference.resolution_error_detail = None
    session.flush()
    http_references = [reference for reference in references if is_http_url(reference.raw_reference)]
    return _resolve_references(session, http_references, document_id=document_id, settings=settings)
