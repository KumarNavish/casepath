# Agent-native desk

The desk presents a handler's saved claims and delegated review work. CasePath
reads the bound sources, extracts cited passages, maps the working process from
saved handling rules, derives document requirements from its nodes, and prepares
local request wording. Cited source findings and process rules retain separate
provenance. The handler
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

An agent citation into an encoded customer email opens the readable message
with the exact passage highlighted. This requires the verified original file,
matching claim and artifact identities, the complete decoded-body hash, and
the exact code-point offsets and quote. A mismatch cannot produce a verified
highlight. Original MIME formatting and the unchanged download remain
available. This is a source preview, not evidence admission.

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
existing workspace journal; it cannot approve or send that draft. The separately
requested live Facts review uses the same safe draft preparer on successful
completion. Desk arrival never starts that paid review.

Open claims reread verified work every 1.4 seconds during a run and every five seconds after it stops. The quiet read catches a draft receipt saved after the terminal work event and refreshes the claim when its revision changes. Navigation cancels that follow-up. Native disclosure intent is retained before a queued toggle can be overtaken by a refresh; obsolete elements cannot overwrite it. These are read and presentation operations, with no provider start or claim mutation.

## Handler decisions

Pending questions use the same priority on the desk and claim: source conflicts, inconsistent completions, condition readings awaiting confirmation, draft approval, unresolved conditions, then process validations. Reviewed questions are removed before ordering. The order changes no question, preview hash or accepted event. A process-derived question names that basis when no direct source quotation is attached.

Every actionable question offers bounded answers, a proposed answer and its
reason, a counter-reading, affected documents, and cited passages when the
sources establish them. Conditions use ordinary handler language. Choosing a
different answer requires a reason. Preview shows the proposed graph and
explicitly changed and unchanged requirements before acceptance.

Condition questions name the current process reading, or the intake reading
before process adoption. A matching selected answer says Awaiting your
confirmation. A different answer shows the current and selected values side by
side, marked not saved. This reads the existing verified claim state without
changing the question, preview hash or saved answer. Missing values and other
question kinds omit the comparison. A persisted reading does not itself
establish a handler decision.

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

For reference reviews, Pause journals the mandate immediately and requests a safe interruption of
queued or running work. A running operation finishes its checkpoint before
`RUN_INTERRUPTED` makes the pause effective. Resume clears the persisted pause
and reuses the recoverable run and completed calls. Pending effects and
recorded provider attempts retain the existing reconciliation restrictions.
An expired running lease uses the existing service's interrupted-run recovery
path, including its pending-call checks. Active pause writes an unknown
`RUN_INTERRUPTED` checkpoint and clears the owner and lease. A pause received
after the final tool check still persists that checkpoint before resume.
Cancel remains a different terminal action.

For external Facts work, the same handler control records a stop request. A
provider request already sent may finish and retain its usage receipt; no next
request is sent after the stop checkpoint. Queued or interrupted external work
can stop without clearing unresolved calls. Once the review is terminal, its
charges are known, no calls remain pending and no local job is active, the
handler may clear the saved pause. Clearing it neither resumes the external run
nor makes a provider call. Unknown outcomes require inspection and retain their
budget reservation.

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
temporary paths and the public synthetic corpus. These reference tests make no
provider calls or external mutations. The separately opted-in model adapter is
tested with mocked transports; actual provider acceptance requires its own saved
run and cost receipts.

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
four delegate event types and requires their local workspace session and
nonempty `delegate.{claim_id}` namespace. Semantic validation of the imported
parent, authority scope and delegate reducer runs before that structural boot
check. Unknown event types, altered command hashes and rehashed foreign
namespaces remain invalid.

### Loading the claim presentation

The native desk starts from a small stable route scaffold. Claim navigation
loads the existing presentation, agent-claim and work-motion modules from their content-bound metadata URLs.
Concurrent openings share one pending load; failed, incomplete and timed-out
loads release it for retry. Existing claim request epochs prevent a late load
from reopening a claim after navigation. The eager script budget remains
300,000 bytes. The exact eager byte count must be established by the release evidence receipt. Self-hosted fonts and both
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


## Connected handoff and node-derived review (8 October 2026)

Overview connects the selected bounded decision to a real node in the verified working process. Node and completion questions use the exact node identifier; relationship questions use their target node; condition questions use the server evaluation's condition dependencies. The current focus is only surrounding process context when a question has no direct node identifier. The browser never recomputes readiness or consequences.

The shared graph renderer shows the selected step once with actual incoming and outgoing neighbors. Its attached document list preserves both route timing and insufficient review state. Proposed processes say their requirements are proposed. Handler-edited or validated state takes precedence over historical policy provenance in the display. Available reviewed process versions and recorded uses in this claim have different counts.

Direct review links from the node and checklist open the existing exact-document form through `openPane(name, detail)`. This navigation waits for shared process/editor reads, checks claim/revision/hash and navigation currentness, and focuses the current form after render. Distinct read tokens prevent an older read from clearing newer loading, even when both share a captured context. Requirement rows carry stable domain identities for focus restoration.

Supervision and counter-reading use native disclosures whose state survives refresh. The bounded decision precedes the full decision selector. Only intentional decision changes animate the context; reduced motion disables that transition.

The agent-claim module now loads alongside claim presentation on entry, through strict local hash-bound metadata. Rendering requires both modules. Load failure, incomplete arrival, timeout, concurrent entry and abandonment are covered by focused regressions. This presentation change preserves journal meaning and outbound authority. The separately opted-in live Facts profile is described below.


### Reviewed knowledge approval

The expanded knowledge surface compares the existing reviewed library with the proposed fragment. The preview exposes its name, rationale, reviewing handler, claim family, validated steps, excluded boundary connections and document definitions. Saving through this surface creates a new fragment at version 1; it does not update a same-named saved version. Cancel reuse returns to the form without approving or saving the fragment. Reuse in another claim requires its own compatibility preview and approval. The creation response's empty conflict list does not establish semantic conflict detection: the interface explicitly says conflicts with other claims have not been checked.

The saved joined proof follows one handler correction through this entire path.
On `clm_f69b1747447bc221`, the handler added `lease_contract` to the validated
`lt_deadline` step and separately approved **Early lease evidence for deadline
review**, version 1, from revision 130. Its fragment hash is
`9a619ae6b4f890b534c5e2fe938a6e54227b9948081883dd0f93b72db0fe57f6`.
Restoring the source's original requirements at revision 135 retained the saved
fragment. Applying it to `clm_0e538990cc6ba7ef` produced revision 4, where the
lease is needed now at that step and appears in the newly prepared, unsent
request draft. Source conflicts and missing receipt dates remain unresolved.
Both approval previews were checked at four sizes; this is one joined save and
reuse sequence, not four independent journeys. The
[joined proof](../../../casepath-agent-native-v2-evidence/v4-joined-knowledge-proof.md)
retains the earlier failed revision-expectation check and exact receipt seals.
Reviewed-memory save/reuse and semantic conflict detection remain outside this
proof; automatic learning is false.

### Explicit live source review and recorded motion

The [separate local demo profile](../setup-demo.md) exposes an explicit model
review for a claim with an accountable handler and current context. The selected
model runs only the Facts role through the existing bounded source tools; the
other five roles use deterministic verification and the same process authority.
The model is explicitly selected from a recent catalogue and checked against its
recent endpoint roster, including required tool-call support and request
parameters within the price ceiling. No fallback model or automatic paid start
is enabled. The normal launcher remains
provider-free.

The demo's durable allowance is three explicit external runs, at most 18
provider requests, USD 0.02 per run and USD 0.10 in aggregate, with one provider
request in flight. Each run reserves its allowance before execution. Actual
charges and unresolved reservations are separate; restarts and exact retries
do not reset the allowance or resend an unknown outcome. Admission also checks
the saved pause, current claim authority and prior unresolved work. Capability
and claim projections expose eligibility and the remaining allowance without
exposing credentials. The run receipt binds the requested context and
idempotency key.

After the base three-run allowance is exhausted, a separate local command can
record one explicitly approved fourth review. Its sealed receipt binds the
operator, reason, exact prior budget and idempotency key. It preserves the
original policy, all runs and unresolved reservations, and the 18-request and
dollar limits. It cannot grant a fifth run or apply automatically on restart.
The command starts no server or provider work; the handler still starts the
review through Controls. See the [allowance procedure](../setup-demo.md).

The live work rail derives Sources, Findings, Process and Documents from
persisted events. It shows concise, cited work summaries and actual model or
reference identity, with motion tied to current work. Historical events are not
replayed as new activity. A source-to-finding connection requires the recorded
span link; a process-to-document connection requires the recorded requirement
link. Process steps are labelled as mapped from saved handling rules. The rail
does not invent a source-fact-to-legal-rule connection. Raw model prose and
hidden reasoning are not persisted or displayed.

The stage buttons show their labels; the selected stage's status and count
appear together below them, and each accessible button name retains that
detail. A completed stage says Review recorded. On a fresh visit, completed
review sits below the decision. A current run observed working opens above the
decision and stays there through completion until the handler closes it or
starts a fresh visit. This per-run display state prevents a completion refresh
from moving the active review. At 540 px and below, the claim panel is the
single vertical scroll region. Optional model review and reruns are inside
Controls, with the cost ceiling beside the start action and the model under
Review details.

Backend, live projection, stop/clear-pause and frontend invariants have focused
test evidence. The final focused frontend gate passed 95 tests; native exact
source, process and document navigation passed at all four sizes without a
provider call. At the source-edit checkpoint, 8 October 2026, 10:27 UTC, actual
provider execution, the browser journey with that live provider, final asset
sealing, full-suite validation, a new release commit and the external exemplar
comparison remain pending. The demo launcher requires a sealed commit and
verified normal boot before a paid acceptance run. Subsequent outcomes belong
in the external evidence directory under the planned
`v4-live-provider-acceptance.json` and `v4-final-release-receipt.json`; those
receipts are not yet established by this checkpoint.
The [acceptance record](AGENT_NATIVE_ACCEPTANCE.md) distinguishes these gates
from the completed reference and learning journeys.

At the later source-edit checkpoint, **8 October 2026, 11:38 UTC**, the full V4
suite had recorded 1,830 passes, ten skips and one packaging failure: the static
asset closure omitted `agent-work-motion-v3.js`. The module is now included in
the public and content-bound inventories, whose strict expected file count is
33; all eleven focused build tests pass. The integrated frontend retest passes
244 tests after two harness updates. A read-only 390×844 reference check at
claim revision 135 records no overflow, a decision action bottom at 823.17 px,
44 px stage controls and unchanged decision position when history opens.
These results do not establish a passing full suite for the changed source,
configured live-control viewport acceptance or actual provider work. Paid
inference remains zero at this checkpoint; release and external comparison
gates remain pending in the acceptance record.

### Explicit recovery of one interrupted local proposal

`POST /api/claim-loops/v1/workspace/claims/{id}/agent/reconcile` is an additive local control-plane action. It requires the existing idempotency header, same-origin agent-work guard, handler and recovery note, expected workspace and delegate revisions/hashes, and the exact run, call, object, work-event and authority-state identities advertised by the verified projection. The handler first reviews the interrupted step.

The service reconstructs only a unique persisted `propose_process_node` call made by the deterministic reference worker from its unchanged authority snapshot. It rejects provider history, multiple pending calls, cancelled work, live leases, changed sources or state, unknown tools and operations with claim effects. A final transactional check prevents another executor from racing the reconstruction. `AGENT_RECOVERY_REQUESTED` records the handler request in the delegate journal; `LOCAL_PROPOSAL_RECONCILED` records the reconstructed local work. Existing lifecycle events and the working process stay unchanged. Exact retries recover the receipt. A superseded handler request reports that outcome explicitly.

Reconciliation leaves the run at an interrupted checkpoint. Resume is a separate existing control action and resumes the same run. No automatic provider retry, local process adoption or claim outcome follows from reconciliation. The invariant and router suites cover refusal cases and the request-to-work interruption gap; browser receipts record the actual interrupted local run and unchanged claim authority before resumption.

Signed browser projections retain the original JSON number representation when checking their digest. Tiny and zero model costs remain exact; the browser does not round them or regenerate their journal hashes. A response with missing numeric provenance or a number it cannot safely represent fails verification.

### Bounded source preparation and direct handoff

The local reader opens the complete original packet through the same source
tools before the external Facts worker selects exact quotations. Those source
reads are real persisted kernel events, count toward the same tool budget, and
stop on changed or failed sources before inference. The model sees a labelled
source packet and selects spans through the existing exact-source gate. Every
selection is checked, including rejected attempts. The host records accepted
quotations verbatim as reported assertions and uses the same completion gate;
both operations remain checked kernel tool calls. Once a valid selection batch
exists, no additional model request is needed for copying or completion.
Rejected selections and extraction limits remain inspectable. No per-run
request, tool or cost limit is increased.

Condition-choice guidance is presentation only; signed questions and persisted
reasons stay unchanged. Exact source passages accompany the proposal, while
the original rationale remains inspectable. The desk has an explicit View
source and review action. An anchored completed review offers Go to decision
without closing its work record or moving focus on refresh.
