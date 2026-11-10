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

## 2026-11-09 evening – 2026-11-10 — From the two-study paper to a paper on the product

Short record; details are in the files named.

- **Statistical review of Study 1** (`analysis/DEVIATIONS.md`): handed-over
  documents now scored as missed in the strict measure; with it the gpt-6-luna
  H1 result reverses (0.30 vs 0.13); Holm in three families; H4 has six
  clusters; a failed Direct output is scored empty (F1 0.664 → 0.642).
- **Study 2** (`STUDY2_DESIGN.md`, `ANALYSIS_PLAN_STUDY2.md` frozen at b86ab9d
  before any run; `fresh/` sealed; `analysis/STUDY2_RESULTS.md`): none of the
  four primary contrasts confirmed. Confirmed as fixed: over-deferral (held
  0.014 vs 3.31 per claim), requested share, correct holds on open facts
  (64/66). The run was interrupted twice and resumed from cache with the caps
  unchanged; transport retries were added after the freeze (disclosed).
  `fresh/` has been development data since.
- **Designs tried on development data and dropped:** quarantine of unrepaired
  rules (first v2), a result checker (v3). **Kept:** CP4 = two independent
  readings must agree, exact quotations, exact deferral (`harness/v2/cp4.py`).
  On theft stories 4–5 with gpt-6-luna: 0.33 errors per pair with the reviewed
  rules, 0.42 with the original ones; Rules in context about 1.5 (same model)
  and 0.54 (gpt-6.1-terra).
- **Rule review** (`rule_review/`): two blind editors and a reconciliation;
  9 of 98 rules changed (99 after one split), 14 queued for a jurist.
- **Owner's direction (2026-11-10):** the paper must report the product
  itself, the same architecture and rules inside and outside Mobiliar, with
  proprietary data as the only difference; external runs use gpt-6-luna, the
  internal deployment its own gateway model. The product is the package
  `casepath-internal` on branch `claude/casepath-internal-20261027`.
- **Adapter for the product** (`harness/product/`): converts the tenancy and
  theft rule bases to the product's workflow format and checks the conversion
  without a model (5,076/5,076 and 81,000/81,000 evaluations equal); runs the
  product through its own command line; scores with the Study 2 scorer;
  baselines from prior work (ReAct, Chain-of-Logic, self-consistency,
  two-valued) in `baselines.py`.
- **Merged into the product (7ff7af64, accepted by the product session):**
  exact deferral in `workflows.evaluate`, optional sourced presumptions,
  optional `must_show`, configurable organisation and language, the `parity`
  command with `docs/PARITY.md`. Working rule agreed with the product session:
  brief first, separate branch, no force-push, they merge.
- **Product measured as merged, gpt-6-luna, three runs**
  (`harness/product/results/score_all_p7ff.json`, `diagnose_p7ff.json`):
  tenancy strict unsafe errors per claim 1.08 (0.58 counting workflow needs
  only) against 0.16–0.20 for the sensible baselines; theft 1.83 per pair.
  Six causes named, agent by agent.
- **Fix branch** `claude/casepath-internal-paper-sync-20261110c` (unpushed):
  routing with one routable workflow, routed presumption, turn limits,
  document "present" rules, two structured readings with agreement, added
  needs as suggestions. One run: tenancy 0.18 (level with the baselines, with
  0.28 required documents per claim held behind a question); theft 0.94
  (two runs). Results in `harness/product/results/score_all_sync-c_*.json`.
  Next: close the remaining gap to CP4 on theft, independent review, brief to
  the product session, then a pre-registered test on unseen cases.
- **Figures:** shared theme `analysis/figtheme.py`; eight figures, two from
  real product screens (`paper/figures/ui_used/`).
- **Paper text:** background, method, evaluation, results and appendix were
  rewritten for the two-study framing; abstract, introduction, discussion and
  conclusion are still the old text. All of it will be rewritten around the
  product once the confirmatory test has run. `deliverables/` is superseded.
- **Commit authorship:** commits on this branch up to 2026-11-10 morning carry
  an assistant author line, against the bridge rule; later commits do not.
  Rewriting the history needs the owner's decision (it needs a force-push).

## 2026-11-10 — ShARC pilot (public benchmark): no advantage, not pursued
- Question: does the core (rule as formula, two agreeing readings with
  quotations, exact deferral) beat prompting on ShARC decision making with the
  same model? Train split only, 320 utterances, gpt-6-luna, USD 0.27
  (`harness/sharc/`, `runs/sharc/summary.json`, commit 546347d8). The dev
  split was not opened.
- Result: core 0.725 micro accuracy; direct 0.706, step-by-step 0.713,
  self-consistency 0.719. No difference is distinguishable from zero (core
  minus self-consistency +0.006 [−0.035, +0.048]). Exact deferral equals
  strong Kleene on every item (no formula uses a condition twice); two
  agreeing readings are not better than one.
- Reading: with one small rule per item there is little for execution to add.
  What the earlier studies show is the same: the advantage appears where many
  rules are in force at once (theft, 98 rules), not on small rule sets.
  ShARC will not be a headline result. Closest prior work found on the way,
  to cite: few-shot policy decomposition with a logic formula evaluated in
  code (arXiv 2501.11335; read and summarised in `analysis/RELATED_LDPC.md`).

## 2026-11-10 — Expert study design reviewed; first inside/outside parity match
- The product session's feedback and study design (5 experts × 3 cases) was
  reviewed against the product code at 6f3de061. Review, pre-registration
  draft, event fields, scales and recall guide, contribution statement and the
  plan for the outside check are in `expert_study/`. The product session
  adopted the changes as binding (its commit 5d0717f4) and builds them.
- Owner's decision: the expert study is planned for this TMIS paper; the
  record is specified so that it also serves a separate paper.
- The product session added a decision point ("Stand am" cut): each study case
  is shown as the file stood before the insurer's first outgoing request. It
  is being written into the pre-registration, which then stands at 1.0-rc
  until the owner names the three cases.
- **Parity:** the inside build reported source-tree hash
  523211edf8c11f12b85687fc2c270117e926a0e399664f9d311a444d1479699a (47 files)
  at product commit c9560c1. `python -m casepath parity` on the same commit
  outside gives the same hash and file count. The code inside and outside is
  byte-identical at that commit.
- Style and history, decided: plain English with short sentences and one term
  per concept (no formal controlled-language conformance); no history rewrite
  and no force-push, assistant author lines are dropped by a squash at merge.
- New sealed cases for the confirmatory test are being built in `fresh2/`.

## 2026-11-10 — Product round 3; Study 3 design drafted

Round 3 on the product fix branch (head `90a50673`, unpushed, 198 tests): quotation
retry, second judgment before a document counts as present, a fact counts as raised
only when both readings quote it, the review findings H1, H3, M1–M4, M6 and the
display fixes, and a checklist-only run setting as the last commit.

Development numbers (gpt-6-luna, three runs, `fresh/`):
- Tenancy, strict unsafe errors per claim: product .157; checklist only .132 (two
  runs); Rules in context .199 (same model), .157 (frontier model);
  self-consistency .194. The product holds more: .065 required documents and .130
  unneeded documents per claim are held.
- Theft stories 4–5, wrong + missed per pair: product .80; checklist only .93;
  core (CP4) .33; Rules in context 1.33 (same model, reviewed rules), .54 (frontier
  model, original rules); self-consistency 1.50; ReAct 1.11; model executes rules
  2.06. Fresh readings on three more runs gave .48–.54, so much of the product's
  .80 is run-to-run variation of the readings; one misread base text costs 16
  errors.
- In no measured run did the process builder, the result checker or the brief
  change a checklist.

Decisions:
- One last development round (round 4), limited to the readings: compare the
  product's reading requests with the core's, measure nine runs each, and test
  agreement rules offline before building anything.
- An independent review of the 20 fix commits runs in parallel.
- `fresh2/` contains claims whose defining event is denied or open; `fresh/` has
  none. Sixteen probe claims (`dev_probe/`) test this case type on development
  data before the plan is frozen.
- `STUDY3_DESIGN.md`: the product at a frozen commit against Rules in context
  (both models), self-consistency, model executes rules, ReAct, two-valued and the
  core; four primary hypotheses in a fixed order; strict errors stay the tenancy
  primary measure and "all deviations per claim" is reported beside it.

## 2026-11-10 — Product round 4, review of the fixes, probe, Study 3 tooling

**Readings (theft, development).** Nine runs each showed that the core's earlier
0.33 was a lucky draw: core 0.75 (sd 0.48), product checklist-only 0.88 (sd 0.62)
wrong + missed per pair. Two request differences had no reason: the product's
second reading saw only 27 of 89 conditions, in reverse order, and lacked the
framing of the task. Resampling stored readings showed that requiring three
readings to agree lowers errors (0.93 to 0.55) and leaves more open pairs
unchanged. Built: every reading judges all conditions in the same order; number of
readings is a setting, default three. Result at the final round-4 commit, nine
runs: product checklist-only **0.40** (sd 0.09), open pairs unchanged 100%;
against core 0.75, frontier single prompt 0.67 (reviewed rules) and 0.54 (original
rules), same-model single prompt 1.33.

**Independent review of the 20 fix commits:** merge after fixes. Fixed: a stopped
document finder dropped unchecked needs from the request list; a failed reading
let a presumption fill a doubt; a recheck skipped the second document judgment;
quotation matching folded superscripts into digits; and smaller points. Each has a
test that fails without it.

**Incident.** The reviewer's script ran `git checkout` in the worktree
`casepath-sync-c` that another worker used. No run was affected (all round-4 runs
came from clean worktrees whose source-tree hash was checked). The tree is left as
it was found; work moved to `casepath-sync-d`.

**Probe (16 development claims, defining event denied, open or true).** With the
event denied the product makes 2.2 unsafe errors per claim, the single prompts 6.0
to 6.6. With the event left open the product requested everything: a presumption
overrode a doubt that both readings had quoted. Fixed by rule: no presumption
applies to a fact the readings find raised and left open. Side effect on normal
claims: a reading's "unresolved" did not separate a stated doubt from silence, so
claims that take the notice for granted were held (held required documents .065 to
.787 per claim). Round 4b gives readings two separate answers, "open" (the file
says it is not known, with a quotation) and "not stated".

**Study 3 tooling.** `analysis/study3.py` with spec and 36 tests reproduces the
round-3 numbers; `harness/study3/run_all.py` runs the whole study in one command
with preflight checks and a resume log. Expected cost of the run: about USD 24.5.
