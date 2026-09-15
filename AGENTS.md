# CasePath working instructions

This repository is the standalone CasePath source. Use `main` as the default
branch and begin with `README.md`, `docs/PRO_HANDOFF.md`, and the nearest
decision-relevant document under `docs/`.

The application lives in `casepath/`, `casepath-api/`, and `casepath-qa/`.
Product design references live in `design/northstar/`; examples live in
`examples/`. `CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md` is a historical record,
so current source and the focused docs take precedence when they disagree.

Own one bounded deliverable through implementation, focused verification, and
direct inspection. Preserve another running server and its journal. Do not
seed, rebuild, or start on port 4173 until you have confirmed that the port is
free. Use a fresh clone or a distinct temporary data root for disposable tests.

Keep immutable source bytes, source receipts, observations, interpretations,
proposals, accepted events, and read-only projections distinct. The hash-chained
claim-loop journal is lifecycle authority. Preserve idempotency, revision
checks, source grounding, replay, and explicit unknown states. Do not fabricate
progress, evidence, decisions, model results, or review.

The main workspace uses `synthetic-150`: all original intake-only inputs,
explicitly requested for local product work. Keep `synthetic-dev-60` unchanged
as the legacy regression profile. Do not import sealed targets, evaluator gold,
expected answers, private real claims, credentials, or research records. No paid
inference is needed. Preview projections are read-only and never admit evidence.
Publishing or deploying the full corpus is not implied by local implementation.

After source or documentation edits, follow the exact sealing commands in
`CONTRIBUTING.md`. Run focused regressions for the changed behavior. Run
`./bin/casepath test` when release risk or handoff scope warrants the full
suite, then inspect the working UI in an isolated local instance. Report what
actually ran, all failures, and any remaining limit.
