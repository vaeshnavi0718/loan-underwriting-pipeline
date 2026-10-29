# Phase 2 progress

A short handoff note so a fresh session can pick up where the last one stopped. See ROADMAP.md for the plan.

## Task 1: varied-document generator (branch `phase-2-extraction-generator`)

Script: `scripts/generate_extraction_dataset.py`. Output: `data/extraction/docs/*.pdf` (gitignored, rebuilt from the seed) and `data/extraction/labels.jsonl` (committed).

- [x] 1a. Skeleton, label format, 8 pay stub layouts
- [ ] 1b. Bank statement layouts (average_monthly_balance, monthly_deposits)
- [ ] 1c. Credit report (credit_score, existing_monthly_debt, payment_history) and ID (name, date_of_birth, id_status) layouts
- [ ] 1d. Tests (each true value appears in pdfplumber text), 1 sample PDF per layout committed, full 1,500-doc run, PR

## Decisions

- Labeled fields per type are the ones the Document Agent already returns, so the regex parser can be scored as-is.
- Layouts are assigned round-robin (doc index mod number of layouts), so every layout gets the same count. The layout name is stored on each label row for the task 2 split.
- 10% of documents leave out one field; its label is null and the field is listed in `missing`.
- `ps_legacy` is the original generator's format, so the regex parser gets credit on one layout.
- `ps_hours_rate` prints the employer in upper case: the extraction suite should compare names case-insensitively.
- `money()` never drops cents from a value that has them, so a printed value always equals its label.
