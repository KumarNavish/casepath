# Evidence and remaining requirements

Paper: *CasePath: Agents That Read, Rules That Decide* (ACM TMIS draft), folder `research/tmis2026/` on the paper branch.
Pointers refer to `CasePath_TMIS.pdf` (31 pages) and, with "Supp.", to `CasePath_TMIS_supplement.pdf` (69 pages), built from the paper sources at 10:28 UTC on 12 November 2026 (commit `2851d5f6`). Numbers are quoted from the text of these PDFs. File paths are relative to `research/tmis2026/`.

## State of things

- **What is shown.** In a pre-registered test of a frozen commit on sealed synthetic data, three of five hypotheses were confirmed, one failed and one was not tested. The strongest result is on tenancy: 0.31 strict unsafe errors per claim against 2.14 and 1.86 for single prompts with the same rules, and 97% of reference-held documents held against 48% and 35%.
- **Where it stops.** The tenancy lead lies in claims with an open fact or a denied or open defining event. Claims that deny the defining event carry about two thirds of it (69% and 62%), and their right answer rests on one reading of the rule text that no lawyer has checked. On theft the lead over self-consistency missed significance. On the frontier model there was no theft advantage. The full product costs 20 to 42 times the same-model prompt.
- **What is missing.** No result from real files or from claims experts. No jurist has reviewed any rule or reference. The deployment study's protocol is at version 1.0-rc and is to be frozen on 20 November 2026.
- **What only others can supply.** 24 `%% AUTHORS:` lines in the sources (14 distinct facts), three legal questions on the theft rules and one on the tenancy rules, the product's builders' inputs to the deployment study, a DOI for the tested commit, and the release decisions of `release/SCRUB_REPORT.md`.
- **Review state.** A check of the rewrite against the third referee report (`analysis/review/REFEREE_ROUND3_CHECK.md`) recommends minor revision; the ten wording problems it found are fixed in the delivered PDF (see `REVIEW_RESPONSE_CHECKLIST.md`).

Status labels: **registered** (a pre-registered hypothesis, tested in the fixed order); **registered secondary** (in the plan, outside the fixed order, descriptive); **added after review** (not pre-registered; marked † in the paper; its p values are descriptive and not corrected for multiplicity); **formal** (proved); **development** (Studies 1 and 2, or deterministic computations).

## (a) What the evidence supports

### The test (Study 3, Section 6)

System under test: the product at commit `6a72159c` (source-tree hash `03048020…`), with three readings, on the cost-efficient model unless stated. Data `fresh2/`, sealed before any design ran: theft, 8 stories, 72 changed-fact pairs and 48 unresolved-fact pairs (9 changed conditions); tenancy, 96 claims in 24 families (24 denied-event, 9 open-event, 63 ordinary claims). Every design except the frontier product ran 3 times per case. Registered output: `analysis/study3_results_fresh2_confirm.md`.

| # | What the paper says | Numbers | Status | Where |
|---|---|---|---|---|
| H1 | Theft, against Rules in context (single prompt) on the same model | 0.58 against 1.74 errors per pair; difference −1.15; p = 0.0078 | registered, confirmed | §6.2, Table 5 (p. 14) |
| H2 | Tenancy, against Rules in context on the same model | 0.31 against 2.14 strict unsafe errors per claim; −1.83; p = 0.0002 | registered, confirmed | §6.2, Table 5 |
| H3 | Tenancy, against Rules in context on the frontier model | 0.31 against 1.86; −1.55; p = 0.0008. Tested only because the hypotheses were reordered 38 minutes before the freeze | registered, confirmed | §6.2, Table 5 |
| H4 | Theft, against each of Self-consistency, Model executes rules and ReAct (all three required) | Self-consistency 0.58 against 1.21, p = 0.0625 (smallest attainable 0.0039); fewer errors on 7 of 9 changed conditions, more on 2 (by 0.13 and 1.00). Model executes rules 1.94 (p = 0.0039), ReAct 1.69 (p = 0.0117) | registered, failed | §6.2, Table 5 |
| H5 | Theft, non-inferiority to Rules in context on the frontier model (margin 0.25) | Not tested, because H4 failed. Values: 0.58 against 0.95 | registered, not tested | §6.2, Table 5 |
| Holding, tenancy | "The design holds what the file leaves open on tenancy." | 97% of reference-held documents held, against 48% and 35% | registered | §1, §6.4, Table 7 (p. 15–16) |
| Holding, theft | No premature request on unresolved-fact pairs, and nothing else changed in most of them. "This measure cannot tell a hold from reading the open condition as false." | CasePath 94% unchanged, 0% premature; 27–47% for every single-prompt and prior-work design given the reviewed rules; 91% for the frontier prompt with the original rules; two-valued "unresolved = false" also 94%. Exact deferral never ran on theft | registered | §6.4, Table 7 |

### Registered secondary results

| What the paper says | Numbers | Where |
|---|---|---|
| Theft, against the same-model prompt with the original (unreviewed) rules | 0.58 against 1.47, p = 0.0117 | §6.2 |
| Theft, against the frontier prompt with the original rules | 0.58 against 0.67; bootstrap share 0.0035, "not a calibrated p"; exact superiority p = 0.6367 (added after review) | §6.2 |
| On the cost-efficient model, a lower mean error than every single-prompt and prior-work design in both data sets | Every such difference had p < 0.05 except the theft difference from Self-consistency (not corrected for multiplicity) | §6.3, Supp. Table S20 |
| Most of the tenancy difference lies in the 33 denied- and open-event claims, as the plan predicted | 0.47 against 5.69 and 5.31 (family means). Ordinary claims: 0.20 against 0.44 (p = 0.0417; the plan predicted no difference) and 0.28 (p = 0.409) | §6.2 (p. 13); Supp. Table S17 |
| Frontier model, CasePath checklist only, one run, no hypothesis: fewer tenancy errors, no theft advantage | Tenancy 0.30 against 1.86 (p = 0.0012). Theft 0.83 against 0.95 (p = 0.672) and 0.67 with the original rules. More theft errors than the product on the cost-efficient model: 0.83 against 0.58 (+0.25, p = 0.0781) | §6.3, Fig. 4 (p. 15) |
| The agents outside the core made no detectable difference in errors | Checklist only 0.34 against 0.31 (p = 0.5) and 0.55 against 0.58 (p = 0.594), at 22% and 16% of the full product's cost. The settings shared cached responses: identical checklists in 93% and 59% of case-runs, against 81% and 17% for two runs of the full product | §4.1, §6.3 |
| Unneeded holds and all deviations | Unneeded holds 0.33 per claim against 0.17 and 0.18. All deviations 0.73 against 2.33 (p = 0.001) and 2.09 (p = 0.0023) | §6.4 |
| Two-valued execution of CasePath's own readings | 1.27 (unresolved taken as false) and 1.51 (taken as true) strict unsafe errors per claim, against 0.31 | §6.4 |
| Principle 1: execute the rules that stop or hold the checklist in code | Denied- and open-event claims: Rules in context 5.68 and 4.63, Model executes rules 1.94 and 1.04, CasePath 0.61 and 0.26 (per-claim means, descriptive) | §7 (p. 20–21) |
| Cost and time (registered costs) | Full product USD 0.013 per tenancy claim and 0.030 per theft text: 19.8 and 41.8 times the same-model prompt, 2.1 and 7.4 times the frontier prompt. Checklist only: 4.4 and 6.8 times the same-model prompt. The frontier checklist-only run cost more per tenancy claim (USD 0.0214) than the full product on the cost-efficient model (0.0134). Median time per case-run at least 204 and 287 s (full product), 33 and 87 s (checklist only), 14 and 10 s (frontier prompt); lower bounds, because cached calls took no time. A handler's time was not measured | §6.5 (p. 17–18), Table 4 (p. 13) |

### Added after review (not registered; none changes a hypothesis's status)

Sources: `analysis/study3_review.md`, `analysis/study3_feedback.md`, `analysis/decomposition.md`, `analysis/lint_followup.md`, `cleanroom/README.md`.

| What the paper says | Numbers | Where |
|---|---|---|
| Order and Holm. Under the order of the plan's final draft (21:26), H3 would not have been tested. Under Holm's correction (not registered) H1, H2, H3 and H5 would pass and H4 would not. "The registered outcome stands." | Holm-adjusted p: H1 0.0234, H2 0.0008, H3 0.0032, H4 0.0625, H5 0.0234 | §6.2, Table 5 |
| H4 under other inference | Inverted sign-flip interval −1.25 to 0.08 (includes zero). Stories as clusters: H4 p = 0.0156, H5 superiority p = 0.0547. "The registered unit stands." | §6.2 |
| Where the tenancy effect sits | The 9 families that contain denied- or open-event claims (termination and rent increase): CasePath lower in every one, by at least 2.33. The other 15 families: lower in 10, equal in 2, higher in 3, by at most 0.75 | §6.2; Supp. Fig. S6 |
| Open or stated (claim-run means) | 56 claims with an open fact (32) or a denied defining event (24): 0.40 against 3.39 and 3.06. 40 claims that state every fact: 0.19 against 0.39 (p = 0.2761) and 0.19 (p = 0.8984), "no advantage over either" | §6.4, Table 8 (p. 15–17) |
| Share of such files | With the mix inside the open group held at the test's, CasePath's expected error is lower than the frontier prompt's at any share above 0%, and "above about 4%" when unneeded holds count. "The share in real files is not known to us." If real files with open facts rarely deny the defining event, the right-hand end of every line would be much lower and the gap far smaller: on the 23 claims with an open branch fact, CasePath made 0.23 strict unsafe errors per claim and Rules in context 0.51 (registered subset rows) | §6.4, Fig. 5 (p. 15–18) |
| The open condition's own documents on theft | Held in 83% of pairs by CasePath, 85% by Rules in context, 85% by the frontier prompt, 90% by Self-consistency. "Their failure was changing other documents." | §6.4 |
| Same budget | Self-consistency stayed near 2.10 on tenancy from 1 to 15 samples; on theft it fell from 1.84 to about 1.00 and levelled off from 9 samples. Checklist only with 1 to 3 readings: 0.52 → 0.34 (tenancy), 1.22 → 0.55 (theft). At matched cost: −1.76 per claim (p = 0.0006), −0.53 per pair (p = 0.1328, not significant) | §6.5, Fig. 6 (p. 19) |
| More readings hold more | From 1 to 3 readings, unneeded holds 0.003 → 0.302 per claim; all deviations 0.55 → 0.74 | §6.5 |
| Error decomposition | Parts add up exactly; none changes with the order of stages. Tenancy, cost-efficient 0.313 = routing 0.045 + document judgment 0.076 + reading 0.167 + hold 0.024; frontier 0.302. Theft, cost-efficient 0.583 = rule 0.333 + reading 0.088 + hold 0.157 + 0.005; frontier 0.833 = rule 0.333 + reading 0.250 + hold 0.250. The rule part is 0.22 to 0.44 under two uncertain mappings | §6.3, Table 6 (p. 16) |
| Frontier theft cell | The decomposition puts the frontier model's extra errors in its readings and holds, and the stored readings trace them to two broadly worded conditions. The frontier model admitted the third-party condition as true in 8 of its 8 ordinary runs; the cost-efficient model in 0 of its 50 ordinary runs, development runs included. Its value for the traces condition changed between the two texts of a pair | §6.7 (p. 19) |
| Clean room | Two AI sessions that never saw the engine, its outputs or the reference wrote evaluators from the rule text, the machine-readable process catalogue and the designed fact states; both agreed with the registered reference on 1,024 of 1,024 document decisions. "This confirms the implementation of the catalogue." One session later listed a scratch directory and saw file names; by its report it opened none | §6.6 (p. 18) |
| Where the reading matters | The denied-event claims, "whose right answer rests on our reading that a denied defining event ends the process, carry about two thirds of the tenancy lead": 69% of the lead over the same-model prompt and 62% over the frontier prompt, by claim weight. Amending the workflow to the other reading removes 64% and 36% of the two leads | §6.6 (p. 18), §7.1 |
| Readings of the rule text, product's workflow unchanged | A1 ("a denied defining event does not stop the process"): +0.55 (p = 0.1348) and +0.21 (p = 0.5134); 2 of 10 registered tenancy contrasts reverse with p < 0.05. All four readings: 6 of 10 reverse, among them H2 (+0.94, p = 0.0234) and H3 (+0.75, p = 0.0472). A2 and A4: the result holds. The alternative references were written by one evaluator, to the authors' instruction, and "are not independent evidence" | §6.6, Table 9 (p. 20) |
| Readings of the rule text, workflow amended | Replay without model calls (reproduces 285 of 286 stored checklists). Under A1 a significant but smaller lead: −0.66 (p = 0.0002) and −1.00 (p = 0.0014), resting on the 9 open-event claims; baselines not re-run, which favours them. A3 and all four together are upper bounds | §6.6, Table 9 |
| Lint (a proposed diagnostic) | Theft test texts: both over-broad conditions flagged, among 14 flags (frontier) and 12 (cost-efficient). Tenancy: 8 and 9 of 10 conditions flagged. Mutation test (USD 0.15, planted by the analyst who designed the lint): 6 of 6 widened conditions flagged, 3 already flagged before widening; 3 of 5 untouched conditions flagged. False-alarm rate unknown | §6.7 (p. 19–20) |
| "A flagged condition is treated as open", frontier theft | In-sample flags: 0.833 → 0.528. Flags from development runs only: 0.778, above the frontier prompt with the original rules (0.67). No paired difference significant (p 0.1406 to 0.6719). "Did not help out of sample." | §6.7; Supp. Table S43 |
| Principle 2: an open fact gets its own value; every completion is evaluated | On 277 of 286 claim-runs: exact deferral 0.25 strict unsafe errors per claim against 0.23 for strong Kleene evaluation, and 0.65 against 1.31 deviations; strong Kleene had fewer strict errors in 3 claim-runs and more in 0 | §7 |
| Principle 3: admit only agreeing, quoted readings | Of 1,344 tenancy fact values, 9 were admitted wrong, each with all readings agreeing; 6 of them admitted a denied defining event as having happened. Reading errors on the denied-event claims make up about half (49%) of CasePath's strict unsafe tenancy errors. With one reading instead of three: 0.34 → 0.52 per claim and 0.55 → 1.22 per pair. Readings that share a model and prompt miss a shared misreading | §3.5 (p. 8), §7 |
| The theft rule review | It made both single prompts worse (1.47 → 1.74; 0.67 → 0.95); only 11% and 27% of the change fell on documents a changed rule names | §6.1 |

### Formal results and the design history

| What the paper says | Evidence | Status | Where |
|---|---|---|---|
| Soundness relative to admitted facts (Prop. 3.1); strong Kleene evaluation over-holds where branches meet again (Prop. 3.2); exact deferral never holds what strong Kleene requests or marks not needed (Prop. 3.3); reading errors (Prop. 3.4). Each within the stated scope: flow workflows, two-valued independent facts, document presence taken as given | Proofs in App. A; the four tested workflows are flow workflows, and the plain walk on theft gives what exact deferral gives, checked with the product's own code by `analysis/check_fragment.py` | formal | §3, App. A |
| What reading errors become | Over the 150 Study 1 tenancy claims, each fact misjudged with probability 0.1: unresolved values give 8.4 expected holds per 100 required documents and no unsafe error under exact deferral; wrong values give 8.4 missed and 3.7 unnecessary requests per 100 | development (exact, no model) | §3.5, Fig. 7 (p. 28) |
| Neither earlier configuration was better than Rules in context | Study 1 (frontier model): 38 against 22 wrong theft changes (p = 0.211); 0.081 against 0.063 unsafe errors per tenancy claim (p = 0.250). Study 2: none of four primary contrasts confirmed | development (pre-registered at the time) | §5; Supp. S1, S2 |

## (b) What the evidence does not support

- **Holding on theft.** The theft measure cannot tell a hold from reading the open fact as false, and exact deferral never ran on theft (§6.4).
- **An advantage on files that state every fact.** 0.19 against 0.19 for the frontier prompt (§6.4).
- **Independence from the reading of the rules.** The references come from the engine CasePath implements, under a silence clause the authors wrote. The clean room confirms the implementation, not the reading. Under reading A1, with the product's workflow unchanged, the tenancy result reverses (§6.6, §7.1).
- **An advantage over self-consistency on theft.** H4 failed; with nine clusters this does not show the designs equal (§6.2, §7.1).
- **An advantage on the frontier model on theft.** No advantage, one run, checklist-only setting, no hypothesis (§6.3).
- **That the rules set the frontier theft limit.** The rule part is the same in both cells (0.33, range 0.22–0.44); the frontier excess is in readings and holds (§6.3, §6.7).
- **A validated lint.** Proposed diagnostic; flags most conditions; false-alarm rate unknown; remedy failed out of sample (§6.7, §7.1).
- **New theft rules.** Theft reuses the nine conditions and the rule base of the earlier studies, reviewed by AI sessions that knew them (§5, §6.1).
- **Legal correctness.** No jurist or lawyer checked any rule, reference or reading (§7.1, App. D).
- **Real, long or human-written files.** Texts are synthetic, 77–320 words, written by an AI session that could read the product's prompts (§6.1, §7.1).
- **A cheap design.** 20 to 42 times the same-model prompt, more unneeded holds, times only as lower bounds (§6.5, §7.1).
- **Value of the brief, process builder, result checker or reply draft.** They are outside the claims and made no detectable difference in errors; their value to a handler was not measured (§4.1, §7.1).
- **That Knowledge (learning from corrections) works.** Every run started with an empty store (§4.1).
- **Any result of the deployment study.** None has run (§5, App. B).
- **Regulatory standing** under the EU AI Act (§2).
- **That the tested commit is the product.** Its merge has not been confirmed; the product has moved on (§6.1, App. C; Supp. S11.5).

## (c) Remaining requirements

### Summary

| Item | Who must act | What exactly is needed | What it unblocks |
|---|---|---|---|
| `%% AUTHORS:` facts (14, listed below) | authors | Write each fact into the source or delete the sentence that waits for it | Submission; App. D; the first-page footnote and cover letter |
| Legal questions on the theft rules (3 decisive of 8; listed below) | jurist | A ruling on the scope of the traces condition, on when the insurer's instruction on measures is due, and on whether an unidentified thief is a third party | Closing the frontier theft cell; the theft rule base; the lint's use |
| Interpretive choice on a denied defining event (tenancy) | jurist | A ruling on whether a denied defining event (for example, a rent-increase notice not received) ends the process | Whether about two thirds of the tenancy lead stands; which row of Table 9 is the result |
| Deployment study: freeze | planner, authors | Freeze the protocol (now 1.0-rc) as version 1.0 on 20 November 2026 with the contents of `expert_study/PREREGISTRATION_DRAFT.md` §13.3 | Any real-file result; Q1 (archival) before Q2 (experts) |
| Deployment study: builders' inputs (7, listed below) | product's builders | The inputs of `expert_study/REQUEST_TO_PRODUCT_20261112.md`, before 20 November | The freeze; the predictions; the development replay |
| Deployment study: questions (7, listed below) | product's builders | Answers to the questions of the same file | Definitions of decision points, T2, budget, the paper's sentence on dossier provenance |
| Ethics statement for the deployment study | authors, study lead | Approving body and reference, or why none is required; consent procedure | App. B; any session with experts |
| DOI archive of the tested commit | authors | Deposit commit `6a72159c` (source-tree hash `030480203f…`) and cite the DOI in §4 | The artefact claim of §4 |
| Release blockers (10, listed below) | authors, product's owners, insurer | The decisions of `release/SCRUB_REPORT.md` §2 and §7 | The release the introduction promises ("will be released"); App. D |
| Response-cache archive | authors | Publish the Study 3 response cache (about 23,000 files, 730 MB; whole folder 79,404 files, 0.9 GB) with a DOI or URL, or delete the offer from App. D | Byte-for-byte re-check of the readings, cost split and post-hoc analyses from a clone |
| The product moved on from the tested commit | product's owners, authors | Decide on the offered branch that applies the tested changes to the owners' tip (by their own check on real development files); report the merge state in §6.1, App. C and Supp. S11.5 | The merge-status `%% AUTHORS:` lines; whether the deployment study runs a product that contains the tested design |
| No real-file and no expert result | planner, product's builders, insurer | Run the frozen protocol: archival comparison on four sealed dossiers first, then five experts | Any claim about real files or about handlers; Section 7 of the article (not input now) |

### The `%% AUTHORS:` facts

Found by `grep -rn "%% AUTHORS" paper/` on 12 November 2026 at commit `2851d5f6`: 24 lines in 10 files, 14 distinct facts. "Main" lines are in files the article inputs; "Supp." lines in files the supplement inputs.

| Fact | Lines |
|---|---|
| 1. Conflict of interest and roles: each author's relation to the insurer and to the product's owners, and who decided the merge of the tested commit | main `main.tex:86` |
| 2. Disclosure of the conference version (venue, year, title) and what is new, as a first-page footnote and in the cover letter | main `main.tex:88` |
| 3. DOI of the archived tested commit | main `sections/s4_casepath.tex:5` |
| 4. Provenance of the eleven dossiers: are they the insurer's real, unaltered closed claim files, and how did they reach the hackathon | main `sections/s5_history.tex:13`, `sections/app_b_protocol.tex:12` |
| 5. Development counts from the insurer (agreement with practice on the seven development dossiers): cite only with the insurer's approval | main `sections/s5_history.tex:14`, `sections/app_b_protocol.tex:23` |
| 6. Merge status of commit `6a72159c` (confirmed, rejected or pending) | main `sections/s6_test.tex:16`; Supp. `sections/app_d_deviations.tex:29` |
| 7. The insurer's share of files with an open deciding fact, if the insurer supplies and approves it; otherwise keep "not known" | main `sections/s6_test.tex:201` |
| 8. State of the product: whether the owners accepted the offered branch, what their check showed, whether the tested changes are in the product | main `sections/app_c_deviations.tex:53`; Supp. `sections/app_d_deviations.tex:86` |
| 9. Ethics statement for the deployment study | main `sections/app_b_protocol.tex:5`; Supp. `sections/app_i_protocol.tex:34` |
| 10. Which release: a scrubbed commit with its own parity hash, or the tested commit with the insurer's approval | main `sections/app_d_repro.tex:9`; Supp. `sections/app_g_repro.tex:13` |
| 11. Location of the response-cache archive, or delete the offer | main `sections/app_d_repro.tex:8`; Supp. `sections/app_g_repro.tex:17` |
| 12. Licences of `fresh/`, `dev_probe/`, `fresh2/`, `rule_review/` and `runs/` | main `sections/app_d_repro.tex:10`; Supp. `sections/app_g_repro.tex:21` |
| 13. Record of the rule editors' model and sessions in `rule_review/` (no record there says they were AI sessions; the statement rests on the authors' record) | main `sections/app_d_repro.tex:17`; Supp. `sections/app_g_repro.tex:53` |
| 14. Names and versions of the AI coding and writing assistants, as the venue requires | main `sections/app_d_repro.tex:18`; Supp. `sections/app_g_repro.tex:60` |

### Legal questions

From `rule_review/lint/final/RECONCILIATION.md` ("Points for a jurist", 8 points). Supp. S12.4 names three of them as deciding the theft floor:

| Rule | Question | Why it matters |
|---|---|---|
| 003 (traces) | Should the condition be limited to changes that could hinder establishing the cause or amount of the loss? Do mitigation or public-interest changes need the consent documents at all? Does the "help services" arm, from one insurer's terms only, apply to the others? | The traces condition is one of the two read too broadly by the frontier model; with designed values the floor is 0.33 or 0.56 depending on this reading (Supp. S12.4) |
| 004 / 004.a (insurer's instruction) | Is the duty to obtain the insurer's instruction triggered in every claim, or only where mitigation, preservation or rescue measures were to be taken? | Decides whether that document is on every ordinary checklist |
| 042 (third party) | Is a thief who has not been identified "ein Dritter" whose fault caused the loss? If not, the condition should say "an identified third party"; if so, the document is due on every theft paid by two of the insurers | The condition the frontier model admitted in 8 of 8 ordinary texts; the two blind editors disagreed on narrowing it, and it stays unchanged |

The other five points (002 police report, 008 "at home", 014 original vouchers, 073 cover without simple theft, insurer scope of insurer-specific rules) are in the file.

**Tenancy, the interpretive choice.** Whether a denied defining event ends the process "is the one interpretive choice on which most of the tenancy effect rests: the denied-event claims carry 69% and 62% of the lead over the two prompts"; "no lawyer has ruled on it" (§7.1). Amending the workflow to the other reading removes 64% and 36% of the two leads; the rest rests on the 9 open-event claims (§6.6).

### The deployment study

Protocol: `expert_study/PREREGISTRATION_DRAFT.md`, version 1.0-rc, summarised in App. B. Freeze on 20 November 2026 (day 10). After the freeze: decision points and cut copies; two transcriptions (T1, T2); settlement by the study lead; runs; archival results and an archival hash. No expert session before that hash exists; the first session, planned for 24 November 2026, moves later if needed. Only counts leave the insurer.

What the product's builders are asked to supply before 20 November (`expert_study/REQUEST_TO_PRODUCT_20261112.md`):

| # | Requirement | If it is missing |
|---|---|---|
| 1 | A law-only variant of the handler process, hashed at the freeze, with one line on how it was written | The replay compares Knowledge only |
| 2 | Each practice Knowledge item names the development dossier(s) it came from | The replay is not run |
| 3 | The replay command's scope (measures, decision points, stored runs on cut copies) and its output per dossier, decision point and arm | — |
| 4 | Labels at every decision point of the seven development dossiers, and the development counts with denominators for the five measures | No predictions can be fixed |
| 5 | The comparator prompt fixed before the freeze; its SHA-256 in the freeze record | The comparison is not reported |
| 6 | A statement of which dossiers' later pages any builder has read | The exposure record is incomplete |
| 7 | Confirm or correct the mapping of `stated_as` to treatment (established = admitted, presumed = presumed, put_to_handler = held with a question, else none) | — |

Questions only the builders can answer (same file):

| # | Question |
|---|---|
| 1 | What counts as an outgoing action in the files (payments, cover decisions, system acknowledgements)? |
| 2 | Who runs the second transcription (T2), and where? It must be inside the insurer and not a session that built the product |
| 3 | Does the token budget cover one CasePath run and one comparator run per decision point? If not, the cap, so a rule for which decision points run can be registered |
| 4 | Were the 2 of 2 follow-up cases ones where the file shows the period? Is 20 of 23 the right count for "CasePath's requests that are in P"? |
| 5 | Do `next_in_days` and `follow_up` enter `items_sha256`? |
| 6 | What share of the seven development dossiers has at least one deciding fact open at the first decision point? (One count per file; the paper needs it to say how common the case type is that carries the synthetic result) |
| 7 | Are the eleven dossiers real and unaltered, real with names removed, or constructed? |

### Release blockers

From `release/SCRUB_REPORT.md` §2 (the report is internal and must be deleted from any export):

| # | Blocker | Who decides | Recommendation in the report |
|---|---|---|---|
| 1 | Git history: 1,110 commits on 12 branches, including earlier states of pseudonymised data | product's owners | Publish a new repository whose first commit is a reviewed export |
| 2 | The tested product names the insurer in its code; any edit changes the parity hash | product's owners, insurer | (a) publish `6a72159c` unchanged with the insurer's written approval, or (b) a scrubbed commit with its own hash reported beside the tested one |
| 3 | A Knowledge seed derived from the insurer's request letters ships as package data | product's owners, insurer | Remove it with its test, loader line and interface text, or keep it only with written approval |
| 4 | Five internal product documents and README lines describe the insurer's internal work | product's owners | Remove the documents; neutral README text |
| 5 | Deployment files for the insurer's platform | product's owners | Keep with approval, or remove |
| 6 | `design-plans/` (3,174 insurer hits, 351 MB of video) | authors | Leave the folder out |
| 7 | The paper branch's own older `casepath-internal/` | authors | Leave it out; publish the tested commit's copy |
| 8 | Local paths and names in top-level and research documents | authors | Replace by neutral paths; leave out internal handoff documents |
| 9 | The insurer's public policy terms used as research sources, by name | authors, product's owners | Keep with approval, or rename to a neutral label |
| 10 | No licence for `fresh/`, `fresh2/`, `dev_probe/`, `rule_review/`, `runs/`, `expert_study/`, `paper/` | authors | Add a licence file to each |

Also from the report: release from neutral branch and tag names; check the remaining screen captures by eye; decide on the response caches (next row); the public repository URL cited in the paper has not been tested with `git clone`.

### Response caches

`runs/product/cache/` is ignored by git. All 22,999 cache files that Study 3's stored plans reference are ignored (`release/SCRUB_REPORT.md` §6). App. D says the Study 3 response cache "will be offered as a separate archive"; Supp. S16 gives about 23,000 files, 730 MB. Without it, a clone reproduces every table but skips the re-runs that read the cache, and a re-run with model calls pays for every call again and may get different answers.

## (d) How to reproduce

One command, no model calls (`RELEASE.md` §3; App. D): clone the repository, fetch the product branch named in `RELEASE.md` §3, install `requirements-reproduce.txt` (it pins `pypdf==5.9.0`; another version breaks the Study 1 cache lookup), and run `research/tmis2026/reproduce.sh`.

| Run (`RELEASE.md` §8) | Result |
|---|---|
| Fresh clone, cache absent, 11 November | 59 steps passed, 2 skipped, none failed; 11 min 20 s |
| Working repository, cache present, 11 November | 61 passed; 11 min 27 s |
| Working repository, cache present, 12 November, after the post-hoc steps were added | 83 passed; 597 s. Not repeated in a fresh clone |

`analysis/verify_paper.py --paper-only` passed on 12 November 2026 at commit `2851d5f6`, the sources of the delivered PDFs: every macro file reproduces byte for byte, and both documents build from clean with no undefined reference, no multiply defined label and no overfull box over 5 pt.

Re-running Study 3 with model calls (`harness/study3/run_all.py`; `RELEASE.md` §4) needs the reader's own model endpoint and key and changes to two model clients. The stored run cost USD 34.33 by the ledgers (22.41 cost-efficient, 11.92 frontier), in five invocations over about 5 h 40 min. Answers can differ: no model snapshot, temperature or seed is recorded.

## The LaTeX package

`CasePath_TMIS_overleaf.zip` holds the sources of the delivered PDFs: `main.tex`, `supplement.tex`, `macros.tex`, `references.bib`, 7 macro files, the 29 section files the two documents input, 13 figures, a `README.txt` and a `latexmkrc`. The `latexmkrc` builds both documents under their own names first, because Overleaf compiles under the job name "output" and the two documents read each other's `.aux` files by name. Tested from the unpacked zip in a scratch directory: the paper's own build order gives 31 and 69 pages with no error, no undefined reference and no overfull box over 5 pt, and text identical to the delivered PDFs; a local latexmk run with Overleaf's job name and options gives the same page counts with no undefined reference. Not tested on Overleaf itself.
