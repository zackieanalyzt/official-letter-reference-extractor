from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.batch.qr_debug import load_debug_payload
from app.config import BASE_DIR
from app.db.models import Document
from app.db.session import get_session_factory
from app.web.context import base_context


router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "app" / "web" / "templates")


def _get_document(database_engine, document_id: int) -> dict | None:
    session_factory = get_session_factory(database_engine)
    with session_factory() as session:
        row = session.execute(
            select(
                Document.id,
                Document.original_file_name,
                Document.processing_status,
                Document.page_count,
                Document.processed_at,
            ).where(Document.id == document_id)
        ).one_or_none()

    if row is None:
        return None

    return {
        "document_id": row.id,
        "filename": row.original_file_name,
        "processing_status": row.processing_status,
        "page_count": row.page_count,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }


@router.get("/debug/document/{document_id}")
async def debug_view(
    request: Request,
    document_id: int,
    format: str | None = Query(default=None),
):
    document = _get_document(request.app.state.database_engine, document_id)
    if document is None:
        if format == "json" or "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"detail": "Document not found"}, status_code=404)
        return RedirectResponse(url="/results", status_code=303)

    payload = load_debug_payload(document_id, request.app.state.settings)
    response_payload = {
        "document_id": document_id,
        "document": document,
        "pages": payload["pages"],
        "generated_at": payload.get("generated_at"),
        "debug_enabled": request.app.state.settings.qr_debug_export,
    }

    accept = request.headers.get("accept", "")
    if format == "json" or ("application/json" in accept and "text/html" not in accept):
        return JSONResponse(response_payload)

    return templates.TemplateResponse(
        request=request,
        name="debug_document.html",
        context=base_context(
            request,
            user=None,
            current_page="debug",
            **response_payload,
        ),
    )
