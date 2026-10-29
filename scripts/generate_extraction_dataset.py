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
}
DOC_PREFIX = {"pay_stub": "PS", "bank_statement": "BS"}
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


LAYOUTS = {
    "pay_stub": [ps_legacy, ps_key_value, ps_ytd_table, ps_stacked,
                 ps_letterhead, ps_letter, ps_hours_rate, ps_european],
    "bank_statement": [bs_legacy, bs_summary, bs_transactions, bs_multi_month,
                       bs_stacked, bs_european, bs_codes, bs_letter],
}
SAMPLERS = {"pay_stub": sample_pay_stub, "bank_statement": sample_bank_statement}


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
