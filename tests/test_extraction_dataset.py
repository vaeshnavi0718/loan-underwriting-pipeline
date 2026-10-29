"""Checks the Phase 2 extraction dataset generator: labels match what the PDFs print."""
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import date

import pdfplumber
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPT = os.path.join(ROOT, "scripts", "generate_extraction_dataset.py")
COMMITTED = os.path.join(ROOT, "data", "extraction", "labels.jsonl")
PER_TYPE = 24  # 3 documents per layout keeps the test fast


def printed_forms(value) -> set[str]:
    """The ways a label value can be printed, lowercased."""
    if isinstance(value, int):
        return {str(value)}
    if isinstance(value, float):
        us = f"{value:,.2f}"
        forms = {us, f"{value:.2f}", us.replace(",", " ").replace(".", ",").replace(" ", ".")}
        if value == int(value):
            forms.add(f"{value:,.0f}")
        return forms
    try:
        d = date.fromisoformat(value)
    except ValueError:
        return {value.lower(), value.lower().replace("_", " ")}
    return {d.isoformat(), d.strftime("%m/%d/%Y"), d.strftime("%d %b %Y").lower(),
            d.strftime("%B %d, %Y").replace(" 0", " ").lower(), d.strftime("%d.%m.%Y"), d.strftime("%Y%m%d")}


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    out = tmp_path_factory.mktemp("extraction")
    subprocess.run([sys.executable, SCRIPT, "--per-type", str(PER_TYPE), "--out", str(out)],
                   check=True, capture_output=True)
    rows = [json.loads(line) for line in open(out / "labels.jsonl")]
    return out, rows


def test_every_true_value_is_printed(dataset):
    out, rows = dataset
    for row in rows:
        with pdfplumber.open(out / row["file"]) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages).lower()
        for field, value in row["fields"].items():
            if value is None:
                continue
            assert any(f in text for f in printed_forms(value)), (row["doc_id"], row["layout"], field, value)


def test_layouts_are_balanced(dataset):
    _, rows = dataset
    counts = Counter(row["layout"] for row in rows)
    assert len(counts) == 32
    assert set(counts.values()) == {PER_TYPE // 8}


def test_missing_fields_are_null(dataset):
    _, rows = dataset
    for row in rows:
        nulls = sorted(k for k, v in row["fields"].items() if v is None)
        assert nulls == sorted(row["missing"]), row["doc_id"]


def test_committed_labels_match_the_seed(dataset):
    # each document's randomness is seeded by its id, so a small run equals the start of the full one
    _, rows = dataset
    committed = {r["doc_id"]: r for r in map(json.loads, open(COMMITTED))}
    assert len(committed) == 1500
    for row in rows:
        assert committed[row["doc_id"]] == row
