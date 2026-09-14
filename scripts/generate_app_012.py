"""One-off generator for APP-012. All data is synthetic.

Scenario: financials look clean (decent credit, low DTI, stable modest
income) but the ID document's date of birth makes the applicant 16 years
old as of the application date -- a compliance/identity inconsistency that
no rule-based agent checks for. This is meant to test whether the Review
and Reasoning Agent catches it purely from reasoning over the data.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from generate_synthetic_data import BASE_DIR, make_pdf  # noqa: E402

APP = dict(
    id="APP-012",
    scenario="Applicant age inconsistency (ID indicates a minor, born 2010)",
    applicant_name="Jordan Ashworth",
    requested_amount=5000,
    loan_purpose="Auto purchase",
    employment_status="Employed part-time",
    employer_name="Sunrise Cafe",
    gross_monthly_income=1800.00,
    average_monthly_balance=1200.00,
    monthly_deposits=1750.00,
    credit_score=690,
    existing_monthly_debt=50.00,
    payment_history="No late payments in 24 months",
    dob="2010-04-22",  # 16 years old as of 2026-09-14
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

    make_pdf(
        os.path.join(app_dir, "pay_stub.pdf"),
        "Synthetic Pay Stub",
        [
            f"Application ID: {APP['id']}",
            f"Employee Name: {APP['applicant_name']}",
            f"Employer Name: {APP['employer_name']}",
            f"Gross Monthly Income: ${APP['gross_monthly_income']:,.2f}",
            "Pay Period: Monthly",
            "-- This document contains entirely synthetic data. --",
        ],
    )

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
