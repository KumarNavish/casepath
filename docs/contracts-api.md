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
| GET | `/claims/{claim_id}/runs/{run_id}/stream` | stream persisted events from a sequence cursor |
| POST | `/claims/{claim_id}/runs/{run_id}/resume` | resume the same recoverable run |
| POST | `/claims/{claim_id}/runs/{run_id}/cancel` | request a safe stop without clearing unresolved calls |

Agent-work mutations require the same-origin `X-CasePath-Agent-Work: 1` guard.
The normal launcher remains provider-free. External Facts additionally requires
explicit server configuration and `facts_worker: "external_facts"`; invalid
configuration is rejected rather than silently falling back. See
[AGENT_REVIEW.md](AGENT_REVIEW.md).

Start accepts `idempotency_key`, `expected_context_sha256`, and `facts_worker`
in its body. An exact retry returns the same admitted run; changing the context
or worker under that key is rejected. Start and run inspection return
`{contract, summary, objects, response_sha256}`. The SHA-256 covers the full
packet except its seal. The summary exposes `claim_id`, `facts_worker`, the
immutable `idempotency_key` and `requested_context_sha256`, selected
`provider_model`, and the run's cost bound and status. A client verifies the
seal and exact request identity before presenting the start as accepted.

`/stream` emits `work` events with persisted sequence IDs, accepts `after` and
`Last-Event-ID`, and emits `done` after draining a terminal or interrupted run.
Reconnection reads saved events; it does not start or retry provider work.

The optional [local demo profile](setup-demo.md) requires both
`CASEPATH_AGENT_WORK_EXTERNAL_FACTS=1` and `CASEPATH_AGENT_WORK_DEMO=1`, an exact
`CASEPATH_AGENT_WORK_MODEL`, a fresh hash-bound `CASEPATH_AGENT_WORK_CATALOGUE`,
and a server-only credential. Its explicit policy is supplied by
`CASEPATH_AGENT_WORK_MAX_EXTERNAL_RUNS=3`,
`CASEPATH_AGENT_WORK_MAX_PROVIDER_CALLS=18`,
`CASEPATH_AGENT_WORK_TOTAL_COST_USD=0.10`, and
`CASEPATH_AGENT_WORK_RUN_COST_USD=0.02`. The persisted policy cannot be reset by
relaunching. The current inspected selection is `anthropic/claude-haiku-5.5`;
selection and applicable prices must validate against that launch's catalogue.

Capabilities add `external_configuration_status`, `external`, and
`external_budget`. The budget includes `scope: "persistent_local_demo"`,
`max_runs`, `max_provider_calls`, `total_cost_limit_usd`, `run_cost_limit_usd`,
`runs_used`, `provider_calls_used`, `actual_cost_usd`, `reserved_cost_usd`,
`remaining_cost_usd`, `unknown_calls`, `in_flight`, `can_start`, `reason`, and
`automatic_retry: false`. The normal profile has no external worker or demo
budget. A configured external start requires an accountable handler, unchanged
workspace authority, an unpaused delegate and no unresolved prior claim work.
Admission reserves the run allowance; provider intent, reservation and the
single in-flight provider slot are persisted atomically before transmission.
Unknown outcomes keep their reservation and cannot be automatically retried.
These fields report a bounded allowance, not a claim of observed provider cost.

Only Facts uses the external model. It accesses the existing typed source tools
and emits checked source quotations. The remaining roles and process authority
are deterministic. Provider prose and hidden reasoning are discarded. A
successful external completion may prepare an unsent draft through the same
guarded workspace path; it does not schedule another paid review.

## Agent-native desk API

All paths below use `/api/claim-loops/v1/workspace`. The desk and claim agent
GETs are read-only projections. Work starts only through an explicit mutation.

| Method | Path | Purpose | Response contract and seal |
| --- | --- | --- | --- |
| GET | `/desk` | 150 claims grouped by saved delegate state | `casepath.agent-desk/1.0.0`, `projection_sha256` |
| POST | `/desk/start` | Start the fixed bounded reference-review batch | `casepath.agent-desk-start/1.0.0`, `projection_sha256` |
| GET | `/claims/{claim_id}/agent` | Mandate, questions, citations, coverage, recorded work, live-review eligibility and knowledge receipts | `casepath.agent-desk-claim/1.0.0`, `projection_sha256` |
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
`coverage`, `activity`, `run`, `process_status`, `learning`, `live_work`,
`live_review`, and `can_clear_external_pause`. State is derived
from persisted work and decisions; unknown and historical work is not
represented as completed current work. `coverage` reports the original intake
roster, read/unread/limited sources, and `arrived_since`. An activity entry has
its actual event sequence, timestamp, type, role, label, and source references.
Knowledge matches are separate from actual accepted uses.

The additive `live_work` projection derives Sources, Findings, Process and
Documents from verified persisted events, preserving claim/run identity,
sequence, event hash, timestamp and source/node/document references. Its scope
is `recorded_review_work_not_claim_authority`. It reports real reader identity
and request/cost observations, and distinguishes current from historical work.
Connections require actual recorded links; mapping a step from saved handling
rules does not establish a source-derived legal conclusion. Its concise work
summaries are not model chain-of-thought.

`live_review` is `{available: false}` when the explicit capability is absent.
When available it includes `model`, `run_cost_limit_usd`,
`total_cost_limit_usd`, `budget`, `context_sha256`, `can_start`, `reason`, and
`automatic_retry: false`. Eligibility checks owner, pause, pending or active
work, budget and the exact context revision/hash. The server repeats admission
checks on start. `can_clear_external_pause` is a separate boolean: it requires
a paused delegate, terminal external run, known finite usage, no pending calls
and no active local job. All these fields are covered by the claim projection
seal. Reading them starts no work.

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
`expected_agent_state_sha256`. A reference pause takes effect at a safe
checkpoint; `pause_requested` can be true while the current operation is still
running. Reference resume reuses completed calls in the same safely interrupted
run. For external Facts, pause records a stop request: a request already sent
may return its receipt, then work stops before another request. Queued or
interrupted external cancellation retains pending effects. A later resume may
only clear that saved pause when `can_clear_external_pause` is true; it neither
resumes external work nor sends a provider request. Unknown outcomes require
inspection. The result
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

The joined native receipt sequence saves the validated `lt_deadline` correction
from source `clm_f69b1747447bc221` at revision 130 as fragment
`9a619ae6b4f890b534c5e2fe938a6e54227b9948081883dd0f93b72db0fe57f6`.
The source's revision-135 restoration retains that saved knowledge. Target
`clm_0e538990cc6ba7ef` revision 4 records the accepted fragment use, the added
`lease_contract` requirement at `lt_deadline`, and its newly prepared
`draft_not_sent` request. This is one explicit same-family reuse, not automatic
learning or generic memory-reuse acceptance. See the
[joined evidence](../../casepath-agent-native-v2-evidence/v4-joined-knowledge-proof.md)
for exact state, event and fragment seals and the retained initial failure.

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
changed input is replayed and tampered prefixes fail closed. These desk,
decision and learning routes never authorize claim outcomes, sending, provider
inference, or automatic learning. Paid inference has the separate explicit
agent-work start and server admission contract above.
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


### Local proposal reconciliation

The agent control plane additionally exposes `POST /api/claim-loops/v1/workspace/claims/{claim_id}/agent/reconcile`. It uses `X-CasePath-Idempotency-Key` and `X-CasePath-Agent-Work: 1`. The body supplies `actor`, `reason` (up to 1,000 characters), `expected_revision`, `expected_state_sha256`, `expected_agent_revision`, `expected_agent_state_sha256`, `run_id`, `call_id`, `object_id`, `expected_last_event_sha256`, and `expected_work_state_sha256`. Use only the exact candidate from `agent.run.recovery.reconciliation`; the server revalidates eligibility and all prefixes.

The sealed `casepath.agent-reconciliation-result/1.0.0` response contains the delegate event identity, replay status, a work reconciliation receipt and the current agent projection. A successful work receipt has `reconciled: true`, its event hash and `claim_state_changed: false`. A superseded request has `reconciled: false` and `reason: superseded_recovery_request`; it does not establish a recovered proposal. The operation never resumes work automatically. See [agent-native behavior](product/AGENT_NATIVE.md) for its narrow deterministic-only scope.
