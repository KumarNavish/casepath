# Review response checklist

Paper: *CasePath: Agents That Read, Rules That Decide. Requesting Evidence for Insurance Claims with Executable Workflows* (ACM TMIS draft).

## State of things

- The paper now has a 29-page article with Sections 1–9 and Appendices A–C (proofs; deviations and irregularities of Study 3; reproducibility and use of generative AI), and a 74-page supplement. Section 7 (a benchmark from public rules, development material) was added on 12 November; the Discussion and its Scope subsection are now §8 and §8.1, the supplement's prompts and reproducibility sections S17 and S18, and page pointers after p. 18 have moved by about two pages.
- The deployment study and the insurer's dossiers are no longer in the paper, by the owner's direction. The paper's last sentence says "A study on an insurer's real files is planned as separate work". The protocol stays in `expert_study/` as separate follow-up work. Every criticism that earlier relied on that study is now answered only as far as the paper's own evidence goes.
- Every limitation is stated once, in Section 7.1 "Scope", and nowhere else. The abstract no longer lists limits.
- A check added after the test changes the reading of the tenancy result. A single prompt told the same stop and hold rules matched CasePath on tenancy overall (0.35 strict unsafe errors per claim against 0.31) and did better on denied defining events. The abstract says: "The registered tenancy result therefore measures mostly what the prompt was told." CasePath kept a lead where a fact is tentatively worded, where a supplied document is insufficient, and on theft.
- Counts are at the end. Statuses that went down in this refresh are listed with their reasons in the last section.

Pointers refer to `CasePath_TMIS.pdf` (27 pages; p. = page) and, with "Supp.", to `CasePath_TMIS_supplement.pdf` (68 pages). Both were built from the paper sources at commit `17497000` (12 November 2026, 12:45 UTC). Every pointer below was checked against these PDFs.

Status words: **done** (the paper does what was asked), **partly** (what is missing is named), **open** (not done; why). A status says what the current text does, not what an earlier version did, and claims nothing the paper does not say.

Sources of the criticisms. The original texts of reviewers CptP, 2Kwe and SBTv and of comments J01–J15 are not in the repository. The one-line criticisms below are the paraphrases kept from earlier versions of this file. Check them against the originals before writing the response letter. J05, J08 and J12 were merged into one paraphrase ("use topic sentences") in the earliest version; where each was raised is not recorded.

Names. The conference version's "Study A" (theft pairs) and "Study B" (tenancy claims) are Study 1 (Supp. S1). Study 2 is in Supp. S2. The article's confirmatory test is Study 3 (Section 6), on new sealed data (`fresh2/`).

## Reviewer CptP

| # | Criticism (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| W1 | Study A shows no accuracy benefit: the gates failed (Holm p = 0.797), CasePath is weaker on several conditions, and its advantage comes from baseline withdrawals. | A new pre-registered test on sealed theft data counts wrong + missed changes, so a withdrawal is an error. H1 confirmed: 0.58 against 1.74 errors per pair (p = 0.0078). H4 failed: against Self-consistency 0.58 against 1.21, p = 0.0625. Added after the test: a prompt with a hold option made 1.68 on theft (p = 0.0078 over the nine clusters). On the frontier model CasePath had no theft advantage (0.83 against 0.95, and 0.67 with the rules before review). Study 1 is kept in the supplement. | §1 (p. 2), §6.2 and Table 5 (p. 11–12), §6.3 and Table 6 (p. 12–13), §6.6 and Table 8 (p. 15–17); Supp. S1, S1.5 | partly. No advantage over Self-consistency on theft and none on the frontier model. H1 uses rules reviewed by AI sessions that knew the reused conditions; the registered secondary contrast with the original rules (0.58 against 1.47, p = 0.0117) does not depend on that review. |
| Q1 | What accuracy claim does Study A support? | A narrow one. On theft, fewer errors than the same cost-efficient model in one prompt (registered), than that prompt with the original rules (registered secondary), and than a prompt with a hold option (added after the test). Not against Self-consistency (H4 failed). On the frontier model, no advantage. | §1 (p. 2), §6.2, §6.3, §6.6, §8 | done |
| W2 | Study B's 98% result follows from the design; holds were unscored; the conservative contrasts were negative; the original evaluator accepted nothing; scoring was switched post hoc. | Holds are scored: "all deviations" adds wrong and unneeded holds, "so that no design gains by holding" (Table 6). Measures and tests were fixed in the plan. The tenancy references come from the engine CasePath implements (§6.1, §8.1). Added after the test: a prompt told the stop and hold rules matched CasePath overall; the paper says the registered tenancy result "measures mostly what the prompt was told". The clean room confirms the implementation, not the reading; under reading A1 with the workflow unchanged the tenancy result reverses. | Abstract, §6.1 (p. 10), §6.3, Table 6 (p. 13), §6.6 and Table 8 (p. 15–17), §6.7 and Table 9 (p. 17–18), §8.1 (p. 19) | partly. The paper now concedes most of the reviewer's point for tenancy. What remains claimed is narrower: fewer wrong holds, document checks, and stability when one sentence changes. The references are still the engine's, under one reading no lawyer has checked. |
| Q2 | Are Study B's references made from the same templates? How accurate is the dispute-type judgment? How should holds count? | Same templates: yes for Study 1 (Supp. S1.2.2); for Study 3 the references come from the engine and each claim's designed fact states (§6.1). Holds count in all deviations (Table 6). Routing errors are one stage of the decomposition: 0.045 strict unsafe errors per claim on the cost-efficient model, 0 on the frontier model (Table 7). Fact-level results: Supp. Table S35. | §6.1, Table 6, Table 7 (p. 15); Supp. S1.2.2, Table S35 | partly. A routing accuracy for Study 3 (share routed to the right workflow) is not reported. It can be computed from stored outputs without model calls. |
| W3 | One model, one run, no prior systems; baseline prompts not shown. | Two models; 3 runs per case for every design except the frontier product (one run) and, added after the test, the frontier prompt with hold option and frontier Model executes rules (one run each). Comparators: single prompt, Self-consistency, Model executes rules (the plan's design in the style of Chain of Logic), ReAct, two-valued execution, original rules, prompt with hold option. Prompts in the supplement. | §6.1 and Table 4 (p. 10–11), §6.6; Supp. S17.3, S15 | done. Chain of Logic itself and the benchmarks' agents were not run (§2, p. 3). The full product was not run on the frontier model. |
| Q3 | How many runs underlie each number? | As in W3. Calls and cost per case-run from the ledgers. | §6.1, Table 4 | done |
| W4 | Data are synthetic, self-authored and unreviewed; held-out inputs were exposed; temperature was unset. | Study 3 data were sealed before any design ran (Table 3). One AI agent session wrote all texts and could read the product's prompts; a model of the same family checked them. No temperature was sent; no snapshot, temperature or seed is recorded. | §6.1 and Table 3 (p. 10), §8.1 (p. 19), App. B (p. 25–27), App. C (p. 27); Supp. S10 | partly. Still synthetic and AI-written; no person, expert or jurist reviewed data or rules. A study on real files is separate follow-up work, not part of this paper. |
| Q4 | What was exposed? Was there expert review? | Disclosed: Study 1's held-out tenancy messages were visible during development; the theft rules were reviewed by AI sessions that knew the reused conditions, without a jurist; no expert review. | Supp. S1.4.4, S5.1; §5 (p. 9), §8.1, App. B, App. C | done (by disclosure) |
| W5 | Algorithm 1 was a picture; the formal definitions sat in the appendix; Figure 2 was a low-resolution raster. | Equations (1)–(3), Propositions 3.1–3.4 and the admission rule (Table 2) are in the main text; proofs in App. A. The Study 1 algorithm is typeset (Supp. Algorithm S1). Fig. 1 crops product screen captures and typesets the checklist from stored results; the other figures are vector PDFs. | §3 (p. 4–8), Table 2 (p. 5), App. A (p. 23); Supp. S1.1 | done |
| W6 | The related work was two paragraphs; the bibliography was inconsistent. | A related-work section of eight run-in paragraphs, each saying what CasePath does differently, and a comparison table. One ACM style. Swiss supervisory guidance is not cited. | §2 and Table 1 (p. 3–4) | done. BibTeX still warns of missing addresses, publishers or pages in some entries (cosmetic). |

## Reviewer 2Kwe

| # | Criticism (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| W1/Q1 | Technical novelty over neuro-symbolic and process-aware methods is unclear. | Each related-work paragraph names what CasePath does differently; "what is new is the application and the reconvergence case of Proposition 3.2, not the semantics". Table 1 compares systems on four properties. | §2 (p. 3–4), Table 1 (p. 4), Prop. 3.2 and Fig. 2 (p. 6–7) | done |
| W2 | Generality is limited; the studies test different parts; no comparison with existing agents. | One artefact, one workflow format and one set of measures on both data sets. ReAct is compared. | §4 (p. 8–9), §6.1, Table 4 | partly. Two synthetic domains, texts of 77–320 words (§8.1). Three rule sets written from public text and a file generator exist in the repository (`study4/`) as development material; nothing from them is in the paper. |
| Q2 | How are extracted rules validated? Can errors be found without manual work? | Study 2's label-free repair did not lower errors. The theft rules were reviewed by two AI editor sessions (9 changed, 14 queued for a jurist), without a jurist. A lint is proposed as a diagnostic: it flags most conditions (14 and 12 on theft; 8 and 9 of 10 on tenancy), was tested only against blunt widening, and treating flagged conditions as open did not help out of sample. | §5 (p. 9), §6.8 (p. 18), §8.1 | partly. The answer the paper gives is "not without review"; no jurist review has happened. |
| Q3 | Why custom baselines instead of adapted prior methods? | ReAct and Self-consistency run over the same workflow and files; Model executes rules is in the style of Chain of Logic. The paper names the published designs it does not run. Added after the test: a prompt with a hold option. | §2 "Agents that apply the rules" (p. 3), Table 4, §6.6; Supp. S17.3 | partly. The paper does not say why Chain of Logic itself and the benchmarks' agents were not run. |
| Q4 | Why different datasets for different aspects? | Study 3 has two data sets, each with its own workflow and measures. | §6 opening (p. 9), §6.1 | partly. The reason for two data sets is not stated in one place. |

## Reviewer SBTv

| # | Criticism (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| W1 | The architecture is standard (neuro-symbolic, DMN, BPMN), and the process definition is ad hoc across studies. | Positioned against rules as code, DMN, Catala, neuro-symbolic systems, case management and declarative or artifact-centric process models. One workflow format; the tested workflows are flow workflows, checked with the product's own walk. | §2, Table 1, §3.1, §3.3 (p. 5–6), §4.2 and Listing 1 (p. 9), App. A; Supp. S17.5 | done |
| W2 | No formal problem definition and no objective. | §3 defines workflows, assignments, completions, evaluation (Eqs. 1–2), exact deferral (Eq. 3) and unsafe errors, with four propositions. Route choice is a fixed rule (Supp. S17.5); its minimisation is discussed for the Study 1 configuration only (Supp. S1.1). | §3.1–§3.5 (p. 5–8); Supp. S1.1, S17.5 | partly. No objective function in §3. |
| W3 | Algorithm 1 is a schematic without types or complexity; the logic is trivial. | Equations, not pseudocode. Cost: one evaluation per completion; above eight open facts or 256 combinations the product uses the plain walk. Prop. 3.2 shows strong Kleene evaluation over-holds where branches meet again. A complexity paragraph is in the supplement, for the Study 1 configuration. | §3.3, §3.4 (p. 6–8), Fig. 2, App. A; Supp. S1.1 "Complexity" | partly. The article states no complexity result. |
| W4 | Synthetic data, no experts, circular evaluation. | Circularity stated (§6.1, §8.1). Added after the test: clean room (confirms the implementation, not the reading), sensitivity to four rejected readings (Table 9), and a prompt told the stop and hold rules (Table 8). Wrong presumptions only simulated (Supp. Table S27). | §6.1, §6.6, §6.7, Tables 8–9, §8.1; Supp. Table S27 | partly. Still synthetic; no expert or real-file result; the references are the engine's, under one reading. A real-file study is separate follow-up work and is not counted here. |
| W5 | Narrow scope and weak baselines; no neuro-symbolic, ReAct or DMN comparison. | ReAct run (0.58 against 1.69, p = 0.0117). Two-valued execution of CasePath's own readings stands for closed-world rule engines (1.27 and 1.51 against 0.31). Self-consistency, Model executes rules and, after the test, a prompt with a hold option. | Table 5 (p. 12), Table 6, §6.4, §6.6 | partly. No system in which the model writes the logic was run. |

## Comments J01–J15

| ID | Comment (paraphrase) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| J01 | State the RQ and its rationale before the contributions. | The introduction states the problem class and the design-science framing before the contributions. | §1, paragraphs 1–2 (p. 1) | partly. No explicit research-question sentence. |
| J02 | Expand related work with a summary table. | Eight paragraphs and Table 1. | §2, Table 1 | done |
| J03 | Separate the insurance background from how the model works. | §3 is the decision rule, §4 the artefact. The insurance background is the running example and one sentence in §2. | §1–§4 | partly. No dedicated background on legal-protection claims handling. |
| J04 | Say what each study is meant to achieve. | §5 describes one design cycle with three pre-registered studies; §6.2 states five ordered hypotheses; §6.6 says what the post-test check adds. | §5 (p. 9), §6.2, §6.6 | done |
| J05 | Use topic sentences. | Each subsection of §6 opens with its finding; each principle in §8 is headed by its statement. | §6.2–§6.8, §8 | done |
| J06 | Relate the methods to the literature. | §2 ties each line of work to CasePath and says which published designs §6 tests. | §2, Table 1, Table 4 | done |
| J07 | A table of methods × elements. | Systems × four properties (Table 1); designs × calls, cost and cost ratios (Table 4); designs × cells (Table 6); pipeline steps × what they may change (Supp. Table S14). | Tables 1, 4, 6; Supp. Table S14 | done |
| J08 | Use topic sentences. | As J05. | §6, §8 | done |
| J09 | A table of terms. | Terms are defined in the text (§3; units and the five kinds of strict unsafe error in §6.1). No glossary table. | §3, §6.1 | open |
| J10 | Since CasePath still errs, what should humans monitor? | Who writes and reviews workflows and presumptions; what an auditor gets; what a hold costs a handler. Disagreeing readings are marked for a person; no or several workflows, or a second routing contradiction, hand the claim to a person. | §8 "For an organisation" (p. 19), Table 2, §4.1 (p. 8) | partly. No evidence on human oversight in the paper; a study with handlers is separate follow-up work. |
| J11 | Managerial guidance on when to use which design. | Three design principles, each with its evidence; Principle 1 now says stating the stop and hold rules closed the defining-event gap "in a prompt as well as in code". A paragraph for an organisation. The old guidance table is in the supplement, marked superseded. | §8 (p. 18–19); Supp. Table S6 | done |
| J12 | Use topic sentences. | As J05. | §6, §8 | done |
| J13 | Where should a human step in (unresolved dispute type)? | No or several candidate workflows, or a second contradiction between routing and admitted facts, hand the claim to a person; disagreeing readings are marked for a person. | §4.1 (p. 8), Table 2; Supp. S9.1 | done |
| J14 | Method statements do not belong in the results. | Data, designs and measures are in §6.1. §6.2 still explains the H4 test. | §6.1, §6.2 | done |
| J15 | Start the discussion with a recap. | §8 opens with Principle 1, not a recap. | §8, §8 | open |

## Internal referee rounds 1 and 2

Reports: `analysis/review/REFEREE_REVIEW.md` (round 1, M1–M10) and `analysis/review/REFEREE_REVIEW_ROUND2.md` (round 2, N1–N12), both on the 55-page version of 11 November.

### Round 1, major concerns

| # | Concern (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| M1 | Contribution and IS positioning unclear; missing related work. | Problem class and design-science framing on p. 1; three contributions; principles with evidence. | §1 (p. 1–3), §2, Table 1, §8 | partly. Swiss supervisory guidance is not cited (`analysis/REFERENCES_ADDED.md`). |
| M2 | Tenancy references are circular; data aligned with the design. | Stated in §6.1 and §8.1. Clean room and reading sensitivity (§6.7). The test set "was designed to include the denied- and open-event claims" (§6.1). The fair-baseline check shows that most of the registered tenancy lead came from what the prompt was told (§6.6). | §6.1, §6.6, §6.7, §8.1 | partly. The references remain the engine's under one reading; 69% and 62% of the tenancy lead rest on reading a denied defining event as ending the process, on which no lawyer has ruled. |
| M3 | Tenancy effect sits in 33 designed gating claims; the unit amplifies them. | §6.2: the effect sits in the 9 families with denied- or open-event claims; the other 15 differ little. §6.4: on the 40 claims that state every fact, 0.19 against 0.39 and 0.19. §6.6: a prompt told the stop and hold rules removes the gap on those claims. | §6.2 (p. 12), §6.4 (p. 14–15), §6.6; Supp. Table S39, Fig. S7, Fig. S8 | done |
| M4 | Unequal development effort; reviewed rules favour execution. | §8.1: "CasePath alone was developed on earlier data"; the rule review "worsened both single prompts (1.47 to 1.74, 0.67 to 0.95)"; CasePath never ran with the original rules. The prompt with hold option was written after the test, on the test data. | §6.2, §6.6, §8.1 (p. 19) | partly. Stated once in Scope; the abstract does not mention the rule review. |
| M5 | Formal statements lack their scope. | Scope in each proposition; admission as Table 2; related facts acknowledged; plain walk on theft stated. | §3, Table 2, App. A | done |
| M6 | Inference with 9 clusters. | Exact sign-flip tests; inverted interval for H4 (−1.25 to 0.08); stories as clusters (p = 0.0156); §8.1 "theft has nine clusters". | §6.2, Table 5; Supp. Table S24 | done |
| M7 | Checklist-only comparison and cost split do not support "later agents changed nothing". | "The full product and the core alone did not differ detectably"; §8.1 "The full product and the core shared cached responses". Run-to-run identity is in the supplement (93% and 59%, against 81% and 17%). | §6.3 (p. 13), §8.1; Supp. S13.2, Table S21 | done |
| M8 | Freeze integrity and test-data independence. | Timeline (Table 3); who read what; open-rule decision (App. B); merge "not confirmed" at the time of writing (App. B). | §6.1, Table 3 (p. 10), App. B (p. 26) | partly. No conflict-of-interest statement yet; merge status pending (authors' facts). |
| M9 | Expert study should not be in the body. | The expert study is out of the paper; one sentence of future work (§8). | §8 (p. 20) | done |
| M10 | Prior conference version not identified; manuscript too long. | 27 pages (body p. 1–20), supplement 68. | — | partly. The conference version is not named and its delta not stated (authors' fact). |

### Round 2, new problems

| # | Problem (one line) | What the paper now does | Where | Status, and what remains |
|---|---|---|---|---|
| N1 | The hypothesis order changed before the freeze, which made H3 testable. | Disclosed with times; Table 5 shows outcomes under the earlier orders; §8.1 "H3 was tested only after a reorder 38 minutes before the freeze". | Table 3, §6.2, Table 5 (p. 12), §8.1, App. B | done |
| N2 | Two intervals for the same contrast. | The reweighting table is in the supplement with a caption on its narrower intervals. | Supp. Table S26 | done |
| N3 | Two estimates for "ordinary claims". | §6.2 gives family means and points to Supp. Table S17; §6.4 uses claim-run means and says so. | §6.2, §6.4; Supp. Table S17 | done |
| N4 | Two single-prompt latencies. | One statement of medians (§6.5); "times are lower bounds" (§8.1). | §6.5 (p. 15), §8.1 | done |
| N5 | Loose pointers; the data-writer disclosure appears three times. | Pointers into the supplement read "Supplement, Section …". The data-writer disclosure is in §8.1, App. B and App. C. | §8.1, App. B, App. C | partly. Still three places. |
| N6 | The change table listed exact deferral as new. | The root-cause table is in the supplement. | Supp. S8, Table S13 | done |
| N7 | Post-review analyses carry headline weight. | Registered results lead; every added analysis is marked with a dagger and its p values are descriptive. The abstract states the post-test fair-baseline result as such ("After the test …"). | §1, §6 opening (p. 9–10), abstract | done |
| N8 | Terminology drift. | Units defined once in §6.1. | §6.1 | done |
| N9 | Post-review numbers cannot be re-checked from a clone. | `reproduce.sh` re-runs them; cache-dependent parts are skipped without the cache archive. | App. C (p. 27); Supp. S18.2 | done |
| N10 | Two check sizes for the theft evaluator. | The supplement says these are two different checks. | Supp. S10, S11.2 | done |
| N11 | The design table said checklist only makes document judgments on theft. | §6.1: the checklist-only setting "skips the document judgments for a claim of one file; every theft text is such a claim". | §6.1 (p. 10) | done |
| N12 | §6.4 too dense. | Section 6 has eight subsections, each opening with its finding. | §6.1–§6.8 | done |

Round-2 items that concerned the abstract: the gloss of "per pair" (open: no gloss), the mechanism sentence that omits presumptions and the plain walk (open: unchanged), and the qualifier on the reviewed rules (open: the abstract no longer mentions the rule review at all; §8.1 does). Minor 9 (handler time) is answered by disclosure: "handler time was not measured" (§8.1).

## Outside feedback of 12 November 2026 (eight points)

The feedback text is not in the repository; the asks are as `WORKLOG.md` (entry of 2026-11-12) lists them (nine asks for eight points).

| Ask | What the paper now does | Where | Status |
|---|---|---|---|
| A different headline: "holds", not "wins" | The registered result leads, then the post-test fair-baseline check, which shows a prompt told the stop and hold rules also holds and matches CasePath on tenancy overall. The abstract's claim is now: "What the design adds is fewer wrong holds, checks of supplied documents, and requests that stay stable when one sentence changes." | Abstract, §1 (p. 2), §6.6 | partly: "holds" is no longer a claim the paper makes against a prompt that is told the rules |
| All four cells, with an error decomposition | Table 6 gives every design in every cell; Fig. 3 draws them; Table 7 splits CasePath's errors by stage. | §6.3, Table 6 (p. 13), Fig. 3 (p. 14), Table 7 (p. 15) | done |
| Real-file evidence that needs no experts (point 3) | Out of the paper by the owner's direction; one sentence of future work. The protocol with the archival endpoint is in `expert_study/` as separate work. | §8 (p. 20) | open |
| An answer to the circularity objection | Clean room (1,024 of 1,024; "confirms the implementation of the catalogue"); readings A1–A4; the fair-baseline check. | §6.6, §6.7, Tables 8–9, §8.1 | partly: the reading itself needs a lawyer |
| Open repair of the statistics | Table 5: outcome under each order and under Holm (not registered); H4's test stated exactly. | §6.2, Table 5 | done |
| The lint as a tested contribution | Tested, not claimed as a contribution: "We propose a lint as a diagnostic"; its remedy failed out of sample. A planted-defect test on the new public rule sets is planned (`study4/SPEC.md`, step 2d) and not done. | §6.8 (p. 18), §8.1 | partly |
| Budget-matched comparisons | At matched cost: −1.76 per claim (p = 0.0006), −0.53 per pair (p = 0.1328). | §6.5, Fig. 4 (p. 15–16) | done |
| The tested commit as the artefact | "The artefact is the core of CasePath at commit 6a72159c". DOI pending. | §4 (p. 8) | partly: DOI not deposited |
| A cut to about 35 pages | 27 pages. | — | done |

## Third referee round (12 November 2026)

Report: `analysis/review/REFEREE_REVIEW_ROUND3.md` (10 major, 23 minor). The check of the first rewrite, `analysis/review/REFEREE_ROUND3_CHECK.md`, found 64 of 71 items closed and 7 partly, recommended minor revision, and listed ten wording problems D1–D10, which the next version closed. The paper has since been restructured again (step 0 and the fair-baseline subsection). The statuses below are of the current PDF.

| # | Concern (short) | Now | Status |
|---|---|---|---|
| M1 | H4 paragraph false | §6.2: fewer errors on 7 of 9 changed conditions, more on 2 (0.13 and 1.00); 32 of 512 sign patterns. | done |
| M2 | Headline led with a post hoc subset | Abstract and §1 lead with registered H1–H3; the post-test results follow, labelled. | done |
| M3 | Theft "holding" does not show holding | §6.4: the open condition's documents held 83, 85, 85, 90%; §8.1: "the unchanged share cannot tell a hold from reading the open fact as false". | done |
| M4 | Frontier theft attributed to the rules | S7c reported (+0.25, p = 0.0781); rule part 0.333, 0.22–0.44 under alternative mappings; §6.8 "Theft on the frontier model". | done |
| M5 | Reviewed rules confound theft comparisons | S4c beside H1 (p = 0.0117); frontier superiority p = 0.6367; §8.1 states the review and its effect. | done |
| M6 | Reading sensitivity too strong | §6.7: two thirds of the lead (69%, 62%) rest on the denied-event reading; amending removes 64% and 36%; 6 of 10 contrasts reverse under all four readings; §8.1 states it once. | done |
| M7 | Cost understated | Table 4 ratio columns; §6.5: 19.8 and 41.8 times the same-model prompt; §8.1 "20–42 times". | done |
| M8 | Lint as finding and contribution | Not a contribution; "proposed diagnostic" in §6.8 with flag counts and the out-of-sample failure. | done |
| M9 | Labelling and multiplicity | Dagger convention; "their p values are descriptive" (§6); §8.1 "secondary and post hoc p values are not corrected for multiplicity". | done |
| M10 | Abstract omits limits | The abstract no longer carries limits; by the owner's direction they are stated once, in §8.1. | partly |

Minor concerns: all 23 done. Minor 11 (provenance of the hackathon dossiers) and minor 5 (the abstract's subset wording) are done because the dossiers and that abstract sentence are no longer in the paper; the other 21 read as the report asked. D1–D10: D1, D2 (now one sentence in §6.4 and Supp. Fig. S8), D3 (§6.7), D4, D5, D6 and D9 read as the check asked; D7, D8 and D10 concerned sentences that are no longer in the article.

## Owner's direction of 12 November and steps 0 to 2

- Step 0 (no model calls): dossiers and expert study out of the paper; one Scope section (§8.1); the artefact is the minimal core; one main table with all cells (Table 6), with holds counted in "all deviations".
- Step 1 (USD 4.45 by the ledgers; `study4/baseline_check/REPORT.md`): a single prompt with a hold option, told the stop and hold rules, on both models; now §6.6 and Table 8.
- Step 2a: three rule sets written from public text, each rule with a verbatim passage and a second reader's check (tenancy 52 and dismissal 74 rules from the Code of Obligations; theft 51 rules from the Insurance Contract Act and one insurer's published conditions; `study4/rules/*/RECONCILIATION.md`).
- Steps 2b–2c: a model-free file generator and development designs for three regimes (`study4/generator/README.md`); two blind clean-room evaluators agree with the engine on 1,240 of 1,240 document decisions (`study4/dev/CLEANROOM.md`). Writing of the development files was still in progress at this refresh.
- Step 2d (lint with planted defects) is specified in `study4/SPEC.md` and not done. Steps 3 to 5 of `STUDY4_COSTED_PLAN.md` are not approved.
- None of steps 2a–2d is in the paper.

## Counts

| Source | Done | Partly | Open |
|---|---|---|---|
| CptP (10) | 6 | 4 | 0 |
| 2Kwe (5) | 1 | 4 | 0 |
| SBTv (5) | 1 | 4 | 0 |
| J01–J15 (15) | 10 | 3 | 2 |
| Round 1, M1–M10 | 5 | 5 | 0 |
| Round 2, N1–N12 | 11 | 1 | 0 |
| Round 2, abstract items (3) | 0 | 0 | 3 |
| Outside feedback (9 asks) | 4 | 4 | 1 |
| Round 3, M1–M10 | 9 | 1 | 0 |
| Round 3, minor 1–23 | 23 | 0 | 0 |
| Round 3 check, D1–D10 | 10 | 0 | 0 |

## Statuses lowered in this refresh, and why

| Item | Before | Now | Why |
|---|---|---|---|
| Outside feedback, real-file evidence (point 3) | partly | open | The archival comparison was the paper's Appendix B; it is now out of the paper and is separate follow-up work. |
| Outside feedback, headline "holds" | done | partly | After the fair-baseline check the paper no longer claims that the design holds what a prompt told the rules does not. |
| Round 3, M10 (abstract limits) | done | partly | By the owner's direction the abstract carries no limits; they are stated once, in §8.1. |
| Round 2, reviewed-rules qualifier in the abstract | partly | open | The abstract no longer mentions the rule review. |
| CptP W2 | partly | partly (narrower) | Status unchanged, but the paper now concedes that the registered tenancy result "measures mostly what the prompt was told". |
| Entries that pointed to the deployment study (CptP W4, SBTv W4, J10, round 1 M8/M9) | relied on App. B | answered only by the paper's own evidence | The study is out of the paper; round 1 M9 rose to done because the study left the body entirely. |
