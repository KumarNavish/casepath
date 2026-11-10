# Deploying CasePath beyond the development workspace

CasePath runs end to end on a single development workspace today. This document describes how the same code moves to an operated environment, where:

- a gateway signs people in;
- runs can outlast a request timeout;
- cases live in a managed database.

Every piece that differs between the two environments sits behind one of the boundaries below and is chosen by configuration. Tests exercise each boundary, so the application that passes the benchmark on the workspace is the application that is deployed.

## The two halves

**Agent core** (`core.py`, with `agents.py`, `reading.py`, `casegraph.py` and `workflows.py`) is everything that uses a model. It is stateless: a JSON job goes in and a JSON outcome comes out.

- `prepare(job, model, blobs, on_event, on_extraction)` reads scanned pages, routes the case, runs the five agents and works out what the run teaches. It can take many minutes.
- `recheck(job, prior, documents, model, on_event)` checks only the document needs a process edit added.
- `evaluate(workflow, knowledge, edits, result, case_id)` gives the case's own process and where the case stands. It uses no model, so it can answer synchronously.

The job and outcome formats (`casepath.agent-job/1`, `casepath.agent-outcome/1`) are specified in `core.py`. `tests/test_core.py` runs a job built from plain JSON with no store at all, as a queue worker would. `python -m casepath_internal.core prepare <job.json> --blobs <dir>` does the same from the command line.

**Case service** (`app.py`, `store.py`, `runner.py`, `knowledge.py`) owns cases, files, runs, events, edits, Knowledge, feedback, deletion and sign-in. It builds jobs (`RunService.job`) and persists outcomes (`RunService.save`):

- each file's reading as soon as it is done;
- the result;
- each applied Knowledge item's statistics, on its current version;
- the result checker's proposals, as candidates.

The case API is fixed in `docs/contracts/case-api.openapi.json`. `tests/test_app.py` fails when the code and the saved contract diverge (`python -m casepath_internal contract --write` updates it). The browser workspace, the batch tool and the benchmark evaluator use only this API, so a reimplementation of the case service that honours the contract keeps all three working.

## Boundaries and how each is chosen

| Concern | Development workspace | Operated environment | What changes |
|---|---|---|---|
| Sign-in | `CASEPATH_DEV_USER` (one person) | Gateway header: `CASEPATH_IDENTITY_HEADER`, `CASEPATH_IDENTITY_FORMAT=jwt`, the user and roles claims, and `CASEPATH_REQUIRED_ROLE` (403 without it) | Configuration |
| Model credential | `CASEPATH_AZURE_CREDENTIAL=cli` (the person's `az` sign-in) | `managed_identity` or `workload_identity` | Configuration |
| Model endpoint | The Azure OpenAI resource | The resource, or a gateway host named in `CASEPATH_MODEL_GATEWAY_HOSTS` (it may carry a path) | Configuration |
| Model deployment | `CASEPATH_AZURE_OPENAI_DEPLOYMENT`, optional reading deployment and dated API version | Same | Configuration |
| Long runs | Worker threads in the case service (`RunService`) | A queue consumer that calls `core.prepare` with the same job; events and the outcome go back on the queue, and large outcomes go through blob storage | One adapter around `core.prepare` |
| File bytes | `core.StoreBlobs` (store files) | A blob-storage reader with the same `read(file)` method (`core.DirectoryBlobs` shows the shape) | One small adapter |
| Persistence | SQLite plus files (`store.py`) | The case service's database, behind the same API contract | The case service, not the agents |
| Workflow catalogue | JSON files in `CASEPATH_WORKFLOW_CATALOGUE` | Same files, shipped with the release | None |
| Retention | `python -m casepath_internal purge --older-than-days N` | The same rule in the case service's scheduled job | Schedule |
| Deletion | `DELETE /api/cases/{id}` removes the case and everything derived from it, and keeps a content-free deletion record | Same contract | None |
| Logs | Run errors and events are stored with the run, not logged | Same; access logs carry ids only | None |

## One container for a pilot

For a first company-wide pilot, the whole application runs as one container (`Dockerfile`): the case API, the case
worker's workspace and the agent core. One replica keeps its cases on a persistent volume at `/data`.

- **Build:** `docker build -t casepath .`
  - `BASE_IMAGE` and `PIP_INDEX_URL` can name internal mirrors.
  - Behind a firewall that re-signs TLS, add `--secret id=ca,src=<CA bundle>`. The bundle is used for the build only.
- **Run:** `docker run -p 8080:8080 -v casepath-data:/data --env-file <settings> casepath`. All settings come from the environment, and none are in the image.
  - **Sign-in:** the gateway variables above. Without them the API refuses to serve.
  - **Model:** endpoint, deployment and credential. For outbound TLS through a firewall, `CASEPATH_CA_BUNDLE` names a mounted CA file.
  - **Synthetic cases:** `CASEPATH_SEED_SUITE=/app/benchmark` loads them at start, once, for everyone to open.
  - **Concurrency:** `CASEPATH_RUN_WORKERS` sets how many cases are prepared at once.
- **Checked here:** the image builds; it runs as a non-root user and serves the workspace. The synthetic cases load once and survive a restart. With gateway sign-in, a request is refused with 401 without an identity and 403 without the access role.

Splitting the agent core from the case service, as described above, comes after the pilot. The container already holds both halves behind their contracts.

## As a Databricks App

The same application runs as a Databricks App. `deploy/databricks/package.sh <dir>` assembles the folder the app runs
from: the package, the workflow catalogue, the synthetic cases, `app.yaml` and `requirements.txt`. In `app.yaml`:

- **Sign-in:** Databricks signs people in and passes their e-mail in `X-Forwarded-Email`. `CASEPATH_ALLOWED_USERS` admits only the named pilot group. App permissions in Databricks should match that list.
- **Model:** `CASEPATH_MODEL_PROVIDER=databricks` calls a model in the workspace, such as one from its gateway, through its OpenAI-compatible chat API. The app signs in as its own service principal. `chat_model.py` translates the agents' messages, tool calls, structured answers and page images, so nothing else changes.
- **Storage:** the app's own disk does not survive a restart. With `CASEPATH_VOLUME` naming a Unity Catalog volume, the case store is restored from the volume at start and copied there every 30 seconds and at shutdown (`mirror.py`). One app instance writes a volume.
- **Packages:** the app needs nothing beyond the platform's web packages.
  - **Prepared cases:** where the PDF libraries are, `python -m casepath_internal.prepare <files> --out <dir>` makes a prepared case: the original files, the extracted text and images of the scanned pages, made without a model.
  - **Importing them:** the app imports prepared cases from the volume's `incoming/` folder. The synthetic cases ship prepared.
  - **Loose files without extra packages:** uploaded or imported files are read by CasePath itself when the PDF
    libraries are missing (`pdfread.py`, `ccitt.py`, `msg.py`, standard library only):
    - a PDF's text layer, including subset and CID fonts with their Unicode maps and compressed object streams;
    - each scanned page's own image: JPEG as it is, bitmaps (also inline, CMYK or 16-bit) and CCITT Group 3/4 fax
      scans as PNG. A page drawn only with vector paths (text as outlines) is drawn as a PNG (`raster.py`). JPEG 2000
      and JBIG2 pages are reported as not read;
    - Outlook `.msg` e-mails like `.eml` ones;
    - every e-mail attachment, which becomes a file of the case, marked with the e-mail it came from.
    `/api/health` reports `pdf_text` (`pypdf` or `builtin`) and `scanned_pages` (`rendered` or `embedded images`).
  - **Rendering every page:** set `WHEELS_INDEX` to the approved package feed when packaging. The PDF libraries are then
    shipped as wheels checked against PyPI's published SHA-256, installed from the app folder and used first.
  - **Checked:** in a Python 3.11 runtime with no network and only fastapi, uvicorn and httpx, the app starts and loads
    the 17 prepared synthetic cases with their page images. The built-in reader matches pypdf word for word on the 17
    benchmark dossiers, and decodes Group 3 and Group 4 fax pages bit for bit as libtiff encodes them. On the 11
    Hackathon dossiers (750 pages, compared on the DSW without any text leaving it) it finds the same text pages as
    pypdf, with letter recall 1.0 on ten dossiers and 0.997 on the eleventh, and takes every scanned page's image
    except one JPEG 2000 page.
- **Gateway limits:** some gateways reject a temperature and forced tool choice. With `CASEPATH_MODEL_API=messages` and `CASEPATH_MODEL_FORCED_TOOLS=false`, each turn offers only the tool that must be called and says so. A structured answer is checked and asked for once more when it is missing or malformed.
- **Cost guard:** `CASEPATH_RUN_TOKEN_BUDGET` caps the tokens one run may use over reading, routing and the agents: input not read from the prompt cache, and output; the run stops with that reason when it is spent. The pilot sets 3,000,000.
- **Prompt caching:** an agent's turns mark the system prompt, the tools and the end of the conversation, so the next turn reads them from the cache. A one-off structured answer marks only the system prompt and tools. Each call's usage in the run record gives `input_tokens` (all input, cached or not), `cached_tokens` (read from the cache) and `cache_write_tokens` (written to it). The marks are dropped only when the gateway refuses them and the same request without them succeeds.
- **Imports:** case files placed in the volume's `incoming/` folder are listed on the Cases page. One click turns each into a case without the file passing through the browser, which suits large dossiers.
- **Checked here:**
  - the packaged folder starts as Databricks starts it: 401 without sign-in, 403 outside the pilot group, the pilot user sees the synthetic cases;
  - a volume round trip restores a store with its files;
  - the model translation works against a simulated endpoint.
- **Not yet checked:** the real workspace, its model and its volume.

## Before an operated deployment

1. Confirm the gateway's token claims and the access role's exact name, then set the identity variables.
2. Grant the service's identity access to the model deployment, and set the credential and, if one is used, the gateway host.
3. Build the queue consumer around `core.prepare` and the blob reader. Run `tests/test_core.py`'s job through it.
4. Point the benchmark evaluator at the deployment: `python -m casepath_internal.evaluate run <suite> --catalogue <dir> --out <dir> --url <base url> --identity-header <header>` (the identity value in `CASEPATH_EVAL_IDENTITY`). Compare it with the workspace's results using `evaluate compare`. Any regression is listed by case and check.
