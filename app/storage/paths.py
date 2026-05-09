from __future__ import annotations

import re
import unicodedata
from pathlib import Path


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MULTISPACE_RE = re.compile(r"\s+")
DEFAULT_INTERNAL_FILENAME = "file"
MAX_FILENAME_BYTES = 120


def normalize_filename(filename: str) -> str:
    raw = unicodedata.normalize("NFC", filename or "").strip()
    if not raw:
        return DEFAULT_INTERNAL_FILENAME

    safe = INVALID_FILENAME_CHARS.sub("_", raw)
    safe = safe.replace("\u2028", "_").replace("\u2029", "_")
    safe = MULTISPACE_RE.sub(" ", safe)
    safe = safe.strip(" .")
    if not safe:
        return DEFAULT_INTERNAL_FILENAME
    return safe


def truncate_safe_filename(filename: str, *, max_bytes: int = MAX_FILENAME_BYTES) -> str:
    normalized = normalize_filename(filename)
    suffix = Path(normalized).suffix
    stem = Path(normalized).stem or DEFAULT_INTERNAL_FILENAME

    if len(normalized.encode("utf-8")) <= max_bytes:
        return normalized

    suffix_bytes = len(suffix.encode("utf-8"))
    allowed_stem_bytes = max(max_bytes - suffix_bytes, 16)
    encoded_parts: list[str] = []
    used_bytes = 0
    for char in stem:
        char_bytes = len(char.encode("utf-8"))
        if used_bytes + char_bytes > allowed_stem_bytes:
            break
        encoded_parts.append(char)
        used_bytes += char_bytes

    truncated_stem = "".join(encoded_parts).rstrip(" .-_") or DEFAULT_INTERNAL_FILENAME
    truncated = f"{truncated_stem}{suffix}"
    if len(truncated.encode("utf-8")) <= max_bytes:
        return truncated

    while truncated_stem and len(f"{truncated_stem}{suffix}".encode("utf-8")) > max_bytes:
        truncated_stem = truncated_stem[:-1].rstrip(" .-_")
    return f"{truncated_stem or DEFAULT_INTERNAL_FILENAME}{suffix}"


def build_storage_key(sha256: str, *, suffix: str = ".pdf") -> str:
    normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}" if suffix else ""
    return f"sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}{normalized_suffix}"
