# Deploying CasePath beyond the development workspace

CasePath runs end to end on a single development workspace today. This document describes how the same code moves to an operated environment, where:

- a gateway signs people in;
- runs can outlast a request timeout;
- cases live in a managed database.

Every piece that differs between the two environments sits behind one of the boundaries below and is chosen by configuration. Tests exercise each boundary, so the application that passes the benchmark on the workspace is the application that is deployed.

## The two halves

**Agent core** (`casepath/agents/core.py`, with `casepath/agents/team.py`, `casepath/read/reading.py`, `casepath/process/casegraph.py` and `casepath/process/workflows.py`) is everything that uses a model. It is stateless: a JSON job goes in and a JSON outcome comes out.

- `prepare(job, model, blobs, on_event, on_extraction)` reads scanned pages, routes the case, runs the five agents and works out what the run teaches. It can take many minutes.
- `recheck(job, prior, documents, model, on_event)` checks only the document needs a process edit added.
- `evaluate(workflow, knowledge, edits, result, case_id)` gives the case's own process and where the case stands. It uses no model, so it can answer synchronously.

The job and outcome formats (`casepath.agent-job/1`, `casepath.agent-outcome/1`) are specified in `casepath/agents/core.py`. `tests/test_core.py` runs a job built from plain JSON with no store at all, as a queue worker would. `python -m casepath job prepare <job.json> --blobs <dir>` does the same from the command line.

**Case service** (`casepath/web/app.py`, `casepath/web/store.py`, `casepath/agents/runner.py`, `casepath/process/knowledge.py`) owns cases, files, runs, events, edits, Knowledge, feedback, deletion and sign-in. It builds jobs (`RunService.job`) and persists outcomes (`RunService.save`):

- each file's reading as soon as it is done;
- the result;
- each applied Knowledge item's statistics, on its current version;
- the result checker's proposals, as candidates.

The case API is fixed in `docs/contracts/case-api.openapi.json`. `tests/test_app.py` fails when the code and the saved contract diverge (`python -m casepath contract --write` updates it). The browser workspace, the batch tool and the benchmark evaluator use only this API, so a reimplementation of the case service that honours the contract keeps all three working.

## Boundaries and how each is chosen

| Concern | Development workspace | Operated environment | What changes |
|---|---|---|---|
| Sign-in | `CASEPATH_DEV_USER` (one person) | Gateway header: `CASEPATH_IDENTITY_HEADER`, `CASEPATH_IDENTITY_FORMAT=jwt`, the user and roles claims, and `CASEPATH_REQUIRED_ROLE` (403 without it) | Configuration |
| Model credential | `CASEPATH_AZURE_CREDENTIAL=cli` (the person's `az` sign-in) | `managed_identity` or `workload_identity` | Configuration |
| Model endpoint | The Azure OpenAI resource | The resource, or a gateway host named in `CASEPATH_MODEL_GATEWAY_HOSTS` (it may carry a path) | Configuration |
| Model deployment | `CASEPATH_AZURE_OPENAI_DEPLOYMENT`, optional reading deployment and dated API version | Same | Configuration |
| The insurer (house) | `CASEPATH_HOUSE` unset: Protekta, the built-in profile | A shipped house or the path of a profile file (docs/HOUSE.md) | Configuration |
| Agents' organisation and writing language | `CASEPATH_ORGANISATION` (default: the house's name, Protekta), `CASEPATH_WRITING_LANGUAGE` (default: the case files' language, usually German, Swiss spelling) | Same | Configuration |
| Long runs | Worker threads in the case service (`RunService`) | A queue consumer that calls `core.prepare` with the same job; events and the outcome go back on the queue, and large outcomes go through blob storage | One adapter around `core.prepare` |
| File bytes | `core.StoreBlobs` (store files) | A blob-storage reader with the same `read(file)` method (`core.DirectoryBlobs` shows the shape) | One small adapter |
| Persistence | SQLite plus files (`casepath/web/store.py`) | The case service's database, behind the same API contract | The case service, not the agents |
| Workflow catalogue | JSON files in `CASEPATH_WORKFLOW_CATALOGUE` | Same files, shipped with the release | None |
| Retention | `python -m casepath purge --older-than-days N` | The same rule in the case service's scheduled job | Schedule |
| Deletion | `DELETE /api/cases/{id}` (its owner, the deputy or a reviewer) removes the case and everything derived from it, and keeps a content-free deletion record. The volume copy follows at its next write: the files' bytes are removed there, the database is copied without its freed pages, and bytes no case refers to are swept at start | Same contract | None |
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

- **The one diagnostic run on a real later arrival** has two forms that do the same thing step for step and give the same receipt (`casepath.diagnose/1`: ids, counts and enums only). `deploy/databricks/rehearse.py` is a notebook cell and needs an identity the app's sign-in admits for notebook calls. Where the sign-in admits only a person's browser session, `deploy/databricks/rehearse_console.js` is pasted into the console of the pilot's own page by the signed-in person: it names no address and no identity, calls only that page's origin, and does nothing without its phrase (`hashes D11` to read the plan, then the phrase the plan prints). A tab can be lost: while a run's receipt reads «started», the same phrase takes that run up where it stands, never starting a preparation or an update the app already holds. `tests/test_rehearsal_receipt.py` runs both forms against one stand-in and requires the same requests and the same receipt.
- **What a preparation costs, measured once** (the diagnostic's receipt, 2026-11-16, build source `edd26364c81a`): one full preparation of a 21-page file made 28 model calls in 363 s and used 245,223 input tokens not read from the cache and 45,754 output tokens (660,650 more input tokens were read from the cache). Per agent, not cached: the claim reader 72,725 in 14 calls, the source checker 67,543 in 3 calls with nothing read from the cache, the document finder 59,418 in 8, the result checker 32,146 in 2, the router 13,391 in 1. The estimate made before the run, 75 to 110 thousand, came from the run sizes of an earlier build and was wrong by a factor of two to three: an estimate is to be made from a run of the build it is for. The diagnostic's stop threshold (200,000) is read after the preparation and stops what follows; it does not bound the preparation. What bounds a run while it runs is `CASEPATH_RUN_TOKEN_BUDGET` (3,000,000 here) and, for an update, `CASEPATH_UPDATE_TOKEN_BUDGET`.
- **What an update costs, measured once** (the same diagnostic, continued from its kept base case): the two replies of that file, 5 pages, imported as one arrival; one update of 8 model calls in 35 s, 37,578 input tokens not from the cache and 4,857 output (the reader 3 calls, the document finder 4, the source checker 1; no routing, no result checker). The estimate made before, 25 to 45 thousand, held. One file, one run: a measure, not a rate.
- **What that run showed, in codes** (one dossier; no validation). The import, the refusal of a file given twice, the bounded update, the two entries recorded, two requests closed and the next action being the kind the handler took all worked on real text through the model. The prepared assessment did not meet the bar: 5 gaps left to the handler; of 6 questions of the customer 1 answered, 3 open because the reader gave them no key point and no keyword proposed one («keine Regel des Gebiets»), 2 held because their key points applied but no intent of the area matched («Absicht der Frage unklar»); and by the replay's matching it did not ask what the handler's own letter asked, while listing four other things.
- **Two leads from that run, neither measured.** (1) Where the tokens of a preparation go: every agent reads the case's text once at full price, because a cache is shared only by calls that open the same way. The source checker's three one-off calls read nothing from the cache (the second reading of the deciding facts sends the whole text of a small case again), the result checker 32 thousand, the router 13. The trials `second_reading_unquoted`, `result_without_files` and `finder_stage_only` (`CASEPATH_SPEED_TRIALS`) were written for exactly these and have never been measured on a real file. (2) What a question asks: the area matches it by word stems, and real wording missed them for two of three tagged questions. Under the trial `reader_intents` the reader names the intent by its meaning (`process/live.py`, `areas/live/absichten.json`), kept only where it belongs to a key point the question is tagged with; a negation, a failing point or a missing tag still hold the question for the handler. Off by default; without it the reader's contract is unchanged. Both need one measured run each, on the owner's approval, before anything is switched on.
- **Continuing a diagnostic that stopped at the threshold** (`continue D11 <tree hash> <labels sha256> <plan>`, the console form only): where the run stopped because its preparation passed the threshold and its base case was kept, this phrase makes the arrival, the one update, the decisions and the reading on that base case, without a second preparation. It is a decision of its own with its own approval; nothing else is ever continued.
- **Update on arrival** (`CASEPATH_AUTO_UPDATE`, the deploy cell's `AUTO_UPDATE`): off. With it on, files added to a prepared case are read by themselves, a bounded update (unread files of at most `CASEPATH_AUTO_UPDATE_MAX_PAGES` pages, default 20); it spends tokens without a click. It is switched on, in the deploy cell only, at the first deployment after the owner has reviewed the diagnostic run on a real later arrival and said so.
- **Reading in English** (`CASEPATH_TRANSLATE`): `memory` by default: what the shipped translation memory knows (the product's wording, the catalogues, the examples) is shown in English, free; the content of a real case stays as written. With `model`, the deployment's model translates the rest in the background, within `CASEPATH_TRANSLATE_TOKENS` a day (default 300,000); it spends tokens when a reader of English opens a case. `off` offers no translation. Switched to `model`, in the deploy cell only, when the owner says so.
- **Sign-in:** Databricks signs people in and passes their e-mail in `X-Forwarded-Email`. `CASEPATH_ALLOWED_USERS` admits only the named pilot group. App permissions in Databricks should match that list. `CASEPATH_REVIEWERS` names who may mark the legal content, release shared rules (Wissen: «Nachspielen», «Freigeben», «Zurückziehen»), read the evaluation and the review export, and delete a colleague's case; the server checks it on each of these routes. Empty, nobody may in a deployment with sign-in (the deploy cell's `REVIEWERS` fills it; docs/AREAS.md, Review by a jurist). `CASEPATH_CASE_ACCESS` is `team` (every member of the group opens every case) or `owner` (a case opens for its owner, the deputy and the reviewers; a colleague sees its number and owner in the list and opens it with «Vertretung übernehmen», which the case's log records); examples are open to everyone. A case is deleted by its owner, the deputy or a reviewer.
- **Model:** `CASEPATH_MODEL_PROVIDER=databricks` calls a model in the workspace, such as one from its gateway, through its OpenAI-compatible chat API. The app signs in as its own service principal. `casepath/agents/chat_model.py` translates the agents' messages, tool calls, structured answers and page images, so nothing else changes.
- **Storage:** the app's own disk does not survive a restart. With `CASEPATH_VOLUME` naming a Unity Catalog volume, the case store is restored from the volume at start and copied there every 30 seconds and at shutdown (`casepath/web/mirror.py`). One app instance writes a volume.
- **Packages:** the app needs nothing beyond the platform's web packages.
  - **Prepared cases:** where the PDF libraries are, `python -m casepath prepare <files> --out <dir>` makes a prepared case: the original files, the extracted text and images of the scanned pages, made without a model.
  - **Importing them:** the app imports prepared cases from the volume's `incoming/` folder. The synthetic cases ship prepared.
  - **Loose files without extra packages:** uploaded or imported files are read by CasePath itself when the PDF
    libraries are missing (`casepath/read/pdfread.py`, `casepath/read/ccitt.py`, `casepath/read/msg.py`, standard library only):
    - a PDF's text layer, including subset and CID fonts with their Unicode maps and compressed object streams;
    - each scanned page's own image: JPEG as it is, bitmaps (also inline, CMYK or 16-bit) and CCITT Group 3/4 fax
      scans as PNG. A page drawn only with vector paths (text as outlines) is drawn as a PNG (`casepath/read/raster.py`). JPEG 2000
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
    pypdf, with letter recall 1.0 on ten dossiers and 0.997 on the eleventh. It takes every scanned page's image except
    one JPEG 2000 page, and draws all 14 pages made only of vector paths. Three pages hold nothing to read.
- **Gateway limits:** some gateways reject a temperature and forced tool choice. With `CASEPATH_MODEL_API=messages` and `CASEPATH_MODEL_FORCED_TOOLS=false`, each turn offers only the tool that must be called and says so. A structured answer is checked and asked for once more when it is missing or malformed.
- **Cost guard:** `CASEPATH_RUN_TOKEN_BUDGET` caps the tokens one run may use over reading, routing and the agents: input not read from the prompt cache, and output; the run stops with that reason when it is spent. The pilot sets 3,000,000.
- **Prompt caching:** an agent's turns mark the system prompt, the tools and the end of the conversation, so the next turn reads them from the cache. A one-off structured answer marks only the system prompt and tools. Each call's usage in the run record gives `input_tokens` (all input, cached or not), `cached_tokens` (read from the cache) and `cache_write_tokens` (written to it). The marks are dropped only when the gateway refuses them and the same request without them succeeds.
- **Imports:** case files placed in the volume's `incoming/` folder are listed on the Cases page. One click turns each into a case without the file passing through the browser, which suits large dossiers.
- **Checked here:**
  - the packaged folder starts as Databricks starts it: 401 without sign-in, 403 outside the pilot group, the pilot user sees the synthetic cases;
  - a volume round trip restores a store with its files;
  - the model translation works against a simulated endpoint.
  - `make package` is repeatable: the synthetic PDFs carry fixed dates and a fixed document id, and their scan noise is
    seeded, so a second build gives the same tree hash (`tests/test_synthetic.py`).
  - On the DSW, 2 tests fail for reasons of that environment, not of the code: the font tests (its virtual
    environment's pip cannot install the fonts) and `FaxTests` (it has Pillow 9.2). The same 2 fail there on older
    builds. They are not skipped; they pass where the packages are current.
- **Checked on the pilot:** the workspace, its gateway model and its volume (docs/history/UI_RECEIPT.md, «Real model pass»). **Not yet
  checked there:** what was added after the build the pilot runs (approval, Versandpaket and dispatch, the update on arrival, deletion
  reaching the volume, the reviewer and case-access checks); these are proven by the unit tests against a scripted reader and a fake
  Files API only.

## Before an operated deployment

1. Confirm the gateway's token claims and the access role's exact name, then set the identity variables.
2. Grant the service's identity access to the model deployment, and set the credential and, if one is used, the gateway host.
3. Build the queue consumer around `core.prepare` and the blob reader. Run `tests/test_core.py`'s job through it.
4. Point the benchmark evaluator at the deployment: `python -m casepath evaluate run <suite> --catalogue <dir> --out <dir> --url <base url> --identity-header <header>` (the identity value in `CASEPATH_EVAL_IDENTITY`). Compare it with the workspace's results using `evaluate compare`. Any regression is listed by case and check.

## The case list stays fast

A row of the list is worked out from the case's whole state, which costs as much as opening the case. With a hundred cases that was 5 to 11 seconds per list on the pilot, and the list is asked for at every return to it (and once more by «Heute»). The server now keeps each row until something it can change with changes: the case, its events, files, runs, edits or saved letter text, the Knowledge base, the jurists' marks, or the day (`store.row_versions`, `case_rows` in `web/app.py`); never longer than ten minutes, so a dependency the key should ever miss corrects itself. The page shows the list at once as it was when the reader comes back from a case in which nothing was written, and brings it up to date behind; after anything was written it asks anew first. Nothing is stored outside the process: a restart works every row out once.

## Reading in English: translated once, for the cases that need it

A text is translated at most once. What the shipped memory does not know and the model translated is kept in the store
(table `translations`, removed with its case) and serves every later reader, also after the model is switched off again.

- `CASEPATH_TRANSLATE=model` allows the model; `CASEPATH_TRANSLATE_AREAS` names the legal areas it may translate for
  (parts of an area's id, comma-separated, e.g. `mietmangel`). Empty means every case. A case outside the named areas
  is never sent to the model; it is shown with what the memory and the store already hold.
- **Ahead of the readers, once** (reviewers only):
  `POST /api/translate/cases {"lang":"en"}` counts and costs nothing: the cases in scope (the study's cases first), the
  lines not yet known, and about how many tokens they would take. The same call with `"dry_run": false` queues them
  within the day's budget (`CASEPATH_TRANSLATE_TOKENS`); `GET /api/translate/cases` says how many are still waiting and
  what was spent. Running it again translates only what is new.
- **What it costs, measured once** (the pilot, 18 November 2026): 12 cases of one legal area held 2,811 lines not yet
  known; the model took about 144 tokens a line (in and out together, batches of 40). The count before a run is set
  against that figure. A run that reaches the day's ceiling stops by itself with nothing lost: what is translated is
  kept, and the same call on a later day (or with a higher `CASEPATH_TRANSLATE_TOKENS`) takes only what is left.
- Afterwards the deployment can go back to `CASEPATH_TRANSLATE=memory`: nothing more is spent and everything translated
  stays available. For cases that arrive later, run the one call again.
