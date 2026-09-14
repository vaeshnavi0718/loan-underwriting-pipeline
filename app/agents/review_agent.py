"""
Review and Reasoning Agent.

The only agent that calls an LLM (Groq). It looks at extraction +
enrichment + risk assessment together and produces a structured,
human-readable report for the reviewer. It explicitly does NOT make or
recommend a final accept/deny decision -- that is the human's job at the
checkpoint. If the Groq call fails after retries, it falls back to a
deterministic template so the pipeline still reaches the human checkpoint.
"""
import json
import os

from dotenv import load_dotenv
from groq import Groq

from app.harness.state import ApplicationState, Step

load_dotenv()

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are the Review and Reasoning Agent inside an automated loan \
underwriting pipeline. You analyze the outputs of upstream agents (document \
extraction, data enrichment, and risk analysis) and produce a clear report \
for a HUMAN loan reviewer, who will make the actual accept/deny decision.

Your job is strictly analytical and explanatory. You must:
- Identify inconsistencies or discrepancies across the documents and data.
- Summarize the most important findings a reviewer needs to know.
- Explain the risk assessment in plain, non-technical language.
- Present the picture even-handedly, noting both strengths and concerns.

You must NOT:
- Recommend, imply, or state whether the application should be approved or denied.
- Use language like "I recommend approval" / "this should be denied" / "approve" / "reject".
- Invent facts not present in the provided data.

Respond with ONLY a JSON object matching this exact schema, no other text:
{
  "summary": "2-3 sentence neutral overview of the application",
  "key_findings": ["short bullet strings of the most important facts"],
  "inconsistencies": ["short bullet strings describing any discrepancies found, or an empty list if none"],
  "risk_explanation": "a plain-language paragraph explaining the risk assessment and why",
  "narrative_report": "a full multi-paragraph underwriting review report combining all of the above, written for a human reviewer to read top to bottom"
}"""


def build_user_prompt(application: dict, state: ApplicationState) -> str:
    payload = {
        "application": application,
        "extracted_information": state.extracted_information,
        "enrichment_results": state.enrichment_results,
        "missing_information": state.missing_information,
        "risk_assessment": state.risk_assessment,
    }
    return (
        "Here is the application data gathered so far. Produce the JSON report "
        "described in your instructions.\n\n" + json.dumps(payload, indent=2, default=str)
    )


def _fallback_report(application: dict, state: ApplicationState, error: str) -> dict:
    risk = state.risk_assessment
    return {
        "summary": (
            f"Application {application.get('application_id')} for "
            f"{application.get('applicant_name')} requesting "
            f"${application.get('requested_amount'):,}. Automated narrative "
            f"generation was unavailable; this is a fallback structured summary."
        ),
        "key_findings": [
            f"Overall risk level: {risk.get('overall_risk_level', 'unknown')}",
            f"DTI band: {risk.get('debt_to_income', {}).get('band', 'unknown')}",
            f"Credit risk band: {risk.get('credit_risk', {}).get('band', 'unknown')}",
        ],
        "inconsistencies": (
            ["Income discrepancy between pay stub and bank deposits"]
            if state.enrichment_results.get("income_discrepancy")
            else []
        ),
        "risk_explanation": (
            f"Risk assessment (fallback, LLM unavailable: {error}): {json.dumps(risk, default=str)}"
        ),
        "narrative_report": (
            f"[Fallback report -- Groq call failed: {error}]\n\n"
            f"Risk assessment: {json.dumps(risk, indent=2, default=str)}\n\n"
            f"Enrichment results: {json.dumps(state.enrichment_results, indent=2, default=str)}"
        ),
    }


def run(state: ApplicationState, application: dict, max_retries: int = 2) -> None:
    state.current_step = Step.REVIEW
    state.log("REVIEW", "STARTED")

    user_prompt = build_user_prompt(application, state)
    state.log("REVIEW", "PROMPT_BUILT", user_prompt[:500] + ("..." if len(user_prompt) > 500 else ""))

    api_key = os.environ.get("GROQ_API_KEY")
    last_error = None

    if api_key:
        client = Groq(api_key=api_key)
        for attempt in range(1, max_retries + 2):
            try:
                completion = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                )
                raw = completion.choices[0].message.content
                report = json.loads(raw)
                state.review_report = report
                state.log("REVIEW", "LLM_REPORT_GENERATED", f"attempt={attempt}")
                state.log("REVIEW", "COMPLETED")
                return
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                state.log("REVIEW", "LLM_CALL_FAILED", f"attempt={attempt}: {last_error}")
    else:
        last_error = "GROQ_API_KEY not set"
        state.log("REVIEW", "LLM_SKIPPED", last_error)

    state.review_report = _fallback_report(application, state, last_error or "unknown error")
    state.log("REVIEW", "FALLBACK_REPORT_USED", last_error or "")
    state.log("REVIEW", "COMPLETED")
