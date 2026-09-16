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

---

## Amendment A1 — 2026-09-16 — the primary intervention becomes e07

**Made before any confirmatory case was run or read, and before the development e03 results were read.** The
reason is structural and is computed from the reference contract alone, with no experimental outcome involved.

A document is withdrawn only when **every** decision requiring it is settled. Reading that off the contract:

| intervention | decisions it settles | documents it can withdraw |
|---|---|---|
| `e03` the notice does use the prescribed form | D4, D7 | **0** |
| `e06` the tenant did challenge within 30 days | D3 | 1 |
| `e07` the tenant did not challenge within 30 days | D3, D11, D12 | **6** |

`e03` cannot withdraw anything. `rent_increase_official_form` is required by eight of the twelve decisions, so
settling the form question releases nothing, and D7 requires no document at all. A withdrawal-recall comparison on
`e03` would have measured zero against zero and told us nothing about any arm — it would have triggered this
preregistration's own "uninformative" clause for a reason that was knowable in advance and that I failed to check
when writing it.

**Amended plan.** The primary outcome is unchanged — withdrawal recall, B5 against B1, paired by case, bootstrapped
over scenarios — but the intervention is `e07`: a minimal factual addition establishing that the tenant did not
bring a challenge to the conciliation authority within 30 days. Expected withdrawal is 6 documents where the
contract leaves those decisions open.

`e03` is retained as a **secondary** probe in the opposite direction. Settling the form as valid opens the
challenge branch, so it should *add* documents rather than remove them; it tests that the arm does not merely
shrink its request whenever a fact arrives. Reported descriptively, carrying no inference.

**What this amendment does not do.** It does not change the arms, the metric, the split, the frozen method, or the
criteria for support and refutation. The confirmatory scenarios remain unread.

---

## Amendment A2 — 2026-09-16 — the confirmatory run is withheld, not run

**Made before any confirmatory case was run or read.**

The primary outcome is structurally determined to be 0.000 for B5 on every probe available, computable from the
frozen contract and the frozen graph without running anything. On `e07` the contract releases six documents, all
of them D12's; B5 can release one, `conciliation_request`; the sets are disjoint. The full computation and its
cause are in `WHY_THE_CONFIRMATORY_RUN_IS_WITHHELD.md`.

Running the confirmatory set would consume the only clean held-out data to observe a predetermined zero, and would
present a structural fact as an empirical result. It is therefore **not run**. The six confirmatory scenarios
remain unread.

This preregistration is **not** void: the method, split, metric and criteria stand. It is suspended pending the
method changes that would make the primary outcome attainable — obligation coverage across nodes, and a node for
the substantive OR 269/269a determination the graph currently omits. When those are made on development data, this
preregistration is rewritten, the changes are logged, and only then is the held-out set read.
