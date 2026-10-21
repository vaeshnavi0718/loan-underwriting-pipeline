"""
Compares hand labels with the LLM judge's verdicts on the same 20 items.

    python -m evals.labels.agreement

Items were sampled from the 2026-10-20 review runs (both grader kinds, a mix
of judge yes and no) and labeled blind in labeling.html: the labeler never
saw the judge's answer. adjudication.json records who was right on each
disagreement, after reading the report.
"""
import json
import os

HERE = os.path.dirname(__file__)


def main() -> None:
    judge = {x["n"]: x for x in json.load(open(os.path.join(HERE, "judge_answers.json")))}
    human = {x["n"]: x["label"] for x in json.load(open(os.path.join(HERE, "human_labels.json")))}
    adjudicated = {x["n"]: x for x in json.load(open(os.path.join(HERE, "adjudication.json")))}

    agree = [n for n in judge if human[n] == judge[n]["judge"]]
    print(f"human and judge agree: {len(agree)}/{len(judge)}")
    for kind in ("states", "claims"):
        ns = [n for n in judge if judge[n]["kind"] == kind]
        print(f"  {kind}: {sum(n in agree for n in ns)}/{len(ns)}")

    truth = {n: adjudicated[n]["correct"] if n in adjudicated else judge[n]["judge"] for n in judge}
    print(f"judge correct: {sum(judge[n]['judge'] == truth[n] for n in judge)}/{len(judge)}")
    print(f"human correct: {sum(human[n] == truth[n] for n in judge)}/{len(judge)}")
    for n, a in sorted(adjudicated.items()):
        print(f"  #{n} {judge[n]['case_id']}: human={human[n]} judge={judge[n]['judge']} correct={a['correct']}: {a['why']}")


if __name__ == "__main__":
    main()
