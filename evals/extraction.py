"""
Extraction suite (Phase 2): scores a field extractor on the varied-document
dataset in data/extraction/, one split at a time.

An extractor takes (pdf text, doc_type) and returns (output, usage):
output is a dict of fields, or a raw string that must parse as a JSON
object; usage is {"input_tokens", "output_tokens", "cost_usd"} or {}.

Per field, a prediction is one of:
  correct      - matches the label after normalization
  wrong        - a different value
  missed       - null, but the document has the field
  hallucinated - a value, but the document leaves the field out
  correct_null - null, and the document leaves the field out

Normalization is semantic, not format-strict: money within half a cent,
dates in any common format, text fields case- and whitespace-insensitive.

The groq extractor asks a large model for JSON. Its answers are cached by
(model, prompt), with the original latency and token usage, so a run that
hits the daily limit resumes where it stopped and re-runs cost nothing.
Cost is only computed when EXTRACTOR_PRICE_IN / EXTRACTOR_PRICE_OUT (USD
per million tokens) are set; on Groq's free tier it is $0.

    python -m evals.extraction --extractor regex --split test_unseen
    python -m evals.extraction --extractor groq --split test_unseen --limit 20
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timezone

from dotenv import load_dotenv

from app.agents.document_agent import PARSERS
from app.tools.pdf_extract import extract_text

load_dotenv()

EXTRACTOR_MODEL = os.environ.get("EXTRACTOR_MODEL", "openai/gpt-oss-120b")
CACHE_PATH = os.path.join(os.path.dirname(__file__), ".extraction_cache.json")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "extraction")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
SPLITS = ["train", "val_seen", "test_unseen"]

MONEY_FIELDS = {"gross_monthly_income", "average_monthly_balance", "monthly_deposits", "existing_monthly_debt"}
DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d %b %Y", "%B %d, %Y", "%d.%m.%Y", "%Y%m%d"]


# ---------- comparing one field ----------

def _number(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = re.sub(r"[\s$,]|USD", "", v)
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _date(v) -> date | None:
    if not isinstance(v, str):
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v.strip(), fmt).date()
        except ValueError:
            pass
    return None


def _text(v) -> str | None:
    if not isinstance(v, str):
        return None
    return " ".join(v.replace("_", " ").split()).casefold().rstrip(".")


def is_null(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def field_matches(field: str, predicted, label) -> bool:
    if field in MONEY_FIELDS:
        p = _number(predicted)
        return p is not None and abs(p - label) < 0.005
    if field == "credit_score":
        p = _number(predicted)
        return p is not None and p == label
    if field == "date_of_birth":
        return _date(predicted) == date.fromisoformat(label)
    return _text(predicted) == _text(label)


def score_field(field: str, predicted, label) -> str:
    if label is None:
        return "correct_null" if is_null(predicted) else "hallucinated"
    if is_null(predicted):
        return "missed"
    return "correct" if field_matches(field, predicted, label) else "wrong"


def parse_output(output) -> dict | None:
    """The extractor's fields, or None when the output isn't a JSON object."""
    if isinstance(output, dict):
        return output
    try:
        parsed = json.loads(output)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


# ---------- extractors ----------

def regex_extractor(text: str, doc_type: str):
    return PARSERS[doc_type](text), {}


class QuotaExhausted(Exception):
    """The model's daily token limit is used up; cached answers so far are kept."""


FIELD_NOTES = {
    "employer_name": "the employer's name as printed",
    "gross_monthly_income": "gross pay for one month, before taxes and deductions (number)",
    "average_monthly_balance": "the account's average balance for the month (number)",
    "monthly_deposits": "total deposits for the month (number)",
    "credit_score": "the applicant's credit score (integer)",
    "existing_monthly_debt": "total monthly payments on existing debts (number)",
    "payment_history": "the payment history statement, as printed",
    "name": "the document holder's full name",
    "date_of_birth": "date of birth as YYYY-MM-DD",
    "id_status": "\"verified\" or \"not_verified\"",
}
EXTRACT_SYSTEM = (
    "You extract fields from a loan application document. Reply with one JSON object that has exactly "
    "the requested keys. Use null for a field the document does not state; never guess. Numbers are plain "
    "JSON numbers in USD, with no currency symbols or thousands separators."
)


def _groq_call(system: str, user: str) -> tuple[str, dict]:
    from groq import Groq, RateLimitError

    client = Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=3)
    try:
        completion = client.chat.completions.create(
            model=EXTRACTOR_MODEL,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
            response_format={"type": "json_object"},
        )
    except RateLimitError as exc:
        if "per day" in str(exc):
            raise QuotaExhausted(f"{EXTRACTOR_MODEL} daily limit reached: {exc}") from exc
        raise
    usage = {"input_tokens": completion.usage.prompt_tokens, "output_tokens": completion.usage.completion_tokens}
    return completion.choices[0].message.content, usage


def _cost(usage: dict) -> float | None:
    price_in, price_out = os.environ.get("EXTRACTOR_PRICE_IN"), os.environ.get("EXTRACTOR_PRICE_OUT")
    if not (price_in and price_out):
        return None
    return (usage["input_tokens"] * float(price_in) + usage["output_tokens"] * float(price_out)) / 1e6


def groq_extractor(text: str, doc_type: str, fields: list[str], call=None, cache: dict | None = None):
    keys = "\n".join(f"- {f}: {FIELD_NOTES[f]}" for f in fields)
    user = f"Document type: {doc_type.replace('_', ' ')}\nKeys:\n{keys}\n\nDocument text:\n{text}"
    key = hashlib.sha256(f"{EXTRACTOR_MODEL}\n{EXTRACT_SYSTEM}\n{user}".encode()).hexdigest()
    if cache is not None and key in cache:
        hit = cache[key]
        return hit["output"], {**hit["usage"], "cached": True, "latency_s": hit["latency_s"]}
    start = time.perf_counter()
    try:
        output, usage = (call or _groq_call)(EXTRACT_SYSTEM, user)
    except QuotaExhausted:
        raise
    except Exception as exc:  # noqa: BLE001  a failed call is scored like invalid output
        output, usage = None, {"input_tokens": 0, "output_tokens": 0, "error": str(exc)}
    usage["latency_s"] = round(time.perf_counter() - start, 4)
    usage["cost_usd"] = _cost(usage) if "error" not in usage else None
    if cache is not None and "error" not in usage:
        cache[key] = {"output": output, "usage": {k: v for k, v in usage.items() if k != "latency_s"},
                      "latency_s": usage["latency_s"]}
    return output, usage


def _load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    with open(CACHE_PATH) as f:
        return json.load(f)


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=1)


EXTRACTORS = {"regex": regex_extractor, "groq": groq_extractor}


# ---------- running a split ----------

def load_split(split: str, data_dir: str = DATA_DIR) -> list[dict]:
    splits = json.load(open(os.path.join(data_dir, "splits.json")))["splits"]
    rows = [json.loads(line) for line in open(os.path.join(data_dir, "labels.jsonl"))]
    return [r for r in rows if splits[r["doc_id"]] == split]


def spread(rows: list[dict]) -> list[dict]:
    """Rows interleaved across layouts, so the first N cover every layout evenly."""
    by_layout = defaultdict(list)
    for row in rows:
        by_layout[row["layout"]].append(row)
    groups = [by_layout[k] for k in sorted(by_layout)]
    return [g[i] for i in range(max(map(len, groups))) for g in groups if i < len(g)]


def run_document(extractor, row: dict, data_dir: str = DATA_DIR) -> dict:
    text = extract_text(os.path.join(data_dir, row["file"]))
    start = time.perf_counter()
    output, usage = extractor(text, row["doc_type"])
    # a cached answer reports the latency of the original call
    latency = usage.pop("latency_s", None) or (time.perf_counter() - start)
    fields = parse_output(output)
    outcomes = {
        f: score_field(f, (fields or {}).get(f), label) if fields is not None else
        ("correct_null" if label is None else "missed")
        for f, label in row["fields"].items()
    }
    return {"doc_id": row["doc_id"], "doc_type": row["doc_type"], "layout": row["layout"],
            "valid_json": fields is not None, "predicted": fields, "outcomes": outcomes,
            "latency_s": round(latency, 4), "usage": usage}


def summarize(docs: list[dict]) -> dict:
    counts = defaultdict(int)
    by_field = defaultdict(lambda: [0, 0])
    by_layout = defaultdict(lambda: [0, 0])
    for d in docs:
        for field, outcome in d["outcomes"].items():
            counts[outcome] += 1
            ok = outcome in ("correct", "correct_null")
            for key, table in ((f"{d['doc_type']}.{field}", by_field), (d["layout"], by_layout)):
                table[key][0] += ok
                table[key][1] += 1
    total = sum(counts.values())
    present = counts["correct"] + counts["wrong"] + counts["missed"]
    absent = counts["correct_null"] + counts["hallucinated"]
    usage = [d["usage"] for d in docs if d["usage"]]
    return {
        "documents": len(docs),
        "field_accuracy": round((counts["correct"] + counts["correct_null"]) / total, 4) if total else None,
        "present_fields": {"total": present, "correct": counts["correct"],
                           "wrong": counts["wrong"], "missed": counts["missed"]},
        "absent_fields": {"total": absent, "correct_null": counts["correct_null"],
                          "hallucinated": counts["hallucinated"]},
        "documents_all_correct": sum(all(o in ("correct", "correct_null") for o in d["outcomes"].values())
                                     for d in docs),
        "valid_json": sum(d["valid_json"] for d in docs),
        "call_errors": sum(bool(d["usage"].get("error")) for d in docs),
        "mean_latency_s": round(sum(d["latency_s"] for d in docs) / len(docs), 4) if docs else None,
        "mean_tokens": round(sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in usage)
                             / len(usage), 1) if usage else None,
        "total_tokens": sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in usage) if usage else None,
        "total_cost_usd": (round(sum(u["cost_usd"] for u in usage), 4)
                           if usage and all(u.get("cost_usd") is not None for u in usage) else None),
        "by_field": {k: {"correct": c, "total": n} for k, (c, n) in sorted(by_field.items())},
        "by_layout": {k: {"correct": c, "total": n} for k, (c, n) in sorted(by_layout.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a field extractor on the extraction dataset.")
    parser.add_argument("--extractor", choices=sorted(EXTRACTORS), required=True)
    parser.add_argument("--split", choices=SPLITS, default="test_unseen")
    parser.add_argument("--limit", type=int, help="only N documents, spread evenly across layouts (a cheap trial run)")
    args = parser.parse_args()

    if not os.path.isdir(os.path.join(DATA_DIR, "docs")):
        print("No PDFs yet: run python scripts/generate_extraction_dataset.py first.")
        return 2
    rows = load_split(args.split)
    if args.limit:
        rows = spread(rows)[:args.limit]
    complete = True
    if args.extractor == "groq":
        if not os.environ.get("GROQ_API_KEY"):
            print("GROQ_API_KEY is not set.")
            return 2
        cache = _load_cache()
        docs = []
        try:
            for row in rows:
                fields = list(row["fields"])
                docs.append(run_document(lambda text, doc_type: groq_extractor(text, doc_type, fields, cache=cache), row))
        except QuotaExhausted as exc:
            complete = False
            print(f"Stopped after {len(docs)}/{len(rows)} documents: {exc}\nRe-run later; cached answers are reused.")
        finally:
            _save_cache(cache)
        if not docs:
            return 1
    else:
        docs = [run_document(EXTRACTORS[args.extractor], row) for row in rows]
    summary = summarize(docs)

    print(f"{args.extractor} on {args.split}: {summary['documents']} documents")
    print(f"  field accuracy      {summary['field_accuracy']:.1%}")
    p, a = summary["present_fields"], summary["absent_fields"]
    print(f"  present fields      {p['correct']}/{p['total']} correct, {p['wrong']} wrong, {p['missed']} missed")
    print(f"  absent fields       {a['correct_null']}/{a['total']} left null, {a['hallucinated']} hallucinated")
    print(f"  all fields correct  {summary['documents_all_correct']}/{summary['documents']} documents")
    print(f"  valid JSON          {summary['valid_json']}/{summary['documents']}"
          + (f"  ({summary['call_errors']} failed calls)" if summary["call_errors"] else ""))
    print(f"  mean latency        {summary['mean_latency_s'] * 1000:.1f} ms")
    if summary["mean_tokens"] is not None:
        cost = "not set" if summary["total_cost_usd"] is None else f"${summary['total_cost_usd']}"
        print(f"  mean tokens / doc   {summary['mean_tokens']}   total {summary['total_tokens']}   cost {cost}")
    print("\n  by layout")
    for layout, s in summary["by_layout"].items():
        print(f"    {layout:<18}{s['correct']:>4}/{s['total']}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_path = os.path.join(RESULTS_DIR, f"{stamp}_extraction_{args.extractor}_{args.split}.json")
    with open(out_path, "w") as f:
        json.dump({"suite": "extraction", "extractor": args.extractor, "split": args.split,
                   "model": EXTRACTOR_MODEL if args.extractor == "groq" else None,
                   "limit": args.limit, "complete": complete,
                   "summary": summary, "documents": docs}, f, indent=2, default=str)
    print(f"\n-> {os.path.relpath(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
