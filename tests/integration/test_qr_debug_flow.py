import json
from types import SimpleNamespace

import numpy as np
from sqlalchemy import text

from app.batch.qr_debug import load_debug_payload, save_debug_image, save_debug_records


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
                    moved_to_path
                )
                VALUES
                    (12, NULL, 'qr-debug.pdf', 'hash-debug', 100, 2, NULL, 'processed', NULL, NULL, NULL, '2026-04-24 10:00:00', '/processed/qr-debug.pdf')
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
                    moved_to_path
                )
                VALUES
                    (13, NULL, 'qr-debug-ui.pdf', 'hash-debug-ui', 100, 1, NULL, 'processed', NULL, NULL, NULL, '2026-04-24 10:00:00', '/processed/qr-debug-ui.pdf')
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
    assert "full_page | rgb" in response.text
