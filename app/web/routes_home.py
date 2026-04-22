from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.session import SessionManager
from app.config import BASE_DIR
from app.dependencies import get_session_manager
from app.services.process_batch import fetch_home_batch_summary


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "web" / "templates")


@router.get("/")
async def home(request: Request, session_manager: SessionManager = Depends(get_session_manager)):
    user = session_manager.get_session_from_request(request)
    if not user:
        return RedirectResponse(url="/login?next=/", status_code=303)

    latest_batch = fetch_home_batch_summary(request.app.state.postgres_engine)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "user": user,
            "batch_summary": None,
            "latest_batch": latest_batch,
        },
    )
