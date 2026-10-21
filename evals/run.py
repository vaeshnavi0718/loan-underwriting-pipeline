"""
Eval runner.

    python -m evals.run --suite review
    python -m evals.run --suite review --repeats 3

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

from evals import judge
from evals.cases import CASES_PATH, INJECTION_CASES_PATH, load_cases
from evals.graders import false_alarm, grounding, issue_recall, no_decision, schema, status
from evals.harness import INJECTION_DIR, SYNTH_DIR, run_case

# suite name -> {grader name: grade(result, case) function}
SUITES = {
    "review": {"status": status.grade, "schema": schema.grade, "grounding": grounding.grade,
               "no_decision": no_decision.grade},
    # LLM-judged: needs GROQ_API_KEY, so not run in CI
    "judged": {"issue_recall": issue_recall.grade, "false_alarm": false_alarm.grade},
    # Prompt-injection attacks: the status must never change and the report
    # must not take the planted instruction. Code graders only.
    "injection": {"status": status.grade, "schema": schema.grade, "no_decision": no_decision.grade},
}

# suite name -> (case file, fixture folder); suites not listed use the review cases
SUITE_DATA = {"injection": (INJECTION_CASES_PATH, INJECTION_DIR)}

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an eval suite over the synthetic applications.")
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--repeats", type=int, default=1, help="runs per case (LLM output varies run to run)")
    parser.add_argument("--cases", nargs="*", help="only these case ids, e.g. APP-005 APP-012")
    parser.add_argument("--from-results", metavar="FILE",
                        help="re-grade reports saved by an earlier run instead of running the pipeline")
    args = parser.parse_args()

    graders = SUITES[args.suite]
    cases_path, fixtures_dir = SUITE_DATA.get(args.suite, (CASES_PATH, SYNTH_DIR))
    all_cases = load_cases(cases_path)
    unknown = sorted(set(args.cases or []) - set(all_cases))
    if unknown:
        parser.error(f"no such case(s): {unknown}")

    if args.from_results:
        with open(args.from_results) as f:
            saved = json.load(f)
        model = saved["model"]
        runs = [(r["case_id"], r["run"], r["result"]) for r in saved["runs"]
                if not args.cases or r["case_id"] in args.cases]
        repeats = saved["repeats"]
        source = f"re-graded from {os.path.relpath(args.from_results)}"
    else:
        model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b") if os.environ.get("GROQ_API_KEY") else "fallback (no GROQ_API_KEY)"
        runs = None
        repeats = args.repeats
        source = "fresh pipeline runs"
    cases = sorted({case_id for case_id, _, _ in runs}) if runs is not None else (args.cases or sorted(all_cases))
    print(f"suite={args.suite}  model={model}  {len(cases)} cases x {repeats} runs  ({source})\n")

    if runs is None:
        runs = [(case_id, run, run_case(case_id, fixtures_dir)) for case_id in cases for run in range(1, repeats + 1)]

    rows, failures, errors = [], [], []
    for case_id, run, result in runs:
        try:
            grades = {name: grade(result, all_cases[case_id]) for name, grade in graders.items()}
        except judge.JudgeQuotaExhausted as exc:
            print(f"\nSTOPPED at {case_id} run {run}: {exc}")
            print("Judge answers so far are cached; re-run the same command once the limit resets.")
            return 2
        rows.append({"case_id": case_id, "run": run, "result": result, "grades": grades})
        for name, g in grades.items():
            if g is not None and g.get("error"):
                errors.append(f"{case_id} run {run}  {name}: {g['detail']}")
            elif g is not None and not g["passed"]:
                failures.append(f"{case_id} run {run}  {name}: {g['detail']}")

    totals = {}
    print(f"{'case':<9}{'stopped at':<26}" + "".join(f"{n:>14}" for n in graders))
    for case_id in cases:
        case_rows = [r for r in rows if r["case_id"] == case_id]
        line = f"{case_id:<9}{case_rows[0]['result']['status']:<26}"
        for name in graders:
            # a grade the judge couldn't produce says nothing about the report: left out of the totals
            applicable = [r["grades"][name] for r in case_rows
                          if r["grades"][name] is not None and not r["grades"][name].get("error")]
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
    if errors:
        print("\nJUDGE ERRORS (not graded, excluded from totals; re-run to fill them in)")
        for e in errors:
            print(" " + e)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    out_path = os.path.join(RESULTS_DIR, f"{stamp}_{args.suite}.json")
    with open(out_path, "w") as f:
        json.dump(
            {"suite": args.suite, "model": model, "repeats": repeats, "source": source,
             "totals": {k: {"passed": p, "applicable": n} for k, (p, n) in totals.items()},
             "runs": rows},
            f, indent=2, default=str,
        )
    print(f"\n-> {os.path.relpath(out_path)}")
    return 1 if failures or errors else 0


if __name__ == "__main__":
    sys.exit(main())
