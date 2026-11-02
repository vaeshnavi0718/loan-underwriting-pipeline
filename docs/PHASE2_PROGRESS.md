# Phase 2 progress

A short handoff note so a fresh session can pick up where the last one stopped. See ROADMAP.md for the plan.

## Task 1: varied-document generator (branch `phase-2-extraction-generator`)

Script: `scripts/generate_extraction_dataset.py`. Output: `data/extraction/docs/*.pdf` (gitignored, rebuilt from the seed) and `data/extraction/labels.jsonl` (committed).

- [x] 1a. Skeleton, label format, 8 pay stub layouts
- [x] 1b. Bank statement layouts (average_monthly_balance, monthly_deposits)
- [x] 1c. Credit report (credit_score, existing_monthly_debt, payment_history) and ID (name, date_of_birth, id_status) layouts
- [x] 1d. Tests (each true value appears in pdfplumber text), 1 sample PDF per layout committed, full 1,500-doc run, PR

## Decisions

- Labeled fields per type are the ones the Document Agent already returns, so the regex parser can be scored as-is.
- Layouts are assigned round-robin (doc index mod number of layouts), so every layout gets the same count. The layout name is stored on each label row for the task 2 split.
- 10% of documents leave out one field; its label is null and the field is listed in `missing`.
- `ps_legacy` is the original generator's format, so the regex parser gets credit on one layout.
- `ps_hours_rate` prints the employer in upper case: the extraction suite should compare names case-insensitively.
- `money()` never drops cents from a value that has them, so a printed value always equals its label.
- `bs_multi_month` shows three months; the label is the printed 3-month average row, and the current month is set so the average is exact to the cent.
- `bs_transactions` prints credits and debits in separate columns, which pdfplumber flattens into one line; the true values are only in the footer totals.
- Checked on an 80-doc sample: every true bank value appears in the pdfplumber text, and the regex parser matches only `bs_legacy` (5/5) and none of the other 7 layouts.
- Labels keep the Document Agent's formats: `date_of_birth` is ISO and `id_status` is `verified`/`not_verified`, while the PDFs print dates as 03/14/1988, 14 Mar 1988, 14.03.1988, 19880314 and so on, and the status as Verified, NOT VERIFIED or NOT_VERIFIED. The extraction suite (and the 1d test) must normalize dates and compare names, statuses and payment history case-insensitively.
- `payment_history` comes from a fixed list of 6 phrases (same style as the existing apps) and is printed word for word, except that `cr_letter` lowercases it.
- `cr_tri_merge` shows three bureau scores; the label is the printed middle score. `cr_score_trend` shows past scores; the label is the current row. `cr_tradelines` has per-account payments that sum to the labeled total.
- Checked on a 160-doc sample: every true credit and ID value appears in the pdfplumber text (after the normalization above), and the regex parser matches only `cr_legacy` and `id_legacy` (5/5 each).
- PDFs are written with ReportLab's `invariant=1`, so the same seed gives byte-identical files and the committed samples only change when a layout does.
- Full run: 1,500 documents (375 per type, 46 or 47 per layout) in under a second; 142 have a missing field. `tests/test_extraction_dataset.py` (no LLM, ~1 s) regenerates 96 documents and checks printed values, balance, nulls and that they match the committed labels.

## Next: Task 2, the layout split (train layouts vs never-seen test layouts)
