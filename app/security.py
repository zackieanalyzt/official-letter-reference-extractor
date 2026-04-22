from html import escape


def safe_redirect_target(value: str | None, default: str = "/") -> str:
    if not value:
        return default
    if not value.startswith("/"):
        return default
    if value.startswith("//"):
        return default
    return escape(value)

