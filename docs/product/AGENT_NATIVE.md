# Agent-native desk

The desk presents a handler's saved claims and delegated review work. CasePath
reads the bound sources, extracts cited passages, derives the working process
and document requirements, and prepares local request wording. The handler
owns process validation, corrections, draft approval, and any action leaving
CasePath. Claim outcomes remain outside this delegate's authority.

## Saved state and evidence

The 150-row desk groups claims into Needs you, Agent working, Waiting on
someone else, Quiet, and Closed. Rows show the accountable handler separately
from the CasePath delegate, the bounded ask, why it matters, source coverage,
the latest actual activity, and the local draft state. The stop reason,
recorded work, full coverage note and unsent draft status are visible with
the row's peek closed. The peek retains dated activity and exact source
passages. A finished review is distinct from findings awaiting the handler;
the desk does not invent a role count when its projection omits one. Each row's signed
`review_started` flag records validated persisted run presence, independently
of source coverage or completion. Quiet includes unstarted claims; their
review remains unknown. Nonpaused interrupted or unconfirmed runs belong in
Needs you, with signed `recovery_required` and `recovery_ask` fields. A verified
local checkpoint may offer resume after review. Pending operation/provider
outcomes require inspection and reconciliation before any retry. Missing
documents do not establish that a request was sent or that
someone else is responding. The current local implementation has no external
waiting or claim-closure receipt, so those groups remain empty.

Review activity comes from persisted work events and an actual journaled
automatic draft receipt. Source coverage reports the original bound intake,
including sources not read and limited text extraction. Citations retain the
original artifact ID, source and extracted-text hashes, quoted text, and exact
text offsets. Extracted text does not establish that every image or page was
read. Deadlines remain unknown when required receipt evidence is absent.

An automatic draft can advance the workspace after a review finishes without
changing its reviewed sources or process. Only the desk may report that review
as current within `reviewed_sources_and_process`, while retaining
`authority_snapshot_currentness: historical`. This requires the unchanged
source-loop hash, graph and effective assessment, a validated historical
parent, and a suffix containing only unedited automatic draft receipts. Manual
drafts, process edits, owner changes, and altered history do not qualify. The
original work API and tool authority checks retain their exact prefix meaning.

Desk arrival explicitly starts at most six deterministic reference reviews by
default, beginning with the family-home case. The batch idempotency key binds
the original roster and review contexts across tabs and restarts. Repeating an
arrival reuses its runs. It never assigns a handler or overrides a saved pause.
Completed reference work can prepare a current local draft through the
existing workspace journal; it cannot approve or send that draft.

## Handler decisions

Every actionable question offers bounded answers, a proposed answer and its
reason, a counter-reading, affected documents, and cited passages when the
sources establish them. Conditions use ordinary handler language. Choosing a
different answer requires a reason. Preview shows the proposed graph and
explicitly changed and unchanged requirements before acceptance.

Condition, step, relationship, and inconsistent-completion decisions use the
existing causal preview/apply pipeline. The bounded Dispute answer retains
`answer_id: disputed` in agent receipts and maps to the engine's existing
`rejected` validation status for both steps and relationships. The agent-native module does not add
another process engine. Source-conflict reviews and draft approvals use a
delegate journal namespace in the same `claim_loop_events` authority. These
events record a handler's review, not a new source fact or claim outcome.

A reviewed conflict leaves the actionable queue while remaining visible with
its original citations, counter-reading, review reason, and unresolved truth
status. Its decision binds the exact conflict material. Draft approval binds
the exact current draft event, including its wording. Editing that wording
reopens approval. Approval is always displayed as approved, not sent. Accepted
process decisions refresh the documents and local draft and request real
deterministic continuation; saved run state and currentness determine what the
UI can report.

The existing process editor and document-review apply routes invoke the same
delegate continuation after acceptance. Their original causal receipt still
describes the accepted process prefix; draft preparation and work are separate
events, so clients refresh the current workspace afterward. Previews have no
continuation effects. Exact retries reuse the event-bound continuation key;
superseded process edits and saved pauses cannot restart work or prepare a new
draft through this hook. Continuation starts only reference review.

When another accepted edit arrives during reference work, the obsolete run
stops at its next safe checkpoint. Its terminal receipt and pending-operation
checks precede a new run for the latest accepted edit. Intermediate edits do
not each create a run. A saved pause prevents the handoff; external inference
and unfinished effects require inspection instead of automatic replacement.
The existing active-run and lease constraints still control execution. There
is no startup scheduler: if the app exits after cancellation and before the
handoff, an exact retry of the latest accepted edit or an explicit handler
Resume/Retry recovers it from the journal.

Saving reusable knowledge is explicit. A lesson preview requires validated
selected steps and internal relationships, shows its process family,
documents, and boundary relationships, and strips held source files. Applying
the preview saves a versioned process fragment through the existing causal
journal. Reusing a fragment uses that engine's preview/apply route. Matching
reviewed memories are suggestions; the Used knowledge list derives only from
accepted memory or fragment-use receipts. No automatic learning occurs.

## Pause, replay, and projection integrity

Workspace reads share a bounded cache of verified immutable journal prefixes.
Every lookup fingerprints every persisted row column and checks the admitted
corpus identity before and after reuse. Cold replay validates the original
reducer and retains its already-verified intermediate states for historical
reads; changed, deleted, or malformed rows force validation again. Cached
states decode into independent objects and preserve existing response field
order, including byte-identical mutation retries. The app reuses a workspace
service only for the same actual storage and corpus objects. Original full
authority snapshots and tool gates remain in place.

[Copied-runtime performance evidence](AGENT_NATIVE_PERFORMANCE.json) records
the same synthetic family-home state at workspace revision 34 with 15 process
edits before and after this change. Cold process projection fell from 3.359 to
0.712 seconds, hot projection from 3.570 to 0.211 seconds, and a full real
six-role reference review from 90.664 to 9.839 seconds. Both reviews completed
six roles, with no provider requests or pending calls. Corpus admission,
service construction, and copy preparation precede these operation timings;
the measurements do not establish browser paint or deployment performance.

Pause journals the mandate immediately and requests a safe interruption of
queued or running work. A running operation finishes its checkpoint before
`RUN_INTERRUPTED` makes the pause effective. Resume clears the persisted pause
and reuses the recoverable run and completed calls. Pending effects and
recorded provider attempts retain the existing reconciliation restrictions.
An expired running lease uses the existing service's interrupted-run recovery
path, including its pending-call checks. Active pause writes an unknown
`RUN_INTERRUPTED` checkpoint and clears the owner and lease. A pause received
after the final tool check still persists that checkpoint before resume.
Cancel remains a different terminal action.

Controls carry both the workspace and delegate revisions and state hashes.
Decision and lesson acceptance carry the workspace revision, state hash, and
preview hash. Every mutation requires an idempotency key. Exact retries return
the original accepted event; changed input under the same key and new commands
against stale state are rejected. Replaying an old pause after a later resume
does not pause the delegate again. Historical accepted decisions remain
replayable after draft preparation or later process changes.
Historical draft and conflict retries return their original accepted event
without preparing replacement wording. Continuation requires that the accepted
delegate event remains the latest mandate/decision event and that its exact
workspace parent is still current. Both checks are repeated before submitting
or resuming work. A saved pause blocks continuation.

The desk's read-only cache fingerprints relevant persisted claim/work rows and
the corpus identity before reusing a verified projection. Work-row scalar
types, column names, lengths, and raw values are bound without serializing
nested stored JSON again. Concurrent polls share one verified cache fill.
Individual rows also bind their workspace, delegate, source-loop, and work
prefixes, plus corpus and global knowledge dependencies. A change to one claim
rebuilds that row while unchanged verified rows are copied. Changed bytes take
the journal replay path; a tampered prefix is rejected. Returned cached values
are copied so a caller cannot alter the next response. Startup prewarms the
desk. A benchmark of an isolated SQLite copy with 150 claims and 24 reviewed
claims, using the production corpus watcher, measured a 0.084-second warmed
projection and 0.135–0.181-second polls during a real reference review. Initial
replay and startup validation remain more expensive. These are local
measurements, not a general latency guarantee.

## API integration and verification

See [the API contracts](../contracts-api.md#agent-native-desk-api) for routes,
envelopes, and hash fields. All decision previews use the agent preview
contract; process previews embed the original causal receipt as `causal`.
Decision results embed the original causal result as `causal_result` when
applicable. Whole-envelope hashes cover the additive agent fields.

The focused backend suite covers read-only projections, stale revisions,
exact idempotency, restart replay, safe pause/resume, historical decision
retries, conflict citations and unknown deadlines, edited-draft reapproval,
explicit fragment approval, fixed arrival batches, and cache tamper rejection.
The active pause test interrupts an actual committed source
read, reopens its database, and resumes the same run without changing completed
call receipts. All test stores use isolated
temporary paths and the public synthetic corpus. No sending, provider calls,
or external mutations are part of this agent-native workflow.

Direct-editor integration tests cover process and document apply,
current draft preparation, a real six-role current review after adding a
document requirement, exact route retries, unchanged causal receipts,
superseded edits, and saved pauses.
Projection tests cover automatic-draft equivalence, excluded manual
draft/process/owner changes, tampered history, and isolated row invalidation.
Concurrent run creation is read from one work-database snapshot, including its
latest-run roster. Exact desk-arrival retries use one verified batch rather
than rebuilding six full authority views. Real rapid-edit tests cover
checkpoint cancellation, latest-only six-role completion, and a concurrent
saved pause; queued-cancellation restart recovery and unresolved-operation
tests cover the bounded handoff limits.

Global startup and replay validation recognizes the exact `delegate.{claim_id}`
namespace only in the local workspace session. It verifies the recorded
parent import and lifecycle prefix, then uses the same delegate reducer to
check chain integrity, schema and decision scope. Foreign prefixes, missing
parents and rehashed authority or approval-scope tampering are rejected.
The read-only validator and claim replay preserve database and journal bytes.
The independent standard-library boot-history verifier also registers these
three delegate event types and requires their local workspace session and
nonempty `delegate.{claim_id}` namespace. Semantic validation of the imported
parent, authority scope and delegate reducer runs before that structural boot
check. Unknown event types, altered command hashes and rehashed foreign
namespaces remain invalid.

### Loading the claim presentation

The native desk starts from a small stable route scaffold. Claim navigation
loads the existing presentation module from its content-bound metadata URL.
Concurrent openings share one pending load; failed, incomplete and timed-out
loads release it for retry. Existing claim request epochs prevent a late load
from reopening a claim after navigation. The eager script budget remains
300,000 bytes (299,594 bytes in this candidate). Self-hosted fonts and both
licence notices belong to the exact public asset inventory and closure checks.

The desk labels the responsible handler explicitly. Unassigned claims keep
their persisted waiting state and say that a handler is needed. The decision
shows the recorded proposed answer and its unsaved status beside the agent
reading, before the longer alternatives. Historical draft activity is labelled
as earlier work when the current revision has no prepared draft.

Native decision answers and Preview consequences carry stable, question-scoped
IDs. The existing focus restoration path therefore retains keyboard focus
when delayed process, draft or memory reads replace the claim panel.

After restoring keyboard focus, the refreshed control scrolls only as far as
needed to remain visible. This also covers late status lines changing the
claim layout; it does not move focus to a different control.
The scroll margin leaves room for the complete focus ring at viewport edges.

Reviewing-handler and reusable-fragment fields also retain stable control IDs.
Refreshes preserve text-input selections as well as textarea selections, and
the unassigned reuse form restores its typed reviewing handler.
An intentionally cleared reuse reason stays blank after refresh.

Action buttons derive deterministic IDs from their label and action attributes;
the duplicate invalid-recovery Reload has a distinct scope. Preview regions,
notices and disclosures also retain explicit identities across outer refreshes.
Changed or disabled commands do not inherit focus from a different action.

Exact-source focus uses the captured artifact, original-byte and text hashes, quote and available
page/character locator; it never falls back to a reused source-array index.
Preview and saved-impact disclosures retain separate entity-scoped open states.
