# Complete exact d0d0fa7f final release gate

**Cloud: 2434 passed, 10 exact known skips, zero failures.** All six shard attempts exited 0, with no retries. Current-candidate Mac owner separately attested 127 passed / zero failed / zero skipped. Combined accounting is **2561 passed + 10 known skips = 2571 inventory IDs**.

Frozen candidate: `d0d0fa7f9041f7405f1d8393bacd47d4332ee79b`.
Source manifest: `cf3bfbe377fb6bd2a3dd4f44f3c3ec1c3fce8864ba19840b822abf30fa1bdd8f` / 1706 files.
JavaScript: `2a5e229f4a316bb68392c124b76cf89caafe263c47724d79f9991f9b7845fa30`.
CSS: `404b05220ed333e14ba9af9ce3f8033d58973fba8fedadf9a058d8fcc75f0e87`.

Fresh full collection has 2571 unique IDs. The 127-ID Mac roster hash is `e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8`; the Cloud complement has 2444 IDs. Assigned, collected, executed observer and JUnit ID sets match exactly, with no overlap, gaps, duplicates or deselections.

Cloud raw evidence has **7323 phase rows**: setup 2435 passed + 9 known skips; call 2434 passed + 1 known skip; teardown 2444 passed. All ten skips match their existing IDs, phases, source files, lines and reasons. Every Cloud JUnit testcase is reconciled to an assigned ID.

All seven existing normal clones prepared cleanly. Before/after source, artifact and static capsule bindings are unchanged (1706 / 25 / 37 files), with equal receipt hash `adc2a33030d3061898803e59499c6acddeae34f0cbca7382d7163801db163ccd`. Fresh short HOME/TMP roots were used; /tmp was not used. Post-prepare disk headroom exceeded 3 GiB. The scheduler observed at most three active heavy processes and exactly one full attempt per shard.

The original gate reconciler passed. The root independently parsed all raw Cloud XML and phase logs and also passed; its receipt is `coordinator/root-independent-raw-reconciliation.json`. Current Mac attestation records 381 unique phase rows and 127 JUnit cases, independently reconciled by the Mac owner, with exact clean source/manifest before and after. Raw Mac receipts remain on Mac; no raw JUnit checksum was supplied or invented.

Targeted/profile evidence is bound to immutable commit `dd6927ef152fdb4cadd6f54d10d82a16ce919cb0` on `codex/map-first-evidence-20261015`, using SHA256SUMS hash `eb3c69d64a42f09ea826d45e5a8d40effa3e4a9106ea8693c41511d92974f12c` (455 entries). Those checks were not repeated.

Raw JUnits, every observer phase, logs, command/environment receipts, source proofs, ID rosters/maps, actual durations and current Mac attestation are included. Two auxiliary read-only/evidence-processing negatives are preserved and diagnosed: a local legacy origin provenance assertion and a parser typo in post-test artifact generation. Neither affected or reran any test or verifier. The old interrupted 2a9 gate remains distinct and contributes no results here. Fixtures, journals and current source capsules remain locally preserved.
