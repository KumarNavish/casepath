# CasePath UI brief for Codex — 20 October 2026

Planner: Claude Cloud session `session_01Ua3SP9623UZKFmS3phA6BH`, which reviews every
pushed result. Executor: a Codex Astra chat, effort extra high, in the Die Mobiliar project.
Repository `KumarNavish/casepath`. Start branch `claude/casepath-cues-prototype`, whose
parent is `claude/casepath-agents-20261019` (PR #21, the round-1 clarity fixes).

## What the user wants (verbatim, in order)

- "a genuinely useful agent-native system whose UX feels awe-inspiring and maximally clear and transparent"
- After a full visual redesign: "I hate the new UI, I really liked the original UI just wanted
  you to change the focus, clarity, and add things for visuals cues … it looks AI slop".
- On the cue prototype: "moving in the right direction but is still not very clear and clean …
  not yet feeling really simple and easy to understand what's happening! The goal is make this
  something memorable and viscerally useful, and felt that way too from the demo!"
- "The real functionality should be your closing gate."

## Hard rules

1. Keep the original visual system: colours already defined in
   `casepath/assets/autonomous-workspace-v1.css`, its fonts and type sizes, layout, hairlines
   and page background. No new palette, serif, cards, shadows, gradients, pills or icon sets.
   Each addition should look like something the original designer would have added.
2. Simplicity beats more information. Remove or hide before adding.
3. Honesty (AGENTS.md): every cue, line and motion is bound to a recorded event or saved
   state. Never imply a read, fact, check or conclusion that was not recorded. Unknown
   stays unknown.
4. Reduced motion, keyboard focus, WCAG AA contrast and 390 px phones must keep working.
5. Seal per `CONTRIBUTING.md` (sha256 queries in `casepath/index.html`, then the sealing
   commands). Every pushed commit is sealed.

## Starting point (unsealed prototype on this branch)

The diff against the parent touches only `autonomous-workspace-v1.js`/`.css` and
`autonomous-language-v1.js`. Screenshots are in `design-plans/cues-20261020/`.

- The active step has a thin green rule; other steps' facts and documents recede (opacity .75).
  The page follows the active step. The recorded result stays in the Last line.
- Source to fact: a landed fact and the document box it satisfies take the passage's
  green tint. The open passage box slides above the active step and points at it.
- Progress: "Step N of M" in the transport row, connectors draw in when the evaluation
  opens them, and the active role marker pulses (off under reduced motion).
- Plain narration: "Reader finds “CHF1650” in “Tenancy details”. To be confirmed.",
  "Checker checks “Heating service report”. Confirmed by the document.",
  "Rulebook reaches the result. …". "Fixed rules" stays in the header line only.
- "Customer asks <original subject line>" under a featured case title.
- Outcome: the plain recorded label first, the recorded legal sentence second; "Documents 3 of
  3 received"; the checklist says Received / Missing / Not needed.

Known prototype defects to fix: the flying fact label can cover a step name or document
box for about a second; long fact chips wrap into tall boxes; the follow-scroll can push the case
title off screen. "on2025-02-01"-style missing spaces come from the source text, not the
UI, so leave the quotes verbatim.

## Preview with real recorded work (no model calls)

After `./bin/casepath prepare` and one sealed `./bin/casepath dev` start (port 4173), run
`PORT=4180 design-plans/tools/run_seeded_preview.sh`. That stages the nine deterministic
reference histories into a copied database and serves them on 4180. For before/after
captures at fixed moments, use `design-plans/tools/capture_moments.mjs` (Playwright;
asset overrides allowed). Judge every change in that preview at 1440×900 and 390×844.

## Work items, in order. One sealed `codex/` branch and one PR into `claude/casepath-agents-20261019` per item, with screenshots.

W1. Productionize the prototype. Fix its known defects, update tests that assert old copy
(do not weaken invariants), seal, and attach before/after captures.

W2. Make each case a story that a first-time viewer understands in 10 seconds:
  - a 1.5 s opening line "Case 2 of 9 · Lease termination · Customer asks …";
  - the work: open → read the exact words → fact lands on its step → confirmed → step done;
  - the answer held for 6–8 s: the plain result, what is still open, and what the handler must do
    next (missing documents with a Draft request link, only from recorded data);
  - a quiet hand-off line to the next case.
  - Hide "How to read this replay" during autoplay behind a small "How to read this".
  - Keep fact chips to one line, with the full quote on hover or focus.

W3. Practical usefulness on a completed case (Cases → open): a single "Handler next step" block
above the steps: missing documents → Draft request (the existing editable letter, "Draft, not sent",
Copy/Export), open questions, and the cited passages one click away. Nothing new is invented;
everything comes from the saved state.

W4. Phones at 390 px: the same story, the passage directly above its step, the Now line sticky,
44 px targets, no horizontal overflow.

W5. Closing gate, real functionality. This gate decides "done":
  - `./bin/casepath test` passes in full at the final sealed commit (report counts and failures);
  - in the seeded preview, click through all nine cases: Cases → open → Steps, Documents,
    Knowledge, Sources; open an exact cited span; edit and save a draft request; replay; reload and
    Back/Forward keep the place. No console errors, and no write requests while browsing;
  - the empty main workspace (4173) still shows honest unrun states;
  - record the results in `docs/product/UI_FINISH_RECEIPT_20261020.md` with screenshots.

After W5, the Mac integration owner follows `docs/product/MAC_COMPLETION_HANDOFF_20261019.md`:
integrate, release from the keychain, and run the approved real nine-original allowance.

## Reporting

Comment on PR #21 when each item's PR is up. Lead with "CODEX W<n> READY", then the PR link,
commits, tests, screenshots and limits. The planner reviews, then answers "APPROVED W<n>" or
gives precise change requests. Do not start the next item until the previous one is approved
or the planner says to proceed in parallel.
