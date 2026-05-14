from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ops.orphan_detection import build_orphan_detection_summary


def test_orphan_detection_finds_missing_and_unreferenced_artifacts(client):
    storage_root = client.app.state.settings.storage_root_path
    referenced_path = storage_root / "sha256" / "aa" / "bb" / "present.pdf"
    referenced_path.parent.mkdir(parents=True, exist_ok=True)
    referenced_path.write_bytes(b"retained source")

    unreferenced_path = storage_root / "sha256" / "ff" / "ee" / "orphan.pdf"
    unreferenced_path.parent.mkdir(parents=True, exist_ok=True)
    unreferenced_path.write_bytes(b"orphan")

    cleaned_legacy_path = client.app.state.settings.failed_retained_path / "cleaned-still-present.pdf"
    cleaned_legacy_path.write_bytes(b"legacy")

    with Session(client.app.state.database_engine) as session:
        session.execute(
            text(
                """
                INSERT INTO documents (
                    id, batch_run_id, original_file_name, content_hash, file_size_bytes,
                    processing_status, lifecycle_state, extraction_version, retention_mode,
                    source_file_present, retry_requires_reupload, last_ingestion_used_cached_result,
                    storage_key, last_source_path, moved_to_path
                )
                VALUES
                    (1, NULL, 'missing.pdf', 'hash-missing', 100, 'failed', 'retained', 1, 'retain_failed_only', 1, 0, 0, 'sha256/00/11/missing.pdf', NULL, NULL),
                    (2, NULL, 'cleaned.pdf', 'hash-cleaned', 100, 'failed', 'cleaned', 1, 'retain_failed_only', 1, 0, 0, NULL, :cleaned_legacy_path, NULL),
                    (3, NULL, 'untracked.pdf', 'hash-untracked', 100, 'failed', 'retained', 1, 'retain_failed_only', 1, 0, 0, NULL, NULL, NULL),
                    (4, NULL, 'present.pdf', 'hash-present', 100, 'failed', 'retained', 1, 'retain_failed_only', 1, 0, 0, 'sha256/aa/bb/present.pdf', NULL, NULL)
                """
            ),
            {"cleaned_legacy_path": str(cleaned_legacy_path)},
        )
        session.commit()

    with Session(client.app.state.database_engine) as session:
        summary = build_orphan_detection_summary(session, client.app.state.settings, sample_limit=10)

    payload = summary.to_dict()
    assert payload["missing_referenced_artifact_count"] == 1
    assert payload["retained_missing_source_count"] == 2
    assert payload["cleaned_source_still_present_count"] == 1
    assert payload["source_expected_without_reference_count"] == 1
    assert payload["unreferenced_storage_file_count"] == 1
    assert {sample["code"] for sample in payload["samples"]} >= {
        "missing_referenced_artifact",
        "retained_missing_source",
        "cleaned_source_still_present",
        "source_expected_without_reference",
        "unreferenced_storage_file",
    }
