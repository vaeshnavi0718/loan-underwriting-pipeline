"""
Risk Analysis Agent.

Rule-based (no LLM). Computes DTI, credit risk, income stability, cash-flow
risk, and loan exposure from the extracted + enrichment data, and writes a
structured risk_assessment onto the shared state.
"""
from app.harness.state import ApplicationState, Step

RISK_ORDER = {"low": 0, "moderate": 1, "high": 2, "critical": 3, "unknown": 2}


def _band(value: float, low_max: float, mod_max: float) -> str:
    if value <= low_max:
        return "low"
    if value <= mod_max:
        return "moderate"
    return "high"


def _debt_to_income(state: ApplicationState, application: dict) -> dict:
    pay_stub = state.extracted_information.get("pay_stub", {})
    credit = state.extracted_information.get("credit_report", {})
    income = pay_stub.get("gross_monthly_income")
    existing_debt = credit.get("existing_monthly_debt")

    if income is None or existing_debt is None:
        return {"ratio": None, "band": "unknown", "note": "Insufficient data to compute DTI"}

    ratio = round(existing_debt / income, 3)
    band = _band(ratio, 0.30, 0.43)
    return {"ratio": ratio, "band": band, "existing_monthly_debt": existing_debt, "gross_monthly_income": income}


def _credit_risk(state: ApplicationState) -> dict:
    credit = state.extracted_information.get("credit_report", {})
    score = credit.get("credit_score")
    history = credit.get("payment_history")

    if score is None:
        return {"score": None, "band": "high", "note": "No credit score on file (thin file / unscored)"}
    if score >= 740:
        band = "low"
    elif score >= 670:
        band = "moderate"
    elif score >= 600:
        band = "high"
    else:
        band = "critical"

    late_payment = bool(history and "late" in history.lower() and "no late" not in history.lower())
    return {"score": score, "band": band, "payment_history": history, "recent_late_payments": late_payment}


def _income_stability(state: ApplicationState, application: dict) -> dict:
    employment_status = (application.get("employment_status") or "").lower()
    employment_result = state.enrichment_results.get("employment", {})
    income_discrepancy = state.enrichment_results.get("income_discrepancy")

    if "part-time" in employment_status:
        band = "moderate"
    elif "self-employed" in employment_status:
        band = "moderate"
    elif employment_result.get("status") != "verified":
        band = "high"
    else:
        band = "low"

    if income_discrepancy:
        band = "high"

    return {
        "band": band,
        "employment_status": application.get("employment_status"),
        "employment_verified": employment_result.get("status") == "verified",
        "income_discrepancy": income_discrepancy,
    }


def _cashflow_risk(state: ApplicationState) -> dict:
    cashflow = state.enrichment_results.get("cashflow", {})
    stability = cashflow.get("cashflow_stability")
    mapping = {"strong": "low", "moderate": "moderate", "low": "high", "critical": "critical"}
    band = mapping.get(stability, "unknown")
    return {"band": band, "cashflow_stability": stability, **cashflow}


def _loan_exposure(state: ApplicationState, application: dict) -> dict:
    pay_stub = state.extracted_information.get("pay_stub", {})
    requested = application.get("requested_amount")
    income = pay_stub.get("gross_monthly_income")

    if requested is None or not income:
        return {"band": "unknown", "note": "Insufficient data to compute loan exposure"}

    annual_income = income * 12
    ratio = round(requested / annual_income, 3)
    band = _band(ratio, 0.20, 0.50)
    return {
        "requested_amount": requested,
        "annual_income": annual_income,
        "loan_to_income_ratio": ratio,
        "band": band,
    }


def run(state: ApplicationState, application: dict) -> None:
    state.current_step = Step.RISK_ANALYSIS
    state.log("RISK_ANALYSIS", "STARTED")

    dti = _debt_to_income(state, application)
    credit_risk = _credit_risk(state)
    income_stability = _income_stability(state, application)
    cashflow_risk = _cashflow_risk(state)
    loan_exposure = _loan_exposure(state, application)

    bands = [dti["band"], credit_risk["band"], income_stability["band"], cashflow_risk["band"], loan_exposure["band"]]
    overall = max(bands, key=lambda b: RISK_ORDER.get(b, 1))

    assessment = {
        "debt_to_income": dti,
        "credit_risk": credit_risk,
        "income_stability": income_stability,
        "cashflow_risk": cashflow_risk,
        "loan_exposure": loan_exposure,
        "overall_risk_level": overall,
    }
    state.risk_assessment = assessment
    state.log("RISK_ANALYSIS", "COMPLETED", f"overall_risk_level={overall}")
