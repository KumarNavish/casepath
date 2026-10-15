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

## Settled-map correction, authorized after the initial handoff

Concrete Mac acceptance failure: settled map, outcome, procedure and transport exceeded the 1600x900 viewport; supported document slots duplicated the outer requirement title, inner source name and a quote already present as a fact chip.

Product commit `57a4153` changes only settled slot markup and map-phase CSS: one existing source/check card per filled slot, no repeated outer label or preview quote; 16px settled node/fact/source-card text, tighter map row gaps and a wider 20px outcome with compact legal-basis/reuse spacing. Active excerpt, timing, phase, source checks and source inspection behavior are unchanged. Commit `143711e685ecc35285bb3bebdbeb2c0fa0f19d32` corrects only the new test fixture's missing document catalog label. Both commits pushed on the same worker branch; working tree clean.

Final product bytes after this correction:
- JS SHA256: `9f1dc91cdf4caf9b2111254c27661f726aa1eb15043914113705cb216c0c8023`
- CSS SHA256: `2acd53960f4e432989498ee75e3db53ff8d21308423664f9b60336b0dc077f22`

One new focused module regression checks the single settled card, unchanged active preview and retained exact source/control/native citation/check identity. The first run at `57a4153` had 209/210 pass (exit 1): the new test fixture lacked `graph.document_catalog`, so its active outer label correctly rendered `Document require` rather than the test's assumed `Separate notice`. Raw output is `57a4153-focused-final.log`. The fixture now supplies its explicit catalog label; no product logic changed for that test correction.

Corrected final command, exit 0, 210/210 passed, 0 failed/skipped:

```bash
HOME=/workspace/map-writer-home TMPDIR=/workspace/map-writer-tmp TMP=/workspace/map-writer-tmp TEMP=/workspace/map-writer-tmp node --test casepath-qa/autonomous-workspace-v1.test.cjs casepath-qa/unified-product-v1.test.cjs > /workspace/casepath-map-first-writer-evidence-20261015/settled-focused-corrected.log 2>&1
```

An initial literal replacement script for this correction exited 1 at its exact-string assertion before changing any file; the following Git command reported `nothing to commit, working tree clean`. The corrected replacement matched the existing template and produced the scoped commit above. No full suite/seal/deployment was run. Actual normally played landed-map geometry remains QA/Mac-owned; the writer inspected the saved Cloud native result image with all eight fact chips and three checked source cards before editing, rather than using a head-only projection with no docked observations.

## Retired-source correction after normal nine-case QA

QA found an actual uncited `knowledge.reuse` step rendering retained `displaySource` above the graph, pushing active transport below the viewport. Commit `29e08999cf07a7b1d9c58614d71ffd5a8d5791cc` changes one production line: stage excerpt markup is emitted only when `operationReading(trace).active` identifies the current actual bounded citation. This keeps uncited knowledge/condition/requirement steps from showing retired source context, while preserving nonstage History/full-source context and deliberately cited operation inspection. CSS unchanged from the settled-map correction.

One meaningful focused regression covers retained source suppression, exact native pin/History retention and actual cited inspection. Initial new-test run had 210/211 pass (exit 1); its source-text regex assumed `Before 😀` was contiguous in HTML, while the correct existing markup wraps `Before` in its exact citation span. Raw log: `retained-source-focused.log`. The assertion now follows the exact span boundary, CRLF encoding and preserved Unicode text. Corrected command exited 0 with 211/211 passed, 0 failed/skipped:

```bash
HOME=/workspace/map-writer-home TMPDIR=/workspace/map-writer-tmp TMP=/workspace/map-writer-tmp TEMP=/workspace/map-writer-tmp node --test casepath-qa/autonomous-workspace-v1.test.cjs casepath-qa/unified-product-v1.test.cjs > /workspace/casepath-map-first-writer-evidence-20261015/retained-source-focused-corrected.log 2>&1
```

Final JS SHA256: `d741a1af6bf769f243cd0d961f724222544046e6bb959cf9c0ffdc59b5c35440`.
Final CSS SHA256: `2acd53960f4e432989498ee75e3db53ff8d21308423664f9b60336b0dc077f22`.
Pushed worker branch clean and frozen for final QA/integration. No pacing, motion, reducer, context, backend, corpus or journal changes made for this follow-on.

## Outcome text size correction

CSS-only commit `7677fe8f86b61bab3ad73204af5d886afe1e4e11` restores the settled legal-basis text, reused-procedure paragraph and reused-version button to 18px. Map nodes/facts/source cards remain 16px; outcome remains 20px. No geometry assertions or tests weakened. CSS SHA256 is now `404b05220ed333e14ba9af9ce3f8033d58973fba8fedadf9a058d8fcc75f0e87`; JS unchanged (`d741a1af6bf769f243cd0d961f724222544046e6bb959cf9c0ffdc59b5c35440`).

The same focused module command was run once for this delta with output redirected to `outcome-font-focused.log`: exit 0, 211/211 passed, 0 failed/skipped. Worker branch pushed and clean, frozen for final geometry/performance acceptance.
