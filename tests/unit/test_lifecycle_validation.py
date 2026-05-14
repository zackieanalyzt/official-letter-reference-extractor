from app.lifecycle import (
    EVENT_DOCUMENT_PROCESSING_STARTED,
    EVENT_DOCUMENT_QUEUED,
    EVENT_DOCUMENT_VALIDATED,
    STATE_PROCESSING,
    STATE_QUEUED,
    STATE_UPLOADED,
    LifecycleTransitionError,
    validate_transition,
)


def test_validate_transition_allows_expected_change():
    validate_transition(STATE_UPLOADED, STATE_QUEUED, EVENT_DOCUMENT_QUEUED)
    validate_transition(STATE_PROCESSING, "validated", EVENT_DOCUMENT_VALIDATED)


def test_validate_transition_rejects_invalid_change():
    try:
        validate_transition(STATE_UPLOADED, STATE_PROCESSING, EVENT_DOCUMENT_PROCESSING_STARTED)
    except LifecycleTransitionError as exc:
        assert "Invalid lifecycle transition" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected invalid transition to fail")

