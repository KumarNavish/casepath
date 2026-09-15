# F1 result — CasePath-Bench v3 development split is closed-form (2026-09-14)

Predictions file: `PREDICTIONS_F1_template_kernel.md` (sha256 076570ba…db0e, written before execution).
Kernel: `f1_kernel/k0_kernel.py` (sha256 098ff3d0…337b). Evaluator: the frozen public package
`casepath-bench-v3-public-current-20260821l` (`runners.public_leaderboard_v3 score-dev`, evaluator 0.1.0).
Zero model calls. Rule self-check: 940 truth-table comparisons of derived branch expressions and node
activation against all 60 gold contracts, 0 mismatches.

## Runs (60 dev cases, official plain means; family-weighted means agree to 3 decimals)

| run | routing | bindings | node R | edge R | branch acc | valid path | crit. evid. recall | unnecessary | premature | doc-state acc | exact provenance | accepted cases |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 | oracle domain | authority table + positional span + PDF lexicon | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.003 | 0.000 | 0.808 | 0.750 | 10 |
| C | oracle domain | none | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.003 | 0.000 | 0.778 | 0.000 | – |
| B | keyword (45/60) | as A2 | 0.785 | – | 0.752 | 0.644 | 0.799 | 0.191 | – | 0.628 | 0.602 | – |

Official receipt for A2: `c5131a872c8a3203e7d5e7c9dd1b56b83d5ff46193734c80735b4ae89acb0979` (submission 0f110fea…).
Zero-call alias-rule floor shipped with the package, for reference: branch 0.04, critical recall 0.54, provenance 0.00.

## Interpretation against the frozen rule
P1 and P2 hold (P1 passed after one mechanical kernel correction: chain concepts must carry their
node's reachability condition, exactly as the gold does). P3 holds. Therefore v3's process structure,
branch semantics, and evidence obligations are a deterministic function of the visible template.
The per-case content that remains is: (a) 3-way domain routing; (b) reading 2–5 scenario flags that
are constant within each near-duplicate family (11 dev families, 11 flag vectors; `mold` and
`family_home` never fire in dev); (c) PDF attachments → `provided_insufficient` (12/12 by filename
token); (d) one generator-designated message span per case (positional second-to-last clause of the
first paragraph in 8/11 families; a fixed non-positional clause in 3 families).

## Consequences
1. v3 cannot discriminate process-identification mechanisms: an arm that reads the flags and hands
   them to the kernel is at ceiling; "process-first vs direct" on v3 measures typed-output
   executability and flag reading, not process reasoning. Do not use v3 as the paper's method arena.
2. The exact-provenance endpoint partly rewards an arbitrary family constant (3/11 families); a
   benchmark paper must fix or drop it.
3. The earlier executability failures (Nemotron, Together, gpt-5.6-sol, Sonnet 5) were interface
   failures on a task whose structure is closed-form; they say nothing about process reasoning.
4. Routing is the only v3 component where a zero-model system is weak (45/60); any LLM will route.

## Not established
Hidden-split behaviour (not opened); whether strong models read the family flags correctly
(untested: optional K1 diagnostic); anything about longitudinal/return-driven acquisition.
