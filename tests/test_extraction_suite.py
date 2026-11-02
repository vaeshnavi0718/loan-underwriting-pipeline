"""Checks the extraction suite's scoring, without any LLM calls."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evals.extraction import (DATA_DIR, parse_output, regex_extractor, run_document, score_field,
                              summarize)


def test_money_ignores_format_but_not_value():
    assert score_field("monthly_deposits", "$5,416.67", 5416.67) == "correct"
    assert score_field("monthly_deposits", 5416.67, 5416.67) == "correct"
    assert score_field("monthly_deposits", "USD 5,416.67", 5416.67) == "correct"
    assert score_field("monthly_deposits", 5416.6, 5416.67) == "wrong"
    assert score_field("monthly_deposits", 65000.0, 5416.67) == "wrong"  # annual instead of monthly


def test_dates_text_and_scores():
    assert score_field("date_of_birth", "03/14/1988", "1988-03-14") == "correct"
    assert score_field("date_of_birth", "14.03.1988", "1988-03-14") == "correct"
    assert score_field("date_of_birth", "2031-03-14", "1988-03-14") == "wrong"  # the expiry date
    assert score_field("id_status", "NOT VERIFIED", "not_verified") == "correct"
    assert score_field("id_status", "verified", "not_verified") == "wrong"
    assert score_field("employer_name", "CASCADE LOGISTICS INC.", "Cascade Logistics Inc.") == "correct"
    assert score_field("payment_history", "no late payments in 24 months.",
                       "No late payments in 24 months") == "correct"
    assert score_field("credit_score", "712", 712) == "correct"
    assert score_field("credit_score", 850, 712) == "wrong"  # the top of the range


def test_missing_fields():
    assert score_field("credit_score", None, 712) == "missed"
    assert score_field("credit_score", "", 712) == "missed"
    assert score_field("credit_score", None, None) == "correct_null"
    assert score_field("credit_score", 712, None) == "hallucinated"


def test_output_must_be_a_json_object():
    assert parse_output('{"credit_score": 712}') == {"credit_score": 712}
    assert parse_output("Here is the JSON: {}") is None
    assert parse_output("[1, 2]") is None
    assert parse_output(None) is None


def test_invalid_json_scores_every_present_field_as_missed():
    row = {"doc_id": "X", "doc_type": "credit_report", "layout": "cr_legacy",
           "file": "samples/cr_legacy.pdf",
           "fields": {"credit_score": 712, "existing_monthly_debt": None, "payment_history": "x"}}
    doc = run_document(lambda text, doc_type: ("not json", {}), row)
    assert doc["valid_json"] is False
    assert doc["outcomes"] == {"credit_score": "missed", "existing_monthly_debt": "correct_null",
                               "payment_history": "missed"}


def test_regex_on_the_committed_samples():
    # each sample is the first document of its layout; the parser should only read the original layouts
    rows = [json.loads(line) for line in open(os.path.join(DATA_DIR, "labels.jsonl"))]
    first = {}
    for row in rows:
        first.setdefault(row["layout"], {**row, "file": f"samples/{row['layout']}.pdf"})
    docs = [run_document(regex_extractor, row) for row in first.values()]
    for d in docs:
        present = [o for f, o in d["outcomes"].items() if first[d["layout"]]["fields"][f] is not None]
        if d["layout"].endswith("_legacy"):
            assert set(present) == {"correct"}, d
        else:
            assert "correct" not in present, d
    summary = summarize(docs)
    assert summary["documents"] == 32 and summary["valid_json"] == 32


def test_groq_extractor_caches_answers_with_their_usage():
    from evals.extraction import groq_extractor

    calls = []

    def fake_call(system, user):
        calls.append(user)
        return '{"credit_score": 712}', {"input_tokens": 300, "output_tokens": 20}

    cache = {}
    out1, usage1 = groq_extractor("Credit Score: 712", "credit_report", ["credit_score"], fake_call, cache)
    out2, usage2 = groq_extractor("Credit Score: 712", "credit_report", ["credit_score"], fake_call, cache)
    assert len(calls) == 1 and out1 == out2 == '{"credit_score": 712}'
    assert usage2["cached"] and usage2["input_tokens"] == 300
    assert "credit_score: the applicant's credit score" in calls[0]


def test_groq_extractor_failed_call_is_scored_not_cached():
    from evals.extraction import groq_extractor

    def broken(system, user):
        raise RuntimeError("500 from the API")

    cache = {}
    out, usage = groq_extractor("text", "pay_stub", ["employer_name"], broken, cache)
    assert out is None and "500" in usage["error"] and cache == {}
