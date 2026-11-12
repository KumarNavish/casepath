# Review response checklist

Paper: *CasePath: Agents That Read, Rules That Decide. Requesting Evidence for Insurance Claims with Executable Workflows* (ACM TMIS draft).

## State of things

- The paper was rewritten on 12 November 2026 after an outside review (eight points) and a third internal referee round. It now has Sections 1–8 and Appendices A–D in a 31-page article. Studies 1 and 2, most robustness tables, the prompts and the full deviations moved to a 69-page supplement.
- The headline is the registered tenancy result. "Holds what the file leaves open" is claimed for tenancy only. On theft the paper says CasePath made no premature request and changed nothing else in 94% of unresolved-fact pairs, and that this measure cannot tell a hold from reading the open fact as false.
- The frontier-model theft cell reads "no advantage". The lint is "a proposed diagnostic". The full product costs about 20 (tenancy) and 42 (theft) times the same-model single prompt.
- Of the earlier criticisms below, most are done or partly done; four are open (J09, J15, and two abstract items of round 2). Several entries of the previous version of this file claimed more than the paper now says; they are lowered here.
- A check of the rewrite against the third referee report (`analysis/review/REFEREE_ROUND3_CHECK.md`) recommends minor revision and names four rewordings still wanted (section "Third referee round" below).

Pointers refer to `CasePath_TMIS.pdf` (31 pages; p. = page) and, with "Supp.", to `CasePath_TMIS_supplement.pdf` (69 pages). Both were built from the paper sources at 10:17 UTC on 12 November 2026. The abstract source was changed after that build (commit `7bfc9951`, 10:22 UTC); the delivered PDF does not contain that change. Every pointer below was checked against the delivered PDFs.

Status words: **done** (the paper does what was asked), **partly** (what is missing is named), **open** (not done; why). A status says what the current text does, not what an earlier version did, and claims nothing the paper does not say.

Sources of the criticisms. The original texts of reviewers CptP, 2Kwe and SBTv and of comments J01–J15 are not in the repository. The one-line criticisms below are the paraphrases kept from earlier versions of this file. Check them against the originals before writing the response letter. J05, J08 and J12 were merged into one paraphrase ("use topic sentences") in the earliest version; where each was raised is not recorded.

Names. The conference version's "Study A" (theft pairs) and "Study B" (tenancy claims) are Study 1 (Supp. S1). Study 2 is in Supp. S2. The article's confirmatory test is Study 3 (Section 6), on new sealed data (`fresh2/`).

## Reviewer CptP

| # | Criticism (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| W1 | Study A shows no accuracy benefit: the gates failed (Holm p = 0.797), CasePath is weaker on several conditions, and its advantage comes from baseline withdrawals. | A new pre-registered test on sealed theft data counts wrong + missed changes, so a withdrawal is an error. H1 confirmed: 0.58 against 1.74 errors per pair for the same-model single prompt (p = 0.0078). H4 failed: against Self-consistency 0.58 against 1.21, p = 0.0625. On the frontier model, CasePath (checklist only, one run) had no advantage: 0.83 against 0.95, and 0.67 with the rules before review. Study 1 is kept in full in the supplement. | §1 (p. 2), §6.2 and Table 5 (p. 12–14), §6.3 and Fig. 4 (p. 14–15); Supp. S1, S1.5 | partly. No advantage over Self-consistency on theft and none on the frontier model. H1 uses rules reviewed by AI sessions that knew the test conditions; the registered secondary contrast with the original rules (0.58 against 1.47, p = 0.0117) does not depend on that review. |
| Q1 | What accuracy claim does Study A support? | A narrow one. On theft, fewer errors than the same cost-efficient model in one prompt (registered), and than that prompt with the original rules (registered secondary). Not against Self-consistency (H4 failed). On the frontier model, no advantage. | §1 (p. 2–3), §6.2, §6.3, §7.1, §8 | done |
| W2 | Study B's 98% result follows from the design; holds were unscored; the conservative contrasts were negative; the original evaluator accepted nothing; scoring was switched post hoc. | Holds are scored: "all deviations" adds wrong and unneeded holds (0.73 against 2.33 and 2.09); held shares and unneeded holds are in Table 7. Measures and tests were fixed in the plan before the run. The paper states that the tenancy references come from the engine CasePath implements, under a silence clause the authors wrote. Added after review: two blind AI evaluators reproduced the references (1,024 of 1,024 decisions), which confirms the implementation, not the reading of the rules; under a rejected reading (A1), with the workflow unchanged, the tenancy result reverses (Table 9). | §6.1 (p. 11), §6.4 and Table 7 (p. 16–17), §6.6 and Table 9 (p. 18–20), §7.1 (p. 21) | partly. The references are still the engine's, under one reading no lawyer has checked. The delivered abstract does not name the engine; the abstract source changed after the build does. |
| Q2 | Are Study B's references made from the same templates? How accurate is the dispute-type judgment? How should holds count? | Same templates: yes for Study 1 (Supp. S1.2.2) and, for Study 3, references from the engine under the silence clause (§6.1). Holds count as deviations (§6.1, §6.4). Fact-level results for Study 3 are in Supp. Table S35. Routing errors are one stage of the error decomposition: 0.045 strict unsafe errors per claim on the cost-efficient model, 0 on the frontier model (Table 6). | §6.1, §6.4, Table 6 (p. 16); Supp. S1.2.2, Table S35 | partly. A routing accuracy for Study 3 (share of claims routed to the right workflow) is still not reported. It can be computed from stored outputs without model calls. |
| W3 | One model, one run, no prior systems; baseline prompts not shown. | Two models (cost-efficient and frontier); 3 runs per case for every design except the frontier product (one run, checklist only). Comparators: single prompt, Self-consistency (5 samples), Model executes rules (the plan's design in the style of Chain of Logic), ReAct, two-valued execution, original rules. Prompts are in the supplement. | §6.1 and Table 4 (p. 12–13); Supp. S15 | done. Chain of Logic itself and the benchmarks' agents were not run (§2, p. 4). The full product was not run on the frontier model. |
| Q3 | How many runs underlie each number? | 3 runs per design and case; the frontier checklist-only product 1. Calls and cost per case-run from the ledgers. | §6.1, Table 4 | done |
| W4 | Data are synthetic, self-authored and unreviewed; held-out inputs were exposed; temperature was unset. | Study 3 data were sealed before any design ran (timeline, Table 3). One AI agent session wrote all texts and could read the product's prompts and development results; a model of the same family checked them blind. No temperature was sent; no snapshot, temperature or seed is recorded. Run-to-run identity is reported (81% and 17% for two runs of the full product). | §6.1 and Table 3 (p. 11–12), §6.3 (p. 15), App. C (p. 29), App. D (p. 30); Supp. S10 | partly. Still synthetic and AI-written; no person, expert or jurist reviewed data or rules. Needs the deployment study (App. B). |
| Q4 | What was exposed? Was there expert review? | Disclosed: Study 1's held-out tenancy messages were visible during development; the rule editors knew the theft conditions Study 3 reuses; no jurist reviewed the rules; the expert part of the deployment study has not run. | Supp. S1.4.4, S5.1; §5 (p. 10), §6.1, §7.1, App. B, App. D | done (by disclosure) |
| W5 | Algorithm 1 was a picture; the formal definitions sat in the appendix; Figure 2 was a low-resolution raster. | Semantics in the main text as Equations (1)–(3), Propositions 3.1–3.4 and the admission rule (Table 2); proofs in App. A. The Study 1 algorithm is typeset (Supp. Algorithm S1). Figures are vector PDFs except Fig. 1, which crops screen captures of the product. | §3 (p. 4–8), Table 2, App. A (p. 26); Supp. S1.1 | done |
| W6 | The related work was two paragraphs; the bibliography was inconsistent. | A related-work section of nine run-in paragraphs, each saying what CasePath does differently, and a comparison table. One ACM style. BibTeX prints 28 warnings for the article (16 empty address, 7 empty publisher, 5 missing pages) and 12 for the supplement. Swiss supervisory guidance is not cited. | §2 and Table 1 (p. 3–5) | done. The BibTeX warnings are cosmetic and remain. |

## Reviewer 2Kwe

| # | Criticism (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| W1/Q1 | Technical novelty over neuro-symbolic and process-aware methods is unclear. | Each related-work paragraph names what CasePath does differently. The paper says the semantics are not new: "what is new is the application and the reconvergence case of Proposition 3.2, not the semantics". Table 1 compares systems on four properties. | §2 (p. 3–4), Table 1 (p. 5), Prop. 3.2 and Fig. 2 (p. 6–7) | done |
| W2 | Generality is limited; the studies test different parts; no comparison with existing agents. | One product, one workflow format and one set of measures on both data sets. ReAct, a tool-using agent, is compared. | §4.2 (p. 9), §6.1, Table 4 | partly. Two synthetic domains under Swiss law, texts of 77–320 words; long-file paths never ran (§6.1, §7.1). Needs other domains or real files. |
| Q2 | How are extracted rules validated? Can errors be found without manual work? | Study 2's label-free check and repair of the rules did not lower errors. The theft rules of Study 3 were reviewed by two AI editor sessions (9 changed, 14 queued for a jurist); no jurist has reviewed them. Added after review: a lint, "a proposed diagnostic", flags over-broad conditions without reference answers, but flags most conditions (14 and 12 on theft; 8 and 9 of 10 on tenancy), its false-alarm rate is unknown, and treating flagged conditions as open did not help out of sample. | §5 (p. 9–10), §6.7 (p. 19–20), §7.1 | partly. The answer the paper gives is "not without review"; the jurist review has not happened. The previous version of this file presented the lint as a finding; the paper now presents it as a proposed diagnostic only. |
| Q3 | Why custom baselines instead of adapted prior methods? | ReAct and Self-consistency run over the same workflow and files; Model executes rules states the semantics in the prompt, in the style of Chain of Logic. The paper names the published designs it does not run. | §2 "Agents that apply the rules" (p. 3–4), Table 4; Supp. S15.3 | partly. The paper does not say why Chain of Logic itself and the benchmarks' agents were not run. One sentence would close it. |
| Q4 | Why different datasets for different aspects? | Study 3 has two data sets, each with its own workflow and measures: theft scores the change between two texts that differ in one fact; tenancy scores the whole checklist. | §6 opening (p. 11), §6.1 | partly. The reason for two data sets is not stated in one place. |

## Reviewer SBTv

| # | Criticism (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| W1 | The architecture is standard (neuro-symbolic, DMN, BPMN), and the process definition is ad hoc across studies. | Positioned against rules as code, DMN, Catala, neuro-symbolic systems, case management and declarative or artifact-centric process models. One workflow format serves both data sets; all four tested workflows are flow workflows, checked with the product's own walk. | §2, Table 1, §3.1, §3.3 (p. 6), §4.2 and Listing 1 (p. 9), App. A; Supp. S15.5 | done |
| W2 | No formal problem definition and no objective. | §3 defines workflows, assignments, completions, evaluation (Eqs. 1–2), exact deferral (Eq. 3) and unsafe errors, with four propositions. Route choice is a fixed rule ("cheapest route", Supp. S15.5); its minimisation is discussed for the Study 1 configuration only (Supp. S1.1). | §3.1–§3.5 (p. 4–8); Supp. S1.1, S15.5 | partly. No objective function is stated in §3. |
| W3 | Algorithm 1 is a schematic without types or complexity; the logic is trivial. | The semantics are equations. Cost: one evaluation per completion; above eight open facts or 256 combinations the product uses the plain walk. Prop. 3.2 shows strong Kleene evaluation over-holds where branches meet again. A complexity paragraph (linear evaluation; coNP-completeness of truth under all completions in general) is in the supplement, for the Study 1 configuration. | §3.3, §3.4 (p. 7–8), Fig. 2, App. A; Supp. S1.1 "Complexity" | partly. The article itself states no complexity result. |
| W4 | Synthetic data, no experts, circular evaluation. | Circularity stated (§6.1, §7.1). Added after review: clean-room re-derivation (confirms the implementation, not the reading) and sensitivity to four rejected readings (Table 9). Stress test of presumptions (Supp. S13.2). Expert study only as a protocol (App. B). | §6.1, §6.6, Table 9, §7.1, App. B; Supp. S13.2 | partly. Still synthetic; the deployment study has not run; the tenancy references are the engine's own, under one reading. |
| W5 | Narrow scope and weak baselines; no neuro-symbolic, ReAct or DMN comparison. | ReAct run (H4 component: 0.58 against 1.69, p = 0.0117). Two-valued execution of CasePath's own readings stands for closed-world rule engines (1.27 and 1.51 strict unsafe errors per claim, against 0.31). Self-consistency and Model executes rules added. | Table 4, Table 5 (p. 14), §6.4 (p. 16) | partly. No system in which the model writes the logic (Logic-LM style) was run; scope is two synthetic Swiss domains. |

## Comments J01–J15

| ID | Comment (paraphrase) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| J01 | State the RQ and its rationale before the contributions. | The introduction states the problem ("deciding which evidence to request while the file leaves deciding facts open"), why it matters and the design-science framing before the contributions. | §1, paragraphs 1–2 (p. 1) | partly. No explicit research-question sentence. |
| J02 | Expand related work with a summary table showing how ours differs. | Nine paragraphs, each with how CasePath differs, and Table 1. | §2, Table 1 | done |
| J03 | Separate the insurance background from how the model works. | §3 is the decision rule, §4 the product. The insurance background is the running example (§1) and one sentence on claims handling (§2). | §1, §2, §3, §4 | partly. No dedicated background on legal-protection claims handling. |
| J04 | Say what each study is meant to achieve. | §5 frames Studies 1–3 as cycle 1 (the core, on synthetic data) and the deployment as cycle 2; §6.2 states five ordered hypotheses. | §5 (p. 9–11), §6.2 | done |
| J05 | Use topic sentences. | Each subsection of §6 opens with its finding (for example §6.2 "Three of five hypotheses were confirmed, one failed and one was not tested"); each principle in §7 is headed by its statement. | §6.2–§6.7, §7 | done |
| J06 | Relate the methods to the literature to give a red thread. | §2 ties each line of work to what CasePath does and says which published designs Section 6 tests. | §2, Table 1, Table 4 | done |
| J07 | A table of methods × elements. | Systems × four properties (Table 1); designs × calls, cost and cost ratios (Table 4); pipeline steps × what they read and may change (Supp. Table S14). | Table 1, Table 4; Supp. Table S14 | done |
| J08 | Use topic sentences. | As J05. | §6, §7 | done |
| J09 | A table of terms. | Terms are defined in the text (§3.1–§3.5; strict unsafe errors and case-run, claim-run, text-run and pair-run in §6.1). No glossary table in the article or supplement. | §3, §6.1 | open. The glossary of an earlier version was dropped. |
| J10 | Since CasePath still errs, what should humans monitor? | Who writes workflows and presumptions and has them reviewed; what an auditor gets (each value with its quotation, each hold with its question, the code hash); what a hold costs a handler. Disagreeing readings are marked for a person; a second routing contradiction hands the claim to a person. | §7 "For an organisation" (p. 21), Table 2, §4.1 (p. 8) | partly. No evidence on human oversight; the deployment study has not run. |
| J11 | Managerial guidance on when to use which design. | Three design principles, each with its evidence and boundary condition, and a paragraph for an organisation. The old guidance table is in the supplement, marked superseded. | §7 (p. 20–21); Supp. Table S6 | done |
| J12 | Use topic sentences. | As J05. | §6, §7 | done |
| J13 | Where should a human step in (unresolved dispute type)? | Several candidate workflows, or a second contradiction between routing and admitted facts, hand the claim to a person; disagreeing readings are marked for a person. | §4.1, Table 2; Supp. S9.1 | done |
| J14 | Method statements do not belong in the results. | Data, designs and measures are in §6.1. §6.2 still explains the H4 test (exact sign flip, smallest attainable p). | §6.1, §6.2 | done |
| J15 | Start the discussion with a recap. | §7 opens with Principle 1, not a recap. The recap is in §8. | §7, §8 | open. Needs two or three sentences at the start of §7. |

## Internal referee rounds 1 and 2

Reports: `analysis/review/REFEREE_REVIEW.md` (round 1, major revision, M1–M10) and `analysis/review/REFEREE_REVIEW_ROUND2.md` (round 2, minor revision, N1–N12). Both reviewed the 55-page version of 11 November. Pointers below are to the current PDFs.

### Round 1, major concerns

| # | Concern (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| M1 | Contribution and IS positioning unclear; two of four contributions are not results; missing related work. | Problem class and design-science framing on p. 1; three contributions (decision rule; artefact and design knowledge; pre-registered evaluation with checks added after review); principles with boundaries. | §1 (p. 1–3), §2, Table 1, §7 | partly. The Swiss supervisory guidance is not cited (it could not be verified from an official page; `analysis/REFERENCES_ADDED.md`). |
| M2 | Tenancy references are circular; data aligned with the design. | Stated in §6.1 and §7.1. Clean room and sensitivity added after review (§6.6, Table 9). The test set "was designed to include the denied- and open-event claims" (§6.1). | §6.1, §6.6, Table 9, §7.1 | partly. The previous version of this file said "answered". The references remain the engine's, and most of the tenancy lead rests on one reading of the rule text that no lawyer has checked. |
| M3 | Tenancy effect sits in 33 designed gating claims; the unit amplifies them. | §6.2 states that the effect sits in the 9 families that contain denied- or open-event claims and that the other 15 families show small, mixed differences. Added after review: on the 56 claims with an open fact or a denied or open defining event, 0.40 against 3.39 and 3.06; on the 40 claims that state every fact, 0.19 against 0.39 and 0.19, no advantage (Table 8, Fig. 5). | §6.2 (p. 13), §6.4, Table 8, Fig. 5 (p. 16–18); Supp. Fig. S6, Table S26 | done |
| M4 | Unequal development effort; reviewed rules favour execution. | One-sided effort stated. The rule review made both single prompts worse (1.47 → 1.74; 0.67 → 0.95), only 11% and 27% of that change on documents a changed rule names; H1, H4 and H5 use the reviewed rules; CasePath with the original rules was not run; the best single-prompt theft result (0.67) came with the original rules. | §6.1 (p. 11), §6.2, §7.1 | partly. Done in the body; the delivered abstract says "rule reviews were made by AI sessions" but not that they knew the test conditions. |
| M5 | Formal statements lack their scope; the system does not meet their premises. | Scope in each proposition; admission as Table 2; related facts acknowledged; plain walk on theft stated; document presence declared a model judgment. | §3, Table 2, App. A | done |
| M6 | Inference with 9 clusters; dependence the clustering ignores. | Exact sign-flip tests; inverted interval for H4 (−1.25 to 0.08); stories as clusters (p = 0.0156); captions say the percentile intervals under-cover with nine theft clusters. | §6.2, Table 5, Fig. 4; Supp. Table S24 | done |
| M7 | Checklist-only comparison and cost split do not support "later agents changed nothing". | "No detectable difference"; identical checklists 93% and 59%, against 81% and 17% for two runs of the full product; "the shared cache narrows the comparison". | §4.1 (p. 8–9), §6.3 (p. 15); Supp. Table S21 | done |
| M8 | Freeze integrity and test-data independence need fuller disclosure. | Timeline table; who read what before the freeze; open-rule decision; merge status "not confirmed at the time of writing". | §6.1, Table 3 (p. 12), App. C | partly. No conflict-of-interest and role statement yet; merge status pending (authors' facts). |
| M9 | Expert study should not be in the body. | The deployment study is one paragraph in §5 and the protocol in App. B (at most 900 words); no result is reported. | §5 (p. 11), App. B (p. 27–29) | partly. No ethics statement yet (authors' fact). |
| M10 | Prior conference version not identified; manuscript too long. | The article is 31 pages (body p. 1–22), the supplement 69. | — | partly. The conference version is not named and its delta not stated (authors' fact). |

### Round 2, new problems

| # | Problem (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| N1 | The hypothesis order changed before the freeze, which made H3 testable; not disclosed. | Disclosed with times and the reason. Table 5 shows the outcome under the order of 21:26 (H3 not tested) and under the first draft's order. | §1 (p. 2), §6.2 and Table 5 (p. 13–14), Table 3, §7.1, App. C | done |
| N2 | Two intervals for the same contrast. | The reweighting table moved to the supplement; its caption says its intervals hold subset weights fixed and are narrower than the registered ones. | Supp. Table S26 | done |
| N3 | Two estimates for "ordinary claims" in the body. | §6.2 gives family means and points to Supp. Table S17 for per-claim values. §6.4 and Table 8 use claim-run means for the added-after-review split and say so. | §6.2, §6.4, Table 8; Supp. Table S17 | done |
| N4 | Two single-prompt latencies. | One statement with medians, marked as lower bounds. | §6.5 (p. 17–18) | done |
| N5 | Wrong or loose pointers; the data-writer disclosure appears three times. | Pointers into the supplement read "Supplement, Section …". The data-writer disclosure appears in §6.1, App. C and App. D. | §6.1, App. C, App. D | partly. The disclosure still appears in three places. |
| N6 | Table 4 listed exact deferral as a change though Study 1 already ran it. | The root-cause table is in the supplement. | Supp. S8, Table S13 | done |
| N7 | Post-review analyses carry headline weight. | The headline is the registered result. Every analysis added after review is marked with a dagger in §6; its p values are "descriptive and not corrected for multiplicity". The abstract, introduction and conclusion label numbers "registered", "registered secondary" or "added after review". | §1, §6 opening (p. 11), §8 | done |
| N8 | Terminology drift (case-run, claim-run, regime, held). | Units defined once in §6.1; "regime" is no longer used. | §6.1 | done |
| N9 | Post-review numbers cannot be re-checked from a clone. | `reproduce.sh` re-runs the analyses added after review; the parts that read the product's response cache are skipped without the cache archive. | App. D (p. 30–31); Supp. S16.2 | done |
| N10 | Two check sizes for the theft evaluator (5,000 and 3,000). | The supplement says these are two different checks. | Supp. S10, S11.2 | done |
| N11 | The design table said checklist only makes document judgments on theft. | §6.1: the checklist-only setting skips the document finder for a claim of one file; every theft text is such a claim. | §6.1 (p. 12) | done |
| N12 | §6.4 too dense. | Section 6 now has seven subsections, each opening with its finding. | §6.1–§6.7 | done |

Round-2 items outside M and N that concerned the abstract: the gloss of "per pair" (open: the abstract still says "errors per pair" without a gloss), the mechanism sentence that omits presumptions and the plain walk (open: unchanged), and the qualifier on the reviewed rules (partly: see M4 above). Minor 9 (latency against a handler's time) is answered by disclosure: "We did not measure a handler's time" (§6.5).

## Outside feedback of 12 November 2026 (eight points)

The feedback text itself is not in the repository. The asks below are as `WORKLOG.md` (entry of 2026-11-12) lists them; it lists nine asks for the eight points, and only point 3 is identified by number in the reply (`expert_study/REQUEST_TO_PRODUCT_20261112.md`). All analyses made in answer are added after review and labelled so; the registered results did not change.

| Ask | What the paper now does | Where | Status |
|---|---|---|---|
| A different headline: "holds", not "wins" | The registered tenancy result leads. "Holds" is claimed for tenancy only (97% of reference-held documents held, against 48% and 35%). "Wins on the mean" became "lower mean error". After the third referee round the open-or-stated split no longer leads; it follows as "added after review". | Abstract, §1 (p. 1–2), §6.4 | done |
| All four cells of model × data set, with an error decomposition | Fig. 4 shows all four cells. The frontier theft cell reads "no advantage" (0.83 against 0.95, and 0.67 with the original rules). Table 6 splits CasePath's errors by stage; the parts add up exactly. | §6.3, Fig. 4, Table 6 (p. 14–16) | done |
| Real-file evidence that needs no experts (point 3) | The protocol's primary endpoint is now an archival comparison with what the insurer did next at every decision point of four sealed files. No result yet. | §5 (p. 11), App. B (p. 27–29) | partly: designed, not run |
| An answer to the circularity objection | Two blind AI evaluators reproduced the references (1,024 of 1,024). This "confirms the implementation of the catalogue", not the reading. Under reading A1 with the workflow unchanged the tenancy result reverses; with the workflow amended, a smaller lead remains, resting on the 9 open-event claims. | §6.6, Table 9 (p. 18–20), §7.1 | partly: the reading itself needs a lawyer |
| Open repair of the statistics | Table 5 adds the outcome under each order and under Holm (not registered). The H4 test is stated exactly (smallest attainable p 0.0039; returned 0.0625; 7 of 9 clusters favoured CasePath). | §6.2, Table 5 | done |
| The lint as a tested contribution | Tested (mutation test, flagged-as-open re-score in and out of sample), but not claimed as a contribution: the paper calls it "a proposed diagnostic", gives its flag counts, and says its remedy failed out of sample. | §4.2 (one sentence), §6.7 (p. 19–20), §7.1 | partly: tested, not adopted as a contribution |
| Budget-matched comparisons | Self-consistency with 1 to 15 samples against CasePath, checklist only, with 1 to 3 readings. At matched cost: −1.76 strict unsafe errors per claim (p = 0.0006) and −0.53 errors per pair (p = 0.1328, not significant). | §6.5, Fig. 6 (p. 17–19) | done |
| The tested commit as the artefact | "The artefact of this article is the tested commit, 6a72159c (source-tree hash 03048020…)". Its DOI is an open `%% AUTHORS:` item. | §4 (p. 8) | partly: DOI not deposited |
| A cut to about 35 pages | 31 pages; Studies 1 and 2 and most tables moved to the supplement. | — | done |

The reply also corrected two readings of the earlier paper: the frontier theft cell was printed, not omitted ("not shown" is now "no advantage"), and p = 0.0625 comes from an exact sign-flip test over nine clusters, not a signed-rank test. Both are carried through.

## Third referee round (12 November 2026)

Report: `analysis/review/REFEREE_REVIEW_ROUND3.md` (major revision; 10 major and 23 minor concerns). Fixes: `FIX_BRIEF_ROUND3.md`. Check of the rewrite against the report: `analysis/review/REFEREE_ROUND3_CHECK.md` (8 major closed, 2 partly; 20 minor closed, 3 partly; recommendation minor revision). The statuses below follow that check and the delivered PDF.

| # | Concern (short) | How it was closed | Status |
|---|---|---|---|
| M1 | H4 paragraph false; wrong reason for p | §6.2 now: fewer errors on 7 of 9 changed conditions, more on 2 (by 0.13 and 1.00); 32 of 512 sign patterns as extreme. | done |
| M2 | Headline led with a post hoc subset, mislabelled | Abstract and §1 lead with registered H2/H3 and the 97% holding result; the split follows, labelled, as claim-run means (0.40 against 3.39 and 3.06) in text, Table 8 and Fig. 5; §6.2 names the 9 families. | done |
| M3 | Theft "holding" evidence does not show holding | "Holds" restricted to tenancy; §6.4 says the theft measure cannot tell a hold from reading the open fact as false and reports the open condition's documents held (83, 85, 85, 90%). | done |
| M4 | Frontier theft cell attributed to the rules | Registered secondary S7c reported (0.83 against 0.58, p = 0.0781); rule part given as 0.33 with range 0.22–0.44; §6.7 retitled "Theft on the frontier model". | done |
| M5 | Reviewed rules confound theft comparisons | §6.1 and §7.1 state who reviewed and what it did; S4c beside H1 (p = 0.0117); frontier exact superiority p = 0.6367; bootstrap share called uncalibrated. | done |
| M6 | Reading sensitivity presented too strongly | §6.6 and Table 9: catalogue in the clean room, references not independent, 6 of 10 contrasts reverse under all four readings, A2/A4 from unchanged rows; §7.1 names the one interpretive choice. | partly: the conclusion's "without the reading that a denied defining event ends the process" is false for the amended workflow (check, D1) |
| M7 | Cost understated | Table 4 has ratio columns; §6.5 gives 19.8 and 41.8 times the same-model prompt and 2.1 and 7.4 times the frontier prompt; times marked as lower bounds. | done |
| M8 | Lint presented as a finding and contribution | Removed from the contributions; "a proposed diagnostic" in §6.7 with flag counts, the analyst who planted the mutations, and the out-of-sample failure. | done |
| M9 | Labelling and multiplicity | Dagger convention in §6; post hoc p values "descriptive and not corrected for multiplicity"; abstract, introduction and conclusion labelled. | done |
| M10 | Abstract omits limits | Delivered abstract adds AI-made texts, references and reviews, no jurist, and the reorder. | partly: the engine-made references and the theft reuse are missing from the delivered abstract; the abstract source changed after the build adds both |

Minor concerns still partly closed, per the check: 8 (§3.5 says the few wrong values "caused most of CasePath's tenancy errors"; the check computes about half), 11 (provenance of the eleven hackathon dossiers; now an `%% AUTHORS:` question and question 7 to the product's builders), 16 (the Fig. 5 sentence on real files; see D2 below). The other 20 are closed.

The check also lists problems the rewrite introduced. Four are wording it wants fixed before acceptance:

| Item | Sentence in the delivered PDF | What the sources support |
|---|---|---|
| D1 | §8: the lead stops "without the reading that a denied defining event ends the process" | With the workflow amended to that reading, the lead stays significant but smaller (−0.66, p = 0.0002; −1.00, p = 0.0014; Table 9). |
| D2 | §6.4: "Real files with open facts but few denied events would lie nearer the left." | Such files are in the right-hand group; what changes is the height of that end (open-branch-fact claims: CasePath 0.23, Rules in context 0.51). |
| D3 | "Most of the tenancy lead rests on our reading …" (abstract, §1, §6.6, §7.1) | Denied-event claims carry about two thirds of the lead against either prompt (about 69% and 62%). The abstract source changed after the build says "about two thirds". |
| D4 | §3.5: the few wrong values "caused most of CasePath's tenancy errors" | About 49%, by the decomposition. |

Smaller wording items D5–D10 are in the check file.

## Counts

| Source | Done | Partly | Open |
|---|---|---|---|
| CptP (10) | 6 | 4 | 0 |
| 2Kwe (5) | 1 | 4 | 0 |
| SBTv (5) | 1 | 4 | 0 |
| J01–J15 (15) | 10 | 3 | 2 |
| Round 1, M1–M10 | 4 | 6 | 0 |
| Round 2, N1–N12 | 11 | 1 | 0 |
| Outside feedback (9 asks) | 5 | 4 | 0 |
| Round 3, M1–M10 | 8 | 2 | 0 |
| Round 3, minor 1–23 | 20 | 3 | 0 |

Changes of status against the previous version of this file: round 1 M2 was lowered from answered to partly (the reading of the rules is now known to carry most of the lead); round 1 M3 rose from in part to done; CptP Q1 is done with a narrower claim than before (the frontier theft cell is "no advantage", not "not shown"). Entries whose text claimed more than the paper now says were lowered in wording: 2Kwe Q2 (the lint is a proposed diagnostic, not evidence that rules can be validated without review), CptP W2 (the clean room confirms the implementation, not the reading), and every cost statement (20 to 42 times the same-model prompt, not "several times").
