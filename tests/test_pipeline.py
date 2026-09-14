"""
Automated backend tests exercising the full agent pipeline end-to-end
against the FastAPI TestClient, using the real synthetic APP-001..APP-010
fixtures. No manual interaction required.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.harness import guardrails
from app.harness.state import ApplicationState, Status
from app.main import app

SYNTH_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_applications")
DOC_TYPES = ["pay_stub", "bank_statement", "credit_report", "id_document"]

client = TestClient(app)


def _open_docs(app_id: str, only: list[str] | None = None) -> dict:
    files = {}
    for doc in only or DOC_TYPES:
        path = os.path.join(SYNTH_DIR, app_id, f"{doc}.pdf")
        if os.path.exists(path):
            files[doc] = (f"{doc}.pdf", open(path, "rb"), "application/pdf")
    return files


def _submit(app_id: str, applicant_name: str, requested_amount: float, employment_status: str, only_docs=None) -> str:
    files = _open_docs(app_id, only_docs)
    data = {
        "applicant_name": applicant_name,
        "requested_amount": requested_amount,
        "loan_purpose": "Testing",
        "employment_status": employment_status,
    }
    resp = client.post("/applications", data=data, files=files, follow_redirects=False)
    for f in files.values():
        f[1].close()
    assert resp.status_code == 303
    location = resp.headers["location"]
    return location.rsplit("/", 1)[-1]


def test_strong_applicant_reaches_human_checkpoint():
    web_id = _submit("APP-001", "Jordan Price", 15000, "Employed full-time")
    state = ApplicationState.load(web_id)
    assert state.status == Status.AWAITING_HUMAN_DECISION
    assert state.risk_assessment["overall_risk_level"] in {"low", "moderate"}
    assert state.review_report.get("narrative_report")


def test_missing_bank_statement_pauses_for_documentation():
    web_id = _submit(
        "APP-004", "Riley Thompson", 12000, "Employed full-time",
        only_docs=["pay_stub", "credit_report", "id_document"],
    )
    state = ApplicationState.load(web_id)
    assert state.status == Status.NEEDS_DOCUMENTATION
    assert "bank_statement" in state.missing_information

    # resume: upload the previously-missing document (APP-004 has no
    # bank_statement.pdf fixture by design, so borrow another app's for the
    # upload-and-resume mechanics)
    stand_in_path = os.path.join(SYNTH_DIR, "APP-001", "bank_statement.pdf")
    with open(stand_in_path, "rb") as f:
        files = {"bank_statement": ("bank_statement.pdf", f, "application/pdf")}
        resp = client.post(f"/applications/{web_id}/documents", files=files, follow_redirects=False)
    assert resp.status_code == 303

    state = ApplicationState.load(web_id)
    assert state.status == Status.AWAITING_HUMAN_DECISION
    assert "bank_statement" not in state.missing_information


def test_income_discrepancy_flagged():
    web_id = _submit("APP-005", "Avery Kim", 18000, "Employed full-time")
    state = ApplicationState.load(web_id)
    assert state.enrichment_results.get("income_discrepancy") is not None


def test_unverified_id_flagged():
    web_id = _submit("APP-006", "Drew Sanders", 9000, "Employed full-time")
    state = ApplicationState.load(web_id)
    assert state.enrichment_results.get("identity_flag") is not None


def test_thin_credit_file_marked_high_credit_risk():
    web_id = _submit("APP-010", "Peyton Reyes", 6000, "Employed part-time")
    state = ApplicationState.load(web_id)
    assert state.risk_assessment["credit_risk"]["band"] == "high"
    assert state.risk_assessment["credit_risk"]["score"] is None


def test_human_accept_sets_approved():
    web_id = _submit("APP-001", "Jordan Price", 15000, "Employed full-time")
    resp = client.post(f"/applications/{web_id}/decision", data={"decision": "ACCEPT"}, follow_redirects=False)
    assert resp.status_code == 303
    state = ApplicationState.load(web_id)
    assert state.status == Status.APPROVED
    assert state.human_decision["decision"] == "ACCEPT"


def test_human_deny_sets_denied():
    web_id = _submit("APP-003", "Casey Nolan", 10000, "Employed full-time")
    resp = client.post(f"/applications/{web_id}/decision", data={"decision": "DENY"}, follow_redirects=False)
    assert resp.status_code == 303
    state = ApplicationState.load(web_id)
    assert state.status == Status.DENIED


def test_request_more_info_reopens_for_upload():
    web_id = _submit("APP-007", "Sam Whitfield", 20000, "Employed full-time")
    resp = client.post(
        f"/applications/{web_id}/decision",
        data={"decision": "REQUEST_MORE_INFO", "requested_documents": ["bank_statement"]},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    state = ApplicationState.load(web_id)
    assert state.status == Status.NEEDS_DOCUMENTATION
    assert "bank_statement" in state.missing_information


def test_guardrail_blocks_agent_from_setting_final_status():
    state = ApplicationState.load_or_create("APP-GUARDRAIL-TEST")
    with pytest.raises(guardrails.GuardrailViolation):
        guardrails.agent_set_status(state, Status.APPROVED)
    with pytest.raises(guardrails.GuardrailViolation):
        guardrails.agent_set_status(state, Status.DENIED)


def test_no_llm_call_in_decision_path():
    """Static guardrail check: orchestrator.apply_human_decision (the human
    decision path) must not import or reference the review/LLM agent."""
    import inspect

    from app.harness import orchestrator

    source = inspect.getsource(orchestrator.apply_human_decision)
    assert "review_agent" not in source
    assert "groq" not in source.lower()


def test_pages_render():
    web_id = _submit("APP-002", "Morgan Ellis", 25000, "Employed full-time")
    assert client.get("/").status_code == 200
    assert client.get(f"/applications/{web_id}").status_code == 200
    r = client.get(f"/applications/{web_id}/review")
    assert r.status_code == 200
    assert "ACCEPT" in r.text and "DENY" in r.text and "REQUEST MORE INFO" in r.text
