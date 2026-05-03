from __future__ import annotations

import re
import inspect
from dataclasses import dataclass
from typing import Callable

import fitz

from app.batch.error_types import (
    NO_REFERENCE_FOUND,
    QR_EXTRACTION_FAIL,
    TEXT_EXTRACTION_FAIL,
)
from app.batch.ocr import extract_text_with_ocr_if_needed
from app.batch.qr_debug import save_debug_image, save_debug_records
from app.logging_config import get_logger


logger = get_logger(__name__)

URL_PATTERN = re.compile(r"(?i)\bhttps?://[^\s<>\"]+")
TRAILING_PUNCTUATION = ".,;:!?)]}>\"'"


@dataclass(frozen=True)
class ExtractedReference:
    page_number: int
    source_type: str
    reference_class: str
    raw_reference: str


@dataclass(frozen=True)
class ExtractionIssue:
    page_number: int | None
    step_name: str
    error_type: str
    message: str


def normalize_reference(raw_reference: str) -> str:
    return raw_reference.strip().strip(TRAILING_PUNCTUATION)


def extract_urls_from_text(page_text: str, page_number: int, *, source_type: str = "text") -> list[ExtractedReference]:
    references: list[ExtractedReference] = []
    seen: set[tuple[int, str, str, str]] = set()

    for match in URL_PATTERN.finditer(page_text):
        normalized = normalize_reference(match.group(0))
        if not normalized:
            continue

        reference = ExtractedReference(
            page_number=page_number,
            source_type=source_type,
            reference_class="url",
            raw_reference=normalized,
        )
        dedupe_key = (
            reference.page_number,
            reference.source_type,
            reference.raw_reference,
            reference.reference_class,
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        references.append(reference)

    return references


def render_page_to_rgb_array(page: fitz.Page, *, scale: float = 3.0):
    import numpy as np

    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    channels = 3 if pixmap.n >= 3 else 1
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, channels)
    if channels == 1:
        image = np.repeat(image, 3, axis=2)
    return image


def _decode_with_opencv(detector, variant) -> list[str]:
    decoded_values: list[str] = []
    try:
        found, values, _, _ = detector.detectAndDecodeMulti(variant)
    except Exception:
        found, values = False, ()

    if found and values:
        decoded_values.extend(value for value in values if value)

    try:
        single_value, _, _ = detector.detectAndDecode(variant)
    except Exception:
        single_value = ""
    if single_value:
        decoded_values.append(single_value)

    return decoded_values


def _dedupe_qr_values(decoded_values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in decoded_values:
        normalized = normalize_reference(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_values.append(normalized)
    return unique_values


def _build_debug_attempt_variants(image, grayscale, thresholded):
    import cv2

    height, width = grayscale.shape[:2]
    bottom_start = int(height * 0.55)
    bottom_crop = grayscale[bottom_start:height, :]
    third_width = max(width // 3, 1)

    variants = [
        ("full_page", "full_original", image),
        ("full_page", "grayscale", grayscale),
        ("full_page", "upscaled_6x", cv2.resize(grayscale, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC)),
        ("full_page", "threshold", thresholded),
        (
            "full_page",
            "adaptive_threshold",
            cv2.adaptiveThreshold(grayscale, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 11),
        ),
        ("bottom_crop", "grayscale", bottom_crop),
        ("bottom_left", "grayscale", bottom_crop[:, :third_width]),
        ("bottom_center", "grayscale", bottom_crop[:, third_width : third_width * 2]),
        ("bottom_right", "grayscale", bottom_crop[:, third_width * 2 :]),
    ]
    return [(zone, variant_name, variant) for zone, variant_name, variant in variants if variant.size]


def _decode_with_pyzbar(image) -> list[str]:
    try:
        from pyzbar.pyzbar import decode
    except Exception:
        logger.info("[QR_FALLBACK_UNAVAILABLE] decoder=pyzbar reason=import_failed")
        return []

    try:
        decoded = decode(image)
    except Exception as exc:
        logger.info("[QR_FALLBACK_UNAVAILABLE] decoder=pyzbar reason=%s", exc)
        return []

    values: list[str] = []
    for item in decoded:
        try:
            values.append(item.data.decode("utf-8"))
        except Exception:
            values.append(item.data.decode("utf-8", errors="ignore"))
    return values


def detect_qr_values_from_page(
    page: fitz.Page,
    *,
    settings=None,
    document_id: int | None = None,
    page_number: int | None = None,
    debug_records: list[dict] | None = None,
) -> list[str]:
    import cv2

    image = render_page_to_rgb_array(page)
    grayscale = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, thresholded = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants = [
        ("full_original", image),
        ("grayscale", grayscale),
        ("threshold", thresholded),
    ]

    detector = cv2.QRCodeDetector()
    decoded_values: list[str] = []
    debug_enabled = bool(settings is not None and getattr(settings, "qr_debug_export", False))

    for variant_name, variant in variants:
        variant_values = _decode_with_opencv(detector, variant)
        decoded_values.extend(variant_values)

        if debug_records is not None and debug_enabled and document_id is not None and page_number is not None:
            normalized_values = _dedupe_qr_values(variant_values)
            meta = {
                "document_id": document_id,
                "page": page_number,
                "zone": "full_page",
                "variant": variant_name,
            }
            debug_path = save_debug_image(variant, meta, settings)
            debug_records.append(
                {
                    "page": page_number,
                    "zone": "full_page",
                    "variant": variant_name,
                    "success": bool(normalized_values),
                    "decoded_value": " | ".join(normalized_values),
                    "image_path": debug_path,
                }
            )

    unique_values = _dedupe_qr_values(decoded_values)

    if debug_records is not None and debug_enabled and document_id is not None and page_number is not None:
        output_variant_keys = {("full_page", variant_name) for variant_name, _ in variants}
        for zone, variant_name, variant in _build_debug_attempt_variants(image, grayscale, thresholded):
            if (zone, variant_name) in output_variant_keys:
                continue
            variant_values = _decode_with_opencv(detector, variant)
            normalized_values = _dedupe_qr_values(variant_values)
            meta = {
                "document_id": document_id,
                "page": page_number,
                "zone": zone,
                "variant": variant_name,
            }
            debug_path = save_debug_image(variant, meta, settings)
            debug_records.append(
                {
                    "page": page_number,
                    "zone": zone,
                    "variant": variant_name,
                    "success": bool(normalized_values),
                    "decoded_value": " | ".join(normalized_values),
                    "image_path": debug_path,
                }
            )

    fallback_decoder = getattr(settings, "qr_fallback_decoder", "none") if settings is not None else "none"
    if not unique_values and fallback_decoder == "pyzbar":
        logger.info("[QR_FALLBACK_START] decoder=pyzbar page=%s", page_number)
        fallback_values = _dedupe_qr_values(_decode_with_pyzbar(image))
        if fallback_values:
            logger.info("[QR_FALLBACK_SUCCESS] decoder=pyzbar page=%s values=%s", page_number, len(fallback_values))
            unique_values.extend(fallback_values)

    return unique_values


def _call_qr_detector(
    detector: Callable,
    page: fitz.Page,
    *,
    settings,
    document_id: int | None,
    page_number: int,
    debug_records: list[dict],
) -> list[str]:
    signature = inspect.signature(detector)
    kwargs = {}
    if "settings" in signature.parameters:
        kwargs["settings"] = settings
    if "document_id" in signature.parameters:
        kwargs["document_id"] = document_id
    if "page_number" in signature.parameters:
        kwargs["page_number"] = page_number
    if "debug_records" in signature.parameters:
        kwargs["debug_records"] = debug_records
    return detector(page, **kwargs)


def extract_references_from_pdf(
    file_path,
    *,
    qr_detector: Callable[[fitz.Page], list[str]] | None = None,
    settings=None,
    document_id: int | None = None,
) -> tuple[list[ExtractedReference], list[ExtractionIssue], int]:
    references: list[ExtractedReference] = []
    issues: list[ExtractionIssue] = []
    seen: set[tuple[int, str, str, str]] = set()
    total_text_chars = 0
    qr_debug_records: list[dict] = []

    detector = qr_detector or detect_qr_values_from_page
    logger.info("[EXTRACT_START] file=%s", file_path)

    if qr_detector is None:
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
        except Exception as exc:
            qr_detection_available = False
            qr_error = str(exc)
        else:
            qr_detection_available = True
            qr_error = ""
    else:
        qr_detection_available = True
        qr_error = ""

    with fitz.open(file_path) as document:
        page_count = document.page_count
        for page_index in range(page_count):
            page_number = page_index + 1
            page = document.load_page(page_index)

            try:
                page_text = page.get_text()
            except Exception as exc:
                page_text = ""
                issues.append(
                    ExtractionIssue(page_number, "reference_text_extraction", TEXT_EXTRACTION_FAIL, str(exc))
                )

            total_text_chars += len(page_text)
            text_references = extract_urls_from_text(page_text, page_number, source_type="text")
            for reference in text_references:
                dedupe_key = (
                    reference.page_number,
                    reference.source_type,
                    reference.raw_reference,
                    reference.reference_class,
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                references.append(reference)

            if settings is not None:
                ocr_result = extract_text_with_ocr_if_needed(page, page_number, page_text, settings)
                if ocr_result["used_ocr"] and ocr_result["error_type"]:
                    issues.append(
                        ExtractionIssue(
                            page_number,
                            "reference_ocr",
                            ocr_result["error_type"],
                            ocr_result["error"] or "",
                        )
                    )
                if ocr_result["used_ocr"] and not ocr_result["error"]:
                    ocr_references = extract_urls_from_text(
                        ocr_result["text"],
                        page_number,
                        source_type="ocr",
                    )
                    for reference in ocr_references:
                        dedupe_key = (
                            reference.page_number,
                            reference.source_type,
                            reference.raw_reference,
                            reference.reference_class,
                        )
                        if dedupe_key in seen:
                            continue
                        seen.add(dedupe_key)
                        references.append(reference)

            if qr_detection_available:
                try:
                    qr_values = _call_qr_detector(
                        detector,
                        page,
                        settings=settings,
                        document_id=document_id,
                        page_number=page_number,
                        debug_records=qr_debug_records,
                    )
                except Exception as exc:
                    issues.append(ExtractionIssue(page_number, "reference_qr_extraction", QR_EXTRACTION_FAIL, str(exc)))
                    qr_values = []
            else:
                issues.append(ExtractionIssue(None, "reference_qr_extraction", QR_EXTRACTION_FAIL, qr_error))
                qr_values = []

            for raw_value in qr_values:
                normalized = normalize_reference(raw_value)
                if not normalized:
                    continue
                reference = ExtractedReference(
                    page_number=page_number,
                    source_type="qr",
                    reference_class="qr",
                    raw_reference=normalized,
                )
                dedupe_key = (
                    reference.page_number,
                    reference.source_type,
                    reference.raw_reference,
                    reference.reference_class,
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                references.append(reference)

        if total_text_chars == 0:
            logger.info("[IMAGE_ONLY_PDF] file=%s pages=%s", file_path, page_count)

    if not references:
        issues.append(ExtractionIssue(None, "reference_summary", NO_REFERENCE_FOUND, "No references found"))

    save_debug_records(document_id, qr_debug_records, settings)
    logger.info("[EXTRACT_DONE] file=%s total_refs=%s", file_path, len(references))
    return references, issues, page_count
