from fastapi import Request

from app.i18n import get_labels, normalize_lang


def base_context(request: Request, **kwargs):
    default_lang = getattr(request.app.state.settings, "app_lang", "th")
    current_lang = normalize_lang(request.cookies.get("lang"), default=default_lang)
    return {
        "request": request,
        "labels": get_labels(current_lang),
        "current_lang": current_lang,
        **kwargs,
    }
