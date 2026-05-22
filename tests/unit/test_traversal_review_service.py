from app.db.models import Document, DocumentReference
from app.services.traversal_review_service import (
    ACTION_BLOCKED,
    ACTION_REVIEW_REQUIRED,
    ACTION_UNCERTAIN,
    RISK_BLOCKED,
    RISK_HIGH,
    STATUS_PENDING_REVIEW,
    build_review_snapshot,
)


def make_reference(*, source_type: str, raw_reference: str, final_url: str | None = None, destination_type: str | None = None):
    return DocumentReference(
        document_id=1,
        page_number=1,
        source_type=source_type,
        reference_class="qr" if source_type == "qr" else "url",
        raw_reference=raw_reference,
        final_url=final_url,
        resolution_status="resolved" if final_url or raw_reference.startswith(("http://", "https://")) else "pending",
        destination_type=destination_type,
        destination_host=None,
        requires_user_action=None,
        http_status=200 if final_url or raw_reference.startswith(("http://", "https://")) else None,
        resolution_error_type=None,
        resolution_error_detail=None,
    )


def make_document(*, references: list[DocumentReference], processing_error_type: str | None = None) -> Document:
    document = Document(
        id=1,
        original_file_name="sample.pdf",
        content_hash="hash",
        file_size_bytes=100,
        processing_status="processed",
        extraction_version=1,
        retention_mode="retain_failed_only",
        source_file_present=False,
        retry_requires_reupload=False,
        last_ingestion_used_cached_result=False,
        processing_error_type=processing_error_type,
    )
    document.references = references
    for reference in references:
        reference.document = document
    return document


def test_scoring_keeps_clear_text_http_candidate_review_required():
    reference = make_reference(
        source_type="text",
        raw_reference="https://moph.go.th/notice",
        final_url="https://moph.go.th/notice",
        destination_type="government",
    )
    document = make_document(references=[reference])

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.confidence_score == 75
    assert snapshot.risk_level == "MEDIUM"
    assert snapshot.recommended_action == ACTION_REVIEW_REQUIRED
    assert snapshot.review_status == STATUS_PENDING_REVIEW


def test_shortlink_becomes_review_required():
    reference = make_reference(
        source_type="qr",
        raw_reference="https://bit.ly/demo",
        final_url="https://bit.ly/demo",
        destination_type="redirect",
    )
    document = make_document(references=[reference])

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.risk_level == RISK_HIGH
    assert snapshot.recommended_action == ACTION_REVIEW_REQUIRED
    assert snapshot.review_status == STATUS_PENDING_REVIEW


def test_unsupported_scheme_is_blocked():
    reference = make_reference(source_type="qr", raw_reference="mailto:test@example.com")
    document = make_document(references=[reference])

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.risk_level == RISK_BLOCKED
    assert snapshot.recommended_action == ACTION_BLOCKED


def test_private_ip_is_blocked():
    reference = make_reference(source_type="text", raw_reference="http://10.10.10.10/report")
    document = make_document(references=[reference])

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.risk_level == RISK_BLOCKED
    assert snapshot.recommended_action == ACTION_BLOCKED


def test_loopback_is_blocked():
    reference = make_reference(source_type="text", raw_reference="http://127.0.0.1/admin")
    document = make_document(references=[reference])

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.risk_level == RISK_BLOCKED
    assert snapshot.recommended_action == ACTION_BLOCKED


def test_link_local_is_blocked():
    reference = make_reference(source_type="text", raw_reference="http://169.254.1.10/scan")
    document = make_document(references=[reference])

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.risk_level == RISK_BLOCKED
    assert snapshot.recommended_action == ACTION_BLOCKED


def test_broken_qr_becomes_uncertain():
    reference = make_reference(source_type="qr", raw_reference="DOC:6176")
    document = make_document(references=[reference])

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.recommended_action in {ACTION_BLOCKED, ACTION_UNCERTAIN, ACTION_REVIEW_REQUIRED}
    assert snapshot.review_reason


def test_multiple_candidates_require_review():
    first = make_reference(
        source_type="text",
        raw_reference="https://example.com/a",
        final_url="https://example.com/a",
        destination_type="external",
    )
    second = make_reference(
        source_type="qr",
        raw_reference="https://example.com/b",
        final_url="https://example.com/b",
        destination_type="external",
    )
    document = make_document(references=[first, second])

    snapshot = build_review_snapshot(first, document)

    assert snapshot.recommended_action == ACTION_REVIEW_REQUIRED


def test_ocr_http_candidate_requires_review():
    reference = make_reference(
        source_type="ocr",
        raw_reference="https://example.com/form",
        final_url="https://example.com/form",
        destination_type="external",
    )
    document = make_document(references=[reference])

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.recommended_action == ACTION_REVIEW_REQUIRED


def test_invalid_pdf_document_is_blocked():
    reference = make_reference(source_type="text", raw_reference="https://example.com/file")
    document = make_document(references=[reference], processing_error_type="INVALID_PDF")

    snapshot = build_review_snapshot(reference, document)

    assert snapshot.risk_level == RISK_BLOCKED
    assert snapshot.recommended_action == ACTION_BLOCKED
