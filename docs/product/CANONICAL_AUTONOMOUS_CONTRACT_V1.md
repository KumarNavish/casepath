# Canonical originals through the autonomous engine

This foundation is based on `36d34e6ad501e6c6d5df3194a645d1b1a7dc0fbb`.
It adds read-only original-case access and explicit admission to the existing
autonomous controller. It does not execute or qualify the nine-case demonstration.

## Identity and admission

All 150 `clm_` identities resolve directly to the immutable `synthetic-150`
observable intake corpus. Browsing does not import 150 journal streams. A
never-started original has revision zero, a source-bound state hash,
`status: not_started`, `phase: not_run`, `mode: unprocessed`, no acquired sources,
and null graph/evaluation/outcome. Startup resume sees only existing journal
streams. Historic `auto_` records retain their own identities.

An explicit same-origin `POST /api/claim-loops/v1/autonomous/claims/{id}/start`
accepts `idempotency_key`, `expected_revision: 0`, and the preview's
`expected_state_sha256`. The server resolves the original packet; clients cannot
replace its bytes or binding. Admission records an ordinary first `intake` event
with its existing null journal parent, plus the requested initial-state hash and
sealed original binding. Native message bytes, media, channel, email metadata,
and attachment relationships remain intact. Source acquisition occurs later in
the same controller, as recorded events. Exact admission retries return the
recorded result and do not submit another job. An explicit hosted retry may wake
an already accepted job parked behind a busy lease, using the existing guarded
scheduler without a new admission or duplicate physical attempt. A stale request
fails closed.

## Read contracts

All routes below share `/api/claim-loops/v1/autonomous`. GETs never submit work,
admit evidence, execute actions, publish knowledge, or send inference.

| Route | Result |
| --- | --- |
| `/claims?limit=200&offset=0&q=&domain=` | Paged summaries, `total`, `limit`, `offset`, `collection_sha256`, and domain counts. Original metadata is merged with recorded revision/hash summaries. |
| `/claims/{id}` or `/claims/{id}/snapshot?after=0` | `state`, revision/hash-bound `projection`, normalized `events`, `mode`, `current_revision`, `current_state_sha256`, `current_event_sha256`, and `cursor_sha256`. |
| `/claims/{id}/events?after=0` | Backward-compatible event/head fields captured atomically from the same journal rows. |
| `/sources/{id}/{artifact}` | Exact native original bytes with filename, media and content hash; available before admission. |
| `/sources/{id}/{artifact}/preview` | Derived extraction, native descriptor, `preview_only: true`, `evidence_admitted: false`, and `preview_sha256`. No evidence receipt. |
| `/sources/{id}/{artifact}/text` | Existing acquired-source receipt only; unacquired sources return 409. |
| `/claims/{id}/replay?through_seq=N` | Verified prefix state/events/projection, `mode: replay`, `replay_only: true`, prefix cursor and current saved-head provenance. |

Snapshot state and events come from one verified journal-row read, fixing the
separate reads that could race an advancing writer. `after` cannot exceed the
captured revision. Replay validates the entire saved chain before reducing its
recorded prefix. Prefix state/hash/cursor belong to `through_seq`; the
`current_*` fields identify the later saved head. Sequence zero is available only
for originals and remains a source projection, with no journal event. Corrupt
journals never fall back to an unprocessed original.

Collection caching compares every SQL field and raw event byte and rechecks
original source hashes; it avoids reducing unchanged histories. Hosted reads
verify fresh persisted chunks at each result boundary, including warm-cache
reads. No cache is journal authority.

## Browsing boundary and limits

Domain/family labels are navigation metadata only. Their source is the exact
three-field whitelist `case_id`, `domain`, `family_id` from the benchmark manifest
with SHA256 `638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c`.
The compact runtime mapping contains 150 IDs, three domains of 50, and 28
families. It appears only in collection summaries, never in state, original
binding, admission payload, source receipts, or provider context. Split, expected
answers, evaluator fields and referenced answer files are excluded.

Extraction coverage is distinct from understanding, document completeness and
evidence sufficiency. A one-page PDF that refers to another page remains the
actual one-page original; extracted text does not supply the absent page. JPEG
sources remain received but unsupported by the operational text reader.

Focused tests use isolated temporary journals, immutable fictional originals,
and deterministic doubles. The hosted allowance remains exhausted at 24 calls;
no allowance, provider configuration, production state, release manifest or
deployment changes belong to this milestone. The 27 legacy migration-audit
cases remain unsupported in this Cloud sandbox because `/proc/1/maps` is
inaccessible; the audit remains fail closed. Mac owns integration, final sealing,
visual acceptance, real demonstration evidence and hosting publication.
