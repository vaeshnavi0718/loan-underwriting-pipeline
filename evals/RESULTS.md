# Eval results

Latest run of each suite. Raw per-application output for every run is in `results/`.

## review

Run 2026-10-20 · model `openai/gpt-oss-120b` · 12 applications × 3 runs · [raw results](results/2026-10-20T191137Z_review.json)

| Grader | Passed | Notes |
|---|---|---|
| Pipeline stops where expected | 36/36 | APP-004 and APP-011 correctly pause for their missing documents |
| Report has all five fields with the right types | 30/30 | The two paused applications never reach the Review Agent, so they are not graded |
| Every dollar amount exists in the input | 30/30 | 312 amounts checked, 7 to 13 per report, none invented |
| No approve/deny recommendation (keyword patterns) | 30/30 | 0 hits across all 70 real reports so far. Neutral phrasing like "final decision" and "eligibility" is correctly not flagged |

No fallback reports were used: every report came from the model.

## judged

Re-graded from the 2026-10-20 review run (same 30 reports) · judge `qwen/qwen3.8-27b` · [raw results](results/2026-10-20T193159Z_judged.json)

| Grader | Passed | Notes |
|---|---|---|
| Report states every `must_mention` fact | 30/30 | 51 facts checked, each confirmed by a quote verified in code |

**Checking the judge before trusting it:**

- **First pass: 28/30.** Reading both "misses" showed the model was right and the case file was wrong. One APP-007 report said "Credit score: 648 (sub-prime) with one payment 30+ days late," but the case file asked for a "*Fair* credit score of 648." Another stated the $2,600 balance against $5,550 deposits, but the case file asked for a "*thin cash cushion*." Facts were rewritten as checkable content instead of adjectives, and the rule is now in the case file's header.
- **Negative control: 0/14.** To make sure the fix didn't just make the judge lenient, each report was asked about facts from a *different* application, facts that are absent. The judge answered "no" to all 14.
- **Still to do:** hand-label a sample and measure agreement with the judge (task 8).

## Found by reading the reports

Before any quality grader existed, reading the reports from the first real run turned up one misreading:

- **APP-008:** the report said *"Income stability rated high while cashflow stability is rated low, indicating conflicting assessments."* The `high` there is a risk band (high risk), not high stability, so the contradiction does not exist. It is now a `must_not_claim` entry in the case file, and the LLM-judged graders will check for it on every run.
