# Adjudicator-robustness protocol — frozen before execution

**Frozen:** 2026-09-16, before any call in this study.

## Question

The original rent-increase reference states were authored by `openai/gpt-5.6-terra`, which is also one of the evaluated interpreters. This study asks whether the benchmark conclusions survive reference adjudication by independent model families while every case, contract, arm output, metric and scoring rule is held fixed.

This is an evaluator-sensitivity study, not a new method experiment. It may strengthen or weaken the paper; no outcome is designated desirable.
## Frozen adjudicators

Three non-OpenAI families, chosen before execution from the live OpenRouter catalogue:

- `anthropic/claude-opus-5`
- `google/gemini-3.1-pro-preview`
- `deepseek/deepseek-v4-pro`

Each adjudicator receives the identical system prompt and case/decision payload used by the original reference runner. Temperature is 0.0, `max_tokens=8000`, and each unit receives three independently recorded calls distinguished only by `(adjudicator k)` for k=1,2,3.
## Frozen data and analysis

- Units: the same 58 rent-increase unit narratives in committed `artifacts/conf_cases.json` (28 complete orig/e07 pairs used by the existing confirmatory analysis; two unmatched units remain recorded but do not enter paired scoring).
- Contract: `reference_contracts/rent_increase.json`.
- Held document: `lease_contract`.
- Arm outputs: the already committed GPT, Claude, Gemini and DeepSeek interpreter artifacts; **no arm is rerun**.
- Reference aggregation: majority status over the three calls; ties remain open under the existing `contract_scoring_v1.adjudicate` rule.
- Primary read: for every adjudicator family, recompute each interpreter × arm excess-withdrawal statistic with the exact hypergeometric volume control, and the case-ignoring/cross-fitted constant oracle.
- Secondary read: agreement of decision states, document reference sets and release sets between adjudicators; global and within-scenario pairing permutations.
- No significance threshold is used to choose which adjudicator to report. The complete matrix is reported.
## Interpretation rules fixed in advance

1. If the cross-fitted input-independent constant remains competitive under all adjudicators, the paired task remains construct-invalid regardless of interpreter ranking.
2. If interpreter rankings or signs materially change across adjudicators, the reported score is demonstrably a representation × interpreter × evaluator quantity and cannot be attributed to the representation alone.
3. If rankings remain stable, the original same-family adjudicator confound is reduced, but this does not rescue an input-independent task.
4. Failed/unparseable calls are retained. There is no semantic repair and no model substitution. Transport-level retries follow the existing bounded transport helper only.
5. The study ends after the frozen three families; no post-result adjudicator shopping.

Raw responses, model identities, usage metadata and prompt hashes must be committed before the analysis claim is finalized. The OpenRouter credential is read only from the existing local key file and must never be printed or committed.