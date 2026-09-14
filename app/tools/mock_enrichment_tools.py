"""
Mock enrichment tools.

These stand in for real external integrations (an employment verification
service, a bank-connectivity/cash-flow provider like Plaid, a credit bureau
API). Each function takes the structured data the Document Agent already
extracted and returns a result shaped like what a real API would return, so
swapping in a real provider later only means rewriting the body of these
functions -- callers (the Data Enrichment Agent) don't change.

No real external network calls are made anywhere in this module.
"""
from typing import Any


def verify_employment(extracted: dict[str, Any]) -> dict[str, Any]:
    """Mock employment verification. A real integration would call a service
    like The Work Number here."""
    pay_stub = extracted.get("pay_stub")
    if not pay_stub or not pay_stub.get("employer_name"):
        return {
            "tool": "verify_employment",
            "status": "unable_to_verify",
            "reason": "No pay stub / employer name available to verify",
        }
    employer = pay_stub["employer_name"]
    return {
        "tool": "verify_employment",
        "status": "verified",
        "employer_name": employer,
        "note": f"Mock registry lookup confirms an active record for '{employer}'.",
    }


def analyze_bank_cashflow(extracted: dict[str, Any]) -> dict[str, Any]:
    """Mock cash-flow analysis. A real integration would call a bank
    connectivity provider (e.g. Plaid) here."""
    bank = extracted.get("bank_statement")
    if not bank or bank.get("average_monthly_balance") is None:
        return {
            "tool": "analyze_bank_cashflow",
            "status": "unavailable",
            "reason": "No bank statement data available to analyze",
        }
    balance = bank["average_monthly_balance"]
    deposits = bank.get("monthly_deposits") or 0
    if balance <= 0:
        stability = "critical"
    elif balance < deposits * 0.5:
        stability = "low"
    elif balance < deposits * 1.5:
        stability = "moderate"
    else:
        stability = "strong"
    return {
        "tool": "analyze_bank_cashflow",
        "status": "analyzed",
        "average_monthly_balance": balance,
        "monthly_deposits": deposits,
        "cashflow_stability": stability,
    }


def get_credit_details(extracted: dict[str, Any]) -> dict[str, Any]:
    """Mock credit bureau pull. A real integration would call a bureau API
    (Experian/Equifax/TransUnion) here."""
    credit = extracted.get("credit_report")
    if not credit or credit.get("credit_score") is None:
        return {
            "tool": "get_credit_details",
            "status": "no_score_on_file",
            "reason": "No credit score found on file (thin file)",
            "existing_monthly_debt": (credit or {}).get("existing_monthly_debt"),
            "payment_history": (credit or {}).get("payment_history"),
        }
    return {
        "tool": "get_credit_details",
        "status": "retrieved",
        "credit_score": credit["credit_score"],
        "existing_monthly_debt": credit.get("existing_monthly_debt"),
        "payment_history": credit.get("payment_history"),
    }
