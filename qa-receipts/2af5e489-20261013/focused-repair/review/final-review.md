No remaining blockers in the focused independent source and QA helper/selector review.

Final asset: casepath/assets/autonomous-workspace-v1.js
Final SHA-256: 8818482c2a05aee88ea36a5dc387d1629653cd0dad7e06686d16d37638e95ca3
Exact base: bc0ddb5340e4251360ee0f4dcb960ddb190a4114

The patch separates hidden replay suspension from persistent inspection intent. It retains the exact replay session, immutable head and prefix promises; clears the active replay timer and visual motion; defers hidden paint and errors; and restarts a full reading interval on visibility restoration. Shared startReplay preserves reference-head qualification on initial entry, Play, Resume and restoration. Existing consumption checks continue to enforce sequence +1, unchanged earlier events and chain linkage. A live presentation ends on hide, preventing visibility restoration from admitting another Start or case dispatch; ordinary saved-state GET refresh remains intact. Synthetic keyboard events cannot create a persistent pause, while trusted inspection continues to hold replay.

Independent findings addressed during review:
- Late next-case responses after show honor the renewed 4s head interval.
- Initial already-hidden Demo entry retains exact prefix zero until visible qualification.
- Trusted Tab during held initial prefix zero remains paused after its head binds.
- A pending raw route blocks deferred visible replay paint.
- Starting a new Demo while hidden with a previous different replay claim now resumes initial admission before startReplay can consider the old claim. The defect was reproduced on fc0500, and the final targeted probe passed on 881848: prior claim stays unchanged while hidden; show admits exact chosen reference prefix zero; after its reading interval playback advances automatically to exact prefix one without Resume or a false qualification error.

Independent test byte binding: three browser probes passed on f386880 (late handoff, initial hidden entry, trusted initial Tab), the targeted abandoned-route probe passed on fc0500, and the targeted different-prior-claim hidden entry probe passed on final 881848. The final probe asserted the actual injected script digest. Earlier passing scenarios were not repeated after these narrow visible guards. git diff --check passed. The first setup attempt failed before assertions because this clone lacks an ignored generated artifact; it was retried with existing verified fixture files. That setup attempt and the reproduced fc0500 admission defect are preserved as separate failed attempts, rather than included in passing counts.

QA test truth scope: the fresh public visitor test avoids title()/History initialization and trusted user input, validating 218 native DOM prefix identities and eight handoffs with four hide/show intervals and visible graph/document/source/citation/Knowledge/outcome consistency. Complete DTO equality belongs to the owner-mode History-instrumented test; that journey must not be described as zero-input. Both use deterministic in-memory browser fixtures, not authenticated owner or live public endpoint access. The two normal/reduced-motion regression variants hide at exact accepted prefix eight with nine held, then assert stable eight after show and exact next nine in accepted paint order.

Test-only helper/selector review: the startNode helper now deliberately uses the existing trusted Play/Resume control after exact title admission for autoplay test setup; direct paused deep-link assertions remain unchanged. All eight helper variants were covered by QA. The original source/document active-rail selectors also failed on exact base. The corrected source variant selects actual accepted lt_family citations at prefix 11, checks exact marked quote and Escape origin, holds the same prefix and advances to exact 12 only after Resume. The document variant asserts the future contextual requirement is absent from the active rail, selects its exact obligation through the actual All recorded requirements checklist, and checks obligation/document/node route identity. These repairs strengthen evidence without changing product behavior or fixture data. QA owns execution of the repository test groups and final-source byte revalidation.

No source edits, broad suite, provider access, production access, deployment, application service startup or network work were performed by this reviewer. Tests used the existing in-memory browser fixture; teardown enforced read-only GET behavior, blocked network API requests and absence of controller browser errors. Live auto-restart was audited statically, not exercised by these replay probes.

See review-receipt.json for exact commands, statuses, byte binding, QA review hashes and artifact paths.
