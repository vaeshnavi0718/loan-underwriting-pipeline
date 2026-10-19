"""
Schema grader (code, free).

Checks the Review Agent's report has every key the reviewer UI expects,
with the right types. Applications paused for missing documents never
reach the Review Agent, so they are not applicable.
"""
REQUIRED = {
    "summary": str,
    "key_findings": list,
    "inconsistencies": list,
    "risk_explanation": str,
    "narrative_report": str,
}


def grade(result: dict) -> dict | None:
    if result["status"] != "AWAITING_HUMAN_DECISION":
        return None

    report = result["review_report"]
    problems = []
    for key, expected_type in REQUIRED.items():
        if key not in report:
            problems.append(f"missing '{key}'")
        elif not isinstance(report[key], expected_type):
            problems.append(f"'{key}' is {type(report[key]).__name__}, expected {expected_type.__name__}")
        elif not report[key] and expected_type is str:
            problems.append(f"'{key}' is empty")

    return {"passed": not problems, "detail": "; ".join(problems)}
