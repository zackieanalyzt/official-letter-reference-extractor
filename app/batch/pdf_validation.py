from pathlib import Path

import fitz


def validate_pdf_readable(file_path: Path) -> None:
    with fitz.open(file_path) as document:
        _ = document.page_count
