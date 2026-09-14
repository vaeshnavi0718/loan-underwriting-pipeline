"""
Document Agent.

Extracts structured fields from each uploaded document and stores the
result in state.extracted_information, keyed by application_id (the state
object itself). Extraction is deterministic text parsing over the PDF text
-- no LLM call is needed or used here.
"""
import re

from app.harness.state import ApplicationState, Step
from app.tools.pdf_extract import extract_text

MONEY_RE = re.compile(r"\$?([\d,]+\.\d{2})")


def _money(pattern: str, text: str) -> float | None:
    m = re.search(pattern + r".*?" + MONEY_RE.pattern, text)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _field(pattern: str, text: str) -> str | None:
    m = re.search(pattern + r":\s*(.+)", text)
    return m.group(1).strip() if m else None


def parse_pay_stub(text: str) -> dict:
    return {
        "employer_name": _field(r"Employer Name", text),
        "gross_monthly_income": _money(r"Gross Monthly Income", text),
    }


def parse_bank_statement(text: str) -> dict:
    return {
        "average_monthly_balance": _money(r"Average Monthly Balance", text),
        "monthly_deposits": _money(r"Monthly Deposits", text),
    }


def parse_credit_report(text: str) -> dict:
    score_raw = _field(r"Credit Score", text)
    credit_score = None
    if score_raw and score_raw.strip().isdigit():
        credit_score = int(score_raw.strip())
    return {
        "credit_score": credit_score,
        "existing_monthly_debt": _money(r"Existing Monthly Debt Payments", text),
        "payment_history": _field(r"Payment History", text),
    }


def parse_id_document(text: str) -> dict:
    status = _field(r"ID Status", text)
    return {
        "name": _field(r"Name", text),
        "date_of_birth": _field(r"Date of Birth", text),
        "id_status": status.strip().lower() if status else None,
    }


PARSERS = {
    "pay_stub": parse_pay_stub,
    "bank_statement": parse_bank_statement,
    "credit_report": parse_credit_report,
    "id_document": parse_id_document,
}


def run(state: ApplicationState, document_paths: dict[str, str]) -> None:
    """document_paths: doc_type -> filesystem path of the uploaded PDF."""
    state.current_step = Step.DOCUMENT_EXTRACTION
    state.log("DOCUMENT_EXTRACTION", "STARTED", f"documents={list(document_paths)}")

    for doc_type, path in document_paths.items():
        parser = PARSERS.get(doc_type)
        if parser is None:
            state.log("DOCUMENT_EXTRACTION", "SKIPPED_UNKNOWN_DOC_TYPE", doc_type)
            continue
        try:
            text = extract_text(path)
            fields = parser(text)
            state.extracted_information[doc_type] = fields
            state.log("DOCUMENT_EXTRACTION", "EXTRACTED", f"{doc_type} -> {fields}")
        except Exception as exc:  # noqa: BLE001
            state.log("DOCUMENT_EXTRACTION", "ERROR", f"{doc_type}: {exc}")

    state.log("DOCUMENT_EXTRACTION", "COMPLETED")
