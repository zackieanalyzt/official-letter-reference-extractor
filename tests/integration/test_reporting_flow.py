from sqlalchemy import text

from app.db.postgres import create_postgres_session_factory
from app.i18n.th import LABELS
from app.services.analytics_service import (
    get_dashboard_summary,
    get_domain_summary,
    normalize_domain,
)


def seed_reporting_rows(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO batch_runs (
                    id,
                    triggered_by,
                    started_at,
                    finished_at,
                    status,
                    total_files_seen,
                    total_files_processed,
                    duplicate_files_skipped,
                    failed_files,
                    total_references_found
                )
                VALUES
                    (901, 'public', '2026-05-01 09:00:00', '2026-05-01 09:05:00', 'completed_with_errors', 3, 2, 1, 1, 3)
                """
            )
        )
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
                    (901, 901, 'alpha-report.pdf', 'hash-report-a', 100, 2, NULL, 'processed', NULL, NULL, NULL, '2026-05-01 10:00:00', '/processed/alpha-report.pdf'),
                    (902, 901, 'beta-report.pdf', 'hash-report-b', 120, 1, NULL, 'failed', 'bad pdf', 'INVALID_PDF', 'broken file', '2026-05-02 11:00:00', '/error/beta-report.pdf')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO document_references (
                    id,
                    document_id,
                    page_number,
                    source_type,
                    reference_class,
                    raw_reference,
                    final_url,
                    resolution_status,
                    http_status,
                    resolution_error_type,
                    resolution_error_detail
                )
                VALUES
                    (901, 901, 1, 'text', 'url', 'https://Example.Go.Th/path?a=1', 'https://example.go.th/final', 'resolved', 200, NULL, NULL),
                    (902, 901, 2, 'qr', 'qr', 'https://example.go.th/qr', 'https://example.go.th/qr', 'failed', 404, 'URL_HTTP_ERROR', 'HTTP status 404'),
                    (903, 901, 2, 'ocr', 'url', 'https://sub.example.org/form', 'https://sub.example.org/form', 'resolved', 200, NULL, NULL)
                """
            )
        )


def test_domain_normalization():
    assert normalize_domain("https://example.go.th/path?a=1") == "example.go.th"
    assert normalize_domain("HTTP://WWW.Example.Go.Th/") == "example.go.th"
    assert normalize_domain("not a url") is None


def test_dashboard_summary_service_returns_expected_counts(client):
    seed_reporting_rows(client.app.state.postgres_engine)
    session_factory = create_postgres_session_factory(client.app.state.postgres_engine)
    with session_factory() as session:
        summary = get_dashboard_summary(session)

    assert summary["total_documents"] == 2
    assert summary["total_references"] == 3
    assert summary["processed_documents"] == 1
    assert summary["failed_documents"] == 1
    assert summary["duplicate_documents"] == 1
    assert summary["resolved_urls"] == 2
    assert summary["failed_urls"] == 1
    assert summary["qr_count"] == 1
    assert summary["text_count"] == 1
    assert summary["ocr_count"] == 1


def test_domain_summary_aggregation(client):
    seed_reporting_rows(client.app.state.postgres_engine)
    session_factory = create_postgres_session_factory(client.app.state.postgres_engine)
    with session_factory() as session:
        domains = get_domain_summary(session)

    example = next(row for row in domains if row.domain == "example.go.th")
    assert example.total_references == 2
    assert example.resolved_count == 1
    assert example.failed_count == 1
    assert example.text_count == 1
    assert example.qr_count == 1


def test_dashboard_and_quality_routes_return_200(client):
    seed_reporting_rows(client.app.state.postgres_engine)

    dashboard_response = client.get("/dashboard")
    quality_response = client.get("/quality")

    assert dashboard_response.status_code == 200
    assert LABELS["dashboard_title"] in dashboard_response.text
    assert quality_response.status_code == 200
    assert LABELS["quality_report"] in quality_response.text


def test_filtered_export_links_preserve_results_filters(client):
    seed_reporting_rows(client.app.state.postgres_engine)

    response = client.get("/results?filename=alpha-report&processing_status=processed&source_type=qr")

    assert response.status_code == 200
    assert "/exports/csv?" in response.text
    assert "/exports/markdown?" in response.text
    assert "filename=alpha-report" in response.text
    assert "processing_status=processed" in response.text
    assert "source_type=qr" in response.text


def test_excel_export_returns_xlsx_response(client):
    seed_reporting_rows(client.app.state.postgres_engine)

    response = client.get("/exports/excel")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "olre_report_" in response.headers["content-disposition"]
    assert response.content.startswith(b"PK")
