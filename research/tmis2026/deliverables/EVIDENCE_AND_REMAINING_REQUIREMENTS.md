# Evidence and remaining requirements

Paper: *CasePath: Agents That Read, Rules That Decide* (ACM TMIS draft), folder `research/tmis2026/`, branch `claude/casepath-tmis-paper-20261109`.
Pointers refer to `CasePath_TMIS.pdf` (55 pages) and, with "Supp.", to `CasePath_TMIS_supplement.pdf` (27 pages), both built on 2026-11-11. Numbers are quoted from the built PDFs. File paths are relative to `research/tmis2026/`.

Status labels: **confirmed hypothesis** (pre-registered, tested in the fixed order, confirmed); **failed** or **not tested** (pre-registered); **secondary** (registered secondary or descriptive contrast, outside the fixed order); **descriptive** (reported without a test); **added after review** (not pre-registered, from `analysis/study3_review.py`); **post hoc** (`analysis/study3_posthoc.py`); **development** (Studies 1 and 2, the probe, or deterministic computations on development data); **formal** (proved).

## (a) What the paper claims

### The test and its hypotheses (Study 3, Section 6)

System under test: the product at commit `6a72159c`, cost-efficient model (gpt-6-luna) unless stated; comparators on the same files and rules; 3 runs per case. Data `fresh2/`: 72 theft changed-fact pairs and 48 unresolved-fact pairs (8 stories, 9 changed facts); 96 tenancy claims in 24 families. Registered output: `analysis/study3_results_fresh2_confirm.md` (and `.json`), produced once by `analysis/study3.py` from `analysis/study3_spec.json`.

| # | Claim | Evidence | Status | Where |
|---|---|---|---|---|
| H1 | On theft, fewer wrong + missed changes per pair than the same model's single prompt (Rules in context), with the reviewed rules. | 0.58 against 1.74, 9 clusters, p = 0.0078. The rules were reviewed by editors who knew the test conditions. | confirmed hypothesis | §6.4, Table 7 |
| H2 | On tenancy, fewer strict unsafe errors per claim than the same model's single prompt. | 0.31 against 2.14, 24 families, p = 0.0002. | confirmed hypothesis | §6.4, Table 7 |
| H3 | On tenancy, fewer strict unsafe errors than the frontier model's single prompt. | 0.31 against 1.86, p = 0.0008. Tested only because of the reorder below. | confirmed hypothesis | §6.3, §6.4, Table 7 |
| H4 | On theft, fewer errors than each of Self-consistency, Model executes rules and ReAct (all three required). | **Failed.** Against Self-consistency 0.58 against 1.21, p = 0.0625 (fewer on 7 changed facts, more on 2). Components that passed: Model executes rules 1.94 (p = 0.0039), ReAct 1.69 (p = 0.0117). The inverted sign-flip interval against Self-consistency includes zero (Table 21). | failed | §6.4, Table 7, Table 21 |
| H5 | On theft, non-inferior to the frontier single prompt (margin 0.25). | **Not tested**, because H4 failed. Values for information: 0.58 against 0.95. | not tested | §6.4, Table 7 |
| Reorder | The order of the hypotheses was changed at 21:51 on 10 November (commit `482873e3`), shortly before the freeze, on development evidence. In the final draft of 21:26 the tenancy contrast against the frontier model came fifth. Under that order the prior-work hypothesis would have been tested third and failed, the tenancy-frontier contrast would not have been tested, and only H1 and H2 would have been confirmed. H3's confirmation depends on this decision. | Commits `984d2991`, `482873e3`, `fd35e438`; `WORKLOG.md` (entry of 2026-11-11). | disclosed | §1, §6.3, App. B.2, §7 "Limits", §8 |

### Secondary and descriptive results of the test

| Claim | Evidence | Status | File | Where |
|---|---|---|---|---|
| The tenancy difference lies mostly in the 33 denied- and open-event claims, which the test set was designed to include. | 0.47 against 5.69 and 5.31 errors per claim there; on the 63 ordinary claims 0.20 against 0.44 (p = 0.0417, not predicted) and 0.28 (p = 0.409). | secondary (registered descriptive subset rows) | `analysis/study3_results_fresh2_confirm.md` | §1, §6.4, Table 14 |
| Against the single prompts with the original theft rules. | Same model: 0.58 against 1.47 (p = 0.0117). Frontier model: 0.58 against 0.67, the best single prompt on theft (non-inferiority share 0.0035, descriptive). | secondary | same | §1, §6.4, Table 17 |
| CasePath held almost every document the engine's reference holds, and more it does not hold. | Held 97% of reference-held documents against 48% and 35%; unneeded holds 0.33 per claim against 0.17 and 0.18 (1.17 on denied-event claims). Theft: 94% of unresolved-fact pairs otherwise unchanged against 27–47% for prior-work designs. All deviations 0.73 against 2.33 (p = 0.001) and 2.09 (p = 0.0023). | secondary | same | §6.4, Table 8 |
| Two-valued execution of CasePath's own readings turns holds into errors. | 1.27 (unresolved taken as false) and 1.51 (taken as true) strict unsafe errors per claim, against 0.31. | secondary | same | §6.4, Table 14 |
| The checklist-only setting showed no detectable difference. | 0.34 against 0.31 (p = 0.5); 0.55 against 0.58 (p = 0.594); at 22% and 16% of the full product's cost. The two settings share cached responses, so this is no independent repetition. | secondary | same | §6.4, Table 17 |
| Cost. | Full product USD 0.013 (tenancy claim) and 0.030 (theft text); frontier single prompt 0.006 and 0.004: 2.1 and 7.4 times. | descriptive | same | §6.4, Table 6 |
| CasePath on the frontier model, checklist only, one run: not better than the frontier single prompt on theft. | 0.83 against 0.95, p = 0.672. | descriptive (no hypothesis) | same | §7 "Where it does not pay", Table 17 |
| Repeated errors counted once. | Theft 0.49 against 0.93 (Rules in context) and 0.72 (Self-consistency). | descriptive | same | §6.4 |
| Worked example. | Claim `f2cl_0868f24595f5f79a`, chosen after the results by a stated rule. | descriptive | stored plans in `runs/study3/confirm/` | §6.4, Table 9 |
| Failed outputs. | 50 comparator outputs failed and were scored as empty checklists (40 from ReAct); none from the product. Leaving ReAct's out changes no p-value (H4 component against ReAct stays at p = 0.0117). | post hoc | `analysis/study3_posthoc.md` | App. B.1, Table 19 |

### Added after review (not pre-registered; none changes a status)

File: `analysis/study3_review.md` (and `.json`), macros `paper/results/numbers_study3_review.tex`.

| ID | Claim | Evidence | Where |
|---|---|---|---|
| R1 | CasePath's whole tenancy checklist was exactly right more often. | 75% of claim-runs against 42% and 53%. | §6.5, Table 10, Table 22 |
| R2 | With fewer gating claims the difference shrinks but stays below zero. | With 5% denied and 5% open: −0.68 (same model) and −0.55 (frontier), intervals below zero. No mix is tied to an insurer's real intake. | §6.5, Table 23 |
| R3 | Few wrong values were admitted; agreement did not catch a shared misreading. | Of 1344 tenancy fact values, 9 admitted values and 2 presumptions were wrong; in every wrong admission all readings gave the wrong value; 34 settled branch-fact values left unresolved. Theft not measured. | §6.5, Table 11 |
| R4 | Wrong presumptions raise every design's errors by about as much. | 0.31 rises to 0.36, 0.41 and 0.51 at 5, 10 and 20%; at 20% the difference is −1.82 and −1.55. | §6.5, Table 24 |
| R5 | Theft inference with other units. | Inverted sign-flip intervals; stories as clusters p = 0.0156 for H4; two-way resampling. | §6.4, Table 21 |
| R6 | Family-level tenancy differences. | Plot of the 24 families. | Fig. 7 |
| R7, R7b | Full product and checklist only differ no more than two runs of either. | Identical checklists in 93% (tenancy) and 59% (theft); two runs of the full product 81% and 17%, of checklist only 80% and 15%. Skipped steps take 65% and 82% of a full run's cost. | §6.5, Table 18 |
| R8 | The single prompts mostly saw the denial and still requested documents. | On 72 denied-event claim-runs, Rules in context asked in 40 and requested in 69; the frontier model 71 and 49. | §6.5 |
| R9 | The reviewed theft rules raised the single prompts' errors; the outputs do not show why. | 1.74 against 1.47 (same model), 0.95 against 0.67 (frontier). | §6.5 |
| R10 | Time per case. | Full product median 204 s (tenancy) and 287 s (theft); checklist only 33 and 87 s; single prompt 10–14 s. A handler's time was not measured. | §6.4, Table 25 |
| R11, R11b | Against strong Kleene evaluation of the same facts, exact deferral made no fewer strict unsafe errors but far fewer wrong holds. | 0.23 against 0.25 strict errors; held required documents 0.48 against 0.07; deviations 1.31 against 0.65 (277 claim-runs). | §6.5, §7 Principle 2, Table 26 |

### Formal results and deterministic computations

| Claim | Evidence | Status | File | Where |
|---|---|---|---|---|
| Soundness relative to admitted facts (Prop. 3.1), strong Kleene over-holds at reconvergence (Prop. 3.2), exact deferral holds exactly what completions disagree on (Prop. 3.3), reading errors (Prop. 3.4); each within the scope stated in Section 3 (flow workflows, two-valued independent facts, document presence taken as given). | Proofs; the tested workflows are flow workflows and the plain walk on theft equals exact deferral, checked with the product's own evaluator. | formal | `analysis/check_fragment.py` (step of `reproduce.sh`) | §3, App. A |
| What reading errors become. | Over the 150 Study 1 tenancy claims, misjudgement probability 0.1: unresolved values gave 84.5 expected holds and no unsafe error; wrong values gave 84.5 expected missed documents and 37.0 unnecessary requests. | development (deterministic, no model) | `analysis/` Study 1 evidence files | §3.5, App. A, Fig. 5 |
| Exact deferral never ran on theft (9–28 open facts per text; the plain walk ran). | Section 3.4; App. A. | stated scope | `analysis/check_fragment.py` | §3.4, App. A |

### How the design was found (Studies 1 and 2)

| Claim | Evidence | Status | Where |
|---|---|---|---|
| Neither earlier configuration was better than Rules in context. Study 1 (frontier model): 38 against 22 wrong theft changes (p = 0.211). Study 2: none of four primary contrasts confirmed. | `paper/results/numbers.tex`, `analysis/*.json` regenerated by `analysis/verify_paper.py` | development (pre-registered at the time, failed) | §5; Supp. S1, S2 |
| Likely causes and the changes they led to (faulty rules, silence read as doubt, a checking call that rejected correct values, strong Kleene over-holding). | Attributed post hoc; no row's evidence comes from a confirmatory test. | development | §5, Table 4 |
| Label-free rule repair failed; the theft rules were then reviewed by two AI editor sessions (9 changed, 14 queued for a jurist, no jurist review). | `rule_review/` | development | §5, App. E.4 |
| ShARC pilot. | Unplanned; no claim rests on it. | development | §5; Supp. S6 |

## (b) What the paper does not claim, and why

- **Not legal correctness.** Tenancy references come from the engine CasePath implements, under a silence clause the researchers wrote; they test how a design applies the rules (§6.1, §7 "Limits", App. C.2).
- **Not an advantage on theft over Self-consistency or over the frontier single prompt with the original rules.** H4 failed; 0.67 against 0.58 is close (§6.4, §7 "Where it does not pay").
- **Not a result for the frontier model run in full.** Only "checklist only", one run, without a hypothesis (§6.2, §7).
- **Not real or long files.** Texts have 77–320 words; long-file paths never ran (§6.1, §7 "Limits").
- **Not wrong presumptions in the test data.** Every unmentioned branch fact is false by design; only the stress test R4 varies this (§6.5, App. C.2).
- **Not that agreement catches misreadings.** All readings share one model and prompt (§6.5, §7 Principle 3).
- **Not new rules on theft.** Theft reuses Study 1's conditions with rules reviewed knowing them (§7 "Limits").
- **Not the value of the brief and reply draft to a handler, and not a handler's time.** Neither was measured (§6.4, §7 Principle 4).
- **Not that Knowledge (learning from corrections) works.** The test did not exercise it (§4.3).
- **Not any result of the expert study.** It has not run (§7, App. G).
- **Not regulatory standing.** The paper claims none for CasePath's records (§2).
- **Not that the tested commit is the released product.** Its merge has not been confirmed by the product's owners (§6.1, App. B.2).

## (c) What remains before submission

### Authors' facts in the source (`%% AUTHORS:` lines; 10 lines in 5 files)

- [ ] **Conflict of interest and roles** (authors). `paper/main.tex:83`. Each author's relation to the insurer and to the product's owners; who decided the merge of the tested commit.
- [ ] **Conference-version disclosure** (authors). `paper/main.tex:85`. Venue, year, title of the conference version and what is new; first-page footnote and cover letter. The previous version of this file names it as the ICLR 2027 submission 57404 and notes that ACM does not allow simultaneous submission; its current status (withdrawn or decided) is not recorded in the repository.
- [ ] **Merge status of `6a72159c`, Section 6.1** (authors, after the product owners decide). `paper/sections/s6_test.tex:18`. Confirmed, rejected or pending.
- [ ] **Merge status, Appendix B.2** (authors). `paper/sections/app_d_deviations.tex:29`. Same fact as above.
- [ ] **Which commit is published** (authors, after the scrub decision). `paper/sections/app_g_repro.tex:13`. The scrubbed commit with its parity hash, or the tested commit with the insurer's approval.
- [ ] **Location of the response-cache archive** (authors). `paper/sections/app_g_repro.tex:17`. DOI or URL, or delete the sentence offering it.
- [ ] **Licences of the data and outputs** (authors). `paper/sections/app_g_repro.tex:21`. For `fresh/`, `dev_probe/`, `fresh2/`, `rule_review/`, `runs/`, or a statement that the root licence covers them.
- [ ] **Record of the rule editors** (authors). `paper/sections/app_g_repro.tex:53`. Record in `rule_review/` which model and sessions were the two editors, or change the text to "two independent editors".
- [ ] **AI assistants used** (authors). `paper/sections/app_g_repro.tex:60`. Names and versions of the coding and writing assistants, as the venue requires.
- [ ] **Ethics statement for the expert study** (authors, with the study lead). `paper/sections/app_i_protocol.tex:33`. Approving body and reference, or why none is required.

### The tested product

- [ ] **Merge of the tested commit** (product owners). Commit `6a72159cdb35a01059d0549b1d437c0b3d5c20cb`, branch `claude/casepath-internal-paper-sync-20261110d`. Confirm that `python -m casepath parity` prints `source_tree_sha256` `030480203f7d10b364e4ecc34e0c0b544c4038e107f489bc2080aba6b349ab4d` at the merged commit. If they reject a change of behaviour, the test must be repeated on new sealed data (App. B.2). Then update the two merge-status lines above.

### Release (`release/SCRUB_REPORT.md`, section 2; `RELEASE.md`)

- [ ] **Git history** (product owners). 1,110 commits on 12 branches, including earlier states of pseudonymised data. Recommendation: publish a new repository whose first commit is a reviewed export.
- [ ] **Insurer's name in the tested product** (product owners). Decide: (a) publish `6a72159c` unchanged with the insurer's written approval, or (b) a scrubbed commit with its new parity hash reported beside the tested one.
- [ ] **Knowledge seed derived from the insurer's letters** (product owners). Remove it with its test, loader line and interface text, or keep it only with written approval.
- [ ] **Internal product documents** (product owners). Remove the five documents named in the scrub report and neutralise the README lines.
- [ ] **Deployment files for the insurer's platform** (product owners). Keep with approval or remove.
- [ ] **`design-plans/` and the paper branch's own `casepath-internal/`** (product owners). Leave out of the public export.
- [ ] **Local paths and names** (authors). Replace in the files that ship.
- [ ] **Licences** (authors). Add a licence file to `fresh/`, `fresh2/`, `dev_probe/`, `rule_review/`, `runs/`, `expert_study/`, `inputs/`, `paper/`.
- [ ] **Cache archive** (authors). Study 3's cache is about 23,000 files (730 MB, App. E.1); the whole `runs/product/cache/` holds 79,404 files (0.9 GB, `RELEASE.md` section 3). Publish it with a DOI, or remove the offer from App. E.1.
- [ ] **Public repository URL** (authors). The paper cites `github.com/KumarNavish/casepath`; the folder exists only on this branch, and `git clone <repository URL>` was not tested from a public address (`RELEASE.md` section 2). Replace the anonymous citation in the root `README.md`.
- [ ] **Delete `release/SCRUB_REPORT.md` from the export** (authors). The report says it is internal.

### Expert study (`expert_study/PREREGISTRATION_DRAFT.md`, section 13; App. G, Table 27)

- [ ] **Formative step** (study lead): day 7, 17 November 2026; product changes from it on 17–19 November, each listed.
- [ ] **Freeze as version 1.0** (study lead): day 10, 20 November 2026, with the contents listed in section 13.3.
- [ ] **Status-source hash** (study lead): by day 13, 23 November 2026. No session before it exists.
- [ ] **First session** (study lead): day 14, 24 November 2026, or soon after.
- [ ] **Ethics statement** (authors, study lead): see the `%% AUTHORS:` line above.
- [ ] **When results exist** (authors): Section 7 (`paper/sections/s7_experts.tex`, now not input) returns to the article with the results of Q1–Q5 (agreement with the insurer's requests and a single prompt; what five experts do with the same items; how they work; learning from corrections on a held-out case; reasons for changes), the deviations from the frozen protocol, and the limits App. G names. The article now reports no result of the study.

### Text and layout

- [ ] **Swiss supervisory guidance** (authors). The internal referee asked for it; it is not cited because title, number and date could not be confirmed from an official page (`analysis/REFERENCES_ADDED.md`). Verify and add it, or leave it out.
- [ ] **Abstract** (authors). Kept unchanged by decision. Still open from round 2: gloss "per pair", the qualifier "by editors who knew the test conditions", and the mechanism sentence (presumptions; plain walk on theft). See `REVIEW_RESPONSE_CHECKLIST.md`.
- [ ] **Template options** (authors). Remove `nonacm` from `\documentclass` in `main.tex` and `supplement.tex`; add `anonymous,review` only if the venue requires it; confirm the CCS concepts.
- [ ] **Length** (authors). The article is 55 pages (body pp. 1–22), the supplement 27. TMIS length limits were not checked against an official page.
- [ ] **Open review items not done**: a glossary table (J09), a recap at the start of §7 (J15), an explicit research-question sentence (J01), a reason for the published designs not run (2Kwe Q3), a complexity sentence (SBTv W3), routing accuracy for Study 3 (CptP Q2). See the checklist.
- [ ] **Build state** (none open). Both documents build from clean with zero undefined references or citations, zero overfull boxes and zero `??`. The logs show 14 harmless "`h` float specifier changed to `ht`" warnings in the article; BibTeX warns of a missing address, publisher or page range in 16 entries of the article and in 1 further entry of the supplement.

## (d) How to reproduce

**One command, no model calls** (`RELEASE.md` section 3; App. E.2):

```sh
git clone <repository URL> casepath && cd casepath
git fetch origin claude/casepath-internal-paper-sync-20261110d
python3 -m venv .venv-repro && .venv-repro/bin/pip install -r research/tmis2026/requirements-reproduce.txt
PYTHON=.venv-repro/bin/python research/tmis2026/reproduce.sh
```

What it checks: the data manifests and the probe rebuild; that the product commit prints the recorded parity hash; the claims of App. A with the product's own evaluator; Study 3's registered analysis, the post-hoc analysis and the number macros, byte for byte; the analyses added after review; the analysis tests (43 + 36 + Study 2); Studies 1 and 2 from their stored checklists and Study 1's response cache; and a clean build of both documents. It blocks model calls and writes nothing into the checkout. It does not re-check the model runs themselves, a few inputs of the Study 1–2 re-analysis, or the Study 1–2 figures.

How long: 11 min 20 s in a fresh clone (59 steps passed, 2 skipped); 11 min 27 s with the cache (61 passed). `pypdf==5.9.0` is required; another version breaks the Study 1 cache lookup.

What needs the cache archive: only two parts of the review analysis, the individual readings behind R3 and the cost split of R7. Without the archive these two lines are SKIP; every other step needs only the repository.

**Re-running Study 3 with model calls** (`harness/study3/run_all.py`; App. E.2; `RELEASE.md` section 4):

- Cost of the stored run: USD 34.33 in the ledgers (22.41 cost-efficient model, 11.92 frontier model); the planned caps were USD 32 plus USD 8 for the frontier product design (App. B.1). Without the cache every call is paid again.
- Time of the stored run: five invocations between 22:30 on 10 November and 04:17 on 11 November 2026 UTC, about 5 h 40 min of running time with up to 20 parallel workers.
- What a reader must do: use their own model endpoint and key; adapt the two model clients (`harness/llm.py`, `harness/product/run_product.py`) to read a key and CA bundle from the environment; pass the product worktree path; use a new `--label`. Answers can differ: the models are not deterministic and no snapshot is recorded. If the two model endpoints are retired, only the re-check from stored outputs remains.
- For orientation (summed by folder from the ledgers' `cost` fields; each folder mixes development, pilots, diagnostics and study runs, and Study 3's spend is split between `runs/v2/` and `runs/product/`; these totals are not stated in the paper): `runs/ledger.jsonl` USD 9.88 (Study 1); `runs/v2/` USD 20.86; `runs/product/` USD 62.02.

Note: `RELEASE.md` section 4 gives the stored run's spend as USD 31.79 (run log plus hand-written notes), while the paper gives USD 34.33 from the ledgers and says the run log does not record all spend (App. E.2). The ledgers are the source.
