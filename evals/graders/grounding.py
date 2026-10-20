"""
Grounding grader (code, free).

Every dollar amount the report cites must exist somewhere in the data the
Review Agent was given. An amount that appears nowhere in its input was
invented or miscalculated, and a reviewer can't verify it.

Checks dollar amounts only. Percentages and ratios are rounded in too many
legitimate ways for an exact check; the LLM-judged graders cover those.
"""
import re

from evals.graders.common import report_text

# "$7,200", "$7,200.00", "$ 650", "$60k", "$1.2 million"
MONEY_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s?(k|m|thousand|million)?\b", re.IGNORECASE)
MULTIPLIERS = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "million": 1_000_000}


def _input_numbers(obj) -> set[float]:
    found: set[float] = set()

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            found.add(round(float(x), 2))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return found


def cited_amounts(text: str) -> list[tuple[str, float, float]]:
    """(as written, value, tolerance) for each dollar amount in the text.
    Shorthand like "$7.2k" is only as precise as its last digit, so it gets
    half a unit of that digit as tolerance; full amounts must match exactly."""
    amounts = []
    for m in MONEY_RE.finditer(text):
        digits = m.group(1).rstrip(",.")
        suffix = (m.group(2) or "").lower()
        value = float(digits.replace(",", ""))
        tolerance = 0.005
        if suffix:
            decimals = len(digits.split(".")[1]) if "." in digits else 0
            value *= MULTIPLIERS[suffix]
            tolerance = 0.5 * MULTIPLIERS[suffix] / 10**decimals
        amounts.append((m.group(0).strip().rstrip(",."), round(value, 2), tolerance))
    return amounts


def grade(result: dict, case: dict) -> dict | None:
    report = result["review_report"]
    if not report:
        return None

    allowed = _input_numbers(result["review_input"])
    invented = [
        written
        for written, value, tol in cited_amounts(report_text(report))
        if not any(abs(value - a) <= tol for a in allowed)
    ]
    return {
        "passed": not invented,
        "detail": f"amounts not in input: {sorted(set(invented))}" if invented else "",
    }
