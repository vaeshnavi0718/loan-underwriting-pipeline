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

    A batched verdict that would fail the report (a fact not found, a false
    claim found) is asked again on its own, the setup the judge was
    calibrated in. On new reports, batching missed 3 facts that single
    questions found, twice by stitching two sentences into one quote.
    Returns {question: verdict}.
    """
    recall = [RECALL_QUESTION.format(fact=f) for f in case.get("must_mention", [])]
    false_alarm = [FALSE_ALARM_QUESTION.format(claim=c) for c in case.get("must_not_claim", [])]
    verdicts = dict(zip(recall + false_alarm, judge.ask_many(recall + false_alarm, text)))
    for question in recall:
        if verdicts[question]["verdict"] in {"no", "unsupported"}:
            verdicts[question] = judge.ask(question, text)
    for question in false_alarm:
        if verdicts[question]["verdict"] == "yes":
            verdicts[question] = judge.ask(question, text)
    return verdicts
