# Map-first writer receipt

Source branch: `codex/map-first-stage-impl-20261015` (pushed).
Clone: `/workspace/casepath-map-first-impl-20261015`.
Verified base: `7904c8050a10568d4168c92b77ee55ec1d7b2b13`.
Final writer commit: `432ec02b28992f2adaf9d708ada8f134b4494532`.
Working tree clean after final focused run. Integration, final manifest/seal, browser/profile acceptance and publication remain with the integration owner.

Changed paths only:
- `casepath/assets/autonomous-workspace-v1.js`
- `casepath/assets/autonomous-workspace-v1.css`
- `casepath-qa/autonomous-workspace-v1.test.cjs`

Final SHA256:
- JS: `59d03ed22e2a99c12222c88595a03f9f0bff3887e9438435b299eed9021f3cfc`
- CSS: `caa8585dc9d0a5902345bd7324dcae7826eddeaad87d63fee63f9e10da9313d5`
- Focused module: `4b6c5d226c409b2ee5b1ca289dc4037f26ef2b86b7a1f12838984fe27095eafa`

Node: v24.19.0. Per-command HOME `/workspace/map-writer-home`; TMPDIR/TMP/TEMP `/workspace/map-writer-tmp`. No new dependencies, servers, provider calls, backend, journal, trace or corpus writes. Reused the native fixture and existing GET-only server identified by QA; writer did not stop or modify that server.

Final exact command (repository working directory):

```bash
HOME=/workspace/map-writer-home TMPDIR=/workspace/map-writer-tmp TMP=/workspace/map-writer-tmp TEMP=/workspace/map-writer-tmp node --test casepath-qa/autonomous-workspace-v1.test.cjs casepath-qa/unified-product-v1.test.cjs > /workspace/casepath-map-first-writer-evidence-20261015/432ec02-focused-final.log 2>&1
```

Exit 0; 209 tests passed, 0 failed, 0 skipped. Prior successful focused reruns are preserved in `focused-second.log` through `focused-ninth.log`. `node --check casepath/assets/autonomous-workspace-v1.js` passed before the early candidate; all subsequent test runs loaded the same production module. No full suite or source seal run, per bounded assignment.

Initial focused regression command:

```bash
HOME=/workspace/map-writer-home TMPDIR=/workspace/map-writer-tmp TMP=/workspace/map-writer-tmp TEMP=/workspace/map-writer-tmp node --test casepath-qa/autonomous-workspace-v1.test.cjs > /workspace/map-writer-tmp/focused-first.log 2>&1
```

Exit 1; 170/179 passed, 9 failed. Raw output preserved as `focused-first.log`. Failures were prior presentation assertions: separate read/match dwell, whole-source body/initial incoming text, zero planned slots, retired-slot disappearance and hidden decision source context. Assertions were updated to the expressly requested compact map, planned empty slots and consequence-only dwell. Authority/hash/checkpoint/history tests stayed in place; new causal ancestry, ambiguous-source, no-future, phase, source-change, native-offset, route preference and metadata-context regressions were added. Final 209/209 passes.

Incidental inspection failures, corrected before edits:
- Initial `git clone --shared /workspace/casepath-map-first-stage-20261015 /workspace/casepath-map-first-impl-20261015 && git -C /workspace/casepath-map-first-impl-20261015 checkout -b codex/map-first-stage-impl-20261015 7904c8050a10568d4168c92b77ee55ec1d7b2b2b13` exited 128 because of a mistyped commit. Clone succeeded; subsequent `git rev-parse HEAD` verified the exact correct base and checkout used `7904c8050a10568d4168c92b77ee55ec1d7b2b13`.
- Initial combined documentation read/search included root `PRO_HANDOFF.md`, which does not exist; `rg` exited 2. Correct `docs/PRO_HANDOFF.md` was then read in full.
- An exploratory `head -c 500 /workspace/operation-runtime-evidence/native-sidecars/*heating*.json` exited 1 because native files use claim IDs. Actual `clm_314f2d309fea25e6.json` and the other eight native sidecars were then inspected by exact path.

Commit sequence:
- `bde49ee` early coherent source candidate.
- `22e8f6e` restored original accepted document evaluation plus observed-check guard, also restored transfer guard.
- `7ea942b` focused regressions, exact preceding source ancestry, route preference retention, stale fetch identity checks, visible landing phases.
- `22ed5a5` bounded playback viewport and adjacent excerpt; owner-trace animation completion guard.
- `432ec02` complete source phrases, native/body-clamped context, substantive source/meaning deduplication.

Native browser measurements belong to QA receipts and are not claimed as writer-run validation. Writer visually inspected QA's actual frame07 before and after the layout fix. The after image showed persistent horizontal process, compact adjacent actual excerpt, pending target hidden and transport visible at 1280x800. Remaining cross-viewport/all-nine/performance acceptance is owned by QA/root.
