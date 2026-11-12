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

1. **Paper** for ACM TMIS: 59 pages plus a 27-page supplement. Design-science
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
| Cost-efficient | Theft | 0.58 | 1.21 (self-consistency) | wins on the mean; p = 0.0625, so that hypothesis failed |
| Frontier | Tenancy | 0.30 | 1.86 | one run, descriptive |
| Frontier | Theft | 0.83 | 0.67 to 0.95 | **not shown** |

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
