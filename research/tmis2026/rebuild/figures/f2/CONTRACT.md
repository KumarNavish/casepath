# Figure 2, "The journey of one sentence": contract (draft for gate 1)

## Sentence
The reader should see that the model contributes only quoted words and a verdict per reading, and that the quotation
check, the agreement of the three readings, the fact's value, the rule and the checklist line are computed by code,
because the checklist line can be followed back across the one rule, along three lines, to the words each reading
quoted.

- **Intervention and prediction.** The same as Figure 1 (same case): the stated sentence becomes the open sentence.
  The three readings turn true → open, quoting the open words. The fact turns true → open, the rule's diamond turns
  ink → amber, and the line turns request → held + one question. Nothing above the rule is computed. Below the rule,
  nothing is produced by a model, except the stored suggestion (see "the record shows otherwise").
- **Comparator.** The partner lane: the stated sentence through the same stages, at the same x positions.
- **Falsifier.** A stored reading without a quotation found in the file that still counts. A value admitted without
  all three readings agreeing. A checklist line that does not follow from the rule and the value.

## Stored instance (measured), the same case as Figure 1
- Records: `runs/study3/confirm/plans_theft_casepath.json`, `PRODUCT|s13-on-PR_third_party_causer|0` (lane A) and
  `PRODUCT|s13-unres-PR_third_party_causer|0` (lane B).
- The three readings: the product's response cache `runs/product/cache/<key>.json` (keys in each record, in call
  order; the full readings with 90 conditions; a 2-condition requote in lane A is skipped). Fact
  `g042_rev_92ab8925` ("…the loss was caused or increased through the fault of a third party").
  - A: true, "An identified building contractor caused the loss and their identity is known." (×2); true, "An
    identified building contractor caused the loss" (×1).
  - B: open, "whether an identifiable third party caused or enlarged the loss has not been established." (×3).
  - All six quotations occur word for word in the file (`found_in_file`, substring check in `extract.py`; the
    product's own check is `evidence.locate`).
- Stored fact: A `established, true, verdict accepted`; B `unknown, cited, not_checked`.
- Rule: `d15.required_when = {fact: g042, is: true}` (`harness/product/workflows/theft-reviewed/household_theft.json`).
- Line: A d15 in requests; B d15 in holds, g042 in questions.
- How the three readings combine: `casepath-sync-e/casepath-internal/casepath/agents/team.py` (`_reading`, `confirm_facts`):
  a value counts only when all readings give it with a quotation found in the files. An open answer counts only with
  its words found.

## The record shows otherwise (drawn, and for the planner)
1. **A model's suggestion lands beside the checklist, below the rule.** Both records store one `agent_added_needs`
   item from `process_builder` (`required: suggested`). It is outside the rules and outside the scored plan, but it
   is part of what the product returns. Drawn as a blue dot above the rule with a dashed blue line down to a dashed
   blue square beside the line. The planner should decide: keep it (true to the product) or run the figure on the
   checklist-only scope, whose record for the same pair-run has no suggestion and the same one-line difference
   (`plans_theft_casepath_checklist.json`, `s13 … |0`).
2. **A model's check on the admitted fact (not drawn).** Lane A's fact carries `verdict: accepted`, written after a
   model checker (`source_checker`) judged the quotation "supported" (`team.py` ~l.690–701). For a fact all readings
   agree on, a "rejected" verdict only adds a flag and cannot change the value. It does not move the line, so it is not
   drawn. Say so in the text, or draw it as a blue mark with no line into the decision.
3. **Document judgments.** d15's stored judgment is `missing / not_checked` in both lanes. No model judgment acts on
   this line here. In files with attachments a model's document judgment (present / unusable) does act on request vs
   on file, below the rule. This case cannot show it.
4. **Routing** (a model reading of the claim type, admitted by code) is upstream and not drawn.

## Element status
| Element | Status | Source |
|---|---|---|
| Sentences and their words | measured | fresh2 texts |
| Blue underlines (one per reading, under exactly the quoted words) | measured | cache responses |
| Reading marks (filled = true, dashed ring = open) | measured | cache responses |
| Ticks (quotation found word for word) | measured (recomputed by substring) | extract.py |
| Bracket joining the three (all agree) → fact value | formal (team.py rule) with the measured inputs | team.py, record |
| Fact value marker (ink filled = true, amber = open) | measured | product_extra.facts |
| Diamond (rule `g042 = true`) and the edge to the line | formal | workflow JSON |
| Checklist line (teal / amber + question) | measured | plan_ids |
| Blue dot + dashed line + dashed square | measured | agent_added_needs |
| Horizontal positions (stage order) | schematic: order of computation, not time | team.py |

## Two constructions
- **a (rejected, `f2_a.*`)**: one lane, the open sentence alone, left to right across the rule. *Gain:* the simplest
  path. *Distortion:* no partner. Amber can't be read as a change without the stated lane, and the "reading: true"
  legend item has no instance. As drafted it also omits the stored suggestion. Rejected.
- **b (kept, `f2.*`)**: two lanes, stated (A) and open (B), through the same stages at the same x. Each reading is one
  line from its quoted words, crossing the rule once and ending in its tick. *Gain:* the three readings are literally
  three lines that become code at the rule. The two lanes differ only in the model's verdicts and quotations, and
  everything after the bracket follows. It is the same case as Figure 1. *Distortion:* the lower left is empty, and
  the workflow "lighting up" is reduced to the one rule that names the fact (the theft workflow is a single step with
  27 conditional needs).

## Calibration (images opened)
- `assets/calibration/14900912-nerf.png` (sha256 e5e5b4b304623b24eb3da07837a767a639c67291b650b045216ebee7c03215b9):
  one ray is carried, with identity kept, through samples, density and the pixel. *Transfer:* each reading is one
  line, kept from the quoted words to its tick. The blue → ink colour change at the rule is the change of
  representation.
- `assets/calibration/genomnimatte-figure.png` (sha256 e90b87bb0211b3a0d5bfd6fc0b02727a39e0e76b3d36635194612e9f7c4051f6):
  matched rows with the same columns, where only the edited object differs. *Transfer:* the two lanes share columns,
  so the reader compares down each column.
- *Not copied:* 3-D perspective, photographic content, panel titles.

## Encoding table
| Meaning | Visual | Evidence |
|---|---|---|
| the file's sentence | ink text | fresh2 text |
| words a reading quoted | blue underline under those words; one stacked underline per reading | cache |
| a reading's verdict | blue dot: filled = true, dashed ring = open | cache |
| the rule "above, models read; below, code decides" | one ink horizontal rule, full width | team.py |
| a reading entering code | its line turns from blue to ink at the rule | — |
| quotation found word for word | ink tick | extract.py |
| all three readings agree | ink bracket joining the three ticks | team.py |
| fact value | ink filled circle = true; amber circle = open | product_extra.facts |
| the workflow rule naming the fact | diamond, ink when its condition holds, amber when open; edge dashed when open | workflow |
| checklist line | teal square = requested now; amber square + amber circle = held, with its question | plan_ids |
| a model's suggestion outside the rules | blue dot, dashed blue line, dashed blue square | agent_added_needs |

Palette: the re-stepped shared values (see `../f1/CONTRACT.md`): teal `#00846F`, blue `#3A7DD6`, amber `#D9962B`,
ink `#1F2A44`, paper `#FBF8F1`.

## Caption (≤ 45 words)
One sentence, stated (top) or left open (bottom). Three readings each quote the file's words. Below the line, code
checks that each quotation exists, admits a value only when all three agree, applies the workflow's rule and writes the
checklist line. Dashed blue: a model's suggestion, outside the rules.

(45 words.)

## Self-review (self-assessed; not a reader test)
Cold read at print size: the eye enters at the sentences, follows the blue lines down, and the two lanes' end marks
(teal vs amber + dot) are compared. The bracket's meaning ("all agree") needs the legend. The diamond reads as "a
step", not as "the rule that names this fact".

| Dimension | Score | Evidence |
|---|---|---|
| Mechanistic insight | 4 | Who acts is visible as the rule and the colour change; agreement is only a bracket. |
| Scientific fidelity | 4 | All marks stored or formal. The suggestion is drawn. The model checker's verdict is not drawn (stated above). Lane B's three identical quotations look like one thick line. |
| Visual intuition | 4 | Lines can be followed; the one-to-one reading→tick is literal. |
| Information hierarchy | 4 | The entry is the sentences; the end marks are small. |
| Encoding originality | 4 | Readings as lines that change colour at the rule is specific to this mechanism. |
| Compositional clarity | 3 | Diagonal mass; the lower left and upper right are empty. |
| Annotation | 4 | Two rule labels and the legend. |
| Aesthetic refinement | 4 | Two legend rows, 7 pt. |
| Publication readiness | 4 | SVG/PDF/PNG at 5.5 × 3.55 in; regenerate with `extract.py` + `f2.py`. |
| Immediate comprehensibility | 3 | Untested. |

**Weakest point:** the "workflow lighting up" is one diamond. A reader does not see that the rule is one line of a data
file among 27, nor that the other needs did not change. Figure 1 carries that, so the two figures depend on each
other. A fix is to draw the 27-need strip of Figure 1 as the last column here, with only d15 lit.

## Files
`extract.py` → `f2_data.json`; `f2.py` → `f2.svg`, `f2.pdf`, `f2.png` (kept b), `f2_a.*` (rejected a).
