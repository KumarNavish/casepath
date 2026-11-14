# CasePath

Agents prepare a legal-protection case from its files. A person decides.

![A case being prepared: the process forms from the files, the agent reads the quote it cites, the document list grows](docs/img/live.png)

```mermaid
flowchart LR
  files["Files<br/>PDF · scans · e-mail · Outlook · Word"] --> read["read/<br/>text · scanned pages · documents"]
  read --> route{{"routing<br/>picks the workflow"}}
  catalogue[("catalogue/<br/>Protekta processes")] --> route
  route --> brief["claim reader<br/>briefs the case"] --> process["process builder<br/>the case's own process"]
  law["the applicable law"] --> process
  knowledge[("Knowledge<br/>activated by a person")] --> process
  process --> facts["claim reader<br/>facts, with quotes"] --> docs["document finder<br/>needs ↔ files"]
  docs --> check["source checker<br/>every quote"] --> result["result checker<br/>answer · reply draft"]
  result -. proposes .-> knowledge
  result --> out["process · checklist · deadlines<br/>case report (.docx)"]
```

Each fact and each document rests on a quote found word for word in the file, and the source checker checks every one. A document the law requires shows its article.

![The document checklist: each need with its purpose, its status, the quote that shows it, and where the need came from](docs/img/documents.png)

## Run

```sh
make setup      # .venv with the dependencies
make test       # every test; no network, no model
make preview    # http://127.0.0.1:8790: synthetic cases, scripted model
```

## Ship (Databricks App `casepath-pilot`)

```sh
make package    # → build/casepath-app/
```

Upload `build/casepath-app/` to the workspace. Fill in the three `FILL-IN`s in its `app.yaml` there, never in Git, then deploy. `GET /api/health` answers `"status": "ok"`. Details: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Map

```
casepath/              python -m casepath <command>   (no command: the list)
  read/                files → text, page images, documents, quotes (PDF, fax and Outlook readers on the standard library)
  agents/              lead, five agents and their plan (team.py); one job in, one outcome out (core.py); model clients
  process/             workflows, each case's own process, Knowledge; areas/: the handler's backbone and one module per legal area (docs/AREAS.md)
  web/                 API (app.py), case store, sign-in, volume, case report, workspace (ui/)
  quality/             benchmark, evaluator, synthetic cases, content-free scorecards
  config.py            every setting, from the environment
catalogue/             Protekta's processes as workflows (JSON)          internal copy
benchmark/             synthetic cases with known answers                internal copy
deploy/                databricks/ · workspace/ (DSW) · preview/ · cloudshell/ · Dockerfile at the root
docs/                  HANDLER_BAR.md (what done means) · DEPLOYMENT.md · contracts/ (case API) · history/
tests/
.gitlab-ci.yml         the DSW's pipeline (+ mobi.yaml, renovate.json)   internal copy
```

## Rules

- A fact counts only with a quote found word for word in the file.
- Case content stays inside Mobiliar. Anything that leaves is a content-free count.
- Knowledge reaches a case only after a person activates it; each use names its version.
- A run stops at its token budget (`CASEPATH_RUN_TOKEN_BUDGET`) and says so.
- Text in a file that addresses an AI is flagged, never followed.
