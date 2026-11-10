# Study 3: confirmatory test of the CasePath product (design draft, 2026-11-10)

Status: DRAFT. It becomes binding when it is copied to
`ANALYSIS_PLAN_STUDY3.md` and committed. That commit must precede every model
call and every scorer run on `fresh2/`; `fresh2/guard.py` enforces it. Items
marked [open] are fixed from development results before the copy is made.

## 1. Question

Does the CasePath product, running on a cost-efficient model, request
evidence with fewer errors than the same model given the same rules under
every single-agent strategy from prior work, and is it no worse than a
frontier model given the same rules?

## 2. What is tested

**The product, not a research version.** The system under test is the
package `casepath` at one frozen commit [open: commit and source-tree hash
from `python -m casepath parity`]. It is run through its HTTP API exactly as
a case worker's browser runs it (`harness/product/run_api.py`,
`run_theft.py`). The only inputs that differ from an inside deployment are
the workflows and the case files.

**Workflows.** Tenancy: the released templates with the silence clause,
converted by `harness/product/convert.py --sync`. Theft: the reviewed rule
base (`rule_review/final/reviewed_rules.json`), converted by
`harness/product/convert_theft.py`. Both conversions are deterministic and
are checked against the reference engines over all or 3,000 random truth
assignments (`compare.py`, `compare_theft.py`); both checks must pass at the
frozen commit.

**Settings.** Default run scope; model gpt-6-luna; reasoning effort passed to
the model (`CASEPATH_MODEL_REASONING=true`) [open: number of readings, if
round 4 makes it a setting]. Three runs per case.

## 3. Data (sealed; hashes in `fresh2/MANIFEST.json`)

- Theft: eight new stories (8–15), each a different kind of case document
  with the condition sentences embedded in running text; 72 changed-fact
  pairs and 48 unresolved-fact pairs; 128 texts.
- Tenancy: 96 new claims in 24 families, 48 English and 48 Swiss Standard
  German; 32 claims raise one fact and leave it open; 51 attachments, 25
  sufficient. In 8 families the dispute's defining event is false, and one
  claim in each leaves it open; 33 claims have an empty request set.

No design, baseline or scorer has run on these data. Development used the
Study 1 data, `fresh/` (Study 2's data, development data since that study
ran) and 16 probe claims in `dev_probe/` written to exercise a denied or open
defining event, a case type that `fresh/` lacks and `fresh2/` contains.

Limits fixed here: tenancy references come from the engine and silence policy
the product implements, and every design receives the policy clause; theft
reuses the nine conditions and the rule base of the earlier studies, so it
tests new documents, not new rules; all case texts were written by one model
that is not among the evaluated ones.

## 4. Designs

All designs receive the same case files, the same catalogue of documents and
the same rules. All run on gpt-6-luna unless a row says otherwise, three runs
per case.

| Design | What it is | Calls |
|---|---|---|
| **CasePath** | the product at the frozen commit, default scope | about 25 |
| CasePath, checklist only | the same commit with `CASEPATH_RUN_SCOPE=checklist`: routing, two readings, document judgments, evaluation | about 3–8 |
| Rules in context | one prompt applies the rules (Study 2's `B1v2p` / `Rv2p` with the reviewed rules) | 1 |
| Rules in context, frontier | the same prompt on gpt-6.1-terra | 1 |
| Self-consistency | five samples of Rules in context, majority per document; costs at least as much as CasePath, checklist only | 5 |
| Model executes rules | Chain-of-Logic-style: the model names each condition's value and derives the documents in one answer | 1 |
| ReAct | a tool-using agent over the same workflow | about 3 |
| Two-valued | the product's own readings, with unresolved taken as false (and, separately, as true); no model calls | 0 |
| Core | the two-reading core outside the product (`harness/v2/cp4.py`), theft only | 2 |
| Rules in context, original rules | theft only, both models: the Study 1 baseline | 1 |

## 5. Measures

Unchanged from Study 2 (`ANALYSIS_PLAN_STUDY2.md` §4), computed by the same
functions.

- Tenancy, per claim-run: **strict unsafe errors per claim** (unnecessary
  requests + missed + handed-over required documents + premature requests +
  silent skips). Also: requested share of required-now documents; held
  required-now documents; holds of documents the reference neither requires
  nor holds; and their sum with the strict errors, **all deviations per
  claim**, so that a design cannot look good by holding.
- Theft, per changed-fact pair-run: **wrong + missed changes per pair**
  (frozen scorer). Per unresolved-fact pair-run: premature request of the
  open condition's documents; share of pairs left otherwise unchanged.
- Cost per case from the ledger, split for the product into the calls that
  can decide the checklist and the rest.

A failed output is an empty plan. A handed-over claim counts as in Study 2.

## 6. Primary hypotheses, tested in a fixed order

Clusters: the nine changed facts for theft; the 24 families for tenancy.
Runs, stories and claims are averaged within a cluster. Each hypothesis is
tested at the 5% level only if every hypothesis before it was confirmed
(fixed-sequence procedure). The order was fixed from development results
before the data were opened. We use a fixed sequence, not Holm's correction,
because with nine clusters the smallest attainable p of the exact test is
0.0039 and a four-way Holm correction leaves almost no power.

[open: final order and comparators after round 4]

- **H1. Theft, same model, same rules.** CasePath makes fewer wrong + missed
  changes per pair than Rules in context. Two-sided exact sign-flip test.
- **H2. Theft, every prior-work strategy.** CasePath makes fewer wrong +
  missed changes per pair than each of Self-consistency, Model executes
  rules and ReAct. Confirmed only if all three two-sided tests are
  significant at 5% (no correction is needed when all must hold).
- **H3. Tenancy, against the frontier model.** CasePath's strict unsafe
  errors per claim are not higher than those of Rules in context, frontier,
  by 0.10 or more. Non-inferiority by paired cluster bootstrap (10,000
  resamples): p = share of resamples in which the difference reaches the
  margin.
- **H4. Theft, against the frontier model.** CasePath's wrong + missed
  changes per pair are not higher than those of Rules in context, frontier
  (same reviewed rules), by 0.25 or more. Same test.

Every contrast is reported with both values, the paired difference, its 95%
cluster-bootstrap interval, the number of clusters and of non-zero clusters,
and the smallest attainable p. The margins are those of Study 2.

## 7. Secondary analyses (reported in full, outside the sequence)

- Tenancy, same model: CasePath against Rules in context, Self-consistency,
  Model executes rules and ReAct on strict unsafe errors and on all
  deviations per claim; requested share with a five-point non-inferiority
  margin.
- Tenancy with and without the 32 claims whose defining event is false, and
  the 32 open-fact claims on their own: correct holds, premature requests,
  silent skips, for every design including Two-valued.
- Theft unresolved-fact pairs: premature requests; share left unchanged.
- H4 against the frontier model with the original rules; H1 with the
  original rules as comparator.
- CasePath against CasePath, checklist only, and against Core: differences
  with intervals. Which agents changed a checklist, and what each costs.
- Cost per case for every design; cost ratio to the frontier baseline.
- Run-to-run agreement; repeated errors counted once per story and run.
- English and German tenancy claims separately.

## 8. Reporting

All results are reported whatever their direction, together with Studies 1
and 2. Anything not specified here is labelled post hoc. Scoring and tests
are implemented in `analysis/study3.py`, written and checked on oracle and
perturbed plans of the development data before any output on `fresh2/`
exists. An interrupted run resumes from the response cache with settings
unchanged; every resumption is listed.
