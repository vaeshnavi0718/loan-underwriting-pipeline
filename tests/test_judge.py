"""LLM judge safeguards, tested with a fake model (no API calls)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evals import judge

REPORT = "Income stability is rated high while cash‑flow stability is rated low, indicating conflicting assessments."


def fake(*replies):
    """A judge 'model' that returns the given replies in order."""
    queue = list(replies)
    return lambda system, user: queue.pop(0)


def test_yes_with_real_quote_is_yes():
    r = judge.ask("Q?", REPORT, call=fake(json.dumps({"answer": "yes", "evidence": "Income stability is rated high"})))
    assert r["verdict"] == "yes"


def test_quote_matches_across_unicode_hyphens_and_spacing():
    quote = "cash-flow   stability is rated low"  # plain hyphen, extra spaces
    r = judge.ask("Q?", REPORT, call=fake(json.dumps({"answer": "yes", "evidence": quote})))
    assert r["verdict"] == "yes"


def test_yes_with_made_up_quote_is_unsupported():
    r = judge.ask("Q?", REPORT, call=fake(json.dumps({"answer": "yes", "evidence": "The applicant is a minor"})))
    assert r["verdict"] == "unsupported"


def test_yes_without_quote_is_unsupported():
    r = judge.ask("Q?", REPORT, call=fake(json.dumps({"answer": "yes", "evidence": ""})))
    assert r["verdict"] == "unsupported"


def test_no_is_no():
    r = judge.ask("Q?", REPORT, call=fake(json.dumps({"answer": "no", "evidence": ""})))
    assert r["verdict"] == "no"


def test_retries_after_bad_output():
    r = judge.ask("Q?", REPORT, call=fake("not json", json.dumps({"answer": "maybe"}), json.dumps({"answer": "no"})))
    assert r["verdict"] == "no"


def test_gives_up_after_max_attempts():
    r = judge.ask("Q?", REPORT, call=fake("x", "y", "z"))
    assert r["verdict"] == "error"


def test_prompt_contains_question_and_whole_report():
    seen = {}

    def capture(system, user):
        seen["user"] = user
        return json.dumps({"answer": "no"})

    judge.ask("Does it mention the DOB?", REPORT, call=capture)
    assert "Does it mention the DOB?" in seen["user"]
    assert REPORT in seen["user"]
