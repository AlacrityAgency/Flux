"""State machine and valid transition rules."""

from typing import Dict, Set
from flux.contracts.run import RunState


VALID_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    "NEW": {"VALIDATING", "CANCELLED"},
    "VALIDATING": {"PLANNING", "NEEDS_INPUT", "REJECTED", "FAILED", "CANCELLED"},
    "PLANNING": {"QUEUED", "NEEDS_INPUT", "ESCALATED", "REJECTED", "PAUSED_BUDGET", "FAILED", "CANCELLED"},
    "QUEUED": {"RUNNING", "NEEDS_INPUT", "ESCALATED", "PAUSED_BUDGET", "FAILED", "CANCELLED"},
    "RUNNING": {"VERIFYING", "NEEDS_INPUT", "ESCALATED", "REJECTED", "PAUSED_BUDGET", "FAILED", "CANCELLED"},
    "VERIFYING": {"ACCEPT_CANDIDATE", "REVISE", "NEEDS_INPUT", "ESCALATED", "REJECTED", "PAUSED_BUDGET", "FAILED", "CANCELLED"},
    "REVISE": {"QUEUED", "ESCALATED", "PAUSED_BUDGET", "FAILED", "CANCELLED"},
    "NEEDS_INPUT": {"VALIDATING", "CANCELLED"},
    "PAUSED_BUDGET": {"VALIDATING", "CANCELLED"},
    "ESCALATED": {"VALIDATING", "CANCELLED"},
    "ACCEPT_CANDIDATE": set(),
    "REJECTED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


def validate_transition(from_state: RunState, to_state: RunState) -> bool:
    allowed = VALID_TRANSITIONS.get(from_state, set())
    if to_state not in allowed:
        raise InvalidStateTransitionError(
            f"Illegal state transition from {from_state} to {to_state}. Allowed: {sorted(list(allowed))}"
        )
    return True
