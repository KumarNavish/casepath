# Evidence and remaining requirements

Paper: *CasePath: Agents That Read, Rules That Decide* (ACM TMIS draft), folder `research/tmis2026/` on the paper branch.
Pointers refer to `CasePath_TMIS.pdf` (27 pages) and, with "Supp.", to `CasePath_TMIS_supplement.pdf` (68 pages), built at commit `17497000` on 12 November 2026. Numbers are quoted from the text of these PDFs or from the files cited. File paths are relative to `research/tmis2026/`.

## State of things

- **Registered result.** In a pre-registered test of a frozen commit on sealed synthetic data, three of five hypotheses were confirmed, one failed and one was not tested. On tenancy CasePath made 0.31 strict unsafe errors per claim against 2.14 and 1.86 for single prompts with the same rules; on theft, 0.58 errors per pair against 1.74.
- **What a fair baseline changed.** After the test, a single prompt told the same stop and hold rules matched CasePath on tenancy overall (0.35 on the same model; 0.19 on the frontier model). It did better where a claim denies its defining event. The paper now says: "The registered tenancy result therefore measures mostly what the prompt was told."
- **Where a lead remains.** Where a fact is tentatively worded, where a supplied document is insufficient, and on theft (0.58 against 1.68). These are added after the test and not registered.
- **What is not in the paper.** No result from real files, from experts or from a jurist. The deployment study and the dossiers were taken out of the paper by the owner's direction and are separate follow-up work (`expert_study/`). A replication study is planned (`STUDY4_COSTED_PLAN.md`); steps 0 to 2 are approved and largely done; steps 3 to 5 are not approved.
- **What only others can supply.** Nine `%% AUTHORS:` facts in the files the two documents input, three legal questions on the theft rules and one on the tenancy rules, a DOI for the tested commit, the release decisions of `release/SCRUB_REPORT.md`, and two new owner's decisions (naming an insurer's published conditions as a rule source; three insurer PDFs in the branch's history).

Labels: **registered** (pre-registered hypothesis, fixed order); **registered secondary** (in the plan, descriptive); **added after the test** (not registered; marked † in the paper; p values descriptive and not corrected for multiplicity); **formal** (proved); **development** (Studies 1 and 2, or exact computations).

## (a) What the evidence supports

### Registered results (Study 3)

System: the core of CasePath at commit `6a72159c` (source-tree hash `03048020…`); the registered tests ran the full product, with three readings, on the cost-efficient model unless stated. Data `fresh2/`, sealed before any design ran: theft, 8 stories, 72 changed-fact pairs and 48 unresolved-fact pairs (9 changed conditions); tenancy, 96 claims in 24 families (24 denied-event, 9 open-event, 63 ordinary). Registered output: `analysis/study3_results_fresh2_confirm.md`.

| # | What was tested | Numbers | Status | Where |
|---|---|---|---|---|
| H1 | Theft, against Rules in context (single prompt), same model | 0.58 against 1.74 errors per pair; −1.15; p = 0.0078 | confirmed | §6.2, Table 5 (p. 12) |
| H2 | Tenancy, against Rules in context, same model | 0.31 against 2.14 strict unsafe errors per claim; −1.83; p = 0.0002 | confirmed | §6.2, Table 5 |
| H3 | Tenancy, against Rules in context on the frontier model | 0.31 against 1.86; −1.55; p = 0.0008. Tested only after a reorder 38 minutes before the freeze | confirmed | §6.2, Table 5 |
| H4 | Theft, against each of Self-consistency, Model executes rules and ReAct | Self-consistency 0.58 against 1.21, p = 0.0625 (smallest attainable 0.0039); fewer errors on 7 of 9 conditions, more on 2. Model executes rules 1.94 (p = 0.0039), ReAct 1.69 (p = 0.0117) | failed | §6.2, Table 5 |
| H5 | Theft, non-inferiority to the frontier prompt | Not tested, because H4 failed. Values 0.58 against 0.95 | not tested | §6.2, Table 5 |

Registered secondary results:

| What the paper says | Numbers | Where |
|---|---|---|
| CasePath held most documents the reference holds | 97% against 48% and 35% | §6.4, Table 6 (p. 13) |
| Theft, unresolved-fact pairs | No premature request; 94% otherwise unchanged, against 27–47% for every single-prompt and prior-work design given the reviewed rules (91% for the frontier prompt with the original rules). Two-valued "unresolved = false" also scores 94%; this measure "cannot tell a hold from reading the open fact as false" (§7.1) | §6.4, Table 6 |
| Theft, against the original (unreviewed) rules | Same model 0.58 against 1.47 (p = 0.0117). Frontier 0.58 against 0.67: bootstrap share 0.0035, "not a calibrated p"; exact superiority p = 0.6367 (added after the test) | §6.2 |
| Tenancy subsets | 33 denied- and open-event claims: 0.47 against 5.69 and 5.31. 63 ordinary claims: 0.20 against 0.44 (p = 0.0417; the plan predicted no difference) and 0.28 (p = 0.409) | §6.2 (p. 12) |
| Frontier model, CasePath checklist only, one run | Tenancy 0.30 against 1.86 (p = 0.0012). Theft 0.83 against 0.95 (p = 0.672) and 0.67 with the original rules; more theft errors than the product on the cost-efficient model, 0.83 against 0.58 (p = 0.0781) | §6.3, Table 6, Fig. 3 (p. 14) |
| The full product and the core alone did not differ detectably | 0.34 against 0.31 (p = 0.5); 0.55 against 0.58 (p = 0.594); at 22% and 16% of the full product's cost. They shared cached responses | §6.3 (p. 13), §7.1 |
| All deviations (holds counted) | 0.73 per claim against 2.33 (p = 0.001) and 2.09 (p = 0.0023); unneeded holds 0.33 against 0.17 and 0.18 | §6.4, Table 6 |
| Two-valued execution of CasePath's own readings | 1.27 (unresolved as false) and 1.51 (as true) strict unsafe errors per claim, against 0.31 | §6.4, §7 Principle 2 |
| Cost and time | USD 0.013 per tenancy claim and 0.030 per theft text: 19.8 and 41.8 times the same-model prompt, 2.1 and 7.4 times the frontier prompt; checklist only 4.4 and 6.8 times. Median case-run 204 and 287 s (full product), 33 and 87 s (checklist only), 14 and 10 s (frontier prompt); "times are lower bounds" and handler time was not measured (§7.1) | §6.5 (p. 15), Table 4 (p. 11) |

### The fair-baseline check (added after the test; `study4/baseline_check/REPORT.md`)

A single prompt "with hold option": Rules in context's prompt with its task replaced by a three-way decision per document (request now; hold with a question; do not request) and the stop and silence rules the product's workflow encodes. On the frontier model also Model executes rules, which already had a hold rule. Run on Study 3's data, which are development data from now on. Prompts hashed before any call; 1,120 outputs, none failed; spend USD 4.45.

| Finding | Numbers (strict unsafe / all deviations per claim; theft errors per pair) | Where |
|---|---|---|
| The tenancy gap closes | Prompt with hold option 0.35 against CasePath 0.31 on the same model (−0.03, p = 0.7379 over claims). Frontier: 0.19 and 0.19 against 0.30 for CasePath, checklist only (+0.11, p = 0.3857) | §6.6, Table 8 (p. 17) |
| On denied defining events CasePath is worse | CasePath 0.61 / 1.78; the prompt 0.21 / 1.10 on the same model and 0.00 / 0.00 on the frontier model (p = 0.1250 and 0.1250 over families). "Its readings disagreed on the denial, and it held." | §6.6 |
| A lead remains on open branch facts | All deviations 0.52 against 1.25, 1.26 and 1.30 (p = 0.0127, 0.0156 and 0.0068 over families). The prompts held documents required now when the wording was tentative (0.65 to 0.70 per claim, against 0.19) and accepted an insufficient original as on file (0.30 to 0.36 missed documents per claim, against 0.16) | §6.6, §7 Principle 1 |
| A lead remains on files that state every fact, frontier model | CasePath, checklist only 0.05 deviations per claim against 0.68 for the frontier prompt with hold option (p = 0.0176 over families) | §6.6 |
| On theft the hold option does not help the prompt | 1.68 against 0.58 on the same model (p = 0.0078 over the nine clusters). Frontier: 1.18 and 1.24 against 0.83 (p = 0.0422 and 0.0196 over pairs; 0.1016 and 0.1484 over clusters). The best frontier single prompt on theft remains Rules in context with the original rules (0.67) | §6.6, Table 8 |
| What the paper concludes | "The registered tenancy result therefore measures mostly what the prompt was told. What the design adds is fewer wrong holds, checks of supplied documents, and requests that stay stable when one sentence changes." Principle 1: stating the stop and hold rules "closed the defining-event gap, in a prompt as well as in code" | Abstract, §7 (p. 18–19) |

### Other analyses added after the test

| What the paper says | Numbers | Where |
|---|---|---|
| Order and Holm (not registered) | Under the order of 21:26 H3 would not have been tested. Under Holm, H1, H2, H3 and H5 would pass and H4 would not. "The registered outcome stands" | §6.2, Table 5 |
| H4 under other units | Inverted interval −1.25 to 0.08; stories as clusters p = 0.0156; H5 superiority p = 0.0547 | §6.2 |
| Where the registered tenancy effect sits | The 9 families with denied- or open-event claims (CasePath lower in every one, by at least 2.33). Other 15 families: lower in 10, equal in 2, higher in 3, by at most 0.75. 56 claims with an open fact or a denied or open defining event: 0.40 against 3.39 and 3.06. 40 claims stating every fact: 0.19 against 0.39 (p = 0.2761) and 0.19 (p = 0.8984). 23 claims with only an open branch fact: 0.23 against 0.51 (registered subset rows) | §6.2, §6.4 (p. 14–15); Supp. Table S39, Fig. S7, Fig. S8 |
| Theft, open condition's own documents | Held in 83% (CasePath), 85% (Rules in context), 85% (frontier prompt), 90% (Self-consistency) of pairs | §6.4 |
| Same budget | Self-consistency near 2.10 on tenancy for 1 to 15 samples; on theft 1.84 → about 1.00. At matched cost: −1.76 per claim (p = 0.0006), −0.53 per pair (p = 0.1328). From 1 to 3 readings, unneeded holds 0.003 → 0.302 per claim, all deviations 0.55 → 0.74 | §6.5, Fig. 4 (p. 15–16) |
| Error decomposition | Tenancy, cost-efficient 0.313 = routing 0.045 + document judgment 0.076 + reading 0.167 + hold 0.024. Theft, cost-efficient 0.583 = rule 0.333 + reading 0.088 + hold 0.157 + 0.005; frontier 0.833 = 0.333 + 0.250 + 0.250. Rule part 0.22 to 0.44 under alternative mappings | §6.3, Table 7 (p. 15) |
| Readings of the rule text | Denied-event claims carry about two thirds of the registered tenancy lead (69% and 62%); amending the workflow to the other reading removes 64% and 36%. Clean room: two AI evaluators agree with the reference on 1,024 of 1,024 decisions, which "confirms the implementation of the catalogue". Workflow unchanged, reading A1: +0.55 (p = 0.1348) and +0.21 (p = 0.5134); all four readings: 6 of 10 contrasts reverse. Amended under A1: −0.66 (p = 0.0002), −1.00 (p = 0.0014), resting on the 9 open-event claims | §6.7, Table 9 (p. 17–18) |
| Theft on the frontier model | Extra errors are in readings and holds; the stored readings trace them to two broadly worded conditions. Third party admitted true in 8 of its 8 ordinary runs (cost-efficient model 0 of its 50) | §6.8 (p. 18) |
| Lint (proposed diagnostic) | 14 and 12 flags on the theft texts; 8 and 9 of 10 tenancy conditions flagged; mutation test 6 of 6 widened conditions flagged, 3 already flagged, 3 of 5 untouched flagged. Flagged-as-open: 0.833 → 0.528 in sample, 0.778 out of sample; no paired difference significant | §6.8; Supp. Table S44 |
| Principles 2 and 3 | Exact deferral 0.25 against 0.23 strict errors for strong Kleene, 0.65 against 1.31 deviations (277 of 286 claim-runs). 9 of 1,344 fact values admitted wrong, all with agreeing readings; reading errors on denied-event claims are about half (49%) of CasePath's strict unsafe tenancy errors. One reading instead of three: 0.34 → 0.52 and 0.55 → 1.22 | §3.5 (p. 8), §7 |

### Formal results and design history

| What the paper says | Status | Where |
|---|---|---|
| Propositions 3.1–3.4 (soundness relative to admitted facts; strong Kleene over-holds at reconvergence; exact deferral against strong Kleene; reading errors), each within its stated scope; the tested workflows are flow workflows and the plain walk on theft equals exact deferral, checked with the product's code | formal | §3, App. A (p. 23) |
| Each fact misjudged with probability 0.1 over Study 1's 150 tenancy claims: unresolved values become holds and no unsafe error; wrong values become missed and unnecessary requests | development (exact) | §3.5, Fig. 5 (p. 25) |
| Neither earlier configuration beat Rules in context: Study 1, 38 against 22 wrong theft changes (p = 0.211); Study 2, none of four primary contrasts confirmed | development | §5 (p. 9); Supp. S1, S2 |

## (b) What the evidence does not support

- **A tenancy advantage over a prompt told the stop and hold rules.** Overall it is level; on denied events the prompt is better (§6.6).
- **That the registered tenancy lead comes from executing rules in code.** The paper says it "measures mostly what the prompt was told" (abstract).
- **Holding on theft.** The theft measure cannot tell a hold from reading the open fact as false; exact deferral never ran on theft (§3.4, §7.1).
- **An advantage over self-consistency on theft** (H4 failed) **or on the frontier model on theft** (no advantage, one run).
- **Independence from the reading of the rule text.** References follow the engine and a silence clause the authors wrote; 69% and 62% of the registered tenancy lead rest on reading a denied defining event as ending the process, on which no lawyer has ruled (§7.1).
- **Registered status for the fair-baseline check.** It is post hoc, on the data the product was tested on; its frontier designs ran once (§7.1).
- **A validated lint.** Tested only against blunt widening; false-alarm rate unknown; remedy failed out of sample.
- **New theft rules, legal correctness, real or long files, handler time, or the value of the agents outside the core.** None was tested (§7.1).
- **Any result on real files or with experts.** That study is not part of this paper.
- **That the tested commit is the product.** Its merge has not been confirmed (App. B).

## (c) Remaining requirements

| Item | Who must act | What exactly is needed | What it unblocks |
|---|---|---|---|
| `%% AUTHORS:` facts (9; listed below) | authors | Write each fact into the source, or delete the sentence that waits for it | Submission; first-page footnote; App. C |
| Legal questions on the theft rules (3 decisive of 8; listed below) | jurist | Rulings on the scope of the traces condition, on when the insurer's instruction is due, and on whether an unidentified thief is a third party | The frontier theft cell; the Study 3 theft rule base |
| Denied defining event (tenancy) | jurist | A ruling on whether a denied defining event ends the process | Whether the 69% and 62% of the registered tenancy lead stand; which row of Table 9 is the result |
| DOI archive of the tested commit | authors | Deposit commit `6a72159c` (source-tree hash `030480203f…`) and cite the DOI in §4 | The artefact statement of §4 |
| Merge state of the tested commit | product's owners, authors | Decide on the offered branch; report the state in App. B and Supp. S11 | The two merge-status `%% AUTHORS:` lines |
| Release blockers (10; listed below) | product's owners, insurer, authors | The decisions of `release/SCRUB_REPORT.md` §2 and §7 | "will be released" (§1); App. C |
| Response-cache archive | authors | Publish the Study 3 response cache (about 23,000 files; 730 MB per Supp. S17) with a DOI or URL, or delete the offer in App. C | Byte-for-byte re-check of the cache-dependent analyses from a clone |
| Replication, step 2d | planner | Lint with planted defects in the three public rule sets (`study4/SPEC.md`); not done | A measured detection and false-alarm rate for the lint |
| Replication, step 3 (not approved) | owner | Approve about USD 45 for a second design cycle on generated development files (re-read only unsettled facts; tie-break reading instead of a hold; lint at rule-writing time; baselines given every improvement) | An improved artefact and a cost curve, as development evidence |
| Replication, step 4 (not approved) | owner, planner | Freeze artefact, plan, hypothesis order and generator seed, with an outside timestamp, at least three days before step 5 (no credits) | A registered replication |
| Replication, step 5 (not approved) | owner | Approve about USD 55 (68 with three runs on the cost-efficient model) for one sealed run: 240 files per regime, three regimes, both models, five designs per model | A registered test of every cell; "every cell" is claimed only if every cell passes |
| An insurer's published conditions named as a rule source | owner | Decide whether the theft rule set of `study4/rules/theft/` may name the insurer whose published household conditions and claim form it quotes, or must use a neutral label (`release/SCRUB_REPORT.md` item 9 asks the same for the earlier sources) | Publishing the public benchmark |
| Three insurer PDFs in the branch's history | owner | Three publicly downloadable insurer PDFs (two of one insurer's household documents and one industry model condition set) were added in commit `b70195ee` and untracked in `7004eda1`; they stay in history. Decide whether to rewrite history (force-push; `WORKLOG.md` records an earlier decision of no history rewrite) | A clean public export; see also blocker 1 below |
| Real files and experts | planner, product's builders, insurer | Separate follow-up work: protocol, requirements and questions in `expert_study/` (`PREREGISTRATION_DRAFT.md`, `REQUEST_TO_PRODUCT_20261112.md`) | Any claim about real files or handlers, in a separate paper |

### The `%% AUTHORS:` facts

Found by `grep -rn "%% AUTHORS" paper/` at commit `17497000`: 20 lines. 16 are in files the two documents input; 4 are in `sections/app_b_protocol.tex` and `sections/app_i_protocol.tex`, which neither document inputs any more (the deployment study left the paper) and can be deleted.

| Fact | Lines in input files |
|---|---|
| 1. Conflict of interest and roles: each author's relation to the insurer and to the product's owners, and who decided the merge of the tested commit | `main.tex:86` |
| 2. Disclosure of the conference version (venue, year, title) and what is new | `main.tex:88` |
| 3. DOI of the archived tested commit | `sections/s4_casepath.tex:5` |
| 4. State of the product: merge of `6a72159c`, the offered branch and the owners' check | `sections/app_c_deviations.tex:53` (article); `sections/app_d_deviations.tex:29, 86` (supplement) |
| 5. Which release: a scrubbed commit with its own parity hash, or the tested commit with the insurer's approval | `sections/app_d_repro.tex:9`; `sections/app_g_repro.tex:13` |
| 6. Location of the response-cache archive, or delete the offer | `sections/app_d_repro.tex:8`; `sections/app_g_repro.tex:17` |
| 7. Licences of `fresh/`, `dev_probe/`, `fresh2/`, `rule_review/` and `runs/` | `sections/app_d_repro.tex:10`; `sections/app_g_repro.tex:21` |
| 8. Record of the rule editors' model and sessions in `rule_review/` | `sections/app_d_repro.tex:17`; `sections/app_g_repro.tex:53` |
| 9. Names and versions of the AI coding and writing assistants | `sections/app_d_repro.tex:18`; `sections/app_g_repro.tex:60` |

No longer in the paper's input files: the dossiers' provenance, the insurer's development counts, the insurer's share of files with an open fact, and the ethics statement for the expert study.

### Legal questions

From `rule_review/lint/final/RECONCILIATION.md` (8 points for a jurist); Supp. S12.4 names three as deciding the Study 3 theft floor:

| Rule | Question |
|---|---|
| 003 (traces) | Is the condition limited to changes that could hinder establishing the cause or amount of the loss? Do mitigation changes need the consent documents? Does the "help services" arm apply beyond the one insurer whose terms contain it? |
| 004 / 004.a (insurer's instruction) | Is the duty to obtain the insurer's instruction triggered in every claim, or only where measures were to be taken? |
| 042 (third party) | Is an unidentified thief "ein Dritter" whose fault caused the loss? The two editors disagreed; the rule is unchanged |

Tenancy: whether a denied defining event ends the process. §7.1: "69% and 62% of the tenancy lead rest on reading a denied defining event as ending the process, on which no lawyer has ruled."

The three new rule sets in `study4/rules/` were written from public text with a second reader's check (AI sessions); no jurist has reviewed them either.

### Release blockers (`release/SCRUB_REPORT.md` §2)

| # | Blocker | Who decides |
|---|---|---|
| 1 | Git history: earlier states of data and documents (and now the three insurer PDFs above) | product's owners, owner |
| 2 | The tested product names the insurer in its code; publish unchanged with written approval, or a scrubbed commit with its own hash | product's owners, insurer |
| 3 | A Knowledge seed derived from the insurer's request letters | product's owners, insurer |
| 4 | Five internal product documents and README lines | product's owners |
| 5 | Deployment files for the insurer's platform | product's owners |
| 6 | `design-plans/` | authors |
| 7 | The paper branch's own older `casepath-internal/` | authors |
| 8 | Local paths and names in top-level and research documents | authors |
| 9 | Public policy terms used as research sources, by name | authors, product's owners |
| 10 | No licence for several data and output folders | authors |

## (d) How to reproduce

One command, no model calls (`RELEASE.md` §3; App. C): clone, fetch the product branch named in `RELEASE.md` §3, install `requirements-reproduce.txt` (it pins `pypdf==5.9.0`), and run `research/tmis2026/reproduce.sh`. Recorded runs (`RELEASE.md` §8): fresh clone without the cache, 59 steps passed and 2 skipped (11 November); working repository with the cache, 83 passed (12 November, before the fair-baseline check). Whether `reproduce.sh` covers the fair-baseline check is not recorded there.

`analysis/verify_paper.py --paper-only` passed at commit `17497000`: every macro file reproduces byte for byte, and both documents build from clean with no undefined reference, no multiply defined label and no overfull box over 5 pt.

## The LaTeX package

`CasePath_TMIS_overleaf.zip`: 55 files. `main.tex`, `supplement.tex`, `macros.tex`, `references.bib`, 8 macro files (including `results/numbers_baseline_check.tex`), the 28 section files the two documents input (followed recursively; no unused section ships), 13 figures, `README.txt`, and a `latexmkrc`. The `latexmkrc` builds both documents under their own names first, because Overleaf compiles under the job name "output" and the documents read each other's `.aux` files by name. Tested from the unpacked zip: the paper's build order gives 27 and 68 pages with no error, no undefined reference and text identical to the delivered PDFs; a local latexmk run with Overleaf's job name and options gives the same page counts with no undefined reference. Not tested on Overleaf itself.
