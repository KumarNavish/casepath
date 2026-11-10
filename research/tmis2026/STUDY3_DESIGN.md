# Analysis plan, Study 3: confirmatory test of the CasePath product

Frozen before any design, baseline or scorer runs on `fresh2/`. This file is
committed as `ANALYSIS_PLAN_STUDY3.md`; `fresh2/guard.py` and
`harness/study3/run_all.py` refuse to touch the data unless that file is
committed unmodified. Date: 2026-11-10.

## 1. Question

Does the CasePath product, running on a cost-efficient model, request
evidence with fewer errors than the same model given the same rules under
every single-agent strategy from prior work, and how does it compare with a
frontier model given the same rules?

## 2. What is tested

**The product, not a research version.** The system under test is the
package `casepath` at commit `5ed0ea7cf951b799abfb393c5e0cfe066a3629bb`
(source-tree hash
`c39341b869c02f06a1e3f5b449e7dede1df0c908c71ae24dd613f7865f642847` from
`python -m casepath parity`). It is run through its HTTP
API as a case worker's browser runs it. The only inputs that differ from an
inside deployment are the workflows and the case files.

**Workflows.** Tenancy: the released templates with the silence clause,
converted by `harness/product/convert.py --sync`
(`harness/product/workflows/fresh-serial-sync`; the templates of `fresh2/`
and `fresh/` have the same hash). Theft: the reviewed rule base
(`rule_review/final/reviewed_rules.json`), converted by
`harness/product/convert_theft.py`. Both conversions are deterministic. The
driver checks them against the reference engines (`compare.py`: every truth
assignment; `compare_theft.py`: 3,000 random assignments) and refuses to run
if a decision differs.

**Settings.** Defaults of the frozen commit: full run scope, three readings
that must all agree on a value, and no presumption for a fact that any
reading finds raised and left open.
Model gpt-6-luna. Reasoning effort is passed to the model
(`CASEPATH_MODEL_REASONING=true`). Three runs per case. All settings are
recorded in `runs/study3/confirm/MANIFEST.json`.

## 3. Data (sealed; hashes in `fresh2/MANIFEST.json`)

- Theft: eight new stories (8–15), each a different kind of case document
  with the condition sentences embedded in running text; 72 changed-fact
  pairs and 48 unresolved-fact pairs; 128 texts.
- Tenancy: 96 new claims in 24 families, 48 English and 48 Swiss Standard
  German; 51 attachments, 25 sufficient. Three subsets, defined from the
  reference: 24 *denied-event* claims (the dispute's defining event is false
  and the claim says so); 9 *open-event* claims (the claim leaves the
  defining event open: 8 in families where it is false, 1 in a family where
  it is true); 63 *ordinary* claims, of which 23 raise one branch fact and
  leave it open.

No design, baseline or scorer has run on these data.

**Development data and what it showed.** Development used the Study 1 data,
`fresh/` (Study 2's data), and 16 probe claims in `dev_probe/` with a denied,
open or true defining event. The probe was written because `fresh/` has no
denied or open defining event and `fresh2/` does; its claims are new texts by
a writer that had not seen `fresh2/`. Theft stories 4–5 of `fresh/` were used
to develop the product; stories 6–7 were used once, for validation, before
the last review fixes, and re-run from cached readings after them. Development results are in `WORKLOG.md` and are not evidence.

Limits fixed here: tenancy references come from the engine and silence policy
that the product implements, and every design receives the policy clause;
theft reuses the nine conditions and the rule base of the earlier studies, so
it tests new documents, not new rules; all case texts were written by one
model that is not among the evaluated ones; the workflow wording of the
defining event ("a termination notice was received") is the template's and is
the same for every design.

## 4. Designs

All designs receive the same case files, the same catalogue of documents and
the same rules. All run on gpt-6-luna unless a row says otherwise, three runs
per case.

| Design | What it is | Calls per case |
|---|---|---|
| **CasePath** | the product at the frozen commit, default settings | about 26 |
| CasePath, checklist only | the same commit with `CASEPATH_RUN_SCOPE=checklist`: routing, the readings, document judgments, evaluation | about 4–9 |
| Rules in context | one prompt applies the rules (Study 2's design, with the reviewed theft rules) | 1 |
| Rules in context, frontier | the same prompt on gpt-6.1-terra | 1 |
| Self-consistency | five samples of Rules in context, a document is requested when more than half request it | 5 |
| Model executes rules | Chain-of-Logic style: the model names each condition's value and derives the documents in one answer | 1 |
| ReAct | a tool-using agent over the same workflow | about 3 |
| Two-valued | the product's own readings with unresolved taken as false, and separately as true; no model calls | 0 |
| Core | two readings and exact deferral outside the product (`harness/v2/cp4.py`), theft only | 2 |
| Rules in context, original rules | theft only, both models: the Study 1 baseline | 1 |
| CasePath on the frontier model, checklist only | the same commit with gpt-6.1-terra as its model; one run per case | about 4–8 |

Self-consistency with five samples costs at least as much as CasePath,
checklist only, on both regimes. No baseline is matched to the cost of the
full product; the checklist-only row is the cost-matched comparison.

## 5. Measures

Unchanged from Study 2 (`ANALYSIS_PLAN_STUDY2.md` §4), computed by the same
functions.

- Tenancy, per claim-run: **strict unsafe errors per claim** (unnecessary
  requests + missed + handed-over required documents + premature requests +
  silent skips). Also: requested share of required-now documents; held
  required-now documents; holds of documents the reference neither requires
  nor holds; and **all deviations per claim**, the sum of the strict errors
  and both kinds of wrong hold, so that a design cannot look good by holding.
- Theft, per changed-fact pair-run: **wrong + missed changes per pair**
  (frozen scorer). Per unresolved-fact pair-run: premature request of the
  open condition's documents; share of pairs left otherwise unchanged.
- Cost per case from the ledger; for the product, split into the calls that
  can decide the checklist and the rest.

A failed output is an empty plan. A handed-over claim counts as in Study 2.
The product's checklist is scored in the conservative view (every need it
marks required and missing is a request, including needs it added itself).

## 6. Primary hypotheses, tested in a fixed order

Clusters: the nine changed facts for theft; the 24 families for tenancy.
Runs, stories and claims are averaged within a cluster. Each hypothesis is
tested at the 5% level only if every hypothesis before it was confirmed
(fixed-sequence procedure). A hypothesis of fewer errors is confirmed when
the two-sided exact sign-flip test gives p < 0.05 and the difference favours
CasePath. The order was fixed from development results before the data were
opened: the contrasts that development supported most strongly come first. We use
a fixed sequence, not Holm's correction, because with nine clusters the
smallest attainable p of the exact test is 0.0039 and a five-way Holm
correction would leave little power.

- **H1. Theft, same model, same rules.** CasePath makes fewer wrong + missed
  changes per pair than Rules in context.
- **H2. Tenancy, same model.** CasePath makes fewer strict unsafe errors per
  claim than Rules in context.
- **H3. Tenancy, against the frontier model.** CasePath makes fewer strict
  unsafe errors per claim than Rules in context, frontier.
- **H4. Theft, every prior-work strategy.** CasePath makes fewer wrong +
  missed changes per pair than each of Self-consistency, Model executes
  rules and ReAct. Confirmed only if all three tests are significant (no
  correction is needed when all must hold).
- **H5. Theft, against the frontier model.** CasePath's wrong + missed
  changes per pair are not higher than those of Rules in context, frontier,
  with the same reviewed rules, by 0.25 or more. Non-inferiority by paired
  cluster bootstrap (10,000 resamples): p = share of resamples in which the
  difference reaches the margin; confirmed when p < 0.05.

**Where we expect the tenancy differences.** The probe predicts that H2 and
H3 are carried by the denied-event and open-event claims: there the rules
stop or hold the whole checklist, and a single prompt tends to request the
standard documents all the same. On the 63 ordinary claims we expect no
difference between CasePath and either baseline. Both subsets are reported
beside each tenancy hypothesis, so a reader can see whether this is what
happened.

Every contrast is reported with both values, the paired difference, its 95%
cluster-bootstrap interval, the number of clusters and of non-zero clusters,
and the smallest attainable p. The margin of H5 is that of Study 2. Results
of hypotheses that are not tested because an earlier one failed are printed
and labelled as outside the procedure.

## 7. Secondary analyses (reported in full, outside the sequence)

- Tenancy by subset (ordinary; denied event; open event): every measure for
  every design. On the ordinary claims: non-inferiority of CasePath to Rules
  in context, frontier, on strict unsafe errors (margin 0.10) and on the
  requested share (five points).
- Tenancy, same model: CasePath against Self-consistency, Model executes
  rules and ReAct on strict unsafe errors and on all deviations per claim.
- All deviations per claim: CasePath against Rules in context on both models.
- The 32 claims with an open fact (23 branch facts, 9 defining events):
  correct holds, premature requests and silent skips for every design,
  including Two-valued.
- Theft unresolved-fact pairs: premature requests; share left unchanged.
- Theft: CasePath against the frontier model, superiority test; H5 with the
  original rules as comparator; H1 with the original rules as comparator.
- CasePath against CasePath, checklist only, and against Core: differences
  with intervals. Needs added by an agent that entered the scored checklist.
  Cost per agent.
- Model for model: CasePath on the frontier model, checklist only (one run),
  against Rules in context, frontier, on both regimes, with intervals. On
  development data this design did not beat the frontier single prompt on
  theft (one run), so we state no hypothesis for it.
- Cost per case for every design; cost ratio to the frontier baseline.
- Run-to-run agreement; repeated errors counted once per story and run.
- English and German tenancy claims separately.

## 8. Reporting

All results are reported whatever their direction, together with Studies 1
and 2. Anything not specified here is labelled post hoc. Scoring and tests
are implemented in `analysis/study3.py` with `analysis/study3_spec.json`
(41 tests; it reproduces the stored development results). The study is run
by `harness/study3/run_all.py --data fresh2 --label confirm --k 3`. An
interrupted run resumes from the response cache with settings unchanged;
every invocation is logged in `runs/study3/confirm/RUNLOG.jsonl` and reported.
The product commit is not changed after this file is committed; if a defect
is found later, the results of the frozen commit are reported and the defect
is described.
