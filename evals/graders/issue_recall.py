"""
Issue recall grader (LLM judge).

Did the report surface every fact the case file lists under must_mention?
Each fact is its own yes/no question to the judge, and a "yes" only counts
if the judge's quote is really in the report.

A judge error is reported as an error, never as a missed fact. Skipped
(None) when no judge is available, e.g. in CI.
"""
from evals import judge
from evals.graders.common import RECALL_QUESTION, judge_report, report_text


def grade(result: dict, case: dict) -> dict | None:
    report = result["review_report"]
    if not report or not case["must_mention"] or not judge.available():
        return None

    verdicts = judge_report(case, report_text(report))
    missed, evidence = [], {}
    for fact in case["must_mention"]:
        verdict = verdicts[RECALL_QUESTION.format(fact=fact)]
        if verdict["verdict"] == "error":
            return {"passed": False, "error": True, "detail": f"judge error on '{fact}': {verdict['detail']}"}
        if verdict["verdict"] == "yes":
            evidence[fact] = verdict["evidence"]
        else:
            note = " [unsupported]" if verdict["verdict"] == "unsupported" else ""
            missed.append(fact + note)

    found = len(case["must_mention"]) - len(missed)
    return {
        "passed": not missed,
        "detail": f"missed: {missed}" if missed else "",
        "facts_found": found,
        "facts_total": len(case["must_mention"]),
        "evidence": evidence,
    }
