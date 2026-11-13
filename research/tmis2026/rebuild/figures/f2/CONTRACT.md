# Figure 2, "The journey of one sentence": contract (draft for gate 1)

## Sentence
The reader should see that the model contributes only quoted words and a verdict per reading, and that the quotation
check, the agreement of the three readings, the fact's value deciding its rule, and the checklist line are computed by code,
because the checklist line can be followed back across the one rule, along three lines, to the words each reading
quoted.

- **Intervention and prediction.** The same as Figure 1 (same case): the stated sentence becomes the open sentence.
  The three readings turn true → open, quoting the open words. The diamond (the fact deciding its rule) turns from
  ink with a filled dot to amber with "?", its outgoing path from taken (ink) to open (amber, dashed), and the line
  from request to held + one question. Nothing above the rule is computed; nothing below it is produced by a model.
- **Comparator.** The partner lane: the stated sentence through the same stages, at the same x positions.
- **Falsifier.** A stored reading without a quotation found in the file that still counts. A value admitted without
  all three readings agreeing. A checklist line that does not follow from the rule and the value.

## Stored instance (measured), the same case and run as Figure 1
- Records: **the core** (checklist-only scope), `runs/study3/confirm/plans_theft_casepath_checklist.json`,
  `PRODUCT|s13-on-PR_third_party_causer|0` (lane A) and `PRODUCT|s13-unres-PR_third_party_causer|0` (lane B).
  Agents in these records: router, claim_reader (first reading, plus one requote call in A), source_checker ×2 (the two
  further readings). No process_builder, document_finder or result_checker ran.
- The three readings: the product's response cache `runs/product/cache/<key>.json`, at the keys the **core** records
  list. These are the same keys the full product's records of the same pair-run list (asserted in `extract.py`), so the
  core's readings are identical requests with identical stored responses. The full readings answer 90 conditions; a
  2-condition requote in lane A is skipped. Fact `g042_rev_92ab8925` ("…the loss was caused or increased through the
  fault of a third party").
  - A: true, "An identified building contractor caused the loss and their identity is known." (×2); true, "An
    identified building contractor caused the loss" (×1).
  - B: open, "whether an identifiable third party caused or enlarged the loss has not been established." (×3).
  - All six quotations occur word for word in the file (`found_in_file`, a substring check in `extract.py`; the
    product's own check is `evidence.locate`).
- Stored fact: A `established, true, verdict accepted`; B `unknown, cited, not_checked`.
- Rule: `d15.required_when = {fact: g042, is: true}` (`harness/product/workflows/theft-reviewed/household_theft.json`).
- Line: A d15 in requests; B d15 in holds, g042 in questions.
- How the readings combine: `casepath-sync-e/casepath-internal/casepath/agents/team.py` (`_reading`, `confirm_facts`).
  A value counts only when all readings give it with a quotation found in the files. An open answer counts only with
  its words found.

## Model steps below the rule? (checked in the core record)
1. **No model-suggested line.** The core records hold no `agent_added_needs` and no added requests or holds.
2. **The "accepted" verdict on lane A's fact is set by code, not by a model check.** In the checklist scope the fact
   check is skipped, and `CaseTeam.run` sets `verdict = "accepted"` for every fact all readings agree on (`team.py`,
   `if self.scope == "checklist": ... row["verdict"] = "accepted"`). So no model checker mark is drawn. The agreement
   bracket already shows that step.
3. **Document judgments.** None in the core record for d15: the document finder is skipped because the case has one
   file, the claim itself.
4. **Routing** (a model reading of the claim type, admitted by code) is upstream and not drawn.

## Element status
| Element | Status | Source |
|---|---|---|
| Sentences and their words | measured | fresh2 texts |
| Blue underlines (one per reading, under exactly the quoted words) | measured | cache responses |
| Reading marks (filled = true, dashed ring = open) | measured | cache responses |
| Ticks (quotation found word for word) | measured (recomputed by substring) | extract.py |
| Bracket joining the three (all agree), its edge into the diamond | formal (team.py rule) with the measured inputs | team.py, record |
| Diamond = the fact deciding its one rule, value inside (Figure 3's mark, `f3.py::diamond`) | measured value; node formal | product_extra.facts, workflow JSON |
| Outgoing edge: path taken (ink, 1.4 pt) or path open (amber, dashed), as in Figure 3 | formal | workflow JSON |
| Checklist line (teal / amber + question) | measured | plan_ids |
| Horizontal positions (stage order) | schematic: order of computation, not time | team.py |

## Two constructions
- **a (rejected, `f2_a.*`)**: one lane, the open sentence alone, left to right across the rule. *Gain:* the simplest
  path. *Distortion:* no partner. Amber can't be read as a change without the stated lane, and the "reading: true"
  legend item has no instance. Rejected; re-rendered with the revision and kept in the folder.
- **b (kept, `f2.*`)**: two lanes, stated (A) and open (B), through the same stages at the same x. Each reading is one
  line from its quoted words, crossing the rule once and ending in its tick. *Gain:* the three readings are literally
  three lines that become code at the rule. The two lanes differ only in the model's verdicts and quotations, and
  everything after the bracket follows. It is the same case and run as Figure 1. The workflow is drawn as Figure 3 draws
  it: the decision node with its one incoming fact and its one outgoing document line. *Distortion:* the lower left is
  empty, and the other 26 needs of the workflow are not shown here (Figure 1 shows them).

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
| the fact deciding its rule (Figure 3's diamond) | hollow ink diamond with filled dot = true decides; amber diamond with "?" = open | product_extra.facts, workflow |
| the path from the rule to its line | ink solid 1.4 pt = taken; amber dashed 1.4 pt = open | workflow |
| checklist line | teal square = requested now; amber square + amber circle = held, with its question | plan_ids |

Palette: the coordinator's shared values (see `../f1/CONTRACT.md`): teal `#008571`, blue `#4A8FD6`, amber `#D9962B`,
ink `#1F2A44`, paper `#FBF8F1`.

## Caption (≤ 45 words)
One sentence, stated (top) or left open (bottom). Three readings quote the file. Below the line, code checks each
quotation, admits a value only when all three agree, and the fact decides its rule: request now, or hold with a
question (marks as Figure 1).

(45 words.)

## Self-review (self-assessed; not a reader test)
Cold read at print size: the eye enters at the sentences, follows the blue lines down, and the two lanes' end marks
(teal vs amber + dot) are compared. The bracket's meaning ("all agree") needs the caption. The diamond now matches
Figure 3's, so in sequence it reads as "the fact decides". Inspected at print size and at 4× on the
bracket → diamond → line joins.

| Dimension | Score | Evidence |
|---|---|---|
| Mechanistic insight | 4 | Who acts is visible as the rule and the colour change; agreement is only a bracket. |
| Scientific fidelity | 4 | All marks are stored or formal; the core record has no model step below the rule. Lane B's three identical quotations look like one thick underline. |
| Visual intuition | 4 | Lines can be followed; the one-to-one reading→tick is literal. |
| Information hierarchy | 4 | The entry is the sentences; the end marks are small. |
| Encoding originality | 4 | Readings as lines that change colour at the rule is specific to this mechanism. |
| Compositional clarity | 3 | Diagonal mass; the lower left and upper right are empty. |
| Annotation | 4 | Two rule labels and the legend. |
| Aesthetic refinement | 4 | Two legend rows, 7 pt. |
| Publication readiness | 4 | SVG/PDF/PNG at 5.5 × 3.55 in; regenerate with `extract.py` + `f2.py`. |
| Immediate comprehensibility | 3 | Untested. |

**Weakest point:** the composition is a diagonal with empty lower-left and upper-right areas. The workflow is one node,
so the reader must take "one of 27 needs" from Figure 1. The two figures depend on each other, by design.

## Files
`extract.py` → `f2_data.json`; `f2.py` → `f2.svg`, `f2.pdf`, `f2.png` (kept b), `f2_a.*` (rejected a).

## House-style revision (coordinator, 2026-11-13)
Ported to `../common/style.py`: white ground, one label size (7.5 pt), the shared checklist mark. The legend has 5
entries: quoted, reading true / open, quote found, fact true / open, requested / held. The question dot is defined by
the caption ("marks as in Figure 1"). Words inside apart from the two sentences: 15 ("models read", "code decides" and
the legend). The readings' lines are thinned to 0.35 pt and the underlines to 0.6 pt, one stroke per text line, so the
sentences stay the heaviest marks above the rule. The quote-to-reading links are kept as the mechanism itself.
Inspected at print size and at 4× on the underlines and the bracket → diamond → line joins.
