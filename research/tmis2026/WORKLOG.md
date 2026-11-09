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

## 2026-11-09 17:30–18:30 — Secondary model, explanations, paper
- gpt-6-luna (the product's configured model), k=3: theft (R, CP) and tenancy
  (B1, CP). Spend USD 0.81. With luna, execution is clearly better:
  theft CP F1 0.810 vs R 0.591 (wrong changes 17 vs 68, Holm p=0.012);
  tenancy unsafe errors 0.03 vs 0.11 per claim (Holm p=0.031). With terra,
  R/B1 match or beat CP. Conclusion: execution makes request quality robust to
  the model; with a frontier model in-context application catches up.
- Mechanisms (terra): interpreter errors are almost all "unresolved" (735) not
  flips (7); 638 unresolved concern facts that are false but unmentioned (the
  references read silence as false). Verifier rejected 35 verdicts, all
  correct; caught none of the 7 flips (helped with luna on theft).
- Exact decision tables for all 150 claims over every partial assignment
  (S1) and engine scalability (S2) were computed locally in the cloud
  container: the Mac running Commander stayed offline, so sciCORE was not
  reached. Scripts and scicore/array.sbatch are ready; results are
  deterministic and should reproduce byte for byte on sciCORE.
- Pre-specified tests with Holm correction in analysis/primary_tests.json.
- Paper (paper/): acmart acmsmall, TMIS; every number generated from evidence
  by analysis/make_numbers.py; figures by analysis/figures.py; prompts
  exported verbatim by analysis/export_prompts.py.
- runs/responses_cache.tar.gz holds every cached model response (the raw
  cache directory stays git-ignored).

## 2026-11-09 18:00–18:40 — Final evidence audit, deliverables
- Audited every claim in the abstract, introduction, results, discussion and
  conclusion against the evidence files before packaging. Corrections:
  - **Correction to the 17:00–17:30 entry above:** exact deferral does *not*
    come "with no new errors". It removes 43% (terra) and 58% (luna) of the
    product engine's deferrals and adds no unnecessary request, but it adds 4
    and 2 silent misses (of 1,779 required documents over three runs). Each is
    a supplied document CasePath judged sufficient that the reference marks
    insufficient (5) or missing (1); the Kleene holds had hidden these
    document-review errors. The paper now reports that the second part of H2
    is not supported (new macros `ten*ExactCut`, `ten*ExactAddedMiss`).
  - "Almost all" deferrals from the routing fact -> "most": 74% (terra,
    397/538) and 59% (luna, 206/352).
  - The frontier model's accuracy edge on extracted rules (F1 0.79 vs 0.67,
    H3 Holm p = 0.42) is now called not significant wherever it is claimed.
  - An introduction sentence gave F1 for a wrong-change count; now 17 vs 68.
  - Limitations now state why no ReAct-style tool-using agent was compared.
- Bug fix: `analysis/tenancy_extra.py` ignored its model argument (the client
  binds the model at import), so it always read terra's cache. It now binds
  the model before import and allows cached responses only (budget 0). Terra
  output reproduced unchanged; luna output is new (deferral causes, routing
  presumption 95.0% recall / 0.0% unnecessary, citations 98.8% verbatim for
  rules in context and 99.4% for CasePath's interpreter). No model calls.
- `analysis/verify_paper.py`: all checks pass (recompute, byte-identical
  macros, citations resolve, clean compile, no undefined references).
- Deliverables in `deliverables/`: Overleaf ZIP, compiled PDF, reviewer/Joe
  checklist, evidence summary with remaining submission requirements.
- Total model spend for this paper: USD 9.42 (terra 8.61, luna 0.81).
- Not done: sciCORE (Mac offline; computations ran locally and are
  deterministic), PR to `main` (needs the owner's decision).
