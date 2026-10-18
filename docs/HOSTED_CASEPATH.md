# Public CasePath workspace

The public hosted workspace lets anyone with the link inspect the synthetic
claims, saved demonstrations, verified original sources, process graphs,
document checklists and qualified Knowledge. It is permanently read-only.
New intake, file upload, starting or retrying work, pause, resume and saved-result
reconciliation are unavailable through the public Site and hosted API.
Authorized Mac work keeps the existing local product and operator paths; the
earlier Review workspace remains available locally.

## Services and persistence

- Frontend: ChatGPT Site `casepath-autonomous`.
  Preserve the Site's current audience during a release.
- Compute: FastAPI Cloud Hobby app `casepath-agent`, configured directory
  `casepath-api`, entrypoint `hosted_main:app`.
- Storage: Turso Free database `casepath-autonomous`, primary in Ireland.

Compute is ephemeral and may sleep. There is no local database replica: the public
service reads saved source chunks, claim events, knowledge and spending records
from the remote primary. Journal replay and source identity checks remain in
force. Browsing never admits evidence, changes a journal or dispatches work.
A wake-up may briefly return an unavailable message. Free
hosting is suitable for the bounded demo; it has no always-on guarantee. FastAPI
Cloud is a public-beta service. No paid hosting, overages, or keep-alive jobs are
part of this deployment.

The Sites worker rejects every method except GET and HEAD before upstream or
asset access. The hosted API independently enforces the same permanent 403
denial before reading a command body or entering a route. This policy covers
current, legacy and unknown paths. Visitor Origin, work headers, user IDs and
email addresses do not grant write authority.

The worker authenticates its read hop with a separate secret and forwards only
allowlisted application headers. Browser login cookies never leave Sites.
The API permits unauthenticated `/healthz` only. Every data route still requires
the server secret and configured Site origin. The secret authenticates the
transport; it does not identify a visitor as an owner.

The hosted status and health responses explicitly report `read_only: true` and
`writable: false`. The hosted bundle declares that capability before entry
selection, including when assets are served directly. Legacy Review and
foundation entry URLs open autonomous inspection. Public controls retain source
inspection and replay playback, with a central request guard against work calls.

## Runtime configuration

Keep runtime values out of source and the Sites manifest. Sites requires
`CASEPATH_API_ORIGIN` and secret `CASEPATH_PROXY_TOKEN`. FastAPI Cloud requires:

| Variable | Meaning |
| --- | --- |
| `CASEPATH_SITE_ORIGIN` | Exact HTTPS origin of the Site |
| `CASEPATH_PROXY_TOKEN` | Same secret as the Sites worker |
| `CASEPATH_TURSO_URL` | Remote libSQL database URL |
| `TURSO_AUTH_TOKEN` | Database-scoped secret |
| `CASEPATH_SOURCE_COMMIT` | Full Git commit used for this release |
| `CASEPATH_HOSTED_WRITABLE` | Legacy value; cannot enable writes in the public service |
| `CASEPATH_AUTONOMOUS_ENABLED` | Legacy value; cannot enable inference in the public service |

The public service never constructs a model adapter, refreshes a provider
catalogue, resumes pending work or arms recovery timers. Model and provider
credentials are not required by this composition. Startup retains existing
schema and lease infrastructure initialization; this is distinct from passive
GET handling, which performs no durable data writes. Its store also uses the
existing read-only source-publication and journal-admission guards. Local and
operator storage and workflow classes retain their existing behavior.

FastAPI Cloud supports secret input over stdin:

```sh
uv run --with 'fastapi[standard]' --no-project fastapi cloud env set NAME \
  --value-stdin --secret --app-id APP_ID --no-redeploy --json
```

Resolve credentials from a secret manager directly into stdin. Never paste them
into commands, source, receipts, logs, or a browser bundle.

### Private read seed

After sealing and committing the final release source, the authorized Mac
operator can acquire a release-bound startup seed from the current primary.
Use the existing private `CASEPATH_TURSO_URL` and `TURSO_AUTH_TOKEN` bindings;
neither credentials nor hosted journal/source bytes belong in Codex Cloud.
The exporter needs no completed cache or local production replica:

```sh
mkdir -p "$PRIVATE_UPLOAD_ROOT/casepath_api/artifacts"
.runtime/casepath-dev-v2/venv/bin/python casepath-api/tools/export_read_seed.py \
  --deployment-commit "$CASEPATH_SOURCE_COMMIT" \
  --output "$PRIVATE_UPLOAD_ROOT/casepath_api/artifacts/hosted-read-seed-v1.json"
```

The JSON schema is `contract: "casepath.hosted-read-seed/1"`,
`deployment_commit: <final 40-hex release>`, `journal_rows: [<row>, ...]`, and
`sources: [{sha256, content_base64}, ...]`. Each row has exactly `session_id`,
`loop_id`, `sequence` (integer), `idempotency_key`, `command_sha256`,
`event_sha256`, `event_json` (verbatim SQL TEXT), and `created_at`; the other row
values are TEXT. Sources contain canonical base64 of the exact original bytes.
No reduced states or SQL templates are serialized.

`CASEPATH_SOURCE_COMMIT` must be the exact final 40-hex release commit, recorded
after source sealing. Do not seal again to include the generated seed. The
output is a server-only API artifact in a temporary private upload archive or
source copy outside every Git checkout. Keep it out of the canonical checkout,
Git, Sites, frontend assets, shared receipts, and logs. The exact artifact path
is also ignored as a defense against accidental copying. Export refuses an
existing output, missing parent directory, Git checkout destination, symlink
ancestor or parent traversal. It rechecks the canonical directory before atomic
publication through its open directory handle.
Remove or archive an old private seed deliberately before a new acquisition.

Every acquisition uses SELECT-only, independently closed snapshots: small
type/length/key metadata pages carry bounded short TEXT values; larger TEXT
and BLOB payloads are reassembled from at most 32 KiB raw byte slices. Encoded
requests and responses, including the final proof, are capped at 64 KiB. Export
also stops at 4,096 requests, one hour, or 256 MiB of cumulative request/response
bytes; it reserves the unchanged 12-second request deadline before each send.
The native transport retains its 32 MiB outer guard and zero retries. The export
transport rejects writes, sequence and batch operations before dispatch.
The exporter preserves exact SQL TEXT bytes, integers and BLOBs; the seed stores
only raw journal rows and hash-bound original source bytes. Full native replay,
source extraction/validation, and one unchanged fresh atomic journal/source
schema and complete byte proof must pass before a new mode-0600 file appears.
A failed acquisition or mutation stops the export; do not relax bounds or
substitute historical fixtures or old local journal/source copies.

The success receipt prints only the target commit, checksum, counts and size.
`CASEPATH_READ_SEED_PATH` defaults to the API package's
`casepath_api/artifacts/hosted-read-seed-v1.json`; set it explicitly for another
private deployed path. `CASEPATH_READ_SEED_SHA256` is required when a seed is
present. Keep the final release commit binding unchanged. A confirmed SQL/schema
mismatch falls back to the current bounded reader; malformed or unconfirmed
proofs fail closed. The exact package-data allowlist includes only
`casepath_api/artifacts/hosted-read-seed-v1.json`; before upload, inspect the
actual private wheel or upload payload and verify it contains those exact seed
bytes and no frontend copy. Git ignore rules do not establish the hosting CLI's
upload behavior. Create the official CLI archive only after verifying clean
canonical source and the full release gate, and inject the seed only into that
temporary API payload. Exporting, building, or checking a package does not deploy
it. Hosting region remains unchanged.

## Ownership, failures, and allowance

Stop the local paid writer before copying its durable journals. Produce SQLite
online backups and copy the immutable originals. Import every table and compare
paged row digests and source hashes before enabling cloud writes. Keep those
backups and the migration receipt outside the source repository. Use
`casepath-api/tools/migrate_hosted.py`: `snapshot` creates the frozen backup,
`migrate` resumes exact inserts, and `verify` compares every remote row and
original. Supply `--source-root`, `--snapshot`, an external `--receipt`, and
`--writers-stopped` as appropriate. The script never changes an allowance.

Existing authorized operator workflows use a remote database lease to fence
work through knowledge publication. Deployment overlap cannot acquire two
committed owners, and every owned write transaction checks its generation.
The public service closes dispatch before exposing projections. Pending work
and completed outcomes awaiting Knowledge publication remain unchanged across
public startup, restart, browser reads and callback races. Recovery behavior in
the separate operator controller is preserved.

The original spending ledger remains authoritative. Migration must preserve its
base allowance, one-time grant, actual costs, unknown reservations, and provider
receipts. It must never create a second allowance. A missing database
acknowledgement poisons that connection and prevents model dispatch. An uncertain
provider call remains reserved and is never automatically resent. Restarting a
service cannot replenish the allowance.

A verification failure stays stopped across service restarts. An authorized
operator may explicitly apply an already completed, sealed interpretation and
verification pair through the existing local operator path
`POST /api/claim-loops/v1/autonomous/claims/{claim_id}/reconcile-saved-results`.
The public hosted route always returns 403. The local command requires the
failed claim's exact `expected_revision`
and `expected_state_sha256`, a unique `idempotency_key`, `actor`, and `reason`,
with the existing `X-CasePath-Agent-Work: 1` header. It has no provider transport,
model reservation, or retry queue. It verifies the saved requests, results,
receipts, original source bytes, and frozen rule context before writing.

Reconciliation appends its admission and completion to the existing journal;
the original failure and provider records remain unchanged. An inaccurate
citation rejects the whole affected item, which remains unresolved and cannot
complete a graph node or qualify reusable evidence. The UI exposes the rejection
and reconciliation history. After an uncertain response, read the journal and
ledger before considering another command. Incomplete reconciliation never
automatically restarts, and a newer source arrival or pause retains ownership.

Do not restart the old local paid writer after cloud cutover. If rollback becomes
necessary, first disable and drain the cloud writer, then reconcile and export
the current cloud ledger. A stale pre-cutover copy is not a writable rollback.

## Synthetic demonstration admission

The `synthetic-nine-v2` profile binds nine original claim IDs to separately
labelled synthetic supplements and historical review dates. It regenerates the
v1 documents with concise fictional-document labels and verifies each cleanup
against its immutable v1 source. Original files, earlier supplements and journal
prefixes remain intact. Reassessment appends a new recorded investigation; the
default demonstration starts at its verified preparation event, while History
retains the earlier documents and explicit replay positions. The profile enables
a deterministic assessment through the existing process and knowledge engine;
it grants no provider calls, spending allowance, external communication or court
action. The public service preserves the resulting history. Its nine demonstrations can
recompute the same assessment in memory and stream source-bound operations.
This GET-only check uses no provider, saves no case or knowledge changes, and
is bounded to two concurrent checks, twelve starts per minute and ten seconds
per check. An unavailable live check falls back to an explicitly labelled,
immutable operation trace admitted by the private operator. History exposes
the operations and the exact saved-state checkpoints they reproduce.

From the same clean, committed checkout, an authorized Mac operator prepares a
private plan with `casepath-api/tools/admit_reference.py dry-run --plan PATH`.
This reads the remote snapshot and executes in disposable local SQLite. Inspect
the nine final heads and exact source additions before running the same command
with `apply`. Apply checks the source/profile identities, unchanged snapshot and
budget, then appends under the existing lease and exact-row comparison. Keep
the plan and receipt outside Git. A source change requires a fresh plan. After
an uncertain apply result, reconcile the committed heads before any retry.

The intake gate derives its document requirements from the applicable process.
Unverified or incomplete packets remain at intake, with missing requirements
available in the projection. Historical reference completion is limited to its
recorded assessment scope; it is not a current filing deadline or a completed
real-world remedy.

## Release and verification

Follow `CONTRIBUTING.md` to seal and test the source. The frontend build is:

```sh
python casepath/tools/build_static_site.py --require-known-commit
python casepath/tools/build_sites_site.py
```

Set `CASEPATH_SOURCE_COMMIT` to the canonical release commit and
`CASEPATH_FRONTEND_ORIGIN` to the selected Site's exact HTTPS origin for the
hosted build. The service override leaves the historical release contract intact.

`dist/client` contains curated assets; `dist/server/index.js` is the Sites worker.
The root `.openai/hosting.json` contains the stable project identity only. Publish
through the Sites workflow and connector using the exact pushed commit.

The Site source repository contains a compact frontend distribution because
the canonical Git history includes research archives larger than the Sites
object limit. Preserve canonical history. The distribution contains the exact
public allowlist from `build_static_site.py`, the three build scripts, the Sites
worker, and the same `.openai/hosting.json`. Its committed
`casepath-source-provenance.json` records the canonical commit, tree, and every
copied file's hash. Its README documents the reproducible build. Do not include
databases, secrets, API runtime state, or research archives in that distribution.

The native Sites version uses the distribution's pushed Git commit. The API
and frontend `source_commit` both use the canonical product commit whose bytes
were copied and verified. Record these two identities separately in release
receipts; do not present the distribution commit as the canonical API source.

Deployment is a separate authorized operation after source review and the
formation and legal-corpus workstream checkpoints. When authorized, deploy the
linked FastAPI Cloud app from the repository root and verify authenticated
saved-state readback. The public service remains read-only regardless of legacy
environment flags. Verify deployment status rather than treating submission as success.
The API `/healthz` and frontend `deployment.json` must identify the same commit.

The deterministic hosted tests use isolated SQLite behind HTTP MockTransport and
mocked provider responses. They cover ambiguous commits, transaction fencing,
no paid redispatch, interrupted source uploads, full-size original readback,
authentication, and recovery. Cloud acceptance additionally requires remote
readback and a fresh compute deployment preserving exact saved state and ledger.
The focused public-policy tests additionally reject forged visitor authority and
all work verbs without upstream or durable-service access. Pending and completed
unpublished synthetic fixtures retain exact saved rows across reads, restarts and
manual recovery-callback probes. These deterministic checks do not deploy or
inspect production state.
