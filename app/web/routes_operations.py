from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from app.config import BASE_DIR
from app.db.postgres import create_postgres_session_factory
from app.logging_config import get_logger
from app.services.batch_monitor_service import get_batch_run_detail, list_batch_runs
from app.services.export_service import export_csv, export_markdown
from app.services.inbox_paths import get_inbox_path
from app.services.results_service import DEFAULT_PAGE_SIZE, get_references
from app.services.retry_service import retry_failed_document
from app.services.ui_views import (
    count_pending_inbox_files,
    fetch_export_summary,
    fetch_latest_batch,
    fetch_recent_batches,
    fetch_recent_error_insights,
    list_inbox_files,
    safe_inbox_file_path,
)


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
    return templates.TemplateResponse(request=request, name=name, context=merged_context)


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


def _save_uploaded_file(target_dir: Path, upload: UploadFile) -> tuple[bool, str]:
    if not upload.filename:
        return False, "ไม่พบชื่อไฟล์"
    if Path(upload.filename).suffix.lower() != ".pdf":
        return False, "รองรับเฉพาะไฟล์ PDF"

    original_name = Path(upload.filename).name
    candidate = target_dir / original_name
    if candidate.exists():
        stem = candidate.stem
        suffix = candidate.suffix
        counter = 1
        while candidate.exists():
            candidate = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    with candidate.open("wb") as output_file:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            output_file.write(chunk)
    return True, str(candidate.resolve())


@router.get("/imports")
async def imports_page(request: Request):
    inbox_items = list_inbox_files(request.app.state.settings, request.app.state.postgres_engine)
    return _render(
        request,
        name="imports.html",
        current_page="imports",
        context={
            "inbox_items": inbox_items,
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.postgres_engine,
            ),
            "upload_summary": None,
        },
    )


@router.post("/imports/upload")
async def upload_imports(
    request: Request,
    files: list[UploadFile] = File(...),
):
    saved_files: list[str] = []
    failed_files: list[str] = []
    target_dir = get_inbox_path(request.app.state.settings)
    logger.info(
        "Imports upload start inbox_path=%s requested_files=%s filenames=%s",
        target_dir,
        len(files),
        [upload.filename for upload in files],
    )

    for upload in files:
        success, value = _save_uploaded_file(target_dir, upload)
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

    inbox_items = list_inbox_files(request.app.state.settings, request.app.state.postgres_engine)
    return _render(
        request,
        name="imports.html",
        current_page="imports",
        context={
            "inbox_items": inbox_items,
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.postgres_engine,
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
    target_path = safe_inbox_file_path(request.app.state.settings, file_name)
    if target_path:
        target_path.unlink(missing_ok=True)
        logger.info("Imports delete removed file_name=%s file_path=%s", file_name, target_path)
    else:
        logger.warning("Imports delete skipped file_name=%s reason=not_found_or_outside_inbox", file_name)

    return RedirectResponse(url="/imports", status_code=303)


@router.get("/batch")
async def batch_page(request: Request):
    return _render(
        request,
        name="batch.html",
        current_page="batch",
        context={
            "batch_summary": None,
            "latest_batch": fetch_latest_batch(request.app.state.postgres_engine),
            "recent_batches": fetch_recent_batches(request.app.state.postgres_engine),
            "error_insights": fetch_recent_error_insights(request.app.state.postgres_engine),
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.postgres_engine,
            ),
        },
    )


@router.get("/batch/runs")
async def batch_runs_page(
    request: Request,
    page: int = Query(default=1, ge=1),
):
    session_factory = create_postgres_session_factory(request.app.state.postgres_engine)
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
    session_factory = create_postgres_session_factory(request.app.state.postgres_engine)
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
    page: int = Query(default=1, ge=1),
):
    normalized_search = _normalize_optional_query(search)
    normalized_status = _normalize_optional_query(status)
    normalized_source_type = _normalize_optional_query(source_type)
    filters = {
        "search": normalized_search,
        "status": normalized_status,
        "source_type": normalized_source_type,
        "filename": _normalize_optional_query(filename),
        "processing_status": _normalize_optional_query(processing_status),
        "processing_error_type": _normalize_optional_query(processing_error_type),
        "resolution_error_type": _normalize_optional_query(resolution_error_type),
        "date_from": _normalize_optional_query(date_from),
        "date_to": _normalize_optional_query(date_to),
        "domain": _normalize_optional_query(domain),
    }
    offset = (page - 1) * DEFAULT_PAGE_SIZE
    session_factory = create_postgres_session_factory(request.app.state.postgres_engine)
    with session_factory() as session:
        results = get_references(
            session,
            search=normalized_search,
            status=normalized_status,
            source_type=normalized_source_type,
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
            "search": normalized_search or "",
            "status": normalized_status or "",
            "source_type": normalized_source_type or "",
            "filename": filters["filename"] or "",
            "processing_status": filters["processing_status"] or "",
            "processing_error_type": filters["processing_error_type"] or "",
            "resolution_error_type": filters["resolution_error_type"] or "",
            "date_from": filters["date_from"] or "",
            "date_to": filters["date_to"] or "",
            "domain": filters["domain"] or "",
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
        },
    )


@router.post("/documents/{document_id}/retry")
async def retry_document(request: Request, document_id: int):
    session_factory = create_postgres_session_factory(request.app.state.postgres_engine)
    with session_factory() as session:
        result = retry_failed_document(session, request.app.state.settings, document_id)

    if result.success:
        logger.info("Retry queued document_id=%s destination=%s", document_id, result.destination_path)
        return RedirectResponse(url="/imports", status_code=303)

    logger.warning("Retry skipped document_id=%s reason=%s", document_id, result.reason)
    return RedirectResponse(url=f"/results?retry_status={result.reason}", status_code=303)


@router.get("/exports")
async def exports_page(
    request: Request,
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
):
    normalized_search = _normalize_optional_query(search)
    normalized_status = _normalize_optional_query(status)
    normalized_source_type = _normalize_optional_query(source_type)

    return _render(
        request,
        name="exports.html",
        current_page="exports",
        context={
            "export_summary": fetch_export_summary(request.app.state.postgres_engine),
            "search": normalized_search or "",
            "status": normalized_status or "",
            "source_type": normalized_source_type or "",
        },
    )


@router.get("/exports/csv")
async def export_csv_route(
    request: Request,
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
):
    session_factory = create_postgres_session_factory(request.app.state.postgres_engine)
    session = session_factory()
    try:
        response = export_csv(
            session,
            {
                "search": _normalize_optional_query(search),
                "status": _normalize_optional_query(status),
                "source_type": _normalize_optional_query(source_type),
            },
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
):
    session_factory = create_postgres_session_factory(request.app.state.postgres_engine)
    session = session_factory()
    try:
        response = export_markdown(
            session,
            {
                "search": _normalize_optional_query(search),
                "status": _normalize_optional_query(status),
                "source_type": _normalize_optional_query(source_type),
            },
        )
    except Exception:
        session.close()
        raise

    response.background = BackgroundTask(session.close)
    return response
