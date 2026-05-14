from __future__ import annotations

from app.db.models import Document


def apply_lifecycle_projection(document: Document, to_state: str) -> Document:
    document.lifecycle_state = to_state
    return document

