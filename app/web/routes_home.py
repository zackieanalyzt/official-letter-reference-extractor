from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.session import SessionManager
from app.config import BASE_DIR
from app.dependencies import get_session_manager
from app.services.ui_views import count_pending_inbox_files, fetch_latest_batch


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "web" / "templates")


@router.get("/")
async def home(request: Request, session_manager: SessionManager = Depends(get_session_manager)):
    user = session_manager.get_session_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "user": user,
            "current_page": "home",
            "latest_batch": fetch_latest_batch(request.app.state.postgres_engine),
            "pending_count": count_pending_inbox_files(
                request.app.state.settings,
                request.app.state.postgres_engine,
            ),
        },
    )
