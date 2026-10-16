# Cloud release gate: 84f972c86fe556ccf5cac7e2aacddc6e154fdbb9

Cloud executed 2,503 unique tests once: 2,493 passed, 10 unchanged known fixture skips, 0 failed phase rows. The fresh complete inventory contains 2,630 IDs, 17 more than the 2,613 baseline, with no removed IDs.

The Mac owner separately attested 127 passed, zero skipped and zero failed tests on the identical sealed commit (381 phases, 127 JUnit cases, 126.0978 seconds). Those exact 127 IDs are the explicit complement of Cloud. Combined counts with that attestation are 2,620 passed and 10 known skips; Cloud has not inspected Mac raw receipts. Independent cross-host raw combination remains pending.

**Resource qualification:** the 3 GiB floor was breached during normal prepare2's transient uv-cache allocation. Minimum observed free bytes were 3,138,469,888, against 3,221,225,472. All six actual test attempts started above the floor, and maximum overlapping prepare/test processes was 3. The unexpected cache was retired only after successful prepare, and additional completed reproducible source was retired before subsequent prepares. Original observations remain intact. Functional checks passed; this receipt does not claim every release-gate guard was satisfied.

| Shard | Selected | Passed | Known skipped | Failed phases | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 9 | 9 | 0 | 0 | 663.86 |
| 2 | 421 | 421 | 0 | 0 | 533.28 |
| 3 | 651 | 650 | 1 | 0 | 513.16 |
| 4 | 391 | 391 | 0 | 0 | 486.08 |
| 5 | 346 | 346 | 0 | 0 | 481.02 |
| 6 | 685 | 676 | 9 | 0 | 506.07 |

All six independent normal clones remained clean at the exact candidate. Each completed normal `./bin/casepath prepare`; 12 actual before/after verifications bound all 1,709 sealed source files, 25 generated artifacts, 39 static files, and the unchanged runtime capsule. Manifest SHA-256: `83d09acf9bfae53fd19d5effbae68bf2db2d20d3844938f0c6734454fd0a8382`. Capsule receipt file SHA-256: `e429f15e95b4c80c77ac5562cee929327ec90afadc93a32f43e0a530c9a1d4ea`.

Selected IDs, raw observer IDs and JUnit mappings agree exactly for every Cloud test; Cloud plus the exact Mac partition equals the complete inventory without overlap or gaps. The ten skip IDs, phases and complete reasons match the immutable prior inventory. Cloud recorded 7,500 phase rows. All 17 newly collected tests passed.

Every native attempt used its exclusive first-attempt latch. There were no retries, source edits, source reseals, browser work, provider calls, production operations or deployment. Test environments had isolated HOME, temporary, database and artifact paths under `/workspace`, deterministic mode and no product/model credentials. Managed proxy and CA variables remained available during normal preparation.

`aggregate.json`, `proof-disjoint-union-after.json`, `resource-after.json`, `source-verification.json`, and per-shard standard raw files establish these results. Exact commands and controlled environments are in each `command.json`, `result.json` and `prepare.json`; raw phase observers and JUnit remain uncompressed beside them.

Export only files listed by `raw-evidence-files-SHA256SUMS.txt`, plus that manifest, `raw-evidence.tar.gz`, `raw-bundle.json` and `SHA256SUMS`. Runtime DBs, caches, passing temporary fixtures and duplicate local per-shard retirement snapshot archives are excluded. Local originals, any failed fixtures, journals, receipts and unrelated jobs remain preserved. Retirement records bind proof and archive hashes. Root owns independent export validation, Git receipt publication and integration; this coordinator made no branch writes.
