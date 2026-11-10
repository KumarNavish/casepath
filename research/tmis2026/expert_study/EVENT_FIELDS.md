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
| `source_case` | A, B, C in the pseudonymous export; dossier label (D2, D4, D7; D5 if the reserve is used) in the content export | label | dossier label | new |
| `reserve_used` | whether D5 replaced a study case, and the listed reason (`inclusion_failed`, `cut_impossible`, `leak_unremovable`) | yes | yes | new |
| `cut_id` | id of the cut copy; `h_` + 12 hex in the pseudonymous export | hashed | yes | new |
| `point` | `first` or `second` (the optional system-only point) | yes | yes | new |
| `decision_point` | in the pseudonymous export a label (`DP1`, `DP2`) and an offset in whole days from the case's first document; in the content export the calendar date | label and offset | date | new |
| `rule_applied` | `first_outgoing_request`, `first_outgoing_action` (no request in the case) or `second_outgoing_action`; plus, content export only, which action and why it is the first | code | code and text | new |
| `cut_sha256` | SHA-256 of the cut copy | yes | yes | new |
| `included_documents` | number of included documents (pseudonymous); list of documents or page ranges with dates (content) | count | list | new |
| `leak_check` | checked by the process owner, done (bool), leaks found before the run (count) | yes | yes, with descriptions | new |
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
| `case.opened` | `position` (1–3), `own_answer_first` (bool, true for position 1) | new |
| `item.exposed` | `from_t`, `to_t` (one on-screen interval; raw, no threshold), `view` | new |
| `source.opened` | `item_id`, `file_id`, `page` | new (the page endpoint exists, `/api/files/{id}/pages`, but is not logged) |
| `item.confirmed` | `item_id` | partial: feedback verdict `correct` (`web/store.py`, `set_feedback`), overwritable |
| `item.corrected` | `item_id`, `before`, `after`, `reason` (1–6 or `none`), `edit_id` when it is a process edit | partial: feedback verdict `wrong` with note; process edits (`case_edits`: `op`, `args`, `reason` free text) |
| `item.dismissed` | `item_id`, `reason`, `edit_id` | partial: `remove_document` edit (`process/casegraph.py:17`) |
| `item.added` | `what` (`document`, `step`, `question`, `fact`, `action`), `catalogue_id` or `free_text_present`, `node`, `reason`, `edit_id` | partial: `add_document`, `add_step`, `add_question` edits |
| `correction.undone` | `undoes` (event id), `edit_id` | partial: `/api/edits/{id}/undo` sets status `undone` without time (`web/store.py`, `set_edit_status`) |
| `item.propagated` | `caused_by` (event id), `item_id`, `change` (`changed`, `vanished`, `appeared`), `before`, `after` | partial: `casegraph.diff` computes it (`process/casegraph.py:226`) but it is not stored; recomputed model-free from the log |
| `point.settled` | `item_id` | exists: verdict `done` on `point:<key>` (`web/app.py:72`) |
| `own_answer.saved` | the three pick-lists: `step` (step id or `not_in_list`), `documents` (catalogue ids), `action_kind` | new |
| `own_answer.frozen` | `answer_sha256` | new |
| `reveal` | | new |
| `note.added` | `where` (screen, or `closing`), `item_id` (optional), `length` (characters) in the pseudonymous export; `text` in the content export only | partial: feedback `note` on an item; no screen-level note today |
| `idle.started`, `idle.ended` | | new |
| `letter.copied` | `change_ratio` (edit distance / draft length) | new |
| `case.closed` | `form` (`erledigt`, `erledigt_mit_vorbehalt`), `capped` (bool), `closing_note_present` (bool) | new |
| `case.attested` | `kept_item_ids` (the items left unchanged at closing, which closing attests), `item_list_sha256` | new |
| `cap.reached` | | new |
| `technical.failure` | `what` (code) | new |
| `session.ended` | `complete` (bool) | new |

## 4. Session record (`casepath.study.session/1`)

| Field | Status |
|---|---|
| `schema`, `session_id`, `expert` (label), `session_order` (1–5) | new |
| `allocation_row` (E1–E5), `cases` (A/B/C by position), `first_case` | new |
| `cut_sha256` per case copy, checked at session start like the item list | new |
| `prior_handling` per case: copied from the status-source record (section 5), not asked | new |
| `parity` (manifest at session start), `frozen_run_ids`, `item_list_check` per case | partial: manifest exists (`parity.py`) |
| `active_seconds` per case (idle excluded), `capped` per case | new |
| `withdrawn` (bool, date inside only) | new |

## 5. Status-source records (`casepath.study.status/1`)

Sources are kept apart; no record merges them into one label. C is derived from the event log and has no record.

| Record | Fields | Pseudonymous | Content | Status |
|---|---|---|---|---|
| **P** (per study case) | `source_case`, `as_of` (`DP1`; `DP2` if a second point is made), `requested` (catalogue ids of the documents and information in the insurer's first outgoing request), `next_action` (action kind), `step` (step id, where the mapping names one), `passage` (verbatim text with page) | ids, kinds | plus `passage` | new |
| **P-later** (per study case) | `source_case`, `requested_later` (catalogue ids, each with a day offset from the decision point), `passage` | ids, offsets | plus `passage` and dates | new |
| P and P-later, provenance | `made_by` (`automated_labeller`), `made_at` (before any run on the cut copy), `sha256`; `owner_check`: checked (bool), result (`agrees`, `corrected`), `checked_at` | yes | plus what was corrected | new |
| **O** | derived from `own_answer.saved` (last before `own_answer.frozen`) | yes | yes | new |
| **A** (per item of every frozen run, and of the comparator) | `item_id`, `label`, `made_at`, `label_set_sha256` (recorded before the first session) | yes | yes | new |
| Prior handling | `expert` (pseudonym inside, label outside), `source_case`, `prior_handling` (bool), `basis` (`file_metadata`), set by the automated labeller | flag | flag and basis | new |
| Status-source hash | `sha256` over P, P-later, the owner's check and A; `recorded_at` (by day 13) | yes | yes | new |
| Benchmark truth for synthetic cases | `truth.facts`, `truth.documents`, `next_actions` | | | exists for synthetic suites only (`quality/evaluate.py:220`, `score`) |

## 6. Formative-session record (`casepath.study.formative/1`)

`schema`, `case` (`D8`), `date` (day 7), the event log of the session (same kinds as section 3.2; not analysed),
`changes` (one row per change made on days 7–9: what changed, commit hash, the gesture or note that caused it) and
`not_changed` (what was deliberately not changed, with one line why). Pseudonymous: counts, kinds and commit hashes;
content: texts. All **new**.

## 7. Exports

| Export | Holds | Leaves the insurer |
|---|---|---|
| **Pseudonymous** (`casepath.study.export/1`) | all records above with relative times, decision points as labels and day offsets, cut hashes, leak flags as booleans, status-source ids and hashes, note lengths, randomised expert labels E1–E5, hashed case-copy and file ids (`h_` + 12 hex, salted, as `quality/scorecard.py` `hashed`), source-case labels A/B/C, item ids, kinds, keys that are catalogue ids, statuses, reason codes, counts, ratios, hashes. No item value, quote, note text, passage, free text or name. Passes the scorecard guard (`quality/scorecard.py`, `guard`) extended with the study's enums. | yes |
| **Content** (`casepath.study.content/1`) | the pseudonymous export plus decision-point dates and the rule's application in words, included-document lists, leak descriptions, the verbatim passages behind P and P-later, item values and texts, before/after values, note texts, free-text additions, absolute times | no |

## 8. Fields kept beyond what the pre-registered analyses need

Kept so that a later, separate paper loses nothing.

| Kept | Export |
|---|---|
| The full event sequence with relative times, not only derived fates | pseudonymous (content-bearing fields in the content export) |
| Raw exposure intervals per item and view | pseudonymous |
| Every version of an item (frozen value, each correction, each undo, each propagated change) | ids and statuses: pseudonymous; values: content |
| Every letter-draft change ratio at each copy, not only the last | pseudonymous |
| The own answer, saved states before the freeze at the reveal | catalogue ids and kinds: pseudonymous |
| Every note with its place and length | place and length: pseudonymous; text: content |
| Every status source separately (P, P-later, O, A), never merged | pseudonymous; passages: content |
| The parity manifest per session and per run | pseudonymous |
| Variation and comparator runs, with their item lists | ids, statuses, hashes: pseudonymous; values: content |
| Agent run events (`run_events`) of the frozen runs | kinds and counts: pseudonymous; full: content |

## 9. Measures and the fields they use

| Measure (pre-registration section) | Fields |
|---|---|
| Final fate (9.1) | `item.corrected`, `item.dismissed`, `correction.undone`, `item.propagated.change = vanished`, `source.opened`, `item.confirmed`, `item.exposed.from_t/to_t`, `case.attested`; item `item_id` |
| Settled / unsettled (4.3) | item `kind`; P, P-later, O |
| Q1 agreement with practice (9.2) | item list (`kind = document`, `next_action`, `step`), `system`, `role`; P, P-later, O |
| Q2 expert agreement, consensus-changed (9.3) | final fate per `expert` and `item_id`; item `kind` |
| Q2 reliance on document requests, sign test (9.3) | final fate of document items; `item.added` (`what = document`, `catalogue_id`); P, P-later |
| Q2 first case: change after the reveal, RAIR and RSR (9.3) | `own_answer.saved` (last before `own_answer.frozen`), final state at `case.closed`, item list; P |
| Q2 checking behaviour (9.3) | final fate; settled status; item `kind` |
| Unsettled items beside C and A (9.3) | final fate of the other four experts; A |
| Q3 work (9.4) | `case.opened`, `case.closed` (`form`), `idle.*`, `active_seconds`; counts of `item.corrected` / `dismissed` / `added`, `note.added`; `letter.copied.change_ratio`; own-answer time from `case.opened` to `own_answer.frozen` |
| Q4 proposals, gate, held-out agreement (9.5) | `item.added` (`what`, `catalogue_id`, `reason`, `node`), `source_case`, `expert`; frozen runs' `result`; Knowledge item fields (`process/knowledge.py`, `new_item`); replay output; P; development reference scores |
| Q5 reasons, reason agreement, notes (9.6) | `reason` on corrections, dismissals, additions, by item kind; `note.added` (`where`, `item_id`) |
| Run-to-run variation (9.6) | item lists of `role = frozen` and `variation` runs, by `kind:key` |
| Decision point, cut, leaks (3.1, 4.4) | cut record; item `leak_flag` |
| Exclusions (11) | `case.closed.capped`, `cap.reached`, `technical.failure`, `prior_handling`, `withdrawn` |
