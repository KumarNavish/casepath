# CasePath ICLR — Fable 5.1 state checksum (2026-09-14, recovered from local records)

Authority used: local mirror of the discovery loop (`Die Mobiliar/.discovery-loop`, 40 iterations, coordinator-work through 2026-09-13), the frozen evaluator repo (`casepath-iclr-eval/casepath-eval`), the Sep-12 paper folder (`ICLR_2027_CASEPATH_SYSTEM`), and the handoff. The Research OS gateway was NOT reachable from this session (hostname unresolvable; ssh/VPN records blocked by the tool classifier), so live ledgers/jobs were not reconciled.

## CURRENT SURVIVOR
None as a runtime method. Standing positives are baselines: (1) R81 ordinary same-model planner on 3 exposed carriers (6/6 roles, 18/18 supported readings, 3 unnecessary repeats); (2) R12 ordinary source compiler + exact planner at the finite optimum (16/16 episodes); (3) E76 six-arm action-conditioned pilot (3 carriers, gpt-5.4-mini): full ledger+compiler arm 7/8 critical, 2 unnecessary, 1 premature readiness vs direct 7/8, 3 unnecessary, 0 premature — retention FAILED. Sep-13 "source-reader probe" (joint answerability diagnostic, 6 calls) frozen but never admitted (gateway HTTP 504s).

## CLOSED DIRECTIONS (do not reopen under new names)
OEET/effect-conditioned commit (BENCHMARK_ONLY); fixed-graph PEG selection (factored robust POMDP); verifier-guided completion (SAT/SMT/CEGIS); sparse shared-warrant learning (= GBS, transcript parity); symbolic-resource bottleneck (ordinary BDD self-test passes; product slices are 8 predicates/256 worlds); repair lifting (Getafix; R13c non-executable); R28 transition-loss learner (identical argmin to CEGIS); R52/R53 process-first & condition-coverage prompting (no gain); R67/R68 role/purpose binding (no gain); R59 action-sufficiency (fails); R89 return rehearsal (no defensible advantage) and automatic source→obligation compilation (0/3 semantic); reread/reuse LP optimization (retired); future-aware EC2 / continuation classes (= EC2); counterexample→retrieval question (= C-GRiD); decision-ledger + obligation-cover compilation (E76 retention fail). Semantic-effect congruence benchmark: prospective, gated on product Iter38/40 (Iter40 = immutable FAIL).

## STRONGEST COMPARATOR
Direct end-to-end same-model planner with the same journal/sources (R81/E76 direct arm). For acquisition selection: EC2/HEC decision-region determination, robust/Bayes-adaptive POMDP (CGDP arXiv:2605.07042), InfoGatherer (arXiv:2603.05909). For process induction: NL2Plan, Planning in the Dark, active reward-machine inference. For source→obligation compilation: PolicyLR.

## FROZEN DATA (verified locally)
CasePath-Bench v3: 150 synthetic Swiss-tenancy cases, 3 subdomains, de-CH/en 75/75, 28 families; dev 60 = 11 families (4/3/4), hidden 90 = 17 families (6/5/6), family sizes 5–7, zero overlap. Dev gold: 2–5 scenario predicates (mean 1.27 true), unresolved branch edges at intake in 20/60 cases, 8–10 obligations per case (2–5 conditional), next action = execute step (45) or request lease contract (15). State-stress track: 48 paired variants (24 public). Evaluator runs offline (Python 3.13 venv); alias-rule zero-call floor: CER 0.54, branch acc 0.04, exact provenance 0.00.
No generative arm has ever executed admissibly on this benchmark (Nemotron/Together/gpt-5.6-sol/Sonnet-5 all failed the 2-call typed transport). The process-first causal hypothesis is UNTESTED, not refuted.

## EXACT RESIDUAL SELECTED
Section-24 seam, sharpened: does explicit process identification (template + predicate readings incl. UNRESOLVED) with deterministic obligation compilation change evidence behavior vs a strong direct planner at matched budget, and is the effect concentrated in cases with unresolved material branches? Algorithmic reduction: constructive to CGDP/InfoGatherer/EC2 (see REDUCTION note). What is NOT reducible by argument is the empirical premise: whether strong 2026 models still fail on the frozen task (executability, unresolved-vs-false handling, sufficiency transitions).

## FALSIFIER (cheapest, development only)
Run one strong-model arm through the frozen v3 evaluator on a family-stratified dev subset and the 24 public state-stress variants, with predeclared thresholds (see PREDICTIONS file). Saturation kills v3 as the method arena; systematic unresolved/sufficiency failures localize the residual on frozen data.

## NEXT CHEAP TEST
If saturated: decide benchmark-first vs acquisition-time mechanism using E76 carriers with a strong model. If residual: freeze the six-arm matched study on all 60 dev.
