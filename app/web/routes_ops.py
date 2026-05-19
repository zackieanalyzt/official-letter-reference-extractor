from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR
from app.db.session import get_session_factory
from app.ops import (
    build_lifecycle_consistency_summary,
    build_ops_dashboard_snapshot,
    build_orphan_detection_summary,
    build_runtime_snapshot,
)
from app.traversal import build_ops_traversal_summary
from app.web.context import base_context


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "web" / "templates")


def _render(request: Request, *, name: str, current_page: str, context: dict | None = None):
    merged_context = {"user": None, "current_page": current_page}
    if context:
        merged_context.update(context)
    return templates.TemplateResponse(request=request, name=name, context=base_context(request, **merged_context))


@router.get("/ops/runtime")
async def ops_runtime(request: Request):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        snapshot = build_runtime_snapshot(session, request.app.state.settings, request.app.state.database_engine)
    return JSONResponse(snapshot.to_dict())


@router.get("/ops/storage/orphans")
async def ops_storage_orphans(request: Request):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        summary = build_orphan_detection_summary(session, request.app.state.settings)
    return JSONResponse(summary.to_dict())


@router.get("/ops/lifecycle/consistency-summary")
async def ops_lifecycle_consistency_summary(request: Request):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        summary = build_lifecycle_consistency_summary(session, settings=request.app.state.settings)
    return JSONResponse(summary.to_dict())


@router.get("/ops/traversal")
async def ops_traversal(request: Request):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        summary = build_ops_traversal_summary(session)
    return JSONResponse(
        {
            "total": summary.total,
            "by_status": summary.by_status,
            "by_policy_decision": summary.by_policy_decision,
            "by_target_type": summary.by_target_type,
        }
    )


@router.get("/ops")
async def ops_page(request: Request):
    session_factory = get_session_factory(request.app.state.database_engine)
    with session_factory() as session:
        payload = build_ops_dashboard_snapshot(session, request.app.state.settings, request.app.state.database_engine)
    return _render(
        request,
        name="ops.html",
        current_page="ops",
        context={"ops": payload.to_dict()},
    )
