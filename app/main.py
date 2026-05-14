import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth.session import SessionManager
from app.config import BASE_DIR, get_settings
from app.db.engine import create_database_engine, get_database_backend
from app.db.mariadb import create_mariadb_engine
from app.db.session import get_session_factory
from app.logging_config import configure_logging, get_logger
from app.runtime import build_readiness_report, validate_startup
from app.services.retention_service import run_retention_cleanup
from app.web.routes_auth import router as auth_router
from app.web.routes_batch import router as batch_router
from app.web.routes_debug import router as debug_router
from app.web.routes_home import router as home_router
from app.web.routes_ops import router as ops_router
from app.web.routes_operations import router as operations_router


settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_startup(settings)
    app.state.settings = settings
    app.state.database_engine = create_database_engine(settings)
    app.state.database_backend = get_database_backend(settings.resolved_database_url)
    logger.info(
        "[DB_CONFIG] backend=%s url=%s",
        app.state.database_backend,
        settings.resolved_database_url,
    )
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
    cleanup_stop = asyncio.Event()

    async def cleanup_loop():
        session_factory = get_session_factory(app.state.database_engine)
        if settings.cleanup_startup_sweep and settings.cleanup_enabled:
            with session_factory() as session:
                summary = run_retention_cleanup(session, settings)
                session.commit()
                logger.info("[CLEANUP_STARTUP] %s", summary)

        while not cleanup_stop.is_set():
            try:
                await asyncio.wait_for(cleanup_stop.wait(), timeout=settings.cleanup_interval_minutes * 60)
            except asyncio.TimeoutError:
                if settings.cleanup_enabled:
                    with session_factory() as session:
                        summary = run_retention_cleanup(session, settings)
                        session.commit()
                        logger.info("[CLEANUP_INTERVAL] %s", summary)

    cleanup_task = asyncio.create_task(cleanup_loop())
    logger.info("Application startup complete")
    yield
    cleanup_stop.set()
    cleanup_task.cancel()
    try:
        await cleanup_task
    except BaseException:
        pass
    app.state.database_engine.dispose()
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
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "database_backend": request.app.state.database_backend,
        }
    )


@app.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    app_settings = request.app.state.settings
    report = build_readiness_report(app_settings, request.app.state.database_engine)
    status_code = 200 if report.ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if report.ok else "not_ready",
            "app_name": app_settings.app_name,
            "environment": app_settings.app_env,
            "database_backend": report.database_backend,
            "database_ping": report.database_ping,
            "writable_paths": report.writable_paths,
            "details": report.details,
        },
    )


if settings.enable_auth:
    app.include_router(auth_router)
app.include_router(batch_router)
app.include_router(debug_router)
app.include_router(home_router)
app.include_router(ops_router)
app.include_router(operations_router)
