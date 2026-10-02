# Working causal process

CasePath's working process determines which steps apply, what can happen next, and which documents those steps require. A handler can correct one node or relationship, inspect the consequences, and apply the change to the current claim. The saved process is an editable snapshot in the claim journal.

The initial graph comes from the current product policy catalog and the claim's deterministic assessment. Its structure starts unvalidated, including the intake node. Source references remain references to supporting material; they do not validate the generated process. This product behavior has no inherited benchmark score or claim-decision authority.

## Use the process in a claim

1. Review the claim, then choose **Review step** or open **Process**. Select a step in **Working process**. The inspector shows its condition, document requirements, connections, validation, and provenance.
2. Edit the step, change a connection, or correct a claim condition. Enter the reviewing handler and the reason. **Preview changes** calculates the resulting steps, documents, questions, and next action without saving.
3. Inspect both the changes and the unchanged requirements. **Apply to this claim** saves the exact reviewed preview. A stale preview requires a reload. The process history retains the handler, reason, and consequences.
4. Use **Review source** beside a document. Select an original claim artifact, quote the passage being reviewed, and record whether it was received, is sufficient for this requirement, or remains insufficient.
5. Mark a step completed when its work is done. Completion is checked against the current route, prerequisites, and document reviews. A recorded completion that conflicts with them is shown for review.
6. Validate selected process structures before saving them for reuse. Applying a saved fragment to another claim requires its own impact preview.

Adding a step after another creates an `enables` connection. Choosing an independent starting step sets its explicit `entry` flag. Removing a node also removes its incident relationships. Remaining nodes never become starting steps merely because their predecessor disappeared. An empty graph can be rebuilt by adding an entry node.

## Nodes, conditions, and dependencies

A node has an identity, label, meaning, kind, condition, document references, completion record, validation, and provenance. The supported kinds are state, action, decision, prerequisite, and outcome. Kind describes the node; conditions and relationships determine execution.

Applicability and readiness are separate. An applicable future step may still wait for an earlier step. A node becomes applicable through an explicit entry or an applicable incoming flow, subject to its own condition. Alternative flows combine with OR: a known applicable route remains applicable when another route is unresolved. To become ready, a non-entry node needs at least one consistently completed incoming flow predecessor. Every applicable explicit prerequisite must also be satisfied.

All relationships point **from source to target**. With source A, target B, and relationship `requires`, **A must complete before B can proceed**. The handler form labels those endpoints **From** and **To**.

| Relationship | Implemented effect on the target |
| --- | --- |
| `enables`, `branches_to`, `conditionally_activates` | Propagate the source's planned applicability through the relationship condition. Readiness waits for a consistent source completion. These labels share execution semantics. |
| `requires` | Adds a mandatory source-completion prerequisite. A false relationship condition waives it; an unresolved condition blocks it. This relationship alone does not create an entry path. |
| `causes` | Creates an applicable route only after a consistent source completion and a true relationship condition. |
| `completes` | Has the activation behavior of `causes` and derives an operational completion for the target. The target's other prerequisites and document requirements can still make that completion inconsistent. |
| `blocks` | Prevents target readiness while the source and relationship condition apply. Completing the blocking source does not remove the block; its applicability or relationship must change. |
| `invalidates`, `supersedes` | Deactivate the target while the source and relationship condition apply. They share execution semantics and preserve the target's history. An existing completion can become inconsistent. |

Conditions use `true`, `false`, and `unresolved`. They support a fixed value, an existing claim flag, negation, and nested **all**/**any** expressions. Unknown flags and unsupported operators are rejected. Expressions never execute code. For example:

```json
{"all": [{"flag": "family_home"}, {"not": {"flag": "arrears"}}]}
```

False decides an **all** expression; true decides an **any** expression. Otherwise, unresolved inputs stay unresolved. Unresolved flags, node conditions, relationships, and document conditions produce questions identifying their dependent work. A question does not invent a case fact.

Every persisted graph must be acyclic, including currently inactive relationships. Missing references and duplicate identities are rejected. The current bounds are 100 nodes, 300 relationships, 100 document definitions, and 100 claim flags. Conditions allow depth 8, at most 12 operands per group, and 128 expression elements. Graph history is bounded at 2,000 entries.

## Documents follow the process

Nodes reference document types in a shared catalog. A document applies when at least one linked node applies and its own condition applies. Its catalog definition and condition apply to every node using that document type. Removing one association does not remove a requirement still justified by another node.

| Document state | Meaning |
| --- | --- |
| `not_needed` | No applicable process route currently justifies it. |
| `held_behind_question` | Applicability remains unresolved; clarify the condition first. |
| `needed_now` | An applicable ready step needs it, and there is no sufficient current review or unreviewed file awaiting inspection. |
| `needed_later` | The applicable planned path needs it after earlier work. |
| `held_not_reviewed` | An original file is present but has no sufficient review for the current definition. |
| `established` | A named human has recorded a sufficient source review for the current document requirement. |
| `optional` | The applicable document definition is optional and has no overriding on-file review state. |

`needed_now` and `needed_later` are request candidates. Draft generation reads these graph-derived candidates; drafting does not send a request. An insufficient review returns an applicable required document to the appropriate missing state. Presence inferred from a filename remains unreviewed.

A source review checks the artifact against this claim's original source binding and byte hash. A supplied quote must occur in the supported original text or extracted PDF text. A sufficient review requires a quote; a small explicit-uncertainty check can reject it. These checks establish source identity and quote presence. The handler remains responsible for judging whether the passage establishes the requested content.

Each receipt records the artifact, file hash, exact quote, reviewer, note, review result, and document-definition hash. A sufficient receipt can satisfy the same document requirement across several nodes. Changing the document definition invalidates the receipt's sufficiency for that definition and requires another review. Reviewing the same artifact again replaces its current receipt while preserving history. A sufficient current receipt takes precedence when other artifacts for that document remain insufficient.

The source-review route uses existing original claim artifacts. It does not upload new external files or establish claim facts, deadlines, legal adequacy, or an authorized claim outcome. Images without supported text can be recorded as received; this route cannot establish sufficiency from an unverified transcription.

## Validation, completion, and history

Validation belongs to a node or relationship. Validating one item changes neither adjacent items nor the whole graph. Rejecting a node deactivates it; rejecting a relationship removes its execution effect. Editing an item marks its validation `revised` and retains the previous status, actor, and previous content. Editing a shared document definition revises the validation of nodes referencing it.

Changing a node's meaning or kind reopens its recorded completion; history retains the earlier completed state. Renaming a label alone preserves completion. Condition and dependency changes retain the completion record and expose an inconsistency when the revised route no longer supports it. A `completes` relationship is an independent explicit rule for deriving completion, so review that relationship when changing the action it completes.

Validation assesses process structure. Completion records procedural work. Source sufficiency assesses one document requirement. These records remain separate from claim-decision authority, which the process API reports as false. A typed handler name is an audit annotation in this local product, not an authenticated enterprise identity.

The overall `process_status` is `needs_review` for inconsistent completion or an empty/unusable route, `unresolved` while questions or unknown applicability remain, `complete` when all applicable nodes are consistently completed, `in_progress` when work is ready, or `blocked` when prerequisites prevent progress. Process completion leaves the claim outcome for separate review; it does not authorize a settlement or legal decision.

New product reviews save the inferred graph with the initial review event, so the workbench, drafts, queue and agent review share one assessment from the start. Earlier unmarked reviews keep their original assessment; their inferred graph is explicitly a proposal until a handler applies a correction. No read mutates a historical claim.

The claim's original intake assessment is preserved. Accepted process events produce a separate working graph. Views, queue summaries, request drafts, operational projections, and agent snapshots use the saved graph's effective assessment, from the initial review for new claims or from explicit adoption for older reviews. The underlying source-acquisition path retains its own authority and event checks.

Impact has several layers: changed and unchanged nodes or relationships; added, removed, and unchanged document requirements; document-definition edits; source-association and receipt changes; reopened questions; next-action changes; and inconsistent completions. A renamed document can therefore appear as a definition change while its requirement remains unchanged. Descendants reconsidered without changed output are reported separately.

## Reusable fragments are pinned snapshots

A saved fragment contains selected validated nodes and their validated internal relationships. It records the source claim and revision, a fragment identity, a version, and a content hash. Completion records and source files do not travel with it.

Applying a version explicitly replaces the selected nodes and their internal relationships in a compatible claim family. A genuinely new imported node may bring a missing boundary connection to an existing external step; that connection starts unvalidated. Missing or changed boundary relationships between nodes already present in the target are rejected. Existing case-condition values stay with the target claim; missing flags become unresolved. The target's own source files remain available. Reused nodes start incomplete and carry the fragment's provenance.

Relationships crossing the selection boundary are compatibility constraints. Missing or changed required boundary relationships between existing target nodes reject the application. Other external relationships remain in the target claim. A fragment that would change a document definition used by nodes outside the selection is rejected for broader review. The combined graph must still pass reference, condition, and cycle validation.

Saving a newer version does not update claims that used an earlier one. Each application records its exact fragment version and hash. Historical journal revisions remain available. The library is a set of explicitly reviewed snapshots; the product does not infer new organizational knowledge automatically from claim closure.

## Integration and verification

The pure engine is [causal_process_v1.py](../../casepath-api/casepath_api/causal_process_v1.py). `build_graph` seeds the current catalog, `evaluate` derives state, `apply_edit` applies a closed edit operation, `refresh_document` accepts a server-checked receipt, and `impact` compares outputs. `seal_graph` copies, validates, and hashes the saved definition.

[causal_workspace_v1.py](../../casepath-api/casepath_api/causal_workspace_v1.py) binds those functions to the claim journal. Preview is read-only. Apply verifies the parent workspace revision, state hash, and preview hash; the journal enforces idempotency and replays accepted events. Process edits and document reviews use `WORKSPACE_CAUSAL_PROCESS_EDITED_V1`; fragment saves use `WORKSPACE_PROCESS_FRAGMENT_SAVED_V1`. Historical handler-note semantics remain unchanged.

Routes are under `/api/claim-loops/v1/workspace/claims/{claim_id}/process`: `GET` for the view; `POST /preview` and `/apply` for edits; `POST /documents/preview` and `/documents/apply` for checked source review; and `POST /fragments` for saving a version. Fragment application uses the normal edit preview/apply flow. Callers cannot supply `held_files` or source authority through ordinary document edits.

Behavioral checks live in [the engine suite](../../casepath-api/tests/test_causal_process_v1.py) and [the workspace integration suite](../../casepath-api/tests/test_causal_workspace_v1.py).

| Required case | Behavioral checks |
| --- | --- |
| A: Remove a node | `test_a_remove_node_reconsiders_descendants_preserves_shared_documents`; workspace removal test checks unaffected requirements. |
| B: Change a branch | `test_b_change_branch_changes_downstream_documents_action_and_questions`; workspace branch test checks queue, draft, restart, and replay. |
| C: Add a prerequisite | `test_c_new_prerequisite_blocks_until_completed_and_exposes_requirements`; workspace prerequisite test checks granular state. |
| D: Validate one node | `test_d_validation_is_local_including_edges_and_roots`. |
| E: Modify validated structure | `test_e_modifying_validated_node_keeps_history_and_flags_inconsistent_completion`; document-definition and source-review tests cover reopened requirements. |
| F: Update a shared fragment | `test_fragment_versions_are_explicit_and_claims_remain_pinned` checks a new version, unchanged target conditions, and unchanged earlier claim snapshots. |

Additional checks cover invalid expressions, cycles, dangling references, atomic rejection, explicit entry recovery, known-route/unknown-alternative merges, reopening a changed completed action, exact source quotes, foreign artifacts, stale previews, conflicting idempotency keys, caller-authored evidence rejection, and process completion without claim-decision authority. Run the focused suite from the repository root after preparation:

```sh
PYTHONPATH=casepath-api .runtime/casepath-dev-v2/venv/bin/python -m pytest \
  casepath-api/tests/test_causal_process_v1.py \
  casepath-api/tests/test_causal_workspace_v1.py -q
```

These checks establish deterministic product mechanics on synthetic intake data. Model quality, legal correctness, enterprise access controls, and outcomes on real claims need separate validation.
