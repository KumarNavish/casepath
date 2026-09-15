# Main results — CTES

Primary utility U = A − P − 0.25·B (A = acquired critical evidence at the final turn, P = any premature readiness,
B = unnecessary + repeat requests capped at 4), averaged within family then across families. Frozen in PREDICTIONS.md
before any arm ran. Every arm sees the same actor JSON, one model call per arm-turn, ≤2 requests per turn, 8000 output
tokens, temperature 0, no retries, no plan repair.


## Claude Opus 5 — dev (24 episodes)

| arm | U | acquired | premature | burden | requests | hearsay receipts | state acc | failed |
|---|---|---|---|---|---|---|---|---|
| direct-end-to-end | +0.194 | 0.726 | 0 | 51 | 96 | 5 | 0.815 | 0 |
| process-only | +0.333 | 0.781 | 0 | 43 | 92 | 3 | 0.855 | 0 |
| full | +0.365 | 0.781 | 0 | 40 | 88 | 3 | 0.853 | 0 |
| ctes-ablation | +0.583 | 0.865 | 1 | 23 | 74 | 0 | 0.859 | 0 |
| ctes | +0.556 | 0.878 | 0 | 31 | 84 | 0 | 0.901 | 0 |

paired family-level differences (CTES − arm), 5000-sample bootstrap CI:

- vs **direct-end-to-end**: +0.361, 95% CI [+0.118, +0.573], families won/lost/tied 7/1/0
- vs **process-only**: +0.222, 95% CI [+0.003, +0.417], families won/lost/tied 7/1/0
- vs **full**: +0.191, 95% CI [+0.031, +0.333], families won/lost/tied 7/1/0
- vs **ctes-ablation**: -0.028, 95% CI [-0.156, +0.139], families won/lost/tied 2/4/2

## Claude Opus 5 — hidden (12 episodes)

| arm | U | acquired | premature | burden | requests | hearsay receipts | state acc | failed |
|---|---|---|---|---|---|---|---|---|
| direct-end-to-end | +0.174 | 0.778 | 1 | 25 | 46 | 4 | 0.817 | 0 |
| process-only | +0.319 | 0.757 | 0 | 21 | 49 | 3 | 0.817 | 0 |
| full | +0.361 | 0.715 | 0 | 17 | 43 | 3 | 0.813 | 0 |
| ctes-ablation | +0.215 | 0.736 | 2 | 17 | 38 | 0 | 0.806 | 0 |
| ctes | +0.639 | 0.889 | 0 | 12 | 36 | 0 | 0.889 | 0 |

paired family-level differences (CTES − arm), 5000-sample bootstrap CI:

- vs **direct-end-to-end**: +0.465, 95% CI [+0.250, +0.722], families won/lost/tied 6/0/0
- vs **process-only**: +0.319, 95% CI [+0.035, +0.556], families won/lost/tied 5/1/0
- vs **full**: +0.278, 95% CI [-0.049, +0.569], families won/lost/tied 4/1/1
- vs **ctes-ablation**: +0.424, 95% CI [+0.062, +0.924], families won/lost/tied 3/0/3

## Claude Opus 5 — transfer (10 episodes)

| arm | U | acquired | premature | burden | requests | hearsay receipts | state acc | failed |
|---|---|---|---|---|---|---|---|---|
| direct-end-to-end | +0.450 | 0.750 | 0 | 12 | 32 | 4 | 0.752 | 0 |
| process-only | +0.233 | 0.683 | 1 | 14 | 29 | 1 | 0.786 | 0 |
| full | +0.375 | 0.650 | 0 | 11 | 28 | 1 | 0.795 | 0 |
| ctes-ablation | -0.417 | 0.383 | 8 | 0 | 12 | 0 | 0.767 | 0 |
| ctes | +0.533 | 0.583 | 0 | 2 | 23 | 0 | 0.919 | 0 |

paired family-level differences (CTES − arm), 5000-sample bootstrap CI:

- vs **direct-end-to-end**: +0.083, 95% CI [-0.100, +0.275], families won/lost/tied 3/1/1
- vs **process-only**: +0.300, 95% CI [+0.050, +0.483], families won/lost/tied 4/1/0
- vs **full**: +0.158, 95% CI [-0.075, +0.383], families won/lost/tied 3/2/0
- vs **ctes-ablation**: +0.950, 95% CI [+0.750, +1.183], families won/lost/tied 5/0/0

## gpt-5.4-mini — dev (24 episodes)

| arm | U | acquired | premature | burden | requests | hearsay receipts | state acc | failed |
|---|---|---|---|---|---|---|---|---|
| direct-end-to-end | -0.420 | 0.549 | 12 | 45 | 91 | 80 | 0.605 | 0 |
| process-only | -0.101 | 0.660 | 4 | 57 | 115 | 35 | 0.687 | 0 |
| full | -0.076 | 0.559 | 3 | 49 | 86 | 47 | 0.647 | 0 |
| ctes-ablation | +0.163 | 0.767 | 5 | 38 | 87 | 0 | 0.756 | 0 |
| ctes | +0.233 | 0.868 | 0 | 61 | 103 | 0 | 0.812 | 0 |

paired family-level differences (CTES − arm), 5000-sample bootstrap CI:

- vs **direct-end-to-end**: +0.653, 95% CI [+0.309, +0.969], families won/lost/tied 7/1/0
- vs **process-only**: +0.333, 95% CI [+0.181, +0.535], families won/lost/tied 8/0/0
- vs **full**: +0.309, 95% CI [+0.045, +0.594], families won/lost/tied 6/2/0
- vs **ctes-ablation**: +0.069, 95% CI [-0.177, +0.306], families won/lost/tied 5/3/0

## gpt-5.4-mini — hidden (12 episodes)

| arm | U | acquired | premature | burden | requests | hearsay receipts | state acc | failed |
|---|---|---|---|---|---|---|---|---|
| direct-end-to-end | -0.111 | 0.597 | 3 | 22 | 51 | 24 | 0.651 | 0 |
| process-only | -0.076 | 0.694 | 1 | 33 | 61 | 11 | 0.758 | 0 |
| full | -0.083 | 0.521 | 0 | 29 | 54 | 11 | 0.679 | 1 |
| ctes-ablation | +0.236 | 0.778 | 1 | 22 | 43 | 0 | 0.802 | 0 |
| ctes | +0.160 | 0.826 | 0 | 32 | 48 | 0 | 0.810 | 0 |

paired family-level differences (CTES − arm), 5000-sample bootstrap CI:

- vs **direct-end-to-end**: +0.271, 95% CI [-0.174, +0.708], families won/lost/tied 4/2/0
- vs **process-only**: +0.236, 95% CI [+0.076, +0.403], families won/lost/tied 5/1/0
- vs **full**: +0.243, 95% CI [-0.042, +0.542], families won/lost/tied 5/1/0
- vs **ctes-ablation**: -0.076, 95% CI [-0.417, +0.229], families won/lost/tied 2/3/1

## gpt-5.4-mini — transfer (10 episodes)

| arm | U | acquired | premature | burden | requests | hearsay receipts | state acc | failed |
|---|---|---|---|---|---|---|---|---|
| direct-end-to-end | -0.433 | 0.517 | 7 | 10 | 26 | 46 | 0.552 | 0 |
| process-only | -0.267 | 0.533 | 5 | 12 | 29 | 32 | 0.557 | 3 |
| full | +0.158 | 0.433 | 1 | 7 | 26 | 35 | 0.486 | 3 |
| ctes-ablation | -0.350 | 0.550 | 7 | 8 | 20 | 0 | 0.743 | 0 |
| ctes | +0.317 | 0.717 | 1 | 12 | 31 | 0 | 0.781 | 0 |

paired family-level differences (CTES − arm), 5000-sample bootstrap CI:

- vs **direct-end-to-end**: +0.750, 95% CI [+0.133, +1.292], families won/lost/tied 4/1/0
- vs **process-only**: +0.583, 95% CI [+0.267, +0.900], families won/lost/tied 5/0/0
- vs **full**: +0.158, 95% CI [-0.108, +0.358], families won/lost/tied 4/1/0
- vs **ctes-ablation**: +0.667, 95% CI [+0.233, +1.100], families won/lost/tied 4/0/1
