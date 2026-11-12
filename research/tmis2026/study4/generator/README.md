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
| 4 compare / rewrite | `assemble.py compare` | blind-check output, design, keys | `blindcheck/compare_round<k>.json`, `rewrite/<id>.json` |
| 5-7 finalise | `assemble.py finalize` (uses `noise.py`) | all of the above | `final/<id>/`, `final/MANIFEST.json` |

```
cd research/tmis2026/study4
python3 -I -B generator/design.py --regime tenancy            # seed 20261112, 15 files per level
python3 -I -B generator/reference.py --regime tenancy
python3 -I -B generator/cleanroom_bundle.py --regime tenancy
python3 -I -B generator/writer_bundle.py --regime tenancy
# ... writing session, then:
python3 -I -B generator/assemble.py blind-in --regime tenancy --round 1
# ... blind-check session, then compare, rewrite once, blind-in/compare round 2, finalize
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

`constraints.json` (optional, in the output folder) states logical dependencies between facts that the rule set
does not encode but a coherent file must respect, as data: `{"if": {"fact", "state" | "in"} | {"all": [...]},
"then": {"fact", "in": [...], "set": state}, "reset_if"?: state}`. When the `if` holds and the `then` fact's state
is not allowed, the `then` fact is set to `set`; if that fact is protected (the defining event or the open fact),
the `if` fact is reset to `reset_if` (default not mentioned; stated false for an `always_stated` fact). A second kind,
`{"kind": "stated_only_if", "fact", "if": {...} | {"any": [...]} | {"all": [...]}}`, leaves the fact not mentioned
in files where the `if` does not hold: an explicit, data-stated instance of the reachability rule above, for a
fact whose question itself limits when it is asked. Every adjustment is logged in the design
(`constraint_adjustments`). Files exist for tenancy (deposit intended/made;
landlord unaware vs. learned orally; increase open vs. a stated cost reason) and dismissal (employment cannot have
ended more than 180 days ago, nor a claim be pending after it, while the notice period has not ended; and
`notice_before_protected_period` is stated only when at least one of the three protected-period facts is stated
true or open, because its question is "not asked where no protected period is raised").

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
bundle holds the questions with their designed answers under neutral labels in a shuffled order, the story seed,
the language and the attachments to write; it holds no fact or document ids, no rule text beyond the questions,
the documents' titles and must_show items and any `generator_note`, no workflow, no reference, no product code and
no prompt of any design (checked by the tests).

The **blind-check session** sees only a text, its attachments (with each document's title and must_show list) and
the questions, and states each fact as stated true / stated false / open / not mentioned and each attachment as
sufficient or which item is missing (`BLIND_CHECK_TASK.md`). `assemble.py compare` requires an exact match on every
fact and attachment (and the designed length); a differing file is rewritten once; a file that still differs is
dropped and counted in the final manifest.

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
  incoherent combinations.
- The reachability rule leaves theft's `burglary_or_robbery` unmentioned in every at-home file where no lock change
  is stated true or open (its only use is the lock-change invoice): the writer must tell a theft at home without
  saying whether anyone broke in.
- The writer bundle contains the questions and must_show items verbatim; some name article numbers (dismissal) or
  conditions ("Ziff."). The tests allow these strings and nothing else of the rule text.
- Seed-specific marginals: at seed 20261112 two of dismissal type 2's combined stops are never reached
  (`b_stop_continued`, expected 3.7 in 60 files; `b_stop_time_limit`, expected 0.2). See `MARGINALS_*.json`.
