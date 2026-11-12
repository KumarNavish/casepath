# Study 4 file generator (model-free parts)

Development material (SPEC.md step 2c). Builds benchmark files from a rule set: the designed state of each file,
the engine reference, the clean-room bundle for the two blind evaluators, the per-file bundle for the writing
session, and the assembly after writing (blind-check comparison, one rewrite, scan noise, final manifest). No
script calls a model or the network. Standard library only (Python 3.11+).

## Pipeline

| Step | Script | Reads | Writes (under `study4/dev/<regime>/`) |
|---|---|---|---|
| 1 design | `design.py` | `rules.json`, `workflow/<type>.json` (presumptions), optional `constraints.json` | `designs/<id>.json`, `designs/MANIFEST.json`, `MARGINALS_design.json` |
| 2 engine reference | `reference.py` | designs, workflows, the product's evaluator at the tested commit | `references/<id>.json`, `references/MANIFEST.json`, `MARGINALS_reference.json` |
| 2b clean-room bundle | `cleanroom_bundle.py` | designs, `rule_text.md`, `rules.json` (catalogue only) | `cleanroom_bundle/` |
| 3 writer bundles | `writer_bundle.py` | designs, `rules.json` (questions, notes, catalogue), `STYLE.md` | `writer_bundles/<id>.json`, `KEYS.json` (operator only), `MANIFEST.json` |
| 3 writing | a writing session, `WRITER_TASK.md` | one bundle | `written/<id>.json` |
| 4 blind check | `assemble.py blind-in`, then a blind-check session, `BLIND_CHECK_TASK.md` | text, attachments, questions | `blindcheck/in/`, `blindcheck/out/` |
| 4 compare | `assemble.py compare` | blind-check output, design (or round-2 target), keys | `blindcheck/compare_round<k>.json` |
| 4 classify / rewrite | `assemble.py classify` (round 1; uses the product's evaluator) | compare output, blind quotes, designs, references, dependency rules, item notes | `blindcheck/classify_round1.json`, `blindcheck/CLASSIFY.md`, `rewrite/<id>.json` (files to rewrite only) |
| 5-7 finalise | `assemble.py finalize` (uses `noise.py`) | all of the above | `final/<id>/`, `final/MANIFEST.json` |
| repair round k >= 3 | `assemble.py repair-prepare`, then `blind-in` / `compare --round k`, then `finalize` | final manifest and records, a list of files whose text differs (or an earlier repair comparison) | `rewrite_r<k>/PLAN.json`, `rewrite_r<k>/bundles/<id>.json`, `blindcheck/in|out/round<k>/`, `compare_round<k>.json`; `finalize` moves dropped files' folders to `dropped/` |

```
cd research/tmis2026/study4
python3 -I -B generator/design.py --regime tenancy            # seed 20261112, 15 files per level
python3 -I -B generator/reference.py --regime tenancy
python3 -I -B generator/cleanroom_bundle.py --regime tenancy
python3 -I -B generator/writer_bundle.py --regime tenancy
# ... writing session, then:
python3 -I -B generator/assemble.py blind-in --regime tenancy --round 1
# ... blind-check session, then:
python3 -I -B generator/assemble.py compare --regime tenancy --round 1
python3 -I -B generator/assemble.py classify --regime tenancy
# ... writing session on rewrite/<id>.json, then blind-in / blind check / compare --round 2, then finalize
python3 -I -B generator/test_generator.py                       # tests (temporary folders only)
```

## Running it on your own rule set

Put your rule set in a folder with `rules.json` (schema of SPEC.md item 6: `types[]` with `id`, `title`,
`defining_event`, `facts[]` with `id`, `question`, optional `always_stated` and `generator_note`; `steps[]` with
`reached_when`; `documents[]` with `step`, `needed_when`, `mandatory`, `must_show`; `presumptions[]`; `stops[]`
with `when`), `rule_text.md`, and `workflow/<type id>.json` in `casepath.workflow/1`. Then pass
`--rules-dir <folder> --out <your dev folder>` to every script. Nothing in the scripts names a fact, document or
type; everything is read from these files:

- the defining event, `always_stated` facts and `generator_note`s from `rules.json`;
- what an unmentioned fact becomes from the workflow's presumptions with `applies: "unstated"` (statutory
  presumptions and the intake convention as encoded, SPEC 6a); without a workflow, from `rules.json`'s
  `presumptions` (then `reference.py` cannot run);
- optional documents from `mandatory: false` (or workflow `optional: true`);
- the routing fact for the evaluator from the workflow's `applies_when`;
- stops and their ids from `rules.json` `stops` (an unnamed stop is called `stop_<n>`).

Only the types listed under `types` are drawn. An out-of-scope case a rule set describes in prose (theft's
`outside_both_types`, routing answer `other`) is **not generated**: routing to "other" is not tested by these
files.

### Dependency rules (`constraints.json`, optional, in the output folder)

Logical dependencies between facts, and between attachments and facts, that the rule set does not encode but a
coherent file must respect, as data. **Principle (from the round-1 blind check, 2026-11-12): a designed "not
mentioned" is not allowed where a stated answer or a required attachment item implies an answer; the design takes
the implied state.** Kinds:

| kind | form | effect |
|---|---|---|
| (none) | `{"if": cond, "then": {"fact", "in": [...], "set": state}, "reset_if"?}` | when `if` holds and the `then` fact's state is not in `in`, it is set to `set`; if that fact is protected (defining event, open fact), the single `if` fact is reset to `reset_if` (default not mentioned; stated false for an always-stated fact) |
| `stated_only_if` | `{"fact", "if"}` | the fact is not mentioned unless `if` holds |
| `stated_if` | `{"fact", "if", "set": state or "drawn", "set_default"?}` | when `if` holds, the fact may not be "not mentioned": it takes its drawn value (or `set_default`, default stated false), also where the reachability rule would leave it unmentioned |
| `attachment_implies` | `{"document", "item"?, "fact", "implies": [states], "set": state or "drawn"}` | a supplied attachment that shows the item (or, without `item`, the document itself) answers the fact: a not-mentioned fact takes `set`; if the fact is protected (open fact, defining event) or stated otherwise, the attachment is not supplied (it would settle or contradict it); logged as `attachment_withdrawn` |
| `claimant_sex` | `{"if": cond, "sex": "female" or "male"}` | fixes the claimant's sex; the first name is then drawn from that sex's list (`lexicon.SEX`); otherwise 50/50 |

`cond` is a condition over designed states: `{"fact", "state" | "in"}`, `{"all": [...]}`, `{"any": [...]}`,
`{"not": ...}`. Order in `design.py`: fact rules, then the reachability rule for always-stated facts (a fact a rule
has set is left alone), fact rules again; attachments are drawn; attachment rules; fact rules once more; a supplied
attachment that is no longer definitely needed is withdrawn. Every adjustment is logged in the design
(`constraint_adjustments`). The files: tenancy (deposit intended / made; landlord unaware / learned orally; a
knowledge proof answers both; an increase notice's reasons answer the cost question; the landlord's reasons answer
the arrears question), theft (attached vouchers answer the vouchers question; a bicycle voucher answers both
bicycle questions), dismissal (notice period vs. 180 days and claim pending; the protected-period order question is
stated exactly when a protected period is stated or open; no notice answers the 180-day question; the contract's
start date answers the probation question; a pregnancy makes the claimant female).

### Item notes (`generator/items/<regime>.json`, generator data, not part of the rule set)

Per must_show item (matched by type or "*", document, exact item text; when a rule-set revision rewords an item,
the entry's `item` is renamed to the new wording and nothing else changes): `conditional` (overrides the wording
heuristic), `applies_when` (a condition over designed states; when it holds a conditional item must be shown and
can be the missing item, when it does not the item is left out), `checkable_as` (what a document must literally
contain for the item to count as shown; passed into the writer bundle and the blind-check input), `observed` (the
round-1 mismatch behind the entry) and `rule_set_wording` (why the item's own wording is a problem, for the
planner; kept as the record after revision 2 addressed it). The missing item of an insufficient attachment is drawn
only from items that must be shown in that file.

**Earlier wordings (`rules/<regime>/MUST_SHOW_WORDING.json`).** Revision 2 of the rule sets (SPEC.md item 6c,
2026-11-12) reworded must_show items; designs, keys and stored blind-check records name an item by the wording of
their time. `Regime.current_item` maps an earlier wording to the current one (written by the rule set's
`tools/build.py`), and the writer bundle, `compare` and `classify` use it, so a design's missing item is the same item
under either wording. Since revision 2 a conditional item uses the fixed form "Only if the file states that
<condition>: <thing>. Otherwise this item does not apply.", which the wording heuristic also recognises.

## Parameters (`design.py`; every one is a command-line option)

| Parameter | Default | What it does, and why this default |
|---|---|---|
| `seed` | 20261112 | Master seed. Each file has its own generator seeded from (seed, regime, level, index), so files are independent draws and a file does not change when another is added. |
| `per_level` | 15 | Files per share level (SPEC item 8: 60 per regime). |
| `levels` | 0,10,25,50 | Percent of files with at least one open fact. **Rounding: per level, round half up**: 0, 1.5 -> 2, 3.75 -> 4, 7.5 -> 8 of 15 (realised 0, 13.3, 26.7, 53.3%). 16 per level would give exact 25/50% but 1.6 files at 10%, so 15 (the specified 60 files) was kept. |
| `open_facts_per_open_file` | 1 | One open fact per open file, drawn uniformly over the type's deciding facts, defining event included. |
| `denied_share` | 0.10 | Defining event stated false in round(0.1 x 15) = 2 files of every level (13.3%), flagged `denied_event`. Denied files are disjoint from open-fact files. |
| `p_branch_true / false / not_mentioned` | 0.35 / 0.20 / 0.45 | State of a non-open branch fact. Not mentioned is the commonest, as in real intake and as the intake convention is meant to be exercised; true is more frequent than false because true is the circumstance a party raises (SPEC 6b) and is what makes the conditional documents needed; false is kept at a fifth so that explicit denials are tested. With these values every document of every type is needed (requested, held or present) in some files: see the marginals. |
| `p_always_stated_true` | 0.50 | An `always_stated` fact has two ordinary alternatives, so both are equally likely. |
| `stop_lean_factor` | 0.25 | For a fact whose one value alone fires a stop (theft's household perpetrator and missing away cover, dismissal's notice during probation), that value's weight is multiplied by 0.25. A file that stops at once carries no checklist to score, and the sealed set should not spend a fifth of its files there; the denied-event files already contribute a fixed 10% of stopped files at every level. With 0.25 such stops are still reached at a few percent of files each (per-file probabilities in the final report of 2026-11-12). Tenancy has none (its only stops are on the defining event). No coverage rule forces a stop to appear: at the sealed set's size chance evens out. |
| `always_stated_where_reachable` | true | **An always-stated fact is stated only in files where its step can be reached; elsewhere it is not mentioned.** A step "uses" a fact when the fact appears in a step's `reached_when`, in the `needed_when` of a document on a step not ruled out, or in a stop's `when`; the fact is stated (as drawn) when at least one such use is not false given the file's other designed states (unresolved facts count as possibly true), and left not mentioned otherwise. Such a fact has no presumption, so it is unresolved, and since nothing that uses it can be reached it changes no document's state: `reference.py` confirms this per file with the product's evaluator (`unreached_always_stated_check`). Denied-event files fall under it too. Logged per design in `always_stated_not_mentioned` with the drawn value. |
| `denied_branch` | false or not mentioned | In a denied-event file the branch facts usually presuppose the event (damage from a defect that does not exist), so they are stated false or not mentioned (in the ratio 0.20 : 0.45); an `always_stated` fact is drawn as usual and then, its steps being unreachable, left not mentioned. The reference is the stop whatever they are. |
| `p_supply` | 0.35 | A mandatory document the design definitely needs is attached. |
| `p_supply_optional` | 0.30 | An optional document whose need definitely holds is attached (theft's police report). |
| `p_sufficient` | 0.50 | An attached document shows every `must_show` item; otherwise exactly one item, drawn uniformly over the items that apply in every file, is missing (conditional items such as "any ... clause", "where ...", "if any" are never the missing item). Half and half, as in Study 3 (25 / 26). |
| `allow_irrelevant_attachments` | false | **Decision:** only documents the design definitely needs are ever attached: never one that is not needed, never one held behind the open fact (it could settle the open fact), never one on a step the stated facts make unreachable. This keeps the reference to request / present and avoids attachments that reveal unmentioned facts. |
| `german_share` | 0.50 | Exact count per level, round half up (8 of 15). |
| `noise_share` | 0.20 | Exact count per level, round half up (3 of 15). |
| `words` | 150,400 | Length of the message (SPEC item 3). |

Story seed per file: claimant, the other party as a person and as an organisation, a third person, a Swiss
municipality and canton, a street, the date written (February to October 2026), the date of the main event (6 to
75 days before), three earlier dates, three amounts in CHF, and a topic-order seed. Lists are in `lexicon.py`
(common first names and surnames combined at random; organisation names composed from neutral landscape words; no
register was consulted, so check a final set against a commercial register before publication). Where a question
names a time span (for example "within 180 days"), the seed gives one date on each side of the span relative to
the date written; the writer uses the one that makes the designed answer true and the blind check verifies it.
A question that depends on dates without naming a span (for example "has the notice period ended?") is left to the
writer and the blind check.

## The engine reference (`reference.py`)

The product's own evaluator (`casepath/process/workflows.py` at the tested commit, imported read-only, no bytecode
written) runs each design under the intake convention: stated facts are established; an unmentioned fact is
filled by the product's own `presumed()` (no row recorded), so a fact without a presumption stays unresolved; an
open fact is recorded as raised and left open, so no presumption fills it; supplied attachments are findings
(`present` / `unusable`), `checked=True`. States: not on the checklist -> `not_needed`; `depends` -> `hold` with
the facts it waits for; `yes` -> `request` / `present_sufficient` / `present_insufficient`; optional ->
`not_needed` unless supplied, then `present_*`, never a request. **A supplied insufficient document is requested
again** (`request: true`), as the product's next actions (`obtain` for `unusable`) and the earlier study's scorer
(`supplied_insufficient` counted with `required_now`) treat it. Each reference is recomputed from `rules.json`
alone (`genlib.rules_outcome`, exact deferral over the unresolved facts) and differences are listed; on all three
regimes there are none. The recomputation follows the rule text's "How to read steps and stops" (`reading_of_stops`):
steps are taken in order, a stop ends the process at its step, no later step is reached and no later document is
requested or held, and documents of steps reached before the stop keep their state. `rules.json` writes each stop
into the `reached_when` of every later step, so reading steps from `reached_when` gives exactly that; the test
`test_rules_recomputation_follows_engine_walk` checks it against the product's in-order walk under every
assignment of every type's facts.

## The writing session and the blind check, and why another model family

The **writing session** turns one bundle into a message and its attachments (`WRITER_TASK.md`, `STYLE.md`). The
bundle holds the questions with their designed answers under neutral labels in a shuffled order, each with its
`not_this` line, the story seed, the language and the attachments to write; in a denied-event file it also holds
the other types' central-event questions under `central_event_denied.must_not_state`. It holds no fact or document
ids, no rule text beyond the questions, their `not_this` lines, the documents' titles and must_show items and any
`generator_note`, no workflow, no reference, no product code and no prompt of any design (checked by the tests).

The **blind-check session** sees only a text, its attachments (with each document's title, must_show list and the
`checkable_as` notes), the questions with their `not_this` lines, the routing question and the other types'
central-event questions; it states each fact and each other-type event as stated true / stated false / open / not
mentioned, gives the routing value the text supports (or none) and says of each attachment whether it is
sufficient or which item is missing (`BLIND_CHECK_TASK.md`). `assemble.py compare` checks for an exact match on
every fact and attachment (and the designed length), and, in a file whose design denies its central event, that no
other type's central event is read as stated or open and that the routing answer names no other type.

**Why (2026-11-12, `lint/DIAGNOSIS.md`).** In 6 theft and 2 dismissal development files the denial of the designed
type's event stated another type's event ("it was not stolen at home, it was taken at the gym"), so the reference
(the designed type's stop) was wrong for the text; the round-1 blind check could not see it because it was asked
only the designed type's questions. And 14 errors came from texts whose wording fell under a `not_this` line the
writer and the blind check never saw. Inputs and bundles made before that date (rounds 1 and 2 of the development
sets) carry neither.

### Blind check, classification and the keep rule (the pipeline's rule from 2026-11-12)

`assemble.py classify` (after round 1) classifies every differing file: (a) the engine reference recomputed from the
states as read (questions as read, attachments' sufficiency as read) against the design's reference:
reference-equivalent or not, with the documents and stop that change; (b) per question difference, the dependency
rules whose antecedent holds in the design and which imply the read state (the implying answer or attachment item
is named, with the blind quote); (c) per attachment difference, the must_show items at issue with their item notes.

**Keep rule.** A file is kept without rewrite if it is exact, or if every difference is a designed "not mentioned"
read as "stated false" **and** the file is reference-equivalent; its recorded fact states then become the states as
read (`facts`), the designed ones are kept beside them (`facts_designed`), and it is flagged `kept_as_read`, with the
reference recomputed from the states as read. Every other differing file gets the one rewrite. Its round-2 target is
the designed states, except where a dependency rule makes a designed "not mentioned" impossible and an implied state
(the one read, else the rule's) leaves the reference unchanged: then the target takes it (`target_revisions`), the
rewrite request says so (`answers_changed`), and the final record is flagged `revised_by_implication`. The rewrite
request carries the file's bundle rebuilt with the current item notes. A file that still differs after round 2 is
dropped and counted.

**Keep rule in repair rounds (2026-11-12).** The same rule applies, in both directions, to a file re-checked (not
rewritten) in a repair round: if its reading differs from its recorded states only by facts read "not mentioned"
where recorded "stated false", or the reverse, and the engine reference from the states now read equals its stored
reference, `compare` counts it as matching (`kept_by_keep_rule` in `compare_round<k>.json`) and `finalize` makes the
states now read its recorded states. Where they equal the designed states the `kept_as_read` flag and the
`facts_designed` copy are dropped (manifest `repair.states: "as designed"`); otherwise the flag stays with the new
states. The reference file is kept byte-identical; the manifest records the changed facts and the previous hashes.

**Dropping instead of rewriting in repair rounds (development sets only, 2026-11-12).** In a repair round, a
development file that differs from its design after first use may be dropped instead of rewritten, and is counted.
The planner records each such drop, with its reason, in `dev/<regime>/DECISIONS.json` (`{"drop": {file_id: {"reason",
"decided"}}}`); `finalize` drops the file with "planner decision: <reason>" in the manifest and does not wait for a
rewrite round for it. Planner drops for other stated reasons (a designed defect that a rule-set revision removed) use
the same file. The sealed set keeps the original rule: one rewrite, then drop.

Both sessions must be of a model family that is **not evaluated** in the study. If an evaluated model wrote the
texts, its own phrasing habits would be what it later reads, which would favour that model; if it did the blind
check, the check would certify texts that model happens to read as designed. The writing and the blind check
should also be different sessions (ideally different models of that family), so that the check is not the writer
reading its own intention back. The study names sessions by role only.

## Scan noise (`noise.py`)

Seeded per file and document; applied in `finalize` to files flagged `scan_noise`, to the message and its
attachments. Character confusions (rn/m, l/1, O/0), lost diacritics, line breaks at a per-file width with
hyphenation of long words, and dropped letters at 0.4% (under 1% of characters). The clean text is kept beside the
degraded one (`*.clean.txt`), and `noise.json` holds every edit, from which `noise.restore` rebuilds the clean text
exactly (tested).

## Known limits

- Fact dependencies the rule set does not encode need a `constraints.json`; without one the generator can draw
  incoherent combinations. The rules are found by reading blind-check mismatches, so a dependency no file has
  exposed yet is not covered.
- Until 2026-11-12 the wording heuristic marked any item beginning with "where" as conditional, so theft's "where
  and when it was bought" was never required in round 1 (12 stolen-items lists differed); the round-1 writer
  bundles in `dev/` carry that error, the rewrite bundles do not.
- `design.py` and `writer_bundle.py` refuse to overwrite designs or bundles in a folder that already holds written
  files (`--force` to override).
- The reachability rule leaves theft's `burglary_or_robbery` unmentioned in every at-home file where no lock change
  is stated true or open (its only use is the lock-change invoice): the writer must tell a theft at home without
  saying whether anyone broke in.
- The writer bundle contains the questions, their not_this lines and must_show items verbatim; some name article
  numbers (dismissal) or conditions ("Ziff."). The tests allow these strings and nothing else of the rule text.
- Repair rounds reuse the round-1 labels (KEYS.json); a rewrite bundle is built from the final record's states (the
  states as read for a file kept as read).
- Seed-specific marginals: at seed 20261112 dismissal type 2's three combined stops are never reached, only
  pending (expected per 60 files: `b_stop_no_objection` 1.7, `b_stop_continued` 3.7, `b_stop_time_limit` 0.2; the
  dependency file removes only the incoherent route to the last). See `MARGINALS_*.json`.
