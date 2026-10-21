"""Prompt-injection attacks can't change an application's status, and text
outside extracted fields never reaches the LLM. Runs without an API key."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evals.cases import INJECTION_CASES_PATH, load_cases
from evals.harness import INJECTION_DIR, list_cases, run_case

CASES = load_cases(INJECTION_CASES_PATH)


def test_every_injection_fixture_has_a_case():
    assert sorted(CASES) == list_cases(INJECTION_DIR)


def test_no_injection_changes_the_status():
    for case_id in CASES:
        status = run_case(case_id, INJECTION_DIR)["status"]
        assert status == "AWAITING_HUMAN_DECISION", f"{case_id} ended at {status}"


def test_injected_text_reaches_the_llm_only_through_fields():
    for case_id, case in CASES.items():
        llm_input = json.dumps(run_case(case_id, INJECTION_DIR)["review_input"])
        assert (case["injection"] in llm_input) == case["reaches_llm"], case_id
