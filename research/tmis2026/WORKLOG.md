# Work log: CasePath TMIS paper (Claude session, 2026-11-09)

Newest entries at the bottom. Times are UTC.

## 2026-11-09 16:55 — Start
- Goal: rework the ICLR CasePath paper into a TMIS paper centred on the latest
  CasePath agent; address all three ICLR reviews and Joe's comments; run new
  decisive experiments.
- Base: `aa4fb25` (head of `claude/casepath-internal-20261027`), which contains
  the agent-native redesign, the autonomous controller (interpret -> verify ->
  admission gates -> causal process engine) and the internal-pilot packaging.
- `main` could not be fast-forwarded: the repository ruleset requires a pull
  request, the "CasePath regression" check and CodeQL. No PR was opened
  (awaiting the owner's decision). This work lives on branch
  `claude/casepath-tmis-paper-20261109`.
- Model for new runs: `openai/gpt-6.1-terra` via OpenRouter, used sparingly
  (owner's instruction). CPU-bound analyses run on sciCORE (`scicore-fast`).
- Inputs reused: Study A theft pairs (`data/casepath-theft-pairs`), Study B
  tenancy claims (`data/casepath-tenancy-claims`), the ICLR reproducibility
  archive (frozen original predictions and judgments).

## 2026-11-09 17:00–17:30 — Harness, checks and main runs (gpt-6.1-terra)
- Oracle check: true scenario flags through the product engine reproduce the
  reference request set for 147/150 tenancy claims (3 differ only by an
  unreadable photo; that document is not scored there). The generator leaves
  `termination_received` and `claim_received` implicitly true.
- Parity: the harness planner (all-routes mode) reproduces all 54 original
  Study A checklists from the original gpt-5.6-terra condition answers, and the
  scorer reproduces the original numbers (24/15/9, F1 0.667). With one route per
  requirement (unified planner) the same answers give 27/15/6, F1 0.720.
- Finding (pilot): strong-Kleene evaluation in `causal_process_v1` holds whole
  processes when a flag at a reconverging branch is unresolved (e.g.
  `health_effects` in the defect template). Fix: supervaluation over the open
  flags, implemented on top of the unchanged engine
  (`harness/casepath_tenancy.py::supervaluate`).
- ANALYSIS_PLAN.md frozen at 46a503b before held-out runs.
- Held-out runs, k=3: theft (D, R, CP) and tenancy (B1, B2, CP). Spend so far
  about USD 8.6 including pilots and diagnostics.
- Results (see analysis/results_gpt-6.1-terra.json): rules-in-context is the
  strongest design with this model on both datasets. Theft: R F1 0.79 vs CP
  0.67; 37 of CP's 38 wrong changes trace to five faulty extracted rules.
  Tenancy: B1 recall 0.97 with 0.1% unnecessary; CP-exact recall 0.69 (0.6%
  unnecessary), deferrals mostly from the unstated routing fact (397/538) and
  whole-claim deferrals (87/538). Exact deferral halves Kleene's deferrals with
  no new errors. Citations were 100% exact for every design.
- Diagnostics: blind rule verifier flags all five faulty rules (64/98 flagged);
  blind reference re-derivation reproduces 7/9 theft conditions exactly.
- Secondary run with gpt-6-luna (the product's configured model) in progress.
- sciCORE: jobs prepared in scicore/ (array.sbatch); the Mac running
  Commander has been offline since ~16:55, so nothing has been dispatched yet.
