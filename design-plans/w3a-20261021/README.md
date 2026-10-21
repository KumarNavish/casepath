# W3-A — Evidence desk

The desktop desk keeps the customer’s files, the passage being read and the actual process together. A completed case opens at its answer. Selecting a step, requirement or failed legal test opens its cited passage; the matching file and step stay marked. The result preserves the original lead and unresolved limits.

Navish’s latest direction supersedes the green canvas in the design study: white surfaces, black and grey typography, and restrained green/amber status cues. Step labels explain what the reader is checking. Technical identities remain in History and Show the reasoning. The customer’s request stays verbatim, including German requests.

During playback, a source underline draws to the corresponding node without crossing text. The node becomes active, then its completion check and outgoing connector appear. Only one cue runs at a time. Pause, resume, skip and reduced motion retain their existing behavior. These are animations of verified deterministic history; no model is invoked.

## Review

- [Mid-work passage and connection](mid-work-thread.png)
- [Case 1 answer](case1-answer.png)
- [Case 4 answer and failed legal test](case4-answer.png)
- [Completed rent case with a document selected](rent-step-selected.png)
- [Case 1 film](case1.mp4)

All frames are 1440 × 900. The local working preview is `http://127.0.0.1:4181/`; the sealed bundle is served on the owned `127.0.0.1:4180` listener. Neither is a hosted release.

## Evidence

`verification.json` summarizes the decisive receipts, source seal and asset hashes. `verification-receipt.json` covers all nine counters and legal labels, verbatim requests, source inspection, local draft persistence, storage failure, copy/download, case isolation, reload, Back/Forward and reduced motion. `motion-receipt.json` binds every cue to an actual operation and checks serial motion, text crossings, overlaps and pause/resume/skip.

The new pure tests check prefix and final counters against the captured traces, preserve the existing source/cause destinations, and require a cited passage for every completed step. The fixture lives under `casepath-qa/fixtures/` so isolated source capsules include it. Existing cases without a supported operation trace retain their established source/process inspection view.

Early checks found draft-event routing errors, overlapping idle pulses, lines crossing node symbols, unbound step inspections and missing German request variants. These were repaired before the final captures. The backend journal, stored outcome, original draft and source content remain unchanged. Local draft edits are keyed by API identity, case and original draft; they save only on the device.

No paid inference, hosted writes, deployment or original-nine rerun occurred. The Mac-owned public read-only test is untouched. Full-product acceptance remains W8. W3-A merge awaits Navish’s visual go.

## Reproduce

With the owned deterministic preview running, use `node design-plans/w3a-20261021/verify.mjs` and `node design-plans/w3a-20261021/motion.mjs`. They use GET-only captured operation responses, and inspect the actual product controller and sealed static assets. Set `OVERRIDES=1` only for working-source development. The final receipts have overrides disabled.

Review handoff follows planner comments 6313172839 and 6313206178. Use only `design-plans/tools/wait_for_planner.sh` for review waits; continue to W4 after W3-A READY while the planner reviews, with any change request taking priority.
