from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Callable

import fitz

from app.batch.error_types import (
    NO_REFERENCE_FOUND,
    QR_EXTRACTION_FAIL,
    TEXT_EXTRACTION_FAIL,
)
from app.batch.ocr import extract_text_with_ocr_if_needed
from app.batch.qr_debug import save_debug_image, save_debug_records, should_persist_debug_image
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


def _crop_region(image, *, x0: int, y0: int, x1: int, y1: int):
    height, width = image.shape[:2]
    left = max(0, min(x0, width))
    top = max(0, min(y0, height))
    right = max(left + 1, min(x1, width))
    bottom = max(top + 1, min(y1, height))
    return image[top:bottom, left:right], {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }


def _build_qr_attempts(image, grayscale, thresholded):
    import cv2

    height, width = grayscale.shape[:2]
    bottom_start = int(height * 0.55)
    third_width = max(width // 3, 1)
    adaptive_full = cv2.adaptiveThreshold(
        grayscale,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        35,
        11,
    )
    adaptive_low_contrast = cv2.adaptiveThreshold(
        grayscale,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY,
        31,
        7,
    )

    def build_attempt(zone: str, strategy_name: str, variant_name: str, variant_image, crop_bounds: dict):
        if not variant_image.size:
            return None
        return {
            "zone": zone,
            "strategy_name": strategy_name,
            "variant": variant_name,
            "image": variant_image,
            "crop_bounds": crop_bounds,
        }

    attempts = [
        build_attempt(
            "full_page",
            "full_page_original",
            "full_original",
            image,
            {"x": 0, "y": 0, "width": width, "height": height},
        ),
        build_attempt(
            "full_page",
            "full_page_grayscale",
            "grayscale",
            grayscale,
            {"x": 0, "y": 0, "width": width, "height": height},
        ),
        build_attempt(
            "full_page",
            "full_page_upscaled_6x",
            "upscaled_6x",
            cv2.resize(grayscale, None, fx=6, fy=6, interpolation=cv2.INTER_CUBIC),
            {"x": 0, "y": 0, "width": width, "height": height},
        ),
        build_attempt(
            "full_page",
            "full_page_threshold",
            "threshold",
            thresholded,
            {"x": 0, "y": 0, "width": width, "height": height},
        ),
        build_attempt(
            "full_page",
            "full_page_adaptive_threshold",
            "adaptive_threshold",
            adaptive_full,
            {"x": 0, "y": 0, "width": width, "height": height},
        ),
    ]

    region_specs = [
        ("bottom_crop", "bottom_crop", 0, bottom_start, width, height),
        ("bottom_left", "bottom_left", 0, bottom_start, third_width, height),
        ("bottom_center", "bottom_center", third_width, bottom_start, third_width * 2, height),
        ("bottom_right", "bottom_right", third_width * 2, bottom_start, width, height),
        ("left_band_40_65_percent", "left_band_40_65_percent", 0, int(height * 0.40), int(width * 0.35), int(height * 0.65)),
        ("left_band_45_70_percent", "left_band_45_70_percent", 0, int(height * 0.45), int(width * 0.35), int(height * 0.70)),
        ("left_lower_mid_35_percent", "left_lower_mid_35_percent", 0, int(height * 0.42), int(width * 0.40), int(height * 0.68)),
        ("bottom_left_deep", "bottom_left_deep", 0, int(height * 0.62), int(width * 0.32), height),
        ("lower_left_25_percent", "lower_left_25_percent", 0, int(height * 0.75), int(width * 0.25), height),
        ("lower_left_30_percent", "lower_left_30_percent", 0, int(height * 0.7), int(width * 0.3), height),
        ("qr_label_region", "qr_label_region", 0, int(height * 0.58), int(width * 0.42), height),
        ("qr_label_band", "qr_label_band", 0, int(height * 0.46), int(width * 0.42), int(height * 0.74)),
    ]

    source_variants = [
        ("grayscale", grayscale),
        ("threshold", thresholded),
        ("adaptive_threshold", adaptive_full),
        ("adaptive_threshold_low_contrast", adaptive_low_contrast),
    ]

    for zone, strategy_name, x0, y0, x1, y1 in region_specs:
        for variant_name, source_variant in source_variants:
            cropped, crop_bounds = _crop_region(source_variant, x0=x0, y0=y0, x1=x1, y1=y1)
            attempts.append(build_attempt(zone, strategy_name, variant_name, cropped, crop_bounds))
            if zone in {
                "left_band_40_65_percent",
                "left_band_45_70_percent",
                "left_lower_mid_35_percent",
                "bottom_left_deep",
                "lower_left_25_percent",
                "lower_left_30_percent",
                "qr_label_region",
                "qr_label_band",
            }:
                upscaled = cv2.resize(cropped, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                attempts.append(
                    build_attempt(
                        zone,
                        f"{strategy_name}_upscaled",
                        f"{variant_name}_upscaled_3x",
                        upscaled,
                        crop_bounds,
                    )
                )
                if variant_name in {"grayscale", "adaptive_threshold", "adaptive_threshold_low_contrast"}:
                    upscaled_4x = cv2.resize(cropped, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
                    attempts.append(
                        build_attempt(
                            zone,
                            f"{strategy_name}_upscaled_4x",
                            f"{variant_name}_upscaled_4x",
                            upscaled_4x,
                            crop_bounds,
                        )
                    )

    return [attempt for attempt in attempts if attempt is not None]


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
    attempts = _build_qr_attempts(image, grayscale, thresholded)
    detector = cv2.QRCodeDetector()
    decoded_values: list[str] = []
    debug_enabled = bool(settings is not None and getattr(settings, "qr_debug_export", False))

    for attempt in attempts:
        variant_values = _decode_with_opencv(detector, attempt["image"])
        decoded_values.extend(variant_values)
        normalized_values = _dedupe_qr_values(variant_values)

        if normalized_values or debug_enabled:
            logger.info(
                "[QR_DETECT_ATTEMPT] page=%s strategy=%s zone=%s variant=%s success=%s values=%s crop=%s",
                page_number,
                attempt["strategy_name"],
                attempt["zone"],
                attempt["variant"],
                bool(normalized_values),
                len(normalized_values),
                attempt["crop_bounds"],
            )

        if debug_records is not None and debug_enabled and document_id is not None and page_number is not None:
            meta = {
                "document_id": document_id,
                "page": page_number,
                "zone": attempt["zone"],
                "variant": attempt["variant"],
                "strategy_name": attempt["strategy_name"],
                "crop_bounds": attempt["crop_bounds"],
                "success": bool(normalized_values),
            }
            debug_path = save_debug_image(attempt["image"], meta, settings) if should_persist_debug_image(meta) else None
            debug_records.append(
                {
                    "page": page_number,
                    "zone": attempt["zone"],
                    "variant": attempt["variant"],
                    "strategy_name": attempt["strategy_name"],
                    "crop_bounds": attempt["crop_bounds"],
                    "success": bool(normalized_values),
                    "decoded_value": " | ".join(normalized_values),
                    "decode_status": "success" if normalized_values else "failed",
                    "image_path": debug_path,
                }
            )

    unique_values = _dedupe_qr_values(decoded_values)

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
