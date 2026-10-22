"""
Shared LLM judge for graders that need to understand meaning.

Design rules (see docs/ROADMAP.md, Phase 1):
- Yes/no questions, never a 1-10 score. ask() sends one question per call;
  ask_many() batches a report's questions into one call to save quota,
  with a separate answer and verified quote for each question.
- The judge writes a one-sentence reason before its answer. Without it, it
  answered "no" 5/5 times to a fact a report stated word for word.
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
import time
import unicodedata
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen/qwen3.8-27b")
CACHE_PATH = os.path.join(os.path.dirname(__file__), ".judge_cache.json")
MAX_ATTEMPTS = 5
BACKOFF_SECONDS = 4  # doubles each attempt: 4, 8, 16, 32

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

Return JSON: {{"reason": "one sentence on what the report says about this", "answer": "yes" or "no", "evidence": "exact quote from the report for a yes, otherwise empty"}}"""

BATCH_TEMPLATE = """Answer each numbered question separately and independently. For each one:
answer "yes" only if the report clearly says this; something merely implied or loosely related is "no".
If you answer "yes", copy the exact sentence or phrase from the report that shows it, word for word.

QUESTIONS:
{questions}

REPORT:
\"\"\"
{report}
\"\"\"

Return JSON: {{"answers": [{{"id": 1, "reason": "one sentence on what the report says about this", "answer": "yes" or "no", "evidence": "exact quote for a yes, otherwise empty"}}, ...]}}
with exactly one entry per question, ids {first} to {last} in order."""

class JudgeQuotaExhausted(RuntimeError):
    """The judge's daily token or request allowance is used up. Waiting
    minutes per call would look like a hang, so the run stops instead;
    answers so far are cached and the next run picks up from there."""


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
    from groq import Groq, RateLimitError

    # the SDK retries short per-minute rate limits itself, honoring retry-after
    client = Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=3)
    try:
        completion = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except RateLimitError as exc:
        if "per day" in str(exc):
            raise JudgeQuotaExhausted(f"{JUDGE_MODEL} daily limit reached: {exc}") from exc
        raise
    return completion.choices[0].message.content


def _load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH) as f:
        return json.load(f)


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=1)


def _verdict(answer: str, evidence: str, reason: str, report: str) -> dict:
    """Turns one raw judge answer into a verdict; a "yes" needs a quote that is really in the report."""
    if answer == "yes" and not quote_in_report(evidence, report):
        return {"verdict": "unsupported", "evidence": evidence, "reason": reason, "model": JUDGE_MODEL,
                "detail": "judge said yes but its quote is not in the report"}
    return {"verdict": answer, "evidence": evidence if answer == "yes" else "", "reason": reason,
            "model": JUDGE_MODEL, "detail": ""}


def _parse_item(item: dict) -> tuple[str, str, str]:
    answer = str(item.get("answer", "")).strip().lower()
    if answer not in {"yes", "no"}:
        raise ValueError(f"answer was {answer!r}")
    return answer, str(item.get("evidence", "") or "").strip(), str(item.get("reason", "") or "").strip()


def _run(prompt: str, parse: Callable[[dict], object], call: JudgeCall | None, use_cache: bool):
    """Calls the judge with retries and caching. Returns (parsed, None) or (None, error message)."""
    key = hashlib.sha256(f"{JUDGE_MODEL}\n{SYSTEM_PROMPT}\n{prompt}".encode()).hexdigest()
    live = call is None
    if use_cache and live:
        cached = _load_cache().get(key)
        if cached is not None:
            return cached, None

    call = call or _groq_call
    last_error = ""
    for attempt in range(MAX_ATTEMPTS):
        if attempt and live:
            time.sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
        try:
            parsed = parse(json.loads(call(SYSTEM_PROMPT, prompt)))
            break
        except JudgeQuotaExhausted:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    else:
        return None, last_error

    if use_cache and live:
        cache = _load_cache()
        cache[key] = parsed
        _save_cache(cache)
    return parsed, None


def ask(question: str, report: str, call: JudgeCall | None = None, use_cache: bool = True) -> dict:
    """Asks the judge one yes/no question about a report.

    Returns {"verdict": "yes" | "no" | "unsupported" | "error", "evidence", "model", "detail"}.
    "unsupported" = the judge said yes but its quote is not in the report.
    """
    prompt = PROMPT_TEMPLATE.format(question=question, report=report)
    parsed, error = _run(prompt, lambda d: list(_parse_item(d)), call, use_cache)
    if error is not None:
        return {"verdict": "error", "evidence": "", "model": JUDGE_MODEL, "detail": error}
    if isinstance(parsed, dict):  # cached before the format change: a finished verdict
        answer = "yes" if parsed.get("verdict") in {"yes", "unsupported"} else "no"
        parsed = [answer, parsed.get("evidence", ""), parsed.get("reason", "")]
    return _verdict(*parsed, report)


def ask_many(questions: list[str], report: str, call: JudgeCall | None = None, use_cache: bool = True) -> list[dict]:
    """Asks several yes/no questions about one report in a single call.

    About a third of the calls and tokens of asking one at a time, since the
    report is sent once. Each question still gets its own reason, answer and
    quote, and each quote is verified in code exactly as in ask().
    """
    if not questions:
        return []
    numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
    prompt = BATCH_TEMPLATE.format(questions=numbered, report=report, first=1, last=len(questions))

    def parse(data: dict) -> list:
        items = data.get("answers")
        if not isinstance(items, list) or len(items) != len(questions):
            raise ValueError(f"expected {len(questions)} answers, got {len(items) if isinstance(items, list) else items!r}")
        if [int(item.get("id", 0)) for item in items] != list(range(1, len(questions) + 1)):
            raise ValueError("answer ids out of order")
        return [list(_parse_item(item)) for item in items]

    parsed, error = _run(prompt, parse, call, use_cache)
    if error is not None:
        return [{"verdict": "error", "evidence": "", "model": JUDGE_MODEL, "detail": error} for _ in questions]
    return [_verdict(*item, report) for item in parsed]
