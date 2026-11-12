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

## 2026-11-10 — Freeze: product commit, Study 3 plan, confirmatory run started

**Pre-freeze.** A second independent review of the round-4 commits found, among
smaller points, that with three readings a single "not stated" answer let a
presumption override a doubt two readings had quoted. Decision (overruling my own
0.05 criterion): a doubt quoted by any reading blocks the presumption; cost on
development data about 0.09 more wrong holds per claim, no premature request
under either rule. All findings fixed with tests.

**Validation on theft stories 6–7** (never used in product development):
product checklist-only 0.57 wrong + missed per pair (runs 0.89, 0.44, 0.39);
same-model single prompt 1.41; frontier single prompt 0.67 (reviewed rules) and
0.54 (original rules). The lead over the frontier model seen on stories 4–5 does
not hold; the lead over the same model does.

**Product on the frontier model** (development, checklist only, one run): theft
0.83 and 0.78 against 0.54–0.67 for the frontier single prompt; tenancy strict
0.12 against 0.16 on 65 claims. The product does not lift the frontier model on
theft. Not pursued before the freeze; added to Study 3 as a one-run secondary
design without a hypothesis.

**Mechanism check.** In the full product no later agent changed a scored
checklist (30 of 30 and 32 of 32 texts); full and checklist-only differ only
through chance in the readings.

**Freeze.** The 63 fix commits were rebased onto the product tip `abe968b5`
without conflicts; every development checklist is identical to the commit
measured before the rebase. Frozen product commit
`6a72159cdb35a01059d0549b1d437c0b3d5c20cb`, source-tree hash `03048020…49ab4d`,
232 tests. Branch `claude/casepath-internal-paper-sync-20261110d` pushed; brief
in `BRIEF_PRODUCT_SYNC_20261110D.md`. `ANALYSIS_PLAN_STUDY3.md` committed
(`fd35e438`) with five hypotheses in a fixed order: theft and tenancy against the
same model, tenancy against the frontier model, theft against every prior-work
strategy, theft non-inferiority to the frontier model. All four preflight checks
passed; the confirmatory run on `fresh2/` started (label `confirm`).

Decision recorded: the run started before the product session confirmed the
merge. If they reject a behaviour change, the test must be repeated on new sealed
data.

## 2026-11-11 — Study 3 result, paper written, two referee rounds

**Run.** Five invocations of `harness/study3/run_all.py` between 10 Nov 22:30
and 11 Nov 04:17 UTC. Four stopped early: two deliberately (my interrupt of
the first, to raise parallelism from 6 to 20 workers, whose log line is wrong
and corrected by a dated note; the wrapper's planned stop of the fourth at 110
minutes) and two by failures of the environment (the session's two-hour limit
on background commands; a container restart). Each resumed from the response
cache with settings unchanged. Spend USD 34.33. 50 failed outputs, none from
the product, 40 from ReAct.

**Result** (`analysis/study3_results_fresh2_confirm.md`, run once): H1, H2,
H3 confirmed; H4 not (against Self-consistency p = 0.0625 over nine facts);
H5 not tested. Theft 0.58 against 1.74 (same model, reviewed rules); tenancy
0.31 against 2.14 (same model) and 1.86 (frontier model). The tenancy
difference lies in the 33 claims whose defining event is denied or open.
Checklist only shows no detectable difference from the full product at 22%
and 16% of its cost. On the frontier model (one run, no hypothesis) the
product is not better than the frontier single prompt on theft.

**Decisions and corrections made while writing.**
- The theft rules were reviewed by two AI editor sessions, not by experts;
  the paper says so everywhere.
- The full product and the checklist-only run share cached routing and part
  of the readings; their comparison is not an independent repetition.
- Every theft case-run had more than eight open facts and used the product's
  plain walk, which equals exact deferral on that workflow; exact deferral's
  benefit is shown on tenancy only.
- The order of the hypotheses was changed at 21:51 on 10 Nov, 39 minutes
  before the freeze, on development evidence (the ReAct comparison was the
  weakest). Under the order of 21:26 the prior-work hypothesis would have
  failed third and the tenancy contrast against the frontier model would not
  have been tested. The second referee found that the paper did not disclose
  this; it now does.

**Review.** An independent referee read (major revision) and a claims audit
(all 409 macros checked match; about 25 wording and attribution errors) led
to: three contributions and a design-science framing; scope stated in the
abstract, introduction and conclusion; Studies 1 and 2 moved to a supplement;
scope conditions inside the propositions and one admission table; eleven
analyses added after review from stored outputs (`analysis/study3_review.*`);
the expert study out of the body (protocol in an appendix). A second referee
round recommended minor revision; its items are in `FINAL_FIX_BRIEF.md`.
Both reports and the audit are in `analysis/review/`.

**Release.** `reproduce.sh` reproduces Study 3's tables and macros and
re-checks Studies 1–2 from stored outputs in about eleven minutes without
model calls; it passes in a fresh clone. A public release is blocked on the
owner's decisions listed in `release/SCRUB_REPORT.md` (git history, the
insurer's name in the tested product, a Knowledge seed derived from its
letters, internal documents, licences, the cache archive).

## 2026-11-11 (later) — After the test: product round 1, cost and time, the open same-model cell

**Owner's framing.** The claim is same-model: for a given model, CasePath against
every baseline on that model; nothing beyond the frontier model; credits used
sparingly, no blind runs.

**Product.** The product's owners pushed "round 1" without the fix commits and set
a gate (their check on seven real development dossiers by 15 Nov) for taking the
fix branch unchanged or not at all. The fix branch was rebased onto their tip with
five rule collisions resolved (`REPLY_PRODUCT_ROUND1.md`), pushed as
`claude/casepath-internal-paper-sync-20261111f` (head `1b96f82e`). On our
development data round 1 alone scores 1.01 strict errors per tenancy claim and
1.50 per theft pair; the rebased branch 0.13–0.16 and 0.35–0.50. Whatever the gate
decides, the product will differ from the tested commit; a repeat of the test on
the frozen product needs new sealed data.

**Expert study.** The product's process for mould cases is now a handler process
written by the builders from seven development dossiers and the law; the drawn
diagrams describe the intake chat. Pre-registration, field list and protocol
appendix adjusted: practice is the reference for the handler's path; a leakage
rule and an order at the freeze were added.

**Cost and time (USD 1.40).** Readings asked at once, checklist stored before the
reply draft, two first turns asked ahead: no request and no checklist changed
(1,812 stored case-runs replayed from stored responses); time to a checklist about
halved. Cost unchanged: output tokens dominate. Three attempts to cut cost failed
(the endpoint ignores a request for three samples; listing only addressed
conditions doubled theft errors; a position-aligned encoding did not decode).

**The open cell: theft on the frontier model (USD 3.0).** Model-free diagnosis:
with perfect facts the theft rules give 0.33 errors per pair in either rule base;
the frontier-model product's excess comes mostly from two over-broad conditions
read literally. A general reading instruction (take the case type as given) met
its pre-set rule on the pair measure and failed the harm check: it dropped the
defining-event conditions. A reference-free lint (conditions admitted true in most
ordinary cases) flags both over-broad conditions with the frontier model's
readings. Two blind AI editors reviewed the flags under a four-eyes rule; the
third-party narrowing was rejected by one editor (the passage states no
exclusion). Evaluated without model calls, the reconciled rules drop three
documents from every ordinary checklist and may raise the floor, so no model test
was run. Decision: no further credits on this cell; it needs a jurist's decision
on three points (`rule_review/lint/final/RECONCILIATION.md`).

**Paper.** Reframed around the same-model claim as a two-by-two (holds in three
cells, not shown on theft with the frontier model); new subsection "After the
test"; abstract rewritten. Main paper 59 pages, supplement 27; all checks pass.

## 2026-11-12: outside feedback (eight points) and the analyses made in answer

An outside review of the status asked for a different headline ("holds", not
"wins"), all four cells with an error decomposition, real-file evidence that
needs no experts, an answer to the circularity objection, open repair of the
statistics, the lint as a tested contribution, budget-matched comparisons, the
tested commit as the artefact, and a cut to about 35 pages. All analyses below
are post hoc and labelled so; the registered results are unchanged. Model spend:
USD 0.15 (lint mutation test, cost-efficient model).

**Clean room.** Two blind AI evaluator sessions each wrote an evaluator from the
rule text and the designed facts only. Their references are byte-identical and
equal the registered reference on 1,024 of 1,024 document decisions. One
evaluator later listed a scratch directory and saw file names (recorded in
`cleanroom/README.md`); its reference had been delivered and hashed before.

**Readings of the rule text (F5, F5b).** Scored against references written under
four rejected readings, with the product's workflow unchanged, the tenancy result
reverses under "a denied event does not stop the process" (not significantly) and
under all four together (significantly). With the workflow amended to each
reading and the checklist recomputed from the stored readings, the lead holds
under every reading (smaller under two). The baselines were not re-run.

**Where the lead sits (F1, F2).** 56 claims with an open fact or a denied or open
defining event: 0.34 against 2.1 to 2.3 for the single prompts on either model.
40 claims with everything stated: 0.22 against 0.19 for the frontier prompt.
CasePath is below every single prompt above a share of about 2% of such claims
(7% counting unneeded holds).

**Order and Holm (F3).** Under Holm's correction four of five hypotheses would
pass; the self-consistency one fails under every procedure. Under the order
before the late change the third would not have been tested.

**Budget (F4).** Self-consistency with 1 to 15 samples stays at 2.1 on tenancy and
levels off near 1.0 on theft. At a matched budget CasePath has 0.34 (p 0.0006)
and 0.55 (p 0.13). More readings lower strict errors and raise unneeded holds.

**Decomposition.** Every cell of the product splits exactly into rule, routing,
document judgment, reading and hold. Theft on the frontier model: 0.83 = rule
0.33 + reading 0.25 + hold 0.25.

**Lint.** Mutation test: six planted over-broad conditions flagged, three of them
newly; three of five untouched conditions also flagged; on the designed tenancy
claims the lint flags most conditions, so it has no usable false-alarm rate.
"A flagged condition is treated as open": frontier theft 0.83 → 0.53 with the
model's own flags (in-sample), 0.83 → 0.78 with flags from development runs. The
remedy does not survive out of sample. Decision: no paid run for this cell; nine
clusters could not confirm a difference of this size.

**Deployment study.** The pre-registration draft now has the archival comparison
with what the insurer did next, at every decision point of four sealed files, as
primary endpoint; the experts are secondary; a leave-one-dossier-out replay is a
registered development analysis. Disagreements between two transcriptions are
settled before any sealed run. Requirements and questions for the product's
builders: `expert_study/REQUEST_TO_PRODUCT_20261112.md`.

**Paper.** Rewritten to brief v4 (`REWRITE_BRIEF.md`): main paper 31 pages (was
59), supplement 69. A third independent referee read it (major revision: 10 major,
23 minor concerns, among them a false sentence on the failed hypothesis, a headline
built on a post hoc split, theft "holding" that the measure cannot show, cost
understated, the lint oversold). All were accepted (`FIX_BRIEF_ROUND3.md`). The
referee's check of the revision: minor revision, 64 of 71 items closed, 7 partly,
and ten small new items, all closed since. The paper now leads with the registered
tenancy result, claims "holds" for tenancy only, states cost as 20 to 42 times the
same-model prompt, and names the one interpretive choice (a denied defining event
ends the process) that carries about two thirds of the tenancy lead. `reproduce.sh`
covers the new analyses (83 steps, about ten minutes, no model calls).
Deliverables refreshed: both PDFs, the Overleaf ZIP (55 files, test-built), the
review checklist and the evidence-and-requirements document.

## 2026-11-12: the owner's new direction; steps 0 to 2 of the costed plan

**Direction.** The paper is to show that the artefact beats every fair
alternative on the same model in every cell, by removing weaknesses and not by
describing them; no claim rests on the hackathon dossiers or the expert study;
one sealed run after a freeze with an external timestamp. Costed plan:
`STUDY4_COSTED_PLAN.md` (seven steps, about USD 110). Approved: steps 0 to 2.
Specification for steps 1 and 2: `study4/SPEC.md`.

**Step 0, paper (USD 0).** Dossiers and expert study removed from every claim,
table and section (one sentence of future work). The artefact is the minimal
core. Limits are stated once, in Section 7.1 "Scope". Main paper 27 pages,
supplement 68.

**Step 1, fair-baseline check (USD 4.45 of 5.00; post hoc; Study 3's data are
development data from now on).** A single prompt told the same stop and hold
rules in plain words matches CasePath on tenancy (0.35 against 0.31 strict
unsafe errors per claim on the same model; 0.19 against 0.30 on the frontier
model) and makes no error on the frontier model where a claim denies its
defining event, where CasePath holds needlessly (0.61 strict, 1.78 all
deviations). CasePath keeps a lead on tentatively worded facts (0.52 against
1.25 to 1.30 deviations), on insufficient supplied documents and on theft (0.58
against 1.68). The registered tenancy result therefore measures mostly what
the prompt was told; the paper says so (Section 6.6, Table 8, abstract).
`study4/baseline_check/REPORT.md`.

**Design estimate (USD 0, in-sample upper bound).** "A quoted denial of the
defining event counts as a denial; the event is true only when all three
readings say true" would take tenancy from 0.74 to 0.45 deviations per claim on
the cost-efficient model and from 0.71 to 0.33 on the frontier model, strict
errors and theft unchanged. `study4/design_estimate/ESTIMATE.md`.

**Step 2a, rules from public text.** Three rule sets, every rule with source,
locator, verbatim passage and basis, each checked by a second reader until
both agreed: tenancy 51 rules (Code of Obligations), dismissal 74 rules (Code
of Obligations, Civil Procedure Code), theft 52 rules (Insurance Contract Act
and one insurer's published household conditions and claim form). One
convention of the benchmark, the same words in every regime, says what an
unmentioned fact is taken to be (`SPEC.md` 6a, 6b). Raw downloads stay out of
the repository; an early work-in-progress commit (`b70195ee`) contains three
public insurer PDFs and statute files, removed from tracking since; history
was not rewritten.

**Step 2b, references.** Per regime two blind evaluators wrote an evaluator
from the prose rule text only. Engine, evaluator A and evaluator B agree on
1,240 of 1,240 document decisions on the development designs, and holds wait
for the same fact. `study4/dev/CLEANROOM.md`.

**Step 2c, generator.** Seeded designs (share of files with an open fact 0, 10,
25, 50%; denied defining event a fixed tenth; German and English), texts by a
session of a model family that is not evaluated, working without product code,
prompts or rule text beyond the condition questions; blind check; one rewrite
round; scan noise on a fifth. Development sets: 176 of 180 files kept (tenancy
59, theft 59, dismissal 58); 4 dropped after the rewrite and counted.

**Step 2d, lint with planted defects (USD 2.79 of 3.50; design hashed before
any call).** On the cited rule sets the lint flags none of 47 untouched branch
conditions (on Study 3's tenancy rules it flagged 8 or 9 of 10). It detects 10
of 19 bluntly widened conditions (two more have too few files to assess) and 0
of 3 subtly widened ones (tenancy only). A blunt widening is missed when the
generated text does not make the widened wording true, so detection measures
lint and wording together. `study4/lint/REPORT.md`.

**First look at the tested core on the new regimes (same runs; no baseline, no
comparison).** Errors per file against the references: tenancy 0.36, theft
1.14, dismissal 0.79. The product failed to route 37 of 176 files to a type
(19 of them files that deny their defining event); in theft the routing
question reads ten ordinary thefts as "other".

**Step 2, after first use (USD 1.03 more; step total USD 3.82 of 4.00).** A
replay of all 134 first-look errors through the product's own evaluator
assigned each to one cause (`study4/lint/DIAGNOSIS.md`): rule wording 39,
product reading or document judgment 35, benchmark design 34, text against
recorded state 14, wording of document requirements 12; none from a workflow
differing from its reference. Repairs, all by general rules and none changing
a reference: routing questions and three fact questions reworded (revision 1);
document requirements made checkable (revision 2, `SPEC.md` 6c); four wordings
narrowed and two rulings applied after the second reader's look, and the
routing questions put into the rule text every design reads (revision 3); the
generator forbids a denial that states another type's event and shows writer
and blind reader each condition's "not this" line. Eight denied-event texts
were rewritten and all 24 re-checked blind; three theft files were dropped.
Development sets now: 173 files (tenancy 59, theft 56, dismissal 58). The
tested product, once, on the repaired benchmark (in-sample; no baseline):
dismissal 0.79 → 0.57 errors per file, theft 1.09 → 0.61; tenancy stopped at
the budget line after 28 of 59 files (0.39 → 0.25 on those) and is not a
regime figure. What remains is the product's: supplied-document judgments
(0.21 per file), holds because a quotation was not found word for word in
scanned text (0.12), holds because one of three readings disagreed (0.11),
routing (0.11; the dismissal routing question needs another look).
`study4/lint/REV3.md`.
