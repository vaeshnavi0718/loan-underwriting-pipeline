"""
Eval runner.

    python -m evals.run --suite schema
    python -m evals.run --suite schema --repeats 3

Runs every synthetic application through the pipeline, applies the suite's
graders, prints a per-case table plus every failure, and writes the full
results to evals/results/<timestamp>_<suite>.json. Exits non-zero if any
grader fails, so CI can gate on it.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from evals.graders import schema
from evals.harness import list_cases, run_case

# suite name -> {grader name: grade function}
SUITES = {
    "schema": {"schema": schema.grade},
}

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an eval suite over the synthetic applications.")
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--repeats", type=int, default=1, help="runs per case (LLM output varies run to run)")
    parser.add_argument("--cases", nargs="*", help="only these case ids, e.g. APP-005 APP-012")
    args = parser.parse_args()

    graders = SUITES[args.suite]
    cases = args.cases or list_cases()
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b") if os.environ.get("GROQ_API_KEY") else "fallback (no GROQ_API_KEY)"
    print(f"suite={args.suite}  model={model}  {len(cases)} cases x {args.repeats} runs\n")

    rows, failures = [], []
    for case_id in cases:
        for run in range(1, args.repeats + 1):
            result = run_case(case_id)
            grades = {name: grade(result) for name, grade in graders.items()}
            rows.append({"case_id": case_id, "run": run, "result": result, "grades": grades})
            for name, g in grades.items():
                if g is not None and not g["passed"]:
                    failures.append(f"{case_id} run {run}  {name}: {g['detail']}")

    totals = {}
    print(f"{'case':<9}{'status':<26}" + "".join(f"{n:>14}" for n in graders))
    for case_id in cases:
        case_rows = [r for r in rows if r["case_id"] == case_id]
        line = f"{case_id:<9}{case_rows[0]['result']['status']:<26}"
        for name in graders:
            applicable = [r["grades"][name] for r in case_rows if r["grades"][name] is not None]
            passed = sum(g["passed"] for g in applicable)
            t = totals.setdefault(name, [0, 0])
            t[0] += passed
            t[1] += len(applicable)
            line += f"{f'{passed}/{len(applicable)}' if applicable else '-':>14}"
        print(line)
    print(f"{'TOTAL':<35}" + "".join(f"{f'{p}/{n}':>14}" for p, n in totals.values()))

    if failures:
        print("\nFAILURES")
        for f in failures:
            print(" " + f)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_path = os.path.join(RESULTS_DIR, f"{stamp}_{args.suite}.json")
    with open(out_path, "w") as f:
        json.dump(
            {"suite": args.suite, "model": model, "repeats": args.repeats,
             "totals": {k: {"passed": p, "applicable": n} for k, (p, n) in totals.items()},
             "runs": rows},
            f, indent=2, default=str,
        )
    print(f"\n-> {os.path.relpath(out_path)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
