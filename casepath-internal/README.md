# CasePath, internal

A fresh CasePath for running inside Mobiliar's own Azure. It keeps the product's core:
- reading case files;
- following a source-grounded workflow;
- checking documents against exact sentences;
- giving an answer with its proof;
- drafting a reply that is never sent;
- learning reusable Knowledge.

It leaves the public demonstration's hosting, ledger and provider machinery behind.

This folder contains no Mobiliar content. Workflows built from Mobiliar's process diagrams, the case files and the deployment settings live inside Mobiliar. [`docs/COORDINATION.md`](docs/COORDINATION.md) describes how the cloud build session and the Mac bridge share the work.

## What is here

| Module | Does |
| --- | --- |
| `workflows.py` | Workflow catalogue format and validation. Every fact, step, branch and document need names its source. Routing selects a workflow, asks for missing facts, or says the case is unmapped. Evaluation finds the current step and the case's document checklist, using three-valued logic. |
| `drawio.py` | Turns a draw.io process diagram into a draft workflow. Each step and branch is traced to its diagram cell, and ambiguities become open questions. |
| `extract.py`, `evidence.py` | Read PDF, e-mail, Word and text files, and count pages without a text layer. Locate quotes word for word, and search. |
| `azure_model.py`, `config.py` | Azure OpenAI client with Entra sign-in and the exact deployment name. It uses the Responses API with tools (`store: false`), and chat completions for deployments without Responses. It refuses any endpoint that is not an Azure OpenAI resource. |
| `agent.py` | The tool loop behind the five roles: claim reader, process builder, document finder, source checker, result checker. Only located quotes count, and an independent pass verifies them. |
| `store.py`, `runner.py`, `app.py` | Fresh case store, background runs with honest statuses, and the API. The API serves only with a configured sign-in. |
| `scorecard.py` | Content-free run scorecards, guarded against free text, for results that may leave Mobiliar. |
| `deploy/workspace/` | One script for setup, start, update and checks on the development workspace, and a private env template. |

## Run the tests

```sh
cd casepath-internal
python3 -m unittest discover -s tests -t .
```

The tests use a synthetic workflow and a scripted model. They make no network calls.

## Run it on the development workspace

1. Clone the repository on the workspace.
2. Copy `deploy/workspace/env.example` to `~/.casepath/env` and fill it in there.
3. Put the workflow catalogue (JSON) in `$CASEPATH_WORKFLOW_CATALOGUE`.
4. Run `az login --use-device-code` once.
5. Run:
   ```sh
   deploy/workspace/casepath.sh setup
   deploy/workspace/casepath.sh check-model   # one synthetic call, with approval
   deploy/workspace/casepath.sh start
   ```

To turn a process diagram into a draft workflow on the workspace:

```sh
~/.casepath/venv/bin/python -m casepath_internal.drawio case_mold.drawio --version <diagram date> > "$CASEPATH_WORKFLOW_CATALOGUE/case_mold.json"
```

A draft gets its routing condition and document needs from a reviewer before it routes cases automatically. Until then, a case worker selects it by hand.

## Not done yet

- The case-worker interface. The next step is to port the product's workspace UI to this API.
- Page images for scanned PDFs (vision input), and photo reading.
- Comparing results with reviewer-labelled references on the Hackathon cases, beyond the structural scorecard.
- Operated hosting (frontend, business service, agent service).
