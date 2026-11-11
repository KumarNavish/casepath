# Second-round referee report

**Manuscript:** "CasePath: Agents That Read, Rules That Decide", revised version (54 pages; body pp. 1–23, references pp. 23–27, appendices A–G pp. 27–54), with Supplement (27 pages).
**Venue:** ACM TMIS.
**Basis of this report:**
- I read the body once as a fresh reader before opening the first-round report.
- I checked the numbers against `analysis/study3_results_fresh2_confirm.md` (registered output) and `analysis/study3_review.md` (the analyses added after review).
- I checked the hypothesis order against the plan's specification history at the commits that Table 6 cites (`482873e3` and its parent).

Page numbers refer to the revised PDF.

**Recommendation: minor revision.** The revision is substantial and mostly honest. Two things keep it short of acceptance:
1. One undisclosed design fact matters for H3: the hypothesis order changed shortly before the freeze (see N1).
2. A small set of number and pointer errors remains, all fixable from material the authors already hold.

---

## 1. Major concerns M1–M10

### M1. Contribution and IS positioning: largely resolved

**What is resolved:**
- p. 1 states the problem class: "deciding which evidence to request when the decision depends on facts the file does not settle".
- p. 1 frames the work as design science [20, 22].
- p. 3 reduces the contributions to three. The release and the protocol are now "resources".
- p. 4: Table 1 drops the "learns" and "registered" columns, and "n.s." is replaced by "–".
- Section 2 adds every line of related work I asked for, except the Swiss supervisory guidance.
- p. 22: the four principles have their evidence and a boundary condition.

**Still missing:**
- **Page 1 says what is new but not why it matters to an organisation.** No sentence on page 1 names the cost of a wrong or premature request (claimant burden, delay, handler rework) or the audit benefit. Auditability first appears on p. 22.
  - *Fix:* after "This is one instance of a class of problems…", add one sentence. For example: "A request made too early burdens the claimant and the handler; a document dropped too early weakens the decision; and an insurer must be able to show why it asked."
- **"For an organisation" (p. 22) is thin.** It does not give the effort of authoring and reviewing a workflow, though the authors have it: 98 rules, two AI editor sessions, 9 changes, 14 queued for a jurist. It also does not say who owns a presumption.
  - *Fix:* add the review effort in hours or sessions if it was recorded. Add one sentence on the owner of a presumption's source clause.

### M2. Circular references and data aligned with the design: resolved

**What is resolved:**
- **Abstract (p. 1):** "Tenancy references come from the engine the product implements."
- **Data and authorship (p. 14):** Section 6.1 states the three limits, including the one writing model.
- **Wrong presumptions (p. 19):** the stress test of presumptions has been added (Table 24).
- **Fact-level accuracy (p. 8):** Table 3 and Section 3.5 now report it.

**Residuals (minor):**
- **The abstract omits that the researchers wrote the silence clause.** Add "under a silence clause we wrote" to the abstract's references sentence.
- **Table 3 merges two different kinds of "Unresolved".** It puts right and wrong unresolved values in one column. Of the 103 unresolved branch-fact values, 69 are designed-open facts (right) and 34 are settled facts left open (wrong). For the defining event the split is 26 and 1 (`study3_review.md`, R3). The 34 wrongly unresolved values are the cost side of Principle 3 and should be visible.
  - *Fix:* split "Unresolved" into "right (open by design)" and "wrong (settled)".

### M3. Effect concentrated in 33 designed gating claims: partly resolved

**What is resolved:**
- p. 19, Tables 10 and 22: claim-level outcomes.
- p. 19 and Table 23: reweighting to other claim mixes.
- p. 19 (R8): what the single prompts did on denied-event claims.
- p. 23: the gold standard is now called "a choice of the data design".
- p. 22, Principle 1: the result of Model executes rules is now discussed.

**Still missing:**
1. **The abstract still claims more than the subset results show.** It says: "On tenancy it made fewer errors than a frontier model's single prompt (0.31 against 1.86); the difference lies in the 33 of 96 claims whose defining event is denied or left open."
   - "The difference lies in" is stronger than the evidence ("most of", p. 17).
   - The abstract omits that the product did not differ from the frontier prompt on the other 63 claims (p = 0.409).
   - *Fix:* "…; most of the difference lies in the 33 of 96 claims, included by design, whose defining event is denied or left open; on the other 63 it did not differ significantly."
2. **Principle 1 compares numbers from different claim sets (p. 22).** It says: "Model executes rules … made 0.83 errors per claim: explicit semantics closed much of the gap, and code most of the rest."
   - 0.83 is the mean over all 96 claims.
   - 0.47, 5.69 and 5.31 in the same paragraph are means over the 33 gating claims.
   - On those 33 claims, Model executes rules made 1.94 errors per claim on denied-event claims and 1.04 on open-event claims (Table 14), about 1.70 per claim pooled.
   - *Fix:* use the 33-claim value. Its family mean comes from the same script.
3. **None of the reweighted mixes is tied to real intake.** Table 23's mixes (90/5/5, 80/10/10) are arbitrary. The first round asked for at least one mix that resembles the insurer's intake.
   - *Fix:* if no intake share can be given, say so in one clause.

### M4. Unequal development effort and rules reviewed in favour of execution: partly resolved

**What is resolved:**
- p. 14, Section 6.1: "Development effort was one-sided…"
- pp. 16–17: the original-rule rows are in the body and in Figure 4.
- p. 19 (R9): an attempted explanation of why the reviewed rules hurt the single prompts. It is inconclusive, and the paper says so.
- p. 2: the introduction states "reviewed for execution, with knowledge of the test conditions".

**Still missing:**
- **The abstract still lacks the qualifier on the reviewed rules.** It says only "on theft, with reviewed rules", and omits that the editors knew the test conditions.
  - *Fix:* "with rules reviewed for execution by editors who knew the test conditions".
- **The abstract omits the strongest single-prompt configuration.** On the frontier model with the original rules, the single prompt made 0.67 errors per pair against CasePath's 0.58 (secondary S4a/S4b, descriptive). This belongs next to H1 in the abstract, because it is the best single-prompt result on theft.
- **Section 6.1 does not say whether any baseline prompt was tuned on development data.** It says the comparators "were written for Studies 1 and 2 or adapted from them".
  - *Fix:* "No baseline prompt was changed in response to development results after Study 2", or the opposite if that is the truth.

### M5. Formal statements and their premises: resolved

**What is resolved:**
- pp. 6–7: flow-workflow and two-valued scope are now in Propositions 3.1–3.4.
- p. 5: related facts are acknowledged.
- p. 6, Table 2: the admission rule is given as a table of cases.
- p. 8: the eight-fact and twelve-fact thresholds are reconciled.
- pp. 27–29: the noise model (ρ = 0 and ρ = 1), the triple 84.5 and the units of Figure 6 are explained.
- p. 8: the fact-level error rate is reported.
- pp. 5 and 8: document presence is declared to be a model judgment.

**Residual:**
- **The plain walk on theft is not mentioned outside Section 3.4.** Every theft case-run used the plain walk, not exact deferral (p. 8). Appendix A justifies this, but the abstract's "holds every request that depends on a fact still open" and Principle 2 both read as if exact deferral ran on theft. Principle 2's boundary covers it only partly. See claim 2 in Section 2 below.

### M6. Inference with 9 clusters: largely resolved

**What is resolved:**
- p. 16: inverted sign-flip intervals in Table 8.
- p. 17: the H4 discrepancy is explained.
- Tables 17 and 21: the bootstrap non-inferiority p-values are caveated.
- Table 21: stories as clusters and two-way resampling.
- Figure 7: the family plot.

**Still missing:**
- **Figures 4 and 5 still use the interval the paper rejects.** Both show the percentile cluster-bootstrap interval for theft ("with the analysis's resampling settings", p. 17), which Section 6.4 calls "too narrow".
  - *Fix:* use the inverted sign-flip interval on the theft panel, or say in the caption that the theft bars under-cover and point to Table 21.
- **Table 8 now mixes registered and post-review intervals.** It is the registered hypothesis table, but its theft interval column holds the post-review interval and its tenancy rows hold the registered one. The caption says so, but one column with two provenances is easy to misread.
  - *Fix:* add a registered-interval column, or footnote each theft interval.

### M7. Checklist-only comparison and the cost split: partly resolved

**What is resolved:**
- pp. 19–20: the paper now says "no detectable difference".
- pp. 19–20: identical checklists in 93% (tenancy) and 59% (theft) of case-runs.
- Appendix D, R7: the cost is reconciled.
- The frontier design is renamed consistently.
- p. 22, Principle 4: now conditional on the handlers' needs.

**Still missing:**
1. **41% of theft checklists differ, and the paper does not say why.** All 159 differing theft case-runs differ first at a fact value (R7). On theft the checklist-only run skips no fact check, so the cause is probably independent re-sampling of the readings outside the shared cache. The reader cannot tell this from an effect of the skipped agents.
   - *Fix:* report the share of identical checklists between two runs of the full product as a baseline, and say that the differences are run-to-run variation if that is what they are.
2. **"Components that can affect the checklist" contradicts Sections 4.1 and 4.6.**
   - Section 4.6 says the checklist-only setting skips "the source checker's check of facts".
   - Table 4 says the source checker "accepts or rejects facts".
   - Section 4.1 says "Rejected items are tried once more".
   - Yet the introduction (p. 2) calls the checklist-only run "running only the components that can affect the checklist".
   - *Fix:* either state that a source-checker rejection of a fact cannot change admission, or drop "only the components that can affect the checklist".

### M8. Integrity of the freeze and disclosure: partly resolved

**What is resolved:**
- p. 15, Table 6: a dated timeline.
- pp. 14 and 44: what the data-writing session could access.
- p. 1: "released" is replaced by "frozen commit".
- p. 30: the open-rule decision is explained.

**Still missing:**
- **No conflict-of-interest or role statement.** The paper does not say who "the product's owners" are, how the authors relate to the insurer, or whether the tested commit has since been merged. p. 21 still says only that "The run started before the product's owners confirmed the merge."
  - *Fix:* add a declaration of interests and roles, and state the current merge status.
- **The reordering of the hypotheses is undisclosed (N1 below).**
- **The plan was drafted after the test data were sealed.** `fresh2/` was sealed at 17:05 and the plan drafted at 19:17. The directing author, who directed the data writing, also set the open rule at 21:53. The paper says the probe writer had not seen the test texts, but says nothing about whether the people who drafted the plan or chose the open rule had read them.
  - *Fix:* one sentence stating whether they had.

### M9. Expert study in the body: largely resolved

**What is resolved:**
- p. 3: removed from the contributions.
- p. 23: reduced to one paragraph.
- p. 23 and p. 51: the P labeller's provenance is stated.
- p. 23: the interface mismatch, prior exposure and the 1/32 floor are listed.

**Still missing:**
- **No ethics statement.** p. 50 says only "The insurer's consent is in place." Add the ethics-committee status of the expert study, or state that none was sought and why.

### M10. Prior conference version and length: partly resolved

**What is resolved:**
- The length is down from 65 to 54 pages.
- Studies 1 and 2 are in the Supplement.
- The Supplement marks Table S6 as superseded.

**Still missing:**
- **The prior version is still not identified.** The acknowledgments thank "the three anonymous reviewers of the conference version" (p. 23), but the manuscript does not name that version or state the new material. ACM policy requires both.
  - *Fix:* add a title-page footnote naming the venue and summarising the delta.

---

## 2. Minor concerns 1–23 and the claims-against-evidence list

### Minor concerns

1. **Terms defined before use: partly resolved.**
   - The introduction now glosses the terms.
   - The abstract still uses "per pair" and "unsafe errors" without a gloss. Add "pairs of texts differing in one fact".
2. **"Study 3" naming: resolved** (Section 6 title).
3. **"CasePath" in the Supplement legends: resolved** by a note on Supplement p. 1.
4. **Figure 2 caption: resolved.**
5. **The lease in Figures 1 and 2: resolved.**
6. **Normalisation of quotations: resolved** (p. 5).
7. **Cache key and independence of the readings: resolved** (pp. 14–15).
8. **Model identification: resolved** (p. 14 and Appendix B).
9. **Latency: partly resolved.** It is reported (p. 20, Table 25), but not put in proportion to a handler's time.
10. **Long files in the limits: resolved** (pp. 14 and 23).
11. **ShARC pilot: resolved** (p. 13: unplanned, training split, 60 development utterances).
12. **Worked example: resolved** (pp. 20–21, Table 11).
13. **"Cost-matched": resolved** (p. 15).
14. **Wrong holds in the abstract: resolved** ("held more than needed"). The number would help; see the abstract fix in Section 4.
15. **Principle 2 on tenancy only: resolved** (p. 22).
16. **Figure 4 pointer: not resolved.**
    - The caption says "The two-valued rows' strict unsafe errors are in Tables 23 (test mix) and 16".
    - Table 16 gives theft wrong + missed changes, not strict unsafe errors.
    - *Fix:* "Their tenancy values are in Table 23, their theft values in Table 16."
17. **Silence clause written by the researchers: resolved** (p. 6).
18. **Scope of the parity check: resolved** (p. 11).
19. **Ref. [32] marked as a preprint: resolved.**
20. **ShARC reference [51]: resolved** (DOI given).
21. **Figure 6: resolved.**
22. **H5 status stated once: resolved** (Table 8).
23. **Section 4.3 (Knowledge) shortened: resolved.**

**Unresolved or partly resolved: 3 (items 1, 9, 16).**

### Claims against evidence (first-round items 1–24)

1. Resolved.
2. **Partly resolved.** The abstract says: "Code admits a value only when the readings agree, executes the organisation's rules, and holds every request that depends on a fact still open."
   - The sentence omits presumptions. Table 2 admits a presumed value with a single supporting reading.
   - It omits "given the admitted facts".
   - On theft the plain walk ran, not exact deferral.
   - *Fix:* use the introduction's own wording (p. 1).
3. Resolved.
4. **Partly resolved.** "the difference lies in the 33 of 96 claims" (abstract). See M3.1.
5. Resolved.
6. Resolved.
7. Resolved.
8. Resolved.
9. Resolved ("most of", "designed to include").
10. Resolved.
11. Resolved.
12. Resolved.
13. Resolved.
14. Resolved.
15. **Resolved in substance, but vague.** "on tenancy it was similar" (p. 22). Give the numbers: −1.83 and −1.56.
16. Resolved.
17. **Not resolved.** Principle 1 uses the wrong subset; see M3.2.
18. **Partly resolved.** Principle 3 still says "a second reading that must agree cut theft errors (Table 5)". Table 5 shows that this came from pairing each run's reading with another run's reading. Add "(recomputed by pairing readings across runs)".
19. Resolved.
20. Resolved.
21. Resolved.
22. Resolved.
23. Resolved.
24. Resolved.

### Sentences that still claim more than Section 6 supports

- **Abstract:** "the difference lies in the 33 of 96 claims whose defining event is denied or left open." The evidence supports "most of".
- **Abstract:** "holds every request that depends on a fact still open." This omits the admitted-facts and presumption qualifiers, and on theft the plain walk ran.
- **Introduction (p. 2):** "H4 was not confirmed: on theft the product beat Model executes rules and ReAct". These are components of a conjunctive hypothesis that failed. Write "made fewer errors than … (p = 0.0039 and 0.0117, components of H4)".
- **Section 6 (p. 14):** "We tested CasePath … against every single-agent strategy of Section 2". Chain of Logic and the policy-in-prompt benchmarks of Section 2 were not run. Write "against single-prompt, self-consistency, explicit-semantics and ReAct baselines".
- **Discussion, Principle 1 (p. 22):** the 0.83 sentence (M3.2).
- **Discussion, Principle 2 (p. 22):** "exact deferral changed the checklist against 'unresolved = false' in 123 of 286". This shows change, not improvement. The evidence for improvement is the two-valued error rows: 1.27 and 1.51 against 0.31 strict unsafe errors per claim (Table 23). For strong Kleene evaluation (80 changed claim-runs) there is no error comparison at all. Cite Table 23 for two-valued, and say that strong Kleene was not scored.
- **Conclusion (p. 23):** "It held more of the documents that should wait". "Should wait" is defined by the engine's reference. Write "documents the engine's reference holds".

---

## 3. New problems introduced by the revision

**N1. The hypothesis order changed after the probe, and the change is what made H3 testable. Not disclosed.**
- Table 6 says only "hypotheses reordered at 21:51" (commit `482873e3`).
- In the parent commit the order was: H1 theft; H2 tenancy; **H3 prior-work strategies on theft; H4 theft non-inferiority to the frontier model; H5 tenancy against the frontier model**.
- Under that order, the prior-work hypothesis would have failed (as H4 did), and the tenancy-frontier contrast, now H3 and "confirmed" in the abstract, would not have been tested.
- The reorder came after the probe (19:51) and before the freeze and any sealed datum. The same commit adds development outputs on the frontier model for theft.
- This is legitimate pre-registration practice only if it is disclosed. Add to Appendix B.3 and to Section 6.3:
  - the original order;
  - the reason for the change;
  - what development results on the moved contrasts were known at 21:51;
  - that under the original order only H1 and H2 would have been confirmed.

**N2. Two intervals for the same contrast.**
- Table 8 gives H2 as −1.83 [−2.72, −0.99] and H3 as −1.55 [−2.44, −0.77].
- Table 23's "Test mix" column gives the same differences with [−2.09, −1.57] and [−1.96, −1.18].
- Both are described as paired cluster bootstraps over families.
- The Table 23 interval pools claim-runs within fixed subset weights (`study3_review.md`, R2), which removes the variation in subset composition. That is why it is narrower.
- *Fix:* say this in Table 23's caption, or drop the test-mix interval.

**N3. Two estimates for "ordinary claims" in the body.**
- p. 17: 0.20 against 0.44 and 0.28 (family means).
- p. 19: 0.21 against 0.43 and 0.29 (claim-run means, reweighted).
- The intervals also differ: S1a gives −0.22 to 0.09, Table 23 gives −0.24 to 0.09.
- *Fix:* use one estimate in the body and name the other in the appendix.

**N4. Two different single-prompt latencies.**
- p. 20: "Rules in context's one call took 11 and 12 s".
- p. 22: "a single prompt's call 11–14 seconds".
- Table 25 gives medians of 10–14 s across both single-prompt designs.
- *Fix:* use one statement.

**N5. Wrong or loose pointers.**
- **Section 5 (p. 12):** "(Supplement, Sections S1 and S2)" for "their deviations and robustness analyses". These are in S3 and S4.
- **Appendix C (p. 35):** "the stress test of Section 7". It is in Section 6.4 and Appendix D.
- **Figure 4 caption:** see minor item 16.
- **Appendix C (p. 33):** points to "Appendix E.4" for who wrote the texts. That is correct, but the same disclosure appears three times (Section 6.1, B.2, E.4). Keep one.

**N6. Table 5 versus the Supplement on exact deferral.**
- Table 5 lists exact deferral as a "change" made after Study 1, with "Study 1, recomputed" evidence.
- The Supplement (S1.3.2, Table S4) shows that Study 1 already ran exact deferral as a variant. The Study 1 figures in Section 5 (0.081 against 0.063) are those of the exact-deferral variant.
- *Fix:* reword the row: "Strong Kleene evaluation (the production engine) held 48.6%; Study 1 also evaluated exact deferral, which held 43–58% less", and drop "recomputed".

**N7. "Added after review" analyses carry headline weight in the body.**
- They are labelled every time, but in the Discussion two principles rest mainly on them:
  - Principle 2 rests on R11;
  - Principle 3 rests on R3.
- p. 2: "against the same model they also differed … which the plan did not predict" puts a descriptive contrast in the first page's results paragraph.
- Table 3 (post-review) sits in Section 3, before Study 3 is introduced.
- *Fix:* move Table 3 to Section 6.4, and state in each principle which evidence is registered.

**N8. Terminology drift.**
- The paper uses "case-run", "claim-run", "text-run" and "pair-run" for overlapping units. Table 3's caption uses both "claim-run" and "case-run".
- "Regime" (Figure 4, Section 6.4) is never defined in the body.
- "Held", "holds", "should wait" and "documents that need not wait" carry one meaning under several names.
- *Fix:* define "case-run" once, and use "regime" only after defining it.

**N9. Reproducibility gap for the new numbers.**
- Appendix E.2 (p. 43): "The analyses added after review … are not yet a step of this command; two of them … read Study 3's response cache and therefore need the separate archive."
- Every post-review number in the body (Table 3, the 93% and 59%) therefore cannot be re-checked from a clone.
- *Fix:* add `study3_review.py` to `reproduce.sh`, and commit its byte-compared output.

**N10. Two different check sizes for the theft evaluator.**
- Appendix A (p. 28): "On 5,000 random three-valued assignments".
- Appendix B.2 (p. 31): "3,000 random theft assignments".
- These are probably two different checks. Say so.

**N11. Table 7 contradicts Section 6.4 on theft.**
- Table 7 says the checklist-only setting runs "routing, readings, document judgments, evaluation".
- On theft it ran no document judgment (Sections 4.6 and 6.4, R7).
- *Fix:* add "(tenancy)" to "document judgments".

**N12. Section 6.4 is now dense.** It runs about six pages (pp. 16–21) under 17 run-in headings, ten of them post-review. See Section 4 for cuts.

**Numbers checked and found consistent:**
- The abstract's 0.58/1.74, 0.31/2.14, 0.31/1.86, 33 of 96, 97/48/35% and 2.1/7.4 against Table 8 and the registered output. Theft's 0.02999/0.00408 = 7.35, rounded to 7.4.
- 0.47/5.69/5.31.
- 0.33/0.17/0.18 and 1.17.
- 22%/16% against Figure 5's 4.5/6.1.
- 65%/82%.
- 93%/59% (268/288, 225/384).
- 123/286 (43%) and 80/286 (28%).
- 1344 fact values with 9 wrong admissions and 2 wrong presumptions.
- The stress-test values 0.36, 0.41, 0.51 and the differences −1.82 and −1.55.
- 11% and 27% (R9).
- 75%/0%/25% (Table 10).
- Table 18's sums.
- The H4 percentile interval −1.13 to −0.08 and the inverted interval −1.25 to 0.08.

---

## 4. Clarity and economy

### Where I had to read twice

- **p. 2, the results paragraph:** about 25 numbers in 14 lines. Also: "against the same model they also differed" (who differed?); "cost 22% and 16% of that" (of what?).
- **p. 8, Section 3.4:** "Every theft case-run had more (9–28) and got the plain walk". I had to go back to see that exact deferral never ran on theft.
- **p. 17, H4:** "The exact test, the registered one, asks how often random signs on these unequal differences give a sum as large, and its inverted interval includes zero."
- **p. 19, "Other mixes":** two "ordinary" estimates (N3).
- **p. 22, Principle 4's heading:** "run agents that cannot decide the checklist only for handlers' needs" parses as "run … only for handlers' needs" only on a second try.

### The ten weakest sentences

1. **Abstract.** "Code admits a value only when the readings agree, executes the organisation's rules, and holds every request that depends on a fact still open."
   - *Why:* it overstates the rule (see claim 2).
   - *Better:* "Code admits a deciding value only when every reading gives it with a quotation found in the file, or applies a stated presumption to a fact the file never mentions; it then executes the organisation's rules and holds each document whose need, given those values, depends on a fact still open."
2. **Abstract.** "the difference lies in the 33 of 96 claims whose defining event is denied or left open."
   - *Better:* "most of the difference lies in the 33 of 96 claims, included by design, whose defining event is denied or left open; on the other 63 it did not differ significantly."
3. **Abstract.** "on theft, with reviewed rules, 0.58 against 1.74 wrong or missed changes per pair"
   - *Why:* "pair" is undefined, and the review is not qualified.
   - *Better:* "on theft, with rules reviewed by editors who knew the test conditions, 0.58 against 1.74 wrong or missed document changes per pair of texts differing in one fact".
4. **Abstract.** "held more than needed"
   - *Why:* vague.
   - *Better:* "and held more documents the reference does not hold (0.33 against 0.17–0.18 per claim)".
5. **p. 2.** "On the other 63 it did not differ significantly from the frontier model; against the same model they also differed (0.20 against 0.44, descriptive), which the plan did not predict."
   - *Better:* "On the other 63 claims it did not differ significantly from the frontier prompt (0.20 against 0.28); against the same-model prompt it made fewer errors (0.20 against 0.44, p = 0.042, not part of the plan)."
6. **p. 2.** "running only the components that can affect the checklist cost 22% and 16% of that"
   - *Why:* "of that" is ambiguous, and "can affect" contradicts Table 4 (M7.2).
   - *Better:* "the checklist-only setting, which skips the brief, the process builder and the result checker, cost 22% and 16% of the full product".
7. **p. 14.** "We tested CasePath at a frozen commit against every single-agent strategy of Section 2 and against a frontier model"
   - *Why:* this overclaims.
   - *Better:* "…against single-prompt, self-consistency, explicit-semantics and ReAct baselines and a frontier single prompt".
8. **p. 22.** "Model executes rules, which states the semantics in its prompt but runs no code, made 0.83 errors per claim: explicit semantics closed much of the gap, and code most of the rest."
   - *Why:* it compares numbers from different claim sets.
   - *Better:* "On the same 33 claims, Model executes rules, which states the semantics in its prompt but runs no code, made about 1.7 errors per claim (Table 14): stating the semantics closed most of the gap, and executing them in code closed most of the rest."
9. **p. 22.** "…than with the frontier model (−0.12, p = 0.672, checklist only, one run); on tenancy it was similar."
   - *Better:* "…; on tenancy the gain was similar for both models (−1.83 and −1.56 against each model's single prompt)."
10. **p. 18.** "CasePath held what the file left open (Table 9)."
    - *Why:* tautological, and it assumes that the reference holds what the file leaves open.
    - *Better:* "CasePath held almost every document the engine's reference holds (Table 9)."

Also: **p. 23, Conclusion.** "It held more of the documents that should wait, and more that need not." *Better:* "It held more of the documents the reference holds, and more that it does not."

### Paragraphs that can be cut without loss

- **p. 14, the data-writer paragraph.** It is repeated almost verbatim in B.2 and E.4. Keep two sentences in the body.
- **p. 19, "Fact-level accuracy (added after review)".** It is a pointer only. Cut it once Table 3 moves into Section 6.4.
- **p. 21, "The run".** It duplicates B.1. One sentence suffices: "The run needed five invocations, two stopped by environment failures; 50 comparator outputs failed and were scored empty (Appendix B)."
- **Duplicated reviewed-rules discussion.** "Reviewed against original rules" (p. 22) and "Why the reviewed rules hurt the single prompts" (p. 19) say the same thing. Keep one.
- **p. 20, "Model for model".** It overlaps with "Where it does not pay" (p. 22). Merge them.
- **p. 13, "A public benchmark" (ShARC).** No claim rests on it. Move it to the Supplement and keep one sentence.

### The first page

- **It does say what is new:** separating reading from deciding, with a third value and exact deferral, framed as design science.
- **It does not say why an information-systems reader should care.** There is no organisational stake: the cost of wrong requests, the audit trail, or the regulatory context.
- It spends its last third on a numerical abstract.
- *Fix:* add one sentence of stakes (see M1).

### Figures and tables

| Item | Verdict |
|---|---|
| Fig. 1 | Keep. |
| Table 1 | Keep. |
| Table 2 | Keep. |
| Fig. 2 | Keep. Darken the grey "not needed" labels; they are barely legible in print. |
| Table 3 | Fix. Move it to Section 6.4, and split Unresolved into right and wrong (M2). |
| Fig. 3 | Keep. |
| Listing 1 | Keep, or cut (it duplicates F.5). |
| Table 4 | Keep. Reconcile "accepts or rejects facts" with the checklist-only claim (M7.2). |
| Table 5 | Fix the "exact deferral" row (N6). |
| Table 6 | Keep. Explain the reorder (N1). |
| Table 7 | Fix "document judgments" for theft (N11). |
| Table 8 | Fix. Separate the registered and post-review intervals (M6). |
| Fig. 4 | Fix. Theft intervals (M6), and the caption pointer to Table 16. |
| Table 9 | Keep. Its mixed units (percent and per claim) are labelled. |
| Table 10 | Keep. |
| Table 11 | Keep, or fold into the text (nine numbers). |
| Fig. 5 | Fix or cut. On theft the labels "Rules in context" and "Rules in context, original rules" sit beside two dots about USD 0.0007 apart, and it is unclear which dot is which. The leader lines cross. The theft intervals have the same problem as Fig. 4. Fig. 4 and Table 7 already carry the information. |
| Figs. 6–7, Tables 12–25 (appendix) | Keep. Table 17's "p" column mixes calibrated p-values and bootstrap shares. Use a separate column header for the non-inferiority rows. |

---

## 5. Recommendation

**Minor revision.** The rescoping is real and the new analyses are careful. With one exception, every remaining problem is wording, a pointer, or a number that already exists in the authors' files. The exception is the undisclosed hypothesis reorder that made H3 testable. It must be disclosed, but it was made before any sealed datum was read, so it does not invalidate the test.

**To reach acceptance:**
1. Disclose the original hypothesis order and the reason for the change, and state that under the original order H3 (tenancy against the frontier model) would not have been tested (N1).
2. Rewrite the abstract's mechanism sentence and its H2/H3 sentence (claims 2 and 4). Qualify H1's reviewed rules as made "by editors who knew the test conditions".
3. Fix Principle 1's 0.83 (use the 33-claim value), and state in Principles 2 and 3 which evidence is registered.
4. Add a declaration of interests and roles, the current merge status, an ethics statement for the expert study, and the identity of the conference version with its delta.
5. Fix the interval inconsistencies:
   - Fig. 4 and Fig. 5 theft bars;
   - Table 23 against Table 8;
   - the two "ordinary" estimates.
6. Fix the pointers (N5, minor item 16), Table 5's exact-deferral row, the two latency statements, and Table 7.
7. Explain the 41% theft checklist differences between the full product and the checklist-only setting, using a full-against-full run baseline. Reconcile "can affect the checklist" with Table 4.
8. Cut or merge the six paragraphs listed in Section 4, and move Table 3 to Section 6.4.
