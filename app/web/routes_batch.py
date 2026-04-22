from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.session import SessionManager
from app.config import BASE_DIR
from app.dependencies import get_session_manager
from app.services.process_batch import fetch_home_batch_summary, run_batch_registration


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
    latest_batch = fetch_home_batch_summary(request.app.state.postgres_engine)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "user": user,
            "batch_summary": batch_summary,
            "latest_batch": latest_batch,
        },
    )
