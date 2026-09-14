"""
Guardrails enforced by the Harness.

Architecture rule: agents may never set the final decision. Only the human
checkpoint endpoint (routes_review.submit_decision) may transition an
application to APPROVED or DENIED. This module is the single choke point
that enforces that rule, independent of what any agent's code does.
"""
from app.harness.state import Status

HUMAN_ONLY_STATUSES = {Status.APPROVED, Status.DENIED}


class GuardrailViolation(Exception):
    pass


def agent_set_status(state, new_status: Status) -> None:
    """The only way agent/harness code may change status. Refuses to set a
    human-only status, no matter what an agent tries to produce."""
    if new_status in HUMAN_ONLY_STATUSES:
        raise GuardrailViolation(
            f"Agents are not permitted to set status={new_status}. "
            "Final decisions may only be made by a human via the review checkpoint."
        )
    state.status = new_status


def human_set_status(state, new_status: Status) -> None:
    """Only called from the human decision endpoint."""
    state.status = new_status
