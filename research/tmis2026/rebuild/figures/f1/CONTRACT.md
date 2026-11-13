# Figure 1, "One changed sentence": contract (draft for gate 1)

## Sentence
The reader should see that replacing the one sentence that states a fact with one that leaves it open changes one
checklist line from "requested now" to "held, with one question", and leaves every other need in the same place and
state, because that line is the only need whose rule names the fact the sentence leaves open.

- **Intervention and prediction.** Swap the stated sentence for the open one: line d15 (written assignment of claims
  against third parties; rule `required_when g042 = true`) goes teal → amber and gains one amber question (g042).
  The other 26 needs keep their state.
- **Comparator.** The partner claim: the same file with the stated sentence (`s13-on-…`), drawn at the same positions
  with the same marks.
- **Falsifier.** Any other need changing state between the two stored checklists, or d15 not moving.

## Stored instance (measured)
- Texts: `fresh2/theft/BENCHMARK_FRESH2.json` via `fresh2/theft_fresh2.py`, story 13 (a social worker's e-mail),
  condition `PR_third_party_causer`: claim A `s13-on-PR_third_party_causer`, claim B `s13-unres-PR_third_party_causer`.
  The texts differ in exactly one sentence (built by one replacement; `extract.py` asserts it).
- Checklists: **the core** (checklist-only scope, `CASEPATH_RUN_SCOPE=checklist`),
  `runs/study3/confirm/plans_theft_casepath_checklist.json`, keys `PRODUCT|<text>|0` (run index 0 of 3). The core runs
  no agent that adds lines: both records have no `agent_added_needs` and no added requests or holds (asserted).
  Workflow: `harness/product/workflows/theft-reviewed/household_theft.json`.
- Stored difference: exactly one line (d15 request → hold) and one question (g042), asserted in `extract.py`.
  A: 9 requested, 9 held, 10 questions; B: 8, 10, 11.
- Revision (coordinator, 2026-11-13): an earlier draft used the full product's records, which also held a different
  model-suggested line in each claim. The owner removed the agents from the artefact, so the core is used, and the
  suggestion marks are gone.

## How the pair was chosen, and the honest rate (`find_pair.py` → `pair_summary.json`)
- Tenancy families: the closest pair differs in 8 sentences (separately written messages). Not usable.
- Theft stated/open pairs: 48 pairs × 3 runs = 144 pair-runs (same run index), each exactly one sentence apart.
  "Governed lines" means the needs whose rule names the condition's fact.

| | core (used) | full product (record) |
|---|---|---|
| governed line(s) request → hold | 118 / 144 | 113 / 144 |
| **exactly the governed line(s) and their question(s), nothing else** | **12 / 144** | 15 / 144 |
| something else also moves (another line or question) | 130 / 144 | 126 / 144 |
| checklists identical | 2 / 144 | 3 / 144 |
| other needs moved per pair-run (0 / 1 / 2 / 3 / 4 / 5+) | 14 / 45 / 43 / 28 / 10 / 4 | 18 / 34 / 40 / 39 / 8 / 5 |
| needs that move most often outside the governed ones | d20 (70), d23 (57), d15 (48), d21 (30), d32 (22) | d20 (71), d23 (54), d15 (50), d21 (36), d32 (25) |

d20 = insurer's written demand under default warning (facts g070/g098); d23 = joint expert's determination (g020);
d15 = assignment of third-party claims (g042), which moves in other conditions' pairs.
- The cause is run-to-run variation, not the sentence. The share of texts with the identical checklist in all three
  stored runs is: **core: theft 8 / 128, tenancy 70 / 96**; full product: theft 9 / 128, tenancy 69 / 96. The theft
  workflow has 89 facts, and most records exceed 8 open facts (`first_open_branch` deferral).
- **So this pair-run is selected**, one of the 12 of 144 in the core. The caption says so and gives the rate.
- A true one-sentence pair: the planner will put sealed twins into the registered test (no replay now).

## Element status
| Element | Status | Source |
|---|---|---|
| Page miniatures (one bar per sentence, length ∝ characters, paragraph breaks) | measured | texts above |
| The two sentences (words) | measured | texts above |
| 27 squares per claim, in workflow order, state = request / held / not needed | measured | plan_ids of the two records |
| Amber circles under holds (questions): one per open fact the line waits for, under the hold(s) whose rule names it | measured (attachment formal, from `required_when`) | plan_ids.questions + workflow |
| Rails linking the same need in both claims | formal (same id) | workflow |
| Ink rail and frame on d15 | formal: marks the stored difference | f1_data.json `checklist_lines_changed` |

## Two constructions
- **a (kept, `f1.*`)**: two whole stored records, one above the other. Each has its page, its sentence and its
  27-need strip at identical x positions, with rails joining the same need. *Gain:* both files and both checklists are
  shown whole, as stored. Identity is visible as position, and the one changed column is framed. *Distortion:* the rails take up space. The 8-sentence page can suggest that the rest of the
  file was not read.
- **b (rejected, `f1_b.*`)**: one page and one fused strip. Each need is a pair of half-squares (A over B). *Gain:*
  very compact, and the difference stands out. *Distortion:* it shows a computed diff, not the two stored records. It
  draws one file for two and drops the questions. Rejected; kept in the folder.

## Calibration (images opened)
- `assets/calibration/genomnimatte-figure.png` (sha256 e90b87bb0211b3a0d5bfd6fc0b02727a39e0e76b3d36635194612e9f7c4051f6): a matched edit. The same scene is kept at
  the same coordinates, and only the removed object's layer differs. *Transfer:* the two claims as matched rows, the
  same positions, and the intervention as the only change.
- `assets/calibration/14900912-nerf.png` (sha256 e5e5b4b304623b24eb3da07837a767a639c67291b650b045216ebee7c03215b9): one traced object carried
  through every representation. *Transfer:* the changed sentence is carried by a leader from the page to its words,
  then by column identity to the checklist line.
- *Not copied:* photographic layers, perspective, panel letters.

## Encoding table
| Meaning | Visual | Evidence |
|---|---|---|
| a sentence of the claim | sand bar, length ∝ characters | text |
| the changed sentence | ink bar + leader to its words | text, `changed_sentence_index` |
| need requested now | teal filled square | plan_ids.requests |
| need held | amber filled square | plan_ids.holds |
| question to the customer | amber circle, one per open fact the held line waits for (d10 waits for three); a short bracket when one question serves two holds | plan_ids.questions, required_when |
| need not needed | sand outline square | neither list |
| same need in both claims | thin sand rail (same x) | workflow id |
| the changed need | ink rail + ink frame across both claims | diff |

## Palette
The coordinator's update is used: teal `#008571`, blue `#4A8FD6`; amber `#D9962B`, rust `#B5482F`, indigo `#4B4A9C`
unchanged. Validator (dataviz method, light, paper `#FBF8F1`, all pairs): lightness, chroma, CVD (worst 9.6) and
normal-vision (worst 16.4) pass. Amber against paper warns at 2.37:1, so amber marks are also told apart by shape
(square = hold, circle = question). This session's own re-step (`#00846F`, `#3A7DD6`, `#4E3F98`) is superseded.

## Caption (≤ 45 words)
One stored run: two claims, one sentence apart; the second leaves the third party's role open. Of 27 needs, one turns
from requested to held. Each dot: one question per open fact a held line awaits. Nothing else changed in 12 of 144
stored pair-runs.

(45 words.)

## Self-review (self-assessed; not a reader test)
Cold read of the captionless PNG at print size (re-rendered after the revision; also inspected at 4× on the framed
column): the two rows, the framed column and the teal → amber change are found first. The dots read as questions after
the legend, which now says "one per open fact the line waits for".

| Dimension | Score | Evidence |
|---|---|---|
| Mechanistic insight | 4 | The changed sentence → changed column can be traced. Why that column (the rule naming the fact) is not visible here; it is in Figure 2. |
| Scientific fidelity | 4 | Every mark is from stored files. The caption gives the selection (12/144). The picture alone still suggests more stability than the data has. |
| Visual intuition | 4 | Identical rows read as identical at a glance. |
| Information hierarchy | 4 | The frame is the entry point after the sentences. |
| Encoding originality | 3 | A matched strip, a familiar form. |
| Compositional clarity | 4 | The rails band is large and empty. |
| Annotation | 4 | Words only for the sentences and the legend. |
| Aesthetic refinement | 4 | Legend runs full width; 7 pt minimum respected. |
| Publication readiness | 4 | SVG/PDF (Inter embedded)/PNG at 5.5 × 2.95 in, generated by `extract.py` + `f1.py`. |
| Immediate comprehensibility | 3 | Untested. Without the caption a reader may not know which claim leaves the fact open. |

**Weakest point:** the instance is selected. The figure is truthful about this pair-run, but the core's theft
checklist differs between runs in 120 of 128 texts, so "nothing else moves" is true here (12 of 144) and not in
general. The registered twins should fix it; drawing cannot.

## Files
`extract.py` → `f1_data.json`; `f1.py` → `f1.svg`, `f1.pdf`, `f1.png` (kept a) and `f1_b.*` (rejected b);
`find_pair.py` → `pair_search.json`, `pair_summary.json`.
