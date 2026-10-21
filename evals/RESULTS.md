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

Judge `qwen/qwen3.8-27b`, re-graded 2026-10-21 from the two 2026-10-20 review runs (30 reports each) · raw results: [run A](results/2026-10-21T105445Z_judged.json), [run B](results/2026-10-21T110522Z_judged.json)

| Grader | Run A | Run B | What failed |
|---|---|---|---|
| Report states every `must_mention` fact | 30/30 | 30/30 | Nothing; every fact confirmed by a quote verified in code |
| Report claims nothing on the `must_not_claim` list | 26/30 | 27/30 | APP-008 risk-band misreading (2 + 3 reports); a ~1% income gap called a mismatch (APP-002, APP-010 in run A) |

Negative control (facts from other applications, so absent): **0/14** wrongly accepted. No judge errors in any run.

**Checking the judge before trusting it:**

- **First pass of issue recall: 28/30.** Reading both "misses" showed the model was right and the case file was wrong. One APP-007 report said "Credit score: 648 (sub-prime) with one payment 30+ days late," but the case file asked for a "*Fair* credit score of 648." Another stated the $2,600 balance against $5,550 deposits, but the case file asked for a "*thin cash cushion*." Facts were rewritten as checkable content instead of adjectives, and the rule is now in the case file's header.
- **A judge blind spot, fixed by asking for a reason first.** The judge answered "no" 5 times out of 5 to a fact an APP-008 report stated word for word. Asking it to write a one-sentence reason before answering turned that into "yes" 3/3, and the negative control stayed at 0/14, so it didn't become lenient.
- **Errors counted as results, fixed.** Rate-limit errors were once counted as missed facts (0/30) and as passes (30/30). Judge errors are now reported separately, excluded from totals, and make the run fail.
- **Still to do:** hand-label a sample and measure agreement with the judge (task 8).

## Found by reading the reports

Real failures in the agent, newest last. The first was found by reading the reports before any quality grader existed; the graders now catch both.

- **APP-008, now confirmed in 6 of 7 reports:** the report said *"Income stability rated high while cashflow stability is rated low, indicating conflicting assessments."* The `high` there is a risk band (high risk), not high stability, so the contradiction does not exist. It is a `must_not_claim` entry in the case file, and the `false_alarm` grader catches it with quoted evidence.
- **APP-002 and APP-010:** reports listed a ~1% gap between deposits and stated income ($5,050 vs $5,100; $2,050 vs $2,100) under *inconsistencies*. The pipeline only treats deposits below 70% of income as a mismatch, so this is noise presented as a concern. Caught by the `false_alarm` grader.
