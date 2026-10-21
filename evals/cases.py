"""
Loads and validates the case files in evals/cases/.

A malformed case file fails loudly here instead of silently skewing
grades later.
"""
import os

import yaml

CASES_PATH = os.path.join(os.path.dirname(__file__), "cases", "review_cases.yaml")
INJECTION_CASES_PATH = os.path.join(os.path.dirname(__file__), "cases", "injection_cases.yaml")
VALID_STATUSES = {"AWAITING_HUMAN_DECISION", "NEEDS_DOCUMENTATION"}


def load_cases(path: str = CASES_PATH) -> dict[str, dict]:
    with open(path) as f:
        raw = yaml.safe_load(f)

    cases: dict[str, dict] = {}
    for case in raw:
        case_id = case.get("id")
        if not case_id:
            raise ValueError(f"case without an id: {case}")
        if case_id in cases:
            raise ValueError(f"duplicate case id: {case_id}")
        if case.get("expected_status") not in VALID_STATUSES:
            raise ValueError(f"{case_id}: expected_status must be one of {sorted(VALID_STATUSES)}")
        if case["expected_status"] == "AWAITING_HUMAN_DECISION":
            if not case.get("must_mention"):
                raise ValueError(f"{case_id}: a case that reaches review needs at least one must_mention")
        elif not case.get("expected_missing"):
            raise ValueError(f"{case_id}: a paused case needs expected_missing")
        case.setdefault("must_mention", [])
        case.setdefault("must_not_claim", [])
        case.setdefault("expected_missing", [])
        cases[case_id] = case
    return cases
