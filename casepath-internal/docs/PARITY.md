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
  - A deciding fact counts as raised by the files and left open (so that no presumption applies) only through readings that answer it open with the words that say so found in the files; see "Presumptions and open facts".
- **Documents.**
  - A message or another document that only mentions a needed document no longer meets the need (`mentioned_only`; the need stays missing).
  - Quotes for a present document count only from the files named for it. The source checker is asked whether the file is the document itself, and checks each `must_show` item on its own; an item it does not find shown makes the document unusable. The finder names `must_show` items exactly as listed.
  - A document counts as present only when a second, independent judgment agrees, naming the same file and quoting each `must_show` item; otherwise it stays requested as unusable. The second judgment is one model call each time the finder has recorded a document as present (in a run, on its retry pass and in a recheck). In a case over 40,000 characters it sees keyword passages for each need, not the whole files. If it fails, the documents stay requested and the warnings say so (`document_check_failed`).
  - When the finder's first pass stops before it finishes, needs it never recorded stay requested (missing) and are marked not checked (`not_checked`, `documents_not_checked`), with a warning; a stop on its later pass for rejected items leaves what the first pass recorded.
  - A later record of a need replaces the earlier one, as an event (`document.changed`) with the status it replaced.
- **Facts.** (The earlier "one structured reading" form is replaced by this one.)
  - In a case of up to 40,000 characters each reading answers every condition of the process true, false, open or not stated. True and false come with one exact quotation found in any file; open means the files themselves say the matter is unknown, undecided, disputed or still to be determined, and comes with the words that say so; not stated means the files do not address it, with no quotation. For the checklist, open and not stated are both unknown; the conditions come, in the same order for every reading, with a task that says they decide which documents are requested and which are held; the case files are the message. Dates are asked as YYYY-MM-DD. There are three readings by default (`CASEPATH_READINGS`, at least 2); a deciding value counts only when all of them give it; where some give another value the fact is conflicting, where only some give a value it stays open with their quotes.
  - Readings ask for low effort on every deployment, whatever the configured effort. A true, false or open answer whose quotation is not found is asked for once more; an open answer whose words are still not found raises nothing.
  - A condition a reading answers twice with different judgments is unknown. A failed reading call leaves its conditions unknown, counts as neither open nor not stated and is a warning (`reading_failed`), not a failed run.
  - A value established at routing and a different value from a reading conflict; a person decides.
  - Over 40,000 characters, the claim reader agent records the facts and the second reading sees keyword passages only, so deciding facts will more often stay open.
- **Routing after the readings.** When the readings admit a routing fact (all readings agree, or all agree against the value routing read) whose value contradicts the condition the workflow was chosen under, routing runs once more on the admitted value and that workflow is prepared; if it is contradicted too, or no workflow fits, the case is handed over with the conflict shown (`conflict`, `rerouted`). The readings now also read the routing facts under the agreement rule. A case worker's chosen workflow is never rerouted.
- **Presumptions and open facts.** No presumption of any kind (routed, unstated or from routing) applies to a fact the files raise and leave open; the documents that depend on it are held. A fact is raised and left open only through open answers whose words are found in the files: a reading that answers not stated raises nothing, whatever it quotes (before, a reading's nearest related sentence counted as raising the matter, and the documents of normal claims that only take the event for granted were held). Each fact row records every reading's answer as `open_readings` (true for an open answer with its words found, false otherwise, null for a reading that did not answer); `OPEN_RULE` in `process/workflows.py` says how many must be open: `any` reading (the default), or `all` readings that answered. A reading that failed or did not answer counts for neither. A row stored without `open_readings` counts as raised when it carries quotations. A reading that found the presumed value still supports the presumption, and a failed reading clears nothing. The default is a policy decision: as readings that differ on a value leave the fact open, readings that differ on whether the files state a doubt hold it, so one reading's "not stated" does not let a presumption override a doubt the others quoted. This overrides the development criterion set beforehand (choose `all` when `any` holds more than 0.05 more required documents or spurious holds per claim-run with equal premature requests): replayed on the same stored readings, `any` held 0.150 and `all` 0.056 per claim-run in checklist-only tenancy runs, with no premature request under either.
- **Optional needs under an open question** keep the label optional, as suggestions do; they never become holds.
- **Quotation matching.** A quotation is found across typographic differences by an explicit list only: quotation marks, apostrophes, dashes, the Latin ligatures U+FB00-FB06, soft hyphens and space variants. Letter case and other compatibility forms (superscripts, fractions) are not folded.
- **Recheck.** A recheck after a process edit keeps the routing presumption, judges a document found present a second time, and adds its own stops to the warnings.
- **Report and interface.** A process-builder suggestion with a statute article is shown as a suggestion with its basis, not as required by law; a suggestion under an open question names the question; a deciding fact the source checker doubted shows the doubt; a need not reached by a stopped finder is shown as missing and not checked; the run's warnings are listed (each stop with a note true for the part that stopped); a checklist-only run names the steps it left out. Notes the product writes carry codes and are shown in German and English where they appear.
- **Deciding facts.**
  - A fact a condition uses, which both readings give with an exact quote, is no longer removed when the source checker doubts it (the doubt is a `flag`). Rejected deciding facts are not retried, and no single agent can record a deciding fact after the two readings.
  - A case worker cannot set a fact's value today: no such path exists in the product. A case worker can still change what a fact requires through process edits (for example `set_required_when`, `remove_document`), also for a locked fact.
- **Suggestions under an open question.** A suggested need keeps its label while the question that decides it is open, instead of becoming a hold.
- **Reasoning effort on chat endpoints.** With `CASEPATH_MODEL_REASONING` on, a chat-completions endpoint receives each call's effort as `reasoning_effort` and no temperature. It is off only by the code's default: `deploy/workspace/env.example` and `deploy/cloudshell/start.sh` set it to true. Both configure the other connector, for which the flag already sent reasoning effort; an environment that keeps the flag and switches to a chat-completions endpoint now sends it too. The request keeps `max_tokens`; the outside endpoint used for research accepts that with reasoning effort. Before turning it on inside, check that the gateway accepts `reasoning_effort` together with `max_tokens` (some reasoning endpoints expect `max_completion_tokens` instead, as the other connector sends). Where a deployment already sends reasoning effort, the readings now go at low effort instead of the team's effort.
- **Process-builder additions** (the owner's decision is pending; the commit can be dropped on its own): a need, question or step the process builder adds stays a suggestion, shown with its stated basis (statute article, quote or Knowledge item), until the workflow, Knowledge or a case handler confirms it. It is no longer required because it names a statute article, and it does not count as a missing document.
- **Turn limits and stops.** An agent that reaches its turn limit, or stops twice without reporting, ends with what it recorded; the run completes, evaluates the checklist and names the stop in its warnings (`turn_limit`, `no_report`), instead of failing.
- **Result format.** New or changed fields:
  - presumed rows, with `by` and `left_open`;
  - `readings`, `reason_code` and `flag` on facts;
  - `note_codes`, `replaces` and `second` on documents;
  - `legal_basis` and, on suggestions, `questions` on checklist rows;
  - `answer_code`, `warnings` kinds (`turn_limit`, `no_report`, `reading_failed`, `document_check_failed`);
  - routing `presumed`, `other_topic` and `reason`.

  Tool error texts now name the bound or the missing and unexpected fields.

These changes change nothing unless a workflow or the configuration uses them:
- the checklist-only run (`CASEPATH_RUN_SCOPE=checklist`, default `full`): a run does only what can decide the checklist. That is routing, the readings, the document judgments (finder, second judgment and source checker on documents) when the case has more than one file or its one file bundles several documents, the process builder when active Knowledge applies to the case, and evaluation. The claim-reader brief, the result checker and the fact checks are skipped: a deciding fact all readings agree on is accepted without the fact check, which could only add a flag. A one-file case without segments is taken as the claim itself, so its document needs count as missing. The result names each skipped step and why (`skipped`, `scope`), the interface shows it, and the parity manifest lists the setting. It is two commits, the checklist-only commit and the fixup right after it; revert both together to drop it.
- presumptions (`presumptions` in a workflow);
- sufficiency checks (`must_show` on a document need);
- the configurable organisation and writing language (the defaults keep the earlier text).
