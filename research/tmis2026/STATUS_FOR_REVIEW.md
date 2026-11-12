# CasePath TMIS paper: status for an outside reviewer (2026-11-12)

Written for a reader with no context. Everything is on branch
`claude/casepath-tmis-paper-20261109` of the CasePath repository, under
`research/tmis2026/`.

## What CasePath is

A product that prepares insurance claims for a case handler. Models read each
deciding fact of a claim file several times and must quote the file. Code
admits a value only when the readings agree, executes the organisation's rules
(a "workflow"), and holds every document request that depends on a fact the
file leaves open. Output: a checklist of documents to request, to hold behind
a question, or already present.

## What was done

1. **Paper** for ACM TMIS: 31 pages plus a 69-page supplement (rewritten on 12 November; was 59 and 27). Design-science
   framing, three contributions: the decision rule with proofs and scope; the
   artefact with four design principles; a pre-registered evaluation.
2. **Product fixes**: 63 commits on a branch of the product (two independent
   code reviews, every finding fixed with a test). Tested commit `6a72159c`.
3. **Confirmatory test (Study 3)**: analysis plan and product commit frozen
   before any run on sealed synthetic data (96 tenancy claims, 128 theft
   texts); five hypotheses in a fixed order; analysis run once.
4. **Two internal referee rounds** and a claims audit of the paper (major
   revision, then minor revision). All 409 number macros checked match their
   sources.
5. **Work after the test** on development data: diagnosis of the one result
   that did not go our way, a check on rules ("lint"), time and cost work.
6. **Release package**: one command reproduces every table from stored outputs
   in about eleven minutes without model calls; passes in a fresh clone.

## Results

Errors per case, lower is better. The claim is same-model: CasePath against
every baseline that uses the same model.

| Model | Regime | CasePath | Best same-model baseline | Status |
|---|---|---|---|---|
| Cost-efficient | Tenancy | 0.31 | 0.83 | all tests significant |
| Cost-efficient | Theft | 0.58 | 1.21 (self-consistency) | lowest mean; exact sign-flip test over nine clusters gave p = 0.0625, so that hypothesis failed |
| Frontier | Tenancy | 0.30 | 1.86 | one run, descriptive |
| Frontier | Theft | 0.83 | 0.67 to 0.95 | **no advantage** (the cell is printed in the paper) |

Registered hypotheses: three confirmed (theft and tenancy against the same
model; tenancy against the frontier single prompt), the fourth failed, the
fifth was not tested. On open facts CasePath held 97% of the documents that
should wait, against 35 to 48% for single prompts.

## What limits the result, stated in the paper

- Tenancy references come from the engine CasePath itself implements, and the
  tenancy lead sits in 33 of 96 claims whose defining event is denied or left
  open, a case type we designed into the test.
- All data are synthetic; the theft rules were reviewed by AI sessions, not
  jurists.
- The order of the hypotheses was changed 38 minutes before the freeze on
  development evidence; the third confirmation depends on that.
- Cost: several times a single prompt on the same model (under half a cent to
  a few cents per case). The agents that cannot decide the checklist produced
  no measurable gain in it.
- Frontier-model theft: with perfect facts the rules still give 0.33 errors
  per pair; the rest comes from two over-broad rule conditions that a frontier
  model reads literally. A lint finds them without reference answers; two
  blind editors could not agree to narrow one of them. It needs a jurist.

## What is open

1. Three legal questions on the theft rules (in
   `rule_review/lint/final/RECONCILIATION.md`).
2. The product has since moved on without the tested commit. A rebased branch
   (`claude/casepath-internal-paper-sync-20261111f`) is offered; the product's
   owners decide by their own check on real files by 15 November. Either way
   the product will differ from what was tested, so the test should be
   repeated on the frozen product with new sealed data.
3. The study with five claims experts on three real files has not run. Its
   protocol is in an appendix (`expert_study/PREREGISTRATION_DRAFT.md`),
   version 1.0-rc, to be frozen on 20 November.
4. Facts only the authors can supply: conflict of interest, conference-version
   disclosure, ethics statement, licences, release choice.
5. The latest reframing (same-model claim, "After the test" subsection) has
   not had an independent referee read.

## Where to look

| What | File |
|---|---|
| Paper and supplement | `deliverables/CasePath_TMIS.pdf`, `CasePath_TMIS_supplement.pdf` |
| Frozen plan and registered results | `ANALYSIS_PLAN_STUDY3.md`, `analysis/study3_results_fresh2_confirm.md` |
| Analyses added after review | `analysis/study3_review.md` |
| Referee reports and claims audit | `analysis/review/` |
| Diagnosis, lint, rule review | `analysis/theft_diagnosis.md`, `analysis/rule_lint.md`, `rule_review/lint/` |
| Time and cost work | `runs/speed/` |
| How each earlier criticism is answered | `deliverables/REVIEW_RESPONSE_CHECKLIST.md` |
| Evidence and remaining requirements | `deliverables/EVIDENCE_AND_REMAINING_REQUIREMENTS.md` |
| Day-by-day record | `WORKLOG.md` |

## Where feedback would help most

1. Is the same-model claim, with one cell not shown, the right headline, or is
   there a sharper framing the evidence supports?
2. Does the tenancy result survive the objection that the references come
   from the product's own engine? What analysis or data would answer it?
3. Is "the limit moves to the rules, and a lint plus a jurist finds them" a
   contribution or an excuse? How should it be tested?
4. What is the smallest further experiment that would most strengthen the
   paper, given few remaining credits and no model stronger than the frontier
   one?
5. Which sections are still too long or unclear for a first-time reader?

## Added on 2026-11-12, after outside feedback (all post hoc)

- Two blind evaluators reproduced the tenancy references exactly (1,024 of
  1,024). With the workflow amended to each of four rejected readings of the
  rule text, the lead holds under every one; with the workflow unchanged it
  reverses under one of them.
- The tenancy lead sits in the 56 claims with an open fact or a denied or open
  defining event (0.34 against 2.1 to 2.3); on the other 40 there is no
  advantage over the frontier prompt (0.22 against 0.19).
- Self-consistency does not improve with more samples (1 to 15); at a matched
  budget CasePath leads on tenancy (p 0.0006) and on theft (p 0.13).
- Under Holm's correction four of five hypotheses would pass.
- Frontier theft: 0.83 = rule 0.33 + reading 0.25 + hold 0.25. Treating
  lint-flagged conditions as open gives 0.53 in-sample and 0.78 with flags from
  development data: the remedy does not survive out of sample.
- The lint finds planted over-broad conditions (three of three new) and has no
  usable false-alarm rate on designed data.
- The deployment protocol now has an archival comparison on four sealed real
  files as primary endpoint.

Details: `analysis/study3_feedback.md`, `analysis/decomposition.md`,
`analysis/lint_followup.md`, `cleanroom/README.md`, `REWRITE_BRIEF.md`.
- Third independent referee round on the rewritten paper: major revision,
  then, on the revision, minor revision with every item since closed
  (`analysis/review/REFEREE_REVIEW_ROUND3.md`, `REFEREE_ROUND3_CHECK.md`).
  The paper now leads with the registered tenancy result (0.31 against 2.14
  and 1.86), claims "holds" for tenancy only, and gives cost as 20 to 42
  times the same-model prompt.

## Added on 2026-11-12, later: a benchmark from public rules (development)

- Paper: new Section 7 (about 1.3 pages) and Supplement S16. Main paper 29 pages, supplement 74.
- Three rule sets (tenancy, theft, dismissal) with 177 rules, each citing a
  verbatim public passage, checked by a second reader; one stated convention
  for unmentioned facts; references on which the engine and two blind
  evaluators agree in 1,240 of 1,240 decisions; 173 generated development
  files (180 designed, 7 dropped).
- Lint with planted defects: 0 of 47 untouched conditions flagged, 10 of 19
  blunt widenings detected (2 not assessable), 0 of 3 subtle ones.
- First use: 134 product errors assigned one cause each; repairs were general
  rules checked by the second reader, with no reference changed. The product's
  errors per file on the repaired benchmark are in the supplement only
  (development, in-sample; tenancy incomplete). No baseline ran on the
  benchmark, so the paper makes no comparison from it.
- Steps 3 to 5 (not approved) would add a second design cycle with baselines
  on development files, a timestamped freeze, and one sealed run on new files:
  the first fair comparison on this benchmark.
- Details: `study4/`, `deliverables/EVIDENCE_AND_REMAINING_REQUIREMENTS.md`.
