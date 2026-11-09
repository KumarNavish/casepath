# Study 2: CasePath v2 and its confirmatory test (design, 2026-11-09)

Status: DRAFT. It becomes binding when it is copied to `ANALYSIS_PLAN_STUDY2.md`
and committed; that commit must precede every model call on fresh data.

## Why

Study 1 (the pre-registered comparison in `ANALYSIS_PLAN.md`) found no accuracy
advantage for executing rules and traced each weakness to a specific cause in
CasePath's own machinery. Study 2 fixes those causes and tests the fixed system
once, on cases no model has seen, against the strongest baseline given the same
knowledge.

## CasePath v2: four changes, each answering one root cause

| # | Root cause found in Study 1 | Change | Where |
|---|---|---|---|
| V1 | Extracted rules are executed unchecked: 5 of 98 theft rules cause 37 of 38 wrong changes | **Verified induction.** Every extracted rule is checked against its cited passages by a blind verifier; flagged rules are repaired with the product's existing typed repair operations (split a joint route into alternatives, drop an unsupported document, bind a condition to a cited proposition) and re-verified; a rule that still fails is quarantined (not executed, its documents go to a handler note). No labels, no case outcomes. | `harness/v2/induce.py`, reusing `rule_verify.py`, `refinement_repairs_v1` |
| V2 | Silence is treated like doubt: facts a claim never mentions become questions (552 of 752 unresolved rows carry no citation) | **Sourced presumptions.** A rule pack may state, with a source clause, what an unstated fact is presumed to be. A presumption applies only to an unresolved judgment without citation; it is recorded as a presumption and a later statement overrides it. A fact the claim raises but leaves open is still held behind a question. | templates + `harness/v2/presume.py` |
| V3 | The verifier rejects correct verdicts without evidence and contradicts itself on the category | **Evidence-bearing verification.** A rejection counts only if it quotes text from the case that contradicts the verdict (exact span); the family is admitted when the verifier affirms it. | `harness/v2/verify.py` |
| V4 | Strong Kleene evaluation holds documents every completion requires | **Exact deferral** as the execution mode. | `harness/casepath_tenancy.py::supervaluate` (exists) |

A fifth component makes the knowledge base evolve:

| V5 | No path from a handler's correction to a rule that later cases use | **Correction-driven repair.** A handler correction of one request is traced to the rule or presumption that produced it; the system proposes a typed repair, checks it against the cited sources and against all earlier corrected cases (regression), and admits it for later cases. | `harness/v2/evolve.py` |

v2 is built in the experiment layer first. Porting it into `casepath-api`
(with the repository's sealing procedure) follows only after Study 2.

## Fresh data (built and sealed before any design runs on it)

- **Theft.** New stories (settings) combined with the nine fixed condition
  sentences and the six open-condition sentences; references from the frozen
  source contract. No model output is consulted when stories are written.
- **Tenancy.** New claims from a new, released generator: flag combinations
  not used in the 150 existing claims, messages written by a model that is not
  among the evaluated ones, a blind check that each message implies its flags,
  references computed by the engine from the true flags under a silence policy
  that the template states in a clause, and supplied documents of which some
  are sufficient and some are not (decided by the generator, recorded in the
  reference).
- Development uses only the existing development split (tenancy development
  families, theft story 0).

## Designs compared (all receive the same knowledge)

- **CasePath v2** (V1–V4), with gpt-6.1-terra and with gpt-6-luna.
- **Rules in context, same pack**: the model applies the rules itself and is
  given the same repaired rule pack and the same presumption clauses.
- **Rules in context, original pack** (theft): the Study 1 baseline as it was.
- **CasePath v1** (Study 1 configuration) for the ablation.
- Evolution experiment: **CasePath v2 + V5** against **Rules in context +
  correction memory** (the same corrections, in the same order, appended to the
  prompt).

## Hypotheses (to be frozen with margins and tests)

- **C1 Accuracy on extracted rules (theft).** v2 makes fewer wrong plus missed
  changes per pair than Rules in context with the same pack, and than Rules in
  context with the original pack.
- **C2 Safety and completeness on complete lists (tenancy).** v2's unsafe
  errors per claim, counting handed-over documents as missed, are not higher
  than those of Rules in context by more than a stated margin, and it requests
  at once a share of required documents within a stated margin; it holds
  documents only for facts the claim raises and leaves open.
- **C3 Cost-efficiency.** v2 with the cost-efficient model is not worse than
  Rules in context with the frontier model on C1 and C2 measures, at less than
  a third of the cost per case.
- **C4 Evolution.** After the same number of handler corrections, v2 + V5
  makes fewer errors on later unseen cases than Rules in context with
  correction memory.
- **C5 Ablation.** Each of V1–V4 removes the failure it targets (wrong changes
  from faulty rules; held documents from unstated facts; handoffs and rejected
  correct verdicts; documents held that every completion requires) without
  adding unsafe errors.

Statistics as in Study 1 after its corrections: units and clusters stated per
test, paired cluster-bootstrap intervals, exact sign-flip tests, Holm over the
primary contrasts, attainable p-values reported, handed-over documents counted
as missed in the headline measure, failed outputs as empty plans.

## Reporting rule

Whatever the outcome, Study 1 and Study 2 are both reported in full. If v2
does not win a contrast, the paper says so.
