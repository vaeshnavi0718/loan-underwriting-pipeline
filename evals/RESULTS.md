# Eval results

Latest run of each suite. Raw per-application output for every run is in `results/`.

## review

Run 2026-10-19 · model `openai/gpt-oss-120b` · 12 applications × 1 run · [raw results](results/2026-10-19T193020Z_review.json)

| Grader | Passed | Notes |
|---|---|---|
| Pipeline stops where expected | 12/12 | APP-004 and APP-011 correctly pause for their missing documents |
| Report has all five fields with the right types | 10/10 | The two paused applications never reach the Review Agent, so they are not graded |

No fallback reports were used: every report came from the model.

## Found by reading the reports

Before any quality grader existed, reading the reports from the first real run turned up one misreading:

- **APP-008:** the report said *"Income stability rated high while cashflow stability is rated low, indicating conflicting assessments."* The `high` there is a risk band (high risk), not high stability, so the contradiction does not exist. It is now a `must_not_claim` entry in the case file, and the LLM-judged graders will check for it on every run.
