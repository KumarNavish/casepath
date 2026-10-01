# Causal workbench acceptance

Operation: `casepath-causal-workbench-20261001`. Tested with the public synthetic corpus, deterministic local execution, no provider credentials, and a dedicated clone. These checks establish product mechanics; they do not establish legal accuracy, real-claim suitability, commercial demand or measured handling-time savings.

## Observed handler workflow

The browser test starts from a new local journal and the Claims screen, opens the family-home walkthrough and selects **Review claim**. The saved review exposes source facts, the inferred process, questions, step-derived requests and the next action.

| Interaction | Observed result |
|---|---|
| Change `family_home` from true to false | Preview deactivates the family-home step and removes the spouse-notice requirement. Unrelated deadline requirements remain. Apply and browser reload retain the correction and history. |
| Add an independent handling-authority step, then connect it as a prerequisite of deadline review | Deadline review changes from ready to blocked, its documents become needed later, and handling-authority review becomes the next action. |
| Complete that prerequisite | Deadline review returns to ready and becomes the next action again. |
| Validate only the new step | The counter changes to 1 of 12 validated steps. Other nodes and the new connection remain unvalidated. |
| Save the validated step for reuse | A named immutable version appears in the same-family process library. |
| Change the validated, completed step's meaning to require a supervisor | Preview shows the previous and new meaning, validated to revised, completed to ready, and deadline review becoming blocked again. Apply retains the earlier completion in history. |
| Review the original tenant PDF as insufficient using exact quote `30. Juni` | The server accepts the source-bound review; the document returns from held/unreviewed to a future requirement because its step is currently blocked. No claim decision is authorized. |
| Generate a request after a condition correction | Spouse notice appears under not requested, rather than requested. The saved draft is labelled not sent. |

## Failure findings repaired during acceptance

The independent reviews and browser walkthrough found and corrected: an incorrectly placed initialization hook; a preview that did not redraw after the asynchronous response; ambiguous blocked/completed states; missing semantic diffs; a draft list validator that rejected intentional current-draft invalidation; inherited document uncertainty incorrectly described as a document's own flag; a graph review that broke the six-role evidence audit; orphan requirements after node removal; fragment document changes leaking beyond the selected nodes; stale-save recovery locking out further edits; and missing empty-graph recovery. Engine review also corrected alternative-route merging and completion after an action's meaning changes.

The saved browser journal was copied with SQLite backup and all 162 events replayed unchanged. The restart gate initially rejected the two new event names; adding their exact registered types repaired boot verification without altering any event, hash or runtime receipt. A fresh HTTP-start regression now verifies the same initial graph and assessment identity in the workbench, draft, queue and agent view. Legacy unmarked reviews remain explicit proposals until adoption. A second fresh claim persisted its graph from the first HTTP review. It successfully previewed and applied the new prerequisite fragment, showed version 1 as applied to this claim, and changed the next action. A simulated concurrent review returned a stale-revision rejection, cleared the failed pending mutation, and allowed a fresh save after reload. The 390 px view has no horizontal overflow (document and workspace width 390 px; process width 358 px). Both layouts were rendered and inspected. Final browser QA also caught an imported prerequisite shown after an unrelated outcome and a next-action explanation using an earlier selected step. The view now orders steps by dependencies, shows connected neighbours, and explains the current graph action. The initial queue requests no process-editor JavaScript; opening a reviewed claim loads it once. Empty draft sections are omitted. Built-in German draft questions use German, while historical compiler versions remain available for exact replay. The full regression result follows below.

## Commercial and operational boundaries

The workbench now carries procedural corrections through executable dependencies, evidence requirements, next actions and request drafts. That removes a specific source of manual reconciliation. The amount of work saved has not been measured with claims handlers.

The shipped local mode reconstructs three public claim families using deterministic templates and source extraction. It is not an unrestricted autonomous agent or a trained process-discovery model. Reuse is explicit and limited to compatible families and boundary relationships. It does not automatically promote a correction into every claim. Structural validation and human document sufficiency reviews remain separate from source facts, legal authority and claim-decision authorization.

No deployment, external customer message or provider call is part of this acceptance. Enterprise authentication, tenant isolation and real organizational policy admission require a separately authorized product integration.

## Adversarial product review

| Perspective | Objection | Result or remaining boundary |
|---|---|---|
| Busy handler | Editing a process adds more work than it removes. | The default view shows nearby steps; one selected step contains its documents, conditions and review controls. The impact preview replaces a manual comparison of separate requests. Time saved is unmeasured. |
| Domain reviewer | A validated diagram may be wrong or obsolete. | Validation is local to a node or connection; semantic edits mark it revised and reopen recorded completion. Source sufficiency and claim authorization remain separate. |
| Manager | There is no proof of ROI. | The acceptance scenarios demonstrate eliminated reconciliation steps. No financial ROI or handling-time claim is made without organizational measurements. |
| Security buyer | AI may invent evidence or send data elsewhere. | Local reference mode has no provider credential. Document reviews bind exact original artifact bytes and passages; caller-authored evidence fields are rejected. Enterprise access controls are not supplied by this local release. |
| First-time user | It is unclear why anything is required. | Review produces the process and each document links directly to its originating step. The short walkthrough now teaches an actual correction and its impact. Independent user comprehension remains untested. |
| Product designer | The graph overwhelms the workspace. | Current-step context appears first; the full process, conditions, history and library open deliberately. Desktop and narrow layouts are inspected as part of final acceptance. |
| Chat/search user | This is another answer generator. | A saved dependency actually blocks execution, changes request timing, invalidates stale drafts and survives replay. An explanation alone cannot perform these state transitions. |
| Correcting user | The editor updates one label while other outputs remain stale. | A–F engine/workspace checks and the browser flow bind next actions, document requests and drafts to the same graph; history and explicit version adoption prevent silent retroactive changes. |

## Rendered evidence

- [Desktop process workspace](screenshots/workbench-desktop.png)
- [Narrow-screen process workspace](screenshots/workbench-mobile.png)

Screenshots show synthetic browser-test state and are product evidence, not research results.

## Final regression result

The sealed-source command `UV_OFFLINE=1 ./bin/casepath test` completed successfully: **1,639 passed, 10 skipped, 10 warnings**, in 963.91 seconds. The isolated-run receipt identifies deterministic reference mode, no provider credential names, and no use of the persistent product database or artifact registry. The warnings concern existing deprecated lifecycle and process APIs; they are not test failures.

`node --test casepath-qa/*.test.cjs` completed with **82 passed, 0 failed**. These include causal rendering, inconsistent completion, dependency ordering, contextual connections, semantic impact, version pins, and the current-action explanation after a workspace refresh.

The tested source manifest SHA-256 is `9bfc86c52aa279a43ba1b63e39eb9a65586f5a1938718085bd922e96e6d4b78f`, based on `81aef08c96e4b5a37ab8493034c6e65997ec7bda` in branch `codex/casepath-causal-workbench-20261001`. Application and test sources stayed unchanged after this run; only acceptance/checkpoint documentation and the source manifest were updated to record completion. Exact local logs and the tested manifest are retained in `.runtime/verification-causal-workbench/`.

Initial queue JavaScript is **299,288 bytes**, below the unchanged 300,000-byte budget. The curated public build contains exactly 25 files, including the two process-editor assets. The desktop and narrow-screen captures above are from the final application code.
