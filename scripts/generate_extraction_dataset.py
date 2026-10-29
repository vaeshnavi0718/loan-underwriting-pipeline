"""
Generates the Phase 2 extraction dataset under data/extraction/: synthetic
PDFs across the four document types, about 8 layouts each, plus
labels.jsonl with the true field values. All data is fake.

Each document's true values are sampled first and then drawn in one
layout, so the labels are exact by construction. Layouts vary the labels,
structure, number and date formats, add distractor values (YTD totals,
net pay, annual salary) and sometimes leave a field out (label: null).

The same seed always gives the same dataset, so only this script and
labels.jsonl are committed, not the PDFs.

    python scripts/generate_extraction_dataset.py [--seed 7] [--per-type 375]
"""
import argparse
import json
import os
import random
from datetime import date, timedelta

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "extraction")

# The fields each document type is labeled with; same names the Document Agent returns.
FIELDS = {
    "pay_stub": ["employer_name", "gross_monthly_income"],
    "bank_statement": ["average_monthly_balance", "monthly_deposits"],
    "credit_report": ["credit_score", "existing_monthly_debt", "payment_history"],
    "id_document": ["name", "date_of_birth", "id_status"],
}
DOC_PREFIX = {"pay_stub": "PS", "bank_statement": "BS", "credit_report": "CR", "id_document": "ID"}
MISSING_RATE = 0.10  # share of documents that leave one field out

FIRST = ["Jordan", "Morgan", "Casey", "Riley", "Avery", "Drew", "Sam", "Taylor", "Jamie",
         "Peyton", "Alex", "Quinn", "Rowan", "Skyler", "Emerson", "Hayden", "Reese", "Blake"]
LAST = ["Price", "Ellis", "Nolan", "Thompson", "Kim", "Sanders", "Whitfield", "Brooks",
        "Ortiz", "Reyes", "Patel", "Nguyen", "Okafor", "Lindqvist", "Moreau", "Haddad"]
ORG_A = ["Cascade", "Northbridge", "Riverstone", "Delta", "Harborline", "Fieldstone",
         "Bright Path", "Summit", "Ironwood", "Bluewater", "Granite", "Pioneer", "Evergreen"]
ORG_B = ["Logistics", "Manufacturing", "Retail", "Health Partners", "Freight", "Insurance Group",
         "Consulting", "Software", "Foods", "Energy", "Construction", "Labs"]
ORG_C = ["Inc.", "LLC", "Co.", "Corp.", "Group", ""]
BANKS = ["First Harbor Bank", "Prairie Federal Credit Union", "Lakeside Savings", "Union Trust Bank",
         "Copperline Bank", "Meridian Community Bank", "Westgate Financial"]
BUREAUS = ["Equifax", "Experian", "TransUnion"]
HISTORIES = ["No late payments in 24 months", "No late payments in 12 months",
             "1 payment 30+ days late in last 12 months", "2 payments 30+ days late in last 12 months",
             "1 payment 60+ days late in last 24 months", "3 payments 30+ days late in last 24 months"]
CREDITORS = ["Auto loan", "Student loan", "Credit card", "Personal loan", "Store card", "Mortgage"]
STATES = ["Ohio", "Texas", "Oregon", "Georgia", "Arizona", "Michigan", "Colorado", "Virginia"]
ROLES = ["Operations Associate", "Analyst", "Technician", "Account Manager", "Nurse",
         "Warehouse Lead", "Engineer", "Sales Representative"]


# ---------- formatting ----------

def money(v: float, style: str) -> str:
    if style == "no_cents" and v != int(v):
        style = "us"  # never round a value away from its label
    us = f"{v:,.2f}"
    return {
        "us": f"${us}",
        "plain": f"{v:.2f}",
        "usd": f"USD {us}",
        "no_cents": f"${v:,.0f}",
        "eu": us.replace(",", " ").replace(".", ",").replace(" ", ".") + " USD",
    }[style]


def fmt_date(d: date, style: str) -> str:
    return {
        "iso": d.isoformat(),
        "us": d.strftime("%m/%d/%Y"),
        "short": d.strftime("%d %b %Y"),
        "long": d.strftime("%B %d, %Y").replace(" 0", " "),
    }[style]


class Page:
    """A one-page PDF with a moving cursor."""

    def __init__(self, path: str):
        self.c = canvas.Canvas(path, pagesize=letter)
        self.y = letter[1] - 72

    def text(self, s: str, x: float = 72, size: int = 11, bold: bool = False, step: int = 18):
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.drawString(x, self.y, s)
        self.y -= step

    def row(self, cells, xs=(72, 300, 430), size: int = 10, bold: bool = False, step: int = 16):
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        for x, s in zip(xs, cells):
            if s:
                self.c.drawString(x, self.y, s)
        self.y -= step

    def rule(self):
        self.c.line(72, self.y + 10, 540, self.y + 10)
        self.y -= 6

    def gap(self, n: int = 10):
        self.y -= n

    def save(self):
        self.c.setFont("Helvetica-Oblique", 8)
        self.c.drawString(72, 40, "This document contains entirely synthetic data.")
        self.c.save()


# ---------- pay stub ----------

def sample_pay_stub(rng: random.Random) -> tuple[dict, dict]:
    annual = rng.randrange(24_000, 150_000, 250)
    gross = round(annual / 12, 2)
    net = round(gross * rng.uniform(0.66, 0.80), 2)
    month = rng.randint(1, 12)
    truth = {
        "employer_name": " ".join(filter(None, [rng.choice(ORG_A), rng.choice(ORG_B), rng.choice(ORG_C)])),
        "gross_monthly_income": gross,
    }
    extra = {
        "employee": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "annual": float(annual),
        "net": net,
        "fed_tax": round((gross - net) * 0.6, 2),
        "state_tax": round((gross - net) * 0.4, 2),
        "ytd_gross": round(gross * month, 2),
        "ytd_net": round(net * month, 2),
        "pay_date": date(2026, month, 1) + timedelta(days=rng.randint(24, 27)),
        "role": rng.choice(ROLES),
        "since": rng.randint(2008, 2025),
        "hours": rng.choice([160, 168, 173.33, 176]),
    }
    return truth, extra


def ps_legacy(p, t, x, rng):
    # the original generator's format, which the regex parser was written for
    p.text("Synthetic Pay Stub", size=14, bold=True, step=30)
    p.text(f"Employee Name: {x['employee']}", step=20)
    if t["employer_name"]:
        p.text(f"Employer Name: {t['employer_name']}", step=20)
    if t["gross_monthly_income"] is not None:
        p.text(f"Gross Monthly Income: {money(t['gross_monthly_income'], 'us')}", step=20)
    p.text("Pay Period: Monthly", step=20)


def ps_key_value(p, t, x, rng):
    m = rng.choice(["us", "no_cents", "usd"])
    p.text("EARNINGS STATEMENT", size=14, bold=True, step=28)
    p.text(f"Employee: {x['employee']}")
    if t["employer_name"]:
        p.text(f"Employer: {t['employer_name']}")
    p.text(f"Pay Date: {fmt_date(x['pay_date'], rng.choice(['us', 'iso']))}")
    p.text("Pay Frequency: Monthly")
    p.gap()
    if t["gross_monthly_income"] is not None:
        p.text(f"Gross Pay: {money(t['gross_monthly_income'], m)}")
    p.text(f"Federal Income Tax: {money(x['fed_tax'], m)}")
    p.text(f"State Income Tax: {money(x['state_tax'], m)}")
    p.text(f"Net Pay: {money(x['net'], m)}", bold=True)


def ps_ytd_table(p, t, x, rng):
    m = rng.choice(["us", "plain"])
    p.text("Payroll Advice", size=14, bold=True, step=26)
    if t["employer_name"]:
        p.text(f"Company: {t['employer_name']}", size=10, step=14)
    p.text(f"Employee: {x['employee']}    Period: {x['pay_date'].strftime('%B %Y')}", size=10, step=24)
    p.row(["Earnings", "Current", "Year to Date"], bold=True)
    p.rule()
    if t["gross_monthly_income"] is not None:
        p.row(["Regular Salary", money(t["gross_monthly_income"], m), money(x["ytd_gross"], m)])
        p.row(["Gross Earnings", money(t["gross_monthly_income"], m), money(x["ytd_gross"], m)], bold=True)
    p.gap(8)
    p.row(["Deductions", "Current", "Year to Date"], bold=True)
    p.rule()
    p.row(["Federal Tax", money(x["fed_tax"], m), ""])
    p.row(["State Tax", money(x["state_tax"], m), ""])
    p.row(["Net Pay", money(x["net"], m), money(x["ytd_net"], m)], bold=True)


def ps_stacked(p, t, x, rng):
    m = rng.choice(["usd", "us"])
    p.text("Wage Statement", size=16, bold=True, step=32)
    for label, value in [
        ("Employee", x["employee"]),
        ("Employing Organization", t["employer_name"]),
        ("Statement Date", fmt_date(x["pay_date"], rng.choice(["long", "short"]))),
        ("Monthly Gross Wages",
         money(t["gross_monthly_income"], m) if t["gross_monthly_income"] is not None else None),
        ("Amount Deposited", money(x["net"], m)),
    ]:
        if value is None:
            continue
        p.text(label, size=9, bold=True, step=13)
        p.text(value, size=12, step=22)


def ps_letterhead(p, t, x, rng):
    # employer appears only as the letterhead, with no label
    m = rng.choice(["us", "no_cents"])
    if t["employer_name"]:
        p.text(t["employer_name"], size=18, bold=True, step=16)
        p.text(f"{rng.randint(100, 9899)} Commerce Way, Suite {rng.randint(100, 900)}", size=9, step=30)
    p.text("Statement of Earnings", size=13, bold=True, step=22)
    p.text(f"Prepared for {x['employee']} on {fmt_date(x['pay_date'], 'short')}", size=10, step=24)
    p.row(["Description", "Amount"], xs=(72, 380), bold=True)
    p.rule()
    if t["gross_monthly_income"] is not None:
        p.row(["Base pay (monthly)", money(t["gross_monthly_income"], m)], xs=(72, 380))
    p.row(["Taxes withheld", money(round(x["fed_tax"] + x["state_tax"], 2), m)], xs=(72, 380))
    p.row(["Take-home pay", money(x["net"], m)], xs=(72, 380), bold=True)


def ps_letter(p, t, x, rng):
    # income verification letter: values in sentences, annual salary as a distractor
    p.text("Employment and Income Verification", size=14, bold=True, step=30)
    p.text(fmt_date(x["pay_date"], "long"), size=10, step=24)
    p.text("To whom it may concern,", step=22)
    who = f"employed by {t['employer_name']}" if t["employer_name"] else "employed with our organization"
    lines = [
        f"This letter confirms that {x['employee']} is {who}",
        f"as a full-time {x['role']} since {x['since']}.",
    ]
    if t["gross_monthly_income"] is not None:
        lines += [
            f"Their gross monthly income is {money(t['gross_monthly_income'], 'us')} before taxes",
            f"and deductions, based on an annual base salary of {money(x['annual'], 'no_cents')}.",
        ]
    for s in lines:
        p.text(s, step=17)
    p.gap(14)
    p.text("Sincerely,", step=17)
    p.text("Human Resources Department", step=17)


def ps_hours_rate(p, t, x, rng):
    # terse payroll codes; the hourly rate is a distractor
    gross = t["gross_monthly_income"]
    p.text("PAY SUMMARY", size=13, bold=True, step=22)
    if t["employer_name"]:
        p.text(f"EMPR: {t['employer_name'].upper()}", size=10, step=14)
    p.text(f"EE: {x['employee'].upper()}   PER END: {fmt_date(x['pay_date'], 'us')}   FREQ: MO", size=10, step=24)
    xs = (72, 220, 320, 430)
    p.row(["CODE", "HRS", "RATE", "AMOUNT"], xs=xs, bold=True)
    p.rule()
    if gross is not None:
        p.row(["REG", f"{x['hours']:.2f}", f"{gross / x['hours']:.4f}", money(gross, "plain")], xs=xs)
        p.row(["GROSS", "", "", money(gross, "plain")], xs=xs, bold=True)
    p.row(["FIT", "", "", f"-{money(x['fed_tax'], 'plain')}"], xs=xs)
    p.row(["SIT", "", "", f"-{money(x['state_tax'], 'plain')}"], xs=xs)
    p.row(["NET", "", "", money(x["net"], "plain")], xs=xs, bold=True)


def ps_european(p, t, x, rng):
    # European number format (5.416,67) with YTD distractor
    p.text("Monthly Pay Slip", size=14, bold=True, step=26)
    if t["employer_name"]:
        p.text(f"Employer / Company name: {t['employer_name']}")
    p.text(f"Employee: {x['employee']}")
    p.text(f"Pay date: {fmt_date(x['pay_date'], 'short')}", step=26)
    if t["gross_monthly_income"] is not None:
        p.text(f"Gross monthly salary ........ {money(t['gross_monthly_income'], 'eu')}")
        p.text(f"Gross salary YTD ............ {money(x['ytd_gross'], 'eu')}")
    p.text(f"Net salary .................. {money(x['net'], 'eu')}")


# ---------- bank statement ----------

def _split(total_cents: int, n: int, rng: random.Random) -> list[float]:
    # n positive amounts that sum exactly to total_cents
    cuts = sorted(rng.sample(range(1, total_cents), n - 1))
    return [(b - a) / 100 for a, b in zip([0] + cuts, cuts + [total_cents])]


def sample_bank_statement(rng: random.Random) -> tuple[dict, dict]:
    deposits_c = rng.randrange(150_000, 1_500_000)
    avg_c = rng.randrange(50_000, 4_000_000)
    begin_c = max(1_000, avg_c + rng.randrange(-avg_c // 4, avg_c // 4 + 1))
    withdrawals_c = rng.randrange(deposits_c * 7 // 10, deposits_c * 11 // 10)
    end_c = max(500, begin_c + deposits_c - withdrawals_c)
    month = rng.randint(1, 12)
    start = date(2026, month, 1)
    n_dep = rng.randint(2, 4)
    truth = {
        "average_monthly_balance": avg_c / 100,
        "monthly_deposits": deposits_c / 100,
    }
    extra = {
        "holder": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "bank": rng.choice(BANKS),
        "account": f"****{rng.randint(1000, 9999)}",
        "begin": begin_c / 100,
        "end": end_c / 100,
        "withdrawals": (begin_c + deposits_c - end_c) / 100,
        "min_balance": round(min(begin_c, end_c) * rng.uniform(0.4, 0.9)) / 100,
        "interest": rng.randrange(1, 900) / 100,
        "credits": _split(deposits_c, n_dep, rng),
        "debits": _split(begin_c + deposits_c - end_c, rng.randint(3, 6), rng),
        "start": start,
        "end_date": start + timedelta(days=27),
        # previous months for the multi-month layout, as shares of the 3-month average
        "prev": [(rng.uniform(0.7, 1.3), rng.uniform(0.7, 1.3)) for _ in range(2)],
    }
    return truth, extra


def bs_legacy(p, t, x, rng):
    # the original generator's format, which the regex parser was written for
    p.text("Synthetic Bank Statement", size=14, bold=True, step=30)
    p.text(f"Account Holder: {x['holder']}", step=20)
    if t["average_monthly_balance"] is not None:
        p.text(f"Average Monthly Balance: {money(t['average_monthly_balance'], 'us')}", step=20)
    if t["monthly_deposits"] is not None:
        p.text(f"Monthly Deposits: {money(t['monthly_deposits'], 'us')}", step=20)


def bs_summary(p, t, x, rng):
    m = rng.choice(["us", "usd"])
    p.text(x["bank"], size=15, bold=True, step=20)
    p.text(f"Account {x['account']}  |  {x['holder']}", size=10, step=14)
    p.text(f"Statement period: {fmt_date(x['start'], 'us')} - {fmt_date(x['end_date'], 'us')}", size=10, step=26)
    p.text("Account Summary", size=12, bold=True, step=18)
    rows = [("Beginning Balance", x["begin"]), ("Deposits and Other Credits", t["monthly_deposits"]),
            ("Withdrawals and Other Debits", x["withdrawals"]), ("Ending Balance", x["end"]),
            ("Average Daily Balance", t["average_monthly_balance"]), ("Interest Earned", x["interest"])]
    for label, v in rows:
        if v is not None:
            p.row([label, money(v, m)], xs=(72, 380))


def bs_transactions(p, t, x, rng):
    # transaction list with a running balance; the true values are only in the footer totals
    p.text(f"{x['bank']} - Checking Statement", size=13, bold=True, step=20)
    p.text(f"{x['holder']}   Acct {x['account']}   {x['start'].strftime('%B %Y')}", size=10, step=24)
    xs = (72, 140, 330, 410, 480)
    p.row(["Date", "Description", "Credit", "Debit", "Balance"], xs=xs, bold=True)
    p.rule()
    bal = x["begin"]
    p.row([fmt_date(x["start"], "us")[:5], "Opening balance", "", "", f"{bal:,.2f}"], xs=xs, size=9)
    txns = [("credit", c, rng.choice(["Payroll deposit", "Direct dep", "Mobile check deposit", "Transfer in"]))
            for c in (x["credits"] if t["monthly_deposits"] is not None else [])]
    txns += [("debit", d, rng.choice(["Card purchase", "Rent payment", "Utility bill", "ATM withdrawal",
                                      "Online transfer", "Insurance"])) for d in x["debits"]]
    rng.shuffle(txns)
    for k, (kind, amt, desc) in enumerate(txns):
        bal = round(bal + amt if kind == "credit" else bal - amt, 2)
        day = x["start"] + timedelta(days=1 + k * 26 // len(txns))
        p.row([day.strftime("%m/%d"), desc, f"{amt:,.2f}" if kind == "credit" else "",
               f"{amt:,.2f}" if kind == "debit" else "", f"{bal:,.2f}"], xs=xs, size=9, step=14)
    p.rule()
    if t["monthly_deposits"] is not None:
        p.row(["", "Total credits", f"{t['monthly_deposits']:,.2f}"], xs=xs, size=9, bold=True)
    p.row(["", "Total debits", "", f"{x['withdrawals']:,.2f}"], xs=xs, size=9, bold=True)
    if t["average_monthly_balance"] is not None:
        p.row(["", "Average ledger balance", "", "", f"{t['average_monthly_balance']:,.2f}"], xs=xs, size=9, bold=True)


def bs_multi_month(p, t, x, rng):
    # three months side by side; the truth is the 3-month average row, the months are distractors
    p.text("Account Activity Overview", size=14, bold=True, step=22)
    p.text(f"{x['bank']}  -  {x['holder']}", size=10, step=24)
    xs = (72, 250, 400)
    p.row(["Month", "Total Deposits", "Average Balance"], xs=xs, bold=True)
    p.rule()
    # the current month is set so the three average to exactly the label (in cents)
    dep_avg = round((t["monthly_deposits"] or 0) * 100)
    bal_avg = round((t["average_monthly_balance"] or 0) * 100)
    dep = [round(dep_avg * f) for f, _ in x["prev"]]
    bal = [round(bal_avg * f) for _, f in x["prev"]]
    dep_c = dep_avg * 3 - sum(dep)
    bal_c = bal_avg * 3 - sum(bal)
    months = [(x["start"] - timedelta(days=62)).strftime("%b %Y"),
              (x["start"] - timedelta(days=31)).strftime("%b %Y"), x["start"].strftime("%b %Y")]
    for k, label in enumerate(months):
        d = dep[k] if k < 2 else dep_c
        b = bal[k] if k < 2 else bal_c
        p.row([label, money(d / 100, "us") if t["monthly_deposits"] is not None else "-",
               money(b / 100, "us") if t["average_monthly_balance"] is not None else "-"], xs=xs)
    p.rule()
    p.row(["3-month average",
           money(t["monthly_deposits"], "us") if t["monthly_deposits"] is not None else "-",
           money(t["average_monthly_balance"], "us") if t["average_monthly_balance"] is not None else "-"],
          xs=xs, bold=True)


def bs_stacked(p, t, x, rng):
    # mobile-app style: label above value
    m = rng.choice(["us", "no_cents"])
    p.text("Monthly Snapshot", size=16, bold=True, step=30)
    for label, value in [
        ("Account", f"{x['holder']} {x['account']}"),
        ("Period", f"{fmt_date(x['start'], 'short')} to {fmt_date(x['end_date'], 'short')}"),
        ("Money in", money(t["monthly_deposits"], m) if t["monthly_deposits"] is not None else None),
        ("Money out", money(x["withdrawals"], m)),
        ("Avg. balance", money(t["average_monthly_balance"], m) if t["average_monthly_balance"] is not None else None),
        ("Lowest balance", money(x["min_balance"], m)),
        ("Closing balance", money(x["end"], m)),
    ]:
        if value is None:
            continue
        p.text(label, size=9, bold=True, step=13)
        p.text(value, size=12, step=22)


def bs_european(p, t, x, rng):
    # European number format with opening/closing balances as distractors
    p.text("Account Statement", size=14, bold=True, step=26)
    p.text(f"Bank: {x['bank']}")
    p.text(f"Account holder: {x['holder']}")
    p.text(f"Period: {fmt_date(x['start'], 'short')} - {fmt_date(x['end_date'], 'short')}", step=26)
    p.text(f"Opening balance ............. {money(x['begin'], 'eu')}")
    if t["monthly_deposits"] is not None:
        p.text(f"Total credits ............... {money(t['monthly_deposits'], 'eu')}")
    p.text(f"Total debits ................ {money(x['withdrawals'], 'eu')}")
    p.text(f"Closing balance ............. {money(x['end'], 'eu')}")
    if t["average_monthly_balance"] is not None:
        p.text(f"Average balance ............. {money(t['average_monthly_balance'], 'eu')}")


def bs_codes(p, t, x, rng):
    # terse core-banking codes
    p.text("ACCT STMT", size=13, bold=True, step=22)
    p.text(f"CUST: {x['holder'].upper()}   ACCT: {x['account']}   CYC: {fmt_date(x['end_date'], 'iso')}", size=10, step=24)
    xs = (72, 300)
    p.row(["CODE", "AMOUNT"], xs=xs, bold=True)
    p.rule()
    for code, v in [("BEG BAL", x["begin"]), ("TOT DEP", t["monthly_deposits"]), ("TOT WD", x["withdrawals"]),
                    ("END BAL", x["end"]), ("MIN BAL", x["min_balance"]), ("AVG BAL", t["average_monthly_balance"]),
                    ("INT PD", x["interest"])]:
        if v is not None:
            p.row([code, money(v, "plain")], xs=xs)


def bs_letter(p, t, x, rng):
    # bank reference letter: values in sentences
    p.text(x["bank"], size=16, bold=True, step=30)
    p.text(fmt_date(x["end_date"], "long"), size=10, step=24)
    p.text("Re: Account verification", bold=True, step=22)
    lines = [f"We confirm that {x['holder']} holds checking account {x['account']} with us",
             "and that the account is in good standing, with a current balance",
             f"of {money(x['end'], 'us')}."]
    if t["average_monthly_balance"] is not None:
        lines += ["Over the last month the account maintained an average balance",
                  f"of {money(t['average_monthly_balance'], 'us')}."]
    if t["monthly_deposits"] is not None:
        lines.append(f"Deposits for the month totaled {money(t['monthly_deposits'], 'us')}.")
    for s in lines:
        p.text(s, size=10, step=17)
    p.gap(14)
    p.text("Sincerely,", step=17)
    p.text("Branch Operations", step=17)


# ---------- credit report ----------

def sample_credit_report(rng: random.Random) -> tuple[dict, dict]:
    score = rng.randint(520, 820)
    debt_c = rng.randrange(5_000, 350_000)
    n_acct = rng.randint(2, 4)
    truth = {
        "credit_score": score,
        "existing_monthly_debt": debt_c / 100,
        "payment_history": rng.choice(HISTORIES),
    }
    accounts = [(rng.choice(CREDITORS), amt, round(amt * rng.uniform(8, 60), 2))
                for amt in _split(debt_c, n_acct, rng)]
    extra = {
        "person": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "bureau": rng.choice(BUREAUS),
        "report_date": date(2026, rng.randint(1, 12), rng.randint(1, 28)),
        "accounts": accounts,  # (type, monthly payment, balance); payments sum to the debt
        "total_balance": round(sum(a[2] for a in accounts), 2),
        "utilization": rng.randint(4, 85),
        "inquiries": rng.randint(0, 6),
        # other bureaus' scores and past scores are distractors; the true score is the middle one
        "other_scores": sorted([score - rng.randint(1, 25), score + rng.randint(1, 25)]),
        "past_scores": [score + rng.randint(-40, 40) for _ in range(3)],
    }
    return truth, extra


def cr_legacy(p, t, x, rng):
    # the original generator's format, which the regex parser was written for
    p.text("Synthetic Credit Report", size=14, bold=True, step=30)
    p.text(f"Name: {x['person']}", step=20)
    if t["credit_score"] is not None:
        p.text(f"Credit Score: {t['credit_score']}", step=20)
    if t["existing_monthly_debt"] is not None:
        p.text(f"Existing Monthly Debt Payments: {money(t['existing_monthly_debt'], 'us')}", step=20)
    if t["payment_history"]:
        p.text(f"Payment History: {t['payment_history']}", step=20)


def cr_bureau(p, t, x, rng):
    # score box with the 300-850 range and utilization as distractor numbers
    p.text(f"{x['bureau']} Consumer Credit File", size=14, bold=True, step=20)
    p.text(f"Consumer: {x['person']}    Report date: {fmt_date(x['report_date'], 'us')}", size=10, step=26)
    if t["credit_score"] is not None:
        p.text(f"FICO Score 8: {t['credit_score']}  (range 300-850)", size=13, bold=True, step=22)
    p.text(f"Revolving utilization: {x['utilization']}%    Hard inquiries (12 mo): {x['inquiries']}", size=10, step=20)
    if t["existing_monthly_debt"] is not None:
        p.text(f"Total scheduled monthly payments: {money(t['existing_monthly_debt'], 'us')}", size=10, step=20)
    p.text(f"Total balances: {money(x['total_balance'], 'us')}", size=10, step=20)
    if t["payment_history"]:
        p.text(f"Delinquency summary: {t['payment_history']}", size=10, step=20)


def cr_tradelines(p, t, x, rng):
    # account table; the true debt is the total row, the per-account payments and balances are distractors
    p.text("Credit Report - Account Detail", size=13, bold=True, step=20)
    p.text(f"{x['person']}  |  Source: {x['bureau']}", size=10, step=14)
    if t["credit_score"] is not None:
        p.text(f"Score: {t['credit_score']}", size=10, step=24)
    xs = (72, 230, 360, 460)
    p.row(["Account", "Balance", "Monthly Payment", "Status"], xs=xs, bold=True)
    p.rule()
    for kind, pay, bal in x["accounts"]:
        p.row([kind, money(bal, "us"), money(pay, "us"), "Open"], xs=xs, size=9, step=14)
    p.rule()
    if t["existing_monthly_debt"] is not None:
        p.row(["Total", money(x["total_balance"], "us"), money(t["existing_monthly_debt"], "us"), ""], xs=xs, bold=True)
    p.gap(10)
    if t["payment_history"]:
        p.text(f"Payment record: {t['payment_history']}", size=10)


def cr_stacked(p, t, x, rng):
    m = rng.choice(["us", "no_cents"])
    p.text("Your Credit at a Glance", size=16, bold=True, step=30)
    for label, value in [
        ("Name", x["person"]),
        ("Credit score", str(t["credit_score"]) if t["credit_score"] is not None else None),
        ("Score change since last report", f"{t['credit_score'] - x['past_scores'][-1]:+d}" if t["credit_score"] else None),
        ("Monthly debt obligations",
         money(t["existing_monthly_debt"], m) if t["existing_monthly_debt"] is not None else None),
        ("Open accounts", str(len(x["accounts"]))),
        ("On-time payments", t["payment_history"]),
    ]:
        if value is None:
            continue
        p.text(label, size=9, bold=True, step=13)
        p.text(value, size=12, step=22)


def cr_tri_merge(p, t, x, rng):
    # three bureau scores; lenders use the middle one, which is the label
    p.text("Tri-Merge Credit Report", size=14, bold=True, step=22)
    p.text(f"Borrower: {x['person']}   Date: {fmt_date(x['report_date'], 'short')}", size=10, step=24)
    if t["credit_score"] is not None:
        scores = [x["other_scores"][0], t["credit_score"], x["other_scores"][1]]
        order = BUREAUS[:]
        rng.shuffle(order)
        shown = dict(zip(order, rng.sample(scores, 3)))
        p.row(["Bureau", "Score"], xs=(72, 250), bold=True)
        p.rule()
        for b in BUREAUS:
            p.row([b, str(shown[b])], xs=(72, 250))
        p.row(["Representative (middle) score", str(t["credit_score"])], xs=(72, 250), bold=True)
        p.gap(8)
    if t["existing_monthly_debt"] is not None:
        p.text(f"Monthly liabilities: {money(t['existing_monthly_debt'], 'usd')}", size=10)
    if t["payment_history"]:
        p.text(f"Late payment history: {t['payment_history']}", size=10)


def cr_codes(p, t, x, rng):
    p.text("CR SUMMARY", size=13, bold=True, step=22)
    p.text(f"SUBJ: {x['person'].upper()}   SRC: {x['bureau'].upper()}   DT: {fmt_date(x['report_date'], 'iso')}", size=10, step=24)
    xs = (72, 220)
    for code, v in [("SCR", t["credit_score"]), ("UTIL", f"{x['utilization']}%"), ("INQ", x["inquiries"]),
                    ("TOT BAL", money(x["total_balance"], "plain")),
                    ("MO PMT", money(t["existing_monthly_debt"], "plain") if t["existing_monthly_debt"] is not None else None),
                    ("DELQ", t["payment_history"])]:
        if v is not None:
            p.row([code, str(v)], xs=xs)


def cr_letter(p, t, x, rng):
    p.text("Credit Review Summary", size=14, bold=True, step=30)
    p.text(fmt_date(x["report_date"], "long"), size=10, step=24)
    lines = [f"We reviewed the {x['bureau']} credit file for {x['person']}."]
    if t["credit_score"] is not None:
        lines.append(f"The applicant's current credit score is {t['credit_score']} on a 300 to 850 scale.")
    if t["existing_monthly_debt"] is not None:
        lines += [f"Existing obligations require {money(t['existing_monthly_debt'], 'us')} per month across",
                  f"{len(x['accounts'])} open accounts with combined balances of {money(x['total_balance'], 'us')}."]
    if t["payment_history"]:
        lines.append(f"Payment history: {t['payment_history'].lower()}.")
    for s in lines:
        p.text(s, size=10, step=17)
    p.gap(14)
    p.text("Underwriting Support", step=17)


def cr_score_trend(p, t, x, rng):
    # score history; only the most recent row is the label
    p.text("Credit Monitoring Report", size=14, bold=True, step=22)
    p.text(f"Member: {x['person']}", size=10, step=24)
    xs = (72, 250)
    p.row(["Date", "Score"], xs=xs, bold=True)
    p.rule()
    for k, past in enumerate(x["past_scores"]):
        p.row([fmt_date(x["report_date"] - timedelta(days=90 * (3 - k)), "us"), str(past)], xs=xs)
    if t["credit_score"] is not None:
        p.row([f"{fmt_date(x['report_date'], 'us')} (current)", str(t["credit_score"])], xs=xs, bold=True)
    p.gap(10)
    if t["existing_monthly_debt"] is not None:
        p.text(f"Minimum payments due monthly: {money(t['existing_monthly_debt'], 'us')}", size=10)
    if t["payment_history"]:
        p.text(f"History: {t['payment_history']}", size=10)


# ---------- ID document ----------

def sample_id_document(rng: random.Random) -> tuple[dict, dict]:
    dob = date(rng.randint(1955, 2004), rng.randint(1, 12), rng.randint(1, 28))
    issued = date(rng.randint(2019, 2025), rng.randint(1, 12), rng.randint(1, 28))
    truth = {
        "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "date_of_birth": dob.isoformat(),
        "id_status": "verified" if rng.random() < 0.85 else "not_verified",
    }
    extra = {
        "dob": dob,
        "issued": issued,
        "expires": issued.replace(year=issued.year + 8),
        "checked": date(2026, rng.randint(1, 12), rng.randint(1, 28)),
        "number": f"{rng.choice('ABDKMSW')}{rng.randint(10_000_000, 99_999_999)}",
        "state": rng.choice(STATES),
        "address": f"{rng.randint(10, 9899)} {rng.choice(['Oak', 'Maple', 'Cedar', 'Lake', 'Hill'])} "
                   f"{rng.choice(['St', 'Ave', 'Rd', 'Dr'])}",
        "agent": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
    }
    return truth, extra


def status_text(status: str, style: str) -> str:
    words = "Verified" if status == "verified" else "Not Verified"
    return {"title": words, "upper": words.upper(), "lower": words.lower()}[style]


def id_legacy(p, t, x, rng):
    # the original generator's format, which the regex parser was written for
    p.text("Synthetic ID Document", size=14, bold=True, step=30)
    if t["name"]:
        p.text(f"Name: {t['name']}", step=20)
    if t["date_of_birth"]:
        p.text(f"Date of Birth: {t['date_of_birth']}", step=20)
    if t["id_status"]:
        p.text(f"ID Status: {t['id_status']}", step=20)


def id_license(p, t, x, rng):
    # driver license card; issue and expiry dates are distractors next to the DOB
    p.text(f"{x['state'].upper()} DRIVER LICENSE", size=14, bold=True, step=24)
    p.text(f"DL {x['number']}", size=10, step=18)
    if t["name"]:
        p.text(t["name"].upper(), size=12, bold=True, step=16)
    p.text(f"{x['address']}, {x['state']}", size=10, step=20)
    if t["date_of_birth"]:
        p.text(f"DOB {fmt_date(x['dob'], 'us')}", size=10, step=14)
    p.text(f"ISS {fmt_date(x['issued'], 'us')}    EXP {fmt_date(x['expires'], 'us')}", size=10, step=24)
    if t["id_status"]:
        p.text(f"Document check: {status_text(t['id_status'], 'upper')}", size=10)


def id_passport(p, t, x, rng):
    p.text("PASSPORT DATA PAGE", size=14, bold=True, step=24)
    for label, value in [
        ("Passport No.", x["number"]),
        ("Full name", t["name"]),
        ("Date of birth", fmt_date(x["dob"], "short") if t["date_of_birth"] else None),
        ("Date of issue", fmt_date(x["issued"], "short")),
        ("Date of expiry", fmt_date(x["expires"], "short")),
        ("Authenticity", status_text(t["id_status"], "title") if t["id_status"] else None),
    ]:
        if value is not None:
            p.row([label, value], xs=(72, 230))


def id_kyc_report(p, t, x, rng):
    # identity verification vendor result
    p.text("Identity Verification Result", size=14, bold=True, step=22)
    p.text(f"Check run {fmt_date(x['checked'], 'iso')} by {x['agent']}", size=10, step=24)
    xs = (72, 250)
    p.row(["Check", "Result"], xs=xs, bold=True)
    p.rule()
    if t["name"]:
        p.row(["Subject name", t["name"]], xs=xs)
    if t["date_of_birth"]:
        p.row(["Subject DOB", t["date_of_birth"]], xs=xs)
    p.row(["Document number", x["number"]], xs=xs)
    p.row(["Document expiry", fmt_date(x["expires"], "iso")], xs=xs)
    if t["id_status"]:
        p.row(["Overall status", status_text(t["id_status"], "upper")], xs=xs, bold=True)


def id_stacked(p, t, x, rng):
    p.text("Identity Card", size=16, bold=True, step=30)
    for label, value in [
        ("Holder", t["name"]),
        ("Born", fmt_date(x["dob"], "long") if t["date_of_birth"] else None),
        ("Issued", fmt_date(x["issued"], "long")),
        ("Valid until", fmt_date(x["expires"], "long")),
        ("Verification", status_text(t["id_status"], "title") if t["id_status"] else None),
    ]:
        if value is None:
            continue
        p.text(label, size=9, bold=True, step=13)
        p.text(value, size=12, step=22)


def id_european(p, t, x, rng):
    # day-first dates
    p.text("National Identity Document", size=14, bold=True, step=26)
    if t["name"]:
        p.text(f"Surname and given names: {t['name']}")
    if t["date_of_birth"]:
        p.text(f"Date of birth (DD.MM.YYYY): {x['dob'].strftime('%d.%m.%Y')}")
    p.text(f"Expiry (DD.MM.YYYY): {x['expires'].strftime('%d.%m.%Y')}")
    p.text(f"Document no.: {x['number']}")
    if t["id_status"]:
        p.text(f"Status: {status_text(t['id_status'], 'lower')}")


def id_codes(p, t, x, rng):
    p.text("IDV RECORD", size=13, bold=True, step=22)
    xs = (72, 200)
    for code, v in [("NM", t["name"].upper() if t["name"] else None),
                    ("DOB", x["dob"].strftime("%Y%m%d") if t["date_of_birth"] else None),
                    ("DOCNO", x["number"]), ("ISS", x["issued"].strftime("%Y%m%d")),
                    ("EXP", x["expires"].strftime("%Y%m%d")),
                    ("STAT", status_text(t["id_status"], "upper").replace(" ", "_") if t["id_status"] else None)]:
        if v is not None:
            p.row([code, v], xs=xs)


def id_letter(p, t, x, rng):
    p.text("Identity Verification Memo", size=14, bold=True, step=30)
    p.text(fmt_date(x["checked"], "long"), size=10, step=24)
    who = t["name"] or "the applicant"
    lines = [f"Reviewer {x['agent']} examined the identity document presented by {who}."]
    if t["date_of_birth"]:
        lines.append(f"The document shows a date of birth of {fmt_date(x['dob'], 'long')}.")
    lines.append(f"It was issued on {fmt_date(x['issued'], 'long')} and expires on {fmt_date(x['expires'], 'long')}.")
    if t["id_status"]:
        lines.append(f"Result: the document is {status_text(t['id_status'], 'lower')}.")
    for s in lines:
        p.text(s, size=10, step=17)


LAYOUTS = {
    "pay_stub": [ps_legacy, ps_key_value, ps_ytd_table, ps_stacked,
                 ps_letterhead, ps_letter, ps_hours_rate, ps_european],
    "bank_statement": [bs_legacy, bs_summary, bs_transactions, bs_multi_month,
                       bs_stacked, bs_european, bs_codes, bs_letter],
    "credit_report": [cr_legacy, cr_bureau, cr_tradelines, cr_stacked,
                      cr_tri_merge, cr_codes, cr_letter, cr_score_trend],
    "id_document": [id_legacy, id_license, id_passport, id_kyc_report,
                    id_stacked, id_european, id_codes, id_letter],
}
SAMPLERS = {"pay_stub": sample_pay_stub, "bank_statement": sample_bank_statement,
            "credit_report": sample_credit_report, "id_document": sample_id_document}


# ---------- driver ----------

def build_document(doc_type: str, i: int, seed: int, out_dir: str) -> dict:
    doc_id = f"{DOC_PREFIX[doc_type]}-{i:04d}"
    rng = random.Random(f"{seed}:{doc_id}")
    layout = LAYOUTS[doc_type][i % len(LAYOUTS[doc_type])]  # round-robin keeps layouts balanced
    truth, extra = SAMPLERS[doc_type](rng)
    missing = []
    if rng.random() < MISSING_RATE:
        missing = [rng.choice(FIELDS[doc_type])]
        truth[missing[0]] = None
    rel = f"docs/{doc_id}.pdf"
    page = Page(os.path.join(out_dir, rel))
    layout(page, truth, extra, rng)
    page.save()
    return {"doc_id": doc_id, "doc_type": doc_type, "layout": layout.__name__,
            "file": rel, "fields": truth, "missing": missing}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--per-type", type=int, default=375)
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    os.makedirs(os.path.join(args.out, "docs"), exist_ok=True)
    rows = [build_document(doc_type, i, args.seed, args.out)
            for doc_type in LAYOUTS for i in range(args.per_type)]
    with open(os.path.join(args.out, "labels.jsonl"), "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {len(rows)} documents to {os.path.normpath(args.out)}")


if __name__ == "__main__":
    main()
