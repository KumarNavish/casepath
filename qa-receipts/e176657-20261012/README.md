# CasePath exact-candidate release gate

Candidate: `e176657b9307ad657fd895e57e83ce88e140bcf5` on canonical branch `codex/casepath-causal-experience-integration-20261009`.

The selected complete shard runs give Cloud 2,317 passed, 0 failed, and 10 unchanged frozen-research-fixture skips across 2,327 canonical IDs. The Mac coordinator reported 127 passed with exact assigned-ID equality for the same candidate; Mac JUnit remains on Mac F2 and was not parsed on Cloud. Combined: 2,444 passed, 0 failed, 10 known skips across 2,454 canonical IDs. See `selected-coverage-summary.json` for selected attempts and evidence basis.

Original shard6 failed one late-arrival completion wait. That original exit1, stdout, JUnit, full failure state, and journal evidence are preserved in `coverage-summary.json`, `shard6/`, and failure files. The unchanged test passed in the one-ID diagnostic, and the user-directed entire542-ID shard6 rerun then passed with exit0 in295.241seconds. The selected result uses complete original shards1-5 and complete full-shard6-rerun. No source, manifest, 15-second timeout, skip, audit, or model configuration was changed.

Fresh collection, Mac scope, partition, selected executions, observer reports, and JUnits reconcile with zero missing, duplicate, or extra selected IDs. Intentional repeat executions are recorded separately. All1,648 sealed file hashes/sizes and exact clean HEADs are checked. `known-skips.json` lists all10 unchanged IDs/reasons. Each complete shard has all durations and independent stdout/JUnit/exit-status receipts.

Six distinct prepared checkouts/venvs, HOME/TMP/caches/databases/registries, and fresh retry outputs were used on Cloud host656813ef2295. Runtime versions are Python3.13.9,Node24.19.0,pytest8.4.2. Tests ran with the reused sanitized deterministic harness and no credentials/provider/transport variables. Failed preparation transport attempt1 is retained; attempt2 preserved inherited platform proxy/CA variable names for frozen dependency preparation, with no TLS or lockfile bypass.

No paid inference, production operation, deployment, allowance change, commit, or push was performed by this gate worker. Evidence publication belongs to the coordinating root agent. `bundle-sha256.json` records packaged artifact sizes/hashes; original and selected coverage receipts remain separate.
