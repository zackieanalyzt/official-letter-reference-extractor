from app.traversal.classifier import classify_reference_url
from app.traversal.schemas import (
    TARGET_HTML_PAGE,
    TARGET_IMAGE_URL,
    TARGET_KNOWN_SHORT_URL,
    TARGET_MALFORMED_URL,
    TARGET_PDF_URL,
    TARGET_UNKNOWN,
    TARGET_UNSUPPORTED_SCHEME,
)


def test_classifies_pdf_url():
    result = classify_reference_url("https://example.go.th/files/letter.pdf")

    assert result.target_type == TARGET_PDF_URL
    assert result.host == "example.go.th"


def test_classifies_known_short_url():
    result = classify_reference_url("https://bit.ly/abc123")

    assert result.target_type == TARGET_KNOWN_SHORT_URL


def test_classifies_html_image_malformed_and_unsupported_scheme():
    assert classify_reference_url("https://example.com/page.html").target_type == TARGET_HTML_PAGE
    assert classify_reference_url("https://example.com/image.png").target_type == TARGET_IMAGE_URL
    assert classify_reference_url("not a url").target_type == TARGET_MALFORMED_URL
    assert classify_reference_url("ftp://example.com/file.pdf").target_type == TARGET_UNSUPPORTED_SCHEME


def test_classifies_unknown_http_target_without_fetching():
    result = classify_reference_url("https://example.com/download/123")

    assert result.target_type == TARGET_UNKNOWN
