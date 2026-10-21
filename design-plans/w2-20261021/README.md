# W2 case story — 21 October 2026

Based on W1 revision `6c80f3ef0a1404fb0699b886b812c3a08a63db29`. W1 remains under review; [the planner explicitly permitted W2 in parallel](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6303119662). W3 waits for W2 approval.

A verified case opens with its position, domain and original customer subject for 1.5 seconds. The existing recorded operations then show the exact source words, fact, confirmation and completed step. The verified answer holds for eight active seconds, followed by a quiet next-case line. During that answer hold, the completed map recedes so the result and document status fit on a phone; pausing restores the steps. Presentation pauses do not advance the saved journal.

The default roster now prefers reference assessments consistently across cold entry, Cases markers, navigation and the picker. Explicit selection of the separate historical model roster remains available. A known row without reference history is excluded rather than relabelled; an entirely unrun catalog remains unrun.

A recorded missing-document result with a readable, unsent draft offers **Draft request**. It opens the exact recorded letter inside Why, focuses its disclosure, and performs no write. Editing, saving, Copy/Export and the completed-case handler block belong to W3. Generic controller next-action text and raw recorded summaries remain in Why. The replay guide continues to appear only when paused, following Addendum 1's instruction, which supersedes the original brief's autoplay link.

## Evidence

Desktop: [opening](checks/1440-opening.png), [work with exact quote](checks/1440-work.png), [answer](checks/1440-answer.png), [handoff](checks/1440-handoff.png).

Phone: [opening](checks/390-opening.png), [work](checks/390-work.png), [answer](checks/390-answer.png), [handoff](checks/390-handoff.png).

The [story receipt](checks/checks.json) measures 1.505 s / 1.504 s openings, 8.007 s / 8.100 s answer phases, and 0.607 s / 0.604 s handoffs at 1440 / 390 px. The phone answer timing includes a brief pause/resume probe; the active timer remains eight seconds. Both widths checked the second case's opening, all nine reference Cases markers, the picker order, return through Demonstration, zero horizontal overflow, no replay fallback, no page errors and no write requests.

Final focused tests: 427 unit/product tests and 35 evidence-identity browser tests, all passed without skips. The latter includes opening the exact unsent draft, preserving its recorded bytes and returning focus without writes. See the copied logs and [verification.json](verification.json) for commands, source seal and asset hashes. Full-suite acceptance belongs to W5.

At the matched Checker/heating-report moment, the supplied baseline's 48 OCR text regions reduce to 28 (41.7%). See [matched frame](checks/matched-heating.png) and [count receipt](checks/text-matched.json), using the same offline OCR settings as the original baseline. In ten seconds, the desktop work frame identifies the customer's heating complaint, Reader finding a possible fact, the exact `CHF1800` words, and the fact's unconfirmed state. The answer frame states what the checks support and which repair/amount/award questions remain undetermined. This is executor frame inspection, not first-time human acceptance.

## Limits and repairs

The first phone capture placed the answer below the completed map; the [diagnostic frame](diagnostics/answer-below-fold-before-fix.png) is preserved. The autoplay answer focus fixes that and is asserted in the final browser check. A first launch of the new check had an incorrect local module path; that test-tool import was corrected before browser execution.

During work, phone following can still move the title out of view; sticky Now, title retention and the remaining phone interaction checks belong to W4. All-nine functional coverage and Mac review findings belong to W5. No backend, public-startup-test, production journal, paid inference, hosted write or deployment change was made. The original nine-case allowance must not be run again.
