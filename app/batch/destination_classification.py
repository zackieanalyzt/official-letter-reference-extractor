from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


SHORT_URL_HOSTS = {
    "bit.ly",
    "t.co",
    "tinyurl.com",
    "forms.gle",
    "goo.gl",
    "buff.ly",
    "cutt.ly",
    "is.gd",
    "ow.ly",
    "rebrand.ly",
    "rb.gy",
    "shorturl.at",
    "tiny.one",
}


@dataclass(frozen=True)
class DestinationClassification:
    destination_type: str
    destination_host: str | None
    requires_user_action: bool


def _normalize_host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower().strip()
    except Exception:
        return None
    return host or None


def _normalize_path(url: str | None) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).path.lower().strip()
    except Exception:
        return ""


def classify_destination(*, raw_url: str | None, final_url: str | None) -> DestinationClassification | None:
    candidate_url = final_url or raw_url
    host = _normalize_host(candidate_url)
    if not host:
        return None

    path = _normalize_path(candidate_url)
    raw_host = _normalize_host(raw_url)

    if host == "forms.gle" or (host == "docs.google.com" and "/forms" in path):
        return DestinationClassification("form", host, True)

    if host == "drive.google.com":
        return DestinationClassification("document", host, False)

    if host == "docs.google.com":
        if "/document/" in path or "/spreadsheets/" in path or "/presentation/" in path or "/file/" in path:
            return DestinationClassification("document", host, False)
        if "/forms/" in path:
            return DestinationClassification("form", host, True)

    if path.endswith(".pdf"):
        return DestinationClassification("document", host, False)

    if host.endswith(".go.th") or host.endswith(".gov") or host.endswith(".gov.th"):
        return DestinationClassification("government", host, False)

    if raw_host in SHORT_URL_HOSTS and final_url and _normalize_host(final_url) != raw_host:
        return DestinationClassification("redirect", _normalize_host(final_url), False)

    return DestinationClassification("external", host, False)


DESTINATION_LABEL_KEYS = {
    "form": "destination_label_form",
    "document": "destination_label_document",
    "government": "destination_label_government",
    "redirect": "destination_label_redirect",
    "external": "destination_label_external",
}

DESTINATION_HINT_KEYS = {
    "form": "destination_hint_form",
    "document": "destination_hint_document",
    "government": "destination_hint_government",
    "redirect": "destination_hint_redirect",
    "external": "destination_hint_external",
}


def destination_label_key(destination_type: str | None, destination_host: str | None) -> str:
    if destination_host == "forms.gle" or destination_host == "docs.google.com":
        if destination_type == "form":
            return "destination_label_google_form"
        if destination_type == "document":
            return "destination_label_google_docs"
    if destination_host == "drive.google.com":
        return "destination_label_google_drive"
    return DESTINATION_LABEL_KEYS.get(destination_type or "", "destination_label_external")


def destination_hint_key(destination_type: str | None) -> str:
    return DESTINATION_HINT_KEYS.get(destination_type or "", "destination_hint_external")
