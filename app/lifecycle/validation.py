from __future__ import annotations

from app.lifecycle.states import ALLOWED_STATE_TRANSITIONS, STATEFUL_LIFECYCLE_STATES


class LifecycleTransitionError(ValueError):
    """Raised when a lifecycle transition is invalid."""


def validate_transition(from_state: str | None, to_state: str, event_type: str) -> None:
    if to_state not in STATEFUL_LIFECYCLE_STATES:
        raise LifecycleTransitionError(f"Unsupported lifecycle state: {to_state}")

    allowed_targets = ALLOWED_STATE_TRANSITIONS.get(from_state)
    if allowed_targets is None:
        raise LifecycleTransitionError(f"Unsupported transition source state: {from_state}")

    if to_state not in allowed_targets:
        raise LifecycleTransitionError(
            f"Invalid lifecycle transition for {event_type}: {from_state!r} -> {to_state!r}"
        )

