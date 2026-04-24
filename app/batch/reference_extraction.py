from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

import fitz

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
    message: str


def normalize_reference(raw_reference: str) -> str:
    return raw_reference.strip().strip(TRAILING_PUNCTUATION)


def extract_urls_from_text(page_text: str, page_number: int) -> list[ExtractedReference]:
    references: list[ExtractedReference] = []
    seen: set[tuple[int, str, str, str]] = set()

    for match in URL_PATTERN.finditer(page_text):
        normalized = normalize_reference(match.group(0))
        if not normalized:
            continue

        reference = ExtractedReference(
            page_number=page_number,
            source_type="text",
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


def render_page_to_rgb_array(page: fitz.Page):
    import numpy as np

    pixmap = page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False)
    channels = 3 if pixmap.n >= 3 else 1
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, channels)
    if channels == 1:
        image = np.repeat(image, 3, axis=2)
    return image


def extract_text_with_ocr_if_needed(file_path) -> str:
    logger.info("[OCR_STUB] file=%s status=not_implemented", file_path)
    return ""


def detect_qr_values_from_page(page: fitz.Page) -> list[str]:
    import cv2

    image = render_page_to_rgb_array(page)
    grayscale = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, thresholded = cv2.threshold(grayscale, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants = [image, grayscale, thresholded]

    detector = cv2.QRCodeDetector()
    decoded_values: list[str] = []

    for variant in variants:
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

    unique_values: list[str] = []
    seen: set[str] = set()
    for value in decoded_values:
        normalized = normalize_reference(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_values.append(normalized)

    return unique_values


def extract_references_from_pdf(
    file_path,
    *,
    qr_detector: Callable[[fitz.Page], list[str]] | None = None,
) -> tuple[list[ExtractedReference], list[ExtractionIssue], int]:
    references: list[ExtractedReference] = []
    issues: list[ExtractionIssue] = []
    seen: set[tuple[int, str, str, str]] = set()
    total_text_chars = 0

    detector = qr_detector or detect_qr_values_from_page
    logger.info("[EXTRACT_START] file=%s", file_path)

    if qr_detector is None:
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
        except Exception as exc:
            qr_detection_available = False
            qr_error = f"QR extraction unavailable: {exc}"
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

            try:
                page = document.load_page(page_index)
            except Exception as exc:
                issues.append(
                    ExtractionIssue(
                        page_number=page_number,
                        step_name="reference_page_load",
                        message=f"Page load failed: {exc}",
                    )
                )
                continue

            try:
                page_text = page.get_text()
            except Exception as exc:
                issues.append(
                    ExtractionIssue(
                        page_number=page_number,
                        step_name="reference_text_extraction",
                        message=f"Text extraction failed: {exc}",
                    )
                )
                page_text = ""

            text_references = extract_urls_from_text(page_text, page_number)
            total_text_chars += len(page_text)
            logger.info("[TEXT] file=%s page=%s chars=%s urls=%s", file_path, page_number, len(page_text), len(text_references))
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

            if not qr_detection_available:
                if page_number == 1:
                    issues.append(
                        ExtractionIssue(
                            page_number=None,
                            step_name="reference_qr_extraction",
                            message=qr_error,
                        )
                    )
                    logger.warning("[QR] file=%s found=0 reason=%s", file_path, qr_error)
                continue

            try:
                qr_values = detector(page)
            except Exception as exc:
                issues.append(
                    ExtractionIssue(
                        page_number=page_number,
                        step_name="reference_qr_extraction",
                        message=f"QR extraction failed: {exc}",
                    )
                )
                logger.exception("[QR] file=%s page=%s found=0 error=%s", file_path, page_number, exc)
                continue

            logger.info("[QR] file=%s page=%s found=%s", file_path, page_number, len(qr_values))
            for raw_value in qr_values:
                normalized = normalize_reference(raw_value)
                if not normalized:
                    continue
                reference = ExtractedReference(
                    page_number=page_number,
                    source_type="image",
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
            _ = extract_text_with_ocr_if_needed(file_path)

    logger.info("[EXTRACT_DONE] file=%s total_refs=%s", file_path, len(references))
    return references, issues, page_count
