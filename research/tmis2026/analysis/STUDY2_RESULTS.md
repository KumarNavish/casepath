<!-- Narrative written by the analyst; tables below are generated from analysis/study2_results.json. -->
## 0. Summary

None of the four primary contrasts is confirmed after Holm correction.

- **A (theft, gpt-6-luna, v2 vs Rules in context with the same pack):** v2 makes fewer errors. The raw p is 0.020, but the Holm p is 0.078.
- **B (tenancy, same model):** there is no difference, and the point estimate favours Rules in context.
- **C (theft, v2 with gpt-6-luna vs the original-pack baseline on gpt-6.1-terra):** non-inferiority fails clearly (p = 0.9998). v2 is significantly worse: +0.72 errors per pair, two-sided sign-flip p = 0.008.
- **D (tenancy, cross-model):** non-inferiority is not shown (p = 0.36).

## Reader fixes made before scoring (file format only; no measure changed)

1. **Ledger key names.** The v2 ledger records the reused Study 1 methods under `exp="theft"`: method `R`, and `CP-interpret` / `CP-verify` for CPv1. The cost reader now maps these to the theft designs R and CPv1.
2. **Evolution file name.** The runner wrote `evolve_theft_gpt-6-luna_fresh_train4_eval567.json`, a single file holding all three runs. The reader now also globs this name. Its rows already carry `condition` and `run`.
3. **Ablation file layout.** The ablation runner wrote three files in the plans format, `ablations_{tenancy,theft,theft_origpack}_gpt-6-luna_fresh_heldout.json`, with keys `"<variant>|<case>|<run>"` and a `_note`. The reader maps the variant names:

   | File name | Analysis name |
   |---|---|
   | CPv2p-nopres | no_presumption |
   | CPv2p-kleene | kleene |
   | CPv2p-2read | two_readings |
   | CPv2p-origpack | original_pack |
   | CPv2p-origpack-full | original_pack_full |

   original_pack_full uses one extra gpt-6-luna judgment call per text for the 8 original-pack guards that the v2 pack does not judge. The two original-pack variants give identical results.
4. **Macro generation.** `make_numbers.py` skips cost entries that are not designs of §3, namely the evolution memory arm `Rv2p+mem` and the helper calls `origpack-extra-guards`. Without this, one macro name contained a `+`.

`analysis/test_study2.py` was rerun after these fixes, and all 30 checks pass. The scoring functions are unchanged.

## Irregularities in the files (none affects scoring)

- **Run counts.** No failed outputs, no ledger errors, and no duplicate ledger rows for fresh cases. Every arm has 3 runs per case.
- **Theft split.** All four theft stories are in the `heldout` plans files; there is no fresh `dev` file.
- **Evolution file.** It also holds per-arm plans, which the analysis does not use.
- **Handoffs.** Tenancy has 1 CPv2p handoff run per model and 4 CPv1 handoff runs.
- **Ledger tags.** The v2 ledgers mix v2 tags (`v2-tenancy`, `v2-theft`) with Study 1 tags (`theft`).
- **Variants equal to the main design.** The theft `kleene` variant is identical to CPv2p (flat rules), and the two original-pack variants are identical to each other.
# Study 2 results (ANALYSIS_PLAN_STUDY2.md, frozen `analysis/study2.py`)

Generated from `analysis/study2_results.json`. Values: theft = wrong + missed changes per pair (per pair-run, 4 stories x 9 changed facts x 3 runs = 108 pair-runs); tenancy = strict unsafe errors per claim (72 claims x 3 runs). Clusters: 9 changed facts (theft), 18 families (tenancy). Differences are a - b; lower is better unless stated. Intervals: paired cluster bootstrap, 10,000 resamples. p (sign-flip): exact two-sided over clusters. NI p: share of resamples with difference at least the margin (0 = none of 10,000).

## 1. Primary contrasts (Holm over A-D)

| | a | b | a value | b value | diff | 95% CI | clusters (non-zero) | p sign-flip | min p | NI margin | NI p | p used | Holm p | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | CPv2p (6-luna) | Rv2p (6-luna) | 1.259 | 2.028 | -0.769 | [-1.130, -0.352] | 9 (9) | 0.0195 | 0.0039 |  |  | 0.0195 | 0.0781 | not significant after Holm (raw p 0.020 favours v2) |
| B | CPv2p (6-luna) | B1v2p (6-luna) | 0.231 | 0.199 | +0.032 | [-0.083, +0.144] | 18 (12) | 0.6479 | 7.6e-06 |  |  | 0.6479 | 1.0000 | no difference shown (favours Rules in context numerically) |
| C | CPv2p (6-luna) | R (6.1-terra) | 1.259 | 0.537 | +0.722 | [+0.454, +0.981] | 9 (9) | 0.0078 | 0.0039 | 0.25 | 0.9998 | 0.9998 | 1.0000 | non-inferiority NOT shown; v2 significantly worse (superiority p 0.008 favours baseline) |
| D | CPv2p (6-luna) | B1v2p (6.1-terra) | 0.231 | 0.157 | +0.074 | [-0.069, +0.208] | 18 (13) | 0.3489 | 7.6e-06 | 0.1 | 0.3612 | 0.3612 | 1.0000 | non-inferiority NOT shown |

## 2. Secondary contrasts

| contrast | a | b | metric | a value | b value | diff | 95% CI | clusters (non-zero) | p sign-flip | NI p (margin) | favours |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A_terra | CPv2p (6.1-terra) | Rv2p (6.1-terra) | errors | 1.167 | 1.648 | -0.481 | [-0.843, -0.065] | 9 (9) | 0.0742 |  | a |
| B_terra | CPv2p (6.1-terra) | B1v2p (6.1-terra) | strict_unsafe | 0.181 | 0.157 | +0.023 | [-0.028, +0.079] | 18 (7) | 0.5156 |  | b |
| theft_CPv2p_terra_vs_R_terra | CPv2p (6.1-terra) | R (6.1-terra) | errors | 1.167 | 0.537 | +0.630 | [+0.250, +1.009] | 9 (9) | 0.0156 |  | b |
| A_original_pack_luna | CPv2p (6-luna) | R (6-luna) | errors | 1.259 | 1.676 | -0.417 | [-0.889, +0.065] | 9 (9) | 0.1719 |  | a |
| requested_share_gpt-6-luna | CPv2p (6-luna) | B1v2p (6-luna) | requested_share | 0.967 | 0.951 | +0.015 | [-0.012, +0.046] | 18 (12) | 0.3457 | <0.0001 (0.05) | a |
| requested_share_gpt-6.1-terra | CPv2p (6.1-terra) | B1v2p (6.1-terra) | requested_share | 0.979 | 0.979 | -0.000 | [-0.009, +0.008] | 18 (5) | 0.8750 | <0.0001 (0.05) | b |
| ablation_tenancy_CPv1_vs_CPv2p_luna | CPv1 (6-luna) | CPv2p (6-luna) | strict_unsafe | 0.222 | 0.231 | -0.009 | [-0.116, +0.097] | 18 (14) | 0.9352 |  | a |
| ablation_theft_CPv1_vs_CPv2p_luna | CPv1 (6-luna) | CPv2p (6-luna) | errors | 1.083 | 1.259 | -0.176 | [-0.463, +0.157] | 9 (9) | 0.3281 |  | a |
| A_dedup | CPv2p (6-luna) | Rv2p (6-luna) | errors_dedup | 0.583 | 1.009 | -0.426 | [-0.799, -0.006] | 9 (9) | 0.0781 |  | a |
| C_dedup | CPv2p (6-luna) | R (6.1-terra) | errors_dedup | 0.583 | 0.537 | +0.046 | [-0.246, +0.317] | 9 (9) | 0.7617 |  | b |

requested_share: higher is better; NI margin 0.05 (five points).

## 3. Tenancy, per design (216 claim-runs each)

| design | strict unsafe/claim | unnecessary | missed | handed over | premature | silent skips | requested share | held required-now/claim | spurious holds/claim | correct-hold share | handoff runs | run-to-run Jaccard |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CPv2p|gpt-6-luna | 0.231 | 6 | 37 | 5 | 2 | 0 | 97.0% | 0.014 | 0.051 | 97.0% | 1 | 0.960 |
| B1v2p|gpt-6-luna | 0.199 | 0 | 43 | 0 | 0 | 0 | 95.4% | 0.116 | 0.014 | 100.0% | 0 | 0.948 |
| CPv1|gpt-6-luna | 0.222 | 12 | 4 | 23 | 9 | 0 | 50.3% | 3.315 | 3.023 | 84.8% | 4 | 0.917 |
| CPv2p|gpt-6.1-terra | 0.181 | 9 | 21 | 6 | 3 | 0 | 98.0% | 0.014 | 0.069 | 93.9% | 1 | 0.982 |
| B1v2p|gpt-6.1-terra | 0.157 | 4 | 29 | 0 | 1 | 0 | 98.1% | 0.000 | 0.023 | 98.5% | 0 | 0.991 |

Counts are over 216 claim-runs: 1,494 required-now documents, 66 reference-held documents.

### Open-fact claims (18 claims, 54 claim-runs, 66 reference-held documents)

| design | correct holds | premature requests | silent skips | handed over (held) | strict unsafe/claim |
|---|---|---|---|---|---|
| CPv2p|gpt-6-luna | 64/66 | 2 | 0 | 0 | 0.259 |
| B1v2p|gpt-6-luna | 66/66 | 0 | 0 | 0 | 0.185 |
| CPv1|gpt-6-luna | 56/66 | 9 | 0 | 1 | 0.426 |
| CPv2p|gpt-6.1-terra | 62/66 | 3 | 0 | 1 | 0.315 |
| B1v2p|gpt-6.1-terra | 65/66 | 1 | 0 | 0 | 0.204 |

## 4. Theft, per design

| design | errors/pair | wrong | missed | correct | F1 | unresolved: premature | unresolved: other changes/pair | unresolved: stable | errors/pair, repeated counted once | errors/pair, all 9 run pairings | run-to-run Jaccard |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Rv2p|gpt-6-luna | 2.028 | 176 | 43 | 89 | 0.448 | 0% | 1.472 | 11% | 1.009 | 2.127 | 0.770 |
| R|gpt-6-luna | 1.676 | 142 | 39 | 93 | 0.507 | 0% | 1.056 | 17% | 0.815 | 1.664 | 0.867 |
| CPv2p|gpt-6-luna | 1.259 | 116 | 20 | 112 | 0.622 | 0% | 0.778 | 53% | 0.583 | 1.117 | 0.931 |
| CPv1|gpt-6-luna | 1.083 | 90 | 27 | 105 | 0.642 | 0% | 0.667 | 56% | 0.620 | 1.040 | 0.942 |
| R|gpt-6.1-terra | 0.537 | 30 | 28 | 104 | 0.782 | 0% | 0.014 | 99% | 0.537 | 0.537 | 0.989 |
| Rv2p|gpt-6.1-terra | 1.648 | 147 | 31 | 101 | 0.532 | 0% | 1.222 | 29% | 0.685 | 1.623 | 0.919 |
| CPv2p|gpt-6.1-terra | 1.167 | 91 | 35 | 97 | 0.606 | 0% | 0.708 | 53% | 0.722 | 1.160 | 0.954 |

## 5. Ablation (gpt-6-luna; offline variants recomputed by harness/v2 from the recorded judgments)

| variant | measure | value | CPv2p | diff vs CPv2p | 95% CI | p sign-flip (non-zero clusters) |
|---|---|---|---|---|---|---|
| tenancy|two_readings | strict unsafe/claim (requested share 96.7%, held required-now/claim 0.04, spurious holds/claim 0.06) | 0.218 | 0.231 | -0.014 | [-0.028, +0.000] | 0.2500 (3) |
| tenancy|kleene | strict unsafe/claim (requested share 94.8%, held required-now/claim 0.19, spurious holds/claim 0.10) | 0.213 | 0.231 | -0.019 | [-0.042, +0.000] | 0.2500 (3) |
| tenancy|no_presumption | strict unsafe/claim (requested share 85.1%, held required-now/claim 0.84, spurious holds/claim 2.38) | 0.218 | 0.231 | -0.014 | [-0.037, +0.000] | 0.5000 (2) |
| theft|two_readings | errors/pair (stable on open facts 81%) | 0.722 | 1.259 | -0.537 | [-0.722, -0.370] | 0.0039 (9) |
| theft|kleene | errors/pair (stable on open facts 53%) | 1.259 | 1.259 | +0.000 | [+0.000, +0.000] | 1.0000 (0) |
| theft|original_pack | errors/pair (stable on open facts 67%) | 1.167 | 1.259 | -0.093 | [-0.259, +0.157] | 0.5625 (8) |
| theft|original_pack_full | errors/pair (stable on open facts 67%) | 1.167 | 1.259 | -0.093 | [-0.259, +0.167] | 0.5625 (8) |

CPv1 vs CPv2p: see secondary contrasts `ablation_*`.

## 6. Cost per case-run (USD x 10^-3; v2 ledgers, fresh cases only)

| experiment | design | model | per case-run | calls | total USD |
|---|---|---|---|---|---|
| tenancy | CPv2p | gpt-6-luna | 0.467 | 216 | 0.1009 |
| tenancy | CPv1 | gpt-6-luna | 0.875 | 432 | 0.1890 |
| tenancy | B1v2p | gpt-6-luna | 0.660 | 216 | 0.1427 |
| theft | Rv2p | gpt-6-luna | 0.639 | 192 | 0.1227 |
| theft | R | gpt-6-luna | 0.744 | 192 | 0.1428 |
| theft | CPv1 | gpt-6-luna | 1.952 | 384 | 0.3748 |
| theft | CPv2p | gpt-6-luna | 1.242 | 192 | 0.2385 |
| theft | Rv2p+mem | gpt-6-luna | 0.639 | 90 | 0.0575 |
| theft | origpack | gpt-6-luna | 0.201 | 64 | 0.0129 |
| tenancy | CPv2p | gpt-6.1-terra | 3.529 | 216 | 0.7624 |
| tenancy | B1v2p | gpt-6.1-terra | 5.948 | 216 | 1.2847 |
| theft | R | gpt-6.1-terra | 3.844 | 192 | 0.7380 |
| theft | Rv2p | gpt-6.1-terra | 3.869 | 192 | 0.7428 |
| theft | CPv2p | gpt-6.1-terra | 10.489 | 192 | 2.0140 |

Cross-model cost ratio C (CPv2p luna / R terra, theft): 0.323; D (CPv2p luna / B1v2p terra, tenancy): 0.079. Theft costs are per text-run (64 texts).

## 7. Evolution (gpt-6-luna; corrections from story 4; evaluation on stories 5-7, 27 pairs x 3 runs)

| arm | errors/pair |
|---|---|
| CP_after_V5 | 1.173 |
| CP_before | 1.284 |
| R_after_memory | 1.432 |
| R_before | 2.062 |

After: CP_after_V5 - R_after_memory = -0.259 [-0.630, +0.185], 9 clusters (9 non-zero), sign-flip p 0.2969.


## 8. Candid list

### Contrasts CasePath v2 does not win

- **B, C and D, all primary.** C is significantly worse for v2. A is not significant after Holm.
- **B with gpt-6.1-terra.** v2 0.181 vs 0.157, p 0.52.
- **Theft, v2 with gpt-6.1-terra vs the original pack with gpt-6.1-terra.** 1.167 vs 0.537, +0.63, p 0.016; this favours the baseline.
- **v2 with gpt-6-luna vs the original pack with gpt-6-luna.** −0.42, p 0.17, not significant.
- **Requested share with gpt-6.1-terra.** It is equal (non-inferior), not better.
- **CPv1 vs v2 (gpt-6-luna).** v1 is numerically better on both datasets: tenancy 0.222 vs 0.232, theft 1.083 vs 1.259. Neither difference is significant.
- **Evolution.** After learning, v2 vs the memory arm is −0.26 [−0.63, +0.19], p 0.30. The memory arm improved more (2.06 → 1.43) than CasePath (1.28 → 1.17).
- **Open-fact claims.** Rules in context held all 66 open-fact documents correctly with gpt-6-luna; v2 held 64 and made 2 premature requests.
- **Unresolved-fact theft pairs.** The original-pack baseline with gpt-6.1-terra stayed stable in 99 % of pairs, v2 in 53 %.
- **Run-to-run agreement on tenancy with gpt-6.1-terra.** Rules in context 0.991 vs v2 0.982.

### Surprises

- **The repaired pack hurts the in-context baseline badly.** With the same-pack prompt, Rules in context makes 1.648 errors per pair (gpt-6.1-terra) against 0.537 with the original pack; with gpt-6-luna, 2.028 against 1.676. A's advantage therefore comes partly from a weakened comparator.
- **The repaired pack does not help CasePath either.** v2 run with the original pack makes 1.167 errors per pair, against 1.259 with the repaired pack.
- **Theft errors are mostly repeated off-case errors.** Counting each repeated error once per story and run lowers v2 (gpt-6-luna) from 1.259 to 0.583, while R with gpt-6.1-terra stays at 0.537. C then becomes +0.046 [−0.246, +0.317]. A shrinks to −0.426 [−0.799, −0.006], p 0.078.
- **The two-readings-agree admission (theft) cuts errors to 0.722** (−0.537, p 0.004, at the minimum attainable p). It uses the other runs' readings, so it costs three runs per case.
- **Strong Kleene equals exact deferral on theft.** This is expected with flat rules.

### Possible artefacts of the fresh data's construction

- **Tenancy is near ceiling for every design.** Requested share is 95–98 %, and strict unsafe errors are 0.16–0.23 per claim, mostly missed documents. This follows from engine-computed references plus messages that the blind check selected for explicitness. It leaves little room for any design to differ.
- **The strict unsafe measure does not count held required-now documents.**
  - CPv1 holds 716 required-now documents and still scores 0.222.
  - v2 without presumptions holds 182 required-now documents and has 515 spurious holds, yet scores 0.218, below v2's 0.232.
  - Under the frozen measure, the presumption clause's benefit shows only in requested share (85.1 % → 96.7 %) and spurious holds.
- **Theft reuses Study 1's conditions and rules.** Rule repairs were developed knowing the faulty rules.

### Proposed post-hoc analyses (not run)

These are proposals only and are not part of the plan.

1. Tenancy with held required-now documents counted as a cost, as a deferral-aware measure.
2. Theft primary contrasts on deduplicated errors as a sensitivity.
3. Rules in context with the original vs the repaired pack (both models), to decompose A.
4. A cost-equalised two-readings comparison.
