# Preregistration — confirmatory analysis, rent increase

Written before any confirmatory case is run or read. Development results are known and named below where they
motivate a choice; confirmatory results are not.

## What is being claimed

A checklist derived by locating a case inside a source-grounded process graph **responds correctly when a fact
settles a branch**: it withdraws the documents the process no longer needs and keeps the ones it still does. A
checklist predicted directly from the case has no mechanism for this — it re-predicts, and any change is
incidental.

Not claimed: that the induced graph is the unique process the sources imply (`INDEPENDENT_INDUCTION_DIVERGENCE.md`
shows it is not), or that the method predicts better static checklists (`STATIC_TASK_SATURATION.md` shows the
static task cannot separate methods on this corpus).

## Frozen method

Commit `c43bc22`. Induction, the exact-quote gate, the obligation compiler, and the case interpreter with
group-wise branch decisions and the contradiction-reverts-to-unresolved rule. Model `openai/gpt-5.6-terra`,
temperature 0, max_tokens 8000, provider pinned to `openai`. The induced graph is `graph_s2`, induced once on
development and reused unchanged. No component may be edited after this point; if one is, this preregistration is
void and must be rewritten with the change logged.

## Data

`splits/rent_increase_scenario_split.json`, frozen at commit `e28f1ed` before any confirmatory case was read.

- **Confirmatory: 6 scenarios, 30 cases.** S4 miscalculated, S5 reference-rate inconsistent, S6 reference-rate
  double-counted, S7 renovation unclear, S8 ancillary-charge reclassification, S9 provisional budget.
- Read **once**. No tuning, no re-running after inspection, no scenario dropped after the fact.

## Procedure

For each confirmatory case: the original narrative, and one variant with a minimal factual addition that settles
the prescribed-form predicate `e03`. Each of the 60 units is scored against the reference contract by three
independent adjudicators who see neither the graph nor any arm's output; a decision is settled on a two-of-three
majority, and ties fall open.

Arms: `b1_direct`, `b3_graph_then_list`, `b5_induced_graph`, matched on model, temperature, catalogue, held
documents and scope statement.

## Primary outcome

**Withdrawal recall.** Of the documents the reference contract stops requiring once `e03` is settled, the fraction
the arm stops requesting. Compared between `b5_induced_graph` and `b1_direct`, paired by case.

Interval: bootstrap resampling **scenarios**, not cases, 5000 draws, 95% percentile interval. Five cases of one
scenario are five variations on one fact pattern; resampling cases would shrink the interval by roughly √5 for no
reason but the corpus generator's choices.

## Secondary outcomes

Reported with the primary, not substituted for it: withdrawal precision; retention (of documents the contract
still requires and the arm already had, the fraction kept); static F1 against the modal-list oracle as a floor
check; the grounded rate of justification chains; adjudicator unanimity as a ground-truth quality check.

## What counts as support, and what refutes the claim

**Supported** if the withdrawal-recall interval for B5 − B1 excludes zero in B5's favour, *and* B5's retention is
not worse than B1's by more than 0.05. Correct withdrawal bought by dropping documents that are still needed is
not the claimed behaviour.

**Refuted** if the interval includes zero, or lies below it. Either outcome is reported as the result. The
development data already show two ways this can fail — a graph with no predicate where the intervention lands, and
contradictory branch verdicts that keep every branch alive — and the second was fixed on development. If the first
recurs on confirmatory scenarios it is a finding, not a reason to re-scope.

**Uninformative** if fewer than 15 confirmatory pairs have a non-empty expected withdrawal set. In that case no
comparison is reported for the primary outcome and the reason is stated. It would mean the intervention does not
bite on these scenarios, which is a property of the scenarios, not evidence about the arms.

## Multiplicity

One primary outcome, one comparison, one test. The secondaries are descriptive and carry no inference. If any
secondary is later promoted to an inferential claim, Holm correction is applied across the whole family and the
promotion is logged as an amendment.

## Amendments

Appended below with date and reason. Nothing above is edited after the first confirmatory case is read.
