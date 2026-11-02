"""
Splits the Phase 2 extraction dataset by layout and writes
data/extraction/splits.json.

- test_unseen: 2 layouts per document type that training never sees.
- train / val_seen: the other 6 layouts; val_seen holds back ~10% of each
  of them, so seen and unseen layouts can be scored side by side.

The held-out layouts are picked by hand so that each layout family (codes,
letters, tables, mobile-style, EU formats, pick-one-of-many) is still in
training for some other document type, and the original layouts stay in
train so the regex baseline isn't flattered.

    python scripts/split_extraction_dataset.py [--seed 7]
"""
import argparse
import json
import os
import random
from collections import Counter, defaultdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "extraction")

HELD_OUT = {
    "pay_stub": ["ps_hours_rate", "ps_letter"],        # terse codes, letter
    "bank_statement": ["bs_transactions", "bs_stacked"],  # transaction table, mobile-style
    "credit_report": ["cr_tri_merge", "cr_letter"],     # pick the middle score, letter
    "id_document": ["id_license", "id_european"],       # card with date distractors, day-first dates
}
VAL_RATE = 0.10


def split(rows: list[dict], seed: int) -> dict[str, str]:
    held = {layout for layouts in HELD_OUT.values() for layout in layouts}
    by_layout = defaultdict(list)
    for row in rows:
        by_layout[row["layout"]].append(row["doc_id"])
    out = {}
    for layout, ids in sorted(by_layout.items()):
        if layout in held:
            out.update({i: "test_unseen" for i in ids})
            continue
        val = set(random.Random(f"{seed}:{layout}").sample(sorted(ids), round(len(ids) * VAL_RATE)))
        out.update({i: "val_seen" if i in val else "train" for i in ids})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--data", default=DATA_DIR)
    args = ap.parse_args()

    rows = [json.loads(line) for line in open(os.path.join(args.data, "labels.jsonl"))]
    splits = split(rows, args.seed)
    with open(os.path.join(args.data, "splits.json"), "w") as f:
        json.dump({"held_out_layouts": HELD_OUT, "splits": splits}, f, indent=1, sort_keys=True)
    print(dict(Counter(splits.values())))


if __name__ == "__main__":
    main()
