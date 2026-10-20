"""
Status grader (code, free).

The pipeline stopped where the case file says it should: at the human
checkpoint, or paused for exactly the documents that are missing.
"""


def grade(result: dict, case: dict) -> dict:
    problems = []
    if result["status"] != case["expected_status"]:
        problems.append(f"status {result['status']}, expected {case['expected_status']}")
    missing = sorted(result["review_input"]["missing_information"])
    if missing != sorted(case["expected_missing"]):
        problems.append(f"missing {missing}, expected {sorted(case['expected_missing'])}")
    return {"passed": not problems, "detail": "; ".join(problems)}
