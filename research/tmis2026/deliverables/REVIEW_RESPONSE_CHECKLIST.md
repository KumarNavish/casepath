# How every criticism was addressed

Paper: *CasePath: Executing Process Rules over LLM Judgments to Request Evidence* (TMIS draft).
Section, table and figure numbers refer to `CasePath_TMIS.pdf`.
✅ addressed · ◐ partly addressed, with the remaining step named.

## Reviewer CptP

| # | Criticism | What changed | Where | Status |
|---|---|---|---|---|
| W1 | Study A shows no accuracy benefit: the gates failed (Holm p = 0.797), CasePath is weaker on several conditions, and its advantage comes from baseline withdrawals. | The study was replicated with two current models, 3 runs each, under an analysis plan frozen before the held-out runs. Results are reported as they came out. With gpt-6-luna, CasePath made 4× fewer wrong changes (17 vs 68, Holm p = 0.012). With gpt-6.1-terra, rules in context made fewer (22 vs 38; F1 0.79 vs 0.67), but the difference was not significant (p = 0.42). Errors are split into wrong and missed changes. The original results and failed gates are kept unchanged in App. A. No blanket accuracy claim remains. | §5.2, Tab. 5, 7, Fig. 3, App. A | ✅ |
| Q1 | What accuracy claim does Study A support? | A model-dependent one. Execution makes fewer wrong changes with the cost-efficient model (significant). The original model showed the same pattern in a single run (15 vs 41). The frontier model showed no significant difference, and descriptively rules in context did better. | §1, §5.2 | ✅ |
| W2 | Study B's 98% result follows from the design; holds were unscored; the conservative contrasts were negative; the original evaluator accepted nothing; scoring was switched post hoc. | The Local-scope comparison is no longer used for any claim; App. A explains why it was uninformative. A new pre-specified tenancy experiment has every design return only its evidence plan (all outputs valid). Holds are scored as deferrals, apart from unsafe errors, and decomposed by cause. CasePath is compared with plans generated independently by the same model. | §4, §5.1, Tab. 6, App. A | ✅ |
| Q2 | Are the Study B references made from the same templates? How accurate is the dispute-type judgment? How should holds count? | Yes, and the paper says so. Oracle check: the true flags reproduce 147/150 reference sets. Family accuracy is 95–100%. Condition judgments (terra): 428 correct, 7 contradicted, 735 unresolved; luna: 450, 0, 720. Holds count as deferrals. Most come from one unstated routing fact (terra 397/538, luna 206/352); presuming that fact (post hoc) gives 95% recall. | §4.2, §5.1, §5.5 | ✅ |
| W3 | One model, one run, no prior systems; baseline prompts not shown. | Two current models (frontier and cost-efficient) plus the original model; k = 3. Five alternatives, each representing a published approach: policy text in the prompt (τ-bench), rules in the prompt (FlowBench), self-consistency, Chain-of-Logic-style rule application, and two-valued (rule-engine/closed-world) execution. All prompts are verbatim in App. E. Tests are exact sign-flip tests with Holm correction. | §4.3, Tab. 4, App. E | ◐ No ReAct-style tool-using agent (reason in §6.4) |
| Q3 | How many runs underlie each number? | Three per design, case and model; every call is logged with tokens and charges. | §4.5, App. D | ✅ |
| W4 | Data are synthetic, self-authored and unreviewed; held-out inputs were exposed; temperature was unset. | A blind re-derivation of the theft references reproduced 7/9 conditions exactly, with a sensitivity analysis on those 7. The oracle check makes the tenancy circularity explicit: the study tests rule *application*, not legal correctness. Exposure is disclosed. The reasoning models accept no temperature, so variability is measured with repeats. | §4.2, §6.4 | ◐ No legal-expert review yet |
| Q4 | What was exposed? Was there expert review? | Disclosed: held-out tenancy inputs were visible during product development, and the theft cases have been public since the first study. There was no expert review. | §6.4 | ✅ disclosed |
| W5 | Algorithm 1 was a picture; the formal definitions sat in the appendix; Figure 2 was a low-resolution raster. | The main text now has a formal problem statement, Eqs. (1)–(4), Propositions 3.1–3.3 with proofs, typed pseudocode (Alg. 1) and a complexity analysis. All figures are vector (TikZ or PDF). | §3, Alg. 1, Fig. 1 | ✅ |
| W6 | The related work was two paragraphs; the bibliography was inconsistent. | New related-work section with a comparison table. All 52 cited references were checked against authoritative records (DOI, publisher, proceedings or arXiv page) and use one ACM style. The unverifiable ServiceNow page was removed. | §2, Tab. 1 | ✅ |

## Reviewer 2Kwe

| # | Criticism | What changed | Where | Status |
|---|---|---|---|---|
| W1/Q1 | Technical novelty over neuro-symbolic and process-aware methods is unclear. | Tab. 1 compares the approach families on the capabilities the decision needs. §2.3 names the missing combination. The paper states what is *not* new: three-valued logic, rule execution, model-based extraction and verification. What is new: soundness under incomplete facts, an incompleteness result for the production engine's strong Kleene semantics, exact deferral by supervaluation, and evidence of when execution pays. | §1, §2, §3 | ✅ |
| W2 | Generality is limited; the two studies test different parts; no comparison with existing agents. | Both datasets now use one agent, one engine and one set of measures. The designs map to published approaches, and two current models are tested. | §4, §5 | ◐ Still synthetic, two Swiss domains (§6.4) |
| Q2 | How are extracted rules validated? Can errors be found without manual work? | Traces attribute 37 of 38 wrong changes to 5 of 98 rules. A blind rule verifier flags all 5, but also 59 other rules, so it can focus expert review but not replace it. | §5.6 | ✅ |
| Q3 | Why custom baselines instead of adapted prior methods? | Each design implements a published approach's core decision under identical inputs, and the prompts are released. Code for the closest systems is not available. | §4.3, Tab. 4, App. E | ✅ |
| Q4 | Why different datasets for different aspects? | Both datasets run the same agent and measures. Tenancy tests complete request lists, because its references are complete. Theft tests changed and unresolved facts, because its references define changes. | §4.2, Tab. 3 | ✅ |

## Reviewer SBTv

| # | Criticism | What changed | Where | Status |
|---|---|---|---|---|
| W1 | The architecture is standard (neuro-symbolic, DMN, BPMN), and the process definition is ad hoc across studies. | Honest positioning (§2.3). One formal framework (process graph, three-valued conditions, requirements, routes) covers both rule packs, with theft as the flat special case, and one engine serves both. | §2, §3.2 | ✅ |
| W2 | No formal problem definition and no objective. | §3.2 states the inputs, outputs, soundness and exactness. Route choice minimises the documents requested per requirement (Eq. 4); minimising over shared documents is a hitting-set problem. | §3.2–3.3 | ✅ |
| W3 | Algorithm 1 is a schematic without types or complexity; the logic is trivial. | Typed pseudocode and complexity: linear evaluation; supervaluation is exponential only in the open flags and coNP-complete in general. Measured runtimes: 65 ms per 100-step graph, 22 s for 10 open flags. Prop. 3.2 shows the strong Kleene evaluation in the production engine is incomplete. Exact deferral removes 43–58% of its deferrals and adds no unnecessary request. It exposes 4 and 2 document-review errors that the holds had hidden. | §3.3–3.4, §5.1, §5.7 | ✅ |
| W4 | Synthetic data, no experts, circular evaluation. | The oracle check, an independent reference re-derivation, and the analysis of how the references treat silence make the circularity explicit and measurable. | §4.2, §5.5, §6.3 | ◐ Expert review pending |
| W5 | Narrow scope and weak baselines; no neuro-symbolic, ReAct or DMN comparison. | Two-valued execution reproduces rule-engine (DMN) and closed-world neuro-symbolic semantics on the same judgments. Self-consistency and Chain-of-Logic-style designs were added, with two models. | Tab. 4, 6, 7, §6.4 | ◐ ReAct not run (reason in §6.4); scope still Swiss |

## Joe's comments

| ID | Comment | What changed | Where |
|---|---|---|---|
| J01 | State the RQ and its rationale before the contributions. | One explicit RQ with three reasons, placed before the contributions. | §1 ¶3 |
| J02 | Expand related work with a summary table showing how ours differs. | Full section, comparison table, and a "what is missing" subsection that leads to the RQ. | §2, Tab. 1 |
| J03 | Separate the insurance background from how the model works. | §2.1 gives the claims context, §2.2 the approaches, §3 the method. | §2.1, §3 |
| J04 | Say what each study is meant to achieve. | Five pre-specified claims (H1–H5), each tested by one experiment; Tab. 3 maps datasets to claims. | §4.1, Tab. 3 |
| J05, J08, J12 | Use topic sentences. | Every results subsection opens with its answer, and every paragraph opens with its point. | §5 |
| J06 | Relate the methods to the literature to give a red thread. | Tab. 4 maps every compared design to the approach it represents. | Tab. 4 |
| J07 | A table of methods × elements. | Tab. 1 (approaches × capabilities) and Tab. 4 (designs × properties). | Tab. 1, 4 |
| J09 | A table of terms. | A glossary. | Tab. 2 |
| J10 | Since CasePath still errs, what should humans monitor? | Named oversight points: rule admission, the presumption policy, held questions, claims handed to a person, and traces. The user study stays in Paper B. | §6.2 |
| J11 | Managerial guidance on when to use which design. | A decision table, "when to execute the rules". | Tab. 8, §6.2 |
| J13 | Where should a human step in (unresolved dispute type)? | Claims whose category cannot be verified go to a person; held questions mark exactly the facts that matter. | §6.2 |
| J14 | Method statements do not belong in the results. | Metric definitions moved to §4.4; the results report findings only. | §4.4, §5 |
| J15 | Start the discussion with a recap. | §6 opens by recapping what was built, compared and found. | §6 |
