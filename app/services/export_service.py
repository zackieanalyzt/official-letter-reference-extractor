from __future__ import annotations

import csv
import io
from collections.abc import Iterator

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.services.results_service import get_reference_summary, iter_references


def export_csv(
    session: Session,
    filters: dict,
) -> StreamingResponse:
    def generate() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "document_id",
                "filename",
                "page_number",
                "reference_class",
                "source_type",
                "raw_reference",
                "final_url",
                "resolution_status",
            ]
        )
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)

        for row in iter_references(session, **filters):
            writer.writerow(
                [
                    row.document_id,
                    row.filename,
                    row.page_number,
                    row.reference_class,
                    row.source_type,
                    row.raw_reference,
                    row.final_url or "",
                    row.resolution_status,
                ]
            )
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="olre-results.csv"'},
    )


def export_markdown(
    session: Session,
    filters: dict,
) -> StreamingResponse:
    summary = get_reference_summary(session, **filters)

    def generate() -> Iterator[str]:
        yield "# OLRE Extraction Report\n\n"
        yield "## Summary\n"
        yield f"- Total documents: {summary['total_documents']}\n"
        yield f"- Total references: {summary['total_references']}\n"
        yield f"- Resolved: {summary['resolved']}\n"
        yield f"- Failed: {summary['failed']}\n\n"
        yield "## Details\n\n"

        current_filename: str | None = None
        for row in iter_references(session, **filters):
            if row.filename != current_filename:
                if current_filename is not None:
                    yield "\n---\n\n"
                current_filename = row.filename
                yield f"### File: {row.filename}\n\n"
                yield "| Page | Type | Raw | Final | Status |\n"
                yield "|------|------|-----|-------|--------|\n"

            raw_reference = (row.raw_reference or "").replace("|", "\\|")
            final_url = (row.final_url or "").replace("|", "\\|")
            yield (
                f"| {row.page_number} | {row.reference_class} | {raw_reference} | "
                f"{final_url} | {row.resolution_status} |\n"
            )

        if current_filename is None:
            yield "_No references found._\n"

    return StreamingResponse(
        generate(),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="olre-report.md"'},
    )
