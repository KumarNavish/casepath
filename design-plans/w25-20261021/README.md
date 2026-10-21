# W2.5 calm desktop layout — 21 October 2026

This item applies the [planner's W2.5 request](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6310972539) on W2 commit `0e45bf5f44c22d7796968eb838ac7b97669587bd`. W1 and W2 behaviour is accepted; this visual revision awaits review. W3 has not started, and W4 is cancelled. The [ACK](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6311075726) also accepts the faster handoff protocol.

The desktop uses a shared 36 px left edge and a 1200 px content width. The transport and its utilities share one baseline, followed by one hairline and the Now line. The source passage retains its paper surface and pointer. Facts and document statuses are plain lines; the just-used fact has a solid green tick. The active step has one pale band, with a small check for completed steps. Role markers no longer collide with step titles.

The answer occupies the passage position while the completed map stays visible and dimmed. The handoff remains beneath the answer. Documents separates the Last result from its timestamp and uses the map's derived step labels. Cases and the saved result share the page's left edge.

## Desktop evidence

All captures are 1440×900. The baseline is the sealed W2 bundle. Final captures use the sealed W2.5 static bundle without asset overrides. The supplied overlap algorithm, selectors and timing are unchanged; its Playwright import resolves from this repository's installed QA dependency instead of the planner's Linux path.

| View | Before | After |
| --- | --- | --- |
| Demo 3 s | [W2](before/demo-03s.png) | [W2.5](after/demo-03s.png) |
| Demo 11 s | [W2](before/demo-11s.png) | [W2.5](after/demo-11s.png) |
| Demo 19 s | [W2](before/demo-19s.png) | [W2.5](after/demo-19s.png) |
| Demo 24 s | [W2](before/demo-24s.png) | [W2.5](after/demo-24s.png) |
| Demo 30 s | [W2](before/demo-30s.png) | [W2.5](after/demo-30s.png) |
| Rent claim | [W2](before/claim-rent.png) | [W2.5](after/claim-rent.png) |
| Documents | [W2](before/claim-docs.png) | [W2.5](after/claim-docs.png) |
| Knowledge | [W2](before/knowledge.png) | [W2.5](after/knowledge.png) |
| Cases | [W2](before/cases.png) | [W2.5](after/cases.png) |

The [before](before/overlaps.json) and [after](after/overlaps.json) reports include 12 frames, including demo 7/15 s and a second saved claim. A separate [story check](story/story.json) inspects the actual work, answer and handoff phases rather than inferring them from wall-clock captures: [work](story/work.png), [answer](story/answer.png), [handoff](story/handoff.png). It checks the grid, type, solid fact tick, retained map, answer above the fold, handoff typography, overflow, page errors and attempted write requests.

## Verification and repairs

See [verification.json](verification.json) and the copied test logs for commands, counts, source and screenshot hashes. The all-nine checklist test preserves the saved records while checking that each document row uses its map's derived label. Existing identity tests retain complete recorded graphs, all 73 exact cited spans, source verification, navigation/focus and unsent-draft invariants.

The initial focused run had 14 obsolete markup expectations for the removed mode disclosure and the now-shared derived step label. Their replacements still assert exact provenance and selection attributes. The first overlap pass exposed wrapped Last text on Documents; placing the result on its own row removed those hits. Visual inspection caught old CSS overriding the retained map, handoff type size and solid fact tick; the story check covers those repairs. The isolated preview initially lacked copied source bytes, and a restart capture reached it before startup completed; the fixture directories and readiness check were corrected before final capture.

An attempted desktop-only `--test-name-pattern` did not exclude seven existing phone tests under the installed Node runner: all 35 tests passed in that diagnostic run. No phone implementation or screenshots were added. The final browser command uses `--test-skip-pattern` explicitly. The full deterministic suite remains the W5 gate.

## Ownership and next action

Only the W2.5 isolated checkout writes these UI, QA and evidence files. The Mac-owned public-startup test, backend, production journals and hosted services were not changed. All preview reads use the isolated deterministic histories. No paid inference, hosted write, deployment or original-nine rerun occurred.

After `CODEX W2.5 READY`, wait only with `design-plans/tools/wait_for_planner.sh` using the last ACK/READY UTC timestamp. ACK the next PLANNER comment and address its precise changes, or begin W3 only after explicit approval or permission. The former ten-minute heartbeat is paused.
