"""
Runs one synthetic application through the real pipeline for evaluation.

Calls the orchestrator directly (no HTTP), under a throwaway application id,
and removes that application's saved state afterwards so eval runs never
show up in the web UI.
"""
import json
import os
import shutil
import uuid

from app.harness import orchestrator
from app.harness.state import ApplicationState

SYNTH_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_applications")
DOC_TYPES = ["pay_stub", "bank_statement", "credit_report", "id_document"]


def list_cases() -> list[str]:
    return sorted(
        name for name in os.listdir(SYNTH_DIR)
        if os.path.isfile(os.path.join(SYNTH_DIR, name, "application.json"))
    )


def run_case(case_id: str) -> dict:
    """Runs the pipeline on one fixture and returns everything graders need."""
    case_dir = os.path.join(SYNTH_DIR, case_id)
    with open(os.path.join(case_dir, "application.json")) as f:
        fixture = json.load(f)

    eval_id = f"EVAL-{case_id}-{uuid.uuid4().hex[:6].upper()}"
    application = {k: v for k, v in fixture.items() if not k.startswith("_")}
    application["application_id"] = eval_id

    doc_paths = {
        doc: os.path.join(case_dir, f"{doc}.pdf")
        for doc in DOC_TYPES
        if os.path.exists(os.path.join(case_dir, f"{doc}.pdf"))
    }

    orchestrator.create_application(eval_id, application)
    state = orchestrator.run_pipeline(eval_id, doc_paths)

    try:
        return {
            "case_id": case_id,
            "scenario": fixture.get("_scenario_note", ""),
            "status": str(state.status),
            "review_report": state.review_report,
            "review_input": {
                "application": application,
                "extracted_information": state.extracted_information,
                "enrichment_results": state.enrichment_results,
                "missing_information": state.missing_information,
                "risk_assessment": state.risk_assessment,
            },
            "used_fallback": any(e.event == "FALLBACK_REPORT_USED" for e in state.execution_history),
        }
    finally:
        shutil.rmtree(ApplicationState(application_id=eval_id).dir_path(), ignore_errors=True)
