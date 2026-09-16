# External positive-control protocol — BFCL V4 Multiple

Frozen before any BFCL model call. Source is Berkeley Function Calling Leaderboard (BFCL) commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`, category `BFCL_v4_multiple` (200 items), Apache-2.0. Exact dataset, possible-answer file, and AST checker are copied under `research/casepath/external/bfcl/` with SHA-256 metadata in `SOURCE.json`.

## Question
Does the same input-dependence audit that falsifies CasePath also reject a public structured-agent benchmark intended to require the user query? BFCL is a **positive control**, not a benchmark we expect to break.

## Conditions
One fixed model: `google/gemini-3.8-flash` through OpenRouter, temperature 0, max 900 output tokens, one physical call per item/condition, no semantic retries. Both conditions receive identical function schemas and identical response-format instruction. `full`: receives the official user query. `query_removed`: user query is replaced by `[REMOVED BY INPUT-DEPENDENCE AUDIT]`. Only this field differs.

The model must return JSON `{ "calls": [{"name": <exact BFCL function name>, "arguments": {...}}] }`. The response is normalized to BFCL's list-of-dictionaries format and scored using the exact copied BFCL AST checker logic from the frozen source commit. Parse failures score incorrect and are never semantically rerun.

## Analyses fixed before execution
1. AST accuracy for `full` and `query_removed` over all 200 items.
2. Exact function-name selection accuracy separately, to distinguish tool selection from argument filling.
3. Output diversity (distinct normalized calls and distinct selected function names).
4. Pairing sensitivity of the `full` condition: 5,000 seeded permutations (seed 20260916) that reassign complete model outputs to different BFCL items while keeping each item's function descriptions and gold answer fixed; report observed AST accuracy and permutation distribution/p-value.
5. Report the BFCL source commit, all source hashes, model identity, physical-call count, parse failures, and reported provider cost.

Interpretation is symmetric: if full-input performance is materially above query-removed and wrong-pairing performance, the audit passes on this public control. We will not tune the prompt/model after seeing results; an execution bug before provider calls may be repaired and committed separately.

## Execution amendment E1 — transport only
The first 400 HTTP requests were rejected by OpenRouter before inference with status 404 because the runner used provider selector `google`; OpenRouter reported the concrete serving endpoints as `google-ai-studio` and `google-vertex`. The failed responses contain no model output, tokens or cost and are preserved as `BFCL_POSITIVE_CONTROL_ROUTING_FAILURE*.json`. Before any semantic BFCL response existed, the selector was repaired to `google-ai-studio` with fallbacks still disabled. The model, prompts, items, conditions, temperature, token cap, scoring and analyses are unchanged.

## Robustness extension R1 — real but wrong query, frozen after hostile review
A hostile review correctly noted that `query_removed` can confound semantic information loss with the unusual removal marker and its high parse-failure rate. Before executing any additional BFCL call, we therefore add one matched robustness condition, `query_shuffled`. The 200 official user queries are deterministically deranged across the 200 items using seed `20260916 + 77`; no item receives its own query. Each item keeps its original candidate function schemas, system instruction, response JSON schema, temperature, model, provider routing, and 900-token cap. Only the user-query text is replaced by a real query from a different BFCL item. We report AST accuracy, function-name accuracy, parse rate, diversity, physical-call count and provider-reported cost. Failed/unparseable semantic outputs score incorrect and are not rerun. The mapping hash is persisted in the result artifact. This is a prospective robustness extension prompted by review, not part of the original frozen protocol.
