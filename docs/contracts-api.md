# API and configuration

`./bin/casepath dev` serves the browser and API from
`http://127.0.0.1:4173`. The generated OpenAPI document is available at
`/openapi.json`, and FastAPI's interactive reference is available at `/docs`.
Use the same origin so source previews, runtime identity, and API state remain
bound to one verified checkout.

## Supported local configuration

The launcher owns configuration for normal use:

| Setting | Local behavior |
| --- | --- |
| `CASEPATH_MODEL_MODE` | forced to `deterministic_reference` |
| `CASEPATH_DB_PATH` | `.runtime/casepath-data-v1/casepath.db` |
| `CASEPATH_ARTIFACT_REGISTRY_PATH` | `.runtime/casepath-data-v1/artifact-registry` |
| `CASEPATH_LOCAL_STATIC_ROOT` | generated `casepath-public` in the verified capsule |
| `CASEPATH_SOURCE_COMMIT` | resolved from the current Git checkout |
| Provider/tracing credentials | removed before CasePath modules load |

`CASEPATH_UV` may point to an absolute `uv` executable. The product port is
fixed at 4173. Direct `uvicorn` and `casepath-api/start.sh` are lower-level
developer surfaces and do not provide the launcher's complete source-capsule,
same-origin, lock, and durable-state guarantees.

## Health and reference routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/healthz` | process and model-mode health |
| GET | `/readyz` | source, runtime, and readiness checks |
| GET | `/deployment-health` | release and source identity projection |
| GET | `/api/demo` | reference scenario metadata |
| GET | `/api/claims` | legacy focused-demo claim list |
| GET | `/api/claims/{claim_id}` | legacy focused-demo claim detail |
| GET | `/api/artifacts/{artifact_id}` | legacy artifact bytes |

The browser's current 150-claim workflow uses the claim-loop workspace routes
below. Older `/api/runs`, foundation, shadow, and native research routes remain
for compatibility and tests; they are not the first integration surface for a
new client.

## Claim-loop workspace

All paths below use the `/api/claim-loops/v1` prefix.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/workspace/claims` | filtered, sorted, cursor-bound queue page |
| GET | `/workspace/claims/{claim_id}` | source-linked claim and immutable binding |
| GET | `/workspace/claims/{claim_id}/artifacts/{artifact_id}` | claim-scoped source bytes |
| POST | `/workspace/claims/{claim_id}/owner` | record owner assignment |
| POST | `/workspace/claims/{claim_id}/start` | start or resume deterministic assessment |
| POST | `/workspace/claims/{claim_id}/reconcile` | resolve an admitted unknown effect |
| POST/GET | `/workspace/claims/{claim_id}/loop` | create or read workspace loop |
| POST | `/workspace/claims/{claim_id}/loop/evidence/intents` | persist evidence action intent |
| POST | `/workspace/claims/{claim_id}/loop/evidence` | admit evidence through authority checks |
| POST | `/workspace/claims/{claim_id}/loop/advance` | advance through deterministic gates |
| GET/POST | `/workspace/claims/{claim_id}/loop/corrections/*` | inspect, preview, and admit corrections |
| GET | `/workspace/claims/{claim_id}/export` | hash-bound current status export |
| POST | `/workspace/rebuild` | validate and reproject the journal roster |

Consult `/openapi.json` from the running commit for exact request and response
schemas. Mutation requests require `X-CasePath-Idempotency-Key` and an expected
revision where the schema defines one. Cursor tokens bind query, sort, page
size, `as_of`, and the full journal roster. Concurrent state changes produce an
explicit stale-cursor failure instead of skipped or duplicated rows.

## Agent review API

All paths below use `/api/agent-work/v1`. The browser exposes work requests and
read projections; it does not expose arbitrary model tools.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/capabilities` | six-role and external-worker capability projection |
| GET | `/workforce` | latest review state across claims |
| GET | `/claims/{claim_id}/context` | authority-bound review context |
| GET | `/claims/{claim_id}/runs` | persisted runs for one claim |
| POST | `/claims/{claim_id}/runs` | start a reference or explicitly external-Facts review |
| GET | `/claims/{claim_id}/runs/{run_id}` | inspect one run |
| GET | `/claims/{claim_id}/runs/{run_id}/events` | paged persisted work events |
| POST | `/claims/{claim_id}/runs/{run_id}/resume` | resume the same recoverable run |

Agent-work mutations require the same-origin `X-CasePath-Agent-Work: 1` guard.
The normal launcher remains provider-free. External Facts additionally requires
explicit server configuration and `facts_worker: "external_facts"`; invalid
configuration is rejected rather than silently falling back. See
[AGENT_REVIEW.md](AGENT_REVIEW.md).

## Agent-native desk API

All paths below use `/api/claim-loops/v1/workspace`. The desk and claim agent
GETs are read-only projections. Work starts only through an explicit mutation.

| Method | Path | Purpose | Response contract and seal |
| --- | --- | --- | --- |
| GET | `/desk` | 150 claims grouped by saved delegate state | `casepath.agent-desk/1.0.0`, `projection_sha256` |
| POST | `/desk/start` | Start the fixed bounded reference-review batch | `casepath.agent-desk-start/1.0.0`, `projection_sha256` |
| GET | `/claims/{claim_id}/agent` | Mandate, questions, citations, coverage, activity and knowledge receipts | `casepath.agent-desk-claim/1.0.0`, `projection_sha256` |
| POST | `/claims/{claim_id}/agent/control` | Persist pause or resume | `casepath.agent-control-result/1.0.0`, `projection_sha256` |
| POST | `/claims/{claim_id}/agent/decisions/preview` | Preview a bounded handler answer | `casepath.agent-decision-preview/1.0.0`, `preview_sha256` and `response_sha256` |
| POST | `/claims/{claim_id}/agent/decisions/apply` | Accept that exact preview | `casepath.agent-decision-result/1.0.0`, `response_sha256` |
| POST | `/claims/{claim_id}/agent/lessons/preview` | Preview explicit reusable fragment scope | `casepath.agent-lesson-preview/1.0.0`, `preview_sha256` |
| POST | `/claims/{claim_id}/agent/lessons/apply` | Save the approved versioned fragment | `casepath.causal-process-result/1.0.0`, `result_sha256` |

`desk/start` accepts `{limit: 6}`, with a strict integer from 1 to 20. It
requires `X-CasePath-Agent-Work: 1`, a same-origin request, and
`X-CasePath-Idempotency-Key`. Its persisted idempotency key binds the first
roster and authority contexts; repeated arrivals reuse that batch, including
across process restart. Saved pauses are respected. The response records each
claim's `started`, `reason`, and real run summary, plus `replayed`,
`mode: "deterministic_reference"`, and `provider_calls: 0`.
Exact arrivals validate their saved plan/context bindings and reuse one
batched verified work projection. The desk fingerprints all work tables and
selects the latest-run roster inside one SQLite read snapshot; a concurrent
new run appears on the next read.

The desk returns `groups: [{id,label,count,claims}]`, `counts`, `total`, and
`unstarted_count`. Group IDs are `needs_you`, `working`, `waiting`, `quiet`, and
`closed`. A row has separate `accountable`/`owner` and `delegate`, `agent_state`,
`ask`, `why`, `decider`, `question_count`, workspace revision/hash,
`latest_activity`, `coverage`, `review_started`, run ID/status, deadline evidence, process status,
and `draft_status` (`not_prepared`, `draft_not_sent`, or `approved_not_sent`).
`review_started` is true only when the row has a validated persisted review run;
it does not establish completion or source coverage. Quiet includes unstarted
reviews. The number of rows with `review_started: false` is `unstarted_count`.
Agent and desk rows also carry `recovery_required` (boolean) and `recovery_ask`
(human-readable string when required, otherwise null). Nonpaused persisted
interrupted/unconfirmed runs appear in `needs_you`; recovery wording takes
priority over their historical activity message. Resume wording requires a
verified safe checkpoint in a reference run. Unfinished calls or recorded
provider attempts instead require inspection and reconciliation.
Missing evidence alone never creates external waiting or closure.

The claim agent response includes `workspace_revision`,
`workspace_state_sha256`, `agent_revision`, `agent_state_sha256`, `owner`,
`mandate`, `state`, `pause_requested`, `questions`, `decisions`, `conflicts`,
`coverage`, `activity`, `run`, `process_status`, and `learning`. State is derived
from persisted work and decisions; unknown and historical work is not
represented as completed current work. `coverage` reports the original intake
roster, read/unread/limited sources, and `arrived_since`. An activity entry has
its actual event sequence, timestamp, type, role, label, and source references.
Knowledge matches are separate from actual accepted uses.

Desk/claim agent run summaries retain `authority_snapshot_currentness` and
identify `currentness_scope`. Exact matches use `authority_state`. A narrowly
verified automatic-draft-only suffix can use
`currentness: "current"`, `currentness_scope: "reviewed_sources_and_process"`,
and `authority_snapshot_currentness: "historical"`, with an explanatory
`currentness_note`. Source-loop, graph, effective assessment and historical
parent must match; manual drafts, owner/process changes and altered history
are excluded. This does not change the original work-service or tool-gate
currentness semantics.

A question includes `question_id`, `kind`, `prompt`, `why`, `decider`,
`proposal: {answer_id,reason}`, `counter_reading`, bounded `answers`, `sources`,
`affected_document_types`, `pane`, `previewable`, and `question_sha256`. Source
references preserve `artifact_id`, `source_sha256`, `text_sha256`, `quote`,
`start`, `end`, optional page, and the claim-scoped artifact URL. Draft approval
also includes the actual current `draft`. A reviewed conflict stays in
`conflicts` with its citations, handler review, and `truth_status: "unresolved"`.
Step and relationship answers retain `answer_id: "disputed"`; their embedded
causal operation uses the existing validation status `rejected`.

Controls accept `action: "pause" | "resume"`, `actor`, a required `reason`,
`expected_revision`, `expected_state_sha256`, `expected_agent_revision`, and
`expected_agent_state_sha256`. A pause takes effect at a safe checkpoint;
`pause_requested` can be true while the current operation is still running.
Resume reuses completed calls in the same safely interrupted run. The result
contains its accepted event hash, `replayed`, current `agent`, and real
`continuation` if any.
An exact historical draft/conflict retry still returns the accepted decision
event. It cannot prepare replacement wording or start/resume work after a
later mandate/decision event or workspace-parent change. Saved pauses are
checked before continuation; a skipped continuation has `started: false` and
reason `paused_by_handler` or `superseded_agent_decision`.

Decision preview accepts `question_id`, `answer_id`, `actor`, `reason`,
`expected_revision`, and `expected_state_sha256`. A proposed answer may use an
empty reason, in which case its proposed reason is bound to the preview. A
different answer requires a reason. The response keeps `graph`, `evaluation`,
`effective_assessment`, `impact`, and workspace binding at the top level. For
process decisions, `causal` contains the original
`casepath.causal-process-preview/1.0.0` receipt; it is null for conflict review
and draft approval. The top-level `preview_sha256` binds the complete outer
preview excluding both seal fields. `response_sha256` seals the returned
envelope including `preview_sha256` and `causal`. Apply adds that outer
`preview_sha256` to the same body and requires an idempotency header. The server
checks the outer identity and passes the original causal preview identity to
the existing engine. Results seal the complete agent envelope, including
`question`, `answer_id`, current `process`/`agent`, and `continuation`. A causal
result retains its original engine seal inside `causal_result`.

Lessons accept `name`, bounded `node_ids`, `actor`, `reason`, and workspace
revision/hash. Preview requires validated selected steps and internal edges,
exposes the family, documents, boundary relationships and stripped fragment,
and states `approval_required: true`, `automatic_learning: false`. Apply adds
the preview hash and idempotency header. Target-claim adoption continues to use
the existing causal `fragment.apply` preview/apply operation.

All mutation schemas forbid extra fields. New commands reject stale revision
or hash bindings. Exact idempotency retries recover the original accepted
event before stale-state checks; changing input under a key is rejected.
Draft approval binds the exact draft event, so edited wording requires another
approval. Conflict review binds the exact conflict material. Whole-envelope
hashes use the existing canonical JSON SHA-256 convention, omitting only the
named seal field unless the preview rule above specifies both fields.

Delegate controls/approvals are hash-chained under `delegate.{claim_id}` in
`claim_loop_events`, with a verified workspace parent. Process decisions and
fragments remain in the existing causal journal. Cached desk reads fingerprint
the relevant persisted authority/work bytes and corpus identity before reuse;
changed input is replayed and tampered prefixes fail closed. These routes never
authorize claim outcomes, sending, provider inference, or automatic learning.
See [Agent-native desk](product/AGENT_NATIVE.md) for behavior and validation.

Row cache reuse additionally binds exact per-claim workspace/delegate/source
journal bytes, all associated work-row bytes, lease-expiry/job state, corpus
identity, and global knowledge or otherwise unscoped journal dependencies.
One active claim can invalidate its own row without replaying the other 149.
Every cache hit still fingerprints persisted inputs, and callers receive
copies of verified rows.

The shared workspace store also memoizes up to 512 verified journal prefixes.
Fresh full-row fingerprints and corpus identity checks guard every reuse;
all historical intermediate states are retained only after successful cold
replay. Returned states are independently decoded and preserve receipt JSON
ordering. Storage/corpus identity changes create a distinct app service.
This changes read cost only; full authority and tool checks remain unchanged.

The local app also supplies the existing claim-loop router's optional accepted
process hook on `/claims/{claim_id}/process/apply` and
`/claims/{claim_id}/process/documents/apply`. Their existing
`casepath.causal-process-result/1.0.0` response and `result_sha256` remain
unchanged: the receipt binds its accepted prefix. The hook separately prepares
an absent current local draft and requests reference continuation only when
the accepted event is still the latest causal edit and the delegate is not
paused. Its continuation key binds that accepted event, preventing duplicate
work on exact retries. A later process edit prevents an old receipt from
reviving work. Clients refresh workspace, process, draft, and agent projections
after acceptance because separate draft events can advance the current prefix.
Preview routes never invoke the hook. Router users without a supplied hook
retain the existing behavior.

A newer accepted process edit requests checkpoint cancellation of an obsolete
reference run. While the executor stops, continuation returns
`started: false`, `reason: "latest_process_review_queued"` and the recorded
run summary. After a verified terminal checkpoint with no pending calls,
only the latest accepted event may start its event-bound continuation.
Saved pauses prevent it. An unfinished operation returns
`reason: "recorded_operation_requires_reconciliation"`; external work is not
automatically replaced. Queued cancellation hands off immediately through the
same guards. No read or startup path creates work: a process exit between
cancellation and handoff requires an exact latest-edit retry or an explicit
handler Resume/Retry. Immutable original receipts retain their meaning.

## Source contracts

The public package validates these primary data contracts before startup:

- `casepath.static-playbook-template/1.0.0`;
- `casepath.claim-binding/1.0.0`;
- `casepath.public-observable-corpus/1.0.0`;
- `casepath.source-manifest/2.1.0`.

The API returns projections of source and journal authority. A successful HTTP
response from a compatibility route does not by itself establish a real-world
claim decision, legal approval, model acceptance, or hosted release identity.
