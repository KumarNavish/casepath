# Constructive reduction: joint process identification + evidence acquisition (handoff §24)

Date: 2026-09-14. Scope: the candidate residual "identify the operative process from heterogeneous
sources while acquiring evidence, where process hypotheses are uncertain, source-grounded, shared
across cases, and acquisitions both resolve case facts and select the applicable process".

## Exact operations of the candidate
1. State: a finite set H of process hypotheses (template × activation), a fact/obligation state per h,
   a source-warrant set per element of h, a belief over H and over unresolved predicates.
2. Update: an acquisition returns a document; its extracted atoms update predicate beliefs and
   discharge obligations under every h that is still admissible.
3. Objective: reach a justified decision (all active obligations of the true h discharged) with
   minimal acquisitions / burden, never requesting outside the currently admissible obligations.
4. Information: sources (message, attachments, templates, authority passages), returns.

## Strongest same-information constructions (primary sources checked 2026-09-14)
- Context Gathering Decision Process (Kausik, Swaminathan, Kallus, arXiv:2605.07042, May 2026):
  POMDP framing of agentic context gathering with a persistent predicate-based belief state,
  explicit open predicates, hypothesis elimination and a programmatic exhaustion/stopping gate.
  Covers operations 1–2 and the stopping rule; the belief is over "necessary information" rather
  than over process hypotheses, but a hypothesis set is a special case of its predicate state.
- InfoGatherer (arXiv:2603.05909, Mar 2026): Dempster–Shafer evidential network over hypotheses
  built from retrieved documents; follow-up questions target network uncertainty; explicit
  representation of ignorance. Covers joint hypothesis/evidence belief with source grounding.
- EC² / HEC (Golovin, Krause, Ray 2010; Javdani et al. 2014, arXiv:1402.5886): test selection to
  determine the decision region (here: the obligation set) rather than the exact hypothesis, with
  O(log n) guarantees; dual-purpose observations are handled by the decision-region objective.
- Adaptive stochastic minimum-cost cover (Golovin & Krause 2011): when the required set depends
  on the latent h and observations reveal both, adaptive greedy is near-optimal.
- Learning-to-Measure / active feature acquisition (arXiv:2510.12624; survey arXiv:2502.11067):
  sequential acquisition with unknown outcome models, in-context or learned.
- Source-warrant admissibility = a prior/constraint on H (no new operation). Shared structure across
  cases = a shared prior; within-class agreement was already shown not to establish correctness.

## Result
Every operation of the candidate is supplied by the composition CGDP/InfoGatherer belief state +
EC²/HEC or adaptive-cover acquisition + source-derived priors. No residual operation survives at
the algorithm level. Verdict for the §24 seam as a *method*: REDUCIBLE.

## What is not settled by reduction (empirical premise)
Whether current strong models actually fail on the frozen task in ways that structured process
state fixes at matched cost. F1 (this session) answers the first half for CasePath-Bench v3: the
structure and evidence planning are closed-form from the visible template (zero-model kernel
reproduces gold), so v3 cannot host that test. The remaining open premise is the longitudinal,
return-driven setting (E-series carriers), where the last measurements used a weak model.
