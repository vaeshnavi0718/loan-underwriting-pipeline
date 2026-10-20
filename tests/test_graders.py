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
