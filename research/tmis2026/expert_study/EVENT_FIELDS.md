# Event fields for the expert study

Code locations are relative to `casepath-internal/casepath/` at product commit `6f3de061`.
**exists** = present today, at the location named; **partial** = present in another shape (what differs is said);
**new** = must be added. Every record and every export carries `schema` (a string such as `casepath.study.event/1`),
so a later analysis knows which shape it reads. That field is **new** everywhere except where noted.

Times: inside the insurer, absolute UTC times are kept (`at`). Every export replaces them with `t`, seconds since the
session's start (or, for runs, since the study's first frozen run).

## 1. Frozen run record (`casepath.study.frozen-run/1`)

| Field | Meaning | Status |
|---|---|---|
| `schema` | record shape | new |
| `frozen_run_id` | id of the stored run shown to all experts | exists as `runs.id` (`web/store.py`, table `runs`) |
| `source_case` | the study case (A, B, C after the lot; internal id inside) | new |
| `cut_sha256` | hash of the cut copy the run used (section 1a) | new |
| `role` | `frozen`, `variation`, `comparator` | new |
| `repeat` | 1 for the frozen run, 2–5 for variation runs, 1–3 for comparator runs | partial: `repeat` in benchmark results (`quality/evaluate.py:409`) |
| `files_sha256` | hash of the case's files | exists (`web/store.py`, `runs.files_sha256`) |
| `workflow_id`, `workflow_version` | routed process | exists (`runs`) |
| `result_sha256` | SHA-256 of the canonical JSON of `runs.result` | new |
| `item_list_sha256` | SHA-256 of the canonical item list (section 2, fields `item_id`, `kind`, `key`, `value`) | new |
| `parity` | the full parity manifest | exists (`parity.py`, `manifest`) |
| `knowledge_content_sha256` | per Knowledge item, hash of `id, family, kind, content, applies_when, status, version` only | new (today's hash includes `stats` and `updated_at`, `parity.py:_digest`) |
| `usage` | model turns and tokens | exists (`result.usage`, `agents/team.py` `finalize`) |
| `deployment` | model deployment name | exists (`runs.deployment`) |

## 1a. Cut copy record (`casepath.study.cut/1`)

One row per study case (and per second decision point, if one is made). Columns "Pseudonymous" and "Content" say which
export carries the field (section 7).

| Field | Meaning | Pseudonymous | Content | Status |
|---|---|---|---|---|
| `schema` | record shape | yes | yes | new |
| `source_case` | A, B, C in the pseudonymous export; internal case id in the content export | label | id | new |
| `cut_id` | id of the cut copy; `h_` + 12 hex in the pseudonymous export | hashed | yes | new |
| `point` | `first` or `second` (the optional system-only point) | yes | yes | new |
| `decision_point` | in the pseudonymous export a label (`DP1`, `DP2`) and an offset in whole days from the case's first document; in the content export the calendar date | label and offset | date | new |
| `rule_applied` | `first_outgoing_request`, `first_outgoing_action` (no request in the case) or `second_outgoing_action`; plus, content export only, which action and why it is the first | code | code and text | new |
| `cut_sha256` | SHA-256 of the cut copy | yes | yes | new |
| `included_documents` | number of included documents (pseudonymous); list of documents or page ranges with dates (content) | count | list | new |
| `leak_check` | adjudicator (G1/G2), done (bool), leaks found before the run (count) | yes | yes, with descriptions | new |
| `routes_to_common_workflow` | inclusion criterion, from routing alone | yes | yes | new |

## 2. Item record (`casepath.study.item/1`)

One row per statement of a frozen run (and of a comparator run).

| Field | Meaning | Status |
|---|---|---|
| `schema` | record shape | new |
| `item_id` | `<frozen_run_id>:<kind>:<key>`; stable for all copies of the case | partial: `kind:key` is the feedback target (`web/app.py:71`) |
| `kind` | `step`, `fact`, `deadline`, `document`, `next_action`, `reply`, `open_point`, `summary`, `party`, `timeline`, `answer` | partial: all but `step`, `next_action`, `party` exist as target kinds (`web/app.py:71`) |
| `key` | fact id, document id, step id, `answer:<fact>` / `obtain:<document>` for next actions, list index for open points, clauses, parties, timeline | partial: fact and document ids exist (`result.facts[].fact`, `evaluation.documents[].document`); next-action keys new; index keys are positional and valid only within one run |
| `chain` | true for step, gating fact, deadline, document, next action | new |
| `value` | what CasePath said (fact value; document `required` and `status`; step id; action text) | exists in `result` and `evaluation` (`process/workflows.py:383–395`) |
| `stated_as` | `established`, `presumed`, `conflicting`, `unknown`, `put_to_handler` (open point, waiting_for, depends) | partial: `facts[].status`, `evaluation.waiting_for`, `documents[].required = depends` |
| `verdict` | the source checker's verdict | exists (`facts[].verdict`, `documents[].verdict`) |
| `evidence` | citations: file id, quote offsets | exists (`facts[].citations`, `documents[].citations`) |
| `node` | process node the item is there for ("wegen") | partial: `evaluation.documents[].step`; new for facts and actions |
| `origin` | `workflow`, `knowledge#<id>@v<n>`, `agent_edit#<id>` | exists (`source_refs`, `documents[].knowledge`, `agent_edits`) |
| `system` | `casepath` or `comparator` | new |
| `source_case`, `cut_sha256` | the study case and the cut copy the item belongs to | new |
| `leak_flag` | set if a leak found after a session affects the item: `leak_id` and date found (content); boolean (pseudonymous) | new |

## 3. Event record (`casepath.study.event/1`)

### 3.1 Fields of every event

| Field | Meaning | Status |
|---|---|---|
| `schema` | record shape | new |
| `event_id` | unique id | new |
| `seq` | order within the session | partial: `run_events.seq` for agent events only (`web/store.py`) |
| `session_id` | session | new |
| `expert` | pseudonym inside; randomised label E1–E5 in exports | partial: `by` / `who` (identity, `web/app.py` `user`) |
| `case_copy` | the expert's copy of the cut copy | exists as `cases.id` |
| `source_case` | A, B, C | new |
| `frozen_run_id` | | new on events |
| `at` / `t` | absolute time inside; relative seconds in exports | partial: `at` on feedback and edits |
| `kind` | one of 3.2 | new |
| `parity_sha` | source-tree hash at the event | new |
| `item_id` | when the event concerns an item | partial: `feedback.target` |

### 3.2 Event kinds

| Kind | Further fields | Status |
|---|---|---|
| `session.started` | `item_list_check` (true/false) | new |
| `case.opened` | `position` (1–3), `condition` (`unaided`, `aided`) | new |
| `item.exposed` | `from_t`, `to_t` (one on-screen interval; raw, no threshold), `view` | new |
| `source.opened` | `item_id`, `file_id`, `page` | new (the page endpoint exists, `/api/files/{id}/pages`, but is not logged) |
| `item.confirmed` | `item_id` | partial: feedback verdict `correct` (`web/store.py`, `set_feedback`), overwritable |
| `item.corrected` | `item_id`, `before`, `after`, `reason` (1–6 or `none`), `note_present` (bool), `edit_id` when it is a process edit | partial: feedback verdict `wrong` with note; process edits (`case_edits`: `op`, `args`, `reason` free text) |
| `item.dismissed` | `item_id`, `reason`, `edit_id` | partial: `remove_document` edit (`process/casegraph.py:17`) |
| `item.added` | `what` (`document`, `step`, `question`, `fact`, `action`), `catalogue_id` or `free_text_present`, `node`, `reason`, `edit_id` | partial: `add_document`, `add_step`, `add_question` edits |
| `correction.undone` | `undoes` (event id), `edit_id` | partial: `/api/edits/{id}/undo` sets status `undone` without time (`web/store.py`, `set_edit_status`) |
| `item.propagated` | `caused_by` (event id), `item_id`, `change` (`changed`, `vanished`, `appeared`), `before`, `after` | partial: `casegraph.diff` computes it (`process/casegraph.py:226`) but it is not stored; recomputed model-free from the log |
| `point.settled` | `item_id` | exists: verdict `done` on `point:<key>` (`web/app.py:72`) |
| `unaided.saved` | `step`, `documents` (catalogue ids), `documents_free_text_present`, `action_kind`, `action_free_text_present` | new |
| `unaided.frozen` | `answer_sha256` | new |
| `reveal` | | new |
| `post_reveal.revised` | the same fields as `unaided.saved` | new |
| `idle.started`, `idle.ended` | | new |
| `letter.copied` | `change_ratio` (edit distance / draft length) | new |
| `case.closed` | `form` (`erledigt`, `erledigt_mit_vorbehalt`), `capped` (bool) | new |
| `cap.reached` | | new |
| `scale.answered` | `scale` (`tlx`, `tia_trust`, `tia_propensity`), `occasion`, `answers` (item number → value; TiA `keine_angabe` as missing) | new |
| `technical.failure` | `what` (code) | new |
| `session.ended` | `complete` (bool) | new |

## 4. Session record (`casepath.study.session/1`)

| Field | Status |
|---|---|
| `schema`, `session_id`, `expert` (label), `session_order` (1–5) | new |
| `allocation_row` (E1–E5), `cases` (A/B/C by position), `unaided_case` | new |
| `cut_sha256` per case copy, checked at session start like the item list | new |
| `knew_case_before` (per case), `made_reference_or_gold` (bool) | new |
| `parity` (manifest at session start), `frozen_run_ids`, `item_list_check` per case | partial: manifest exists (`parity.py`) |
| `active_seconds` per case (idle excluded), `capped` per case | new |
| `withdrawn` (bool, date inside only) | new |

## 5. Gold record (`casepath.study.gold/1`)

| Field | Status |
|---|---|
| `schema`, `item_id`, `adjudicator` (G1, G2, or A for automatic labels), `rater_kind` (`qualified`, `blind_rater`, `automatic`), `label` (`correct`, `incorrect`, `undecidable`), `basis` (`reference`, `file`) | new |
| `as_of` (`DP1`, `DP2`): the decision point the label is for | new |
| `reference_action`: the insurer's next action and documents requested, from the later file (catalogue ids pseudonymous; text content only); `alternatives`: those judged equally correct, with the time they were listed (before the first session) | new |
| `reconciled_label`, `reconciled_by` (`agreement`, `discussion`, `undecidable`) | new |
| `omission`: `reference_item`, `kind`, `source_case`, `system`, `adjudicator` | new |
| `correction_label`: `event_id`, `adjudicator`, `label` (after the sessions, blind to the expert) | new |
| benchmark truth for synthetic cases (`truth.facts`, `truth.documents`, `next_actions`) | exists for synthetic suites only (`quality/evaluate.py:220`, `score`) |

## 6. Recall coding record (`casepath.study.recall/1`)

`schema`, `event_id` (the correction discussed), `coded_reason` (1–6, `none`), `coder`, `tapped_reason_hidden` (true),
`segment_start_t`, `segment_end_t`. Transcript: content export only. All **new**.

## 7. Exports

| Export | Holds | Leaves the insurer |
|---|---|---|
| **Pseudonymous** (`casepath.study.export/1`) | all records above with relative times, decision points as labels and day offsets, cut hashes, leak flags as booleans, randomised expert labels E1–E5, hashed case-copy and file ids (`h_` + 12 hex, salted, as `quality/scorecard.py` `hashed`), source-case labels A/B/C, item ids, kinds, keys that are catalogue ids, statuses, reason codes, labels, counts, ratios, scale answers, hashes. No item value, quote, note, free text or name. Passes the scorecard guard (`quality/scorecard.py`, `guard`) extended with the study's enums. | yes |
| **Content** (`casepath.study.content/1`) | the pseudonymous export plus decision-point dates and the rule's application in words, included-document lists, leak descriptions, item values and texts, before/after values, notes, free-text additions and answers, recall transcripts, absolute times | no |

## 8. Fields kept beyond what the pre-registered analyses need

Kept so that a later, separate paper loses nothing.

| Kept | Export |
|---|---|
| The full event sequence with relative times, not only derived fates | pseudonymous (content-bearing fields in the content export) |
| Raw exposure intervals per item and view | pseudonymous |
| Every version of an item (frozen value, each correction, each undo, each propagated change) | ids and statuses: pseudonymous; values: content |
| Every letter-draft change ratio at each copy, not only the last | pseudonymous |
| The unaided answer and every revision after the reveal | catalogue ids and kinds: pseudonymous; free text: content |
| Scale answers per item, per occasion and per case | pseudonymous |
| Blind-coded reasons and the tapped reasons | pseudonymous; transcripts: content |
| Each adjudicator's individual labels, not only the reconciled one | pseudonymous |
| The parity manifest per session and per run | pseudonymous |
| Variation and comparator runs, with their item lists | ids, statuses, hashes: pseudonymous; values: content |
| Agent run events (`run_events`) of the frozen runs | kinds and counts: pseudonymous; full: content |

## 9. Measures and the fields they use

| Measure (pre-registration section) | Fields |
|---|---|
| Final fate (9.1) | `item.corrected`, `item.dismissed`, `correction.undone`, `item.propagated.change = vanished`, `source.opened`, `item.confirmed`, `item.exposed.from_t/to_t`; item `item_id` |
| Q1 item accuracy, coverage (9.2) | item `item_id`, `chain`, `system`; gold `reconciled_label`; `omission` |
| Q2 change shares, over- and under-reliance (9.3) | final fate; gold `reconciled_label`; item `kind`, `source_case`; event `expert` |
| Q2 correction correctness | `item.corrected.after` (content), gold `correction_label` |
| Q2 expert agreement | final fate per `expert` and `item_id` |
| Q3 accuracy unaided / after reveal / CasePath (9.4) | `unaided.saved` (last before `unaided.frozen`), `post_reveal.revised` (last before `case.closed`), item list; gold `reconciled_label`, `omission` |
| Q3 time, corrections, letter | `case.opened`, `case.closed`, `idle.*`, `active_seconds`; counts of `item.corrected` / `dismissed` / `added`; `letter.copied.change_ratio` |
| Q3 relative AI reliance and self-reliance | decision units from `unaided.saved`, `post_reveal.revised`, item list, gold |
| Q4 proposals, gate, held-out accuracy (9.5) | `item.added` (`what`, `catalogue_id`, `reason`, `node`), `source_case`, `expert`; frozen runs' `result`; Knowledge item fields (`process/knowledge.py`, `new_item`); replay output; gold |
| Q5 reasons (9.6) | `reason` on corrections, dismissals, additions; recall `coded_reason`; gold `correction_label` for reason 5 |
| Run-to-run variation (9.7) | item lists of `role = frozen` and `variation` runs, by `kind:key` |
| Adjudicator agreement | gold `label` per `adjudicator` |
| Calibration | `case.closed.form`; Q1 accuracy per case copy |
| Trust, workload | `scale.answered` |
| Decision point, cut, leaks (sections 3.1, 4.4) | cut record; item `leak_flag`; gold `as_of`, `reference_action`, `alternatives` |
| Exclusions | `case.closed.capped`, `technical.failure`, session `knew_case_before`, `made_reference_or_gold`, `withdrawn`; gold `undecidable` |
