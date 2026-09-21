> **HISTORICAL RESEARCH RECORD — not the submission claim.** This file documents the earlier
> process-induction line, whose positive claims were **withdrawn** after a constant-oracle and
> wrong-pairing audit; see `PAIRED_DESIGN_DEGENERACY.md` for what failed and why. The submitted
> ICLR 2027 paper is `research/casepath/iclr2027-integrated/`, and its Study A benchmark reproduces
> offline from `research/casepath/branch-benchmark/`. `research/casepath/iclr2027/` is a separate,
> unsubmitted paper from this same historical line. Numbers in this file must not be quoted as
> current results.

> ## ⚠ SUPERSEDED IN PART — read `PAIRED_DESIGN_DEGENERACY.md` first
>
> An adversarial review panel (verdict: **reject as submitted**) overturned the central claim after this handoff
> was written. **Three results below are withdrawn:** that the compiled pipeline carries signal, that direct
> prediction is anti-correlated, and that the paired design escapes degeneracy.
>
> A case-ignoring constant scores **+0.447 [+0.429, +0.476]** against the best arm's **+0.118** — 3.8×. The winning
> arm emits **one** distinct request set across 28 pairs. A permutation null leaves one "signal" arm's statistic
> *exactly invariant*. The ground truth was authored by **the same model that wins** (`gpt-5.6-terra`,
> `runners/conf_ref.py:29`), so every unanimity figure is self-consistency, not inter-rater agreement.
>
> §2's tables remain accurate as *computations*; what is withdrawn is what they were taken to mean. §3 (errors) and
> §5 (traps) remain fully valid — and two further errors are added: I failed to run a constant-output oracle while
> explicitly hunting the static version of that same degeneracy, and I did not notice the adjudicator was drawn
> from the systems under test.
>
> Current paper: **"A Case-Ignoring Constant Beats Every Arm: Degeneracy Survives the Move from Static Checklists
> to Paired Retraction"** (`PAPER.md`, 1694 lines, 29 TODOs, panel-revised). Binding limit: **zero scopes of two**.

# Research handoff — CasePath, 2026-09-16

Everything needed to resume without re-deriving anything. Read this first, then `PAPER.md`.

---

## 1. What the work is now

The project pivoted twice. It is **no longer** a method paper about CTES (superseded, `research/ctes/`) and it is
**no longer** a method paper about process induction. It is a **measurement and negative-results paper**.

**Central finding.** Hold the induced process graph, the reference contract, the case corpus and the pipeline code
fixed. Change only the model that interprets a case against them. The identical artifact scores **+0.119** excess
withdrawal recall on one reasoner and **−0.077** on another, intervals non-overlapping. A single-model evaluation
of a structured representation measures the *pairing* and attributes it to the representation.

**Title (current):** *A Source-Grounded Process Representation Does Not Confer Correct Retraction Behaviour: The
Interpreting Model Decides the Sign.*

---

## 2. The four results, with provenance

All reproduce from committed artifacts. `cd casepath-api` then run the scripts in `research/casepath/`.

### 2.1 Static task is degenerate — **two scopes, replicated**

| scope | cases | distinct ground-truth checklists | mean reference set |
|---|---|---|---|
| rent increase | 30 | **1** | 10.0 |
| termination | 49 | **1** | 17.0 |

Six-arm floor check: five arms within **0.034 F1** (0.601–0.635); modal-list oracle **F1 1.000**.
Script: `development_analysis.py`. Docs: `STATIC_TASK_SATURATION.md`, `STATIC_FLOOR.md`.

### 2.2 Confirmatory read (rent increase, gpt-5.6-terra, 28 held-out pairs, 6 scenarios)

| arm | recall | own random baseline | excess | 95% CI |
|---|---|---|---|---|
| b1_direct | 0.038 | 0.099 | **−0.061** | [−0.096, −0.026] |
| b3_graph_then_list | 0.121 | 0.110 | +0.011 | [−0.017, +0.038] |
| b5_induced_graph | 0.591 | 0.473 | **+0.118** | [+0.106, +0.126] |

Uncontrolled, b5−b1 reads **+0.553**. The volume control is worth **4.7×** and inverts b1's sign.
Script: `confirmatory_analysis.py`. Doc: `RESULTS.md` §2.

### 2.3 Model generality — **the central result** (same 28 pairs, same frozen artifact)

| model | b1_direct | b5_induced_graph |
|---|---|---|
| gpt-5.6-terra | **−0.061** [−0.096, −0.026] anti-corr | **+0.119** [+0.108, +0.125] signal |
| claude-haiku-4.5 | +0.003 none | **−0.077** [−0.092, −0.070] anti-corr |
| gemini-2.5-flash | +0.001 none | **+0.109** [+0.107, +0.112] signal |
| deepseek-v3.2 | +0.010 none | **−0.034** [−0.037, −0.031] anti-corr |

Zero execution errors on every model. Predicate resolution 10–12% everywhere (27/28/467, 32/28/462, 32/29/461,
**30/29/463**). Script: `model_generality_analysis.py`. Doc: `MODEL_GENERALITY.md`.

### 2.4 Transfer to termination — **not supported** (49 pairs, 8 scenarios)

No arm's interval excludes zero (+0.015, +0.019, −0.012). b5 requests 16 of 18 documents, retains 0.992, withdrew
6 documents total, **none correct**. The ceiling was computed from the contract *before* the run: the probed
decision releases 3 documents against the rent-increase probe's 6; measured, 1.57 per pair.
Script: `transfer_analysis.py`. Doc: `TRANSFER_RESULT.md`.

---

## 3. Errors I made and corrected — **do not re-introduce these**

1. **False structural-impossibility proof.** I computed that b5's withdrawal recall was capped at 0.000 and
   committed a document acting on it (`b45bf4c`). The computation pooled each node's document supply *across*
   cases when the compiler recomputes it *per case*. Data refuted it. Corrected at `df63478`.
2. **Retracted a cross-scope fabrication rate.** I nearly published "25–60% of quotes fail verification across
   scopes". It was an artifact of contracts storing sources and quotes as unmapped parallel lists, so guide quotes
   were tested against statutes. Once the corpus covered the cited articles the same contract verified at
   **85.8%**. Retracted at `b6c9195`.
3. **Amendment A3 was a mistake.** I moved the preregistered primary away from `b5` on development evidence that
   was unrepresentative (all four development scenarios were form-defect disputes, which activate nodes carrying no
   evidentiary obligation). Declared before the read, so the original primary survived in the record — which is the
   only reason the result was recoverable. **The fact-checkers then found A3's own basis no longer reproduces**:
   re-running gives b3−b1 = +0.104 **[+0.000, +0.229]**, now including zero.
4. **Called a synthetic corpus "real cases"** throughout, until the fact-checkers caught it.
5. **Wrote DeepSeek diagnostics from partial data** (13/15/232); correct values are **30/29/463**.

---

## 4. Immediate next steps, in priority order

1. **Collect the hostile review** (workflow `wf_6f21ba42-ea1`, run ID in
   `.claude/projects/.../subagents/workflows/`). Five lenses — statistics, construct validity, novelty,
   reproducibility, clarity — plus a triage agent that applies revisions directly to `PAPER.md`. It was at 5 of 6
   agents when this handoff was written. Read its journal:
   `python3 -c "import json;[print(json.loads(l).get('type')) for l in open('<dir>/journal.jsonl')]"`.
2. **Close the 20 TODOs in `PAPER.md`.** They are listed in a consolidated block at the end of the file. Most are
   `TODO[number not found]` or `TODO[verify]` — none require new model calls except possibly the termination
   modal-oracle F1, which is computable from committed artifacts.
3. **Resolve the A3 non-reproduction** (see §3.3). Either explain the discrepancy or report the re-measured figure
   as authoritative. Do not quietly keep the original.
4. **Decide the paper's venue framing.** It is currently a measurement paper. The honest alternative is a
   "lessons/negative results" track submission.
5. **Optional, costs credits:** a fifth reasoner would strengthen the 2-of-4 split. Nothing else needs credits.

---

## 5. Traps and constraints

- **OpenRouter credits: $304.47 remaining** of 617. Session spend was ~$15. The key lives only at
  `~/.config/casepath/openrouter.key` (0600), read via `CASEPATH_OPENROUTER_KEY_FILE`. **Never print, log or commit
  it.**
- **Do not touch** `casepath/assets/agent-work-v1.css`, `agent-work-v1.js`, `casepath/index.html`,
  `casepath/source-manifest.json` — product-owned, in flight elsewhere. Verified: zero commits from this session.
- **Test suite: 975 pass, 7 fail.** All 7 are in `test_cli_v1.py` and fail because `casepath/source-manifest.json`
  pins hashes for ten files last modified 2026-09-15, before this session. None of this work's modules is in its
  1348 entries. Fix is a manifest regeneration by whoever owns the release. Doc: `TEST_SUITE_STATUS.md`.
- **The novelty audit's synthesizer output is unusable** — I sliced its input at 40k chars so it saw 1 claim of 5
  and then pulled in unrelated superseded CTES material. The per-claim verdicts in `NOVELTY_AUDIT.md` were
  extracted from the run journal and *are* reliable. Raw: `NOVELTY_AUDIT_raw.txt`.
- **Never claim "constitutive rather than diagnostic" as ours.** Preempted by Wang 2026, GopherCite 2022, CHyD
  2026, CANONIC 2026.
- **Never report a withdrawal/retraction metric without the per-arm random-drop control.** It is worth 4.7× and
  flips signs.
- **Cite nothing marked `search_result_only` or `recalled_uncertain`** in the novelty audit. Only
  `verified_source_read`.

---

## 6. File map

```
research/casepath/
  PAPER.md                        the submission draft (1098 lines, 20 TODOs)
  HANDOFF.md                      this file
  RESULTS.md                      canonical results, all four experiments
  CANONICAL_RESULTS.json          every headline number, machine-readable
  MODEL_GENERALITY.md             the central result
  TRANSFER_RESULT.md              the negative transfer
  STATIC_TASK_SATURATION.md       degeneracy, both scopes
  STATIC_FLOOR.md                 six-arm floor check
  NOVELTY_AUDIT.md                what survives prior work (+ _raw.txt)
  PREREGISTRATION.md              plan, amendments A1/A3, outcome
  TRANSFER_PREREGISTRATION.md     transfer plan + amendment T1
  METHOD.md  LIMITATIONS.md  REPRODUCIBILITY.md  CONTRIBUTION.md
  PIPELINE_STATUS.md  TEST_SUITE_STATUS.md  CITATION_FIDELITY.md
  CORPUS_CONTAMINATION.md         the 33% contaminated bucket and the fix
  INDEPENDENT_INDUCTION_DIVERGENCE.md  two inductions partition differently
  ENTRY_PREDICATE_DEFECT.md       the unrepaired applicability-gate defect
  DEV_RESULT_e07.md               superseded; kept because A3 rested on it
  artifacts/                      25 run artifacts + MANIFEST.json (33 MB)
  runners/                        9 runner scripts incl. multimodel.py
  reference_contracts/            rent_increase.json (gated), termination.gated.json, +3 ungated
  splits/                         frozen scenario split
  verify_artifacts.py             release gate: hashes, quote gate, split isolation
  *_analysis.py                   4 analysis scripts, all reading committed artifacts
casepath-api/casepath_api/
  authority_corpus_v1.py  process_induction_v1.py  case_interpreter_v1.py
  obligation_compiler_v1.py  process_experiment_v1.py  contract_scoring_v1.py
  casepath_process_service_v1.py  checklist_baselines_v1.py
```

**Reproduce everything:** `cd casepath-api && ../.runtime/casepath-dev-v2/venv/bin/python
../research/casepath/<script>.py` — no network calls, reads committed artifacts.
**Verify integrity:** `python ../research/casepath/verify_artifacts.py` (exits non-zero on failure).

---

## 7. What is and is not established

**Established.** A static document-checklist benchmark in this domain cannot separate methods (two scopes).
Retraction metrics require a per-arm volume control or they overstate ~4.7× and can invert a sign. A frozen
source-grounded representation does **not** confer correct retraction independent of the reasoner (four models,
non-overlapping intervals, zero errors).

**Not established.** That the method works in general. The positive effect holds on **one scope of two** and **two
reasoners of four**, and nothing predicts the boundary short of running it — except the ceiling computation, which
did correctly predict the transfer failure in advance.

**Unrepaired.** The graph has no applicability gate (its entry node has no incoming condition, so the process
cannot be told the scope does not apply). The re-induced `graph_s2_v2` — which adds the substantive-determination
node the first lacked — was produced after seeing development results and is **unevaluated**; it was deliberately
excluded from the held-out read.
