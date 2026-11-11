# Review response checklist

Paper: *CasePath: Agents That Read, Rules That Decide. Requesting Evidence for Insurance Claims with Executable Workflows* (ACM TMIS draft).
Pointers refer to `CasePath_TMIS.pdf` (55 pages) and, with "Supp.", to `CasePath_TMIS_supplement.pdf` (27 pages), both built on 2026-11-11. Every pointer below was checked against those PDFs.

Status: **answered**, **in part** (what is missing is named), **not answered** (why, and what would be needed). A status says what the current text does, not what an earlier version did.

Sources of the criticisms. The original review texts of CptP, 2Kwe and SBTv and the original wording of J01–J15 are not in the repository (searched for "CptP", "2Kwe", "SBTv", "J01" in every text file). The criticisms below are the paraphrases of the previous version of this file (`git show HEAD:research/tmis2026/deliverables/REVIEW_RESPONSE_CHECKLIST.md`). Check them against the originals before writing the letter. The old file merged J05, J08 and J12 into one paraphrase ("use topic sentences"); where each was raised is not recorded.

Names. The conference version's "Study A" (theft pairs) and "Study B" (tenancy claims) became Study 1 (Supp. S1). The article's confirmatory test is Study 3 (Section 6), on new sealed data (`fresh2/`).

## Reviewer CptP

| # | Criticism (one line) | What the paper now does | Where | Status |
|---|---|---|---|---|
| W1 | Study A shows no accuracy benefit: the gates failed (Holm p = 0.797), CasePath is weaker on several conditions, and its advantage comes from baseline withdrawals. | A new pre-registered test on sealed theft data. Errors are wrong + missed changes, so withdrawals count as errors. H1 confirmed: 0.58 against 1.74 per pair for the same model's single prompt (p = 0.0078). H4 failed: against Self-consistency p = 0.0625. With the original rules the frontier single prompt made 0.67, close to CasePath's 0.58. The original study's results are kept in the supplement. | §1, §6.3, §6.4, Table 7, Fig. 4, Table 21; Supp. S1.5, Table S7 | in part: no advantage is shown over Self-consistency or over the frontier prompt with the original rules; H1 uses rules reviewed by editors who knew the test conditions. |
| Q1 | What accuracy claim does Study A support? | A narrow one, stated in the text: on theft, fewer errors than the same cost-efficient model in one prompt, with the reviewed rules; not shown against the frontier prompt or Self-consistency. "H1 to H3 hold for the cost-efficient model only." | §1, §6.4, §7 "Where it does not pay", §7 "Limits", §8 | answered |
| W2 | Study B's 98% result follows from the design; holds were unscored; the conservative contrasts were negative; the original evaluator accepted nothing; scoring was switched post hoc. | Holds are scored: "all deviations" counts wrong holds, and held shares and unneeded holds are reported. Measures and tests were fixed in the plan before the run. The paper says the tenancy references come from the engine CasePath implements, under a silence clause the researchers wrote. A stress test makes unmentioned facts true (added after review). | Abstract, §1, §6.1, §6.2, Table 8, §6.5, Table 24, §7 "Limits" | in part: the tenancy references are still produced by CasePath's own engine. Disclosed, not removed. Needs references made independently of the engine (for example the planned expert study on real files). |
| Q2 | Are Study B's references made from the same templates? How accurate is the dispute-type judgment? How should holds count? | Same templates: yes, stated for Study 1 (oracle 147 of 150) and for Study 3 (references from the engine under the silence clause). Holds count as deviations. Fact-level accuracy is reported for the defining event and the branch facts (added after review). | §6.1, §6.2, App. C.2, Table 11; Supp. S1.2.2 | in part: no routing (dispute-type) accuracy is reported for Study 3. It can be computed from the stored outputs without model calls. |
| W3 | One model, one run, no prior systems; baseline prompts not shown. | Two models (cost-efficient and frontier), 3 runs per case. Comparators: single prompt, Self-consistency (5 samples), Model executes rules, ReAct, two-valued execution, original rules. All prompts are quoted. | §6.2, Table 6, Table 7, App. F.2, F.3 | answered. Note: Chain of Logic and the benchmarks' policy-in-prompt agents were not run (§2); the full product was not run on the frontier model (only "checklist only", one run). |
| Q3 | How many runs underlie each number? | 3 runs per design and case; the frontier checklist-only design has 1. Calls and cost per case-run come from the ledgers. | §6.2, Table 6, App. B.1 | answered |
| W4 | Data are synthetic, self-authored and unreviewed; held-out inputs were exposed; temperature was unset. | Study 3 data were sealed before any design ran and read before the freeze only by the writing and blind-check sessions. One AI agent session wrote all texts, with read access to the repository; a model of the same family checked them blind. No design sent a temperature; provider defaults applied and are not recorded. Run-to-run variation is measured. | §6.1, Table 5, App. B.1, App. C.2, Table 13, App. E.4, §6.5 | in part: data are still synthetic and written by an AI session with repository access; no expert or jurist reviewed data or rules. Needs the expert study on real files (App. G). |
| Q4 | What was exposed? Was there expert review? | Disclosed: Study 1's held-out tenancy messages were visible during development; the rule editors knew the theft conditions Study 3 reuses; no jurist reviewed the rules; the expert study has not run. | Supp. S5.1; §1, §5, §6.4, §7 "Limits", App. B.2, App. E.4 | answered (by disclosure) |
| W5 | Algorithm 1 was a picture; the formal definitions sat in the appendix; Figure 2 was a low-resolution raster. | The semantics are in the main text as Equations (1)–(3) with Propositions 3.1–3.4 and the admission rule as Table 2; proofs in App. A. The Study 1 algorithm is typeset (Algorithm S1). All figures are vector PDFs except Fig. 1, which crops product screenshots at 300 ppi. | §3, Table 2, App. A; Supp. S1.1 | answered |
| W6 | The related work was two paragraphs; the bibliography was inconsistent. | A related-work section of nine paragraphs, each saying what CasePath does differently, and a comparison table. One ACM style. BibTeX warns of a missing address, publisher or page range in 16 entries of the article (cosmetic). The Swiss supervisory guidance the internal referee asked for is not cited (not verified). | §2, Table 1 | answered |

## Reviewer 2Kwe

| # | Criticism (one line) | What the paper now does | Where | Status |
|---|---|---|---|---|
| W1/Q1 | Technical novelty over neuro-symbolic and process-aware methods is unclear. | Each related-work paragraph names what CasePath does differently. The paper says the semantics are not new: "what is new is the application and the reconvergence case of Proposition 3.2". Table 1 compares systems on four properties. | §2, Table 1, §3.3 (Prop. 3.2), Fig. 2 | answered |
| W2 | Generality is limited; the studies test different parts; no comparison with existing agents. | One product, one workflow format and one set of measures on both data sets. ReAct, a tool-using agent, is compared. | §4.2, §6.2, Table 6, Table 7 | in part: still synthetic, two domains (tenancy, household theft) under Swiss law, texts of 77–320 words; long-file paths never ran (§6.1, §7 "Limits"). Needs other domains or real files. |
| Q2 | How are extracted rules validated? Can errors be found without manual work? | Study 2 tested a label-free check and repair of the rules; it failed. The rules used in Study 3 were reviewed by two AI editor sessions: 9 changed, 14 queued for a jurist, no jurist has reviewed them. Errors trace to a rule or a reading. | §5 "What failed", "What remains", Table 4, §7 "For an organisation", App. E.4 | in part: the honest answer is "not without review"; the jurist review has not happened. |
| Q3 | Why custom baselines instead of adapted prior methods? | ReAct and self-consistency are implemented over the same workflow and files; "Model executes rules" states the semantics in the prompt. The paper names the published designs it does not run. Prompts are quoted. | §2 "Agents that apply the rules", Table 6, App. F.3 | in part: the paper does not say why Chain of Logic and the policy-in-prompt agents were not run. One sentence would answer it. |
| Q4 | Why different datasets for different aspects? | Study 3 has two regimes, each with its own data, workflow and measures: theft scores the change between two texts that differ in one fact; tenancy scores the whole checklist. | §6 (opening), §6.2, App. C.2 | in part: the reason for two data sets is not stated in one place. |

## Reviewer SBTv

| # | Criticism (one line) | What the paper now does | Where | Status |
|---|---|---|---|---|
| W1 | The architecture is standard (neuro-symbolic, DMN, BPMN), and the process definition is ad hoc across studies. | Positioned against rules as code, DMN, Catala, neuro-symbolic systems, case management and declarative or artifact-centric process models. One workflow definition and one file format serve both data sets; both tested workflows are shown to be flow workflows. | §2, Table 1, §3.1, §4.2, Listing 1, App. A, App. F.5 | answered |
| W2 | No formal problem definition and no objective. | §3 defines the workflow, assignments, completions, evaluation (Eqs. 1–2), exact deferral (Eq. 3) and unsafe errors, with four propositions. | §3.1–§3.5 | in part: no objective function is stated. Route choice is fixed at conversion ("cheapest route", App. F.5), not formulated as an optimisation in §3. |
| W3 | Algorithm 1 is a schematic without types or complexity; the logic is trivial. | The semantics are equations, not pseudocode. Cost: one evaluation per completion; above eight open facts or 256 combinations the product uses the plain walk. Prop. 3.2 shows strong Kleene evaluation over-holds where branches meet again. | §3.3, §3.4, Fig. 2, App. A | in part: no complexity statement (the earlier coNP result is no longer in the paper). Add one sentence if this reviewer is sent the revision. |
| W4 | Synthetic data, no experts, circular evaluation. | As CptP W2 and W4: circularity stated in the abstract and §6.1; stress test of presumptions; fact-level accuracy; blind check of the texts. Expert study only as a protocol. | Abstract, §6.1, §6.5, Table 11, Table 24, §7 "Limits", App. G | in part: still synthetic, the expert study has not run, the tenancy references are the engine's own. |
| W5 | Narrow scope and weak baselines; no neuro-symbolic, ReAct or DMN comparison. | ReAct run (H4 component, 0.58 against 1.69, p = 0.0117). Two-valued execution of CasePath's own readings stands for closed-world rule engines. Self-consistency and Model executes rules added. | §3.3, §6.4, Table 7, Table 8, Table 14 | in part: no model-writes-logic system (Logic-LM style) was run; scope is two synthetic Swiss domains. |

## Comments J01–J15

| ID | Comment (paraphrase) | What the paper now does | Where | Status |
|---|---|---|---|---|
| J01 | State the RQ and its rationale before the contributions. | The introduction states the problem class ("deciding which evidence to request when the decision depends on facts the file does not settle"), why it matters, and the design-science framing, before the contributions. | §1 (paragraphs 2–3) | in part: there is no explicit research-question sentence. One sentence before the contributions would close it. |
| J02 | Expand related work with a summary table showing how ours differs. | Nine paragraphs, each ending with how CasePath differs, and a comparison table. | §2, Table 1 | answered |
| J03 | Separate the insurance background from how the model works. | Method and product are separate sections (§3 decision rule, §4 CasePath). Insurance background is the running example (§1) and one sentence on claims handling (§2, "Case management and process models"). | §1, §2, §3, §4 | in part: no dedicated background on legal-protection claims handling. |
| J04 | Say what each study is meant to achieve. | §5 frames Studies 1 and 2 as build-and-evaluate cycles and says what each led to; §6 states five ordered hypotheses. | §5, Table 4, §6.3, Table 7 | answered |
| J05 | Use topic sentences. | Results paragraphs open with their finding ("H1, confirmed.", "H4, not confirmed, and H5, not tested."); §6.5 paragraphs open with their finding; each principle in §7 is headed by its statement. | §6.4, §6.5, §7 | answered |
| J06 | Relate the methods to the literature to give a red thread. | §2 ties each line of work to what CasePath does and says which published designs Section 6 tests. | §2, Table 1, Table 6 | answered |
| J07 | A table of methods × elements. | Systems × four properties (Table 1); pipeline steps × what they read, may change and may never change (Table 3); designs with calls and cost (Table 6). | Table 1, Table 3, Table 6 | answered |
| J08 | Use topic sentences. | As J05. | §6.4, §6.5, §7 | answered |
| J09 | A table of terms. | Terms are defined in the text (§3.1–§3.5; case-run, claim-run, text-run and pair-run in §6.2). There is no glossary table in this version. | §3, §6.2 | not answered: the glossary of the earlier version was dropped. A short table would add length to a 55-page article. |
| J10 | Since CasePath still errs, what should humans monitor? | Who writes and reviews workflows and presumptions; who answers for a presumption; what an auditor gets (each value with its quotation, each presumption with its clause, each hold with its question, the code hash). Disagreeing readings are marked for a person; uncertain routing goes to a person. | §7 "For an organisation", Table 2, §4.1 | in part: no evidence on human oversight; the expert study has not run. |
| J11 | Managerial guidance on when to use which design. | Four design principles, each with its evidence and boundary condition, and where execution does not pay. The old guidance table is in the supplement, marked superseded. | §7, Supp. Table S6 | answered |
| J12 | Use topic sentences. | As J05. | §6.4, §6.5, §7 | answered |
| J13 | Where should a human step in (unresolved dispute type)? | Several candidate workflows, or a second contradiction between routing and admitted facts, hand the claim to a person; disagreeing readings are marked for a person. | §4.1, Table 2, Table 3 | answered |
| J14 | Method statements do not belong in the results. | Measures are defined in §6.2 and hypotheses in §6.3; §6.4 and §6.5 report findings. One methodical passage remains: the H4 paragraph explains the exact test. | §6.2, §6.3, §6.4 | answered |
| J15 | Start the discussion with a recap. | §7 opens with the four principles, not a recap. The recap is in §8. | §7, §8 | not answered: needs two or three sentences at the start of §7. |

## Internal referee rounds of this version

Reports: `analysis/review/REFEREE_REVIEW.md` (round 1, major revision, concerns M1–M10) and `analysis/review/REFEREE_REVIEW_ROUND2.md` (round 2, minor revision, new problems N1–N12). Round-2 page and table numbers refer to an earlier build; the pointers below are to the current PDF. The authors decided to keep the abstract as written (`FINAL_FIX_BRIEF.md`: "The abstract is final"); round-2 items that asked for abstract changes are therefore open.

### Round 1, major concerns, with the round-2 status

| # | Concern (one line) | Round 2 | Now | Where | Status |
|---|---|---|---|---|---|
| M1 | Contribution and IS positioning unclear; two of four contributions are not results; missing related work. | largely resolved | Problem class, stakes sentence and design-science framing on page 1; three contributions, release and protocol as resources; principles with boundaries; review effort ("duration was not recorded") and owner of a presumption stated. | §1, §2, Table 1, §7 | in part: the Swiss supervisory guidance is not cited (could not be verified from an official page; `analysis/REFERENCES_ADDED.md`). |
| M2 | Tenancy references are circular; data aligned with the design. | resolved | Abstract and §6.1 state it; stress test; fact-level table with right and wrong "unresolved" split. | Abstract, §6.1, Table 11, Table 24 | answered |
| M3 | Tenancy effect sits in 33 designed gating claims; the unit amplifies them. | partly resolved | Claim-level outcomes, reweighted mixes ("none tied to an insurer's real intake"), per-family plot, what single prompts did on denials; Principle 1 compares like with like (1.94 and 1.04). | §1, §6.4, §6.5, §7 Principle 1, Tables 10, 14, 22, 23, Fig. 7 | in part: the abstract keeps its wording; no legal source for "announced but not received needs no document", which the paper calls a choice of the data design (App. C.2, §7 "Limits"). |
| M4 | Unequal development effort; reviewed rules favour execution. | partly resolved | One-sided effort stated; comparator texts dated, none changed after 19:10 on 10 Nov; original-rule rows in the body; R9 explains nothing and says so. | §6.1, App. B.2, §6.4, §6.5, Fig. 4 | in part: the abstract says "with rules reviewed for execution" but not "by editors who knew the test conditions" (the introduction does), and omits the frontier original-rules result (0.67). |
| M5 | Formal statements lack their scope; the system does not meet their premises. | resolved | Scope in each proposition; admission as Table 2; related facts acknowledged; plain walk on theft stated; document presence declared a model judgment. | §3, Table 2, App. A, Fig. 5 | answered (the abstract's "holds every request that depends on an open fact" is unchanged) |
| M6 | Inference with 9 clusters; dependence the clustering ignores. | largely resolved | Inverted sign-flip intervals, stories as clusters, two-way resampling; captions say the percentile theft bars under-cover; registered interval column kept in Table 7. | §6.4, Table 7, Fig. 4, Table 21, Fig. 7 | answered |
| M7 | Checklist-only comparison and cost split do not support "later agents changed nothing". | partly resolved | "No detectable difference"; identical checklists 93% and 59%, against 81% and 17% for two runs of the full product; cost reconciled; "can affect the checklist" removed. | §4.6, §6.4, §6.5, Table 18, App. D | answered |
| M8 | Freeze integrity and test-data independence need fuller disclosure. | partly resolved | Timeline table; who read what before the freeze; open-rule decision; merge status "not confirmed at the time of writing". | §6.1, Table 5, App. B.2, App. E.4 | in part: no conflict-of-interest and role statement; merge status still pending (authors' facts, see the requirements file). |
| M9 | Expert study should not be in the body. | largely resolved | One paragraph in §7; protocol in App. G; P's labeller, interface mismatch, exposure and the 1/32 floor stated. | §7 "The expert study", App. G | in part: no ethics statement (authors' fact). |
| M10 | Prior conference version not identified; manuscript too long. | partly resolved | Studies 1 and 2 moved to the supplement; Table S6 marked superseded. The article is 55 pages (22 body), the supplement 27. | Supp. S1–S7, Table S6 | in part: the conference version is not named and its delta not stated (authors' fact). |

### Round 2, new problems

| # | Problem (one line) | What the paper now does | Where | Status |
|---|---|---|---|---|
| N1 | The hypothesis order changed before the freeze, which made H3 testable; not disclosed. | Disclosed: original orders, reason, development results known at the time, and that under the earlier order only H1 and H2 would have been confirmed. | §1, §6 (opening), §6.3, App. B.2, §7 "Limits", §8 | answered |
| N2 | Two intervals for the same contrast (Table 7 against the reweighting table). | The reweighting table's caption says its intervals hold subset weights fixed and are narrower than the registered ones. | Table 23 | answered |
| N3 | Two estimates for "ordinary claims" in the body. | Family means in the body; per-claim means only in the appendix, with a note. | §6.4, Table 14, Table 23 | answered |
| N4 | Two single-prompt latencies. | One statement with the medians by regime and model. | §6.4 "Cost and time", Table 25 | answered |
| N5 | Wrong or loose pointers; the data-writer disclosure appears three times. | Pointers fixed (Supp. S3 and S4; stress test of §6.5 and App. D; Fig. 4 caption). The disclosure is shortened in §6.1 and App. B.2 points to App. E.4. | §5, App. C.2 (end), Fig. 4, §6.1, App. B.2, App. E.4 | in part: the disclosure still appears in three places. |
| N6 | Table 4 lists exact deferral as a change though Study 1 already ran it. | The row says Study 1 had evaluated it as a variant and it became the evaluation. | Table 4 | answered |
| N7 | Post-review analyses carry headline weight. | The fact table moved to §6.5; each principle says which evidence is registered. The introduction's same-model contrast on ordinary claims is labelled "not part of the plan". | §6.5, Table 11, §7, §1 | answered |
| N8 | Terminology drift (case-run, claim-run, regime, held). | Units defined once in §6.2; "regime" defined at the start of §6. | §6, §6.2 | answered |
| N9 | Post-review numbers cannot be re-checked from a clone. | `study3_review.py` is a step of `reproduce.sh`; two parts need the cache archive and are skipped without it. | App. E.2 | answered |
| N10 | Two check sizes for the theft evaluator (5,000 and 3,000). | App. B.2 says these are two different checks. | App. A, App. B.2 (last bullet) | answered |
| N11 | The design table says checklist only makes document judgments on theft. | "document judgments (tenancy only)". | Table 6 | answered |
| N12 | §6.4 too dense (17 run-in headings). | Eight run-in headings in §6.4; post-review results grouped in §6.5. | §6.4, §6.5 | answered |

Round-2 items outside M and N that remain open, all in the abstract: the gloss of "per pair" (minor 1), the mechanism sentence that omits presumptions and the plain walk (claim 2), the qualifier on the reviewed rules (M4). Minor 9 (latency against a handler's time) is answered by disclosure: "We did not measure a handler's time" (§6.4).

## Counts

| Source | Answered | In part | Not answered |
|---|---|---|---|
| CptP (10) | 6 | 4 | 0 |
| 2Kwe (5) | 1 | 4 | 0 |
| SBTv (5) | 1 | 4 | 0 |
| J01–J15 (15) | 10 | 3 | 2 |
| Round 1, M1–M10 | 4 | 6 | 0 |
| Round 2, N1–N12 | 11 | 1 | 0 |
