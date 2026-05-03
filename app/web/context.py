from fastapi import Request

from app.i18n.th import LABELS


def base_context(request: Request, **kwargs):
    return {
        "request": request,
        "labels": LABELS,
        **kwargs,
    }
