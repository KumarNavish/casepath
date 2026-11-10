# ShARC pilot (train split only)

A cheap pilot on a public, human-annotated benchmark: does CasePath's core (CP4: rules as conditions plus a
formula, two agreeing quotation-grounded readings, code that evaluates the formula with exact deferral) beat
prompting baselines on ShARC decision making (Saeidi et al., EMNLP 2018) with the same small model
(gpt-6-luna, low reasoning effort, schema-constrained output)?

**This is a pilot on a sample of the ShARC TRAIN split.** The dev split was not opened, printed, sampled or
scored; it is reserved for a later pre-registered test. Numbers here are not comparable with published dev/test
results. The dataset is not committed.

- `fetch.sh <empty-dir>`: downloads the official archive, checks SHA-256
  `72dca3f4f3ba73b1d796b40e952a80d53cd2011ef90b2168b8bcaa818f5edd1e`, extracts only the train split.
- `sample.py`: 320 train utterances, seed 20261110, 80 per class (Yes, No, Irrelevant, Inquire = the gold
  answer is a follow-up question); the first 60 of a seeded shuffle are the prompt-development subset
  (`runs/sharc/sample_ids.json`).
- `pilot.py`: designs `direct`, `steps` (Chain-of-Logic style), `sc3` (steps x3, majority, ties to Inquire;
  run 0 is the `steps` call), `cp` (call A per (snippet, question); readings B1/B2; quotation admission with
  `v2/match.py`; agreement; exact deferral), plus model-free `kleene` and `single` (B1 only) from the same
  judgments. CasePath prompts: v1 written from the task definition, revised twice (v2, v3) after reading errors
  on the 60-utterance subset; v3 was then run once on all 320. Baseline prompts were written once, not revised.
- `analyse.py`: micro/macro accuracy, confusion matrices, paired differences with a 95% bootstrap clustered by
  snippet, calls and USD per utterance -> `runs/sharc/summary.json`.
- `error_sample.py`: seeded samples for hand reading; classification in `runs/sharc/error_classification.json`.

All calls are in `runs/sharc/ledger_pilot_gpt-6-luna.jsonl` (cap USD 2.50; spent USD 0.27).
Run every script with `python3 -I`, with the extracted data outside the repository.

Result (n = 320, 225 snippet clusters): micro accuracy direct 0.706, steps 0.713, sc3 0.719, CasePath core 0.725;
core minus sc3 +0.006 (95% CI -0.035 to +0.048). No significant advantage in this pilot.
