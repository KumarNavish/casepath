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

## Source contracts

The public package validates these primary data contracts before startup:

- `casepath.static-playbook-template/1.0.0`;
- `casepath.claim-binding/1.0.0`;
- `casepath.public-observable-corpus/1.0.0`;
- `casepath.source-manifest/2.1.0`.

The API returns projections of source and journal authority. A successful HTTP
response from a compatibility route does not by itself establish a real-world
claim decision, legal approval, model acceptance, or hosted release identity.
