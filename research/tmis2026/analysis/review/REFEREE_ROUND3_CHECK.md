# Round 3 check of the revision (v2) against REFEREE_REVIEW_ROUND3.md

## What was read

- **The revision:** `v2/main.txt` and `v2/supplement.txt`. I rendered page 20 (Table 9) and looked at it.
- **Sources, read-only:** `analysis/study3_feedback.md` (H4 cluster line, l. 205; theft "open condition's documents held", l. 77–91), `analysis/study3_feedback.json`, `paper/results/numbers_study3_feedback.tex` (cost-ratio and cluster-count macros, l. 376–377 and 1075–1100), `analysis/study3_review.md` (R6 family table, l. 223–246) and the files of the first check.
- **Not read:** none of the authors' briefs or earlier reviews.

## Totals

| Group | Items | Closed | Partly | Not closed |
|---|---|---|---|---|
| Major (M1–M10) | 10 | 8 | 2 | 0 |
| Minor (1–23) | 23 | 20 | 3 | 0 |
| Part 2 numbered items (1–38) | 38 | 36 | 2 | 0 |
| **All** | **71** | **64** | **7** | **0** |

In addition, ten new problems were introduced by the revision (section D). Four of them matter.

## A. Major concerns

**M1. H4 paragraph. Closed.**
§6.2: "CasePath had fewer errors on 7 of the nine changed conditions and more on 2, by 0.13 and 1.00 errors per pair (expert procedure; third party caused the loss; Supplement, Table S23). 32 of the 512 sign patterns give a sum at least as far from zero."
The source agrees: `study3_feedback.md` l. 205; macros `sthreeFThreeSCFewer` = 7 and `SCMore` = 2.

**M2. Headline numbers, subset labels and the 9 families. Closed.**
- The abstract now leads with the registered values: 0.31 against 2.14 and 1.86; 97% against 48% and 35%.
- The open-or-denied split is labelled "Added after review".
- §1 and §6.4 give claim-run means, 0.40 / 3.39 / 3.06, which match `study3_feedback.md` l. 15–22.
- Table 8 and Figure 5 now use the same quantity.
- §6.2 states the 9 families.

**M3. Theft holding measure. Closed.**
- §1: "this measure cannot tell a hold from reading the open fact as false, which scores the same."
- §6.4 reports 83 / 85 / 85 / 90%. The source gives 83.3, 85.4, 84.7 and 90.3 (`study3_feedback.md` l. 79–84). Correct.

**M4. Frontier theft cell. Closed.**
- S7c is now reported in §1 and §6.3 ("0.83 against 0.58 (+0.25, p = 0.0781)").
- §6.3 and the Table 6 caption give the 0.22–0.44 range.
- The conclusion no longer says "the rules set the limit".

**M5. Rule-review confound. Closed.**
- §6.1: "The review made both single prompts worse … Only 11% and 27% of that change fell on documents named by a changed rule … H1, H4 and H5 use the reviewed rules, and CasePath with the original rules was not run."
- §6.2 reports S4c (p = 0.0117) and the exact superiority p of 0.6367 against the frontier prompt with the original rules.
- §7.1 repeats the point.

**M6. Reading sensitivity. Partly closed.**
Closed in §6.6 and Table 9:
- the clean room "confirms the implementation of the catalogue";
- the alternative references are "not independent evidence";
- "6 of the 10 reverse";
- A2 and A4 are argued from the unchanged-workflow rows.

Still failing in §8, the conclusion: "Analyses added after review show where the lead stops: on files that state every fact, without the reading that a denied defining event ends the process, …"

This is false for the amended workflow. Under A1 with the workflow amended, the lead stays significant: −0.66 (p = 0.0002) and −1.00 (p = 0.0014) (Table 9; `study3_feedback.md` l. 285).

Corrected: "…on files that state every fact; with the product's workflow unchanged, under the reading that a denied defining event does not end the process (amended to that reading, it keeps a smaller lead, which rests on the 9 open-event claims); and on theft with the frontier model, …"

**M7. Cost. Closed.**
- Table 4 now has ratio columns.
- §6.5: "19.8 and 41.8 times the same-model single prompt, and 2.1 and 7.4 times the frontier single prompt. Checklist only cost 4.4 and 6.8 times." All of these match macros l. 1082–1096.
- The 31.6 / 53.8 ratios for the frontier checklist-only run also match.
- The run times are now marked as lower bounds.

**M8. Lint. Closed.**
- The lint has been removed from contribution (2) and from the introduction.
- §6.7 calls it "a diagnostic we propose", gives 14 and 12 flags and 8 and 9 of 10, says the mutations were written by "the analyst who designed the lint", and says the false-alarm rate is unknown.

**M9. Labelling and multiplicity. Closed.**
- §6 now uses a dagger convention: "their p values are descriptive and not corrected for multiplicity".
- The abstract, introduction and conclusion carry "registered", "registered secondary" or "added after review".

**M10. Limits in the abstract. Partly closed.**
The abstract now says: "Texts, references and rule reviews were made by AI sessions and the authors, checked by no jurist; one confirmation depends on a reordering of the hypotheses before the freeze."

Two limits are still missing from the abstract:
- the tenancy references come from the engine CasePath implements;
- the theft test reuses the earlier conditions and rule base. The text-writer's access to the prompts is also implicit only.

Corrected: "The texts were written by an AI session that could read the product's prompts; the tenancy references come from the engine CasePath implements and the theft test reuses the conditions of earlier studies; the theft rules were reviewed by AI sessions; no jurist checked any of it; one confirmation depends on a reordering of the hypotheses before the freeze."

## B. Minor concerns

| # | Status | Evidence in v2, or the failing sentence with a correction |
|---|---|---|
| 1 | Closed | §6.3: "in these data none of them changes with the order … A part can be negative" |
| 2 | Closed | Table 5 Holm column uses the exact p for H5 (0.0234); the bootstrap value is in footnote b |
| 3 | Closed | §6.2: "with a margin of 0.25 errors per pair and a paired cluster-bootstrap test" |
| 4 | Closed | §1 and §6.1 define all five kinds of strict unsafe error |
| 5 | Closed | Abstract: "claims with an open fact or a denied or open defining event" |
| 6 | Closed | §6.2: "Supplement, Table S17 gives the per-claim values" (S17 is the per-claim subset table) |
| 7 | Closed | §6.6: "6 of the 10 reverse with p < 0.05" |
| 8 | **Partly** | §3.5 now breaks the count down by role, but says "these few values caused most of CasePath's tenancy errors". The denied-event reading part is 0.611 × 24/96 = 0.153 of 0.313, about 49% (`decomposition.md` l. 19, 34). **Corrected:** "…caused about half of CasePath's strict unsafe tenancy errors." |
| 9 | Closed | §6.5: "These are lower bounds, because calls answered from the response cache took no time." |
| 10 | Closed | Appendix C: "43 design outputs … and 7 Self-consistency samples, counted as empty votes" |
| 11 | **Partly** | §5 and Appendix B now say "dossiers of an internal hackathon", but not whether these are the insurer's real, unaltered closed claim files. §5 still speaks of "what the insurer did next". **Add:** "…closed claim files of the insurer, made available unaltered for an internal hackathon" (or whatever is true). |
| 12 | Closed | Abstract and §1: "will be released" |
| 13 | Closed | Part (a) is now stated "By definition"; Proposition 3.3 keeps only part (b) |
| 14 | Closed | §6.7: "the analyst who designed the lint widened 6 conditions … Only blunt widening was tested" |
| 15 | Closed | §6.4: "0.19, against 0.39 for the same-model prompt (p = 0.2761)" |
| 16 | **Partly** | The within-group mix is now stated, but the new sentence is wrong; see D2. |
| 17 | Closed | §2 and §6.1: "the plan's design in the style of Chain of Logic" |
| 18 | Closed | §6.3: "identical in 93% … and 59% … while two runs of the full product were identical in 81% and 17%" |
| 19 | Closed | §6.1 states that the frontier product ran in the checklist-only setting and that the document finder is skipped |
| 20 | Closed | §6.1: "The comparators' prompt texts did not change after 19:10" |
| 21 | Closed | Principle 2: "on the 277 of 286 claim-runs … fewer strict errors in 3 claim-runs and more in 0" |
| 22 | Closed | The lint table moved to the Supplement (Table S43); the old units clash is gone |
| 23 | Closed | §6.2: "p = 0.0417, descriptive; the plan had predicted no difference" |

## C. Part 2 numbered items

| # | Status | Where in v2 |
|---|---|---|
| 1 | Closed | §6.2, 7-of-9 sentence |
| 2 | Closed | Abstract and §1 lead with the registered values; the split gives claim-run 0.40 / 3.39 / 3.06 |
| 3 | Closed | §6.4: claim-run means, with "the p values come from sign-flip tests over family means" |
| 4 | Closed | Table 8: "means over claim-runs, as in Figure 5" |
| 5 | Closed | §6.2, pointer to S17 |
| 6 | Closed | Principle 1: "(registered secondary, descriptive; per-claim means)" |
| 7 | Closed | §6.4: "every single-prompt and prior-work design … two-valued … scores the same 94%" |
| 8 | Closed | §6.3: "registered tests H1, H2 and H4, and the plan's secondary contrasts S2a–S2c and S4c, not corrected" |
| 9 | Closed | §6.6 and Table 9 "Use" column |
| 10 | Closed | §6.6: 6 of 10, H2 and H3 |
| 11 | **Partly** | §3.5 breakdown given; "most" should be "about half" (minor 8) |
| 12 | Closed | Table 5, Holm |
| 13 | Closed | Unchanged; it was already correct |
| 14 | Closed | §6.2: "H5's superiority p is 0.0547" |
| 15 | Closed | §6.4, same-model S contrast |
| 16 | Closed | §6.4: "(p = 0.0023; registered secondary)" |
| 17 | Closed | §6.3, S7c; the frontier cell is named "checklist only" |
| 18 | Closed | The abstract drops 0.333; the conclusion has "read two broadly worded conditions literally"; §6.3 gives the range |
| 19 | Closed | Abstract: "Added after review:" |
| 20 | Closed | §1: "An error decomposition added after review traces most of the difference…" |
| 21 | Closed | The lint is gone from §1 |
| 22 | Closed | Contribution (2) no longer names the lint |
| 23 | Closed | §6.6: "This confirms the implementation of the catalogue" |
| 24 | Closed | §6.6: "Evaluator B wrote these references afterwards, to our instruction" |
| 25 | Closed | §6.6 and Table 9 |
| 26 | Closed | §6.6: "rests on the 9 open-event claims" |
| 27 | Closed | §6.7: "Run on the theft test texts themselves … among 14 flags" |
| 28 | Closed | §6.7, mutation analyst; "Only blunt widening was tested" |
| 29 | Closed | Unchanged; it was already correct |
| 30 | Closed | Abstract: "20 to 42 times the same-model prompt"; §6.5 and Table 4 |
| 31 | Closed | §6.5, lower bounds |
| 32 | Closed | The abstract drops the sentence; §6.5: "on theft the gap at matched cost was not significant" |
| 33 | Closed | §6.3, decomposition wording |
| 34 | Closed | §6.1 and §7.1 |
| 35 | **Partly** | Hackathon provenance, as minor 11 |
| 36 | Closed | Appendix C |
| 37 | Closed | §6.1: "Four limits apply to every result. … Theft reuses the nine conditions…" |
| 38 | Closed | §6.2 |

## D. Problems introduced by the revision

Each of the requested new numbers matches its source:

| Number in v2 | Source |
|---|---|
| 7 of 9 changed conditions | `study3_feedback.md` l. 205; macros l. 376–377 |
| 0.40 / 3.39 / 3.06 (claim-run means) | `study3_feedback.md` l. 16, 20, 22 |
| Cost ratios 19.8 / 41.8 / 2.1 / 7.4 / 4.4 / 6.8 / 31.6 / 53.8 | `numbers_study3_feedback.tex` l. 1082–1096 |
| Theft held 83 / 85 / 85 / 90% | `study3_feedback.md` l. 79–84 |
| "6 of 10" reversals | `study3_feedback.md` l. 600–609; macro `sthreeFFiveAAllReverseSig` = 6 |
| "2 of 10" under A1 | `study3_feedback.md` l. 565, 568 |
| 9 of 24 families; 15 others (13 defect, 2 termination); 10 lower, 2 equal, 3 higher, at most 0.75; at least 2.33 | `study3_review.md` l. 223–246 |

The problems below are in the wording around these numbers.

**D1. The conclusion's "without the reading that a denied defining event ends the process". False.**
See M6. With the workflow amended to A1, the lead stays significant.

**D2. §6.4: "Real files with open facts but few denied events would lie nearer the left." Wrong.**
Such files belong to the open-or-denied group, which is the right-hand end of Figure 5. What changes is the height of that end: claims with an open branch fact cost CasePath 0.23 and Rules in context 0.51 per claim, far below the group's 0.40 and 3.39 (`study3_results_fresh2_confirm.md` l. 131, 145).
Corrected: "If real files with open facts rarely deny the defining event, the right-hand end of every line would be much lower (on open-branch-fact claims CasePath made 0.23 strict unsafe errors per claim and Rules in context 0.51), and the gap far smaller than the figure shows."

**D3. "Most of the tenancy lead rests on our reading that a denied defining event ends the process" (abstract, §1, §6.6, §7.1). True only with its basis stated.**
- By claim weight, the denied-event claims carry about 69% of the same-model lead (24 × 5.07 / 96 = 1.27 of 1.83) and about 62% of the frontier lead (0.96 of 1.55) (`study3_feedback.md` l. 375).
- The amended A1 replay removes 64% of the same-model lead but only 36% of the frontier lead (−1.83 → −0.66; −1.55 → −1.00).

Corrected (§6.6): "The denied-event claims, whose right answer rests on our reading that a denied defining event ends the process, carry about two thirds of the tenancy lead against either prompt."

**D4. §3.5: "these few values caused most of CasePath's tenancy errors". Overstated.**
The figure is about 49%. See minor 8.

**D5. §6.7: "admitted it as true in 8 of 8 ordinary texts …; the cost-efficient model did so in 0 of 50". Units differ.**
The 50 are runs, and they pool development runs (`lint_followup.md` l. 7, 64).
Corrected: "in none of its 50 ordinary runs, development runs included".

**D6. §6.7: "the decomposition traces the frontier model's extra errors … to its readings of two broadly worded conditions". Overattributed.**
The decomposition splits errors by stage, not by condition. The two conditions come from the diagnosis of the stored readings (Supplement, S11/S12).
Corrected: "the decomposition puts the frontier model's extra errors in its readings and holds, and the stored readings trace them to two broadly worded conditions."

**D7. Abstract: "every comparator received the same rules".**
The original-rules comparators did not, and S4c and S4b are cited.
Corrected: "every comparator in the hypotheses received the same rules".

**D8. Abstract: "On the frontier model, run once, CasePath led on tenancy and not on theft". Unclear.**
Corrected: "…CasePath in its checklist-only setting, run once, led…"

**D9. §6.1: "Designs ran 3 times per case." This directly follows "On the frontier model the product ran once".**
Corrected: "The other designs ran 3 times per case."

**D10. §6.4: "Counting unneeded holds as errors, it is lower above 4%."**
The crossover is 3.7% (`study3_feedback.md` l. 167). Write "above about 4%".

The tables still bear checking. Table 9 now carries the "Use" column and markers, which helps, but it uses family means beside Table 8's claim-run means; the caption says so. The Figure 6 point labels were not re-checked at render level.

## E. Recommendation for the revision as it stands

**Minor revision.** Every major concern is closed or nearly closed. No number I checked disagrees with its source. The registered and post hoc results are now clearly separated.

Four rewordings stand between the revision and "accept with minor revisions":

1. Correct the conclusion's A1 clause (D1 / M6).
2. Correct the Figure 5 sentence about real files (D2).
3. State the basis of "most of the tenancy lead" (D3).
4. Change "most" to "about half" in §3.5 (D4).

In addition, two short additions are wanted: the two missing limits in the abstract (M10), and the provenance of the hackathon dossiers (minor 11).

All of these are wording or stored data, and none needs a model run.
