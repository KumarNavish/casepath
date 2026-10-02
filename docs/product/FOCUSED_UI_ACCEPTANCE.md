# Focused claim workspace — 2 October 2026

Operation: `casepath-focused-agentic-ui-20261002`. Starting source: `8d60c40939401105d1c50f2de75a1bf8c52107ae`. This change responds to the user's direct feedback that the causal workbench was cluttered. It changes the frontend and its focused checks; the causal engine, API, journal semantics, corpus and research outputs are unchanged.

## Research translated into behavior

The [three-product study](AGENT_NATIVE_TOP_THREE.md) selected OpenHands, Dify and NotebookLM from eight candidates. Independent awards and GitHub popularity are explicitly distinguished. Public docs, published product screens and selected first-party implementation files were inspected; commercial products were not run through authenticated accounts.

- OpenHands: one active task with optional details → Overview shows the next decision; Sources opens only on request.
- Dify: staged edits with explicit impact → Process shows one selected step and immediate connections; preview, apply and unchanged consequences remain inspectable.
- NotebookLM: evidence in context → the conflict's source citation opens the exact original and candidate passage; closing it returns to the active claim view.

UI Skills used `pbakaus/distill`, then `pbakaus/polish`. Overview, Process and Documents stay mounted; switching views hides irrelevant controls without destroying form contents. The process editor's enclosing card, large validation counter, status band and repeated dependency labels were removed. Conditions, connections, provenance, reuse creation and history are disclosed where needed. Existing graph-derived document and draft behavior remains intact.

## Direct browser acceptance

Local ego-browser task space 49 used the standalone clone's sealed runtime and synthetic durable journal. No provider calls, customer messages or deployment were made.

| Check | Observed result |
|---|---|
| Open reviewed family-home claim | One primary Review step action; source rail and other task views hidden. |
| Edit a step, switch to Documents, open/close Sources, return to Process | Unsaved meaning, actor and reason remain intact. Preview describes the one changed step, unchanged requirements and unchanged next action. Keeping the current process makes no saved change. |
| Change family-home condition from false to true | Preview reports 6 affected steps, 4 changed document requirements and 7 affected connections. Apply persists graph revision 8. The spouse notice becomes held, not reviewed, linked to family-home service. |
| Open Documents after apply | Earlier draft is invalidated. A new request includes the missing second spouse-notice page and retains the held document distinction. Reload recovers the draft and selected Documents view. Draft remains labelled not sent. |
| Open the June-date citation | Correct tenant PDF loads; the candidate passage is `30. Juni`. Escape closes Sources and restores focus. |
| Keyboard tabs | End and Home select and focus the correct tabs; only one pane is visible and inactive panes are inert. |
| Fresh claim `clm_a62c178195d21648` | Empty Process/Documents states explain the prerequisite review. Review claim shows actual reading/submission progress, produces the process and next action, and retains its activity history. |
| Block only the process GET request in browser | Overview offers Open process; Process shows a recoverable failure. Documents withholds generation and the cached draft while the current process cannot be verified. Unblocking and Try again restores the process and saved draft. |
| Legacy route | `?journey=legacy-v20` still loads one paper-method script and renders its panel. The everyday workspace no longer eagerly loads that unrelated script. |
| Narrow and intermediate layout | At 390px the document width is 390px and Process is 358px; at 1024px the document width is 1024px and Process is 896px. Desktop and mobile screenshots were rendered and visually inspected. |

## Measured presentation difference

At a 1440 × 749 viewport, the same family-home claim's default scrolling work region changes from 3,532px to 673px. Its default source rail changes from open to closed. The focused Process entry shows two connected steps, with all twelve available through Show all steps. The visible viewport control count is **19 before and 20 after**, because the new tabs are explicit controls; raw control count did not decrease. These are layout observations, not user productivity or usability study results.

Screenshots: [before](screenshots/workbench-clutter-before.png), [Overview desktop](screenshots/focused-overview-desktop.png), [Process desktop](screenshots/focused-process-desktop.png), [Documents desktop](screenshots/focused-documents-desktop.png), [Overview mobile](screenshots/focused-overview-mobile.png), [Process mobile](screenshots/focused-process-mobile.png).

## Executed checks

- `node --test casepath-qa/*.test.cjs`: **87 passed**, no failures. Includes mounted edit retention, per-claim section persistence, keyboard navigation, source closure, legacy loading and withholding drafts on process failure.
- `PYTHONPATH=casepath-api PYTHONDONTWRITEBYTECODE=1 .runtime/casepath-dev-v2/venv/bin/python -m pytest -q casepath-api/tests/test_causal_workspace_v1.py casepath-api/tests/test_causal_process_v1.py`: **55 passed**, 5 dependency deprecation warnings, 90.30 seconds. Tests use temporary SQLite roots; the working journal is not their fixture.
- JavaScript syntax checks and `git diff --check`: passed.
- Eager workspace scripts: **299,162 bytes**, below the existing 300,000-byte budget. No added runtime dependency or public asset; the legacy script uses a hash-bound deferred route entry.
- Exact source/asset reseal and immutable runtime startup completed for browser acceptance. The earlier 1,639-test full-suite result belongs to the preceding causal implementation, not to this UI iteration. The focused scope here did not warrant repeating that suite.

The first direct Python test command omitted `PYTHONPATH` and failed at collection; the corrected invocation above passed. One browser check used an over-specific quote selector; inspection confirmed the correct PDF and candidate passage in the existing packet renderer. No product defect was inferred from that locator timeout.

## Remaining limits

This is local product acceptance with synthetic claims and deterministic reference workers. It does not establish real-claim correctness, commercial demand or measured handling-time savings. Screen-reader behavior and a formal automated accessibility audit were not exercised. More questions returns to its collapsed default after a full workspace rerender; ordinary tab/source navigation preserves it. Reusable process and authorization semantics retain the separately documented boundaries in [CAUSAL_PROCESS.md](CAUSAL_PROCESS.md).
