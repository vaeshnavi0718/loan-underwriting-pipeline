"""
Generates 10 synthetic loan applications (APP-001..APP-010) under
data/synthetic_applications/. All data is fake. No real applicant,
bureau, employment, or banking data is used anywhere in this project.

Each application folder gets:
  application.json, pay_stub.pdf, bank_statement.pdf,
  credit_report.pdf, id_document.pdf
"""
import json
import os

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_applications")


def make_pdf(path: str, title: str, lines: list[str]) -> None:
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter
    y = height - 72
    c.setFont("Helvetica-Bold", 14)
    c.drawString(72, y, title)
    y -= 30
    c.setFont("Helvetica", 11)
    for line in lines:
        c.drawString(72, y, line)
        y -= 20
    c.save()


APPLICATIONS = [
    dict(
        id="APP-001",
        scenario="Strong applicant",
        applicant_name="Jordan Price",
        requested_amount=15000,
        loan_purpose="Debt consolidation",
        employment_status="Employed full-time",
        employer_name="Cascade Logistics Inc.",
        gross_monthly_income=7200,
        average_monthly_balance=9400,
        monthly_deposits=7150,
        credit_score=782,
        existing_monthly_debt=650,
        payment_history="No late payments in 24 months",
        dob="1988-03-14",
        id_status="verified",
    ),
    dict(
        id="APP-002",
        scenario="High debt-to-income",
        applicant_name="Morgan Ellis",
        requested_amount=25000,
        loan_purpose="Home improvement",
        employment_status="Employed full-time",
        employer_name="Northbridge Manufacturing",
        gross_monthly_income=5100,
        average_monthly_balance=2100,
        monthly_deposits=5050,
        credit_score=701,
        existing_monthly_debt=2850,
        payment_history="No late payments in 24 months",
        dob="1979-11-02",
        id_status="verified",
    ),
    dict(
        id="APP-003",
        scenario="Low credit score",
        applicant_name="Casey Nolan",
        requested_amount=10000,
        loan_purpose="Auto repair",
        employment_status="Employed full-time",
        employer_name="Riverstone Retail",
        gross_monthly_income=4300,
        average_monthly_balance=1300,
        monthly_deposits=4250,
        credit_score=571,
        existing_monthly_debt=780,
        payment_history="2 payments 30+ days late in last 12 months",
        dob="1995-06-21",
        id_status="verified",
    ),
    dict(
        id="APP-004",
        scenario="Missing information (no bank statement uploaded)",
        applicant_name="Riley Thompson",
        requested_amount=12000,
        loan_purpose="Medical expenses",
        employment_status="Employed full-time",
        employer_name="Union Health Partners",
        gross_monthly_income=6000,
        average_monthly_balance=None,
        monthly_deposits=None,
        credit_score=690,
        existing_monthly_debt=900,
        payment_history="No late payments in 24 months",
        dob="1990-01-09",
        id_status="verified",
        skip_docs=["bank_statement"],
    ),
    dict(
        id="APP-005",
        scenario="Income discrepancy (pay stub vs. bank deposits mismatch)",
        applicant_name="Avery Kim",
        requested_amount=18000,
        loan_purpose="Debt consolidation",
        employment_status="Employed full-time",
        employer_name="Delta Freight Co.",
        gross_monthly_income=8000,
        average_monthly_balance=3200,
        monthly_deposits=3100,  # far below stated gross income
        credit_score=715,
        existing_monthly_debt=1100,
        payment_history="No late payments in 24 months",
        dob="1985-09-30",
        id_status="verified",
    ),
    dict(
        id="APP-006",
        scenario="Unverified ID document",
        applicant_name="Drew Sanders",
        requested_amount=9000,
        loan_purpose="Auto purchase",
        employment_status="Employed full-time",
        employer_name="Bright Path Consulting",
        gross_monthly_income=5400,
        average_monthly_balance=4200,
        monthly_deposits=5350,
        credit_score=730,
        existing_monthly_debt=600,
        payment_history="No late payments in 24 months",
        dob="1992-04-17",
        id_status="not_verified",
    ),
    dict(
        id="APP-007",
        scenario="Borderline, needs manual review",
        applicant_name="Sam Whitfield",
        requested_amount=20000,
        loan_purpose="Small business",
        employment_status="Employed full-time",
        employer_name="Harborline Freight",
        gross_monthly_income=5600,
        average_monthly_balance=2600,
        monthly_deposits=5550,
        credit_score=648,
        existing_monthly_debt=1900,
        payment_history="1 payment 30+ days late in last 12 months",
        dob="1983-12-05",
        id_status="verified",
    ),
    dict(
        id="APP-008",
        scenario="Self-employed, volatile cash flow",
        applicant_name="Taylor Brooks",
        requested_amount=14000,
        loan_purpose="Business equipment",
        employment_status="Self-employed",
        employer_name="Brooks Creative Studio (self-employed)",
        gross_monthly_income=6200,
        average_monthly_balance=1450,
        monthly_deposits=3900,  # volatile / lower than claimed
        credit_score=705,
        existing_monthly_debt=1200,
        payment_history="No late payments in 24 months",
        dob="1991-07-23",
        id_status="verified",
    ),
    dict(
        id="APP-009",
        scenario="Large loan relative to income (exposure risk)",
        applicant_name="Jamie Ortiz",
        requested_amount=60000,
        loan_purpose="Debt consolidation",
        employment_status="Employed full-time",
        employer_name="Fieldstone Insurance Group",
        gross_monthly_income=5000,
        average_monthly_balance=3000,
        monthly_deposits=4950,
        credit_score=712,
        existing_monthly_debt=950,
        payment_history="No late payments in 24 months",
        dob="1987-02-28",
        id_status="verified",
    ),
    dict(
        id="APP-010",
        scenario="Thin credit file, young applicant",
        applicant_name="Peyton Reyes",
        requested_amount=6000,
        loan_purpose="Education",
        employment_status="Employed part-time",
        employer_name="Campus Grounds Cafe",
        gross_monthly_income=2100,
        average_monthly_balance=800,
        monthly_deposits=2050,
        credit_score=None,  # thin file: no score on record yet
        existing_monthly_debt=150,
        payment_history="Insufficient history to establish a pattern",
        dob="2003-05-11",
        id_status="verified",
    ),
]


def build_application(app: dict) -> None:
    app_dir = os.path.join(BASE_DIR, app["id"])
    os.makedirs(app_dir, exist_ok=True)
    skip_docs = set(app.get("skip_docs", []))

    application_json = {
        "application_id": app["id"],
        "applicant_name": app["applicant_name"],
        "requested_amount": app["requested_amount"],
        "loan_purpose": app["loan_purpose"],
        "employment_status": app["employment_status"],
        "_scenario_note": app["scenario"],  # for humans browsing the fixtures only
    }
    with open(os.path.join(app_dir, "application.json"), "w") as f:
        json.dump(application_json, f, indent=2)

    if "pay_stub" not in skip_docs:
        make_pdf(
            os.path.join(app_dir, "pay_stub.pdf"),
            "Synthetic Pay Stub",
            [
                f"Application ID: {app['id']}",
                f"Employee Name: {app['applicant_name']}",
                f"Employer Name: {app['employer_name']}",
                f"Gross Monthly Income: ${app['gross_monthly_income']:,.2f}",
                "Pay Period: Monthly",
                "-- This document contains entirely synthetic data. --",
            ],
        )

    if "bank_statement" not in skip_docs and app["average_monthly_balance"] is not None:
        make_pdf(
            os.path.join(app_dir, "bank_statement.pdf"),
            "Synthetic Bank Statement",
            [
                f"Application ID: {app['id']}",
                f"Account Holder: {app['applicant_name']}",
                f"Average Monthly Balance: ${app['average_monthly_balance']:,.2f}",
                f"Monthly Deposits: ${app['monthly_deposits']:,.2f}",
                "-- This document contains entirely synthetic data. --",
            ],
        )

    if "credit_report" not in skip_docs:
        score_line = (
            f"Credit Score: {app['credit_score']}"
            if app["credit_score"] is not None
            else "Credit Score: NO SCORE ON FILE (thin file)"
        )
        make_pdf(
            os.path.join(app_dir, "credit_report.pdf"),
            "Synthetic Credit Report",
            [
                f"Application ID: {app['id']}",
                f"Name: {app['applicant_name']}",
                score_line,
                f"Existing Monthly Debt Payments: ${app['existing_monthly_debt']:,.2f}",
                f"Payment History: {app['payment_history']}",
                "-- This document contains entirely synthetic data. --",
            ],
        )

    if "id_document" not in skip_docs:
        make_pdf(
            os.path.join(app_dir, "id_document.pdf"),
            "Synthetic ID Document",
            [
                f"Application ID: {app['id']}",
                f"Name: {app['applicant_name']}",
                f"Date of Birth: {app['dob']}",
                f"ID Status: {app['id_status']}",
                "-- This document contains entirely synthetic data. --",
            ],
        )


def main():
    os.makedirs(BASE_DIR, exist_ok=True)
    for app in APPLICATIONS:
        build_application(app)
        print(f"Built {app['id']}: {app['scenario']}")


if __name__ == "__main__":
    main()
