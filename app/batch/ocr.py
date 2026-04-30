from __future__ import annotations

from dataclasses import dataclass

import fitz
import pytesseract
from PIL import Image
from pytesseract import TesseractError

from app.batch.error_types import OCR_FAIL, OCR_NOT_AVAILABLE
from app.config import get_settings
from app.logging_config import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class OcrResult:
    used_ocr: bool
    text: str
    char_count: int
    engine: str
    error: str | None
    error_type: str | None


def is_ocr_enabled(settings=None) -> bool:
    settings = settings or get_settings()
    return bool(getattr(settings, "ocr_enabled", False))


def extract_text_with_ocr_if_needed(
    page: fitz.Page,
    page_number: int,
    existing_text: str,
    settings,
) -> dict:
    min_text_chars = getattr(settings, "ocr_min_text_chars", 0)
    engine = getattr(settings, "ocr_engine", "tesseract")

    if not is_ocr_enabled(settings):
        logger.info("[OCR_SKIPPED] page=%s reason=disabled engine=%s", page_number, engine)
        return OcrResult(False, existing_text, len(existing_text), engine, None, None).__dict__

    if len(existing_text.strip()) >= min_text_chars:
        logger.info("[OCR_SKIPPED] page=%s reason=text_threshold engine=%s", page_number, engine)
        return OcrResult(False, existing_text, len(existing_text), engine, None, None).__dict__

    logger.info("[OCR_START] page=%s engine=%s", page_number, engine)
    try:
        pytesseract.pytesseract.tesseract_cmd = engine

        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(settings.ocr_render_scale, settings.ocr_render_scale),
            alpha=False,
        )
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        text = pytesseract.image_to_string(
            image,
            lang=settings.ocr_language,
            config=f"--psm {settings.ocr_page_segmentation_mode}",
            timeout=settings.ocr_timeout_seconds,
        ).strip()
    except RuntimeError as exc:
        error_type = OCR_NOT_AVAILABLE if "tesseract" in str(exc).lower() else OCR_FAIL
        logger.warning("[OCR_FAIL] page=%s engine=%s error_type=%s error=%s", page_number, engine, error_type, exc)
        return OcrResult(True, existing_text, len(existing_text), engine, str(exc), error_type).__dict__
    except TesseractError as exc:
        error_message = str(exc)
        error_type = OCR_NOT_AVAILABLE if "language" in error_message.lower() else OCR_FAIL
        logger.warning("[OCR_FAIL] page=%s engine=%s error_type=%s error=%s", page_number, engine, error_type, error_message)
        return OcrResult(True, existing_text, len(existing_text), engine, error_message, error_type).__dict__
    except Exception as exc:
        logger.warning("[OCR_FAIL] page=%s engine=%s error_type=%s error=%s", page_number, engine, OCR_FAIL, exc)
        return OcrResult(True, existing_text, len(existing_text), engine, str(exc), OCR_FAIL).__dict__

    logger.info("[OCR_DONE] page=%s engine=%s char_count=%s", page_number, engine, len(text))
    return OcrResult(True, text, len(text), engine, None, None).__dict__
