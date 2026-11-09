# Analysis plan (fixed before the held-out runs)

Written 2026-11-09 after the development pilots and before any held-out call of
the new experiments. Prompts and code are frozen at the commit that adds this
file. Development material used for piloting: six tenancy claims from the
development split and story 0 of the theft cases.

## Research question

Should an LLM agent apply evidence rules itself, or should code apply
source-grounded rules to the agent's verified judgments of the case?

## Systems (same model, same inputs, same reasoning effort and output limit)

Model: `openai/gpt-6.1-terra`, reasoning effort `low`, strict JSON-schema
output, three independent runs per method and case (k = 3).

Tenancy (90 held-out claims, 17 families; latest CasePath scope):
- **B1 Rules in context**: rules in the prompt; the model writes the evidence plan.
- **B2 Model executes rules**: the model judges each condition, then applies the
  stated three-valued process semantics itself.
- **CP CasePath (product engine)**: typed interpretation, independent
  verification, deterministic admission (`validate_interpretation`), process
  compilation and `causal_process_v1.evaluate` (strong Kleene), unchanged.
- **CP-exact**: the same calls and admitted judgments, evaluated by
  supervaluation over the open flags (our fix for Kleene incompleteness).
- Derived without extra calls: CP without verifier; self-consistency (document-
  wise majority of the three B1 runs).

Theft (3 held-out stories: 27 off->on pairs, 18 off->unresolved pairs):
- **D Direct**: sources and catalogue in the prompt.
- **R Rules in context**: plus CasePath's extracted rules (ICLR "Graph context").
- **CP CasePath**: condition judgments, independent verification of true/false
  verdicts, exact-quote admission, executable rules with one route per
  requirement (flat rules: Kleene equals supervaluation).
- Derived without extra calls: CP without verifier; CP in the ICLR all-routes
  mode; self-consistency for D and R.

## Outcomes

Tenancy, per claim against the reference request set (documents in state
`missing` or `provided_insufficient`):
- unnecessary requests (requested, not required);
- silent misses (required, neither requested nor held);
- deferrals (required, held behind a question); questions asked;
- claim-level deferral (family not admitted).

Theft:
- off->on: correct, wrong (additions, withdrawals) and missed signed changes
  (frozen scorer `best_realization`), pooled precision/recall/F1, exact pairs;
- off->unresolved: premature request (a document of the open condition
  requested), other changes, held (an acceptable route held), stable (no change).

Both: test-retest agreement (mean pairwise Jaccard of request sets over the
three runs of the same input); cost (USD, tokens) and latency per case.

## Hypotheses

- H1 Safety (tenancy): CP-exact has no more unnecessary requests plus silent
  misses than B1.
- H2 Deferral (tenancy): CP defers more required documents than B1; CP-exact
  defers fewer than CP without more unnecessary requests or silent misses.
- H3 Changed facts (theft): CP makes fewer wrong changes than D and R.
- H4 Unresolved facts (theft): CP makes fewer premature requests and changes
  than D and R.
- H5 Stability: CP's test-retest agreement exceeds that of the model-written
  plans (B1, D, R).
The decomposition B1 -> B2 -> CP without verifier -> CP attributes differences
to explicit judgment, execution in code and independent verification.

## Statistics

Unit: claim (tenancy) or pair (theft), averaged over the three runs. Paired
differences between methods on the same units. 95% intervals by cluster
bootstrap (10,000 resamples of families for tenancy, of conditions for theft).
Two-sided cluster sign-flip permutation tests; Holm correction across the five
primary contrasts (H1-H5, CP-exact or CP versus the strongest comparator).
Effects are reported with intervals; no claim rests on a single p-value.

## Data rules

- A failed output (no valid JSON) is reported and scored as an empty plan.
- `dated_photos` is not scored in the three defect claims whose only evidence
  is an attached photo: no text-only method can read it.
- References are used only for scoring. They follow the admitted templates;
  the generator leaves the routing facts `termination_received` and
  `claim_received` implicitly true.

## Secondary analyses

- Model sensitivity with `openai/gpt-6-luna`, the model configured in the
  product's autonomous profile (CP and the strongest comparator, k = 3).
- Original ICLR judgments (gpt-5.6-terra) re-scored with the unified planner.
- Error tracing of CasePath's remaining errors to rules or judgments.
- Rule verification: an independent check of each extracted theft rule against
  its source passages; detection of the rules behind the known ICLR errors.
- sciCORE: judgment-error propagation, engine scalability, resampling.
