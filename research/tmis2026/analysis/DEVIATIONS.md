# Deviations from ANALYSIS_PLAN.md

One line each. "Post hoc" means decided after the held-out runs. Every number named here is computed by the scripts in this folder and exported as a macro.

- **Primary model.** gpt-6.1-terra is the pre-registered primary analysis. gpt-6-luna is the pre-registered model-sensitivity analysis. Holm is reported within terra (the planned family of five), within luna, and across all ten tests (`p_holm`, `p_holm_all10` in primary_tests.json).
- **H1 test type.** H1 is stated as non-inferiority ("no more than") but no margin was fixed. It is tested two-sided for a difference, and the paired cluster-bootstrap interval of the difference is reported instead of a non-inferiority decision.
- **Paired intervals were missing.** The plan promises 95% cluster-bootstrap intervals for paired differences, but only per-design intervals were computed. Paired intervals (joint resampling of clusters) are now computed for every contrast.
- **Bootstrap percentiles.** The bootstrap previously read the sorted resamples at indices 250 and 9,749. It now uses the symmetric linear-interpolation quantile; no rounded reported number changed.
- **Whole-claim handoffs (post hoc).** Tenancy outcomes are a four-way partition: requested / held behind a question / handed to a person / silently missed. Headline unsafe errors exclude handed-over documents. The strict sensitivity counts them as missed. The earlier code counted them as deferred without saying so.
- **H2 metric.** "Deferred" in the H2 test is held plus handed-over (the earlier code's meaning). Held-only is reported as a secondary contrast (`H2_held`).
- **H2, second part.** "CP-exact defers fewer than CP without more unsafe errors" was not in the Holm family. It is reported as secondary contrasts (`H2b_deferred`, `H2b_unsafe`).
- **Comparators for H3/H4.** The plan says "than D and R"; only CasePath vs R enters Holm. CasePath vs D is now reported as a secondary contrast (terra only: D was not run with luna).
- **"Strongest comparator".** The comparator was fixed a priori as Rules in context. Majority-of-3 is sometimes stronger:
  - luna H1: B1-SC3 0.089 vs B1 0.115 unsafe errors per claim;
  - terra H3: R-SC3 0.22 vs R 0.27 wrong changes per pair.
  
  Contrasts against majority-of-3 are reported as secondary.
- **H5 scope.** The plan compares CasePath with B1, D and R; the Holm test covers tenancy only (CP-exact vs B1). Theft test-retest contrasts are now reported as secondary. They are CP vs R (both models) and CP vs D (terra), with 10 clusters: the 9 conditions plus the three off texts as one cluster.
- **H5 variant.** The plan says "CP"; the test uses CasePath with exact deferral (CP-exact), the same model calls as CP.
- **Test-retest with failed outputs.** Agreement is averaged over the pairs of valid runs; a failed run is excluded rather than treated as an empty plan. The earlier code divided by 3 regardless, which only affected Direct, terra: 0.931 → 0.943.
- **Failed theft output (correction).** The plan scores a failed output as an empty plan. The theft scorer dropped the one failed output (Direct, terra, s2-on-PR_declined run 1); it is now scored as empty:
  - wrong changes 43 → 49, missed 28 → 29, F1 0.664 → 0.642;
  - 81 pair runs instead of 80.
- **H4 clusters.** Unresolved-fact variants exist for 6 conditions, so H4 has 6 clusters, not 9. The minimum attainable two-sided p is 0.031, and both models' H4 raw p equal that floor.
- **Dependence between theft clusters.** All pairs of a story share that story's off-case plan in each run, so one off-plan error repeats across conditions. The condition-level sign-flip test assumes independent clusters. Post-hoc sensitivity: each repeated wrong change is counted once per story×run (`H3dedup_*`).
- **Run pairing.** Off run r is scored against variant run r; the plan does not specify this. Post-hoc sensitivity: averages over all 9 pairings of off and variant runs (`sensitivity_all_pairings`).
- **H4 metric.** "Premature or changed" equals "any change": a premature request is itself a change.
- **Two-valued execution (post hoc).** Not in the plan. It is exploratory: the same rules executed on CasePath's recorded judgments with open facts read as false or true. Non-admitted families now count as handoffs, consistently with the CasePath rows; earlier they counted as silent misses.
- **Routing presumption (post hoc).** Presuming the routing fact once the family is admitted is a policy counterfactual on the recorded judgments (disclosed in the appendix).
- **Break-even cost of deferral (post hoc).** This analysis is new (break_even.json).
- **Holds of non-required documents (post hoc).** This descriptive measure is new; such holds are not penalised by any planned outcome.
- **Handoff causes (post hoc).** This descriptive classification is new (handoff_causes.json).
- **Tenancy self-consistency.** The document-wise majority ignores the runs' whole-claim handoff flag; only one luna B1 run was a handoff.
- **Decomposition B1 → B2 → CP without verifier → CP.** The plan names this decomposition, but it is reported descriptively without tests.
- **Error attribution.** The tenancy entries of error_causes.json (7 unnecessary requests from flipped verdicts, 15 misses judged sufficient) are recorded by hand. The theft entries are regenerated by theft_error_origin.py.
