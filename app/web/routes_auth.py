from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth.service import authenticate_user, write_audit_log
from app.auth.session import SessionManager
from app.config import BASE_DIR
from app.dependencies import get_session_manager
from app.security import safe_redirect_target


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "web" / "templates")


@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error_message": None,
            "next_url": request.query_params.get("next", "/"),
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next_url: str = Form("/"),
    session_manager: SessionManager = Depends(get_session_manager),
):
    normalized_username = username.strip()
    result = authenticate_user(
        request.app.state.mariadb_engine,
        username=normalized_username,
        password=password,
    )
    if not result.success:
        write_audit_log(
            request.app.state.database_engine,
            username=normalized_username or "unknown",
            action="login_failure",
            action_detail=result.error_message,
        )
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error_message": result.error_message,
                "next_url": next_url,
                "username": normalized_username,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(url=safe_redirect_target(next_url), status_code=status.HTTP_303_SEE_OTHER)
    token = session_manager.create_session(
        username=result.username or username,
        display_name=result.display_name or username,
    )
    session_manager.set_session_cookie(response, token)
    write_audit_log(
        request.app.state.database_engine,
        username=result.username or normalized_username,
        action="login_success",
        action_detail=f"display_name={result.display_name or normalized_username}",
    )
    return response


@router.post("/logout")
async def logout(request: Request, session_manager: SessionManager = Depends(get_session_manager)):
    session = session_manager.get_session_from_request(request)
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    session_manager.clear_session_cookie(response)
    if session:
        write_audit_log(
            request.app.state.database_engine,
            username=session["username"],
            action="logout",
            action_detail=f"display_name={session['display_name']}",
        )
    return response
