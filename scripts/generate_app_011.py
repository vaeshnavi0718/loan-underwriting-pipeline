"""One-off generator for APP-011, added after the initial 10 fixtures.
Reuses the same make_pdf helper as generate_synthetic_data.py. All data
is synthetic."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from generate_synthetic_data import BASE_DIR, make_pdf  # noqa: E402

APP = dict(
    id="APP-011",
    scenario="Unemployed applicant, no pay stub (missing income documentation)",
    applicant_name="Reese Donovan",
    requested_amount=8000,
    loan_purpose="Personal expenses",
    employment_status="Unemployed",
    average_monthly_balance=4200.00,
    monthly_deposits=1200.00,  # irregular, reflects no steady employment income
    credit_score=655,
    existing_monthly_debt=300.00,
    payment_history="No late payments in 24 months",
    dob="1994-08-15",
    id_status="verified",
)


def main():
    app_dir = os.path.join(BASE_DIR, APP["id"])
    os.makedirs(app_dir, exist_ok=True)

    application_json = {
        "application_id": APP["id"],
        "applicant_name": APP["applicant_name"],
        "requested_amount": APP["requested_amount"],
        "loan_purpose": APP["loan_purpose"],
        "employment_status": APP["employment_status"],
        "_scenario_note": APP["scenario"],
    }
    with open(os.path.join(app_dir, "application.json"), "w") as f:
        json.dump(application_json, f, indent=2)

    # NOTE: pay_stub.pdf is intentionally NOT generated -- applicant is
    # unemployed and has no pay stub to provide. This should trigger
    # NEEDS_DOCUMENTATION via the missing-document path (distinct from
    # APP-004, which is missing its bank_statement instead).

    make_pdf(
        os.path.join(app_dir, "bank_statement.pdf"),
        "Synthetic Bank Statement",
        [
            f"Application ID: {APP['id']}",
            f"Account Holder: {APP['applicant_name']}",
            f"Average Monthly Balance: ${APP['average_monthly_balance']:,.2f}",
            f"Monthly Deposits: ${APP['monthly_deposits']:,.2f}",
            "-- This document contains entirely synthetic data. --",
        ],
    )

    make_pdf(
        os.path.join(app_dir, "credit_report.pdf"),
        "Synthetic Credit Report",
        [
            f"Application ID: {APP['id']}",
            f"Name: {APP['applicant_name']}",
            f"Credit Score: {APP['credit_score']}",
            f"Existing Monthly Debt Payments: ${APP['existing_monthly_debt']:,.2f}",
            f"Payment History: {APP['payment_history']}",
            "-- This document contains entirely synthetic data. --",
        ],
    )

    make_pdf(
        os.path.join(app_dir, "id_document.pdf"),
        "Synthetic ID Document",
        [
            f"Application ID: {APP['id']}",
            f"Name: {APP['applicant_name']}",
            f"Date of Birth: {APP['dob']}",
            f"ID Status: {APP['id_status']}",
            "-- This document contains entirely synthetic data. --",
        ],
    )

    print(f"Built {APP['id']}: {APP['scenario']}")


if __name__ == "__main__":
    main()
