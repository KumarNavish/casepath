# Connected claims workspace

This redesign changes information architecture, navigation and presentation. It preserves the existing claim authority and source contracts.

The workspace sidebar exposes urgent claims, evidence waiting, readiness, action issues and unassigned work. Counts come from complete verified queue responses. Search, filters and sorting stay server-backed.

The claim workbench shows current state, controlling requirement, one next action and its reason. Overview, Evidence, Process and Activity are views of the same claim, not separate workflows. Sources remain beside the work on desktop and use a dedicated full-height view on compact screens.

Accepted evidence shows the source passage, changed interpretation, resolved requirement, removed request, newly active requirement and resulting readiness. Corrections are available beside the exact permitted finding and through Claim actions. The preview replaces the normal action rather than competing with it.

Filters stay in the URL. Active view, reading position, keyboard focus and back-navigation are preserved. A contextual shortcut returns to the original next action when it is offscreen. Source text is escaped; original downloads retain size and hash verification.

Recovery uses the existing idempotency keys, revisions and verified pre-advance state. The UI distinguishes recovered committed evidence from unaccepted evidence. A zero difference between two post-commit reads is not a rejection.

Exact identifiers, hashes, compiler output and gate receipts remain in Technical details. No fabricated agent activity, fake claims, paid inference or customer dispatch is introduced. The public standalone repository contains 60 synthetic development claims, not the historical 150-case research corpus.

Run the presentation tests in `casepath-qa/*presentation-v1.test.cjs`, then follow `CONTRIBUTING.md` to seal the source and run `./bin/casepath test`. Browser evidence belongs outside the source tree. The browser programs exercise the real isolated API and journal at large desktop, laptop, tablet and 390-pixel mobile sizes.
