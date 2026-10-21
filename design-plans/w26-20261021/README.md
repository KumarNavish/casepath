# W2.6 recorded desktop cues

Implements the [planner's priority request](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6311605774) on approved W2.5 commit `8918d117a9182ee3eb27ef9fd58f35c4ac3b94c7`. W3's separate partial work is preserved and paused. W4 is cancelled.

The approved desktop layout remains: one passage/answer box, one transport baseline, open text below the steps. A bounded read wipes the exact cited words, draws a thin thread through the gutter, and lands the fact. Its left tick persists until the next fact; recorded checks fill it. Active document requirements show Needed until a sufficient recorded check supplies Received ✓. Completed steps draw a check and then their outgoing connector. The transport hairline uses accepted completed steps divided by total steps.

The verified result crossfades into the passage position, then its left rule grows. The map stays fully opaque with muted text. An exact recorded reuse pin leaves a quiet label above the map. The role dot can take one finite breath during the remaining operation dwell; it stops when the operation changes. Cue animations run serially, use the specified durations/easing, stop on inspection, hiding or navigation, and render final states immediately under reduced motion.

## Evidence

- [Full case MP4](cues/full-case.mp4), at 1440×900, through the recorded result and handoff.
- Eight frames at a requested 120 ms interval: [fact landing](fact-landing-strip.png), [step completion](step-completion-strip.png), [answer arrival](answer-arrival-strip.png). Original full-size frames and actual capture times are in [the cue receipt](cues/cues.json).
- [Twelve overlap frames](frames/overlaps.json), using the planner's unchanged audit algorithm and schedule. All are 1440×900. The SVG thread is separately sampled along its full path against every step title, including its held and fading geometry.
- [Verification receipt](verification.json), [focused tests](unit.tap), [desktop identity tests](desktop-browser.tap), [seal verification](seal.log), and [reduced-motion capture](cues/reduced-motion.png).

The cue probe checks each trigger ID and kind against the isolated recorded operation stream, serial motion including the native answer crossfade, full-case completion, document status transitions, title-safe thread routing, 15 px minimum text and WCAG AA text contrast, zero page errors and zero attempted write requests. Pure tests reject unrelated reads, rejected checks and proposed completions, and verify that progress cannot derive from replay position. Reduced motion runs zero cue animations. Final captures use the sealed static bundle without asset overrides.

## Repairs and limits

Early probes exposed an old transport offset and a ResizeObserver that cancelled new cues on ordinary content layout; both were repaired. The streaming response-body API sometimes evicted completed reads, so the probe validates identities by re-reading only observed loopback GET URLs after capture. The first seal command encountered stale content-hash URLs; those were updated to exact asset hashes before the successful seal. Timed screenshot receipts preserve measured timing rather than claiming perfectly timed browser scheduling.

This is deterministic, local presentation evidence, not human or hosted acceptance. No paid inference, hosted mutation, deployment or exhausted original-nine rerun occurred. The Mac integration checkout and its owned startup test were untouched. The final full-suite gate remains W5.

After CODEX W2.6 READY, use only `design-plans/tools/wait_for_planner.sh` with the READY timestamp. ACK the planner, address precise changes, and resume W3 on the approved cue branch. The W3 autonomous draft-save boundary question remains pending on PR #21.
