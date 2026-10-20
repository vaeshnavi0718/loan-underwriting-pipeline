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
