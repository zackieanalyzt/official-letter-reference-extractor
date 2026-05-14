from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document
from app.lifecycle.consistency import (
    SEVERITY_CRITICAL,
    SEVERITY_ERROR,
    SEVERITY_PASS,
    SEVERITY_WARNING,
    validate_document_consistency,
)
from app.ops.orphan_detection import build_orphan_detection_summary
from app.ops.runtime import build_runtime_snapshot
from app.ops.schemas import DiagnosticSample, IssueCount, LifecycleConsistencySummary, OpsDashboardSnapshot


def build_lifecycle_consistency_summary(
    session: Session,
    *,
    settings,
    scan_limit: int = 200,
    sample_limit: int = 10,
) -> LifecycleConsistencySummary:
    document_ids = session.execute(select(Document.id).order_by(Document.id.asc())).scalars().all()
    scanned_ids = document_ids[:scan_limit]

    pass_count = 0
    warning_count = 0
    error_count = 0
    critical_count = 0
    issue_counts: Counter[str] = Counter()
    samples: list[DiagnosticSample] = []

    for document_id in scanned_ids:
        result = validate_document_consistency(session, document_id, settings=settings)
        if result is None:
            continue

        if result.status == SEVERITY_PASS:
            pass_count += 1
        elif result.status == SEVERITY_WARNING:
            warning_count += 1
        elif result.status == SEVERITY_ERROR:
            error_count += 1
        elif result.status == SEVERITY_CRITICAL:
            critical_count += 1

        failing_checks = [check for check in result.checks if not check.passed]
        for check in failing_checks:
            issue_counts[check.code] += 1

        if failing_checks and len(samples) < sample_limit:
            samples.append(
                DiagnosticSample(
                    code=failing_checks[0].code,
                    document_id=document_id,
                    summary=result.summary,
                    details="; ".join(check.summary for check in failing_checks[:3]),
                )
            )

    top_issue_codes = [
        IssueCount(code=code, count=count)
        for code, count in issue_counts.most_common(5)
    ]

    return LifecycleConsistencySummary(
        total_documents=len(document_ids),
        scan_limit=scan_limit,
        scanned_documents=len(scanned_ids),
        truncated=len(document_ids) > scan_limit,
        pass_count=pass_count,
        warning_count=warning_count,
        error_count=error_count,
        critical_count=critical_count,
        top_issue_codes=top_issue_codes,
        samples=samples,
    )


def build_ops_dashboard_snapshot(session: Session, settings, engine) -> OpsDashboardSnapshot:
    return OpsDashboardSnapshot(
        runtime=build_runtime_snapshot(session, settings, engine),
        orphans=build_orphan_detection_summary(session, settings),
        lifecycle_consistency=build_lifecycle_consistency_summary(session, settings=settings),
    )
