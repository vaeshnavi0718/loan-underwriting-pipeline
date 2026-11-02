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

    python -m evals.extraction --extractor regex --split test_unseen
"""
import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timezone

from app.agents.document_agent import PARSERS
from app.tools.pdf_extract import extract_text

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


EXTRACTORS = {"regex": regex_extractor}


# ---------- running a split ----------

def load_split(split: str, data_dir: str = DATA_DIR) -> list[dict]:
    splits = json.load(open(os.path.join(data_dir, "splits.json")))["splits"]
    rows = [json.loads(line) for line in open(os.path.join(data_dir, "labels.jsonl"))]
    return [r for r in rows if splits[r["doc_id"]] == split]


def run_document(extractor, row: dict, data_dir: str = DATA_DIR) -> dict:
    text = extract_text(os.path.join(data_dir, row["file"]))
    start = time.perf_counter()
    output, usage = extractor(text, row["doc_type"])
    latency = time.perf_counter() - start
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
        "mean_latency_s": round(sum(d["latency_s"] for d in docs) / len(docs), 4) if docs else None,
        "mean_tokens": round(sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in usage)
                             / len(usage), 1) if usage else None,
        "total_cost_usd": round(sum(u.get("cost_usd", 0) for u in usage), 4) if usage else None,
        "by_field": {k: {"correct": c, "total": n} for k, (c, n) in sorted(by_field.items())},
        "by_layout": {k: {"correct": c, "total": n} for k, (c, n) in sorted(by_layout.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a field extractor on the extraction dataset.")
    parser.add_argument("--extractor", choices=sorted(EXTRACTORS), required=True)
    parser.add_argument("--split", choices=SPLITS, default="test_unseen")
    parser.add_argument("--limit", type=int, help="only the first N documents (a cheap trial run)")
    args = parser.parse_args()

    if not os.path.isdir(os.path.join(DATA_DIR, "docs")):
        print("No PDFs yet: run python scripts/generate_extraction_dataset.py first.")
        return 2
    rows = load_split(args.split)[:args.limit]
    extractor = EXTRACTORS[args.extractor]
    docs = [run_document(extractor, row) for row in rows]
    summary = summarize(docs)

    print(f"{args.extractor} on {args.split}: {summary['documents']} documents")
    print(f"  field accuracy      {summary['field_accuracy']:.1%}")
    p, a = summary["present_fields"], summary["absent_fields"]
    print(f"  present fields      {p['correct']}/{p['total']} correct, {p['wrong']} wrong, {p['missed']} missed")
    print(f"  absent fields       {a['correct_null']}/{a['total']} left null, {a['hallucinated']} hallucinated")
    print(f"  all fields correct  {summary['documents_all_correct']}/{summary['documents']} documents")
    print(f"  valid JSON          {summary['valid_json']}/{summary['documents']}")
    print(f"  mean latency        {summary['mean_latency_s'] * 1000:.1f} ms")
    if summary["mean_tokens"] is not None:
        print(f"  mean tokens / doc   {summary['mean_tokens']}   total cost ${summary['total_cost_usd']}")
    print("\n  by layout")
    for layout, s in summary["by_layout"].items():
        print(f"    {layout:<18}{s['correct']:>4}/{s['total']}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_path = os.path.join(RESULTS_DIR, f"{stamp}_extraction_{args.extractor}_{args.split}.json")
    with open(out_path, "w") as f:
        json.dump({"suite": "extraction", "extractor": args.extractor, "split": args.split,
                   "summary": summary, "documents": docs}, f, indent=2, default=str)
    print(f"\n-> {os.path.relpath(out_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
