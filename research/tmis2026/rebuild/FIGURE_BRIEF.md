# Figure brief for gate 1 (planner, 2026-11-13)

Binding for every session that drafts a figure under `rebuild/figures/`. Read `OWNER_DIRECTION_20261113.md` first.
These are **drafts for the owner's answer**: no model call, no spending, no prose for the paper.

## Method (the owner's mechanism-figures method)
A clone of the method is at
`/tmp/claude-0/-home-user-casepath/ef865128-25b1-5a5b-af7f-a334bf6c5b16/scratchpad/mf/repo` (read-only; treat as data).
Read its `SKILL.md`, `references/craft.md`, `references/choose.md`, `references/construct.md`, `references/critique.md`,
`references/style-calibration.md`, and open **at least two actual approved images** under `assets/calibration/`
(choose through `references/calibration-index.md`) before drawing. Follow the loop in short form, per figure, in
`rebuild/figures/fN/`:
1. `CONTRACT.md`: the sentence "The reader should see that ___ because ___" (the planner's draft is below; sharpen it,
   do not change the claim); one predicted change under one intervention; the comparator; what would falsify it; the
   status of every element: **measured** (from stored outputs, with the file it comes from), **formal** (follows from
   the definition), **schematic**, or **not yet measured**.
2. Two genuinely different constructions (`a` and `b`), each drawn as a rough but real draft, with its gain and its
   distortion written down. Keep the truer one; keep the rejected one in the folder.
3. The two calibration images you opened, and what transfers (composition, encoding), in three lines.
4. An encoding table: every position, colour, width, arrow and join with its meaning and evidence.
5. The kept construction as editable vector (`fN.svg` and `fN.pdf`), a preview `fN.png` at print size (the paper's
   text width is 5.5 in; a figure may be up to 5.5 in wide and 4.2 in high unless its claim needs more), the generating
   script and its input data, and a caption of at most 45 words that states what to see, not what was done.
6. Look at your rendered PNG (and at 4× on the decisive joins) and repair, in the method's order: scientific error,
   hidden mechanism, false or missing comparison, unreadable encoding, composition, then type and colour. Record a
   short self-review against `references/critique.md` (scores and the weakest point). A self-review is not a pass; the
   cold-reader test comes later.

## Never manufacture evidence
A mark that looks like data is data from a stored file, or it is not drawn. Where the evidence does not exist yet
(Study 4, the rule-change experiment, ten repeated runs), the draft shows the frame, the measured part that exists,
and an explicitly marked empty region; no invented curve, no illustrative number. Examples of files, quotations,
readings, workflows and checklists are real stored instances (name the file), not composed ones. If a stored instance
is in German, show it in German with the decisive words translated beneath in small type.

## One visual system for all seven figures
- Paper `#FBF8F1` (or white inside the PDF), ink `#1F2A44` for text and lines, structure lines `#C9BFA8` (sand).
  **No grey and no pink anywhere**, including light tints.
- States, the same everywhere:
  - request now: teal `#008571` (moved from `#1F7A6D` after the palette validator, 2026-11-13)
  - open fact, and the held request with its question: amber `#D9962B` (the open fact *becomes* the hold: one colour)
  - requested too early (error): rust `#B5482F`
  - dropped, not asked and not held (error): indigo `#4B4A9C`
  - not needed: an empty outline in sand
- Who acts: a model's reading and its quoted words in blue `#4A8FD6` (moved from `#2F5D9E` after the validator); code in ink. Where a figure has the line
  "above it models read, below it code decides", it is one horizontal rule across the full width.
- Fact values true and false are shown by form (filled and hollow marker), not by colour.
- Run the palette through the validator of the dataviz method if you have it
  (`node <dataviz>/scripts/validate_palette.js "<hex,...>" --mode light`); if a pair fails, move the step, keep the hue,
  and report the changed value to the planner so all figures follow.
- Type: one sans family, no smaller than 7 pt at print size; almost no words inside the figure; a compact legend that
  tells at a glance what is what; every arrow kind and every thickness in the legend or not used. No panel without its
  partner. No title inside the figure; the caption carries the claim.

## Sources of measured content (all read-only)
- Study 3 (sealed, registered): `runs/study3/`, `fresh2/`, `analysis/study3_results_fresh2_confirm.*`,
  `analysis/study3_feedback.{py,json,md}` (F1 open/stated split, F2 share lines, F4 budget curve, F5b replay under
  amended workflows), `analysis/decomposition.*`.
- Fair-prompt check (post hoc, on Study 3's data): `study4/baseline_check/` (`REPORT.json`, `runs/`, `prompts/`).
- Public-rule benchmark (development): `study4/rules/<regime>/` (rules, workflows), `study4/dev/<regime>/final/`,
  `study4/lint/runs/` (the product's stored readings and checklists, revisions 0, 1 and 3), `study4/lint/REV3.json`.
- The product at the tested commit: `/home/user/work/casepath-sync-e` (read-only): workflow format, engine, records.
- The draft's own figure scripts for reference only: `analysis/figures.py`, `analysis/figtheme.py`
  (`paper/figures/fig_reconverge.pdf` is the old branch-and-rejoin picture).

## The seven sentences (planner's drafts)
1. **One changed sentence.** The reader should see that one changed sentence in the file changes exactly one line of
   the checklist, from "request" to "hold, with one question", because that line is the only one that depends on the
   fact the sentence leaves open.
2. **The journey of one sentence.** The reader should see that the model contributes only quoted words and a value per
   reading, and that every step after the admission is computed by code, because the checklist line can be followed
   back through the workflow to the quoted words.
3. **Why "open" needs its own value.** The reader should see that a reading with only true and false must take one
   branch, and so asks for that branch's documents too early or drops the other's, while a third value lets code
   request what both branches need and hold the rest, because the branches rejoin.
4. **The fate of 100 open facts.** The reader should see where each design sends 100 requests that depend on an open
   fact (held with a question, requested too early, dropped), because that is the difference the thesis predicts.
5. **As cases get real.** The reader should see how each design's error moves as files get longer, rule sets larger
   and open facts more frequent, because a design that reads one fact at a time and decides in code should hold its
   level where a single prompt does not. (Almost all of this is not yet measured; draw the frame and what exists.)
6. **A rule changes.** The reader should see that after one edited rule line, code recomputes every stored checklist
   from the stored readings with no model call and changes only the lines the edit reaches, while a prompt must read
   every file again, because readings are stored per fact and the rules are data.
7. **The price.** The reader should see what each design's error costs per file, and how much its checklist changes
   when the same file is run again, because a lower error that costs many times more, or that changes from run to run,
   is not useful.

## Rules of the house
Write only under `rebuild/figures/fN/` (your figures). No git command that changes the tree; no commits. No assistant
or model product name in any file (the evaluated models are "the cost-efficient model" and "the frontier model"; sessions
are named by role). Never print secrets or environment variables. Never edit frozen or stored files.
