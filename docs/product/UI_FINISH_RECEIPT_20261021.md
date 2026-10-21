# CasePath UI finish receipt — 21 October 2026

## Scope and ownership

W1–W6 and NS1a/NS1b/NS2 are planner approved. NS3 is PR #33 at
`1b61d1a`; W8 follows that source. W7 was cancelled and is excluded. The
Mac integration owner retains merge and release authority. This receipt
admits no hosted write, deployment, inference or original-nine rerun.
The original nine allowance is already consumed.

The visual target is the three approved concepts in `design/northstar`,
with the planner's final glossary and geometry. Desktop evidence is captured
at 1440×900. The gate also retains the existing narrow-screen regressions.
No synthetic branch, reviewer edit, expert-review label or missing evidence
is presented when the record does not support it.

## Evidence and reproduction

The authoritative result for this source is the adjacent W8 evidence package:
[`design-plans/w8-20261021/verification.json`](../../design-plans/w8-20261021/verification.json).
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
them. Port 4173 and the Mac-owned hosted-read-only test are untouched.

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
and the actual reuse result. Claim reader exposes established source facts.

State 7 / optional NS4 is omitted: the nine inspected DAGs contain no recorded
alternatives with consequences. No decision editor or illustrative fork is
invented. No Before/Now comparison appears because no recorded reuse changed a
step-specific outcome. Missing spaces already present in source
text stay byte-exact. Final W8 evidence reports these as deliberate limits.

## Next legitimate action

Only after the strict gate and browser receipts pass and the planner accepts
W8, the Mac owner can review the full stack for integration. READY FOR MAC is
a source handoff, not a release or evidence of public deployment. Release
requires separately authorized source-aligned frontend/API verification.
