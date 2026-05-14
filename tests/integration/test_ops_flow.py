from sqlalchemy import text


def _seed_ops_documents(engine, *, missing_path: str):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (
                    id, batch_run_id, original_file_name, content_hash, file_size_bytes,
                    processing_status, lifecycle_state, extraction_version, retention_mode,
                    source_file_present, retry_requires_reupload, last_ingestion_used_cached_result,
                    storage_key, last_source_path
                )
                VALUES
                    (10, NULL, 'missing.pdf', 'hash-missing', 100, 'failed', 'retained', 1, 'retain_failed_only', 1, 0, 0, 'sha256/ab/cd/missing.pdf', :missing_path),
                    (11, NULL, 'resolved.pdf', 'hash-resolved', 100, 'processed', 'resolved', 1, 'retain_failed_only', 0, 1, 0, NULL, NULL)
                """
            ),
            {"missing_path": missing_path},
        )
        connection.execute(
            text(
                """
                INSERT INTO document_lifecycle_events (
                    id, document_id, event_type, from_state, to_state, occurred_at,
                    actor_source, correlation_id, operation_id, batch_run_id, metadata_json,
                    error_type, error_detail
                )
                VALUES
                    (100, 11, 'DOCUMENT_UPLOADED', NULL, 'uploaded', '2026-05-14 09:00:00', 'batch_processor', 'doc:11', 'op:11', NULL, '{}', NULL, NULL),
                    (101, 11, 'DOCUMENT_RESOLUTION_COMPLETED', 'uploaded', 'resolved', '2026-05-14 09:10:00', 'batch_processor', 'doc:11', 'op:12', NULL, '{}', NULL, NULL),
                    (102, 10, 'DOCUMENT_RETAINED', 'failed', 'retained', '2026-05-14 09:20:00', 'retention_service', 'doc:10', 'op:13', NULL, '{}', NULL, NULL)
                """
            )
        )


def test_ops_endpoints_return_json_and_remain_read_only(client):
    missing_path = str(client.app.state.settings.failed_retained_path / "missing-source.pdf")
    _seed_ops_documents(client.app.state.postgres_engine, missing_path=missing_path)

    with client.app.state.postgres_engine.begin() as connection:
        before_counts = connection.execute(
            text("SELECT COUNT(*) AS documents, COALESCE(MAX(id), 0) AS max_id FROM documents")
        ).mappings().one()

    runtime_response = client.get("/ops/runtime")
    orphan_response = client.get("/ops/storage/orphans")
    consistency_response = client.get("/ops/lifecycle/consistency-summary")
    page_response = client.get("/ops")

    assert runtime_response.status_code == 200
    assert orphan_response.status_code == 200
    assert consistency_response.status_code == 200
    assert page_response.status_code == 200

    runtime_payload = runtime_response.json()
    orphan_payload = orphan_response.json()
    consistency_payload = consistency_response.json()

    assert runtime_payload["active_database_backend"] == "sqlite"
    assert "password" not in runtime_payload["configured_database_target"]
    assert orphan_payload["missing_referenced_artifact_count"] >= 1
    assert consistency_payload["total_documents"] == 2
    assert "ภาพรวมการปฏิบัติการ" in page_response.text

    with client.app.state.postgres_engine.begin() as connection:
        after_counts = connection.execute(
            text("SELECT COUNT(*) AS documents, COALESCE(MAX(id), 0) AS max_id FROM documents")
        ).mappings().one()

    assert before_counts["documents"] == after_counts["documents"]
    assert before_counts["max_id"] == after_counts["max_id"]
