from __future__ import annotations

from urllib.parse import urlparse

from app.batch.destination_classification import SHORT_URL_HOSTS
from app.traversal.schemas import (
    TARGET_HTML_PAGE,
    TARGET_IMAGE_URL,
    TARGET_KNOWN_SHORT_URL,
    TARGET_MALFORMED_URL,
    TARGET_PDF_URL,
    TARGET_UNKNOWN,
    TARGET_UNSUPPORTED_SCHEME,
    TraversalClassification,
)


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff", ".bmp"}
HTML_SUFFIXES = {".htm", ".html", ".php", ".asp", ".aspx"}
SUPPORTED_SCHEMES = {"http", "https"}


def classify_reference_url(url: str | None) -> TraversalClassification:
    if not isinstance(url, str) or not url.strip():
        return TraversalClassification(
            target_type=TARGET_MALFORMED_URL,
            candidate_url=None,
            scheme=None,
            host=None,
            path="",
            reason="empty_url",
        )

    candidate_url = url.strip()
    try:
        parsed = urlparse(candidate_url)
    except Exception:
        return TraversalClassification(
            target_type=TARGET_MALFORMED_URL,
            candidate_url=candidate_url,
            scheme=None,
            host=None,
            path="",
            reason="parse_error",
        )

    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower().strip() or None
    path = parsed.path.lower().strip()

    if not scheme or not host:
        return TraversalClassification(
            target_type=TARGET_MALFORMED_URL,
            candidate_url=candidate_url,
            scheme=scheme or None,
            host=host,
            path=path,
            reason="missing_scheme_or_host",
        )

    if scheme not in SUPPORTED_SCHEMES:
        return TraversalClassification(
            target_type=TARGET_UNSUPPORTED_SCHEME,
            candidate_url=candidate_url,
            scheme=scheme,
            host=host,
            path=path,
            reason="unsupported_scheme",
        )

    if path.endswith(".pdf"):
        target_type = TARGET_PDF_URL
    elif host in SHORT_URL_HOSTS:
        target_type = TARGET_KNOWN_SHORT_URL
    elif any(path.endswith(suffix) for suffix in IMAGE_SUFFIXES):
        target_type = TARGET_IMAGE_URL
    elif any(path.endswith(suffix) for suffix in HTML_SUFFIXES) or path in {"", "/"}:
        target_type = TARGET_HTML_PAGE
    else:
        target_type = TARGET_UNKNOWN

    return TraversalClassification(
        target_type=target_type,
        candidate_url=candidate_url,
        scheme=scheme,
        host=host,
        path=path,
        reason=None,
    )

