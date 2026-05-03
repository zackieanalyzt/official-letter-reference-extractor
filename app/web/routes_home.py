from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse


router = APIRouter()


@router.get("/")
async def home(request: Request):
    return RedirectResponse(url="/imports", status_code=303)
