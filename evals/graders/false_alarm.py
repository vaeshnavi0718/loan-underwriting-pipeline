"""
False alarm grader (LLM judge).

The report must not claim anything listed under must_not_claim for the
case: problems that aren't there (an income mismatch on a clean file) and
misreadings seen in real runs (APP-008's risk band read as stability).

A "yes" only fails the report when the judge's quote is verified in the
report. An unverified "yes" passes but is noted, since a failure needs
evidence. A judge error is reported as an error, never as a pass or a
failure. Skipped (None) when no judge is available, e.g. in CI.
"""
from evals import judge
from evals.graders.common import report_text

QUESTION = (
    "Does the report claim or assert the following? {claim}. "
    "Answer no if the report only mentions the topic to rule it out "
    "(for example \"no inconsistencies were found\" does not claim an inconsistency)."
)


def grade(result: dict, case: dict) -> dict | None:
    report = result["review_report"]
    if not report or not case["must_not_claim"] or not judge.available():
        return None

    text = report_text(report)
    claimed, notes = [], []
    for claim in case["must_not_claim"]:
        verdict = judge.ask(QUESTION.format(claim=claim), text)
        if verdict["verdict"] == "error":
            return {"passed": False, "error": True, "detail": f"judge error on '{claim}': {verdict['detail']}"}
        if verdict["verdict"] == "yes":
            claimed.append(f"{claim} -> \"{verdict['evidence']}\"")
        elif verdict["verdict"] == "unsupported":
            notes.append(f"{claim} [{verdict['verdict']}]")

    detail = "; ".join(([f"claimed: {claimed}"] if claimed else []) + ([f"unverified: {notes}"] if notes else []))
    return {"passed": not claimed, "detail": detail}
