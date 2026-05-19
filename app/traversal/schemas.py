from __future__ import annotations

from dataclasses import dataclass


TARGET_PDF_URL = "pdf_url"
TARGET_KNOWN_SHORT_URL = "known_short_url"
TARGET_HTML_PAGE = "html_page"
TARGET_IMAGE_URL = "image_url"
TARGET_MALFORMED_URL = "malformed_url"
TARGET_UNSUPPORTED_SCHEME = "unsupported_scheme"
TARGET_UNKNOWN = "unknown"

STATUS_NOT_FOLLOWED = "NOT_FOLLOWED"
STATUS_SKIPPED_BY_POLICY = "SKIPPED_BY_POLICY"
STATUS_UNSUPPORTED = "UNSUPPORTED"
STATUS_DEPTH_LIMIT_REACHED = "DEPTH_LIMIT_REACHED"

# Reserved for future manual traversal/downloader phases. Phase 2A planning must not emit these.
STATUS_QUEUED = "QUEUED"
STATUS_DOWNLOADED = "DOWNLOADED"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_PROCESSED = "PROCESSED"
STATUS_FAILED = "FAILED"

POLICY_ALLOWED = "allowed"
POLICY_BLOCKED = "blocked"
POLICY_UNSUPPORTED = "unsupported"
POLICY_NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class TraversalClassification:
    target_type: str
    candidate_url: str | None
    scheme: str | None
    host: str | None
    path: str
    reason: str | None = None


@dataclass(frozen=True)
class TraversalPolicyDecision:
    policy_decision: str
    policy_reason: str | None
    traversal_status: str


@dataclass(frozen=True)
class TraversalPlanSummary:
    document_id: int
    created: int
    updated: int
    unchanged: int
    total: int


@dataclass(frozen=True)
class TraversalSummary:
    total: int
    by_status: dict[str, int]
    by_policy_decision: dict[str, int]
    by_target_type: dict[str, int]
