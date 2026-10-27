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
| `reading.py` | Real dossiers: scanned pages are read from their page images (in parallel; a page the model cannot read stays listed and is tried again on the next run), and each file is split into its documents with a page range, date, sender and a summary. In a dossier of hundreds of pages, the agents use these summaries to choose what to read. |
| `azure_model.py`, `config.py` | Azure OpenAI client with Entra sign-in and the exact deployment name. It uses the Responses API with tools (`store: false`), and chat completions for deployments without Responses. It refuses any endpoint that is not an Azure OpenAI resource. |
| `agents.py` | The agent team on one deployment. A lead delegates to the claim reader, process builder, document finder, source checker and result checker; each has its own instructions, tools and context. Only located quotes count, and the source checker verifies them independently. |
| `casegraph.py` | A case's own process: workflow, applicable Knowledge and validated edits. Edits re-evaluate the case, show a before-and-after diff, and can be undone. |
| `knowledge.py` | Knowledge items with versions, evidence and use statistics. Candidates are applied as suggestions, a person activates them, and later cases refine or contradict them. |
| `synthetic.py` | Synthetic cases made inside Mobiliar: a profile of a real dossier from its documents, a planned case written document by document, copy guard, realistic PDF rendering (including scans), loading into the store through the same reading as real cases, a blind judge on read text and on page images, and scoring CasePath's results against each synthetic case's truth. |
| `store.py`, `runner.py`, `app.py` | Fresh case store, background runs with honest statuses, and the API. The API serves only with a configured sign-in. |
| `ui/` | The case worker's workspace on the API, in German (`?lang=en` switches to English): the five agents' live work, the case's process with editable decisions, document checklist, case summary, deadlines, reply draft (also as Word), the contents of each dossier, and Knowledge. |
| `batch.py`, `mining.py` | Import a folder of case PDFs into a running CasePath and prepare them one case at a time, printing content-free lines. Reconstruct each real case's course and the pattern across cases. |
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

- A completed run on the internal model, first on the made-up example and then on the Hackathon cases (in Azure Cloud Shell).
- Running the synthetic pipeline on the internal model.
- Comparing results with reviewer-labelled references on the Hackathon cases, beyond the structural scorecard.
- Operated hosting (frontend, business service, agent service).
