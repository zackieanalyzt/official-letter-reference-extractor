from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth.session import SessionManager
from app.config import BASE_DIR, get_settings
from app.db.engine import create_database_engine
from app.db.mariadb import create_mariadb_engine
from app.logging_config import configure_logging, get_logger
from app.web.routes_auth import router as auth_router
from app.web.routes_batch import router as batch_router
from app.web.routes_debug import router as debug_router
from app.web.routes_home import router as home_router
from app.web.routes_operations import router as operations_router


settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.postgres_engine = create_database_engine(settings)
    if settings.enable_auth:
        app.state.mariadb_engine = create_mariadb_engine(settings)
        app.state.session_manager = SessionManager(
            secret_key=settings.secret_key,
            cookie_name=settings.session_cookie_name,
            max_age_seconds=settings.session_max_age_seconds,
        )
    else:
        app.state.mariadb_engine = None
        app.state.session_manager = None
    logger.info("Application startup complete")
    yield
    app.state.postgres_engine.dispose()
    if app.state.mariadb_engine is not None:
        app.state.mariadb_engine.dispose()
    logger.info("Application shutdown complete")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
app.mount("/debug/qr", StaticFiles(directory=settings.qr_debug_path, check_dir=False), name="debug_qr")


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    logger.info("Request started method=%s path=%s", request.method, request.url.path)
    response = await call_next(request)
    logger.info(
        "Request completed method=%s path=%s status=%s",
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    app_settings = request.app.state.settings
    return JSONResponse(
        {
            "status": "ready",
            "app_name": app_settings.app_name,
            "environment": app_settings.app_env,
        }
    )


if settings.enable_auth:
    app.include_router(auth_router)
app.include_router(batch_router)
app.include_router(debug_router)
app.include_router(home_router)
app.include_router(operations_router)
