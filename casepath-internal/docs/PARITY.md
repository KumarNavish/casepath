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

- **Routing.**
  - When the routing facts leave exactly one workflow open and no other workflow or fallback can apply, that workflow is prepared. A routing fact is then recorded as presumed from routing only with a value its condition names uniquely (`is`, or `in` with one value); any other stays open. Before, such a case was handed over.
  - That workflow is not taken when routing names another matter in the files (`other_topic`) or gives a routing value whose quotation is not found: the case is handed over.
  - A catalogue without routing facts now prepares its fallback workflow.
  - `needs_facts` lists fallback workflows among its candidates.
  - Routing accepts up to four `other_topic` values and keeps the first quoted one (one was allowed, and two failed the run).
  - A routing quotation not found in the files is asked for once more before routing decides without it.
- **Presumptions.**
  - The defining event of the routed case type (`applies: "routed"`) is presumed also when the files mention it but leave it open; it yields to an established value or to two conflicting readings.
  - No presumption (routed, unstated or from routing) applies to a fact one of the two readings gave another value with an admitted quotation: the fact stays open for a person. A reading that found the presumed value does not block it.
  - A deciding fact counts as raised by the files (so that an unstated presumption does not apply) only when both readings quote a passage that raises it.
- **Documents.**
  - A message or another document that only mentions a needed document no longer meets the need (`mentioned_only`; the need stays missing).
  - Quotes for a present document count only from the files named for it. The source checker is asked whether the file is the document itself, and checks each `must_show` item on its own; an item it does not find shown makes the document unusable. The finder names `must_show` items exactly as listed.
  - A document counts as present only when a second, independent judgment agrees, naming the same file and quoting each `must_show` item; otherwise it stays requested as unusable. This adds one model call per case with a document found present.
  - When the finder stops before it finishes, needs it never recorded are unchecked, not missing.
  - A later record of a need replaces the earlier one, as an event (`document.changed`) with the status it replaced.
- **Facts.** (The earlier "one structured reading" form is replaced by this one.)
  - In a case of up to 40,000 characters both readings judge every condition true, false or unresolved, with one exact quotation found in any file; the conditions come with the task and the case files are the message. A value counts only where both readings give it.
  - Readings ask for low effort on every deployment, whatever the configured effort. A verdict whose quotation is not found is asked for once more.
  - A condition a reading answers twice with different judgments is unresolved. A failed reading call leaves its conditions unresolved and is a warning (`reading_failed`), not a failed run.
  - A value established at routing and a different value from a reading conflict; a person decides.
  - Over 40,000 characters, the claim reader agent records the facts and the second reading sees keyword passages only, so deciding facts will more often stay open.
- **Deciding facts.**
  - A fact a condition uses, which both readings give with an exact quote, is no longer removed when the source checker doubts it (the doubt is a `flag`). Rejected deciding facts are not retried, and no single agent can record a deciding fact after the two readings.
  - A case worker cannot set a fact's value today: no such path exists in the product. A case worker can still change what a fact requires through process edits (for example `set_required_when`, `remove_document`), also for a locked fact.
- **Suggestions under an open question.** A suggested need keeps its label while the question that decides it is open, instead of becoming a hold.
- **Reasoning effort on chat endpoints.** With `CASEPATH_MODEL_REASONING` on, a chat-completions endpoint receives each call's effort as `reasoning_effort` and no temperature. It is off only by the code's default: `deploy/workspace/env.example` and `deploy/cloudshell/start.sh` set it to true. Both configure an Azure OpenAI resource, for which the flag already sent reasoning effort; an environment that keeps the flag and switches to a chat-completions endpoint now sends it too. The request keeps `max_tokens`; the outside endpoint used for research accepts that with reasoning effort. Before turning it on inside, check that the gateway accepts `reasoning_effort` with `max_tokens` (OpenAI's own reasoning endpoints expect `max_completion_tokens`, as the Azure connector sends). Where an Azure deployment already sends reasoning effort, the readings now go at low effort instead of the team's effort.
- **Process-builder additions** (the owner's decision is pending; the commit can be dropped on its own): a need, question or step the process builder adds stays a suggestion, shown with its stated basis (statute article, quote or Knowledge item), until the workflow, Knowledge or a case handler confirms it. It is no longer required because it names a statute article, and it does not count as a missing document.
- **Turn limits and stops.** An agent that reaches its turn limit, or stops twice without reporting, ends with what it recorded; the run completes, evaluates the checklist and names the stop in its warnings (`turn_limit`, `no_report`), instead of failing.
- **Result format.** New or changed fields:
  - presumed rows, with `by` and `left_open`;
  - `readings`, `reason_code` and `flag` on facts;
  - `note_codes`, `replaces` and `second` on documents;
  - `legal_basis` and, on suggestions, `questions` on checklist rows;
  - `answer_code`, `warnings` kinds (`turn_limit`, `no_report`, `reading_failed`);
  - routing `presumed`, `other_topic` and `reason`.

  Tool error texts now name the bound or the missing and unexpected fields.

These changes change nothing unless a workflow or the configuration uses them:
- presumptions (`presumptions` in a workflow);
- sufficiency checks (`must_show` on a document need);
- the configurable organisation and writing language (the defaults keep the earlier text).
