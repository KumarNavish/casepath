# INTERRUPTED / SUPERSEDED exact 2a9aa89f gate

Candidate: `2a9aa89f1a5ae843527fcc0a2afcccb5e5e6cfae`.
Manifest: `7d0ff8316b243d2d0b5eacd64909c94fe94f64613c65857b44e315844127bea2` (1706 files).

This gate did not complete and provides no full or combined green result. Root/Mac explicitly stopped the obsolete candidate to prepare a performance correction. No result applies to any later SHA.

The complete final raw interrupted bundle is in **interrupted-final/**. Earlier top-level preparation receipts remain for history. The final outcome is interrupted-final/interrupted-aggregate.json; its process, signal and source proofs are adjacent.

All seven existing normal clones prepared cleanly. Before and after source/artifact/static capsule checks match exactly (1706 / 25 / 37 files; capsule receipt `ffdd095b51b6cff0078e6deaf09881e71d5a31719e6b82724e833479dd7941a3`). Fresh inventory collected 2571 unique IDs, split into the exact 127-ID Mac roster and 2444-ID Cloud complement. These are planned inventory proofs; execution did not cover the planned partitions.

Shards 1–3 were interrupted: pytest exits **2, 2, -15**, after **244.7s, 255.0s, 262.5s**. Raw observer rows cover 71 IDs: 68 have complete passing setup/call/teardown phases, and three have incomplete phases. JUnit files are incomplete: 71 testcase rows, with headers totaling 68 tests. Testcase presence is not a completed pass. No failed phase rows or runtime skips were observed before interruption. All ten known skips were not reached and verified at runtime.

Shards 4–6 never started and have no attempt IDs, phase rows, results or JUnits. Their 1391 assigned IDs remain unexecuted. No test retries occurred. The scheduler stayed stopped while running children ended, then was terminated/reaped with exit **137**, preventing queued launches. Owned pytest and scheduler PIDs are absent. Three orphaned runner zombies have no execution or CPU.

Raw logs, observer phases, incomplete JUnits, commands, controlled environment values, source proofs and process/signal receipts are preserved. Full and partial success reconcilers were retained as provenance and were never executed. A read-only source-authority preflight negative and a copy2 evidence-packaging PermissionError are preserved with diagnoses. Packaging used fresh writable byte copies, without changing any original capsule permissions or rerunning verification/tests. Fixtures, journals and current capsules remain locally, as recorded in retained-local-state.json.

A new sealed candidate requires a fresh inventory and all six full attempts after explicit release authorization.
