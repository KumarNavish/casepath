# Event fields for the expert study

Code locations are relative to `casepath-internal/casepath/` at product commit `6f3de061`.
**exists** = present today, at the location named; **partial** = present in another shape (what differs is said);
**new** = must be added. Every record and every export carries `schema` (a string such as `casepath.study.event/1`),
so a later analysis knows which shape it reads. That field is **new** everywhere except where noted.

Times: inside the insurer, absolute UTC times are kept (`at`). Every export replaces them with `t`, seconds since the
session's start (or, for runs, since the study's first frozen run). Dates in a dossier are exported only as whole-day
offsets from the dossier's first document.

**Change (2026-11-12).** The pre-registration's primary endpoint is now the archival comparison at every decision point
of the four sealed dossiers D2, D4, D5, D7 (pre-registration 3.1, 9.2). Added: the decision-point record (1b), P per
decision point with two transcriptions and their agreement (5), the archival-result record (5a), the replay record for
the leave-one-dossier-out analysis (5b). Changed: the run record (1: role `archival`, `dp_index`), the cut copy record
(1a: one row per decision point; the optional second point is removed), the status-source hash (now the archival hash,
5), the exports (7) and the measures table (9).

**Dossier labels.** In the pseudonymous export the study cases are A, B, C (after the lot), the reserve D5 is `R`, and
development dossiers keep their labels D1, D3, D6, D8, D9, D10, D11. Inside, the dossier labels D1–D11 are used
throughout.

## 1. Frozen run record (`casepath.study.frozen-run/1`)

| Field | Meaning | Status |
|---|---|---|
| `schema` | record shape | new |
| `frozen_run_id` | id of the stored run shown to all experts | exists as `runs.id` (`web/store.py`, table `runs`) |
| `source_case` | the sealed dossier (A, B, C after the lot, `R` for D5; internal id inside) | new |
| `dp_index` | the decision point the run belongs to (section 1b) | new |
| `cut_sha256` | hash of the cut copy the run used (section 1a) | new |
| `role` | `archival` (the one CasePath run at a decision point that is not an expert decision point), `frozen` (the archival run at an expert decision point, shown to the experts), `variation`, `comparator` | new |
| `repeat` | 1 for the archival and the frozen run, 2–5 for variation runs, 1 for the primary comparator run and 2–3 for the optional ones at expert decision points | partial: `repeat` in benchmark results (`quality/evaluate.py:409`) |
| `files_sha256` | hash of the case's files | exists (`web/store.py`, `runs.files_sha256`) |
| `workflow_id`, `workflow_version` | routed process | exists (`runs`) |
| `result_sha256` | SHA-256 of the canonical JSON of `runs.result` | new |
| `item_list_sha256` | SHA-256 of the canonical item list (section 2, fields `item_id`, `kind`, `key`, `value`) | new |
| `parity` | the full parity manifest | exists (`parity.py`, `manifest`) |
| `knowledge_content_sha256` | per Knowledge item, hash of `id, family, kind, content, applies_when, status, version` only | new (today's hash includes `stats` and `updated_at`, `parity.py:_digest`) |
| `usage` | model turns and tokens | exists (`result.usage`, `agents/team.py` `finalize`) |
| `deployment` | model deployment name | exists (`runs.deployment`) |

## 1a. Cut copy record (`casepath.study.cut/1`)

One row per decision point of each of the four sealed dossiers (and, for the development analysis, of each development
dossier). The optional second decision point of earlier versions is removed (2026-11-12). Columns "Pseudonymous" and
"Content" say which export carries the field (section 7).

| Field | Meaning | Pseudonymous | Content | Status |
|---|---|---|---|---|
| `schema` | record shape | yes | yes | new |
| `source_case` | A, B, C, `R` in the pseudonymous export; dossier label (D2, D4, D5, D7) in the content export | label | dossier label | new |
| `dp_index` | the decision point (section 1b) | yes | yes | new |
| `reserve_used` | expert sessions only: whether D5 replaced a study case, and the listed reason (`inclusion_failed`, `cut_impossible`, `leak_unremovable`) | yes | yes | new |
| `cut_id` | id of the cut copy; `h_` + 12 hex in the pseudonymous export | hashed | yes | new |
| `cut_sha256` | SHA-256 of the cut copy | yes | yes | new |
| `included_documents` | number of included documents (pseudonymous); list of documents or page ranges with dates (content) | count | list | new |
| `same_day_left_out` | documents of the action's day left out because their order relative to the action cannot be told: count (pseudonymous); list (content) | count | list | new |
| `leak_check` | checked by the study lead, done (bool), leaks found before the run (count) | yes | yes, with descriptions | new |
| `routes_to_common_workflow` | expert decision points only: the inclusion criterion, from routing alone | yes | yes | new |

## 1b. Decision-point record (`casepath.study.decision-point/1`)

One row per decision point: the state of a dossier's file immediately before a recorded outgoing action of the insurer
(pre-registration 3.1). Made after the product's freeze hash exists and before any run on the cut copy.

| Field | Meaning | Pseudonymous | Content | Status |
|---|---|---|---|---|
| `schema` | record shape | yes | yes | new |
| `source_case` | the dossier (labels as in 1a) | label | dossier label | new |
| `dp_index` | 1, 2, ... in the order of the file (`DP1`, `DP2`, ...) | yes | yes | new |
| `cut_sha256` | SHA-256 of the cut copy of this decision point (section 1a) | yes | yes | new |
| `action_offset_days` | the action's date as a whole-day offset from the dossier's first document; never a calendar date | yes | yes | new |
| `action_date` | the calendar date of the action | no | yes | new |
| `merged_actions` | number of same-day outgoing actions merged into this decision point (1 if none) | yes | yes | new |
| `expert_point` | true for the decision point used in the expert sessions (before the first outgoing request; DP1 if there is none) | yes | yes | new |
| `rule_applied` | `outgoing_action`; for the expert point also `first_outgoing_request` or `first_outgoing_action`; plus, content export only, which action and why | code | code and text | new |
| `transcribable` | whether P can be stated from the file; if false, `exclusion_reason` (code; text in content) and the point is excluded for every system | yes | yes, with text | new |
| `decision_points_in_dossier` | total number of decision points of the dossier, set once all are found | yes | yes | new |
| `made_at` | after the product's freeze hash exists (relative time in exports) | yes | yes | new |
| `sha256` | hash of this record | yes | yes | new |

## 2. Item record (`casepath.study.item/1`)

One row per statement of a frozen run (and of a comparator run).

| Field | Meaning | Status |
|---|---|---|
| `schema` | record shape | new |
| `item_id` | `<frozen_run_id>:<kind>:<key>`; stable for all copies of the case | partial: `kind:key` is the feedback target (`web/app.py:71`) |
| `kind` | `step`, `fact`, `deadline`, `document`, `next_action`, `reply`, `open_point`, `summary`, `party`, `timeline`, `answer` | partial: all but `step`, `next_action`, `party` exist as target kinds (`web/app.py:71`) |
| `key` | fact id, document id, step id; for next actions as the product's item function gives it (`casepath/process/items.py`), to be confirmed; list index for open points, clauses, parties, timeline | partial: fact and document ids exist (`result.facts[].fact`, `evaluation.documents[].document`); next-action keys: to be confirmed; index keys are positional and valid only within one run |
| `chain` | true for step, gating fact, deadline, document, next action | new |
| `value` | what CasePath said (fact value; document `required` and `status`; step id; action text) | exists in `result` and `evaluation` (`process/workflows.py:383–395`) |
| `stated_as` | `established`, `presumed`, `conflicting`, `unknown`, `put_to_handler` (open point, waiting_for, depends), `computed` (a date or deadline derived from a stated period; not an established value and not counted as asserted) | partial: `facts[].status`, `evaluation.waiting_for`, `documents[].required = depends` |
| `verdict` | the source checker's verdict | exists (`facts[].verdict`, `documents[].verdict`) |
| `evidence` | citations: file id, quote offsets | exists (`facts[].citations`, `documents[].citations`) |
| `node` | process node the item is there for ("wegen") | partial: `evaluation.documents[].step`; new for facts and actions |
| `origin` | `workflow`, `knowledge#<id>@v<n>`, `agent_edit#<id>` | exists (`source_refs`, `documents[].knowledge`, `agent_edits`) |
| `status`, `required`, `ask`, `part_of`, `reason` | document items: status in the file; whether required; `ask` = `now`, `later` or null (whether the first request asks for it now); the document it is part of; the reason shown | product (`items`, commit ea88df9d) |
| `part`, `chat_only`, `path` | fact items: the alternative a quote supports when the value names alternatives; whether the fact came from the chat only; whether it lies on the path | product |
| `action` | next-action items: the handler's action kind from the catalogue A1–A12, defined in the product's handler process (`casepath/process/workflow_seed/mietmangel-handler.json`); for example A1 first request, A5 assessment, A6 pending with deadline, A12 closing. Replaces the earlier values `request`, `answer`, `close`, `resolve`, which this file listed until 2026-11-11 (and before that `obtain` for `request`) | product |
| `next_in_days` | next-action items: the number of days to the next action, as the product gives it | product |
| `follow_up` | next-action items: the follow-up the product gives with the action, as the product gives it | product |
| `stated`, `rule` | deadline items: the period as stated and how a computed date was derived | product |
| `legal_basis`, `label` | the basis shown with an item; its label in German and English | product |
| `system` | `casepath` or `comparator` | new |
| `source_case`, `cut_sha256` | the study case and the cut copy the item belongs to | new |
| `leak_flag` | set if a leak found after a session affects the item: `leak_id` and date found (content); boolean (pseudonymous) | new |

**Source of the item list (2026-11-11).** From product commit `ea88df9d` the item list is built by one server
function (`casepath/process/items.py`) and returned as `items` on `GET /api/cases/{id}`, with `items_sha256`: the
SHA-256 over the canonical JSON of each item's assertion fields (`item_id`, `kind`, `key`, `value`, `stated_as`,
`status`, `required`, `ask`, `part_of`, `part`, `action`, `stated`, `rule`), sorted by `item_id`. Labels, evidence,
origin, verdict, node, chain, legal basis and reason are not in the hash. The study prefix `<frozen_run_id>:` is
added to `item_id` at the freeze. Evidence is `{file, page, quote}`. Keys of `open_point`, `summary`, `reply` and
`timeline` items are positions and are valid within one run only; analyses across runs (the variation runs) use
chain items, whose keys are ids. Where this file's names differed from the product's, the product's names hold.
From 2026-11-11 the `action` of next-action items is an action kind A1–A12 of the handler process, and next-action
items carry `next_in_days` and `follow_up`. Whether `next_in_days` and `follow_up` enter `items_sha256` is to be
confirmed by the product's builders.

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
| `own_answer.saved` | the three pick-lists: `step` (step id of the handler process or `not_in_list`), `documents` (catalogue ids), `action_kind` (A1–A12) | new |
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
| **P** (per sealed dossier and decision point) | `source_case`, `dp_index` (section 1b); `transcriptions`: two, `t1` (by `automated_labeller`) and `t2` (by `independent_session`: a session that did not build the product and sees neither `t1` nor any CasePath or comparator output), each with `requested` (catalogue ids of the documents and information the insurer requested in the action), `action` (catalogue kind A1–A12 of the frozen catalogue, or `other` when the action in the file fits no entry; `other` counts as disagreement for every system), `next_in_days` and `follow_up` (where the file shows them, else null), `days_to_next_action` (whole days to the insurer's next recorded outgoing action; null at the last decision point), `fact_states` (per deciding fact of the handler process: `fact` id and `state` = `stated`, `open` or `not_addressed`; pre-registration 4.6), `step` (step id, where the mapping names one; kept, but P does not settle the step), `passage` (verbatim text with page), `made_at`, `sha256`; `agreement` (t1 against t2, before settlement, per measure: documents agreeing / documents in either, action kind equal (bool), `next_in_days` equal (bool or null), `days_to_next_action` equal (bool or null), fact states agreeing / facts); `settlements` (one per disagreement: field, the two values, the settled value, `reason` code, `settled_at`; made by the study lead before any run output of the sealed dossiers is opened; both versions kept); `settled` (the fields above as settled), with its `sha256` | ids, kinds, days, agreement counts, settlement codes | plus `passage` and settlement reasons in words | new |
| **P-later** (per study case, expert decision point) | `source_case`, `requested_later` (catalogue ids, each with the `dp_index` and day offset of the later decision point where the insurer requested it), derived from the settled P records of the later decision points | ids, offsets | plus dates | new |
| P, provenance | `t1.made_by` (`automated_labeller`), `t2.made_by` (`independent_session`, with the SHA-256 of its instructions), both `made_at` after the product's freeze hash exists and before any run on the cut copy; `settled_by` (`study_lead`), `settled_at` (before any run output of the sealed dossiers is opened) | yes | yes | new |
| **O** | derived from `own_answer.saved` (last before `own_answer.frozen`) | yes | yes | new |
| **A** (per item of every frozen run, and of the comparator) | `item_id`, `label`, `made_at`, `label_set_sha256` (recorded before the first session) | yes | yes | new |
| Prior handling | `expert` (pseudonym inside, label outside), `source_case`, `prior_handling` (bool), `basis` (`file_metadata`), set by the automated labeller | flag | flag and basis | new |
| Archival hash (replaces the status-source hash, 2026-11-12) | `sha256` over the decision-point and cut records (1a, 1b), both transcriptions and the settled P, P-later, the run hashes, A and the archival results (5a); `recorded_at` (after the freeze; no session before it exists) | yes | yes | new |
| Benchmark truth for synthetic cases | `truth.facts`, `truth.documents`, `next_actions` | | | exists for synthetic suites only (`quality/evaluate.py:220`, `score`) |

## 5a. Archival-result record (`casepath.study.archival/1`)

One row per system and decision point of the four sealed dossiers (pre-registration 9.2). Computed mechanically from
the run's item list and the settled P. Counts and ids only; no content in either export.

| Field | Meaning | Status |
|---|---|---|
| `schema` | record shape | new |
| `source_case`, `dp_index`, `cut_sha256` | the decision point | new |
| `system` | `casepath` or `comparator` | new |
| `run_id`, `role`, `repeat`, `result_sha256` | the run scored (section 1); at expert decision points the frozen run, and the variation runs as separate rows with `repeat` 2–5 | new |
| `run_failed` | true if the run failed; it then counts as not agreeing on (a)–(d) | new |
| `routing_right` | (a): routed to the handler process (bool); null for the comparator, which is given the handler process | new |
| `p_documents` | (b): number of documents in the settled P | new |
| `p_documents_named` | (b): of those, the number the system names to request now (CasePath: document items with `ask = now`) | new |
| `requested_now` | (b): number of documents the system requests now | new |
| `extras` | (b): `requested_now` not in P | new |
| `extras_requested_later` | (b), descriptive: of the extras, the number the insurer requested at a later decision point | new |
| `action_kind`, `action_same` | (c): the system's action kind (A1–A12 or none) and whether it equals P's (P's `other` and no action count as not) | new |
| `next_in_days`, `next_in_days_equal`, `next_in_days_diff` | (d): the system's value; equal to P's where the file shows it (bool, else null); otherwise the signed difference from P's `days_to_next_action` (null where neither exists) | new |
| `follow_up_same` | (d), descriptive: the same as P's, where the file shows it (bool, else null) | new |
| `facts` | (e): for the deciding facts of the steps the system reached, a count per cell of state (`stated`, `open`, `not_addressed`) by treatment (`admitted`, `presumed`, `held_with_question`, `none`) | new |
| `leak_flag` | set if a leak found after the run affects this decision point | new |
| `excluded` | true if the decision point is excluded for every system (not transcribable, cut impossible), with the code | new |
| `parity_sha` | source-tree hash of the run | new |

Fact treatment for CasePath is mapped from the item field `stated_as`: `established` = admitted, `presumed` = presumed,
`put_to_handler` = held with a question, anything else = none. The mapping is to be confirmed by the product's builders
before the freeze (pre-registration 16, item 6).

## 5b. Replay record (`casepath.study.replay/1`)

One row per fold, development dossier, decision point and arm of the leave-one-dossier-out analysis (pre-registration
9.7). Development evidence; never pooled with 5a.

| Field | Meaning | Status |
|---|---|---|
| `schema` | record shape | new |
| `fold` | the held-out development dossier (D1, D3, D6, D8, D9, D10, D11) | new |
| `dp_index`, `cut_sha256` | the decision point of the held-out dossier | new |
| `arm` | `law_only` or `law_plus_practice`; `knowledge_only` marks a run without a law-only variant (both arms on the frozen handler process) | new |
| `process_sha256` | hash of the process variant used (the law-only variant, or the frozen handler process) | new |
| `knowledge_set_sha256`, `knowledge_items` | hash of the Knowledge set (empty for `law_only`) and the number of items in it | new |
| `knowledge_items_left_out` | number of items left out because they came wholly or partly from the held-out dossier (needs each item's source dossiers) | new |
| `stored_run_id` | the stored run the replay used | new |
| `replay_applies` | whether the builders confirm the replay applies at this decision point; if false, the point is listed and left out of both arms | new |
| `p_documents`, `p_documents_named`, `requested_now`, `extras`, `action_same`, `next_in_days_equal`, `next_in_days_diff` | measures (b)–(d), as in 5a, against the development label | new |
| `reference` | `development_label` (one automated labeller who also builds the product) | new |
| `replay_command`, `output_sha256` | the replay command's identity at the frozen commit and the hash of its output | new; output format to be given by the product's builders |

## 6. Formative-session record (`casepath.study.formative/1`)

`schema`, `case` (`D8`), `date` (day 7), the event log of the session (same kinds as section 3.2; not analysed),
`changes` (one row per change made on days 7–9: what changed, commit hash, the gesture or note that caused it) and
`not_changed` (what was deliberately not changed, with one line why). Pseudonymous: counts, kinds and commit hashes;
content: texts. All **new**.

## 7. Exports

| Export | Holds | Leaves the insurer |
|---|---|---|
| **Pseudonymous** (`casepath.study.export/1`) | all records above with relative times, decision points as indexes and day offsets, cut hashes, transcription agreement and settlement codes, archival-result and replay counts, leak flags as booleans, status-source ids and hashes, note lengths, randomised expert labels E1–E5, hashed case-copy and file ids (`h_` + 12 hex, salted, as `quality/scorecard.py` `hashed`), source-case labels A/B/C, item ids, kinds, keys that are catalogue ids, statuses, reason codes, counts, ratios, hashes. No item value, quote, note text, passage, free text or name. Passes the scorecard guard (`quality/scorecard.py`, `guard`) extended with the study's enums. | yes |
| **Content** (`casepath.study.content/1`) | the pseudonymous export plus decision-point dates and the rule's application in words, included-document lists, leak descriptions, the verbatim passages behind both transcriptions of P and P-later, settlement reasons in words, item values and texts, before/after values, note texts, free-text additions, absolute times | no |

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
| Every status source separately (P, P-later, O, A), never merged; both transcriptions of P and every settlement | pseudonymous; passages and reasons in words: content |
| The parity manifest per session and per run | pseudonymous |
| Archival, variation and comparator runs, with their item lists | ids, statuses, hashes: pseudonymous; values: content |
| Agent run events (`run_events`) of the frozen runs | kinds and counts: pseudonymous; full: content |

## 9. Measures and the fields they use

| Measure (pre-registration section) | Fields |
|---|---|
| Final fate (9.1) | `item.corrected`, `item.dismissed`, `correction.undone`, `item.propagated.change = vanished`, `source.opened`, `item.confirmed`, `item.exposed.from_t/to_t`, `case.attested`; item `item_id` |
| Settled / unsettled (4.3) | item `kind`; settled P at the expert decision point, P-later, O (the step: O only) |
| Q1, primary: archival agreement with practice (9.2), (a)–(e), per dossier and pooled | archival-result record (5a): `routing_right`; `p_documents`, `p_documents_named`, `requested_now`, `extras`, `extras_requested_later`; `action_same`; `next_in_days_equal`, `next_in_days_diff`, `follow_up_same`; `facts`; by `system`, `source_case`, `dp_index`; `excluded`, `run_failed`, `leak_flag`. Built from the run's item list (`kind = document` with `ask`; `kind = next_action` with `action`, `next_in_days`, `follow_up`; fact items with `stated_as` on the reached steps; routing from `workflow_id`) and the settled P (`requested`, `action`, `next_in_days`, `follow_up`, `days_to_next_action`, `fact_states`). Range over variation runs at expert decision points: 5a rows with `role = variation`. The step is not part of Q1 |
| Q1 predictions (9.2) | development counts and their 80% intervals (freeze record); pooled counts and denominators from 5a; number of sealed decision points from 1b |
| Agreement of the two transcriptions (9.2, 10) | P `agreement` and `settlements` (5) |
| Deciding facts at each decision point (4.6) | P `fact_states` (both transcriptions and settled); the handler process's deciding facts |
| Development analysis, leave-one-dossier-out replay (9.7) | replay record (5b); development labels at every decision point of the development dossiers; Knowledge items' source dossiers |
| Q2 step (9.3) | final fate of `kind = step` items; `own_answer.saved.step` (O) on the first case, final state at `case.closed` |
| Q2 expert agreement, consensus-changed (9.3) | final fate per `expert` and `item_id`; item `kind` |
| Q2 reliance on document requests, sign test (9.3) | final fate of document items; `item.added` (`what = document`, `catalogue_id`); P, P-later |
| Q2 first case: change after the reveal, RAIR and RSR; CasePath and comparator against O (9.3) | `own_answer.saved` (last before `own_answer.frozen`), final state at `case.closed`, item list; settled P at the expert decision point; comparator item list |
| Q2 checking behaviour (9.3) | final fate; settled status; item `kind` |
| Unsettled items beside C and A (9.3) | final fate of the other four experts; A |
| Q3 work (9.4) | `case.opened`, `case.closed` (`form`), `idle.*`, `active_seconds`; counts of `item.corrected` / `dismissed` / `added`, `note.added`; `letter.copied.change_ratio`; own-answer time from `case.opened` to `own_answer.frozen` |
| Q4 proposals, gate, held-out agreement (9.5) | `item.added` (`what`, `catalogue_id`, `reason`, `node`), `source_case`, `expert`; frozen runs' `result`; Knowledge item fields (`process/knowledge.py`, `new_item`); replay output; P; development reference scores |
| Q5 reasons, reason agreement, notes (9.6) | `reason` on corrections, dismissals, additions, by item kind; `note.added` (`where`, `item_id`) |
| Run-to-run variation (9.6) | item lists of `role = frozen` and `variation` runs, by `kind:key` |
| Decision points, cuts, leaks (3.1, 4.4) | decision-point record (1b); cut record (1a); item and archival-result `leak_flag` |
| Exclusions (11) | decision-point `transcribable`, `exclusion_reason`; archival-result `excluded`, `run_failed`; `case.closed.capped`, `cap.reached`, `technical.failure`, `prior_handling`, `withdrawn` |
| Order at the freeze, no session before the archival hash (4.3, 13) | `made_at` of 1b, both transcriptions, runs and settlements; archival hash `recorded_at`; `session.started` |
