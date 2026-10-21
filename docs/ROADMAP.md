# Roadmap: evals and LoRA

The goal is to measure how well the pipeline's AI parts work, then use those measurements to fine-tune a small model for document extraction and compare it honestly against the alternatives.

## Phase 0: Foundation

- [x] GitHub Actions running the tests on every push
- [x] Eval runner: `python -m evals.run --suite <name>`, results saved to `evals/results/`
- [x] First code grader (report schema)

## Phase 1: Review Agent evals

The Review Agent is the only agent that calls an LLM. Each synthetic application has a planted issue (or none), which becomes its expected behavior.

- [x] Case file with what each application's report must and must not flag
- [x] Status grader (code): the pipeline stops where the case file expects
- [x] Grounding grader (code): every dollar amount in the report exists in the input
- [x] No-decision grader, keyword part (code): explicit and common soft recommendations
- [ ] No-decision grader, judge part (LLM judge): subtler implied recommendations
- [x] Shared LLM judge: one yes/no question per call, whole report, quotes checked in code, different model family from the agent, cached answers
- [x] Re-grade saved reports without re-running the pipeline (`--from-results`)
- [x] Issue recall grader (LLM judge, must quote evidence)
- [x] False alarm grader (LLM judge): nothing on the must_not_claim list, including the APP-008 misreading
- [x] Judge hardening: reason before answering, judge errors reported separately from results, clean stop at the daily quota
- [ ] Hand-label 20 reports and record how often the judge agrees
- [ ] Prompt injection set: instructions hidden in PDFs; report stays neutral and status never changes
- [ ] Manual GitHub Actions workflow for the suites that call the LLM

## Phase 2: Extraction dataset and baselines

The Document Agent's regex parser matches the fixed labels the generator writes, so it looks perfect on today's data. A fair test needs documents that vary.

- [ ] Generator for about 1,500 documents across about 8 layouts per document type (different labels, tables, number formats, distractor values like YTD totals)
- [ ] Split by layout: train on some layouts, test only on layouts never seen in training
- [ ] Extraction suite: field accuracy, correct handling of missing fields, valid JSON, cost and latency per document
- [ ] Baselines: regex parser, and a large model via Groq prompted for JSON

## Phase 3: LoRA fine-tune

- [ ] Fine-tune Qwen2.5-1.5B-Instruct with LoRA (Hugging Face `transformers` + `peft` + `trl`, Colab GPU)
- [ ] Compare against 0.5B, and find the training-set size where accuracy stops improving
- [ ] Publish the adapter with a model card (data, metrics, limitations)

## Phase 4: Integration and write-up

- [ ] `EXTRACTOR=regex|llm|lora` setting in the Document Agent
- [ ] Fallback chain: LoRA output, then schema check, then the large model, then regex, each step logged in the audit trail
- [ ] README results table comparing the three approaches on accuracy, cost and latency
- [ ] Limitations: synthetic data, digital PDFs only, LoRA runs locally (the free Render tier can't serve it)
