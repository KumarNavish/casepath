# CasePath-Bench-v3

A fully synthetic benchmark for executable process reconstruction, activation, and process-derived evidence planning. Data and documentation: CC BY 4.0. Code: Apache 2.0.

The 60-case dev split includes gold contracts. The 90-case test split exposes claims, source files, and evaluator commitments only. Test scoring runs through the locked leaderboard evaluator. Near-duplicate families never cross splits. Every case exposes the same three static rule templates; no hidden subtype router selects a template. CasePath-Bench tests closed-vocabulary domain selection and case-specific structure, activation, and evidence planning. PAGED supplies the open-vocabulary process-discovery test.

The `state-stress/` track adds 48 paired variants over 12 stratified bases. It objectively tests sufficient evidence, conditional requests, irrelevant branches, and empty-request stopping while requiring the unaffected process graph to remain stable. Development gold is public; hidden variants expose commitments only.

## Reproduce the public development evaluation

From this directory, install the pinned package and run:

```bash
uv sync --frozen --offline --extra dev
uv run python -m runners.public_leaderboard_v3 --root . baseline-dev --output alias-rule-dev.jsonl
uv run python -m runners.public_leaderboard_v3 --root . validate-submission --submission alias-rule-dev.jsonl --split public_dev
uv run python -m runners.public_leaderboard_v3 --root . score-dev --submission alias-rule-dev.jsonl --output alias-rule-dev-score.json
uv run python -m runners.public_leaderboard_v3 --root . verify-hidden-interface
uv run python reproduce/independent_release_verifier.py --root .
uv run python -m runners.state_stress_v3 --root . baseline-dev --output state-stress-floor.jsonl
uv run python -m runners.state_stress_v3 --root . score-dev --submission state-stress-floor.jsonl --output state-stress-floor-score.json
uv run pytest -q
```

A submission is JSONL with exactly one object per case: `{"case_id": ..., "candidate": ...}`. The candidate must satisfy `schema/submission-v3.schema.json`. Missing, duplicate, extra, or malformed rows fail closed with exit code 2. Development scoring reports the denominator for every overall and domain metric.
