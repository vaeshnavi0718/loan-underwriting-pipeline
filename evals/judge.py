"""
Shared LLM judge for graders that need to understand meaning.

Design rules (see docs/ROADMAP.md, Phase 1):
- One yes/no question per call, never a 1-10 score.
- The judge sees the WHOLE report, every field.
- A "yes" must quote the report. The quote is then checked in code: a quote
  that isn't actually in the report makes the verdict "unsupported", so a
  judge can't pass or fail a report on text it made up.
- The judge is a different model family from the Review Agent
  (gpt-oss-120b), because models tend to grade their own family's writing
  too kindly.
- Answers are cached by (model, prompt), so re-grading saved reports
  costs nothing and gives the same verdicts.
"""
import hashlib
import json
import os
import re
import unicodedata
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen/qwen3.8-27b")
CACHE_PATH = os.path.join(os.path.dirname(__file__), ".judge_cache.json")
MAX_ATTEMPTS = 3

SYSTEM_PROMPT = (
    "You are a strict evaluator checking a loan underwriting report written by another model. "
    "Answer only the question asked, using only the report text. Reply with JSON only."
)

PROMPT_TEMPLATE = """QUESTION: {question}

Answer "yes" only if the report clearly says this; something merely implied or loosely related is "no".
If you answer "yes", copy the exact sentence or phrase from the report that shows it, word for word.

REPORT:
\"\"\"
{report}
\"\"\"

Return JSON: {{"answer": "yes" or "no", "evidence": "exact quote from the report for a yes, otherwise empty"}}"""

# call(system, user) -> raw model output
JudgeCall = Callable[[str, str], str]


def available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[‐-―−]", "-", text)  # hyphen and dash variants
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[“”]", '"', text)
    return re.sub(r"\s+", " ", text).strip().lower().strip(" .\"'")


def quote_in_report(quote: str, report: str) -> bool:
    q = _normalize(quote)
    return bool(q) and q in _normalize(report)


def _groq_call(system: str, user: str) -> str:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    completion = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return completion.choices[0].message.content


def _load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH) as f:
        return json.load(f)


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=1)


def ask(question: str, report: str, call: JudgeCall | None = None, use_cache: bool = True) -> dict:
    """Asks the judge one yes/no question about a report.

    Returns {"verdict": "yes" | "no" | "unsupported" | "error", "evidence", "model", "detail"}.
    "unsupported" = the judge said yes but its quote is not in the report.
    """
    prompt = PROMPT_TEMPLATE.format(question=question, report=report)
    key = hashlib.sha256(f"{JUDGE_MODEL}\n{SYSTEM_PROMPT}\n{prompt}".encode()).hexdigest()
    cache = _load_cache() if use_cache and call is None else {}
    if key in cache:
        return cache[key]

    call = call or _groq_call
    last_error = ""
    for _ in range(MAX_ATTEMPTS):
        try:
            parsed = json.loads(call(SYSTEM_PROMPT, prompt))
            answer = str(parsed.get("answer", "")).strip().lower()
            evidence = str(parsed.get("evidence", "") or "").strip()
            if answer not in {"yes", "no"}:
                raise ValueError(f"answer was {answer!r}")
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    else:
        return {"verdict": "error", "evidence": "", "model": JUDGE_MODEL, "detail": last_error}

    if answer == "yes" and not quote_in_report(evidence, report):
        result = {"verdict": "unsupported", "evidence": evidence, "model": JUDGE_MODEL,
                  "detail": "judge said yes but its quote is not in the report"}
    else:
        result = {"verdict": answer, "evidence": evidence if answer == "yes" else "", "model": JUDGE_MODEL, "detail": ""}

    if use_cache and call is _groq_call:
        cache = _load_cache()
        cache[key] = result
        _save_cache(cache)
    return result
