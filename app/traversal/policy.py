from __future__ import annotations

from app.config import Settings
from app.traversal.schemas import (
    POLICY_ALLOWED,
    POLICY_BLOCKED,
    POLICY_UNSUPPORTED,
    STATUS_DEPTH_LIMIT_REACHED,
    STATUS_NOT_FOLLOWED,
    STATUS_SKIPPED_BY_POLICY,
    STATUS_UNSUPPORTED,
    TARGET_HTML_PAGE,
    TARGET_IMAGE_URL,
    TARGET_KNOWN_SHORT_URL,
    TARGET_MALFORMED_URL,
    TARGET_PDF_URL,
    TARGET_UNKNOWN,
    TARGET_UNSUPPORTED_SCHEME,
    TraversalClassification,
    TraversalPolicyDecision,
)
from app.traversal.security import blocked_ip_reason, is_domain_allowed, parse_allowed_domains


UNSUPPORTED_TARGET_REASONS = {
    TARGET_MALFORMED_URL: "malformed_url",
    TARGET_UNSUPPORTED_SCHEME: "unsupported_scheme",
    TARGET_HTML_PAGE: "html_expansion_not_supported",
    TARGET_IMAGE_URL: "unsupported_target_type",
    TARGET_UNKNOWN: "unsupported_target_type",
}


def evaluate_traversal_policy(
    classification: TraversalClassification,
    *,
    settings: Settings,
    traversal_depth: int,
    resolved_ips: list[str] | None = None,
) -> TraversalPolicyDecision:
    if traversal_depth > settings.traversal_max_depth:
        return TraversalPolicyDecision(
            policy_decision=POLICY_BLOCKED,
            policy_reason="depth_limit_reached",
            traversal_status=STATUS_DEPTH_LIMIT_REACHED,
        )

    unsupported_reason = UNSUPPORTED_TARGET_REASONS.get(classification.target_type)
    if unsupported_reason:
        return TraversalPolicyDecision(
            policy_decision=POLICY_UNSUPPORTED,
            policy_reason=unsupported_reason,
            traversal_status=STATUS_UNSUPPORTED,
        )

    if classification.target_type not in {TARGET_PDF_URL, TARGET_KNOWN_SHORT_URL}:
        return TraversalPolicyDecision(
            policy_decision=POLICY_UNSUPPORTED,
            policy_reason="unsupported_target_type",
            traversal_status=STATUS_UNSUPPORTED,
        )

    if settings.traversal_block_private_ips:
        ip_reason = blocked_ip_reason(classification.host, resolved_ips=resolved_ips)
        if ip_reason:
            return TraversalPolicyDecision(
                policy_decision=POLICY_BLOCKED,
                policy_reason=ip_reason,
                traversal_status=STATUS_SKIPPED_BY_POLICY,
            )

    allowed_domains = parse_allowed_domains(settings.traversal_allowed_domains)
    if not is_domain_allowed(classification.host, allowed_domains):
        return TraversalPolicyDecision(
            policy_decision=POLICY_BLOCKED,
            policy_reason="domain_not_allowed",
            traversal_status=STATUS_SKIPPED_BY_POLICY,
        )

    if not settings.traversal_enabled:
        return TraversalPolicyDecision(
            policy_decision=POLICY_BLOCKED,
            policy_reason="traversal_disabled",
            traversal_status=STATUS_SKIPPED_BY_POLICY,
        )

    return TraversalPolicyDecision(
        policy_decision=POLICY_ALLOWED,
        policy_reason=None,
        traversal_status=STATUS_NOT_FOLLOWED,
    )

