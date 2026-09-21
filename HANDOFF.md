# CasePath — research handoff (written 2026-09-21, verified against files on disk)

This file is for someone with no access to the sessions that produced the work. Every path below was
checked on disk when this file was written; where something could not be verified it is marked
**UNVERIFIED**. Numbers are quoted from evidence files, never from memory.

Two machines/agents have been working in parallel:

* **This checkout** (`~/Documents/ChatGPT/CasePath Agentic Acceptance 20260915d/casepath`, git remote
  `github` = `https://github.com/KumarNavish/casepath.git`, branch `main`) — the CasePath product plus the
  research line described here. The submission-ready manuscript is `research/casepath/iclr2027-integrated/`.
* **Codex/"Astra" state root** (`~/.local/state/navish-acceptance-20260919/`, workspace
  `~/Documents/Die Mobiliar`) — runs the 150-claim Study B experiment and keeps an older manuscript copy.
  Read `final-publication/CONTINUE.md` there first. **One-writer rule:** never launch, resend or reconcile
  anything under `mac-native150/` while Codex is active; never touch its ledger.

---

## 1. CLAIM

**Submitted title/abstract (locked, ICLR 2027, paper deadline 2026-09-25 23:59 AOE):**
"CasePath: An Agentic, Process-First Architecture for Determining Evidence Requirements". The abstract
(`research/casepath/iclr2027-integrated/submitted_frontmatter.tex`) claims: a source-defined process, not the
LLM, controls evidence acquisition; tested on matched cases differing in one branch-defining fact; *across
27 held-out pairs CasePath makes 15 false-positive document changes versus at least 27 for every comparison
system*.

**What the evidence supports (Study A, frozen V5 theft benchmark, one-shot held-out read):**
* spurious signed changes 15 vs 27 (Direct), 41 (Graph as context), 52 (Evidence-first);
* micro-F1 0.667 vs 0.588 / 0.590 / 0.317; precision 0.615; exact pairs 12/27;
* wrong-family reassignment collapses F1 to ≤ 0.083 (mean 0.011) over 5,008 evaluated reassignments;
* input-free (leave-one-family-out constant) predictor: max held-out micro-F1 0.0.

**What it does not support (stated in the paper):** the preregistered broad-superiority gate FAILS
(F1 margins +0.078/+0.076 < 0.10; precision 0.615 < 0.70; Holm-adjusted family-swap p = 0.797/0.797/0.129).
CasePath scores zero on two of nine branch concepts (third-party causer, formal expert procedure).

**Study B (150-claim native corpus):** protocol frozen and executing; **no scores exist** (scoring is
contractually deferred until both prediction freezes). The paper reports the protocol and the completed
development-split execution record only.

## 2. METHOD

Chain: source → process node → obligation → required fact → evidence capability → document route (closed
catalogue). Three-valued guards (true/false/unresolved) decided per guard per case with an exact-quote gate;
unresolved ⇒ clarification question, never branch-specific documents; plan = deterministic projection of active
chains (Eq. 3 of the paper). Study B controller adds acquisition permission and per-capability route
sufficiency (Eqs. 4–5). Full text: `research/casepath/iclr2027-integrated/method.tex`.

Semantic roles are model calls (extraction, process synthesis, rule refinement, catalogue mapping, guard
interpretation); code owns activation, projection, route selection, next action and justification.

## 3. SETUP

**Study A** (all values from `research/casepath/iclr2027-integrated/evidence/`):
* Sources: 197 exact passages (Fedlex, CSS, AXA, Generali, Simpego, SVV); 308 propositions; 98 evidence rules;
  87 guards; 13 non-evidentiary classifications; 33 document types (`HISTORICAL_AUDIT.json`).
* Benchmark: 9 branch concepts × 4 contexts = 36 pairs / 72 units; development 9 pairs, held-out 27 pairs read
  once after hash-freeze (`SHORTCUT_PREFLIGHT_V3.json`, `HISTORICAL_AUDIT.json`).
* Model: `openai/gpt-5.6-terra`, OpenAI provider restriction, temperature 0; calls 54/54/108/87
  (Direct / Graph as context / Evidence-first / CasePath); costs USD 4.83 / 8.41 / 1.06 / 5.44
  (`PAIRED_V5_RECEIPT_ACCOUNTING.json`). Not compute-matched.
* Statistics: 10,000 family-cluster bootstrap draws (seed 20260917); exact 2^9 family sign-flip with Holm;
  wrong-pairing null = 8 cyclic shifts + 5,000 derangements (`PAIRED_V5_REPRODUCED_RESULT.json`).
* Product parity: 72/72 units and 36/36 pair deltas match on replay with recorded guard decisions
  (`PAIRED_V5_REPRODUCED_PARITY.json`).

**Study B** (`PUBLICATION_STATIC_FACTS.json`, `ANALYSIS_CONTRACT.json`, `studyB_execution_status_695.json`):
* 150 synthetic tenancy claims, 28 families, 3 domains; dev 60/11 families, protected 90/17 families.
* 7 arms: CASEPATH_CONTROL, DIRECT_REVIEWED, DOCUMENT_FIRST_REVIEWED, PROCESS_CONTEXT_REVIEWED,
  RULE_FIRST_REVIEWED (learned, 2 calls each, medium reasoning, 4,096 completion tokens) + COMPILED_EQUIVALENT,
  LOCAL_SCOPE_ABLATION (dependent). 1,050 cells (750 learned + 300 dependent).
* Endpoints: emitted-checklist F1, critical-evidence recall, unnecessary fraction; conservative −1 contrasts;
  boundaries +0.03/−0.03/−0.03; family-deletion sensitivity; no p-values.
* Execution as of 2026-09-21 12:25 UTC: 829/1,050 cells recorded (420/420 dev, 409/630 protected;
  `evidence/studyB_execution_status.json`, regenerated by `build_manuscript_numbers.py` from the newest
  `mac-native150/*/work/output/cells` directory). Dev validation failures: CasePath 16/60; Direct 41;
  Document-first 43; Process-context 33; Rule-first 32. History of the run (from Codex's thread and
  `mac-native150/*/run/TERMINAL.json`): lid-close sleep stop at 07:01 UTC; replacement launches at 07:41 and
  ~07:59 UTC exited with code 3 (`local_clock_discontinuity`); a later worker reached 814 records at the
  11:22 UTC cutoff; the pre-approved one-day extension is now ACTIVE (latest allowed send 2026-09-22 11:16 UTC);
  a four-request-concurrency worker was relaunched by Codex at 12:11 UTC with USD 70.04 charged against the
  USD 236.80 ceiling and 233 cells remaining. **Whether Study B finishes remains outside this checkout's
  control; nothing under `mac-native150/` was touched.**

## 4. RESULTS

| Arm | Prec | Recall | F1 | Exact | Pred/Gold | Spurious | Missed |
|---|---|---|---|---|---|---|---|
| Direct | 0.481 | 0.758 | 0.588 | 0.333 | 52/33 | 27 | 8 |
| Graph as context | 0.431 | 0.939 | 0.590 | 0.148 | 72/33 | 41 | 2 |
| Evidence-first | 0.235 | 0.485 | 0.317 | 0.074 | 68/33 | 52 | 17 |
| CasePath (V5) | 0.615 | 0.727 | 0.667 | 0.444 | 39/33 | 15 | 9 |

95% family-cluster CIs: CasePath [0.435, 0.880]; Direct [0.404, 0.759]; Graph [0.471, 0.716];
Evidence-first [0.239, 0.400]. Paired differences vs Direct [−0.253, +0.420], vs Graph [−0.199, +0.333],
vs Evidence-first [+0.110, +0.565]. Chain attribution 39/39; gold-chain coverage 27/33 (81.8%).
Per-concept F1 and gate table: `research/casepath/iclr2027-integrated/table_family_results.tex`,
`table_claim_gates.tex`. Study B: no results yet (see §7).

## 5. ARTIFACTS

* **Manuscript source:** `research/casepath/iclr2027-integrated/` (main.tex + 12 section files, numbers.tex,
  5 generated tables, 7 figures, references.bib with 44 entries / 38 cited, official
  `iclr2027_conference.sty/.bst` whose SHA-256 match `~/.local/state/navish-acceptance-20260919/final-publication/ICLR_2027_SUBMISSION_REQUIREMENTS.json`).
* **Build:** `.runtime/tools/tectonic/tectonic main.tex` (Tectonic 0.17.0, XeTeX). 16 pages; main text
  ends on page 9 (`\label{end-of-main-text}` → `main.aux`); AI-use statement and references follow.
* **Deliverables:** `research/casepath/iclr2027-integrated/dist/casepath_iclr2027_submission_source.zip`
  (Overleaf-ready) and `dist/casepath_iclr2027_submission.pdf`.
* **Benchmark release (new 2026-09-21):** `research/casepath/branch-benchmark/` — the 36-pair
  benchmark, source snapshot, admission controls, recorded predictions of all four arms for both
  splits, the frozen scorer/statistics, freeze records and the product-parity report, with
  `MANIFEST.json` giving each file's sha256 and its path inside the release archive (bytes
  unchanged; only the layout was reorganised). `python3 reproduce.py` verifies the hashes and
  recomputes the held-out result offline in ~7 s; it matched the preserved report on every value
  (10 values differ only by floating-point summation order, largest deviation 1.1e-16).
  `research/casepath/iclr2027-integrated/evidence/check_against_benchmark_release.py` then confirms
  86 paper macros against that fresh recomputation.
* **Numerical audit:** `evidence/build_manuscript_numbers.py` regenerates every number macro and table from the
  evidence files and writes `evidence/NUMERICAL_AUDIT.json` (215 macros; each with evidence file SHA-256 and
  JSON pointer). `evidence/check_literal_numbers.py` lists any literal number left in prose (only figure widths,
  the CHF amounts of the quoted example pair, the 95% CI level and "temperature 0" remain).
* **Citation verification:** `evidence/CITATION_VERIFICATION.json` (38/38 cited keys verified by arXiv id, DOI,
  PMLR listing or reachable URL); raw lookups in `evidence/bib_verification_*.json`.
* **Study B injector:** `evidence/build_native_results.py FINITE_REPORT.json` → `native_results_numbers.tex`,
  `table_native_results.tex`, `evidence/NATIVE_RESULTS_AUDIT.json` (smoke-tested on a synthetic report in a
  scratch directory only).
* **Study B release builder (new 2026-09-21):** `research/casepath/iclr2027-integrated/evidence/build_native_release.py
  --evidence <final-evidence-dir>` assembles `research/casepath/native-corpus/`: the scored rows of both splits,
  the released report, the frozen `finite_reporting.py` (byte-identical, with a shim for its one infrastructure
  import), the analysis contract, the cell plan, a target-free per-cell execution index, a hash manifest, a
  generated `README.md` whose numbers all come from the report, and a generated `reproduce.py` that recomputes
  the report from the rows. It refuses to build unless `RESULT.state == finite_corpus_evaluated` and the report
  declares `statistical_significance_computed = false`, and it verifies the bundle by running the reproduction.
  Validated end to end on a synthetic export in a scratch directory (13 files, exact recomputation); `--dry-run`
  validates an export without writing.
* **Authenticated Study A evidence (Codex):** `~/.local/state/navish-acceptance-20260919/final-publication/submitted-foundation/`
  (`PAIRED_V5_REPRODUCED_RESULT.json`, `PAIRED_V5_RECEIPT_ACCOUNTING.json`, `PAIRED_V5_REPRODUCED_PARITY.json`,
  `CasePath_ICLR2027_Anonymous_Release_v5.zip` = the V5 reproducibility archive, 3.2 MB).
* **Study B state:** `~/.local/state/navish-acceptance-20260919/mac-native150/deterministic-failure-continuation/work/output/cells/`
  (695 cell JSONs), `final-execution-bridge-854b8a85/ANALYSIS_CONTRACT.json`, `PRO_NATIVE150_MATRIX.jsonl`.
* **Overleaf:** original (read-only, do not modify) `https://www.overleaf.com/project/6aac718dca785b22bced2b83`;
  Codex's project `https://www.overleaf.com/project/6ab03c462d2eaea03e194fb2` holds **Codex's older
  manuscript**; **this manuscript** was uploaded to a separate project
  `https://www.overleaf.com/project/6ab0eea72f79f49c515c7853` ("CasePath - ICLR 2027 Submission (integrated,
  2026-09-21)"), confirmed reachable from the author's logged-in browser on 2026-09-21 12:30 UTC; `numbers.tex` and
  `table_native_execution.tex` were re-uploaded there at 12:45 UTC (829-cell execution record) and the
  project recompiles to 16 pages.

## 6. REPO MAP (this checkout)

* `casepath/` — the sealed product (index.html, assets/agent-work-v1.*, source-manifest.json). Do not edit.
* `research/casepath/iclr2027-integrated/` — **the submission manuscript** (this handoff's subject).
* `research/casepath/iclr2027/` — an earlier alternative paper ("Can the Score Be Earned Without the Input?",
  falsification-audit line). Not the submitted abstract. Its working tree has uncommitted modifications from an
  earlier session (see `git status`); left untouched.
* `research/casepath/*.md`, `artifacts/`, `runners/`, `*_analysis.py` — the earlier process-induction line whose
  positive claims were withdrawn (`PAIRED_DESIGN_DEGENERACY.md`). Historical evidence only.
* `research/casepath/HANDOFF.md` — the 2026-09-16 handoff of that earlier line; superseded by this file.
* `.runtime/tools/tectonic/tectonic` — the LaTeX engine used for all builds.

## 7. GAPS

1. **Study B results are absent.** The paper honestly reports protocol + execution record. When Codex produces
   `FINITE_REPORT.json` (state `finite_corpus_evaluated`), run the injector, add
   `\input{native_results_numbers.tex}` to `main.tex`, write the results paragraph in `native_study.tex` from
   the generated macros, recompile, and re-run the two check scripts. If Study B never completes, the paper is
   submittable as is; the abstract's claim rests on Study A.
2. **Overleaf sync.** After any local change, re-upload `dist/casepath_iclr2027_submission_source.zip` into
   project `6ab0eea72f79f49c515c7853` (replace all files), compile there and confirm the main text ends on
   page 9. Codex's automation writes only to its own project `6ab03c46…`; do not let the two be confused at
   submission time.
3. **Two manuscript versions exist.** Codex's copy (`final-publication/overleaf-submission-integrated/`) is the
   cautious two-study assembly this rewrite started from; this checkout's version supersedes it.
4. **OpenReview submission** must be done by the author: anonymous PDF, supplementary zip (V5 archive + Study B
   release when available), and the mandatory AI-use disclosure form.
5. **Git:** `main` is pushed to `github/main` (re-checked 2026-09-21 13:00 UTC). Re-check after further commits.
6. **Uncommitted work in the older research line (deliberately not landed).** `git status` shows ~26 modified
   and ~117 untracked files under `research/casepath/` outside the submission directories: substantive Sep 16-17
   work on the falsification-audit line, including the separate unsubmitted paper `research/casepath/iclr2027/`
   (main.tex/main.pdf/figures), `release_set_validity_analysis.py` (~312 changed lines) and artifact JSONs that
   embed raw provider responses — about 8,700 added lines in total. This session landed **only** the seven
   Markdown notice headers (commit `4ce8a1b`), because the committed copies of `PAPER.md`, `RESULTS.md` and
   their siblings otherwise present withdrawn claims with no notice. Everything else is left for the author to
   review; it is not needed for the submission and was not read line by line here.
7. **Unverified claims to avoid:** any Study B score; any statement that CasePath is statistically superior;
   any transfer to unseen rules or domains; live-inference product parity (parity is conditional on recorded
   guard decisions).

## 8. PRIOR WRITING

* `research/casepath/iclr2027-integrated/` — this manuscript (current).
* `~/.local/state/navish-acceptance-20260919/final-publication/overleaf-submission-integrated/` — Codex's
  integrated draft (Sep 20), plus `DESIGN.md`, `METHOD_AND_METRIC_SOURCE_MAP.md`, `PRO_*.md` (GPT-6 Pro
  decisions), `INTEGRATED_NUMERICAL_AUDIT.json`, `CITATION_CLAIM_AUDIT.json`.
* V5 method-pack paper inside `CasePath_ICLR2027_Anonymous_Release_v5.zip` (`research/casepath/iclr2027_method_v5/main.tex`):
  the complete Study A exposition this rewrite draws on.
* `research/casepath/iclr2027/main.tex` — the falsification-audit paper (alternative framing, not submitted).
* `research/casepath/PAPER.md`, `RESULTS.md`, `PAIRED_DESIGN_DEGENERACY.md`, `NOVELTY_AUDIT.md` — the withdrawn
  process-induction line and why it was withdrawn (constant-oracle and wrong-pairing audits).
