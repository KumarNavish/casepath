# W1 planner revision — 21 October 2026

Addresses [W1 CHANGES REQUESTED](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6303119662) on PR #22, based on `20809e3f58a9d25277676600200366852342c80b`.

- Removed both ID-based stage label tables. Labels now come from the recorded name. Shortening removes only a leading Check, Read, Capture, Establish, Assess or Record (and an optional “the”), then capitalises the remaining text. No synonyms or ID-based substitutions. The label regression checks every step/document in all nine reference catalogs and the two rent-case meanings called out by the planner.
- Fact chips use 100% of their step column before ellipsis; full quoted text remains on hover/focus and in the record.
- Now is left-aligned directly below the transport. Details stays inside that line on phones; the inherited absolute-position rule no longer detaches it.
- Next is omitted when absent or when the record contains one of the controller's three generic boilerplates. Those recorded sentences remain inside Why. A concrete recorded action remains visible verbatim. No fallback action is invented.

## Evidence

[Matched heating frame](after/demo-matched-heating.png), [10-second desktop frame](after/demo-10s.png), [390 px frame](after/mobile-demo-12s.png), [completed rent case](after/claim.png), [desktop result](checks/w1-1440-result.png), [phone result](checks/w1-390-result.png), [exact source](exact-source.png).

The supplied baseline has 48 OCR text regions. The revised matched Checker/heating-report frame has 28, a 41.7% reduction. The [OCR receipt](checks/text-matched.json) uses the same offline settings as the [original baseline receipt](../w1-20261020/checks/text-before.json). Longer truthful labels take precedence over the earlier 47.9% result; the revised frame still exceeds the 40% target.

In ten seconds the matched frame identifies the customer's repeated heating failure, Checker checking the heating service report, the exact `15.8C` passage, and confirmation of that document check. The repair/reduction step remains unfinished. This is executor frame review, not first-time human acceptance.

467 focused frontend tests pass: 433 unit/product tests and 34 evidence-identity browser tests, no failures or skips. Geometry checks cover 1440×900 and 390×844, full-column chips, Now alignment, Details containment, one moving cue, no horizontal overflow and no duplicate controls. Keyboard full-quote/source access, Escape focus restoration and reduced motion are checked separately. Final receipts and asset hashes are in [verification.json](verification.json).

## Limits and diagnostic history

One preliminary phone capture displayed a replay fallback while several browser checks overlapped. The original diagnostic frame is preserved in [diagnostics](diagnostics/overlapping-capture-fallback.png); its in-page exception was not recovered before that page closed, so its cause is unconfirmed. The capture tool now fails on an unexpected notice and saves its details. A subsequent capture passed; final capture/geometry/access commands run serially. W5 must still cover all nine cases and the Mac findings.

Phone follow can still move the title out of view; W4 owns that work. The earlier empty-workspace and gate-fix receipts remain in the original W1 evidence directory. No API/backend changes, paid calls, hosted writes, deployment, or passive-startup-test edits occurred in this revision. Full-suite and human/planner acceptance remain outstanding. W2 may proceed in parallel only under the planner's explicit permission in the linked review.
