# CasePath UI finish receipt — 21 October 2026

## Scope and ownership

W1–W6 and NS1a/NS1b/NS2/NS3 are planner approved. NS3 is PR #33 at
`1b61d1a`; W8 includes the final refinements from planner comment 6319227767. W7 was cancelled and is excluded. The
Mac integration owner retains merge and release authority. This receipt
admits no hosted write, deployment, inference or original-nine rerun.
The Mac integration owner runs the approved nine-original allowance after handoff,
per [MAC_COMPLETION_HANDOFF_20261019.md](MAC_COMPLETION_HANDOFF_20261019.md).
Before any call, the Mac integration owner checks the ledger to confirm this allowance is still available. This receipt grants no new allowance or retry.

The visual target is the three approved concepts in `design/northstar`,
with the planner's final glossary and geometry. Desktop evidence is captured
at 1440×900. The gate also retains the existing narrow-screen regressions.
No synthetic branch, reviewer edit, expert-review label or missing evidence
is presented when the record does not support it.

## Evidence and reproduction

The authoritative result for this source is the adjacent W8 evidence package:
[`design-plans/w8-20261021-mac-r1/verification.json`](../../design-plans/w8-20261021-mac-r1/verification.json).
It records the implementation commit, sealed source manifest, served asset
hashes, completed gate counts, browser receipts and failures. A missing or
failed receipt is not a pass. Review frames and fidelity comparisons are in
that same directory. Historical W1–NS3 receipts remain unchanged.

The final strict gate is:

```sh
CASEPATH_REQUIRE_FRONTEND_SUITES=1 \
CASEPATH_NODE="$(command -v node)" \
NODE_PATH="$PWD/casepath-qa/node_modules" \
PLAYWRIGHT_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
./bin/casepath test
```

The launcher verifies the seal and isolates HOME, temporary files, database
and artifact registry. It does not use the production journal. TAP is explicit,
pytest prints skip reasons, and a missing browser dependency fails this command.
The gate now registers all nine frontend suites, including Cases, desk,
Knowledge and north-star coverage.

Export tests allocate their synthetic output in a private temporary directory
outside Git. The product launcher keeps its TMPDIR inside the checkout, which
made seven export tests hit the intended destination guard before exercising
their assertions. The fixture repair preserves that guard and all assertions;
all 26 export tests pass under the launcher's original temporary-directory
conditions. The strict gate is rerun against the repaired source.

The static inventory also includes the approved Mulish font and its OFL file,
with a license link in the page head. All 16 static-build checks pass. The first
strict run is preserved in the evidence package: 2,854 passed, ten failed and
ten skipped. Seven failures were the export fixture placement, two were font
packaging assertions, and one is the separately owned hosted-startup test. The
ten skips require unavailable historical packets; no frontend suite was skipped.

Browser scripts `verify-process.mjs`, `verify-memory.mjs`,
`verify-acceptance.mjs`, `verify-motion.mjs` and `verify-reduced.mjs` run against
the owned GET-only preview on 4180. Final proof uses built assets without
overrides. Operations use the immutable `desk-v3.json.gz` fixture; it is never
recaptured. Every non-GET/HEAD request is blocked and recorded. Console errors
and page errors are captured. Paid provider calls and hosted writes are zero.

The all-nine walk covers Cases, every step, every grouped source, received
documents, exact cited spans, the draft, reasoning, History and recorded
checklist reuse. Reload and Back/Forward retain the selected step and passage.
A browser-local draft copy is edited, saved, reloaded, copied and downloaded;
its recorded original remains unchanged. A storage failure retains unsaved
edits. The 150-case catalog and unrun originals are inspected without starting
them. Port 4173 is untouched. The Mac-owned test changes only through the exact owner commit described below.

## Mac review closure map

| Finding | Disposition and decisive evidence |
| --- | --- |
| 0 | One reference roster governs entry, markers and the picker; workspace roster regressions. |
| 1 | Skip during preparation advances through the intended case; two-Skip and natural-handoff regressions. |
| 2, 6, 12 | Failed Knowledge reads say the read failed and offer Open Knowledge; successful empty reads remain distinct. |
| 3 | Skip after Pause exits the result hold immediately; no fresh eight-second timer. |
| 4 | Saved-history mode is retained across Skip; no operations request is substituted. |
| 5, 20 | The Python wrapper explicitly requests TAP, including on Node 26. |
| 7, 21 | Strict gate requires Node/Playwright and prints all pytest skip reasons. |
| 8 | flock contention and other lock errors retain distinct exit statuses; launcher regression. |
| 9 | Model wording remains behind Recorded wording; templated results lead. Existing outcome and browser paint regressions remain. |
| 10 | Next action comes from actual missing evidence or the honest no-gap template; desk regressions. |
| 11 | Draft controls open recorded subject/body; completed reference summaries are not mislabelled as missing-document requests. |
| 13 | Replay day uses the same local date format as History/Last; non-UTC midnight regression. Intake calendar dates stay unchanged. |
| 14 | One case has a saved history; plural counts retain have. |
| 15 | Selected subject lines become focusable current lines; mounted replacement-focus regression. |
| 16 | Pause/Resume keep focus on their toggle; Skip retains focus; disappearing transport moves focus to the case title. Completed process selection also retains focus. |
| 17 | Reduced-motion replay stops at each result; explicit Skip can advance. |
| 18 | Transport controls use an inset focus ring so clipping cannot hide it. |
| 19 | Existing responsive answer focus follows its scroll; Requires/Leads to keeps focus in the new answer. Full browser suite retains narrow-screen checks. |
| 22 | Mounted private/public replay tests require Fictional case and public View only. The safety guide is available when paused; autoplay keeps it collapsed. |
| 23 | Cited underline is neutral #525252, above 3:1 on the light field, with spoken citation boundaries outside the immutable quote. |

## North-star states and limits

States 1–5 are captured from real recorded playback: ready, source opened,
exact span selected, fact linked and process node accepted. Motion is serial,
source-pinned and disabled for reduced motion. State 6 is the completed
selected-step process. State 8 connects the selected step to its exact source, the earlier checklist
and the actual reuse result. The memory cards align with the selected node within the content bounds, joined by one level rule. Claim reader exposes established source facts and quotes the request only when it exists verbatim in the recorded message. Source checker groups verified passages under one heading per source.

State 7 / optional NS4 is omitted: the nine inspected DAGs contain no recorded
alternatives with consequences. No decision editor or illustrative fork is
invented. No Before/Now comparison appears because no recorded reuse changed a
step-specific outcome. Missing spaces already present in source
text stay byte-exact. Final W8 evidence reports these as deliberate limits.

## Final live-canvas correction

Planner changes 6321748940 and binding answer 6321925670 are included in this
revision. The dashed 1.5px #C4C5C6 ring and #9C9BA0 label follow the same current
recorded node as the plan title. Source-pinned, node-bound fact extractions join
the source's Read row; shared/unlinked work stays out. Rows sort by their first
operation and their status and 2px progress bar follow completed recorded
operations. Every sequence in all nine streams is checked for row state,
progress and ring/title agreement.

Recorded fact labels remain whole, with equal-height cards allowing three lines.
Only unlabelled quotes use the planner-approved three-line ellipsis. Their full
verbatim text remains in the DOM and hover title and in the source highlight.
The dotted connector appears after the last card arrives and begins at its right
edge. The source, fact and accepted-node frames are captured at rest.

## Frames beside their concepts

The side-by-side images below contain the concept on the left and the product on
the right. They preserve recorded content instead of illustrative concept copy.
State 7 remains omitted because the record has no alternatives with consequences.

| State | Concept beside product | Overlay / mean difference | Matched | Deliberate | Pending |
| --- | --- | --- | --- | --- | --- |
| 1 · Ready | ![Concept and ready state](../../design-plans/w8-20261021-mac-r1/fidelity-state1-ready-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-state1-ready-overlay.png) · 3.53% | Shell, type, palette and overview geometry | Read-only Watch the analysis action. | None in W8; W9 presentation review follows. |
| 2 · Source opened | ![Concept and opened source](../../design-plans/w8-20261021-mac-r1/fidelity-state2-source-opened-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-state2-source-opened-overlay.png) · 4.43% | Shell, type, palette and overview geometry | Only recorded source fields. | None in W8; W9 presentation review follows. |
| 3 · Exact passage | ![Concept and exact passage](../../design-plans/w8-20261021-mac-r1/fidelity-state3-exact-passage-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-state3-exact-passage-overlay.png) · 5.31% | Shell, type, palette and overview geometry | Exact source offsets; no fact connector yet. | None in W8; W9 presentation review follows. |
| 4 · Fact | ![Concept and source fact](../../design-plans/w8-20261021-mac-r1/fidelity-state4-source-fact-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-state4-source-fact-overlay.png) · 5.41% | Shell, type, palette and overview geometry | Full recorded label; connector starts at the card. | None in W8; W9 presentation review follows. |
| 5 · Node accepted | ![Concept and accepted process node](../../design-plans/w8-20261021-mac-r1/fidelity-state5-process-decision-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-state5-process-decision-overlay.png) · 5.37% | Shell, type, palette and overview geometry | Recorded process and operations. | None in W8; W9 presentation review follows. |
| 6 · Process, case 1 | ![Concept and case 1 process](../../design-plans/w8-20261021-mac-r1/fidelity-case1-process-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-case1-process-overlay.png) · 6.1% | Shell, type, palette and overview geometry | Actual linear DAG and exact source passage. | None in W8; W9 presentation review follows. |
| 6 · Process, case 4 | ![Concept and case 4 process](../../design-plans/w8-20261021-mac-r1/fidelity-case4-process-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-case4-process-overlay.png) · 6.02% | Shell, type, palette and overview geometry | Actual decisive legal test. | None in W8; W9 presentation review follows. |
| 8 · Checklist, case 1 | ![Concept and case 1 checklist reuse](../../design-plans/w8-20261021-mac-r1/fidelity-case1-memory-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-case1-memory-overlay.png) · 4.51% | Shell, type, palette and overview geometry | Recorded checklist reuse; no unsupported Before/Now. | None in W8; W9 presentation review follows. |
| 8 · Checklist, case 4 | ![Concept and case 4 checklist reuse](../../design-plans/w8-20261021-mac-r1/fidelity-case4-memory-side.png) | [Overlay](../../design-plans/w8-20261021-mac-r1/fidelity-case4-memory-overlay.png) · 4.25% | Shell, type, palette and overview geometry | Recorded checklist reuse; no expert-review claim. | None in W8; W9 presentation review follows. |

The revision's `verification.json` records per-case overlap counts for live
selection/fact frames, every completed process node, every memory node and role
views. Counts are admitted only from completed browser receipts; missing or
failed checks are never counted as zero.

### Nine-case overlap audit

| Case | Live checks / overlaps | Process and role checks / overlaps | Memory checks / overlaps | Total overlaps |
| --- | --- | --- | --- | --- |
| 1 · `clm_314f2d309fea25e6` | 3 / 0 | 10 / 0 | 6 / 0 | 0 |
| 2 · `clm_4a07dbbbd859a3ce` | 3 / 0 | 10 / 0 | 6 / 0 | 0 |
| 3 · `clm_95d08975bc575592` | 3 / 0 | 10 / 0 | 6 / 0 | 0 |
| 4 · `clm_0f4f13b1e3e1328c` | 3 / 0 | 6 / 0 | 2 / 0 | 0 |
| 5 · `clm_393285577dcb12c4` | 3 / 0 | 6 / 0 | 2 / 0 | 0 |
| 6 · `clm_4a53299cfe619303` | 3 / 0 | 6 / 0 | 2 / 0 | 0 |
| 7 · `clm_2c55cdd816b1d0e8` | 3 / 0 | 7 / 0 | 3 / 0 | 0 |
| 8 · `clm_543f08f2415b2a33` | 3 / 0 | 7 / 0 | 3 / 0 | 0 |
| 9 · `clm_7dbd7c7d1c4ddf90` | 3 / 0 | 7 / 0 | 3 / 0 | 0 |

All 129 checks completed at 1440 × 900 using built assets. The generic box audit excludes the role cursor’s coarse box; a separate motion check verifies that its badge does not cover source text. Every source pin is checked against the recorded offsets and quote.

## Owner correction integrated unchanged

Planner comment 6320266952 authorizes the Mac owner's commit
`4c46f43bdfd32c4fe965d0b9593b65d84a0c8c33`, integrated unchanged with
`git cherry-pick -x` as `1122d7b14ec64e90c5d0bdec11d759e7fbb3c94a`.
The author and message are retained. This corrects the stale hosted-startup
test contract to require passive warmup on a closed, model-free, read-only
controller. SQL is limited to SELECT/BEGIN/COMMIT, database rows stay unchanged,
and every saved claim is covered. Claim discovery, resume and wake remain
forbidden. No additional protected-test or hosted-startup edit is included.

## Next legitimate action

After W9 product direction and film are approved, run the full strict gate on
one sealed W8+W9 commit and post READY FOR MAC. Only then can the Mac owner
review the full stack for integration. READY FOR MAC is
a source handoff, not a release or evidence of public deployment. Release
requires separately authorized source-aligned frontend/API verification.
