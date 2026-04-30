from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.session import SessionManager
from app.config import BASE_DIR
from app.dependencies import get_session_manager
from app.services.process_batch import run_batch_registration
from app.services.ui_views import (
    count_pending_inbox_files,
    fetch_latest_batch,
    fetch_recent_batches,
    fetch_recent_error_insights,
    localize_batch_summary,
)


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "web" / "templates")


@router.post("/batch/process")
async def process_batch(request: Request, session_manager: SessionManager = Depends(get_session_manager)):
    user = session_manager.get_session_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/", status_code=303)

    batch_summary = run_batch_registration(
        request.app.state.settings,
        request.app.state.postgres_engine,
        triggered_by=user["username"],
    )
    batch_summary = localize_batch_summary(batch_summary)
    latest_batch = fetch_latest_batch(request.app.state.postgres_engine)
    return templates.TemplateResponse(
        request=request,
        name="batch.html",
        context={
            "user": user,
            "current_page": "batch",
            "batch_summary": batch_summary,
            "latest_batch": latest_batch,
            "recent_batches": fetch_recent_batches(request.app.state.postgres_engine),
            "error_insights": fetch_recent_error_insights(request.app.state.postgres_engine),
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.postgres_engine,
            ),
        },
    )
