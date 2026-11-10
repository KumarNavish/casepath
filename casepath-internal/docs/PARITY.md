# Parity: one CasePath, two deployments

The same CasePath code runs in two places:
- inside the insurer's environment, on real cases;
- outside it, on synthetic cases and public rules, for development and research.

The only permitted difference between them is proprietary data. This page says what is code and what is data or configuration, how to check that two deployments run the same code, and what is known to differ today.

## Shared code

Everything under `casepath/` is shared:

| Area | Modules |
|---|---|
| The agents and their instructions | `agents/team.py` |
| Evaluation, deferral and presumptions | `process/workflows.py`, `process/casegraph.py` |
| Evidence checks | `read/evidence.py` |
| Knowledge | `process/knowledge.py` |
| Reading | `read/` |
| Routing and the job contract | `agents/core.py` |
| Run service | `agents/runner.py` |
| API and interface | `web/` |
| Model connectors | `agents/azure_model.py`, `agents/chat_model.py`, `agents/anthropic_model.py` |

No module may hold behaviour that only one deployment uses. A difference in behaviour must come from the data or the configuration below.

## Data and configuration, supplied from outside the package

| What | Where it comes from |
|---|---|
| Workflow catalogue: case types, steps, facts, document needs, presumptions, what a need `must_show` | `CASEPATH_WORKFLOW_CATALOGUE`, a folder of `casepath.workflow/1` files |
| Knowledge items | The case store (`CASEPATH_DATA_DIR`, optionally mirrored to a volume) |
| Case files | Uploads, volume import or the batch tool |
| Model endpoint, provider, model name, API dialect, reading model | `CASEPATH_MODEL_PROVIDER`, `CASEPATH_MODEL_ENDPOINT` / `CASEPATH_AZURE_OPENAI_ENDPOINT`, `CASEPATH_MODEL` / `CASEPATH_AZURE_OPENAI_DEPLOYMENT`, `CASEPATH_MODEL_API`, `CASEPATH_READING_MODEL`, gateway hosts |
| Sign-in | Identity header or development user, required role, allowed users |
| Organisation the agents work for, language they write in | `CASEPATH_ORGANISATION`, `CASEPATH_WRITING_LANGUAGE`. The defaults are the internal deployment's. |
| Interface language | Browser setting (`?lang=`). German is the default. |
| Limits | Run workers, reading workers, page image size, token budget |

## Checking that two deployments run the same code

Run the same command in each deployment and compare `source_tree_sha256`:

```
python -m casepath parity --catalogue "$CASEPATH_WORKFLOW_CATALOGUE"
```

The output names:
- the hash of every file of the imported package (caches excluded);
- the git commit, when the package sits in a checkout;
- the hash of each workflow file and of each Knowledge item supplied;
- the model provider and name;
- every setting that differs from the default.

Equal tree hashes mean the same code. The workflow and Knowledge hashes then show exactly which data differs.

Neither the manifest nor this page contains case content or credentials.

## What differs today, as far as can be established from outside

- **Workflow catalogue.** The internal copy carries the insurer's own process catalogue and a set of synthetic benchmark cases (`deploy/databricks/package.sh` copies `catalogue/` and `benchmark/` when they are present). Neither is in this repository. That is proprietary data and an expected difference.
- **Commits.** The internal copy is kept as separate commits on another host. Their hashes and messages differ from the commits here, so commit hashes cannot show that the code is equal. Use the tree hash instead.
- **Model.** This is the one declared difference besides proprietary data, and it is configuration, not code:
  - the internal deployment runs on the model of the workspace's gateway, named in its deployment settings;
  - the external research deployment runs on a separately configured model, named in its run manifests;
  - both use the same connectors, selected by `CASEPATH_MODEL_PROVIDER` and `CASEPATH_MODEL_API`, with the model named in `CASEPATH_MODEL` or `CASEPATH_AZURE_OPENAI_DEPLOYMENT`.

  No code path depends on the model's name, with one exception: for an Azure OpenAI resource, `CASEPATH_MODEL_REASONING` defaults from the deployment name (on for names containing "gpt-5" or "-o"), and setting it explicitly overrides the default.
- **Not established from outside:**
  - whether any code change exists only in the internal copy;
  - which commit here the deployed internal build corresponds to.

  Running `parity` in both places settles both points.

## Behaviour changes that both deployments must approve

These changes on the paper-sync branch of 10.11.2026 alter behaviour even for workflows that use none of the new optional fields:

- **Exact deferral.** With a fact open, documents and steps after the open question are no longer dropped:
  - those needed under every answer are listed as needed;
  - those needed under some answers are listed as depending on the question that decides them.

  With every fact known, evaluation is unchanged; tests assert this for all assignments.
- **Wider second reading.** Every fact a step or a document condition uses is read twice. This is the existing rule, now covered by a test; no code changed.

The changes below, made after those, also alter behaviour for existing workflows:

- **Routing.** When the routing facts leave exactly one workflow open and no other workflow or fallback can apply, that workflow is prepared and its routing facts are recorded as presumed from routing. Before, such a case was handed over. A catalogue without routing facts now prepares its fallback workflow.
- **Routed presumption.** The defining event of the routed case type (`applies: "routed"`) is presumed also when the files mention it but leave it open; it yields to an established value or to two conflicting readings. Presumptions for unstated facts are unchanged.
- **Documents.** A message or another document that only mentions a needed document no longer meets the need (`mentioned_only`; the need stays missing). Quotes for a present document count only from the files named for it. The source checker is asked whether the file is the document itself, and checks each `must_show` item on its own; an item it does not find shown makes the document unusable. The finder names `must_show` items exactly as listed.
- **Facts.** In a case of up to 40,000 characters the claim reader answers every fact of the process in one structured reading (established, unknown with a quote, or unknown without). The second reading of every deciding fact answers in the same form. A value counts only where both readings give it; a value found by one reading only leaves the fact unknown. A longer dossier is still read by the agent, with the same agreement rule.
- **Fact readings, second form.** Both readings judge every condition true, false or unresolved, with one exact quotation found in any file; the conditions come with the task and the case files are the message; readings ask for low effort. Unchanged: a value counts only where both readings give it.
- **Deciding facts.** A fact a condition uses, which both readings give with an exact quote, is no longer removed when the source checker doubts it (the doubt is a flag), and no single agent can record a deciding fact after the two readings.
- **Suggestions under an open question.** A suggested need keeps its label while the question that decides it is open, instead of becoming a hold.
- **Reasoning effort on chat endpoints** (configuration, off by default): with `CASEPATH_MODEL_REASONING` on, a chat-completions endpoint receives each call's effort as the model's reasoning effort and no temperature. Where an Azure deployment already sends reasoning effort, the readings now go at low effort instead of the team's effort.
- **Process-builder additions** (the last commit, which can be dropped on its own; the owner's decision is pending): a need, question or step the process builder adds stays a suggestion, shown with its stated basis (statute article, quote or Knowledge item), until the workflow, Knowledge or a case handler confirms it. It is no longer required because it names a statute article, and it does not count as a missing document.
- **Turn limits.** An agent that reaches its turn limit ends with what it recorded; the run completes, evaluates the checklist and names the limit in its warnings, instead of failing.

These changes change nothing unless a workflow or the configuration uses them:
- presumptions (`presumptions` in a workflow);
- sufficiency checks (`must_show` on a document need);
- the configurable organisation and writing language (the defaults keep the earlier text).
