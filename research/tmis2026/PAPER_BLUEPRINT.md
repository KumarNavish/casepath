# Paper blueprint, version 2 (planner's specification, 2026-11-10)

Binding for writers and figure makers. It replaces version 1. Every number
comes from a macro in `paper/results/numbers.tex` (Study 1 macros; Study 2
macros with the `st…` prefix; tables in `analysis/STUDY2_RESULTS.md`).
Deviations: `analysis/DEVIATIONS.md` (Study 1) and the irregularities listed in
§2 below (Study 2). The author chose: write the honest two-study paper now,
structured so that a Study 3 (expert-reviewed rules, new conditions) can be
added later.

## 1. Thesis

**Executing an organisation's rules over a language model's judgments does not
make evidence requests more accurate than a frontier model applying the same
rules. It makes the agent's uncertainty explicit and its errors systematic and
traceable, and it moves the limit on accuracy from the model to the rules.**

Two pre-registered studies carry this. Study 1 diagnoses: no accuracy
advantage, heavy deferral, and errors that trace to a handful of faulty
extracted rules. We fixed each cause we could fix without labels. Study 2 tests
the fixed agent once on fresh cases: the deferral and handoff costs are gone,
open facts are handled correctly, and accuracy still only matches the baseline
on clean rules and trails the frontier model on extracted ones, because
label-free rule repair did not work. What remains is rule review by people,
which the system's knowledge loop is built for and which this article does not
yet test.

Title: **Where the Uncertainty Goes: Executing Rules over LLM Judgments to
Request Evidence**.

Abstract (planner's draft; adapt with macros, at most 200 words):
"An agent that requests evidence for a claim must act on facts it does not yet
know. A language model that applies an organisation's rules itself settles
such facts inside its answer. CasePath separates the two steps: the model
judges each rule condition as true, false or unresolved, with a quotation, and
code executes the rules. We show that such execution never requests a document
that an unresolved fact could make unnecessary, and that evaluating over all
completions holds exactly the documents that depend on one. Two pre-registered
studies test what this buys. In Study 1, execution was no more accurate than a
frontier model applying the same rules, deferred 30% of required documents,
and reproduced the errors of five faulty extracted rules exactly. We traced
each weakness to a cause and fixed what could be fixed without labels. In
Study 2, on fresh cases, the revised agent requested as many documents at once
as the baseline and held correctly when a fact was open, but it won none of
four primary contrasts: it matched the baseline on hand-written rules and
trailed the frontier model on extracted ones. Executing rules makes an agent's
uncertainty and errors explicit and traceable; its accuracy is set by its
rules, which still need review."

## 2. Claims allowed

Formal: as in version 1 (F1 soundness in the flow fragment, relative to
admitted judgments; F2 strong Kleene over-holds, exact computation; F3 exact
deferral; F4 error fate, two kinds of judgment error, exact computation at
error probability 0.1).

Study 1 (pre-registered; primary model gpt-6.1-terra, secondary gpt-6-luna):
E1–E4 and M1–M6 of version 1, with these corrections from the figure work:
Rules in context repeated 14 of the 37 rule-caused errors, and 18 of its 22
wrong changes fall on the documents of rules 084 and 074 (it avoided the
errors of 042 and 003, not those of 084 and 074); the break-even ratio is in
deferred (held or handed-over) documents; 52 of Rules in context's 68 wrong
changes with gpt-6-luna are repeats of 13 items; on the open-fact theft pairs
no design requested prematurely.

From diagnosis to v2 (development data only, disclosed as development):
five root causes and what was done. Verified induction: 64 of 98 rules
flagged; 8 repaired and passing; 56 stay in force on a review queue; of the
five known faulty rules only one was partly repaired. Presumption clause for
silence. Admission by normalised quotation matching; handoff only when the
family is unsupported. The evidence-bearing verifier changed no plan and was
dropped. Exact deferral. The first v2 design (quarantine of unrepaired rules)
failed on development data and was revised; say so in one sentence.

Study 2 (pre-registered, fresh cases, plan frozen in commit b86ab9d before any
run):
- Primary contrasts, none confirmed after Holm correction: A theft, same
  model and pack (gpt-6-luna) 1.26 vs 2.03 wrong + missed per pair, difference
  −0.77 [−1.13, −0.35], raw p 0.020, Holm p 0.078; B tenancy, same model
  0.23 vs 0.20 strict unsafe errors per claim, no difference; C v2 on
  gpt-6-luna vs the frontier model with the original pack on theft 1.26 vs
  0.54, not non-inferior and worse (p 0.008); D tenancy cross-model 0.23 vs
  0.16, not non-inferior.
- Secondary, confirmed fixes: requested share non-inferior to Rules in context
  for both models (96.7% vs 95.4%; 97.9% vs 97.9%); held required-now
  documents per claim 0.014 (v2) vs 3.31 (v1); one handoff run per model; open
  facts: 64 and 62 correct holds of 66, no premature request, no silent skip
  (v1: 56 correct holds, 9 premature requests); no design requested
  prematurely on the unresolved-fact theft pairs.
- Secondary, not in v2's favour: with gpt-6.1-terra, v2 vs Rules in context
  with the original pack 1.17 vs 0.54 (p 0.016); same pack −0.48 (p 0.074);
  tenancy +0.02; unchanged-when-open 53% for v2 vs 99% for the frontier
  baseline with the original pack; the repaired pack hurt Rules in context
  (frontier model 0.54 → 1.65), so contrast A partly reflects a weakened
  comparator; v1 vs v2 on the primary measures not significantly different;
  evolution: v2 1.28 → 1.17, memory baseline 2.06 → 1.43, difference after
  learning −0.26 [−0.63, +0.19], one repair applied.
- Mechanism (post hoc where marked): v2's theft errors are systematic:
  counting each repeated error once gives 0.58 for v2 on gpt-6-luna, level
  with the frontier baseline (C becomes +0.05 [−0.25, +0.32]); the planned
  ablation "two readings agree" gives 0.72 (p 0.004 against v2); presumptions
  raise the requested share from 85.1% to 96.7% and cut spurious holds from
  2.38 to 0.05 per claim at no significant cost in unsafe errors; strong
  Kleene vs exact deferral made little difference on these claims.
- Cost: v2 on gpt-6-luna costs 0.08 of the frontier tenancy baseline and 0.32
  of the frontier theft baseline per case; on the frontier model v2 costs
  more per theft text than Rules in context.
- Disclosed limits and irregularities: tenancy references come from the same
  engine and silence policy v2 implements; misread messages were replaced, so
  claims are explicit; tenancy is near ceiling for all designs; the strict
  measure does not penalise over-holding; theft reuses the nine conditions and
  98 rules, and the repair pass was developed knowing which rules are faulty;
  the run was interrupted twice (a time limit, a container restart) and
  resumed from cache with the caps unchanged; transport retries and two helper
  scripts were added after the freeze; reader fixes were limited to file
  formats.

What the article does not show and must say plainly: that executing rules
beats a frontier model applying them; that label-free rule repair works; that
the knowledge loop improves accuracy. The route it identifies and leaves to
future work (Study 3): expert review of the queued rules, tested on new
conditions.

Never write: "as safe as" for a non-significant difference; "robust to the
model" as a general claim; any wording that presents a secondary or post-hoc
result as confirmed; "outperforms" without the comparator and the test.

## 3. Structure (target: at most 8,200 words of running text, Sections 1–8)

1. **Introduction.** The mould claim in one sentence, the rule, the open
   fact. The question. The answer in one paragraph (thesis), then one
   paragraph per study with its headline numbers. Relation to the earlier
   version in two sentences. Contributions: (i) the formulation with soundness,
   exact deferral and the error-fate analysis; (ii) the CasePath agent and two
   pre-registered studies reported with their failed hypotheses, including a
   fix-and-retest cycle on fresh cases; (iii) design knowledge: what executing
   rules buys, what it does not, and that rule quality is the binding limit.
2. **Background and related work** (existing text, lightly edited).
3. **Executing rules over judgments** (existing; running example becomes the
   mould claim; Fig. `fig_reconverge`, Fig. `fig_fate`).
4. **Study 1: is execution more accurate?** Design in brief (hypotheses, two
   regimes, designs, measures, statistics), results under the four questions
   of the existing results section, condensed. Fig. `fig_outcomes`,
   Fig. `fig_trace`. The detailed tables stay; move the cross-model chart
   (`fig_models`) to the appendix.
5. **From diagnosis to CasePath v2.** One table: root cause → evidence in
   Study 1 → change → what development data showed. One paragraph on the
   first v2 design that failed and why.
6. **Study 2: does the revised agent do better on fresh cases?** Data and
   freeze; designs; primary contrasts (table with values, differences,
   intervals, p, Holm p); what was confirmed as fixed; where it still loses
   and why (systematic errors, faulty rules in force, the frontier model's
   implicit repair); ablations; evolution experiment; cost.
   Fig. `fig_study2`.
7. **Discussion.** What executing rules buys and does not buy (three short
   paragraphs). Design principles (four, in the stated form). The knowledge
   loop as the remaining lever, with Fig. `fig_knowledge`, described as what
   the system does, not as evaluated. When to execute (table). For evaluation
   research (references encode a silence policy; fix-and-retest on fresh
   cases; conclusions are statements about a model). Limitations, short, each
   with its consequence. A sentence on the planned Study 3.
8. **Conclusion.** Five sentences.
Appendices: A original evaluation; B deviations (both studies); C data
(including the fresh datasets); D robustness and sensitivity (both studies,
`fig_models`); E reproducibility and use of generative AI (state the models
used to write the fresh claims and to render the interface screens);
F prompts.

## 4. Running example and Figure 1

The running example is the mould claim on the interface screens: mould in the
bathroom and the child's room, caretaker told by phone, "Our daughter has been
coughing for weeks; the paediatrician suspects a link with the mould. I do not
have a medical report yet." versus the open variant "…we do not know whether
it has anything to do with the mould and have not seen a doctor." The rule:
if the mould has affected someone's health, a medical report is required.
Carry it through Sections 1, 3 (the health-effects branch of
`fig_reconverge` is the same fact) and 6 (an open-fact tenancy claim from the
fresh data, described exactly). The theft example (the watch) may appear only
where theft rules are introduced.

## 5. Figures (one insight each; shared theme in `analysis/figtheme.py`)

Main text: `fig_hero` (real interface screens: one sentence, stated vs left
open), `fig_reconverge`, `fig_fate`, `fig_outcomes` (Study 1), `fig_trace`
(Study 1), `fig_study2` (new: Study 2 at a glance), `fig_knowledge` (real
screens, in the discussion). Appendix: `fig_models`. Captions state provenance
for the screen figures exactly as the figure maker drafted them.

`fig_study2`: the reader should see that the fix removed the deferral cost but
not the accuracy gap. Left: tenancy, held required documents per claim and
strict unsafe errors per claim for CasePath v1, CasePath v2 and Rules in
context (both models where run). Right: theft, wrong + missed per pair for
CasePath v2, Rules in context (same pack) and Rules in context (original
pack), both models, with intervals and the counted-once sensitivity as the
theme's subtle tick. No more than two panels; dot plots; theme only.

## 6. Terminology and style

As in version 1 (§4 and §6 there are restated here by reference: one term per
concept; outcomes requested / held / handed over / missed; unsafe error;
strict; primary / secondary analysis), plus: *Study 1*, *Study 2*; *CasePath
v1* (the Study 1 configuration) and *CasePath v2*; *verified pack*, *original
pack*, *review queue*; *presumption clause*; *fresh cases*. Style: plain,
exact, short; every paragraph leads with its point; numbers with
denominators; no filler, no stacked hedges, no rhetorical flourishes; British
spelling. Report failures in the same voice as successes.
