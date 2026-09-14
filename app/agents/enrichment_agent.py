"""
Data Enrichment Agent.

Calls the mock enrichment tools, records what was found vs. what's missing,
and tells the Harness whether the application must pause for more
documentation. Required documents that were never uploaded trigger a pause;
a document that *was* uploaded but has incomplete data (e.g. a thin credit
file with no score) is treated as a risk signal for the Risk Agent, not a
missing-documentation pause.
"""
from app.harness.state import ApplicationState, Step
from app.tools.mock_enrichment_tools import (
    analyze_bank_cashflow,
    get_credit_details,
    verify_employment,
)

REQUIRED_DOCUMENTS = ["pay_stub", "bank_statement", "credit_report", "id_document"]
INCOME_DISCREPANCY_THRESHOLD = 0.7  # deposits below 70% of stated gross income flagged


def run(state: ApplicationState) -> bool:
    """Returns True if the application must pause for more documentation."""
    state.current_step = Step.ENRICHMENT
    state.log("ENRICHMENT", "STARTED")

    missing = [d for d in REQUIRED_DOCUMENTS if d not in state.extracted_information]
    state.missing_information = missing
    if missing:
        state.log("ENRICHMENT", "MISSING_DOCUMENTS", f"{missing}")

    employment = verify_employment(state.extracted_information)
    cashflow = analyze_bank_cashflow(state.extracted_information)
    credit = get_credit_details(state.extracted_information)
    state.log("ENRICHMENT", "TOOL_RESULT", f"verify_employment -> {employment}")
    state.log("ENRICHMENT", "TOOL_RESULT", f"analyze_bank_cashflow -> {cashflow}")
    state.log("ENRICHMENT", "TOOL_RESULT", f"get_credit_details -> {credit}")

    results: dict = {"employment": employment, "cashflow": cashflow, "credit": credit}

    pay_stub = state.extracted_information.get("pay_stub", {})
    bank_statement = state.extracted_information.get("bank_statement", {})
    stated_income = pay_stub.get("gross_monthly_income")
    deposits = bank_statement.get("monthly_deposits")
    income_discrepancy = None
    if stated_income and deposits is not None:
        if deposits < stated_income * INCOME_DISCREPANCY_THRESHOLD:
            income_discrepancy = {
                "stated_gross_monthly_income": stated_income,
                "observed_monthly_deposits": deposits,
                "shortfall_pct": round((1 - deposits / stated_income) * 100, 1),
            }
            state.log("ENRICHMENT", "INCOME_DISCREPANCY_FLAGGED", f"{income_discrepancy}")
    results["income_discrepancy"] = income_discrepancy

    id_document = state.extracted_information.get("id_document", {})
    identity_flag = None
    if id_document.get("id_status") == "not_verified":
        identity_flag = "ID document could not be verified"
        state.log("ENRICHMENT", "IDENTITY_FLAG", identity_flag)
    results["identity_flag"] = identity_flag

    results["additional_documentation_required"] = bool(missing)
    state.enrichment_results = results
    state.log("ENRICHMENT", "COMPLETED")

    return bool(missing)
