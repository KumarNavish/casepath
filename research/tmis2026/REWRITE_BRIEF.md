# Rewrite brief, version 4 (planner, 2026-11-12)

Binding for the writer and the figure maker. It supersedes the structure and
the thesis of `PAPER_BLUEPRINT.md` (v3.1); the terminology and style table of
that file (§6) and every "never claim" line stay binding. `REVISION_BRIEF.md`
and `FINAL_FIX_BRIEF.md` stay binding wherever this brief is silent: no
disclosed limit, failure or irregularity may disappear in the cut.

Why a rewrite: an outside review of the status (eight points) and the
analyses made in answer to it (`analysis/study3_feedback.md`,
`analysis/decomposition.md`, `analysis/rule_lint*.md`, `cleanroom/`). The
registered results do not change. What changes is what the paper leads with,
what it shows, and its length.

## 1. Thesis and headline

**The model reads and quotes; code decides; what the file leaves open is
held. With the same model, the same rules and the same file, this design
holds what a prompt that applies the rules does not hold, at every budget we
tried.**

The headline verb is **holds**, not "wins". Lead with the open-fact results,
then the error counts:

- Tenancy, files with an open fact or a denied or open defining event (56 of
  96 claims): 0.34 strict unsafe errors per claim against 2.1 to 2.3 for
  every single-prompt design on either model (F1). Files with everything
  stated (40 claims): 0.22 against 0.19 (frontier prompt) to 0.40; no
  advantage over the frontier prompt there, and we say so in the same
  sentence.
- Theft, unresolved-fact pairs: 94% left otherwise unchanged against 27 to
  47% for every design that received the reviewed rules.
- Reference-held documents held: 97% against 48% and 35%.

All four cells of model × data set are shown in one table and one figure,
each with its error decomposition (§4 below). The frontier-model theft cell
reads "no advantage" (0.83 against 0.67 to 0.95), never "not shown" and never
softened; its decomposition is presented as a finding: with perfect facts the
rules still give 0.33; the rest is two over-broad rule conditions.

Same-model claim, stated exactly once in the abstract, the introduction and
the conclusion: on the cost-efficient model CasePath had the lowest mean
error of all designs in both data sets; the registered test confirmed it
against the single prompt in both and against two of three prior-work
strategies on theft; against self-consistency the lead (0.58 against 1.21)
gave p = 0.0625 and the hypothesis failed. On the frontier model, one run:
fewer errors on tenancy, no advantage on theft.

## 2. What the artefact is

The artefact of the paper is **the tested commit** (`6a72159c…`, source-tree
hash `03048020…`), to be archived with a DOI (`%% AUTHORS:` line for the
DOI). Its **core** is what the claims are about: several readings with exact
quotation, admission by agreement, code that executes the workflow with exact
deferral, and the rule lint. The brief, the process builder, the result
checker and the reply draft are parts of the product and **outside the
claims**: they could not change a scored checklist and produced no detectable
difference in errors; say that once, in Section 4, and remove design
principle 4 as a principle (it becomes one sentence of the limitations).
No claim may depend on the product's owners adopting any branch.

**Two design cycles** (Section 5, one page): cycle 1 built the core on
synthetic data (Studies 1 to 3). Cycle 2 is the deployment: a handler
workflow written from seven development files and the law, evaluated by a
protocol (Appendix B) whose primary endpoint is an archival comparison with
what the insurer did next at every decision point of four sealed files, with
five experts as secondary endpoint. Cycle 2 has no result in this paper; say
what will be reported and that only counts leave the insurer. Leave a
`%% AUTHORS:` line where development counts from the insurer could be cited
if the insurer approves; do not print them.

## 3. Structure and budget (main PDF about 35 pages; body at most 8,500 words)

1. Introduction (650). Problem in one paragraph with the mould claim; the
   idea in three sentences; what the test showed (holds; four cells; what
   failed); three contributions (decision rule; artefact and design
   knowledge incl. the lint; pre-registered evaluation with the checks added
   after review).
2. Related work (650). Unchanged in content, tightened; Table 1 kept.
3. The decision rule (1,300). As now; the admission table; two propositions
   stated, proofs in Appendix A.
4. CasePath (1,000). Pipeline figure, hero figure; core against the rest;
   workflow format; **rule lint** defined here in one paragraph (what it
   flags, that it needs no reference answers).
5. How the design was found (500). Two cycles; root-cause table.
6. Evaluation (3,300). Subsections, each opening with its finding:
   6.1 Data, designs, freeze (incl. timeline table, who had seen what, the
       reorder 38 minutes before the freeze) — 550.
   6.2 Registered outcomes: the hypothesis table with three added columns
       (outcome under the order of 21:26, under the first draft's order,
       under Holm), labelled "not registered"; H4's test stated exactly
       (exact sign-flip over nine clusters, smallest attainable p 0.0039,
       returned 0.0625); one sentence on stories as clusters — 450.
   6.3 All four cells, with decomposition (Table + `fig_main` rebuilt as a
       2 × 2 small multiple or the existing figure with all cells) — 450.
   6.4 What is held: S against O files (F1), `fig_share` (F2) with the
       sentence that the real share is not known to us (`%% AUTHORS:` line
       for the insurer's count if supplied); open-fact results; the cost in
       unneeded holds — 500.
   6.5 The same budget: `fig_budget` (F4): readings k = 1, 2, 3 against
       self-consistency m = 1…15; more samples of the same prompt do not buy
       what the design buys (tenancy flat at 2.1; theft levels off near 1.0);
       matched-budget contrasts with their p values, the theft one not
       significant; cost and latency stated once — 400.
   6.6 Does the result depend on our reading of the rules? Clean room (two
       blind evaluators, 1,024 of 1,024, AI sessions, the recorded breach in
       one sentence), sensitivity table (F5) and the matched-workflow replay
       (F5b); state plainly under which reading the lead vanishes or
       reverses — 450.
   6.7 Rules as the limit, and a lint that finds them: decomposition of the
       frontier theft cell; lint flags; mutation test (planted over-broad
       conditions found / not found, false flags); "a flagged condition is
       treated as open" re-score; blind editors could not agree on one
       narrowing; needs a jurist — 500.
7. Discussion (900): three design principles, each with evidence and
   boundary condition; "For an organisation" (120 words, concrete: who
   writes workflows, what the lint and the record give them, what a hold
   costs a handler); **one** limitations subsection that every limit lives
   in (references from the implemented engine under one reading; synthetic
   data; AI-reviewed rules; reorder; one frontier run; cost several times a
   single prompt; unneeded holds; short files; agents outside the claims;
   AI sessions as evaluators and editors; no expert result yet).
8. Conclusion (150).

Appendices in the main PDF: A proofs (as now); B protocol of the deployment
study, cut to at most 900 words from the restructured
`expert_study/PREREGISTRATION_DRAFT.md` (primary archival endpoint, measures
(a)–(e), prediction rule, order after the freeze, stated limits; still
"version 1.0-rc, to be frozen on 20 November", never "registered"); C
deviations and irregularities of Study 3, at most 700 words (every item
kept, one line each, details in the supplement); D reproducibility and
generative-AI statement, at most 400 words. Everything else (data, robustness
tables, prompts, full deviations, Studies 1 and 2, the review analyses'
tables) moves to the supplement, which may grow. References to moved
material say "Supplement, Section …".

## 4. Results to use (sources; every number through a macro)

- Registered: `\sthree…` (unchanged).
- Review analyses: `\sthreeR…`.
- Feedback analyses: `paper/results/numbers_study3_feedback.tex`
  (`\sthreeF…`), from `analysis/study3_feedback.md`: F1 (S/O split), F2
  (share lines, crossover with the frontier prompt at 0 to 1.7% for strict
  errors and 3.7 to 7.2% for all deviations), F3 (orders, Holm), F4 (budget),
  F5/F5b (readings).
- Decomposition, lint on tenancy, flagged-as-open, mutation test:
  `analysis/decomposition.md`, `analysis/rule_lint*.md` and their macro file
  (named in the hand-over note appended below when those analyses finish).

Label every F and decomposition result "added after review, not registered".
The registered table and the registered voice come first in every subsection
that has both.

## 5. Corrections to carry through

- "wins on the mean" → "lowest mean error"; "not shown" → "no advantage".
- Holm: under Holm's correction over the five registered hypotheses, H1, H2,
  H3 and H5 would pass and H4 would not; we did not register Holm; the
  registered outcome stands (three confirmed, one failed, one not tested).
- Under the order of 21:26, H3 would not have been tested (already stated;
  keep).
- F5: under reading A1 (a denied defining event does not stop the process)
  with the product's workflow unchanged, the tenancy result reverses (not
  significantly for H2 and H3; significantly for two all-deviation
  contrasts); with A1–A4 together it reverses significantly. State this in
  the body, then what F5b shows.
- More readings lower strict errors and raise unneeded holds (k = 1 → 3:
  spurious holds 0.003 → 0.30 per claim; all deviations 0.55 → 0.74). This
  goes into 6.5 and the limitations, not a footnote.
- The clean-room evaluators and the rule editors are AI sessions; no person
  checked them.

## 6. Figures (seven in the body at most)

`fig_hero`, `fig_pipeline`, `fig_reconverge`, `fig_main` (all four cells),
`fig_share`, `fig_budget`, and one for 6.7 only if a table says it worse.
`fig_budget` is decluttered: label m = 1, 5, 15 and k = 1, 2, 3 only; no
label may touch a mark or another label; the frontier single prompt as one
open circle with a direct label. Rules of `PAPER_BLUEPRINT.md` §5 apply.
Every figure is rendered and looked at before it is delivered.

## 7. Deliver

Both PDFs built from clean, zero undefined references, no overfull box over
5pt; `analysis/verify_paper.py --paper-only` passing with the new macro files
in its list; word counts per section; page counts; a list of every limit and
irregularity of the previous version with the place it now stands (main or
supplement). The abstract is written by the planner; leave it as found.

## 8. Hand-over notes (results that arrived after §1–7 were written)

**F5b (matched workflow), `\sthreeFFiveB…` macros.** With the workflow
amended to each reading and the checklist recomputed from the stored
readings (no model calls; the unamended replay reproduces 285 of 286 stored
checklists), CasePath keeps a significant lead over both single prompts under
every reading: H2-style difference −0.66 (A1), −1.43 (A2), −2.54 (A3), −1.87
(A4), −1.30 (all four); H3-style −1.00, −1.01, −2.27, −1.59, −1.49. Write 6.6
in this order: (1) clean room, identical; (2) F5, the product's unchanged
workflow scored against other readings: reverses under A1 — this measures the
workflow, and shows that a workflow written under the wrong reading is wrong
in every affected file; (3) F5b: the design follows whatever reading the
workflow encodes, and the lead holds, smaller under A1 and A2. State the
caveat in the body: the baselines were not re-run; their prompts carried the
registered rule text; under A1 this favours them, under A3 and "all four" it
works against them, so those two rows are upper bounds and only A1, A2 and A4
are read as evidence. What the lead consists of: under A1 the open-event
claims; under A2 the denied-event claims.

**Decomposition (`analysis/decomposition.md`).** Every cell of the product
splits exactly into rule, routing, document judgment, reading and hold
(interaction remainder 0). Tenancy, strict: cost-efficient 0.31 = routing
0.05 + document judgment 0.08 + reading 0.17 + hold 0.02; frontier 0.30 =
0.08 + 0.10 + 0.12 (document, reading, hold). Theft: cost-efficient 0.58 =
rule 0.33 + reading 0.09 + hold 0.16; frontier 0.83 = rule 0.33 + reading
0.25 + hold 0.25. Single prompts have no observable stage: report their
errors by kind (denied-event claims: 4.4 to 5.9 unnecessary requests per
claim; open-event claims: 4.0 to 6.1 premature requests). One table in 6.3,
the per-subset tables in the supplement.

**Lint (`analysis/lint_followup.md`).** Say all of this, in this voice:
- Mutation test (one model, one run, USD 0.15): six over-broad conditions
  planted, six flagged; three of them were already flagged with their
  original wording, so the informative count is three of three. Three of
  five untouched conditions were flagged in both arms. On the Study 3
  tenancy claims the lint flags eight of ten (cost-efficient) and nine of
  ten (frontier) conditions without any mutation, because those claims were
  built with several true branch facts each and are not ordinary cases.
  Conclusion: the lint detects blunt over-breadth; its false-alarm rate is
  unknown and needs files in which the condition is known not to apply.
- "A flagged condition is treated as open", theft, stored readings, the
  model's own flags (in-sample): frontier 0.83 → 0.53, below both frontier
  prompts (0.95, 0.67); all unresolved pairs unchanged; cost-efficient
  0.58 → 0.57. Cost: the rule error rises from 0.33 to 0.44; three to five
  more documents are held in every case and the handler gets three to six
  more questions per claim.
- The same with flags computed out of sample (development runs only; the
  frontier flags come from four off texts at an earlier commit whose reading
  form was checked identical): frontier 0.83 → 0.78, still above the
  frontier prompt with the original rules (0.67); the development flags
  miss the traces condition, which carried most of the in-sample gain. No
  paired difference is significant (p 0.14 to 0.67 over nine clusters). So
  the remedy does not survive out of sample; say so in one sentence.
- The lint is presented as a diagnostic with these limits, not as a tested
  remedy. No new paid run was made for the frontier theft cell: with nine
  clusters a difference of 0.53 against 0.67 cannot be confirmed.

**Macros.** `paper/results/numbers_study3_feedback.tex` (`\sthreeF…`) must be
input in both documents and added to `verify_paper.py`'s regeneration list
(`analysis/make_numbers_study3_feedback.py`). Decomposition and lint numbers: `analysis/posthoc_numbers.tex` (`\spost…`,
written by `analysis/lint_followup.py`, tests in `analysis/test_posthoc.py`);
copy it to `paper/results/numbers_posthoc.tex` by a step added to
`verify_paper.py`'s regeneration list, and input it in both documents.

**Abstract.** Rewritten by the planner on 2026-11-12 (uses `\sthreeFOne…`).
