from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from app.config import BASE_DIR
from app.db.models import Document
from app.db.session import get_session_factory
from app.lifecycle import get_document_timeline
from app.lifecycle.consistency import validate_document_consistency
from app.lifecycle.presentation import build_document_lifecycle_payload
from app.logging_config import get_logger
from app.i18n import normalize_lang
from app.security import safe_redirect_target
from app.services.batch_monitor_service import get_batch_run_detail, list_batch_runs
from app.services.analytics_service import (
    get_dashboard_summary,
    get_daily_document_trend,
    get_domain_summary,
    get_error_summary,
    get_quality_report,
    get_reference_source_summary,
)
from app.services.export_service import export_csv, export_excel, export_markdown
from app.services.results_service import DEFAULT_PAGE_SIZE, get_references
from app.services.retry_service import (
    force_reprocess_document,
    retry_document_resolution,
    retry_failed_document,
)
from app.services.ui_views import (
    count_pending_inbox_files,
    fetch_export_summary,
    fetch_latest_batch,
    fetch_recent_batches,
    fetch_recent_error_insights,
    list_inbox_files,
)
from app.storage import get_storage_service
from app.traversal import build_document_traversal_payload
from app.web.context import base_context


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "web" / "templates")
logger = get_logger(__name__)


def _render(
    request: Request,
    *,
    name: str,
    current_page: str,
    context: dict | None = None,
):
    merged_context = {"user": None, "current_page": current_page}
    if context:
        merged_context.update(context)
    return templates.TemplateResponse(request=request, name=name, context=base_context(request, **merged_context))


def _normalize_optional_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _build_results_query_string(
    *,
    filters: dict[str, str | None],
    page: int,
) -> str:
    params = {"page": page}
    for key, value in filters.items():
        if value:
            params[key] = value
    return urlencode(params)


def _collect_result_filters(
    *,
    search: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    filename: str | None = None,
    processing_status: str | None = None,
    processing_error_type: str | None = None,
    resolution_error_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    domain: str | None = None,
) -> dict[str, str | None]:
    return {
        "search": _normalize_optional_query(search),
        "status": _normalize_optional_query(status),
        "source_type": _normalize_optional_query(source_type),
        "filename": _normalize_optional_query(filename),
        "processing_status": _normalize_optional_query(processing_status),
        "processing_error_type": _normalize_optional_query(processing_error_type),
        "resolution_error_type": _normalize_optional_query(resolution_error_type),
        "date_from": _normalize_optional_query(date_from),
        "date_to": _normalize_optional_query(date_to),
        "domain": _normalize_optional_query(domain),
    }


def _export_filter_context(filters: dict[str, str | None]) -> dict[str, str]:
    return {key: value or "" for key, value in filters.items()}


def _save_uploaded_file(request: Request, upload: UploadFile) -> tuple[bool, str]:
    if not upload.filename:
        return False, "ไม่พบชื่อไฟล์"
    if Path(upload.filename).suffix.lower() != ".pdf":
        return False, "รองรับเฉพาะไฟล์ PDF"

    original_name = Path(upload.filename).name
    storage = get_storage_service(request.app.state.settings)
    saved_path = storage.save_upload_to_inbox(filename=original_name, fileobj=upload.file)
    return True, str(saved_path)


def _load_document_lifecycle_payload(request: Request, document_id: int) -> dict | None:
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        document = session.get(Document, document_id)
        if document is None:
            return None
        timeline = get_document_timeline(session, document_id)
        consistency = validate_document_consistency(session, document_id, settings=request.app.state.settings)
        if consistency is None:
            return None
        return build_document_lifecycle_payload(document, events=timeline, consistency=consistency)


@router.post("/settings/language")
async def set_language(
    lang: str = Form(...),
    next_url: str | None = Form(default=None, alias="next"),
):
    normalized_lang = normalize_lang(lang)
    redirect_url = safe_redirect_target(next_url, default="/dashboard")
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        key="lang",
        value=normalized_lang,
        max_age=31_536_000,
        httponly=False,
        samesite="lax",
    )
    return response


@router.get("/imports")
async def imports_page(request: Request):
    inbox_items = list_inbox_files(request.app.state.settings, request.app.state.database_engine)
    return _render(
        request,
        name="imports.html",
        current_page="imports",
        context={
            "inbox_items": inbox_items,
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.database_engine,
            ),
            "upload_summary": None,
        },
    )


@router.get("/dashboard")
async def dashboard_page(request: Request):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        summary = get_dashboard_summary(session)
        domain_summary = get_domain_summary(session)
        source_summary = get_reference_source_summary(session)
        error_summary = get_error_summary(session)
        daily_trend = get_daily_document_trend(session)

    return _render(
        request,
        name="dashboard.html",
        current_page="dashboard",
        context={
            "summary": summary,
            "domain_summary": domain_summary,
            "source_summary": source_summary,
            "error_summary": error_summary,
            "daily_trend": daily_trend,
        },
    )


@router.get("/quality")
async def quality_page(request: Request):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        quality = get_quality_report(session)

    return _render(
        request,
        name="quality.html",
        current_page="quality",
        context={"quality": quality},
    )


@router.post("/imports/upload")
async def upload_imports(
    request: Request,
    files: list[UploadFile] = File(...),
):
    saved_files: list[str] = []
    failed_files: list[str] = []
    storage = get_storage_service(request.app.state.settings)
    target_dir = storage.inbox_root
    logger.info(
        "Imports upload start inbox_path=%s requested_files=%s filenames=%s",
        target_dir,
        len(files),
        [upload.filename for upload in files],
    )

    for upload in files:
        success, value = _save_uploaded_file(request, upload)
        if success:
            saved_files.append(value)
            logger.info(
                "Imports upload saved original_name=%s saved_path=%s inbox_path=%s",
                upload.filename,
                value,
                target_dir,
            )
        else:
            failed_files.append(f"{upload.filename or 'unknown'}: {value}")
            logger.warning(
                "Imports upload failed original_name=%s reason=%s inbox_path=%s",
                upload.filename,
                value,
                target_dir,
            )
        await upload.close()

    inbox_items = list_inbox_files(request.app.state.settings, request.app.state.database_engine)
    return _render(
        request,
        name="imports.html",
        current_page="imports",
        context={
            "inbox_items": inbox_items,
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.database_engine,
            ),
            "upload_summary": {
                "saved_count": len(saved_files),
                "failed_count": len(failed_files),
                "saved_files": saved_files,
                "failed_files": failed_files,
            },
        },
    )


@router.post("/imports/delete")
async def delete_import_file(
    request: Request,
    file_name: str = Form(...),
):
    storage = get_storage_service(request.app.state.settings)
    if storage.delete_inbox_file(file_name):
        logger.info("Imports delete removed file_name=%s inbox_path=%s", file_name, storage.inbox_root)
    else:
        logger.warning("Imports delete skipped file_name=%s reason=not_found", file_name)

    return RedirectResponse(url="/imports", status_code=303)


@router.get("/batch")
async def batch_page(request: Request, force_reprocess_status: str | None = Query(default=None)):
    return _render(
        request,
        name="batch.html",
        current_page="batch",
        context={
            "batch_summary": None,
            "latest_batch": fetch_latest_batch(request.app.state.database_engine),
            "recent_batches": fetch_recent_batches(request.app.state.database_engine),
            "error_insights": fetch_recent_error_insights(request.app.state.database_engine),
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.database_engine,
            ),
            "force_reprocess_status": force_reprocess_status,
        },
    )


@router.get("/batch/runs")
async def batch_runs_page(
    request: Request,
    page: int = Query(default=1, ge=1),
):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        runs = list_batch_runs(session, page=page, page_size=20)

    return _render(
        request,
        name="batch_runs.html",
        current_page="batch_runs",
        context={
            "runs": runs,
        },
    )


@router.get("/batch/runs/{batch_run_id}")
async def batch_run_detail_page(
    request: Request,
    batch_run_id: int,
):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        detail = get_batch_run_detail(session, batch_run_id)

    if detail is None:
        return RedirectResponse(url="/batch/runs", status_code=303)

    return _render(
        request,
        name="batch_run_detail.html",
        current_page="batch_runs",
        context={
            "detail": detail,
        },
    )


@router.get("/results")
async def results_page(
    request: Request,
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    filename: str | None = Query(default=None),
    processing_status: str | None = Query(default=None),
    processing_error_type: str | None = Query(default=None),
    resolution_error_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    retry_status: str | None = Query(default=None),
    force_reprocess_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
):
    filters = _collect_result_filters(
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
    )
    offset = (page - 1) * DEFAULT_PAGE_SIZE
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        results = get_references(
            session,
            search=filters["search"],
            status=filters["status"],
            source_type=filters["source_type"],
            filename=filters["filename"],
            processing_status=filters["processing_status"],
            processing_error_type=filters["processing_error_type"],
            resolution_error_type=filters["resolution_error_type"],
            date_from=filters["date_from"],
            date_to=filters["date_to"],
            domain=filters["domain"],
            limit=DEFAULT_PAGE_SIZE,
            offset=offset,
        )

    total = results["total"]
    has_prev = page > 1
    has_next = offset + DEFAULT_PAGE_SIZE < total

    return _render(
        request,
        name="results.html",
        current_page="results",
        context={
            "rows": results["rows"],
            "total": total,
            "page": page,
            "page_size": DEFAULT_PAGE_SIZE,
            **_export_filter_context(filters),
            "filter_query": urlencode({key: value for key, value in filters.items() if value}),
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_query": _build_results_query_string(
                filters=filters,
                page=page - 1,
            ),
            "next_query": _build_results_query_string(
                filters=filters,
                page=page + 1,
            ),
            "retry_status": retry_status,
            "force_reprocess_status": force_reprocess_status,
        },
    )


@router.get("/documents/{document_id}/lifecycle")
async def document_lifecycle_timeline(request: Request, document_id: int):
    payload = _load_document_lifecycle_payload(request, document_id)
    if payload is None:
        return JSONResponse({"detail": "Document not found"}, status_code=404)
    return JSONResponse(payload)


@router.get("/documents/{document_id}/lifecycle/consistency")
async def document_lifecycle_consistency(request: Request, document_id: int):
    payload = _load_document_lifecycle_payload(request, document_id)
    if payload is None:
        return JSONResponse({"detail": "Document not found"}, status_code=404)
    return JSONResponse(
        {
            "document_id": document_id,
            "current_state": payload["current_state"],
            "consistency": payload["consistency"],
        }
    )


@router.get("/documents/{document_id}/lifecycle/view")
async def document_lifecycle_page(request: Request, document_id: int):
    payload = _load_document_lifecycle_payload(request, document_id)
    if payload is None:
        return RedirectResponse(url="/results", status_code=303)
    return _render(
        request,
        name="document_lifecycle.html",
        current_page="results",
        context={"lifecycle": payload},
    )


@router.get("/documents/{document_id}/traversal")
async def document_traversal_plan(request: Request, document_id: int):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        payload = build_document_traversal_payload(
            session,
            document_id=document_id,
            settings=request.app.state.settings,
        )
        if payload is not None:
            session.commit()
    if payload is None:
        return JSONResponse({"detail": "Document not found"}, status_code=404)
    return JSONResponse(payload)


@router.get("/documents/{document_id}/traversal/view")
async def document_traversal_page(request: Request, document_id: int):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        payload = build_document_traversal_payload(
            session,
            document_id=document_id,
            settings=request.app.state.settings,
        )
        if payload is not None:
            session.commit()
    if payload is None:
        return RedirectResponse(url="/results", status_code=303)
    return _render(
        request,
        name="document_traversal.html",
        current_page="results",
        context={"traversal": payload},
    )


@router.post("/documents/{document_id}/retry")
async def retry_document(request: Request, document_id: int):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        result = retry_failed_document(
            session,
            request.app.state.settings,
            request.app.state.database_engine,
            document_id,
        )
        session.commit()

    if result.success:
        logger.info("Retry queued document_id=%s batch_run_id=%s", document_id, result.batch_run_id)
        return RedirectResponse(url="/batch", status_code=303)

    logger.warning("Retry skipped document_id=%s reason=%s", document_id, result.reason)
    return RedirectResponse(url=f"/results?retry_status={result.reason}", status_code=303)


@router.post("/documents/{document_id}/retry-resolution")
async def retry_document_url_resolution(request: Request, document_id: int):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        result = retry_document_resolution(session, request.app.state.settings, document_id)
        session.commit()

    if result.success:
        return RedirectResponse(url="/results?retry_status=resolution_retried", status_code=303)
    return RedirectResponse(url=f"/results?retry_status={result.reason}", status_code=303)


@router.post("/documents/{document_id}/force-reprocess")
async def force_reprocess(request: Request, document_id: int):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        result = force_reprocess_document(
            session,
            request.app.state.settings,
            request.app.state.database_engine,
            document_id,
        )
        session.commit()

    if result.success:
        return RedirectResponse(url="/batch?force_reprocess_status=queued", status_code=303)
    return RedirectResponse(
        url=f"/results?force_reprocess_status={result.reason}",
        status_code=303,
    )


@router.get("/exports")
async def exports_page(
    request: Request,
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    filename: str | None = Query(default=None),
    processing_status: str | None = Query(default=None),
    processing_error_type: str | None = Query(default=None),
    resolution_error_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    domain: str | None = Query(default=None),
):
    filters = _collect_result_filters(
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
    )

    return _render(
        request,
        name="exports.html",
        current_page="exports",
        context={
            "export_summary": fetch_export_summary(request.app.state.database_engine),
            **_export_filter_context(filters),
            "filter_query": urlencode({key: value for key, value in filters.items() if value}),
        },
    )


@router.get("/exports/csv")
async def export_csv_route(
    request: Request,
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    filename: str | None = Query(default=None),
    processing_status: str | None = Query(default=None),
    processing_error_type: str | None = Query(default=None),
    resolution_error_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    domain: str | None = Query(default=None),
):
    filters = _collect_result_filters(
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
    )
    session_factory = get_session_factory(request.app.state.database_engine)
    session = session_factory()
    try:
        response = export_csv(
            session,
            filters,
        )
    except Exception:
        session.close()
        raise

    response.background = BackgroundTask(session.close)
    return response


@router.get("/exports/markdown")
async def export_markdown_route(
    request: Request,
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    filename: str | None = Query(default=None),
    processing_status: str | None = Query(default=None),
    processing_error_type: str | None = Query(default=None),
    resolution_error_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    domain: str | None = Query(default=None),
):
    filters = _collect_result_filters(
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
    )
    session_factory = get_session_factory(request.app.state.database_engine)
    session = session_factory()
    try:
        response = export_markdown(
            session,
            filters,
        )
    except Exception:
        session.close()
        raise

    response.background = BackgroundTask(session.close)
    return response


@router.get("/exports/excel")
async def export_excel_route(
    request: Request,
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    filename: str | None = Query(default=None),
    processing_status: str | None = Query(default=None),
    processing_error_type: str | None = Query(default=None),
    resolution_error_type: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    domain: str | None = Query(default=None),
):
    filters = _collect_result_filters(
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
    )
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        return export_excel(session, filters)
