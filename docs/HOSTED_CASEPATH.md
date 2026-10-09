# Hosted autonomous workspace

The hosted workspace runs the same source-grounded autonomous controller,
process graph, node-derived document checklist, and qualified knowledge store as
the accepted local product. It exposes the autonomous workspace; the earlier
Review workspace remains available in the local product.

## Services and persistence

- Frontend: owner-private ChatGPT Site `casepath-autonomous`.
- Compute: FastAPI Cloud Hobby app `casepath-agent`, configured directory
  `casepath-api`, entrypoint `hosted_main:app`.
- Storage: Turso Free database `casepath-autonomous`, primary in Ireland.

Compute is ephemeral and may sleep. There is no local database replica: original
source chunks, claim events, knowledge, and model reservations commit directly to
the remote primary. Replay and source validation run before the short write
transaction, which compares the full journal snapshot before accepting an event.
A wake-up may briefly return an unavailable message. Free
hosting is suitable for the bounded demo; it has no always-on guarantee. FastAPI
Cloud is a public-beta service. No paid hosting, overages, or keep-alive jobs are
part of this deployment.

The Sites worker authenticates its server hop with a separate secret and forwards
only allowlisted application headers. Browser login cookies never leave Sites.
The API permits unauthenticated `/healthz` only. Every data route requires the
server secret and the configured Site origin; mutations additionally require the
browser Origin and existing autonomous-work header.

## Runtime configuration

Keep runtime values out of source and the Sites manifest. Sites requires
`CASEPATH_API_ORIGIN` and secret `CASEPATH_PROXY_TOKEN`. FastAPI Cloud requires:

| Variable | Meaning |
| --- | --- |
| `CASEPATH_SITE_ORIGIN` | Exact HTTPS origin of the private Site |
| `CASEPATH_PROXY_TOKEN` | Same secret as the Sites worker |
| `CASEPATH_TURSO_URL` | Remote libSQL database URL |
| `TURSO_AUTH_TOKEN` | Database-scoped secret |
| `CASEPATH_SOURCE_COMMIT` | Full Git commit used for this release |
| `CASEPATH_HOSTED_WRITABLE` | `0` during migration; `1` after ownership transfers |
| `CASEPATH_AUTONOMOUS_ENABLED` | `1` only with the existing imported allowance |
| `CASEPATH_AGENT_WORK_MODEL` | Pinned model identifier |
| `OPENROUTER_API_KEY` | Existing authorized demo credential, as a secret |

FastAPI Cloud supports secret input over stdin:

```sh
uv run --with 'fastapi[standard]' --no-project fastapi cloud env set NAME \
  --value-stdin --secret --app-id APP_ID --no-redeploy --json
```

Resolve credentials from a secret manager directly into stdin. Never paste them
into commands, source, receipts, logs, or a browser bundle.

## Ownership, failures, and allowance

Stop the local paid writer before copying its durable journals. Produce SQLite
online backups and copy the immutable originals. Import every table and compare
paged row digests and source hashes before enabling cloud writes. Keep those
backups and the migration receipt outside the source repository. Use
`casepath-api/tools/migrate_hosted.py`: `snapshot` creates the frozen backup,
`migrate` resumes exact inserts, and `verify` compares every remote row and
original. Supply `--source-root`, `--snapshot`, an external `--receipt`, and
`--writers-stopped` as appropriate. The script never changes an allowance.

A remote database lease fences each workflow through knowledge publication.
Deployment overlap cannot acquire two committed owners. Every owned write
transaction checks its generation. The controller recovers durable pending work
from real HTTP requests; there is no periodic synthetic traffic.

The original spending ledger remains authoritative. Migration must preserve its
base allowance, one-time grant, actual costs, unknown reservations, and provider
receipts. It must never create a second allowance. A missing database
acknowledgement poisons that connection and prevents model dispatch. An uncertain
provider call remains reserved and is never automatically resent. Restarting a
service cannot replenish the allowance.

Do not restart the old local paid writer after cloud cutover. If rollback becomes
necessary, first disable and drain the cloud writer, then reconcile and export
the current cloud ledger. A stale pre-cutover copy is not a writable rollback.

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

Deploy the linked FastAPI Cloud app from the repository root. Start read-only,
verify authenticated saved-state readback, then complete the single-writer
cutover. Verify deployment status rather than treating submission as success.
The API `/healthz` and frontend `deployment.json` must identify the same commit.

The deterministic hosted tests use isolated SQLite behind HTTP MockTransport and
mocked provider responses. They cover ambiguous commits, transaction fencing,
no paid redispatch, interrupted source uploads, full-size original readback,
authentication, and recovery. Cloud acceptance additionally requires remote
readback and a fresh compute deployment preserving exact saved state and ledger.
