from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _debug_enabled(settings) -> bool:
    return bool(settings is not None and getattr(settings, "qr_debug_export", False))


def _debug_base_dir(settings) -> Path:
    if hasattr(settings, "qr_debug_path"):
        return settings.qr_debug_path
    return Path(getattr(settings, "qr_debug_dir", "data/debug/qr")).resolve()


def _safe_part(value: Any) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(value))
    return safe.strip("_") or "unknown"


def save_debug_image(img, meta: dict, settings) -> str | None:
    if not _debug_enabled(settings):
        return None

    import cv2

    base_dir = _debug_base_dir(settings)
    base_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        f"doc_{_safe_part(meta['document_id'])}_"
        f"page_{_safe_part(meta['page'])}_"
        f"{_safe_part(meta['zone'])}_"
        f"{_safe_part(meta['variant'])}.png"
    )
    path = base_dir / filename
    cv2.imwrite(str(path), img)
    return str(path)


def should_persist_debug_image(meta: dict) -> bool:
    if meta.get("success"):
        return True
    zone = meta.get("zone")
    return zone in {
        "full_page",
        "bottom_left_deep",
        "lower_left_25_percent",
        "lower_left_30_percent",
        "qr_label_region",
    }


def save_debug_records(document_id: int | None, records: list[dict], settings) -> str | None:
    if not _debug_enabled(settings) or document_id is None:
        return None

    base_dir = _debug_base_dir(settings)
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"doc_{document_id}.json"
    payload = {
        "document_id": document_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "attempts": records,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def load_debug_payload(document_id: int, settings) -> dict:
    base_dir = _debug_base_dir(settings)
    path = base_dir / f"doc_{document_id}.json"
    if not path.exists():
        return {"document_id": document_id, "pages": []}

    payload = json.loads(path.read_text(encoding="utf-8"))
    pages: dict[int, list[dict]] = {}
    for attempt in payload.get("attempts", []):
        page_number = int(attempt.get("page") or 0)
        image_path = attempt.get("image_path")
        if image_path:
            image_name = Path(image_path).name
            attempt["image_url"] = f"/debug/qr/{image_name}"
        pages.setdefault(page_number, []).append(attempt)

    return {
        "document_id": payload.get("document_id", document_id),
        "generated_at": payload.get("generated_at"),
        "pages": [
            {
                "page": page_number,
                "attempts": attempts,
            }
            for page_number, attempts in sorted(pages.items())
        ],
    }
