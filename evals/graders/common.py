"""Helpers shared by the graders."""
from evals import judge

RECALL_QUESTION = (
    "Does the report state the following? Wording, rounding and number formatting may differ, "
    "but the substance must be there: {fact}"
)

FALSE_ALARM_QUESTION = (
    "Does the report claim or assert the following? {claim}. "
    "Answer no if the report only mentions the topic to rule it out "
    "(for example \"no inconsistencies were found\" does not claim an inconsistency)."
)


def report_text(report: dict) -> str:
    """All of a review report's text fields joined, so graders check every field."""
    parts = []
    for value in report.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
    return "\n".join(parts)


def judge_report(case: dict, text: str) -> dict[str, dict]:
    """Asks the judge every question about one report in a single batched call.

    Both judge graders call this with the same case and report, so they send
    the same prompt and the second one is a cache hit: one call per report.
    Batched and one-at-a-time verdicts agreed on 141/141 questions (39 reports).
    Returns {question: verdict}.
    """
    questions = [RECALL_QUESTION.format(fact=f) for f in case.get("must_mention", [])]
    questions += [FALSE_ALARM_QUESTION.format(claim=c) for c in case.get("must_not_claim", [])]
    return dict(zip(questions, judge.ask_many(questions, text)))
