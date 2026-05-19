from app.config import Settings
from app.traversal.classifier import classify_reference_url
from app.traversal.policy import evaluate_traversal_policy
from app.traversal.schemas import (
    POLICY_ALLOWED,
    POLICY_BLOCKED,
    POLICY_UNSUPPORTED,
    STATUS_DEPTH_LIMIT_REACHED,
    STATUS_NOT_FOLLOWED,
    STATUS_SKIPPED_BY_POLICY,
    STATUS_UNSUPPORTED,
)


def _settings(monkeypatch, **overrides) -> Settings:
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("TRAVERSAL_ENABLED", str(overrides.get("enabled", False)).lower())
    monkeypatch.setenv("TRAVERSAL_MAX_DEPTH", str(overrides.get("max_depth", 1)))
    monkeypatch.setenv("TRAVERSAL_ALLOWED_DOMAINS", overrides.get("allowed_domains", ""))
    monkeypatch.setenv("TRAVERSAL_BLOCK_PRIVATE_IPS", str(overrides.get("block_private", True)).lower())
    return Settings(_env_file=None)


def test_policy_is_disabled_by_default(monkeypatch):
    settings = _settings(monkeypatch)
    classification = classify_reference_url("https://example.go.th/file.pdf")

    decision = evaluate_traversal_policy(classification, settings=settings, traversal_depth=1)

    assert decision.policy_decision == POLICY_BLOCKED
    assert decision.policy_reason == "traversal_disabled"
    assert decision.traversal_status == STATUS_SKIPPED_BY_POLICY


def test_policy_allows_pdf_when_enabled(monkeypatch):
    settings = _settings(monkeypatch, enabled=True)
    classification = classify_reference_url("https://example.go.th/file.pdf")

    decision = evaluate_traversal_policy(classification, settings=settings, traversal_depth=1)

    assert decision.policy_decision == POLICY_ALLOWED
    assert decision.policy_reason is None
    assert decision.traversal_status == STATUS_NOT_FOLLOWED


def test_policy_rejects_unsupported_targets_before_enabled_check(monkeypatch):
    settings = _settings(monkeypatch, enabled=True)
    classification = classify_reference_url("https://example.go.th/page.html")

    decision = evaluate_traversal_policy(classification, settings=settings, traversal_depth=1)

    assert decision.policy_decision == POLICY_UNSUPPORTED
    assert decision.policy_reason == "html_expansion_not_supported"
    assert decision.traversal_status == STATUS_UNSUPPORTED


def test_policy_enforces_depth_limit(monkeypatch):
    settings = _settings(monkeypatch, enabled=True, max_depth=1)
    classification = classify_reference_url("https://example.go.th/file.pdf")

    decision = evaluate_traversal_policy(classification, settings=settings, traversal_depth=2)

    assert decision.policy_decision == POLICY_BLOCKED
    assert decision.policy_reason == "depth_limit_reached"
    assert decision.traversal_status == STATUS_DEPTH_LIMIT_REACHED


def test_policy_blocks_private_loopback_link_local_multicast_and_unspecified(monkeypatch):
    settings = _settings(monkeypatch, enabled=True)

    cases = {
        "http://10.0.0.1/file.pdf": "private_ip_blocked",
        "http://127.0.0.1/file.pdf": "loopback_blocked",
        "http://169.254.10.1/file.pdf": "link_local_blocked",
        "http://224.0.0.1/file.pdf": "multicast_blocked",
        "http://0.0.0.0/file.pdf": "unspecified_ip_blocked",
    }
    for url, reason in cases.items():
        decision = evaluate_traversal_policy(
            classify_reference_url(url),
            settings=settings,
            traversal_depth=1,
        )
        assert decision.policy_decision == POLICY_BLOCKED
        assert decision.policy_reason == reason


def test_policy_enforces_domain_allowlist(monkeypatch):
    settings = _settings(monkeypatch, enabled=True, allowed_domains="moph.go.th")

    blocked = evaluate_traversal_policy(
        classify_reference_url("https://example.com/file.pdf"),
        settings=settings,
        traversal_depth=1,
    )
    allowed = evaluate_traversal_policy(
        classify_reference_url("https://dept.moph.go.th/file.pdf"),
        settings=settings,
        traversal_depth=1,
    )

    assert blocked.policy_reason == "domain_not_allowed"
    assert allowed.policy_decision == POLICY_ALLOWED
