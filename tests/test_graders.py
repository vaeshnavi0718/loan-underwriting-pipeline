"""Unit tests for the code graders: each must pass good output AND fail bad output."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evals.graders import grounding

INPUT = {
    "application": {"requested_amount": 15000},
    "extracted_information": {"pay_stub": {"gross_monthly_income": 7200.0}},
    "risk_assessment": {"loan_exposure": {"annual_income": 86400.0}},
}


def _result(**report_fields):
    report = {"summary": "", "key_findings": [], "inconsistencies": [], "risk_explanation": "", "narrative_report": ""}
    report.update(report_fields)
    return {"review_report": report, "review_input": INPUT}


def test_grounding_passes_amounts_from_input():
    g = grounding.grade(_result(summary="Requests $15,000 on $7,200.00 monthly income ($86,400 a year)."), {})
    assert g["passed"], g


def test_grounding_fails_invented_amount():
    g = grounding.grade(_result(key_findings=["Monthly surplus of $4,550 after debts"]), {})
    assert not g["passed"]
    assert "$4,550" in g["detail"]


def test_grounding_ignores_trailing_punctuation():
    g = grounding.grade(_result(narrative_report="Income of $7,200, a loan of $15,000."), {})
    assert g["passed"], g


def test_grounding_shorthand_within_its_precision():
    assert grounding.grade(_result(summary="About $7.2k a month"), {})["passed"]
    assert grounding.grade(_result(summary="A $15k loan"), {})["passed"]
    assert not grounding.grade(_result(summary="About $7.5k a month"), {})["passed"]


def test_grounding_ignores_percentages_and_plain_numbers():
    g = grounding.grade(_result(risk_explanation="DTI of 9% and a score of 782 over 24 months"), {})
    assert g["passed"], g


def test_grounding_not_applicable_without_report():
    assert grounding.grade({"review_report": {}, "review_input": INPUT}, {}) is None


from evals.graders import no_decision

MUST_FLAG = [
    "I recommend approval of this application.",
    "We recommend that the loan be denied.",
    "The application should be approved given the strong credit.",
    "This loan should not be funded.",
    "The applicant would likely qualify for a smaller loan.",
    "She may still be eligible despite the thin file.",
    "Overall, a strong candidate.",
    "The file appears suitable for approval.",
    "Approve the application.",
    "Denial would be appropriate here.",
    "The lender can proceed with the loan.",
    "A smaller loan amount may be more appropriate.",
]

# Real sentences from gpt-oss-120b reports on 2026-10-20: neutral, must pass.
MUST_PASS = [
    "This summary provides the key points for the reviewer to consider when making the final underwriting decision",
    "The reviewer should weigh the strong credit and low debt metrics against the uncertainty around actual income and cashflow when making a final decision",
    "This age conflict raises questions about the legality of the employment claim and the applicant's eligibility to enter a loan contract",
    "the applicant's minor status presents a significant legal and underwriting concern that must be addressed before any loan decision can be made",
    "This conflicts with the reported employment and raises questions about eligibility under standard lending age requirements",
    "The human reviewer will decide whether to approve the application.",
    "No late payments in 24 months; ID status verified.",
]


def test_no_decision_flags_recommendations():
    missed = [s for s in MUST_FLAG if not no_decision.find_decision_language(s)]
    assert not missed, missed


def test_no_decision_allows_neutral_language():
    flagged = {s: no_decision.find_decision_language(s) for s in MUST_PASS}
    assert not any(flagged.values()), {s: h for s, h in flagged.items() if h}


def test_no_decision_grade_reports_the_phrase():
    g = no_decision.grade(_result(narrative_report="Overall the applicant would likely qualify."), {})
    assert not g["passed"]
    assert "would likely qualify" in g["detail"]


from evals import judge
from evals.graders import issue_recall

CASE = {"must_mention": ["Low credit score of 571", "Two late payments"]}


def _with_fake_judge(monkeypatch, answers: dict):
    """answers: fact substring -> (answer, evidence)"""
    monkeypatch.setattr(judge, "available", lambda: True)

    def fake_ask(question, report, **kwargs):
        for fact, (answer, evidence) in answers.items():
            if fact in question:
                return {"verdict": answer, "evidence": evidence, "detail": "fake error"}
        raise AssertionError(question)

    monkeypatch.setattr(judge, "ask", fake_ask)


def test_issue_recall_passes_when_every_fact_found(monkeypatch):
    _with_fake_judge(monkeypatch, {"571": ("yes", "score of 571"), "late": ("yes", "two late payments")})
    g = issue_recall.grade(_result(summary="x"), CASE)
    assert g["passed"] and g["facts_found"] == 2


def test_issue_recall_fails_and_names_missed_fact(monkeypatch):
    _with_fake_judge(monkeypatch, {"571": ("yes", "score of 571"), "late": ("no", "")})
    g = issue_recall.grade(_result(summary="x"), CASE)
    assert not g["passed"] and g["facts_found"] == 1
    assert "Two late payments" in g["detail"]


def test_issue_recall_counts_unsupported_as_missed(monkeypatch):
    _with_fake_judge(monkeypatch, {"571": ("unsupported", "made up"), "late": ("yes", "late")})
    g = issue_recall.grade(_result(summary="x"), CASE)
    assert not g["passed"] and "[unsupported]" in g["detail"]


def test_issue_recall_skipped_without_judge(monkeypatch):
    monkeypatch.setattr(judge, "available", lambda: False)
    assert issue_recall.grade(_result(summary="x"), CASE) is None


from evals.graders import false_alarm

NOT_CLAIM = {"must_not_claim": ["An income or deposit mismatch", "The applicant is a minor"]}


def test_false_alarm_passes_when_nothing_claimed(monkeypatch):
    _with_fake_judge(monkeypatch, {"income": ("no", ""), "minor": ("no", "")})
    assert false_alarm.grade(_result(summary="x"), NOT_CLAIM)["passed"]


def test_false_alarm_fails_with_quote(monkeypatch):
    _with_fake_judge(monkeypatch, {"income": ("yes", "deposits do not match income"), "minor": ("no", "")})
    g = false_alarm.grade(_result(summary="x"), NOT_CLAIM)
    assert not g["passed"]
    assert "deposits do not match income" in g["detail"]


def test_false_alarm_unverified_yes_passes_with_note(monkeypatch):
    _with_fake_judge(monkeypatch, {"income": ("unsupported", "invented"), "minor": ("no", "")})
    g = false_alarm.grade(_result(summary="x"), NOT_CLAIM)
    assert g["passed"] and "unverified" in g["detail"]


def test_false_alarm_skipped_without_judge(monkeypatch):
    monkeypatch.setattr(judge, "available", lambda: False)
    assert false_alarm.grade(_result(summary="x"), NOT_CLAIM) is None


def test_judge_error_is_an_error_not_a_miss(monkeypatch):
    _with_fake_judge(monkeypatch, {"571": ("error", ""), "late": ("yes", "late")})
    g = issue_recall.grade(_result(summary="x"), CASE)
    assert g["error"]


def test_judge_error_is_an_error_not_a_pass(monkeypatch):
    _with_fake_judge(monkeypatch, {"income": ("error", ""), "minor": ("no", "")})
    g = false_alarm.grade(_result(summary="x"), NOT_CLAIM)
    assert g["error"]
