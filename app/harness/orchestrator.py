"""
Agent Harness -- the orchestration layer.

Owns the shared ApplicationState, routes work to agents in order, applies
guardrails (agents can never set a final decision), pauses/resumes the
workflow, retries failed steps, and logs every transition to
state.execution_history.

Agents perform specialized tasks. The Harness controls the workflow.
The Human makes the final underwriting decision.
"""
import os
from datetime import datetime, timezone

from app.agents import document_agent, enrichment_agent, review_agent, risk_agent
from app.harness import guardrails
from app.harness.state import ApplicationState, Status, Step

MAX_STEP_RETRIES = 2
VALID_DECISIONS = {"ACCEPT", "DENY", "REQUEST_MORE_INFO"}


def _application_fields(state: ApplicationState) -> dict:
    return state.extracted_information.get("application", {})


def _run_step(state: ApplicationState, step_name: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        retries = state.retry_counts.get(step_name, 0) + 1
        state.retry_counts[step_name] = retries
        state.log(step_name, "STEP_ERROR", f"{exc} (retry {retries}/{MAX_STEP_RETRIES})")
        state.save()
        if retries > MAX_STEP_RETRIES:
            guardrails.agent_set_status(state, Status.ERROR)
            state.log(step_name, "STEP_FAILED_PERMANENTLY", str(exc))
            state.save()
            raise
        return _run_step(state, step_name, fn, *args, **kwargs)


def create_application(application_id: str, application_fields: dict) -> ApplicationState:
    state = ApplicationState.load_or_create(application_id)
    state.extracted_information["application"] = application_fields
    state.log("INTAKE", "APPLICATION_SUBMITTED", str(application_fields))
    state.save()
    return state


def run_pipeline(application_id: str, new_document_paths: dict[str, str] | None = None) -> ApplicationState:
    """Runs (or resumes) the agent pipeline for an application.

    Called after initial document submission, and again after additional
    documents are uploaded in response to NEEDS_DOCUMENTATION.
    """
    state = ApplicationState.load_or_create(application_id)
    guardrails.agent_set_status(state, Status.IN_PROGRESS)
    state.log("HARNESS", "PIPELINE_STARTED", f"resume={bool(new_document_paths)}")
    state.save()

    if new_document_paths:
        for doc_type, path in new_document_paths.items():
            state.uploaded_documents[doc_type] = os.path.basename(path)
        state.save()
        _run_step(state, "DOCUMENT_EXTRACTION", document_agent.run, state, new_document_paths)
        state.save()

    needs_docs = _run_step(state, "ENRICHMENT", enrichment_agent.run, state)
    state.save()

    if needs_docs:
        guardrails.agent_set_status(state, Status.NEEDS_DOCUMENTATION)
        state.log("HARNESS", "PAUSED_FOR_DOCUMENTATION", f"missing={state.missing_information}")
        state.save()
        return state

    application = _application_fields(state)
    _run_step(state, "RISK_ANALYSIS", risk_agent.run, state, application)
    state.save()

    _run_step(state, "REVIEW", review_agent.run, state, application)
    state.save()

    state.current_step = Step.HUMAN_CHECKPOINT
    guardrails.agent_set_status(state, Status.AWAITING_HUMAN_DECISION)
    state.log("HARNESS", "PAUSED_FOR_HUMAN_DECISION")
    state.save()
    return state


def apply_human_decision(
    application_id: str,
    decision: str,
    notes: str = "",
    requested_documents: list[str] | None = None,
) -> ApplicationState:
    """The ONLY function permitted to move an application to APPROVED/DENIED.
    Called exclusively from the human-facing review endpoint -- never by an
    agent."""
    decision = decision.upper().replace(" ", "_")
    if decision not in VALID_DECISIONS:
        raise ValueError(f"Unknown decision '{decision}'. Must be one of {VALID_DECISIONS}")

    state = ApplicationState.load_or_create(application_id)
    state.human_decision = {
        "decision": decision,
        "notes": notes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if decision == "ACCEPT":
        guardrails.human_set_status(state, Status.APPROVED)
        state.current_step = Step.DONE
    elif decision == "DENY":
        guardrails.human_set_status(state, Status.DENIED)
        state.current_step = Step.DONE
    else:  # REQUEST_MORE_INFO
        guardrails.human_set_status(state, Status.NEEDS_DOCUMENTATION)
        for doc in requested_documents or []:
            if doc not in state.missing_information:
                state.missing_information.append(doc)
        state.current_step = Step.ENRICHMENT

    state.log("HUMAN_CHECKPOINT", "DECISION_RECORDED", f"{decision} notes={notes!r}")
    state.save()
    return state
