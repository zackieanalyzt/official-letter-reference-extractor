from fastapi import Request

from app.i18n import get_labels, normalize_lang
from app.release import get_release_info


def base_context(request: Request, **kwargs):
    settings = request.app.state.settings
    default_lang = getattr(settings, "app_lang", "th")
    current_lang = normalize_lang(request.cookies.get("lang"), default=default_lang)
    return {
        "request": request,
        "labels": get_labels(current_lang),
        "current_lang": current_lang,
        "release_info": get_release_info(settings),
        **kwargs,
    }
