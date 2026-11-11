# Final fixes after the second referee round (2026-11-11)

Input: `analysis/review/REFEREE_REVIEW_ROUND2.md` (read in full: status of
M1–M10, the minor items and claims still open, new problems N1–N12, the ten
weakest sentences with rewrites, the paragraphs it proposes to cut, the
figure and table notes). `REVISION_BRIEF.md` and `PAPER_BLUEPRINT.md` §6 stay
binding. The abstract is final (the planner wrote it); change it only if a
number in it is wrong.

Every item of the round-2 report is to be closed. Decisions for the ones that
need one:

**N1. The order of the hypotheses was changed before the freeze, and the paper
must say so.** Facts: the first draft of the plan (commit `71eaa9eb`, 10 Nov
19:17) ordered them theft same model; theft every prior-work strategy; tenancy
against the frontier model; theft against the frontier model. The final draft
(21:26) had five: theft same model, tenancy same model, theft every prior-work
strategy, theft against the frontier model (non-inferiority), tenancy against
the frontier model. At 21:51 (commit `482873e3`) the order became the frozen
one: theft same model, tenancy same model, tenancy against the frontier model,
theft every prior-work strategy, theft against the frontier model. Reason
recorded at the time: on development data the comparison with ReAct was the
weakest (one run, errors concentrated in one fact), and a failed hypothesis
blocks every later one, so the hypotheses that development supported best
were put first. This was 39 minutes before the freeze and before any design
or scorer had touched the sealed data. Consequence, to be stated plainly in
Section 6.3 and Appendix B: under the order of 21:26 the prior-work
hypothesis would have been tested third, would have failed as it did, and the
tenancy contrast against the frontier model would not have been tested; its
confirmation depends on an ordering decision made on development evidence
shortly before the freeze. Check the three commits to confirm these facts
before writing them (`git show 71eaa9eb:research/tmis2026/STUDY3_DESIGN.md`,
`984d2991`, `482873e3`); write what the commits show.

**M8, who had seen what.** State: the session that directed development,
drafted the plan and chose the open rule had written the test set's design
and read its description and counts (`fresh2/README.md`), not its texts; the
texts were read before the freeze only by the session that wrote them and by
the blind-check sessions. The development runs on the frontier model that the
reorder commit also contains used development data only. Merge status of the
tested commit: not yet confirmed by the product's owners at the time of
writing; keep the `%% AUTHORS:` line for an update.

**M3, M4, principle 1.** Compare like with like: on the denied- and open-event
claims use Model executes rules' value on those claims (from the subset
table), not its overall value. Say which mixes of claim types were computed
and that none is tied to an insurer's real intake, which we do not know. State
what the records show about tuning of comparator prompts: for each of Rules in
context, Self-consistency, Model executes rules and ReAct, when its prompt
text was written and whether it changed afterwards (use `git log -p` on the
harness files that hold the prompt texts; report the facts; if a prompt was
written during product development and run on development data before the
freeze, say so). The best single prompt on theft (frontier model, original
rules) appears wherever the theft comparison with the frontier model is
summarised in Sections 1, 7 and 8.

**M7.** Add a run-to-run baseline for "identical checklists": the share of
case-runs in which two runs of the same design on the same case produce
identical scored checklists (full product run pairs, checklist-only run
pairs), per regime, so that the 59% on theft can be read against it. Add it
to `analysis/study3_review.py` as R7b with a test, regenerate the review
outputs and macros. Fix "only the components that can affect the checklist":
the checklist-only run skips the brief, the result checker and the fact
checks of the source checker (read the code at the tested commit for what it
skips and say exactly that); correct Table 7's entry for theft (no document
judgments ran there; say why).

**N7, principle 2.** Evidence must be about being better, not about being
different. Use the registered two-valued rows (strict errors with unresolved
taken as false and as true, against CasePath's) for exact deferral against
two-valued evaluation. For strong Kleene evaluation, add R11b to the review
analyses: score the strong Kleene checklists computed from the product's
stored facts against the reference (strict errors, held required documents,
all deviations), on the claim-runs where the harness reproduces the product's
checklist, and state the result whatever it is. Move the fact-level accuracy
table out of Section 3 into Section 6 with a one-sentence pointer from
Section 3.

**M6.** Captions of Figures 4 and 5 say what the theft intervals are
(percentile bootstrap of each design's mean over nine clusters) and that they
under-cover. In the hypothesis table, the registered interval and the
post-review interval are in separate, labelled columns, or the post-review
one moves to the appendix table and the caption says so. Choose the cleaner.

**N2, N3, N4, N5, N6, N10, N11.** One value per quantity. The ordinary-claims
estimates: use the family-mean values of the registered subset rows
everywhere in the body and say once that per-claim means differ in the second
decimal (appendix table). The "test mix" intervals of the reweighting table
are computed by a different method than the registered intervals: explain in
the table note, or replace the test-mix row's interval by the registered one.
Latency: one statement, with the measured medians by regime. Pointers into
the supplement and between sections are corrected (check every `S-` reference
and every "Section", "Table", "Figure", "Appendix" reference in the body
against what it points to). Table 5: exact deferral was already evaluated in
Study 1; say what changed after Study 1 (it became the execution mode).
The theft evaluator check: one number, the one the script uses
(`analysis/check_fragment.py` once it exists, otherwise the script in
`harness/product/compare_theft.py`); state which check each appendix means.

**N8.** Units: "claim-run" (tenancy), "text-run" and "pair-run" (theft) and
"case-run" (either) are defined once in Section 6.2 and used accordingly;
"regime" is defined at first use or replaced by "data set".

**N9.** Appendix E says that the analyses added after review are a step of
`reproduce.sh` (the release worker has added it; check `RELEASE.md` and the
script, and describe what the step does and what it skips without the cache
archive).

**N12 and the rest of round 2's clarity list.** Section 6.4 is cut and merged
as the report proposes: at most ten run-in headings; the post-review results
are grouped under one heading "Analyses added after review" with short
paragraphs, each opening with its finding; details go to Appendix D. Apply the
ten sentence rewrites or better ones. Cut the paragraphs the report marks as
removable unless they carry a limit or a failure. First page: one sentence on
why this matters to an organisation (what a wrong or premature request costs
a handler and a customer; only what is plain without citation, or cite). The
"For an organisation" paragraph is made concrete or cut to what the evidence
supports. Figure and table notes of the report are applied.

**Still open from round 1** (minor 1, 9, 16; claims 2, 4, 17, 18): close each
as the round-2 report says.

**Authors' facts** stay as `%% AUTHORS:` comment lines: conflict of interest
and roles, conference version, ethics, tool name, licences, cache archive,
release choice, merge status.

Word budget: body at most 9,000 words; Section 6 at most 2,600.

Deliver: both PDFs built from clean in `paper/` (main, bibtex, supplement,
bibtex, then each twice more), zero undefined references and citations, no
overfull box over 5pt; `analysis/verify_paper.py --paper-only` passing; the
round-2 report's items listed one by one with "closed" and where, or the
reason it is not; word counts; page counts.
