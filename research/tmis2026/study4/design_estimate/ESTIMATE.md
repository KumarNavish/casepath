# Development estimate from Study 3's stored readings; post hoc; not a result

**Post hoc and in-sample.** The combining rules below were chosen after Study 3's stored readings (including the denied-event reading table) were seen and are scored on the same data, so every number is an upper bound on what a redesign would show on new data. No model or network call; nothing here is a result. Produced by `estimate.py`; all numbers are in `ESTIMATE.json`.

Each variant recombines the three stored readings of each case-run of the checklist-only product and re-runs the product's own evaluator at the tested commit (routing and document findings as stored). Scoring is Study 3's registered scoring (via `study4/baseline_check/analyse.py`). No rule uses a reference answer.

## Variants

- **V0 tested: all three must agree.** study3_feedback.combine_k with k = 3, unchanged: a fact's value is admitted only when every one of the three readings admits it (a value with a quotation found word for word in the files) and they give the same value. Values that differ make the fact 'conflicting'; anything else leaves it 'unknown'. Presumptions then apply by the product's rule (workflows.presumed, open rule 'any': a fact that any reading answered 'open' with words found in the files is raised and left open, and no presumption fills it; nor does one when the first or second reading admitted a different value).
- **V1 majority on the defining event only.** For the workflow's defining event (the fact of its 'routed' presumption: termination_received, claim_received; theft has none, so V1 = V0 there): when at least two of the three readings admit the same value (with a located quotation), that value is admitted, whatever the third reading says. Otherwise, and for every other fact, as V0.
- **V2 majority on every deciding fact.** For every fact the readings decide (all workflow facts except those set by routing): when at least two of the three readings admit the same value, that value is admitted, whatever the third says (a different value, 'open', 'not stated', or a quotation not found). Otherwise as V0.
- **V3 a quoted denial of the defining event counts.** For the defining event: if at least one reading admits false (answer false with a quotation found in the files) and no reading admits true, the event is admitted false. If one reading admits true and another admits false, it stays 'conflicting' (unresolved) as in V0. Otherwise as V0; every other fact as V0.
- **V4 V1, and two values outweigh one 'open'.** As V1 for the defining event. For every other fact: when two readings admit the same value, no reading admits a different value, and the remaining reading answered 'open' (with or without words found), that value is admitted. Difference from the tested open rule 'any': under 'any', one 'open' answer with words found both prevents agreement and blocks every presumption, so the fact is held even when the other two readings quote the same value; under V4 that single 'open' is outvoted by two quoted values. A fact with at most one quoted value keeps the tested rule: any located 'open' still blocks the presumption and the fact is held. A dissent that is 'not stated' or an unlocated quotation is not changed (as V0).
- **V5 first reading alone (k = 1).** study3_feedback.combine_k with k = 1: the first reading's admitted values; presumptions by the same rule from the first reading's 'open' answer. For reference (one reading's cost).
- **V6 a quoted denial counts unless contradicted; an 'open' needs two readings on the defining event.** For the defining event: admitted false when at least one reading admits false and no reading admits true (V3); admitted true when at least two readings admit true and none admits false (V1's majority without an override of a quoted false); when no reading admits a value, the event is held (left open) only when at least two readings answered 'open' with words found, otherwise the routed presumption (true) applies. Every other fact as V0.
- **V7 V6 on the defining event, V4 on every other fact.** V6's rule for the defining event; for every other fact, two quoted values outweigh one 'open' (V4).

## Checks

- casepath_checklist/tenancy: {"replayed": 286, "V0 reproduces the stored scored checklist": 285, "stored plan kept (failed, handed over or not routed)": 2}
- casepath_checklist/theft: {"replayed": 384, "V0 reproduces the stored scored checklist": 384}
- casepath_checklist/R3 admitted wrong (stored review) vs V0: [9, 9]
- casepath_checklist/R3 presumed wrong (stored review) vs V0: [3, 3]
- casepath_frontier_checklist/tenancy: {"replayed": 96, "V0 reproduces the stored scored checklist": 95}
- casepath_frontier_checklist/theft: {"replayed": 128, "V0 reproduces the stored scored checklist": 128}

## CasePath, checklist only, cost-efficient (three runs)

### What the readings answered on the defining event, denied-event claims (72 claim-runs routed to the right family)

| answer of one reading | readings |
|---|---|
| false, quotation not found | 180 |
| true, quotation not found | 36 |

Per claim-run (admitted answers):

| admitted answers of the three readings | claim-runs |
|---|---|
| quoted false 3, quoted true 0, open with words found 0 | 54 |
| quoted false 2, quoted true 1, open with words found 0 | 7 |
| quoted false 0, quoted true 3, open with words found 0 | 7 |
| quoted false 1, quoted true 2, open with words found 0 | 4 |

Examples (verbatim quotations):

- *false, quotation not found* (f2cl_0868f24595f5f79a, run 0, reading 1): "I have not received any individual notification of a rent increase, either by post or by email."
- *false, quotation not found* (f2cl_0868f24595f5f79a, run 0, reading 3): "I have not received any individual notification of a rent increase"
- *false, quotation not found* (f2cl_09127308ca120a39, run 0, reading 1): "Ich habe bis heute keine Kündigung erhalten"
- *true, quotation not found* (f2cl_0868f24595f5f79a, run 0, reading 2): "Last week a notice from Hausverwaltung Pilatus appeared on the board in our entrance hall: "Rents in this building will be adjusted from 1 April 2027. Tenants will be informed individually.""
- *true, quotation not found* (f2cl_0868f24595f5f79a, run 1, reading 2): "Last week a notice from Hausverwaltung Pilatus appeared on the board in our entrance hall"
- *true, quotation not found* (f2cl_0c4512154d36a3b4, run 0, reading 1): "he mentioned CHF 180 a month"

### Tenancy (96 claims) and theft (128 texts)

Tenancy: strict unsafe errors / all deviations per claim-run. Theft: wrong + missed changes per pair; unresolved pairs left unchanged / changed prematurely. Wrong values: designed facts x claim-runs given an admitted (or presumed) value that is not the designed one.

| variant | all | every fact stated (S) | open branch fact only | denied event | open event | ordinary | spurious holds | held required now | correct-hold share | theft errors (wrong + missed) | unresolved: unchanged / premature | admitted / presumed wrong values |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 | 0.34 / 0.74 | 0.21 / 0.34 | 0.32 / 0.62 | 0.72 / 1.78 | 0.00 / 0.00 | 0.25 / 0.44 | 0.30 | 0.09 | 1.00 | 0.55 (0.32 + 0.23) | 0.95 / 0.00 | 9 / 3 of 1344 |
| V1 | 0.43 / 0.56 | 0.21 / 0.34 | 0.32 / 0.62 | 1.08 / 1.08 | 0.00 / 0.00 | 0.25 / 0.44 | 0.04 | 0.09 | 1.00 | 0.55 (0.32 + 0.23) | 0.95 / 0.00 | 13 / 3 of 1344 |
| V2 | 0.44 / 0.53 | 0.22 / 0.28 | 0.32 / 0.59 | 1.08 / 1.08 | 0.00 / 0.00 | 0.25 / 0.39 | 0.03 | 0.06 | 1.00 | 0.87 (0.69 + 0.17) | 0.76 / 0.00 | 15 / 3 of 1344 |
| V3 | 0.34 / 0.74 | 0.21 / 0.34 | 0.32 / 0.62 | 0.72 / 1.78 | 0.00 / 0.00 | 0.25 / 0.44 | 0.30 | 0.09 | 1.00 | 0.55 (0.32 + 0.23) | 0.95 / 0.00 | 9 / 3 of 1344 |
| V4 | 0.43 / 0.54 | 0.21 / 0.30 | 0.32 / 0.61 | 1.08 / 1.08 | 0.00 / 0.00 | 0.25 / 0.41 | 0.04 | 0.07 | 1.00 | 0.55 (0.32 + 0.23) | 0.95 / 0.00 | 13 / 3 of 1344 |
| V5 | 0.52 / 0.55 | 0.24 / 0.27 | 0.39 / 0.45 | 1.31 / 1.31 | 0.00 / 0.00 | 0.30 / 0.33 | 0.00 | 0.02 | 1.00 | 1.22 (1.05 + 0.17) | 0.53 / 0.00 | 21 / 7 of 1344 |
| V6 | 0.34 / 0.72 | 0.21 / 0.34 | 0.32 / 0.54 | 0.72 / 1.78 | 0.00 / 0.00 | 0.25 / 0.41 | 0.30 | 0.07 | 1.00 | 0.55 (0.32 + 0.23) | 0.95 / 0.00 | 9 / 3 of 1344 |
| V7 | 0.34 / 0.69 | 0.21 / 0.30 | 0.32 / 0.52 | 0.72 / 1.78 | 0.00 / 0.00 | 0.25 / 0.38 | 0.30 | 0.05 | 1.00 | 0.55 (0.32 + 0.23) | 0.95 / 0.00 | 9 / 3 of 1344 |
| A, cost-efficient | 0.35 / 0.89 | 0.41 / 0.73 | 0.48 / 1.25 | 0.21 / 1.10 | 0.11 / 0.11 | 0.43 / 0.92 | 0.26 | 0.28 | 0.97 | 1.68 (1.49 + 0.19) | 0.19 / 0.03 | - |

### Paired contrasts (variant minus comparator; difference of per-case means; p: sign-flip over cases / over registered clusters)

| variant | against | regime | subset | measure | values | difference | cases lower/higher | p cases | p clusters |
|---|---|---|---|---|---|---|---|---|---|
| V0 | A, cost-efficient | tenancy | all | strict_unsafe | 0.34 vs 0.35 | -0.00 | 26/12 | 1.000 | 1.000 |
| V0 | A, cost-efficient | tenancy | all | all_dev | 0.74 vs 0.89 | -0.15 | 34/18 | 0.412 | 0.441 |
| V0 | A, cost-efficient | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.41 | -0.20 | 15/5 | 0.139 | 0.349 |
| V0 | A, cost-efficient | tenancy | every fact stated (S) | all_dev | 0.34 vs 0.73 | -0.39 | 16/8 | 0.073 | 0.140 |
| V0 | A, cost-efficient | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.48 | -0.16 | 9/4 | 0.238 | 0.171 |
| V0 | A, cost-efficient | tenancy | open branch fact only | all_dev | 0.62 vs 1.25 | -0.62 | 13/5 | 0.077 | 0.066 |
| V0 | A, cost-efficient | tenancy | denied event | strict_unsafe | 0.72 vs 0.21 | +0.51 | 0/3 | 0.250 | 0.250 |
| V0 | A, cost-efficient | tenancy | denied event | all_dev | 1.78 vs 1.10 | +0.68 | 3/5 | 0.195 | 0.125 |
| V0 | A, cost-efficient | theft | changed-fact pairs | errors | 0.55 vs 1.68 | -1.12 | 62/5 | <0.001 | 0.004 |
| V1 | V0 | tenancy | all | strict_unsafe | 0.43 vs 0.34 | +0.09 | 0/3 | 0.250 | 0.500 |
| V1 | V0 | tenancy | all | all_dev | 0.56 vs 0.74 | -0.17 | 6/0 | 0.031 | 0.125 |
| V1 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.21 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | every fact stated (S) | all_dev | 0.34 vs 0.34 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.32 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | open branch fact only | all_dev | 0.62 vs 0.62 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | denied event | strict_unsafe | 1.08 vs 0.72 | +0.36 | 0/3 | 0.250 | 0.500 |
| V1 | V0 | tenancy | denied event | all_dev | 1.08 vs 1.78 | -0.69 | 6/0 | 0.031 | 0.125 |
| V1 | V0 | theft | changed-fact pairs | errors | 0.55 vs 0.55 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | A, cost-efficient | tenancy | all | strict_unsafe | 0.43 vs 0.35 | +0.09 | 26/15 | 0.473 | 0.557 |
| V1 | A, cost-efficient | tenancy | all | all_dev | 0.56 vs 0.89 | -0.33 | 36/18 | 0.053 | 0.048 |
| V1 | A, cost-efficient | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.41 | -0.20 | 15/5 | 0.139 | 0.349 |
| V1 | A, cost-efficient | tenancy | every fact stated (S) | all_dev | 0.34 vs 0.73 | -0.39 | 16/8 | 0.073 | 0.140 |
| V1 | A, cost-efficient | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.48 | -0.16 | 9/4 | 0.238 | 0.171 |
| V1 | A, cost-efficient | tenancy | open branch fact only | all_dev | 0.62 vs 1.25 | -0.62 | 13/5 | 0.077 | 0.066 |
| V1 | A, cost-efficient | tenancy | denied event | strict_unsafe | 1.08 vs 0.21 | +0.88 | 0/6 | 0.031 | 0.125 |
| V1 | A, cost-efficient | tenancy | denied event | all_dev | 1.08 vs 1.10 | -0.01 | 5/5 | 1.000 | 1.000 |
| V1 | A, cost-efficient | theft | changed-fact pairs | errors | 0.55 vs 1.68 | -1.12 | 62/5 | <0.001 | 0.004 |
| V2 | V0 | tenancy | all | strict_unsafe | 0.44 vs 0.34 | +0.09 | 0/4 | 0.125 | 0.250 |
| V2 | V0 | tenancy | all | all_dev | 0.53 vs 0.74 | -0.21 | 15/0 | <0.001 | <0.001 |
| V2 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.22 vs 0.21 | +0.01 | 0/1 | 1.000 | 1.000 |
| V2 | V0 | tenancy | every fact stated (S) | all_dev | 0.28 vs 0.34 | -0.07 | 7/0 | 0.016 | 0.016 |
| V2 | V0 | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.32 | +0.00 | 0/0 | 1.000 | 1.000 |
| V2 | V0 | tenancy | open branch fact only | all_dev | 0.59 vs 0.62 | -0.03 | 2/0 | 0.500 | 0.500 |
| V2 | V0 | tenancy | denied event | strict_unsafe | 1.08 vs 0.72 | +0.36 | 0/3 | 0.250 | 0.500 |
| V2 | V0 | tenancy | denied event | all_dev | 1.08 vs 1.78 | -0.69 | 6/0 | 0.031 | 0.125 |
| V2 | V0 | theft | changed-fact pairs | errors | 0.87 vs 0.55 | +0.31 | 11/37 | <0.001 | 0.012 |
| V2 | A, cost-efficient | tenancy | all | strict_unsafe | 0.44 vs 0.35 | +0.09 | 26/15 | 0.454 | 0.539 |
| V2 | A, cost-efficient | tenancy | all | all_dev | 0.53 vs 0.89 | -0.36 | 37/15 | 0.034 | 0.032 |
| V2 | A, cost-efficient | tenancy | every fact stated (S) | strict_unsafe | 0.22 vs 0.41 | -0.19 | 15/5 | 0.155 | 0.363 |
| V2 | A, cost-efficient | tenancy | every fact stated (S) | all_dev | 0.28 vs 0.73 | -0.46 | 17/5 | 0.037 | 0.089 |
| V2 | A, cost-efficient | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.48 | -0.16 | 9/4 | 0.238 | 0.171 |
| V2 | A, cost-efficient | tenancy | open branch fact only | all_dev | 0.59 vs 1.25 | -0.65 | 13/5 | 0.056 | 0.057 |
| V2 | A, cost-efficient | tenancy | denied event | strict_unsafe | 1.08 vs 0.21 | +0.88 | 0/6 | 0.031 | 0.125 |
| V2 | A, cost-efficient | tenancy | denied event | all_dev | 1.08 vs 1.10 | -0.01 | 5/5 | 1.000 | 1.000 |
| V2 | A, cost-efficient | theft | changed-fact pairs | errors | 0.87 vs 1.68 | -0.81 | 56/7 | <0.001 | 0.004 |
| V3 | V0 | tenancy | all | strict_unsafe | 0.34 vs 0.34 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | all | all_dev | 0.74 vs 0.74 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.21 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | every fact stated (S) | all_dev | 0.34 vs 0.34 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.32 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | open branch fact only | all_dev | 0.62 vs 0.62 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | denied event | strict_unsafe | 0.72 vs 0.72 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | denied event | all_dev | 1.78 vs 1.78 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | theft | changed-fact pairs | errors | 0.55 vs 0.55 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | A, cost-efficient | tenancy | all | strict_unsafe | 0.34 vs 0.35 | -0.00 | 26/12 | 1.000 | 1.000 |
| V3 | A, cost-efficient | tenancy | all | all_dev | 0.74 vs 0.89 | -0.15 | 34/18 | 0.412 | 0.441 |
| V3 | A, cost-efficient | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.41 | -0.20 | 15/5 | 0.139 | 0.349 |
| V3 | A, cost-efficient | tenancy | every fact stated (S) | all_dev | 0.34 vs 0.73 | -0.39 | 16/8 | 0.073 | 0.140 |
| V3 | A, cost-efficient | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.48 | -0.16 | 9/4 | 0.238 | 0.171 |
| V3 | A, cost-efficient | tenancy | open branch fact only | all_dev | 0.62 vs 1.25 | -0.62 | 13/5 | 0.077 | 0.066 |
| V3 | A, cost-efficient | tenancy | denied event | strict_unsafe | 0.72 vs 0.21 | +0.51 | 0/3 | 0.250 | 0.250 |
| V3 | A, cost-efficient | tenancy | denied event | all_dev | 1.78 vs 1.10 | +0.68 | 3/5 | 0.195 | 0.125 |
| V3 | A, cost-efficient | theft | changed-fact pairs | errors | 0.55 vs 1.68 | -1.12 | 62/5 | <0.001 | 0.004 |
| V4 | V0 | tenancy | all | strict_unsafe | 0.43 vs 0.34 | +0.09 | 0/3 | 0.250 | 0.500 |
| V4 | V0 | tenancy | all | all_dev | 0.54 vs 0.74 | -0.19 | 11/0 | <0.001 | 0.004 |
| V4 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.21 | +0.00 | 0/0 | 1.000 | 1.000 |
| V4 | V0 | tenancy | every fact stated (S) | all_dev | 0.30 vs 0.34 | -0.04 | 4/0 | 0.125 | 0.125 |
| V4 | V0 | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.32 | +0.00 | 0/0 | 1.000 | 1.000 |
| V4 | V0 | tenancy | open branch fact only | all_dev | 0.61 vs 0.62 | -0.01 | 1/0 | 1.000 | 1.000 |
| V4 | V0 | tenancy | denied event | strict_unsafe | 1.08 vs 0.72 | +0.36 | 0/3 | 0.250 | 0.500 |
| V4 | V0 | tenancy | denied event | all_dev | 1.08 vs 1.78 | -0.69 | 6/0 | 0.031 | 0.125 |
| V4 | V0 | theft | changed-fact pairs | errors | 0.55 vs 0.55 | -0.00 | 2/3 | 1.000 | 1.000 |
| V4 | A, cost-efficient | tenancy | all | strict_unsafe | 0.43 vs 0.35 | +0.09 | 26/15 | 0.473 | 0.557 |
| V4 | A, cost-efficient | tenancy | all | all_dev | 0.54 vs 0.89 | -0.35 | 37/16 | 0.040 | 0.039 |
| V4 | A, cost-efficient | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.41 | -0.20 | 15/5 | 0.139 | 0.349 |
| V4 | A, cost-efficient | tenancy | every fact stated (S) | all_dev | 0.30 vs 0.73 | -0.43 | 17/6 | 0.045 | 0.104 |
| V4 | A, cost-efficient | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.48 | -0.16 | 9/4 | 0.238 | 0.171 |
| V4 | A, cost-efficient | tenancy | open branch fact only | all_dev | 0.61 vs 1.25 | -0.64 | 13/5 | 0.070 | 0.066 |
| V4 | A, cost-efficient | tenancy | denied event | strict_unsafe | 1.08 vs 0.21 | +0.88 | 0/6 | 0.031 | 0.125 |
| V4 | A, cost-efficient | tenancy | denied event | all_dev | 1.08 vs 1.10 | -0.01 | 5/5 | 1.000 | 1.000 |
| V4 | A, cost-efficient | theft | changed-fact pairs | errors | 0.55 vs 1.68 | -1.12 | 64/5 | <0.001 | 0.004 |
| V5 | V0 | tenancy | all | strict_unsafe | 0.52 vs 0.34 | +0.18 | 1/9 | 0.008 | 0.008 |
| V5 | V0 | tenancy | all | all_dev | 0.55 vs 0.74 | -0.19 | 15/0 | <0.001 | <0.001 |
| V5 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.24 vs 0.21 | +0.03 | 0/3 | 0.250 | 0.250 |
| V5 | V0 | tenancy | every fact stated (S) | all_dev | 0.27 vs 0.34 | -0.07 | 8/0 | 0.008 | 0.031 |
| V5 | V0 | tenancy | open branch fact only | strict_unsafe | 0.39 vs 0.32 | +0.07 | 1/2 | 0.500 | 0.500 |
| V5 | V0 | tenancy | open branch fact only | all_dev | 0.45 vs 0.62 | -0.17 | 4/0 | 0.125 | 0.125 |
| V5 | V0 | tenancy | denied event | strict_unsafe | 1.31 vs 0.72 | +0.58 | 0/4 | 0.125 | 0.125 |
| V5 | V0 | tenancy | denied event | all_dev | 1.31 vs 1.78 | -0.47 | 3/0 | 0.250 | 0.500 |
| V5 | V0 | theft | changed-fact pairs | errors | 1.22 vs 0.55 | +0.67 | 9/57 | <0.001 | 0.004 |
| V5 | A, cost-efficient | tenancy | all | strict_unsafe | 0.52 vs 0.35 | +0.17 | 26/18 | 0.202 | 0.314 |
| V5 | A, cost-efficient | tenancy | all | all_dev | 0.55 vs 0.89 | -0.34 | 37/14 | 0.062 | 0.075 |
| V5 | A, cost-efficient | tenancy | every fact stated (S) | strict_unsafe | 0.24 vs 0.41 | -0.17 | 15/7 | 0.229 | 0.430 |
| V5 | A, cost-efficient | tenancy | every fact stated (S) | all_dev | 0.27 vs 0.73 | -0.47 | 18/5 | 0.033 | 0.094 |
| V5 | A, cost-efficient | tenancy | open branch fact only | strict_unsafe | 0.39 vs 0.48 | -0.09 | 9/5 | 0.617 | 0.360 |
| V5 | A, cost-efficient | tenancy | open branch fact only | all_dev | 0.45 vs 1.25 | -0.80 | 13/5 | 0.031 | 0.039 |
| V5 | A, cost-efficient | tenancy | denied event | strict_unsafe | 1.31 vs 0.21 | +1.10 | 0/6 | 0.031 | 0.125 |
| V5 | A, cost-efficient | tenancy | denied event | all_dev | 1.31 vs 1.10 | +0.21 | 4/4 | 0.695 | 0.500 |
| V5 | A, cost-efficient | theft | changed-fact pairs | errors | 1.22 vs 1.68 | -0.46 | 45/18 | <0.001 | 0.031 |
| V6 | V0 | tenancy | all | strict_unsafe | 0.34 vs 0.34 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | all | all_dev | 0.72 vs 0.74 | -0.02 | 1/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.21 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | every fact stated (S) | all_dev | 0.34 vs 0.34 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.32 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | open branch fact only | all_dev | 0.54 vs 0.62 | -0.09 | 1/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | denied event | strict_unsafe | 0.72 vs 0.72 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | denied event | all_dev | 1.78 vs 1.78 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | theft | changed-fact pairs | errors | 0.55 vs 0.55 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | A, cost-efficient | tenancy | all | strict_unsafe | 0.34 vs 0.35 | -0.00 | 26/12 | 1.000 | 1.000 |
| V6 | A, cost-efficient | tenancy | all | all_dev | 0.72 vs 0.89 | -0.17 | 34/18 | 0.355 | 0.399 |
| V6 | A, cost-efficient | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.41 | -0.20 | 15/5 | 0.139 | 0.349 |
| V6 | A, cost-efficient | tenancy | every fact stated (S) | all_dev | 0.34 vs 0.73 | -0.39 | 16/8 | 0.073 | 0.140 |
| V6 | A, cost-efficient | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.48 | -0.16 | 9/4 | 0.238 | 0.171 |
| V6 | A, cost-efficient | tenancy | open branch fact only | all_dev | 0.54 vs 1.25 | -0.71 | 13/5 | 0.057 | 0.066 |
| V6 | A, cost-efficient | tenancy | denied event | strict_unsafe | 0.72 vs 0.21 | +0.51 | 0/3 | 0.250 | 0.250 |
| V6 | A, cost-efficient | tenancy | denied event | all_dev | 1.78 vs 1.10 | +0.68 | 3/5 | 0.195 | 0.125 |
| V6 | A, cost-efficient | theft | changed-fact pairs | errors | 0.55 vs 1.68 | -1.12 | 62/5 | <0.001 | 0.004 |
| V7 | V0 | tenancy | all | strict_unsafe | 0.34 vs 0.34 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | all | all_dev | 0.69 vs 0.74 | -0.04 | 5/0 | 0.062 | 0.062 |
| V7 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.21 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | every fact stated (S) | all_dev | 0.30 vs 0.34 | -0.04 | 4/0 | 0.125 | 0.125 |
| V7 | V0 | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.32 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | open branch fact only | all_dev | 0.52 vs 0.62 | -0.10 | 1/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | denied event | strict_unsafe | 0.72 vs 0.72 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | denied event | all_dev | 1.78 vs 1.78 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | theft | changed-fact pairs | errors | 0.55 vs 0.55 | -0.00 | 2/3 | 1.000 | 1.000 |
| V7 | A, cost-efficient | tenancy | all | strict_unsafe | 0.34 vs 0.35 | -0.00 | 26/12 | 1.000 | 1.000 |
| V7 | A, cost-efficient | tenancy | all | all_dev | 0.69 vs 0.89 | -0.19 | 35/16 | 0.302 | 0.353 |
| V7 | A, cost-efficient | tenancy | every fact stated (S) | strict_unsafe | 0.21 vs 0.41 | -0.20 | 15/5 | 0.139 | 0.349 |
| V7 | A, cost-efficient | tenancy | every fact stated (S) | all_dev | 0.30 vs 0.73 | -0.43 | 17/6 | 0.045 | 0.104 |
| V7 | A, cost-efficient | tenancy | open branch fact only | strict_unsafe | 0.32 vs 0.48 | -0.16 | 9/4 | 0.238 | 0.171 |
| V7 | A, cost-efficient | tenancy | open branch fact only | all_dev | 0.52 vs 1.25 | -0.72 | 13/5 | 0.057 | 0.066 |
| V7 | A, cost-efficient | tenancy | denied event | strict_unsafe | 0.72 vs 0.21 | +0.51 | 0/3 | 0.250 | 0.250 |
| V7 | A, cost-efficient | tenancy | denied event | all_dev | 1.78 vs 1.10 | +0.68 | 3/5 | 0.195 | 0.125 |
| V7 | A, cost-efficient | theft | changed-fact pairs | errors | 0.55 vs 1.68 | -1.12 | 64/5 | <0.001 | 0.004 |

### What no combining rule can remove (tested product, tenancy, all deviations, counted per document)

Sequential: tested -> best combining rule (per fact the designed outcome wherever some reading supports it) -> every fact at its designed value -> also the designed document findings. Claim-runs routed to another family (or not replayed) keep their stored plan.

| part | deviations |
|---|---|
| removable by a combining rule (tested - best rule) | 115 |
| readings all wrong (best rule - facts as designed) | 55 |
| document judgments (facts as designed - also findings as designed) | 29 |
| evaluator / workflow against the reference (remaining) | 0 |
| routing (another family) or no replay | 13 |
| total tested deviations | 212 |

Steps by subset:

| subset | tested | best combining rule | facts as designed | facts and findings as designed | routing (another family) or no replay |
|---|---|---|---|---|---|
| O: denied defining event | 128 | 52 | 0 | 0 | 0 |
| O: open branch fact only | 43 | 22 | 19 | 0 | 0 |
| O: open defining event | 0 | 0 | 0 | 0 | 0 |
| S | 28 | 10 | 10 | 0 | 13 |

Facts whose designed outcome no reading supports (fact x claim-run): {"branch fact / stated_false": 3, "branch fact / stated_true": 4, "defining event / stated_false": 7}

## CasePath, checklist only, frontier (one run)

### What the readings answered on the defining event, denied-event claims (24 claim-runs routed to the right family)

| answer of one reading | readings |
|---|---|
| false, quotation not found | 60 |
| true, quotation not found | 12 |

Per claim-run (admitted answers):

| admitted answers of the three readings | claim-runs |
|---|---|
| quoted false 3, quoted true 0, open with words found 0 | 18 |
| quoted false 1, quoted true 2, open with words found 0 | 4 |
| quoted false 0, quoted true 3, open with words found 0 | 1 |
| quoted false 2, quoted true 1, open with words found 0 | 1 |

Examples (verbatim quotations):

- *false, quotation not found* (f2cl_0868f24595f5f79a, run 0, reading 1): "I have not received any individual notification of a rent increase, either by post or by email."
- *false, quotation not found* (f2cl_09127308ca120a39, run 0, reading 1): "Ich habe bis heute keine Kündigung erhalten"
- *false, quotation not found* (f2cl_0c4512154d36a3b4, run 0, reading 2): "the papers will be sent out with the official form "before the end of the year", so I'm waiting for that"
- *true, quotation not found* (f2cl_0868f24595f5f79a, run 0, reading 2): "All we have is that notice in the hallway."
- *true, quotation not found* (f2cl_0c4512154d36a3b4, run 0, reading 1): "now the manager says everyone will pay more for that, he mentioned CHF 180 a month"
- *true, quotation not found* (f2cl_0c4512154d36a3b4, run 0, reading 3): "the manager says everyone will pay more for that, he mentioned CHF 180 a month"

### Tenancy (96 claims) and theft (128 texts)

Tenancy: strict unsafe errors / all deviations per claim-run. Theft: wrong + missed changes per pair; unresolved pairs left unchanged / changed prematurely. Wrong values: designed facts x claim-runs given an admitted (or presumed) value that is not the designed one.

| variant | all | every fact stated (S) | open branch fact only | denied event | open event | ordinary | spurious holds | held required now | correct-hold share | theft errors (wrong + missed) | unresolved: unchanged / premature | admitted / presumed wrong values |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 | 0.30 / 0.71 | 0.05 / 0.07 | 0.61 / 0.65 | 0.29 / 1.79 | 0.67 / 0.78 | 0.25 / 0.29 | 0.39 | 0.02 | 0.87 | 0.83 (0.42 + 0.42) | 0.75 / 0.00 | 4 / 4 of 448 |
| V1 | 0.59 / 0.62 | 0.05 / 0.07 | 0.61 / 0.65 | 1.46 / 1.46 | 0.67 / 0.78 | 0.25 / 0.29 | 0.01 | 0.02 | 0.87 | 0.83 (0.42 + 0.42) | 0.75 / 0.00 | 9 / 3 of 448 |
| V2 | 0.59 / 0.61 | 0.05 / 0.05 | 0.61 / 0.65 | 1.46 / 1.46 | 0.67 / 0.78 | 0.25 / 0.27 | 0.01 | 0.01 | 0.87 | 0.78 (0.42 + 0.36) | 0.75 / 0.00 | 11 / 2 of 448 |
| V3 | 0.30 / 0.71 | 0.05 / 0.07 | 0.61 / 0.65 | 0.29 / 1.79 | 0.67 / 0.78 | 0.25 / 0.29 | 0.39 | 0.02 | 0.87 | 0.83 (0.42 + 0.42) | 0.75 / 0.00 | 4 / 4 of 448 |
| V4 | 0.59 / 0.62 | 0.05 / 0.07 | 0.61 / 0.65 | 1.46 / 1.46 | 0.67 / 0.78 | 0.25 / 0.29 | 0.01 | 0.02 | 0.87 | 0.83 (0.42 + 0.42) | 0.75 / 0.00 | 10 / 2 of 448 |
| V5 | 0.61 / 0.64 | 0.05 / 0.05 | 0.61 / 0.65 | 1.54 / 1.54 | 0.67 / 0.78 | 0.25 / 0.27 | 0.01 | 0.01 | 0.87 | 0.89 (0.56 + 0.33) | 0.69 / 0.00 | 14 / 2 of 448 |
| V6 | 0.30 / 0.71 | 0.05 / 0.07 | 0.61 / 0.65 | 0.29 / 1.79 | 0.67 / 0.78 | 0.25 / 0.29 | 0.39 | 0.02 | 0.87 | 0.83 (0.42 + 0.42) | 0.75 / 0.00 | 5 / 3 of 448 |
| V7 | 0.30 / 0.71 | 0.05 / 0.07 | 0.61 / 0.65 | 0.29 / 1.79 | 0.67 / 0.78 | 0.25 / 0.29 | 0.39 | 0.02 | 0.87 | 0.83 (0.42 + 0.42) | 0.75 / 0.00 | 6 / 2 of 448 |
| A, frontier | 0.19 / 0.58 | 0.17 / 0.68 | 0.48 / 1.26 | 0.00 / 0.00 | 0.00 / 0.00 | 0.29 / 0.89 | 0.03 | 0.36 | 0.98 | 1.18 (0.96 + 0.22) | 0.56 / 0.00 | - |
| B, frontier | 0.19 / 0.54 | 0.12 / 0.40 | 0.57 / 1.30 | 0.00 / 0.25 | 0.00 / 0.00 | 0.29 / 0.73 | 0.09 | 0.26 | 0.97 | 1.24 (0.93 + 0.31) | 0.46 / 0.00 | - |

### Paired contrasts (variant minus comparator; difference of per-case means; p: sign-flip over cases / over registered clusters)

| variant | against | regime | subset | measure | values | difference | cases lower/higher | p cases | p clusters |
|---|---|---|---|---|---|---|---|---|---|
| V0 | A, frontier | tenancy | all | strict_unsafe | 0.30 vs 0.19 | +0.11 | 10/11 | 0.386 | 0.392 |
| V0 | A, frontier | tenancy | all | all_dev | 0.71 vs 0.58 | +0.12 | 15/15 | 0.673 | 0.751 |
| V0 | A, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.17 | -0.12 | 7/2 | 0.180 | 0.156 |
| V0 | A, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.68 | -0.60 | 9/1 | 0.059 | 0.066 |
| V0 | A, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.48 | +0.13 | 3/7 | 0.684 | 1.000 |
| V0 | A, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.26 | -0.61 | 6/6 | 0.292 | 0.195 |
| V0 | A, frontier | tenancy | denied event | strict_unsafe | 0.29 vs 0.00 | +0.29 | 0/1 | 1.000 | 1.000 |
| V0 | A, frontier | tenancy | denied event | all_dev | 1.79 vs 0.00 | +1.79 | 0/6 | 0.031 | 0.125 |
| V0 | A, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.18 | -0.35 | 32/14 | 0.042 | 0.102 |
| V0 | B, frontier | tenancy | all | strict_unsafe | 0.30 vs 0.19 | +0.11 | 8/9 | 0.384 | 0.390 |
| V0 | B, frontier | tenancy | all | all_dev | 0.71 vs 0.54 | +0.17 | 12/13 | 0.550 | 0.628 |
| V0 | B, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.12 | -0.07 | 4/2 | 0.531 | 0.531 |
| V0 | B, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.40 | -0.33 | 5/1 | 0.281 | 0.406 |
| V0 | B, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.57 | +0.04 | 4/5 | 1.000 | 0.875 |
| V0 | B, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.30 | -0.65 | 6/4 | 0.250 | 0.312 |
| V0 | B, frontier | tenancy | denied event | strict_unsafe | 0.29 vs 0.00 | +0.29 | 0/1 | 1.000 | 1.000 |
| V0 | B, frontier | tenancy | denied event | all_dev | 1.79 vs 0.25 | +1.54 | 1/6 | 0.047 | 0.250 |
| V0 | B, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.24 | -0.40 | 29/16 | 0.020 | 0.148 |
| V1 | V0 | tenancy | all | strict_unsafe | 0.59 vs 0.30 | +0.29 | 0/4 | 0.125 | 0.125 |
| V1 | V0 | tenancy | all | all_dev | 0.62 vs 0.71 | -0.08 | 1/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.05 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.07 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.61 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | open branch fact only | all_dev | 0.65 vs 0.65 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | V0 | tenancy | denied event | strict_unsafe | 1.46 vs 0.29 | +1.17 | 0/4 | 0.125 | 0.125 |
| V1 | V0 | tenancy | denied event | all_dev | 1.46 vs 1.79 | -0.33 | 1/0 | 1.000 | 1.000 |
| V1 | V0 | theft | changed-fact pairs | errors | 0.83 vs 0.83 | +0.00 | 0/0 | 1.000 | 1.000 |
| V1 | A, frontier | tenancy | all | strict_unsafe | 0.59 vs 0.19 | +0.41 | 10/15 | 0.027 | 0.090 |
| V1 | A, frontier | tenancy | all | all_dev | 0.62 vs 0.58 | +0.04 | 15/14 | 0.903 | 0.924 |
| V1 | A, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.17 | -0.12 | 7/2 | 0.180 | 0.156 |
| V1 | A, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.68 | -0.60 | 9/1 | 0.059 | 0.066 |
| V1 | A, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.48 | +0.13 | 3/7 | 0.684 | 1.000 |
| V1 | A, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.26 | -0.61 | 6/6 | 0.292 | 0.195 |
| V1 | A, frontier | tenancy | denied event | strict_unsafe | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V1 | A, frontier | tenancy | denied event | all_dev | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V1 | A, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.18 | -0.35 | 32/14 | 0.042 | 0.102 |
| V1 | B, frontier | tenancy | all | strict_unsafe | 0.59 vs 0.19 | +0.41 | 8/13 | 0.026 | 0.091 |
| V1 | B, frontier | tenancy | all | all_dev | 0.62 vs 0.54 | +0.08 | 12/12 | 0.769 | 0.798 |
| V1 | B, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.12 | -0.07 | 4/2 | 0.531 | 0.531 |
| V1 | B, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.40 | -0.33 | 5/1 | 0.281 | 0.406 |
| V1 | B, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.57 | +0.04 | 4/5 | 1.000 | 0.875 |
| V1 | B, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.30 | -0.65 | 6/4 | 0.250 | 0.312 |
| V1 | B, frontier | tenancy | denied event | strict_unsafe | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V1 | B, frontier | tenancy | denied event | all_dev | 1.46 vs 0.25 | +1.21 | 1/5 | 0.094 | 0.250 |
| V1 | B, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.24 | -0.40 | 29/16 | 0.020 | 0.148 |
| V2 | V0 | tenancy | all | strict_unsafe | 0.59 vs 0.30 | +0.29 | 0/4 | 0.125 | 0.125 |
| V2 | V0 | tenancy | all | all_dev | 0.61 vs 0.71 | -0.09 | 2/0 | 0.500 | 0.500 |
| V2 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.05 | +0.00 | 0/0 | 1.000 | 1.000 |
| V2 | V0 | tenancy | every fact stated (S) | all_dev | 0.05 vs 0.07 | -0.03 | 1/0 | 1.000 | 1.000 |
| V2 | V0 | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.61 | +0.00 | 0/0 | 1.000 | 1.000 |
| V2 | V0 | tenancy | open branch fact only | all_dev | 0.65 vs 0.65 | +0.00 | 0/0 | 1.000 | 1.000 |
| V2 | V0 | tenancy | denied event | strict_unsafe | 1.46 vs 0.29 | +1.17 | 0/4 | 0.125 | 0.125 |
| V2 | V0 | tenancy | denied event | all_dev | 1.46 vs 1.79 | -0.33 | 1/0 | 1.000 | 1.000 |
| V2 | V0 | theft | changed-fact pairs | errors | 0.78 vs 0.83 | -0.06 | 11/6 | 0.676 | 0.758 |
| V2 | A, frontier | tenancy | all | strict_unsafe | 0.59 vs 0.19 | +0.41 | 10/15 | 0.027 | 0.090 |
| V2 | A, frontier | tenancy | all | all_dev | 0.61 vs 0.58 | +0.03 | 15/14 | 0.934 | 0.950 |
| V2 | A, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.17 | -0.12 | 7/2 | 0.180 | 0.156 |
| V2 | A, frontier | tenancy | every fact stated (S) | all_dev | 0.05 vs 0.68 | -0.62 | 9/1 | 0.018 | 0.018 |
| V2 | A, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.48 | +0.13 | 3/7 | 0.684 | 1.000 |
| V2 | A, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.26 | -0.61 | 6/6 | 0.292 | 0.195 |
| V2 | A, frontier | tenancy | denied event | strict_unsafe | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V2 | A, frontier | tenancy | denied event | all_dev | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V2 | A, frontier | theft | changed-fact pairs | errors | 0.78 vs 1.18 | -0.40 | 33/13 | 0.017 | 0.148 |
| V2 | B, frontier | tenancy | all | strict_unsafe | 0.59 vs 0.19 | +0.41 | 8/13 | 0.026 | 0.091 |
| V2 | B, frontier | tenancy | all | all_dev | 0.61 vs 0.54 | +0.07 | 12/12 | 0.798 | 0.825 |
| V2 | B, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.12 | -0.07 | 4/2 | 0.531 | 0.531 |
| V2 | B, frontier | tenancy | every fact stated (S) | all_dev | 0.05 vs 0.40 | -0.35 | 5/1 | 0.156 | 0.156 |
| V2 | B, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.57 | +0.04 | 4/5 | 1.000 | 0.875 |
| V2 | B, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.30 | -0.65 | 6/4 | 0.250 | 0.312 |
| V2 | B, frontier | tenancy | denied event | strict_unsafe | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V2 | B, frontier | tenancy | denied event | all_dev | 1.46 vs 0.25 | +1.21 | 1/5 | 0.094 | 0.250 |
| V2 | B, frontier | theft | changed-fact pairs | errors | 0.78 vs 1.24 | -0.46 | 28/11 | 0.005 | 0.109 |
| V3 | V0 | tenancy | all | strict_unsafe | 0.30 vs 0.30 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | all | all_dev | 0.71 vs 0.71 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.05 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.07 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.61 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | open branch fact only | all_dev | 0.65 vs 0.65 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | denied event | strict_unsafe | 0.29 vs 0.29 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | tenancy | denied event | all_dev | 1.79 vs 1.79 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | V0 | theft | changed-fact pairs | errors | 0.83 vs 0.83 | +0.00 | 0/0 | 1.000 | 1.000 |
| V3 | A, frontier | tenancy | all | strict_unsafe | 0.30 vs 0.19 | +0.11 | 10/11 | 0.386 | 0.392 |
| V3 | A, frontier | tenancy | all | all_dev | 0.71 vs 0.58 | +0.12 | 15/15 | 0.673 | 0.751 |
| V3 | A, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.17 | -0.12 | 7/2 | 0.180 | 0.156 |
| V3 | A, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.68 | -0.60 | 9/1 | 0.059 | 0.066 |
| V3 | A, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.48 | +0.13 | 3/7 | 0.684 | 1.000 |
| V3 | A, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.26 | -0.61 | 6/6 | 0.292 | 0.195 |
| V3 | A, frontier | tenancy | denied event | strict_unsafe | 0.29 vs 0.00 | +0.29 | 0/1 | 1.000 | 1.000 |
| V3 | A, frontier | tenancy | denied event | all_dev | 1.79 vs 0.00 | +1.79 | 0/6 | 0.031 | 0.125 |
| V3 | A, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.18 | -0.35 | 32/14 | 0.042 | 0.102 |
| V3 | B, frontier | tenancy | all | strict_unsafe | 0.30 vs 0.19 | +0.11 | 8/9 | 0.384 | 0.390 |
| V3 | B, frontier | tenancy | all | all_dev | 0.71 vs 0.54 | +0.17 | 12/13 | 0.550 | 0.628 |
| V3 | B, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.12 | -0.07 | 4/2 | 0.531 | 0.531 |
| V3 | B, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.40 | -0.33 | 5/1 | 0.281 | 0.406 |
| V3 | B, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.57 | +0.04 | 4/5 | 1.000 | 0.875 |
| V3 | B, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.30 | -0.65 | 6/4 | 0.250 | 0.312 |
| V3 | B, frontier | tenancy | denied event | strict_unsafe | 0.29 vs 0.00 | +0.29 | 0/1 | 1.000 | 1.000 |
| V3 | B, frontier | tenancy | denied event | all_dev | 1.79 vs 0.25 | +1.54 | 1/6 | 0.047 | 0.250 |
| V3 | B, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.24 | -0.40 | 29/16 | 0.020 | 0.148 |
| V4 | V0 | tenancy | all | strict_unsafe | 0.59 vs 0.30 | +0.29 | 0/4 | 0.125 | 0.125 |
| V4 | V0 | tenancy | all | all_dev | 0.62 vs 0.71 | -0.08 | 1/0 | 1.000 | 1.000 |
| V4 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.05 | +0.00 | 0/0 | 1.000 | 1.000 |
| V4 | V0 | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.07 | +0.00 | 0/0 | 1.000 | 1.000 |
| V4 | V0 | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.61 | +0.00 | 0/0 | 1.000 | 1.000 |
| V4 | V0 | tenancy | open branch fact only | all_dev | 0.65 vs 0.65 | +0.00 | 0/0 | 1.000 | 1.000 |
| V4 | V0 | tenancy | denied event | strict_unsafe | 1.46 vs 0.29 | +1.17 | 0/4 | 0.125 | 0.125 |
| V4 | V0 | tenancy | denied event | all_dev | 1.46 vs 1.79 | -0.33 | 1/0 | 1.000 | 1.000 |
| V4 | V0 | theft | changed-fact pairs | errors | 0.83 vs 0.83 | +0.00 | 0/0 | 1.000 | 1.000 |
| V4 | A, frontier | tenancy | all | strict_unsafe | 0.59 vs 0.19 | +0.41 | 10/15 | 0.027 | 0.090 |
| V4 | A, frontier | tenancy | all | all_dev | 0.62 vs 0.58 | +0.04 | 15/14 | 0.903 | 0.924 |
| V4 | A, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.17 | -0.12 | 7/2 | 0.180 | 0.156 |
| V4 | A, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.68 | -0.60 | 9/1 | 0.059 | 0.066 |
| V4 | A, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.48 | +0.13 | 3/7 | 0.684 | 1.000 |
| V4 | A, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.26 | -0.61 | 6/6 | 0.292 | 0.195 |
| V4 | A, frontier | tenancy | denied event | strict_unsafe | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V4 | A, frontier | tenancy | denied event | all_dev | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V4 | A, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.18 | -0.35 | 32/14 | 0.042 | 0.102 |
| V4 | B, frontier | tenancy | all | strict_unsafe | 0.59 vs 0.19 | +0.41 | 8/13 | 0.026 | 0.091 |
| V4 | B, frontier | tenancy | all | all_dev | 0.62 vs 0.54 | +0.08 | 12/12 | 0.769 | 0.798 |
| V4 | B, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.12 | -0.07 | 4/2 | 0.531 | 0.531 |
| V4 | B, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.40 | -0.33 | 5/1 | 0.281 | 0.406 |
| V4 | B, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.57 | +0.04 | 4/5 | 1.000 | 0.875 |
| V4 | B, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.30 | -0.65 | 6/4 | 0.250 | 0.312 |
| V4 | B, frontier | tenancy | denied event | strict_unsafe | 1.46 vs 0.00 | +1.46 | 0/5 | 0.062 | 0.125 |
| V4 | B, frontier | tenancy | denied event | all_dev | 1.46 vs 0.25 | +1.21 | 1/5 | 0.094 | 0.250 |
| V4 | B, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.24 | -0.40 | 29/16 | 0.020 | 0.148 |
| V5 | V0 | tenancy | all | strict_unsafe | 0.61 vs 0.30 | +0.31 | 0/4 | 0.125 | 0.250 |
| V5 | V0 | tenancy | all | all_dev | 0.64 vs 0.71 | -0.07 | 2/0 | 0.500 | 0.500 |
| V5 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.05 | +0.00 | 0/0 | 1.000 | 1.000 |
| V5 | V0 | tenancy | every fact stated (S) | all_dev | 0.05 vs 0.07 | -0.03 | 1/0 | 1.000 | 1.000 |
| V5 | V0 | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.61 | +0.00 | 0/0 | 1.000 | 1.000 |
| V5 | V0 | tenancy | open branch fact only | all_dev | 0.65 vs 0.65 | +0.00 | 0/0 | 1.000 | 1.000 |
| V5 | V0 | tenancy | denied event | strict_unsafe | 1.54 vs 0.29 | +1.25 | 0/4 | 0.125 | 0.250 |
| V5 | V0 | tenancy | denied event | all_dev | 1.54 vs 1.79 | -0.25 | 1/0 | 1.000 | 1.000 |
| V5 | V0 | theft | changed-fact pairs | errors | 0.89 vs 0.83 | +0.06 | 8/8 | 0.663 | 0.750 |
| V5 | A, frontier | tenancy | all | strict_unsafe | 0.61 vs 0.19 | +0.43 | 10/15 | 0.025 | 0.098 |
| V5 | A, frontier | tenancy | all | all_dev | 0.64 vs 0.58 | +0.05 | 15/14 | 0.872 | 0.904 |
| V5 | A, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.17 | -0.12 | 7/2 | 0.180 | 0.156 |
| V5 | A, frontier | tenancy | every fact stated (S) | all_dev | 0.05 vs 0.68 | -0.62 | 9/1 | 0.018 | 0.018 |
| V5 | A, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.48 | +0.13 | 3/7 | 0.684 | 1.000 |
| V5 | A, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.26 | -0.61 | 6/6 | 0.292 | 0.195 |
| V5 | A, frontier | tenancy | denied event | strict_unsafe | 1.54 vs 0.00 | +1.54 | 0/5 | 0.062 | 0.250 |
| V5 | A, frontier | tenancy | denied event | all_dev | 1.54 vs 0.00 | +1.54 | 0/5 | 0.062 | 0.250 |
| V5 | A, frontier | theft | changed-fact pairs | errors | 0.89 vs 1.18 | -0.29 | 32/16 | 0.092 | 0.199 |
| V5 | B, frontier | tenancy | all | strict_unsafe | 0.61 vs 0.19 | +0.43 | 8/13 | 0.025 | 0.098 |
| V5 | B, frontier | tenancy | all | all_dev | 0.64 vs 0.54 | +0.09 | 12/12 | 0.747 | 0.792 |
| V5 | B, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.12 | -0.07 | 4/2 | 0.531 | 0.531 |
| V5 | B, frontier | tenancy | every fact stated (S) | all_dev | 0.05 vs 0.40 | -0.35 | 5/1 | 0.156 | 0.156 |
| V5 | B, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.57 | +0.04 | 4/5 | 1.000 | 0.875 |
| V5 | B, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.30 | -0.65 | 6/4 | 0.250 | 0.312 |
| V5 | B, frontier | tenancy | denied event | strict_unsafe | 1.54 vs 0.00 | +1.54 | 0/5 | 0.062 | 0.250 |
| V5 | B, frontier | tenancy | denied event | all_dev | 1.54 vs 0.25 | +1.29 | 1/5 | 0.062 | 0.250 |
| V5 | B, frontier | theft | changed-fact pairs | errors | 0.89 vs 1.24 | -0.35 | 26/15 | 0.037 | 0.191 |
| V6 | V0 | tenancy | all | strict_unsafe | 0.30 vs 0.30 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | all | all_dev | 0.71 vs 0.71 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.05 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.07 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.61 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | open branch fact only | all_dev | 0.65 vs 0.65 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | denied event | strict_unsafe | 0.29 vs 0.29 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | tenancy | denied event | all_dev | 1.79 vs 1.79 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | V0 | theft | changed-fact pairs | errors | 0.83 vs 0.83 | +0.00 | 0/0 | 1.000 | 1.000 |
| V6 | A, frontier | tenancy | all | strict_unsafe | 0.30 vs 0.19 | +0.11 | 10/11 | 0.386 | 0.392 |
| V6 | A, frontier | tenancy | all | all_dev | 0.71 vs 0.58 | +0.12 | 15/15 | 0.673 | 0.751 |
| V6 | A, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.17 | -0.12 | 7/2 | 0.180 | 0.156 |
| V6 | A, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.68 | -0.60 | 9/1 | 0.059 | 0.066 |
| V6 | A, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.48 | +0.13 | 3/7 | 0.684 | 1.000 |
| V6 | A, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.26 | -0.61 | 6/6 | 0.292 | 0.195 |
| V6 | A, frontier | tenancy | denied event | strict_unsafe | 0.29 vs 0.00 | +0.29 | 0/1 | 1.000 | 1.000 |
| V6 | A, frontier | tenancy | denied event | all_dev | 1.79 vs 0.00 | +1.79 | 0/6 | 0.031 | 0.125 |
| V6 | A, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.18 | -0.35 | 32/14 | 0.042 | 0.102 |
| V6 | B, frontier | tenancy | all | strict_unsafe | 0.30 vs 0.19 | +0.11 | 8/9 | 0.384 | 0.390 |
| V6 | B, frontier | tenancy | all | all_dev | 0.71 vs 0.54 | +0.17 | 12/13 | 0.550 | 0.628 |
| V6 | B, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.12 | -0.07 | 4/2 | 0.531 | 0.531 |
| V6 | B, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.40 | -0.33 | 5/1 | 0.281 | 0.406 |
| V6 | B, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.57 | +0.04 | 4/5 | 1.000 | 0.875 |
| V6 | B, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.30 | -0.65 | 6/4 | 0.250 | 0.312 |
| V6 | B, frontier | tenancy | denied event | strict_unsafe | 0.29 vs 0.00 | +0.29 | 0/1 | 1.000 | 1.000 |
| V6 | B, frontier | tenancy | denied event | all_dev | 1.79 vs 0.25 | +1.54 | 1/6 | 0.047 | 0.250 |
| V6 | B, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.24 | -0.40 | 29/16 | 0.020 | 0.148 |
| V7 | V0 | tenancy | all | strict_unsafe | 0.30 vs 0.30 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | all | all_dev | 0.71 vs 0.71 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.05 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.07 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.61 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | open branch fact only | all_dev | 0.65 vs 0.65 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | denied event | strict_unsafe | 0.29 vs 0.29 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | tenancy | denied event | all_dev | 1.79 vs 1.79 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | V0 | theft | changed-fact pairs | errors | 0.83 vs 0.83 | +0.00 | 0/0 | 1.000 | 1.000 |
| V7 | A, frontier | tenancy | all | strict_unsafe | 0.30 vs 0.19 | +0.11 | 10/11 | 0.386 | 0.392 |
| V7 | A, frontier | tenancy | all | all_dev | 0.71 vs 0.58 | +0.12 | 15/15 | 0.673 | 0.751 |
| V7 | A, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.17 | -0.12 | 7/2 | 0.180 | 0.156 |
| V7 | A, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.68 | -0.60 | 9/1 | 0.059 | 0.066 |
| V7 | A, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.48 | +0.13 | 3/7 | 0.684 | 1.000 |
| V7 | A, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.26 | -0.61 | 6/6 | 0.292 | 0.195 |
| V7 | A, frontier | tenancy | denied event | strict_unsafe | 0.29 vs 0.00 | +0.29 | 0/1 | 1.000 | 1.000 |
| V7 | A, frontier | tenancy | denied event | all_dev | 1.79 vs 0.00 | +1.79 | 0/6 | 0.031 | 0.125 |
| V7 | A, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.18 | -0.35 | 32/14 | 0.042 | 0.102 |
| V7 | B, frontier | tenancy | all | strict_unsafe | 0.30 vs 0.19 | +0.11 | 8/9 | 0.384 | 0.390 |
| V7 | B, frontier | tenancy | all | all_dev | 0.71 vs 0.54 | +0.17 | 12/13 | 0.550 | 0.628 |
| V7 | B, frontier | tenancy | every fact stated (S) | strict_unsafe | 0.05 vs 0.12 | -0.07 | 4/2 | 0.531 | 0.531 |
| V7 | B, frontier | tenancy | every fact stated (S) | all_dev | 0.07 vs 0.40 | -0.33 | 5/1 | 0.281 | 0.406 |
| V7 | B, frontier | tenancy | open branch fact only | strict_unsafe | 0.61 vs 0.57 | +0.04 | 4/5 | 1.000 | 0.875 |
| V7 | B, frontier | tenancy | open branch fact only | all_dev | 0.65 vs 1.30 | -0.65 | 6/4 | 0.250 | 0.312 |
| V7 | B, frontier | tenancy | denied event | strict_unsafe | 0.29 vs 0.00 | +0.29 | 0/1 | 1.000 | 1.000 |
| V7 | B, frontier | tenancy | denied event | all_dev | 1.79 vs 0.25 | +1.54 | 1/6 | 0.047 | 0.250 |
| V7 | B, frontier | theft | changed-fact pairs | errors | 0.83 vs 1.24 | -0.40 | 29/16 | 0.020 | 0.148 |

### What no combining rule can remove (tested product, tenancy, all deviations, counted per document)

Sequential: tested -> best combining rule (per fact the designed outcome wherever some reading supports it) -> every fact at its designed value -> also the designed document findings. Claim-runs routed to another family (or not replayed) keep their stored plan.

| part | deviations |
|---|---|
| removable by a combining rule (tested - best rule) | 46 |
| readings all wrong (best rule - facts as designed) | 14 |
| document judgments (facts as designed - also findings as designed) | 8 |
| evaluator / workflow against the reference (remaining) | 0 |
| routing (another family) or no replay | 0 |
| total tested deviations | 68 |

Steps by subset:

| subset | tested | best combining rule | facts as designed | facts and findings as designed | routing (another family) or no replay |
|---|---|---|---|---|---|
| O: denied defining event | 43 | 7 | 0 | 0 | 0 |
| O: open branch fact only | 15 | 14 | 7 | 0 | 0 |
| O: open defining event | 7 | 0 | 0 | 0 | 0 |
| S | 3 | 1 | 1 | 0 | 0 |

Facts whose designed outcome no reading supports (fact x claim-run): {"branch fact / open": 4, "branch fact / stated_true": 3, "defining event / stated_false": 1}
