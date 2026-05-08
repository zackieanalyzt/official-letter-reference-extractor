import json
import sys
import types
from types import SimpleNamespace

import numpy as np
import fitz
from sqlalchemy import text

from app.batch.qr_debug import load_debug_payload, save_debug_image, save_debug_records
from app.batch.reference_extraction import detect_qr_values_from_page


def test_qr_debug_image_export_is_disabled_by_default(tmp_path):
    settings = SimpleNamespace(qr_debug_export=False, qr_debug_dir=str(tmp_path / "qr"))
    image = np.zeros((8, 8), dtype=np.uint8)

    result = save_debug_image(
        image,
        {"document_id": 1, "page": 1, "zone": "full_page", "variant": "thresholded"},
        settings,
    )

    assert result is None
    assert not (tmp_path / "qr").exists()


def test_qr_debug_records_group_by_page_when_enabled(tmp_path):
    settings = SimpleNamespace(qr_debug_export=True, qr_debug_dir=str(tmp_path / "qr"))
    image = np.zeros((8, 8), dtype=np.uint8)
    image_path = save_debug_image(
        image,
        {"document_id": 7, "page": 2, "zone": "full_page", "variant": "grayscale"},
        settings,
    )

    save_debug_records(
        7,
        [
            {
                "page": 2,
                "zone": "full_page",
                "variant": "grayscale",
                "success": True,
                "decoded_value": "https://example.com/qr",
                "image_path": image_path,
            }
        ],
        settings,
    )

    payload = load_debug_payload(7, settings)

    assert payload["document_id"] == 7
    assert payload["pages"][0]["page"] == 2
    assert payload["pages"][0]["attempts"][0]["success"] is True
    assert payload["pages"][0]["attempts"][0]["image_url"].endswith("doc_7_page_2_full_page_grayscale.png")


def test_qr_debug_capture_includes_real_world_variants(tmp_path):
    settings = SimpleNamespace(qr_debug_export=True, qr_debug_dir=str(tmp_path / "qr"), qr_fallback_decoder="none")
    records = []
    document = fitz.open()
    page = document.new_page()

    detect_qr_values_from_page(
        page,
        settings=settings,
        document_id=8,
        page_number=1,
        debug_records=records,
    )
    document.close()

    attempts = {(record["zone"], record["variant"]) for record in records}
    assert ("full_page", "full_original") in attempts
    assert ("full_page", "grayscale") in attempts
    assert ("full_page", "upscaled_6x") in attempts
    assert ("full_page", "threshold") in attempts
    assert ("full_page", "adaptive_threshold") in attempts
    assert ("bottom_crop", "grayscale") in attempts
    assert ("bottom_left", "grayscale") in attempts
    assert ("bottom_left_deep", "adaptive_threshold_upscaled_3x") in attempts
    assert ("lower_left_25_percent", "adaptive_threshold_low_contrast_upscaled_3x") in attempts
    assert ("lower_left_30_percent", "threshold_upscaled_3x") in attempts
    assert ("qr_label_region", "adaptive_threshold_upscaled_3x") in attempts
    assert "strategy_name" in records[0]
    assert "crop_bounds" in records[0]
    assert "decode_status" in records[0]
    assert list((tmp_path / "qr").glob("*.png"))


def test_lower_left_qr_strategy_contributes_decoded_value(monkeypatch):
    settings = SimpleNamespace(qr_debug_export=False, qr_fallback_decoder="none")
    fake_image = np.zeros((120, 120, 3), dtype=np.uint8)
    document = fitz.open()
    page = document.new_page()

    monkeypatch.setattr("app.batch.reference_extraction.render_page_to_rgb_array", lambda _page: fake_image)

    def fake_decode(_detector, variant):
        if variant.shape[:2] == (30, 30):
            return ["https://forms.gle/lower-left"]
        return []

    monkeypatch.setattr("app.batch.reference_extraction._decode_with_opencv", fake_decode)

    values = detect_qr_values_from_page(page, settings=settings, page_number=1)
    document.close()

    assert values == ["https://forms.gle/lower-left"]


def test_qr_pyzbar_fallback_is_optional_and_safe(monkeypatch):
    pyzbar_package = types.ModuleType("pyzbar")
    pyzbar_module = types.ModuleType("pyzbar.pyzbar")

    class Decoded:
        data = b"https://fallback.example/qr"

    pyzbar_module.decode = lambda _image: [Decoded()]
    monkeypatch.setitem(sys.modules, "pyzbar", pyzbar_package)
    monkeypatch.setitem(sys.modules, "pyzbar.pyzbar", pyzbar_module)

    settings = SimpleNamespace(qr_debug_export=False, qr_fallback_decoder="pyzbar")
    document = fitz.open()
    page = document.new_page()

    values = detect_qr_values_from_page(page, settings=settings)
    document.close()

    assert values == ["https://fallback.example/qr"]


def test_debug_document_api_returns_sidecar_payload(client):
    client.app.state.settings.qr_debug_path.mkdir(parents=True, exist_ok=True)
    with client.app.state.postgres_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (
                    id,
                    batch_run_id,
                    original_file_name,
                    content_hash,
                    file_size_bytes,
                    page_count,
                    document_number,
                    processing_status,
                    processing_error,
                    processing_error_type,
                    processing_error_detail,
                    processed_at,
                    moved_to_path,
                    extraction_version,
                    retention_mode,
                    source_file_present,
                    source_deleted_at,
                    last_source_path,
                    retry_requires_reupload,
                    last_ingestion_used_cached_result
                )
                VALUES
                    (12, NULL, 'qr-debug.pdf', 'hash-debug', 100, 2, NULL, 'processed', NULL, NULL, NULL, '2026-04-24 10:00:00', NULL, 1, 'retain_failed_only', 0, '2026-04-24 10:01:00', NULL, 1, 0)
                """
            )
        )

    debug_payload = {
        "document_id": 12,
        "generated_at": "2026-04-24T10:00:00+00:00",
        "attempts": [
            {
                "page": 2,
                "zone": "full_page",
                "variant": "thresholded",
                "success": True,
                "decoded_value": "https://example.com/qr",
                "image_path": str(client.app.state.settings.qr_debug_path / "doc_12_page_2_full_page_thresholded.png"),
            }
        ],
    }
    (client.app.state.settings.qr_debug_path / "doc_12.json").write_text(
        json.dumps(debug_payload),
        encoding="utf-8",
    )

    response = client.get("/debug/document/12?format=json")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == 12
    assert body["document"]["filename"] == "qr-debug.pdf"
    assert body["pages"][0]["attempts"][0]["decoded_value"] == "https://example.com/qr"


def test_debug_document_ui_renders_attempts(client):
    client.app.state.settings.qr_debug_path.mkdir(parents=True, exist_ok=True)
    with client.app.state.postgres_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (
                    id,
                    batch_run_id,
                    original_file_name,
                    content_hash,
                    file_size_bytes,
                    page_count,
                    document_number,
                    processing_status,
                    processing_error,
                    processing_error_type,
                    processing_error_detail,
                    processed_at,
                    moved_to_path,
                    extraction_version,
                    retention_mode,
                    source_file_present,
                    source_deleted_at,
                    last_source_path,
                    retry_requires_reupload,
                    last_ingestion_used_cached_result
                )
                VALUES
                    (13, NULL, 'qr-debug-ui.pdf', 'hash-debug-ui', 100, 1, NULL, 'processed', NULL, NULL, NULL, '2026-04-24 10:00:00', NULL, 1, 'retain_failed_only', 0, '2026-04-24 10:01:00', NULL, 1, 0)
                """
            )
        )

    (client.app.state.settings.qr_debug_path / "doc_13.json").write_text(
        json.dumps(
            {
                "document_id": 13,
                "attempts": [
                    {
                        "page": 1,
                        "zone": "full_page",
                        "variant": "rgb",
                        "success": False,
                        "decoded_value": "",
                        "image_path": None,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    response = client.get("/debug/document/13")

    assert response.status_code == 200
    assert "qr-debug-ui.pdf" in response.text
    assert "full_page" in response.text
