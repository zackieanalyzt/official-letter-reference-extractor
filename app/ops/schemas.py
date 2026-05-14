from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class PathAccessSnapshot:
    name: str
    path: str
    exists: bool
    readable: bool
    writable: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeSnapshot:
    app_env: str
    storage_backend: str
    configured_database_backend: str
    active_database_backend: str
    configured_database_target: str
    lifecycle_table_available: bool
    document_count: int
    lifecycle_event_count: int
    retained_document_count: int
    cleaned_document_count: int
    failed_document_count: int
    captured_at: datetime
    paths: list[PathAccessSnapshot]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["captured_at"] = self.captured_at.isoformat()
        payload["paths"] = [path.to_dict() for path in self.paths]
        return payload


@dataclass(frozen=True)
class DiagnosticSample:
    code: str
    summary: str
    document_id: int | None = None
    storage_key: str | None = None
    path: str | None = None
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrphanDetectionSummary:
    scanned_documents: int
    scanned_storage_files: int
    sample_limit: int
    unreferenced_storage_file_count: int
    missing_referenced_artifact_count: int
    retained_missing_source_count: int
    cleaned_source_still_present_count: int
    source_expected_without_reference_count: int
    samples: list[DiagnosticSample]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned_documents": self.scanned_documents,
            "scanned_storage_files": self.scanned_storage_files,
            "sample_limit": self.sample_limit,
            "unreferenced_storage_file_count": self.unreferenced_storage_file_count,
            "missing_referenced_artifact_count": self.missing_referenced_artifact_count,
            "retained_missing_source_count": self.retained_missing_source_count,
            "cleaned_source_still_present_count": self.cleaned_source_still_present_count,
            "source_expected_without_reference_count": self.source_expected_without_reference_count,
            "samples": [sample.to_dict() for sample in self.samples],
        }


@dataclass(frozen=True)
class IssueCount:
    code: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LifecycleConsistencySummary:
    total_documents: int
    scan_limit: int
    scanned_documents: int
    truncated: bool
    pass_count: int
    warning_count: int
    error_count: int
    critical_count: int
    top_issue_codes: list[IssueCount]
    samples: list[DiagnosticSample]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_documents": self.total_documents,
            "scan_limit": self.scan_limit,
            "scanned_documents": self.scanned_documents,
            "truncated": self.truncated,
            "pass_count": self.pass_count,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "critical_count": self.critical_count,
            "top_issue_codes": [item.to_dict() for item in self.top_issue_codes],
            "samples": [sample.to_dict() for sample in self.samples],
        }


@dataclass(frozen=True)
class OpsDashboardSnapshot:
    runtime: RuntimeSnapshot
    orphans: OrphanDetectionSummary
    lifecycle_consistency: LifecycleConsistencySummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime": self.runtime.to_dict(),
            "orphans": self.orphans.to_dict(),
            "lifecycle_consistency": self.lifecycle_consistency.to_dict(),
        }
