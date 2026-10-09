# Causal workspace

CasePath's primary object is the work in progress. A claim keeps its identity as
the user follows an original source into an established fact, a process branch,
a document obligation, a recorded action, and qualified reusable knowledge.

## Interaction rules

1. Existing work comes first. The workspace opens on the claim collection;
   starting a claim is an explicit, reversible transition into intake.
2. Keep orientation. The workspace rail, claim identity and process path remain
   visible while the user inspects a step, documents, sources or activity.
3. Show cause beside consequence. Selecting a process step brings its required
   facts, source citations, document obligations and recorded actions together.
   The complete document list remains available without leaving the claim.
4. Summarize before expanding. Show a concise state and its immediate constraint.
   Preserve the complete outcome, authority limits, history and provenance in
   labeled disclosures. Hashes are inspection details, not primary content.
5. Represent knowledge as lineage. A qualified version connects its source claim
   to the claims that reused it. Qualification, applicability, supersession and
   quarantined candidates remain distinguishable and inspectable.
6. Preserve actual capabilities. The autonomous controller currently serializes
   claims. Show recorded phases and queue states without inventing a workforce,
   concurrent agents, approvals, manual graph edits or external dispatch.
   Reviewed-claim mutations retain their own authority and API domain.

## Motion rules

Motion answers a question: what changed, what caused it, or where did the
selected object go? It never supplies evidence that the backend has not recorded.

- Animate saved changes only after the matching event sequence, revision and
  state hash have been accepted. Initial loads and reconnections settle directly.
- Trace changed dependencies before emphasizing their affected steps and derived
  documents. Unchanged objects remain still.
- Context selection may use a short, cancellable transition that preserves the
  process position. Closing a source returns focus to its citation.
- Use transform and opacity for moving surfaces. Read layout in a batch before
  writing. No perpetual loops, simulated progress or decorative pulses.
- Reduced motion, hidden documents, open source dialogs and keyboard interaction
  suppress unnecessary movement. Controls remain operable during transitions.
- Polling preserves native file inputs, unfinished forms, selected context,
  disclosures, focus and scroll position.

## Design language

Use a quiet ivory workspace, near-black text and the existing wine accent.
Reserve green for established/completed work and ochre for uncertainty or a
constraint. State is also expressed in words and shape; color is never the only
signal. Typography and alignment establish hierarchy. Thin causal lines connect
objects; borders separate regions only when needed. Avoid panels inside panels.

The desktop composition places the actual process path beside its selected
context. Narrow screens preserve the same hierarchy through deliberate stacking
and a direct return to the process. Large collections use search and meaningful
status filters, rather than an expanding wall of cards.

## Grounding and audit

The October 9, 2026 live audit covered the collection, a saved 11-step claim,
branch selection, derived documents, verified source text and qualified
knowledge. It found intake displacing existing work, process selection leaving
consequences below the fold, repeated descriptions competing with evidence, and
knowledge hashes obscuring the relationship between versions and claims.

The public [Legora Agent](https://legora.com/product/agent),
[Lists](https://legora.com/product/lists), and
[Intake](https://legora.com/product/intake) presentations inform three principles:
work product should persist as an object, source references should stay attached
to derived obligations, and incoming requests should become trackable work.
These are design inferences from public material, not an audit of Legora's
authenticated product. [Awwwards' interaction collection](https://www.awwwards.com/websites/animation/)
is a craft reference; promotional animation is not evidence of real agent work.

## Acceptance evidence

Inspect the actual running app at desktop and phone widths. Follow a branch to
its citations, a verified original source and its document obligations; open a
knowledge version and return through its source and receiving claims. Check
search/filtering, empty and failure states, browser history, keyboard focus,
reduced motion, repeated polling and source arrivals. Verify action boundaries,
idempotency and stale-state handling with isolated deterministic tests. Product
QA must not consume provider calls or mutate the hosted claim journal.

A polished still image, a scripted replay and a passing unit suite are each
insufficient on their own. Record the observed interface, exercised behavior,
test evidence and any remaining limitation separately.

## October 9 integration checks

The Cloud implementation and independent audit used `gpt-6.1-sol` at `xhigh`
reasoning. Mac integration checked the rendered collection, branch inspector,
source overlay and knowledge lineage using nine recorded fictional claims.
The recording server accepted GET requests only.

A separate disposable FastAPI instance exercised the actual autonomous router,
controller and SQLite journal with the repository's deterministic semantic
fixture. Browser actions created a claim, added a later source, paused and
resumed work, and read back the resulting established spouse-notice requirement.
The upload's native FileList survived context switches and polling. Closing a
verified citation restored focus to that citation. Collection search and status
survived cancelled intake, and the unsubmitted draft remained editable.

At 390 CSS pixels the document had no horizontal overflow. Selecting a branch
focused and scrolled to its inspector; Back to process returned to the selected
node. With the browser's reduced-motion media query verified active throughout
a complete new investigation, no Web Animations ran. Initial state restoration
also produced no animations. Event-driven motion was observed during ordinary
investigation. These checks used no model-provider calls and did not write to
the hosted journal. They do not establish real-model interpretation quality or
an uptime guarantee.
