from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.session import SessionManager
from app.batch.file_ops import ensure_directory
from app.config import BASE_DIR
from app.dependencies import get_session_manager
from app.services.ui_views import (
    count_pending_inbox_files,
    fetch_export_summary,
    fetch_latest_batch,
    fetch_results_rows,
    list_inbox_files,
    safe_inbox_file_path,
)


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "web" / "templates")


def _require_user(request: Request, session_manager: SessionManager):
    user = session_manager.get_session_from_request(request)
    if not user:
        return None, RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)
    return user, None


def _render(
    request: Request,
    *,
    name: str,
    user,
    current_page: str,
    context: dict | None = None,
):
    merged_context = {"user": user, "current_page": current_page}
    if context:
        merged_context.update(context)
    return templates.TemplateResponse(request=request, name=name, context=merged_context)


def _save_uploaded_file(target_dir: Path, upload: UploadFile) -> tuple[bool, str]:
    if not upload.filename:
        return False, "ไม่พบชื่อไฟล์"
    if Path(upload.filename).suffix.lower() != ".pdf":
        return False, "รองรับเฉพาะไฟล์ PDF"

    target_dir = ensure_directory(target_dir)
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
    return True, candidate.name


@router.get("/imports")
async def imports_page(request: Request, session_manager: SessionManager = Depends(get_session_manager)):
    user, redirect_response = _require_user(request, session_manager)
    if redirect_response:
        return redirect_response

    inbox_items = list_inbox_files(request.app.state.settings, request.app.state.postgres_engine)
    return _render(
        request,
        name="imports.html",
        user=user,
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
    session_manager: SessionManager = Depends(get_session_manager),
):
    user, redirect_response = _require_user(request, session_manager)
    if redirect_response:
        return redirect_response

    saved_files: list[str] = []
    failed_files: list[str] = []
    target_dir = request.app.state.settings.input_path

    for upload in files:
        success, value = _save_uploaded_file(target_dir, upload)
        if success:
            saved_files.append(value)
        else:
            failed_files.append(f"{upload.filename or 'unknown'}: {value}")
        await upload.close()

    inbox_items = list_inbox_files(request.app.state.settings, request.app.state.postgres_engine)
    return _render(
        request,
        name="imports.html",
        user=user,
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
    session_manager: SessionManager = Depends(get_session_manager),
):
    user, redirect_response = _require_user(request, session_manager)
    if redirect_response:
        return redirect_response

    target_path = safe_inbox_file_path(request.app.state.settings, file_name)
    if target_path:
        target_path.unlink(missing_ok=True)

    return RedirectResponse(url="/imports", status_code=303)


@router.get("/batch")
async def batch_page(request: Request, session_manager: SessionManager = Depends(get_session_manager)):
    user, redirect_response = _require_user(request, session_manager)
    if redirect_response:
        return redirect_response

    return _render(
        request,
        name="batch.html",
        user=user,
        current_page="batch",
        context={
            "batch_summary": None,
            "latest_batch": fetch_latest_batch(request.app.state.postgres_engine),
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.postgres_engine,
            ),
        },
    )


@router.get("/results")
async def results_page(request: Request, session_manager: SessionManager = Depends(get_session_manager)):
    user, redirect_response = _require_user(request, session_manager)
    if redirect_response:
        return redirect_response

    return _render(
        request,
        name="results.html",
        user=user,
        current_page="results",
        context={
            "result_rows": fetch_results_rows(request.app.state.postgres_engine),
        },
    )


@router.get("/exports")
async def exports_page(request: Request, session_manager: SessionManager = Depends(get_session_manager)):
    user, redirect_response = _require_user(request, session_manager)
    if redirect_response:
        return redirect_response

    return _render(
        request,
        name="exports.html",
        user=user,
        current_page="exports",
        context={
            "export_summary": fetch_export_summary(request.app.state.postgres_engine),
        },
    )
