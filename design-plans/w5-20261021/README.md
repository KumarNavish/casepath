# W5 — The handler's next step

Completed desks now put the next action above the answer: “Nothing missing — answer can go to the customer after your review.” The original answer, unresolved limits and unsent draft remain visible below it.

When the recorded outcome lists missing documents, each document links to its inspection view and to the recorded step that requires it. A recorded recipient is shown when present. Otherwise the UI says whom to ask is not recorded. An absent missing-document field never becomes “Nothing missing.” These paths are covered with isolated fixtures; the nine existing reference outcomes have no missing documents.

The draft workflow retains an immutable original plus a device-local editable copy, Copy text and Download letter. It does not send the letter or change the recorded outcome.

This item also closes planner comment 6314376218: each Cases row has a muted identity line, so identical requests can be distinguished. Featured cases use their existing label; other originals retain the recorded subject and received date where no customer name is recorded. An answered row says “All legal tests met” in green only when every recorded test is supported and at least one test exists.

## Review frames

- [Next step above the Case 1 answer](case1-answer.png)
- [Case 4 caveat and failed test](case4-answer.png)
- [Distinct identities for identical requests](case-identities.png)
- [All legal tests met](legal-tests-met.png)
- [Device-local draft copy](local-draft-copy.png)

## Verification

463 focused tests cover next-step truth, unknown recipients and graph links, original-state immutability, case identity, and legal cues. The browser script checks all nine completed desks, the exact next-action line, source inspection, edit/save/reload, storage failure, clipboard/download contents, original retention, case isolation, Back/Forward and reduced motion. The visual audit checks the open modal's own contents separately from the intentionally obscured page.

`verification.json` binds the sealed source and served asset hashes to the browser receipt and frames. No paid inference, hosted writes, deployment or original-nine rerun. Mac-owned public read-only tests are untouched. Review remains on PR #21 through `wait_for_planner.sh`.
