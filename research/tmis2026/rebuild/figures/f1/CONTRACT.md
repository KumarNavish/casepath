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
- Checklists: `runs/study3/confirm/plans_theft_casepath.json`, keys `PRODUCT|<text>|0` (the full product, default
  settings, run index 0 of 3). Workflow: `harness/product/workflows/theft-reviewed/household_theft.json`.
- Stored difference: one line (d15 request → hold), one question (g042). **And one more difference, drawn:** each
  record stores one extra line a model (`process_builder`) suggested outside the rules (`agent_added_needs`,
  `required: suggested`; not in the scored plan). The two suggestions differ (A: the representative's written
  authorisation; B, in German: the contractor's work order and access records). Drawn as the dashed blue square with ≠.

## How the pair was chosen (search by script, `find_pair.py` → `pair_search.json`, `pair_summary.json`)
- Tenancy families: the closest pair differs in 8 sentences (separately written messages). Not usable for a
  one-sentence figure.
- Theft stated/open pairs: 48 pairs × 3 runs = 144 pair-runs, each pair exactly one sentence apart.
  In 113 of 144 the dependent line(s) move request → hold. In **15 of 144** that is the *only* checklist difference
  (with its question). In the rest, 1–12 other lines also differ.
- Cause of the other differences: run-to-run variation, not the sentence. The same text gives the same checklist in
  all three runs for only 9 of 128 theft texts (tenancy: 69 of 96). The theft workflow has 89 facts; most records hold
  more than 8 open facts, and the product then switches to `first_open_branch` deferral.
- **So this instance was selected.** It is a real stored pair-run, but it is one of 15 of 144 in which the run-to-run
  variation happened not to touch other lines. The caption or text must say so. The figure does not show that the
  rest of the checklist is stable from run to run. That question belongs to Figure 7.

## What would give a true one-sentence pair (for the planner)
1. **No model call (replay):** take claim A's stored readings, replace only g042's three readings with claim B's
   stored readings, and recompute the checklist in code. This isolates the sentence's effect by construction. It is
   formal, not an independent run, and should be labelled that way.
2. **A run:** one-sentence stated/open variants of tenancy claims (smaller workflows, more stable). Either write them
   or take the theft on/unres pairs, and run the full product k = 5 per text. Then report how often the checklists
   differ only in the dependent line, across all run pairings, not only same-index runs. The cost is about 26 calls
   per text, on the order of the Study 3 product cost per text; pricing it is for the planner's costed plan.

## Element status
| Element | Status | Source |
|---|---|---|
| Page miniatures (one bar per sentence, length ∝ characters, paragraph breaks) | measured | texts above |
| The two sentences (words) | measured | texts above |
| 27 squares per claim, in workflow order, state = request / held / not needed | measured | plan_ids of the two records |
| Amber circles under holds (questions), one per stored question, under the hold(s) whose rule names it | measured (attachment formal, from `required_when`) | plan_ids.questions + workflow |
| Rails linking the same need in both claims | formal (same id) | workflow |
| Ink rail and frame on d15 | formal: marks the stored difference | f1_data.json `checklist_lines_changed` |
| Dashed blue square and ≠ | measured | `product_extra.agent_added_needs` |

## Two constructions
- **a (kept, `f1.*`)**: two whole stored records, one above the other. Each has its page, its sentence and its
  27-need strip at identical x positions, with rails joining the same need. *Gain:* both files and both checklists are
  shown whole, as stored. Identity is visible as position, and the one changed column is framed. The model's
  suggestion is visible. *Distortion:* the rails take up space. The 8-sentence page can suggest that the rest of the
  file was not read.
- **b (rejected, `f1_b.*`)**: one page and one fused strip. Each need is a pair of half-squares (A over B). *Gain:*
  very compact, and the difference stands out. *Distortion:* it shows a computed diff, not the two stored records. It
  draws one file for two. It dropped the questions and the suggestion, which hides a stored difference. Rejected.

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
| question to the customer | amber circle under the hold whose rule names it; a short bracket when one question serves two holds | plan_ids.questions, required_when |
| need not needed | sand outline square | neither list |
| same need in both claims | thin sand rail (same x) | workflow id |
| the changed need | ink rail + ink frame across both claims | diff |
| a model's suggestion outside the rules | dashed blue square; ≠ when the two differ | agent_added_needs |

## Palette (validator of the dataviz method, light, paper `#FBF8F1`, all pairs)
The brief's values failed: blue `#2F5D9E` against indigo `#4B4A9C` (normal ΔE 5.7, deutan 3.0), teal chroma below the
floor, and blue against teal (normal ΔE 13.5). Re-stepped, keeping the hues: **teal `#00846F`, blue `#3A7DD6`,
indigo `#4E3F98`**, with rust `#B5482F` and amber `#D9962B` unchanged. This passes the lightness, chroma, CVD
(worst 9.4) and normal-vision (worst 16.6) checks. Amber against paper warns at 2.37:1, so amber marks are always
also told apart by shape (square = hold, circle = question). **All seven figures should use the re-stepped values.**

## Caption (≤ 45 words)
Two stored claims, one sentence apart: the second leaves open whether a third party caused the loss. Of 27 document
needs, one changes: requested now becomes held, with one question. A model's extra suggestion, outside the rules,
also differs. Selected: in 15 of 144 stored pair-runs nothing else changes.

(42 words.)

## Self-review (self-assessed; not a reader test)
Cold read of the captionless PNG at print size: the two rows, the framed column and the teal → amber change are found
first. The suggestion square is found last. The questions read as "something attached to holds" only after the legend.

| Dimension | Score | Evidence |
|---|---|---|
| Mechanistic insight | 4 | The changed sentence → changed column can be traced. Why that column (the rule naming the fact) is not visible here; it is in Figure 2. |
| Scientific fidelity | 4 | Every mark is from stored files. The selection (15/144) and run-to-run variation must be stated in the caption; the picture alone suggests more stability than the data has. |
| Visual intuition | 4 | Identical rows read as identical at a glance. |
| Information hierarchy | 4 | The frame is the entry point after the sentences. |
| Encoding originality | 3 | A matched strip, a familiar form. |
| Compositional clarity | 4 | The rails band is large and empty. |
| Annotation | 4 | Words only for the sentences and the legend. |
| Aesthetic refinement | 4 | Legend runs full width; 7 pt minimum respected. |
| Publication readiness | 4 | SVG/PDF (Inter embedded)/PNG at 5.5 × 2.95 in, generated by `extract.py` + `f1.py`. |
| Immediate comprehensibility | 3 | Untested. Without the caption a reader may not know which claim leaves the fact open. |

**Weakest point:** the instance is selected. The figure is truthful about this pair-run, but the theft checklist
moves between runs in 119 of 128 texts, so "nothing else moves" is true here and not in general. Fix by the replay
or run above, not by drawing.

## Files
`extract.py` → `f1_data.json`; `f1.py` → `f1.svg`, `f1.pdf`, `f1.png` (kept a) and `f1_b.*` (rejected b);
`find_pair.py` → `pair_search.json`, `pair_summary.json`.
