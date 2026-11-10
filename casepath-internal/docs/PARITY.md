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
- **Commits.** The internal copy is kept as separate commits on another host. Their hashes and messages differ from the commits here, so equal hashes cannot be used to show equal code. Use the tree hash instead.
- **Model.** The internal deployment uses an internal model. The research runs use a public model through the same chat connector. This is configuration.
- **Not established from outside:**
  - whether any code change exists only in the internal copy;
  - which commit here the deployed internal build corresponds to.

  Running `parity` in both places settles both points.

## Behaviour changes that both deployments must approve

These changes on branch `claude/casepath-internal-paper-sync-20261110` alter behaviour even for workflows that use none of the new optional fields:

- **Exact deferral.** With a fact open, documents and steps after the open question are no longer dropped:
  - those needed under every answer are listed as needed;
  - those needed under some answers are listed as depending on the question that decides them.

  With every fact known, evaluation is unchanged; tests assert this for all assignments.
- **Wider second reading.** Every fact a step or a document condition uses is read twice. This is the existing rule, now covered by a test; no code changed.

These changes change nothing unless a workflow or the configuration uses them:
- presumptions (`presumptions` in a workflow);
- sufficiency checks (`must_show` on a document need);
- the configurable organisation and writing language (the defaults keep the earlier text).
