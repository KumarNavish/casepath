# Verified evidence and remaining requirements

Paper A (TMIS): *CasePath: Executing Process Rules over LLM Judgments to Request Evidence*
Branch `claude/casepath-tmis-paper-20261109` of `KumarNavish/casepath`, folder `research/tmis2026/`.

## 1. Bottom line

The evidence changes the paper's central claim. The ICLR version argued that executing rules is more accurate. The new experiments show that **this depends on the model**:

- **With the cost-efficient model (gpt-6-luna, the product's model), execution wins clearly.**
  - Unsafe errors: 4× fewer on complete request lists (0.03 vs 0.11 per claim, Holm p = 0.031).
  - Wrong changes when a fact changes: 4× fewer (17 vs 68, p = 0.012).
- **With the frontier model (gpt-6.1-terra), rules in the prompt do as well or better**, but the differences are not significant. The reason is that execution reproduces the errors of automatically extracted rules exactly.
- **What holds across models:**
  - Execution makes request quality far less model-dependent (0.21–0.56 vs 0.27–1.52 wrong changes per pair across three models).
  - It never requests prematurely, by construction.
  - Every error is traceable to a rule or a judgment.
- **Its price is deferral:** 20–30% of required documents are held behind questions, most of them waiting on one unstated routing fact.

The paper now argues exactly this. No result was typed by hand: every number in the PDF is generated from the evidence files.

## 2. What was run

| Item | Detail |
|---|---|
| Agent | Latest CasePath (`claude/casepath-internal-20261027` @ `aa4fb25`). The production admission, process compiler and causal process engine are called unchanged. |
| Models | `openai/gpt-6.1-terra` (frontier) and `openai/gpt-6-luna` (cost-efficient, the product's configured model), via OpenRouter, low reasoning effort, strict JSON schema. The original study's `gpt-5.6-terra` predictions were re-scored. |
| Tenancy | 90 held-out claims (17 families), 3 runs per design and model. |
| Theft | 27 changed-fact pairs plus 18 new unresolved-fact pairs, 3 runs per design and model. |
| Designs | Direct; Rules in context; Self-consistency (majority of 3); Model executes rules; Two-valued execution (open read as false or as true); CasePath (product engine and exact deferral, with and without the verifier). |
| Plan | `ANALYSIS_PLAN.md`, frozen in commit `46a503b` before any held-out run. |
| Statistics | Cluster bootstrap (10,000 resamples) over 17 families or 9 conditions; exact sign-flip tests; Holm correction over H1–H5. |
| Spend | USD 9.42 in total: 8.61 terra and 0.81 luna, including pilots and diagnostics. Every call is logged in `runs/ledger.jsonl`. |

## 3. Results

### Pre-specified tests (Holm-adjusted p)

| Claim | gpt-6.1-terra | gpt-6-luna |
|---|---|---|
| H1 Unsafe errors on complete lists (CasePath exact vs Rules in context) | 0.08 vs 0.06 per claim; no sig. difference (p = 0.42) | **0.03 vs 0.11; fewer with CasePath (p = 0.031)** |
| H2 Deferred required documents | more with CasePath (p < 0.001) | more with CasePath (p < 0.001) |
| H3 Wrong changes when a fact changes | 38 vs 22; no sig. difference (p = 0.42) | **17 vs 68; fewer with CasePath (p = 0.012)** |
| H4 Other requests unchanged when a fact is open | 72% vs 98%; no sig. difference (p = 0.094) | **89% vs 43%; better with CasePath (p = 0.031)** |
| H5 Test–retest agreement (tenancy) | not supported: rules in context higher (p = 0.002) | not supported: rules in context higher (p = 0.006) |

H2's second part was **not supported**. It predicted that exact deferral would cut deferrals without adding unsafe errors:

- Exact deferral removed 43% (terra) and 58% (luna) of the product engine's deferrals.
- It added no unnecessary request.
- It added 4 and 2 silent misses among 1,779 required documents. Each was a supplied document that CasePath had judged sufficient and that the reference marks as insufficient (5) or missing (1). The product engine had hidden these errors by holding the documents.

### Tenancy

Requested / deferred / silently missed, as % of required documents; unnecessary as % of requests.

| Design | gpt-6.1-terra | gpt-6-luna |
|---|---|---|
| Rules in context | 96.6 / 2.6 / 0.8 / 0.1 | 96.6 / 1.8 / 1.6 / 0.1 |
| — majority of 3 | 96.6 / 2.5 / 0.8 / 0.2 | 97.0 / 1.7 / 1.3 / 0.0 |
| Model executes rules | 78.1 / 21.0 / 0.9 / 0.6 | not run |
| CasePath, product engine | 45.9 / 53.5 / 0.6 / 0.8 | 53.1 / 46.7 / 0.3 / 0.0 |
| CasePath, exact deferral | 68.9 / 30.2 / 0.8 / 0.6 | 79.8 / 19.8 / 0.4 / 0.0 |
| — without verifier | 79.8 / 19.3 / 0.8 / 0.5 | 87.8 / 11.6 / 0.6 / 0.0 |
| Two-valued, open read as false | 68.9 / 0 / 31.1 / 0.6 | 79.8 / 0 / 20.2 / 0.0 |
| Two-valued, open read as true | 94.3 / 0 / 5.7 / 29.5 | 95.4 / 0 / 4.6 / 29.4 |

### Theft

Wrong changes / missed changes / F1 over 81 pair runs, and the share of unresolved-fact pairs with no other request changed.

| Design | gpt-6.1-terra | gpt-6-luna |
|---|---|---|
| Direct | 43 / 28 / 0.664 / 43% | not run |
| Rules in context | 22 / 20 / 0.790 / 98% | 68 / 29 / 0.591 / 43% |
| — majority of 3 | 18 / 21 / 0.800 / 100% | 48 / 33 / 0.620 / 56% |
| CasePath | 38 / 30 / 0.670 / 72% | 17 / 20 / 0.810 / 89% |
| — without verifier | 32 / 28 / 0.703 / 81% | 29 / 15 / 0.792 / 80% |
| Two-valued, open read as true | 34 / 45 / 0.578 / 46% | 97 / 44 / 0.438 / 20% |

Premature requests on unresolved-fact pairs: CasePath 0% with both models. The in-context designs made premature requests in at most 2% of pairs. Reading open facts as true made them in 50–52%.

### Mechanisms and checks

- **Judgments are cautious, not wrong.**
  - Terra, of 1,170 condition judgments: 428 matched the reference, 7 contradicted it, 735 were unresolved. 638 of the unresolved concern facts that the claim never mentions and that the reference reads as false.
  - Luna: 450, 0 and 720.
- **The verifier helps only with the cheaper model.**
  - With terra it rejected 35 verdicts, all correct, and caught none of the 7 wrong ones.
  - With luna it cut wrong theft changes from 29 to 17 but increased tenancy deferrals.
- **Deferral causes.**
  - The unstated routing fact accounts for 74% of deferrals with terra (397 of 538) and 59% with luna (206 of 352).
  - Presuming that fact once the family is admitted (a post-hoc analysis, disclosed as such) gives recall of 95.6% and 95.0%, with 0.4% and 0.0% unnecessary requests.
- **Semantics.** On CasePath's recorded judgments, two-valued execution turns deferrals into errors:
  - reading open facts as false gives 31.1% and 20.2% silent misses;
  - reading them as true makes 29.5% and 29.4% of requests unnecessary.
- **Error origins (terra, theft).**
  - 37 of 38 wrong changes and 17 of 30 misses trace to 5 of 98 extracted rules.
  - A blind rule verifier flags all 5, plus 59 other rules.
  - Tenancy: CasePath's 7 unnecessary requests come from its 7 wrong verdicts, and its 15 misses are supplied files it judged sufficient.
- **Citations.**
  - Terra: 100% verbatim for every design.
  - Luna: 98.8% for rules in context and 99.4% for CasePath's interpreter. CasePath's admission rejects non-verbatim quotations.
- **Reference checks.**
  - Oracle: the true flags reproduce 147 of 150 tenancy reference sets.
  - A blind re-derivation reproduces 7 of 9 theft conditions exactly; on those 7, the design ranking is unchanged.
- **Original study.** The harness reproduces all 54 original CasePath checklists and the original scores (24 / 15 / 9, F1 0.667).
- **Exact computations (deterministic, all 150 claims).** Strong Kleene evaluation defers 68% more documents than necessary.
- **Engine runtime.** 65 ms for a 100-step process; 22 s for exact deferral over 10 open flags. Real claims have at most 5 flags.
- **Cost per case (USD × 10⁻³).**
  - Tenancy: CasePath 7.0 vs rules in context 5.5 (terra); 0.9 vs 0.7 (luna).
  - Theft: 15.4 vs 4.0 (terra); 1.9 vs 0.7 (luna).
  - CasePath with luna is at least as accurate on theft as terra with rules in context, at half the cost.

## 4. Corrections from the final evidence audit

Before packaging, every claim in the abstract, introduction, results, discussion and conclusion was checked against the evidence files. Four statements overstated the evidence and were corrected:

1. **Exact deferral.** "Halves deferrals without adding a single unsafe error" became the measured result: 43–58% fewer deferrals, no added unnecessary request, and 4 and 2 added silent misses, explained above. The paper now states that H2's second part was not supported.
2. **Deferral causes.** "Almost all" deferrals from the routing fact became "most" (74% and 59%). The cost-efficient model's numbers were added.
3. **Significance.** The frontier model's accuracy advantage on extracted rules is described as not significant in the abstract, introduction, guidance table and conclusion.
4. **Mismatched figure.** One sentence quoted F1 for a claim about wrong-change counts; it now gives the counts (17 vs 68).

One analysis script (`analysis/tenancy_extra.py`) always read the frontier model's cached responses, whatever model was named. It now binds the model before import and runs on cached responses only. The terra results reproduce unchanged, and the luna results are new. No model call was made.

The limitations section now also says why no ReAct-style tool-using agent was compared.

## 5. How to verify

```bash
cd research/tmis2026 && tar -xzf runs/responses_cache.tar.gz -C runs
```

```bash
cd research/tmis2026/analysis && python3 verify_paper.py
```

`verify_paper.py` recomputes every analysis from the saved plans and cached responses, with the budget capped so no model call is possible. It regenerates `paper/results/numbers.tex` and requires a byte-for-byte match, resolves every citation key, and compiles the paper from a clean copy. Current status: **all checks pass**, with 0 LaTeX errors, 0 undefined references and 0 overfull boxes.

## 6. Remaining requirements before submission

**Must**

1. **Resolve the ICLR 2027 submission (57404).** ACM does not permit simultaneous submission. Withdraw it, or wait for the decision, before submitting to TMIS.
2. **Co-author approval.** The conclusion now reverses for the frontier model. All four authors should approve this framing, the author order and affiliations, and add ORCIDs and funding to the acknowledgments.
3. **Template.** Remove `nonacm` from `\documentclass` in `main.tex`. TMIS reviews single-blind, so no `anonymous` option is needed. Confirm the CCS concepts in ACM's CCS tool.
4. **Length.** Running text in §1–7 is about 7,200 words, plus 9 tables, 4 figures, 1 algorithm and a 5-page appendix; the abstract has 199 words. I could not verify TMIS's current length limits from an official page (a search snippet suggested 4,000–6,000 words and a 150–200-word abstract). Check the current author guidelines. If a limit applies, move Appendix E (verbatim prompts) to supplementary material first, then Appendices B–C.
5. **Public release.** The data-availability statement (App. D) points to `github.com/KumarNavish/casepath`, folder `research/tmis2026`. That folder exists only on this branch, so the branch must be merged or the folder released as a tagged snapshot, ideally with a DOI. The repository must also be public by submission.
6. **AI-use statement.** App. D describes how generative AI was used in the method, in creating the original datasets, and in assisting the authors. Confirm it matches your actual use, including this revision.

**Should**

7. **Expert review of rules and references.** All three reviewers raised this; the paper discloses it as a limitation. A legal expert should check the 98 theft rules (start with the 64 the verifier flags) and a sample of both reference sets.
8. **Merge to `main`.** The ruleset requires a pull request, the "CasePath regression" check and CodeQL. No PR has been opened yet.

**Optional**

9. **sciCORE rerun.** The deterministic computations were run in the cloud container because the Mac running Commander was offline, so sciCORE was never reached. `scicore/array.sbatch` is ready; results should reproduce byte for byte. The paper makes no sciCORE claim.
10. **ReAct-style baseline.** A tool-using agent that chooses when to call the rule engine (reviewer SBTv). It is named as future work in §6.4.

## 7. Provenance

| Commit | Content |
|---|---|
| `dcc20c1` | Workspace on the latest CasePath agent |
| `46a503b` | Harness and analysis plan, frozen before held-out runs |
| `2e0e9c3` | Held-out terra results, diagnostics, draft sections |
| `e288bf3` | Luna results, mechanism analyses, paper draft |
| branch head | Final audit corrections and these deliverables |

`WORKLOG.md` records every step, decision and expense in order.
