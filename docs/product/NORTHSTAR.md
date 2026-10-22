# CasePath north star

This document records the planner design and verification requirements. It grants
no spending, release, or write authority. Current task-specific user instructions
prevail over the quoted coordination message.

## Planner handoff

Source: [6335641593](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6335641593), 2026-10-22T07:50:47Z.

PLANNER → Codex: **FINAL PLANNER MESSAGE. You now hold yourself accountable to the north star. The planner is stepping out.** The user (22 Oct): *"Please set up the north star and make sure Codex keeps itself accountable to that north star and then get out of the loop."*

**Stop waiting for the planner.** End `wait_for_planner.sh`. No planner reviews will follow this comment. Decide everything in scope by the north star below. Anything that needs the user (spending, release, credentials, scope) goes in your READY FOR MAC post for the Mac owner.

### 1. Commit the north star into the product
In your current W9 branch:
- Add `docs/product/NORTHSTAR.md` with this comment's content and the build spec from `claude/casepath-cues-prototype:design-plans/northstar-20261021/SPEC.md` (tokens, Mulish, geometry, data rules, fidelity gate).
- Add one line to `AGENTS.md`: *"Before any UI change, read docs/product/NORTHSTAR.md and pass its self-review checklist; record the result in the receipt."*

### 2. The north star (authority, in order)
1. **The exact target is the three concepts** in `design/northstar/` (01 live decision building, 02 completed process, 03 reviewed-memory payoff). Match layout, proportions, palette, type, icons and motion, filled with recorded data only. The user: *"This is exactly what I want."*
2. **The cinematic standard (W9).** A nontechnical executive watching the film with no narration or explanation understands three things:
   - what CasePath does;
   - how its intelligence works: exact source → fact → law → step → documents → answer, checklists learned from earlier cases, and a person decides;
   - why it is valuable.

   The cinema lives in the product: one continuous take, no captions or edits beyond 0.5 s fades, and a visible `4×` whenever playback is accelerated.
3. **Honesty invariants.**
   - Recorded data only, with faithful labels; never invent a fact, role, plan row, branch or memory claim.
   - No writes. Zero overlaps. Reduced motion works. Desktop 1440×900.
   - The writing rules and glossaries already approved in this thread.

### 3. Self-review checklist (every item, before any READY)
1. **Fidelity:** `design-plans/tools/fidelity.mjs` side-by-side and overlay against the matching concept, with the mean difference and a deviation list (matched / deliberate with reason / pending). No pending item ships.
2. **Motion:** one change at a time, and the cursor arrives before the highlight, with recorded-trace tests for plan rows, highlights, cursor targets and tabs.
3. **Cold viewer:** sample 24 evenly spaced frames from the film and give them, with no context, to a fresh reviewer as *"a nontechnical insurance executive watching a silent product video"*.
   - Record its answer to *what does it do / how does it reach results / why valuable / what was unclear* in the receipt.
   - Any miss is fixed in the product, never by editing, and the film is recaptured.
4. **Real function:** the full `./bin/casepath test`, all nine cases clicked through, zero console errors, writes or overlaps, on one sealed commit.

### 4. Remaining path to the Mac
1. Apply W9b changes 6335602195: the source follows each node's facts, step numbers sit on legal tests, and the learning act opens with "Later case".
2. Recapture the film, then run the checklist above.
3. Run the full strict gate on one sealed commit carrying W8 and W9.
4. Post a comment whose first line is exactly `READY FOR MAC — <40-char sha>`. Include the counts, digest, film and contact sheet, the cold-viewer answer, the receipt, and the deliberate differences.

The Mac integration owner then follows `docs/product/MAC_COMPLETION_HANDOFF_20261019.md`:
- integrate;
- exact-commit gate;
- keychain release;
- the approved nine-original run (≤18 calls, ≤USD 0.18 new, USD 0.22 aggregate);
- recapture the film from the real histories if they are substantive.

The planner's independent gate stays in `claude/casepath-cues-prototype:design-plans/tools/planner_gate/` for the Mac owner to use.

Thank you. Hold the bar the user set: exactly the concepts, honest data, and a film any executive understands without a word.

---

## Build specification

Copied from `design-plans/northstar-20261021/SPEC.md` at planner commit
`02f80fff047188f5dc838c9ceb70db142fb07c00`.

# North star build spec, 21 October 2026

The user confirmed that `design/northstar/01-decision-building.png`,
`02-completed-process.png` and `03-reviewed-memory-payoff.png` are exactly what
they want. Build them to match: layout, proportions, palette, type, icons and
motion. Fill them with recorded data only.

Geometry below is measured on the 1586×992 concepts and scaled ×0.908 to
1440×900. It is approximate. The overlay decides (`design-plans/tools/fidelity.mjs`).

## Tokens (sampled from the PNGs)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#FFFFFF` | page, top bar, cards, documents |
| `--ink` | `#141516` | titles, node labels, done rings, checks |
| `--ink-doc` | `#2C2B2C` | document body text |
| `--ink-2` | `#4C4B4D` | inactive tabs, rail labels, plan rows, fact cards |
| `--ghost` | `#9C9BA0` | label of the node being built |
| `--ghost-ring` | `#C4C5C6` | dashed ring of the node being built |
| `--line` | `#EBEBEE` | hairlines: under the top bar, rail edge, rail rows |
| `--border` | `#D6D6D7` | cards, plan, fact cards, waiting nodes, branch boxes |
| `--crimson` | `#82072A` | active tab and underline, active source bar, cursor, hexagon, plan title and progress, connector, done-node borders/badges/edges, Edit decision, Documents box, selected node |
| `--crimson-tint` | `#DFB9C3` | selected exact passage |
| `--crimson-track` | `#EFDEE3` | plan progress track |
| `--crimson-wash` | `#F6EFF0` | active source row |
| `--green` | `#2E6B35` | received checks, reviewed shields |
| `--green-ink` | `#1F5530` | `Retrieved 1 …`, `Edited by reviewer`, result headline |
| `--yellow` | `#FEF6C5` | cited line in the completed source preview |
| `--notice` | `#F6F6F7` / text `#61636B` | memory notice bar (03) |

Type: Mulish (OFL, bundled locally). It is closest to the concepts' Avenir-like
sans, with a double-storey a and a single-storey g. Fall back to Instrument Sans.

Sizes at 1440: wordmark 25 (01 regular; 02 bold with the crimson mark), tab 15.5,
rail label 14.5, node label 15.5, document body 16.5/24.5, header field 15,
plan title 16.5, plan row 14.5, fact card 14, chain heading 13.5, chain body 13.5,
dates 12.5.

Icons: 1.5px line icons, about 22px in the tabs and 30px in the rail, drawn in
the text colour of their row. One set only.

## Shell (all three)

- **Top bar:** 75px high, white, 1px `--line` underneath.
  - Wordmark at x 27.
  - Five tabs with icon and label: `Claim reader` · `Source checker` · `Process builder` · `Document finder` · `Result checker`. They start at about x 280 / 459 / 652 / 855 / 1056.
  - Active tab: `--crimson` label (600 weight in 02) and a 3px `--crimson` underline across the tab, sitting on the bar's bottom edge.
  - Right edge (02): search → case search; help → the existing How-to-read guide. There is no settings icon, because no settings exist.
- **Sources rail:** 262px wide with a 1px `--line` right edge.
  - Optional case line at top (03: `<case title> · <case id>`), then `Sources <n>`.
  - Rows about 75px high with `--line` separators inset 27–235. A media icon at x 27, the label at x 75, and `Received <dd.mm.yyyy>` under the label only when recorded.
  - Active row: 5px `--crimson` bar at x 0, plus a `--crimson-wash` fill in the completed view.
  - Rail bottom, read-only demo only, muted 13px: `Case <n> of 9 · Pause · Skip to answer`, then `All cases are fictional.`.
- **No text nav on case views.** The wordmark returns to Cases. On Cases and Knowledge pages the same bar shows `Cases · Knowledge` where the tabs sit.

## 01, live decision building (states 1–5)

- **Spine,** y ≈ 132.
  - 40px rings, 1.5px, about 182px apart, with long thin `--ink-2` arrows between. The label sits under each ring.
  - Done: `--ink` ring with a check.
  - Being built: dashed `--ghost-ring` ring with a `--ghost` label.
  - Waiting: solid `--border` ring with an `--ink-2` label.
  - Labels are the recorded process questions (see Data).
- **Source card,** x 298–969, y 234–727, 1px `--border`, radius 6.
  - Toolbar row 59px: ← → step to the previous/next source; ⋮ opens `Open full source`. No reply icons (they would be fake controls).
  - Recorded header fields (From / To / Date / Subject) in a two-column grid with a hairline below, then the body.
- **Highlight:** the recorded span gets a `--crimson-tint` rectangle with 6px side padding. It appears only after the cursor arrives.
- **Cursor:** a crimson arrow pointer whose tip lands at the span's end, plus a 40px crimson hexagon with the active role's white icon, offset down and right.
- **Fact cards:** about 191×71 at y 762, 1px `--border`, radius 6. Each card has the source-type icon and two lines of `--ink-2`, joined by `+`. A dotted `--crimson` connector runs right to a small hollow junction ring, then up with an arrowhead.
- **Plan,** x 1013–1311, y 262–569, 1px `--border`, radius 8.
  - Title `Building “<question>”` in `--crimson`, with a hairline below.
  - Rows 60px: check (done), crimson spinner arc plus a 2px `--crimson` progress bar on `--crimson-track` (active), hollow ring (waiting).
- **Bottom right:** a 36px crimson hexagon with the role name, and `Work log ›` as a 199×49 bordered button that opens History.

## 02, completed process (state 6)

- **Nodes:** 129×76 boxes, radius 4, about 186px apart, with a second row about 146px lower and a dashed return connector.
  - Number (bold) at top left, recorded question below.
  - Done: 1.5px `--crimson` border and a 16px crimson check badge, with solid crimson arrows.
  - Not reached: `--border` with dashed `#A6A5A7` arrows.
  - Selected: crimson border with a ring badge.
- **`Edit decision`** (pencil, crimson) sits left of the selected node on a crimson rule. It appears only under the NS4 conditions; otherwise omit it.
- **Branches:** recorded forks as 100×50 boxes. The taken branch has a crimson border and ring, then a crimson arrow down to the resulting step box.
- **Local chain strip,** x 288–1142, 1px `#ACACAC`, five columns split by hairlines: `Source facts` (green checks) · `Law` · `Current evidence` · `Evidence still needed` · `Relevant reference case`, each with a line icon and `›`. A crimson rule runs to the `Documents <n> missing ›` box (crimson border, folder icon).
- **Source preview** at the bottom (y 643–869):
  - Left: dated lines (dates in crimson), with the cited line on `--yellow`.
  - Right: a page render with a shadow and the same line on `--yellow`.
  - Controls: expand, +, −, `<page> of <pages>`.
  - `Open full source` stays at the rail bottom.

## 03, reviewed memory payoff (state 8)

- **Vertical spine:** 30px numbered rings (`#B3B3B7`) on a thin line, each with a rounded question box. The selected node has a crimson ring and number, and a larger box with a crimson border and bold text.
- **BEFORE → NOW:**
  - BEFORE: dashed `#C2C3C3` box, muted text.
  - A crimson arrow.
  - NOW: crimson border, bold. `Edited by reviewer` with a green shield, only if recorded.
  - Missing items below, each with a crimson ⊗ and `<item> · missing`.
- **Memory chain:** `Retrieved 1 expert-reviewed case` in `--green-ink`, only if recorded; otherwise the faithful recorded label. Then three cards with green-grey `#9CAC9C` borders:
  - the source card, with the cited line boxed in green;
  - the memory card, with a green shield;
  - the `Result` card, with a green headline.

  An up arrow runs from the memory card to NOW.
- **Notice bar:** `--notice`, 58px, shield icon: `This case used reviewed memory. Qualified review is still required.` (only when true).
- **Top-right:** `Open documents ↗`. `+ Add source` appears only where adding a source works.

## Data (recorded only)

- **Process questions:** use a planner-approved glossary keyed by recorded step ID, like the legal-test glossary.
  - Each question must be answered by that step's own recorded outcome, e.g. "Check what the landlord knew" → "Did the landlord know?".
  - The recorded label stays one hover/click away.
  - List the glossary in the NS1 READY post for review. Unknown IDs fall back to the recorded label.
- **Role tabs:** one tested table from recorded actor/kind to the five roles. An unknown kind keeps the previous role.
- **Plan rows:** only recorded operations linked to the node, labelled by template from kind + recorded source label, ending with `Form process decision`.
- **Fact cards:** recorded fact short label, or the recorded quote clamped to 2 lines.
- **Forks, branches and chain columns:** recorded DAG and recorded fields only. A column with no recorded content is omitted, not invented.
- **Case per concept:** pick the recorded case that best fits each concept (for example a mould or heating case for 02 and 03), and say which.

## Deliberate differences (allowed, list them in each READY)

- State 1 button `Watch the analysis` (a replay, not a live run).
- No reply/reply-all or settings icons.
- Demo transport at the rail bottom.
- Recorded content instead of the concept's illustrative text.

## Fidelity gate (every READY)

For each concept state, post three things:
- the 1440×900 frame;
- `node design-plans/tools/fidelity.mjs <concept> <frame> <out>` side-by-side and overlay images;
- the printed mean difference.

Then list every visible deviation as matched / deliberate (with reason) / pending.

## Current Mac completion boundary (22 October 2026)

The Mac handoff [6342169004](https://github.com/KumarNavish/casepath/pull/21#issuecomment-6342169004) supersedes the historical quoted allowance above: the nine-original grant was consumed on 9 October, 18/18 calls. No remaining allowance or new spending is authorized. Codex owns the cold-landing and north-star UI continuation on `mac/casepath-cold-landing-20261022`; the Mac retains release.

The handoff requests recorded intake and publisher provenance, clear automated-role and question labels, the actual unsent draft, and the later case's own result. “Checking” and “Decide: [recorded question]” are deliberate replacements for the generic Building/Form process decision labels. No recorded alternatives or human-reviewed memory change exists in the nine reference histories. Keep those differences explicit and ask about any local reviewer action in the READY post; do not invent one. See `design-plans/northstar-finish-20261022/REVIEW.md` and its source-bound final evidence.
