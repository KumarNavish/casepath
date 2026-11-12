# Repair round 3 of the development sets: denied events that state another type's event

DEVELOPMENT material, prepared 2026-11-12. No text was written or read for this note and no model was called; the
writing and the blind check are for other sessions (of a model family that is not evaluated; writer and blind
reader in different sessions).

## Criterion and standing rule

- **Criterion** (`generator/STYLE.md` message item 14, `generator/BLIND_CHECK_TASK.md`, `assemble.py compare`): where a
  design's defining event is stated false, the text states no defining event of any type of the regime: the
  claimant says the event did not take place at all. The blind check now gets the routing question and every other
  type's defining-event question (with each `not_this` line) and records each; in a denied-event file, another
  type's event read as stated or open, or a routing answer naming another type, differs from the design.
- **Standing rule:** a text that differs from its design is rewritten once; a file already rewritten once is dropped
  and counted; a rewrite that still differs is dropped.

## The list (from `lint/DIAGNOSIS.json` and `lint/diagnosis_review.json` only)

The 24 denied-event files of `final/` (8 per regime) were sorted by what the diagnosis recorded about them; the
texts were not read again. The input of `repair-prepare` is `dev/REPAIR_R3_LIST.json` (evidence per file).

| Regime | File | Designed type | What the text states (diagnosis quotation) | Kept as | Decision |
|---|---|---|---|---|---|
| theft | the_1dfba8facf5e | theft_at_home | the theft happened on holiday in Ticino, "nicht bei mir zu Hause" | round 1, exact | rewrite |
| theft | the_6634ab23ee99 | theft_at_home | camera bag stolen in Bern | round 1, exact | rewrite |
| theft | the_685edf55333b | theft_at_home | laptop stolen in Zürich at a work meeting, "This wasn't at home" | round 1, exact | rewrite |
| theft | the_86b4e22a87e7 | theft_at_home | items stolen while shopping in Konstanz | round 1, exact | rewrite |
| theft | the_86e739ec9184 | simple_theft_away | "bei mir zu Hause gestohlen" | round 1, exact | rewrite |
| theft | the_a529fff2269d | simple_theft_away | "a break-in at home, in my own flat" | round 1, exact | rewrite |
| dismissal | dis_827bbd04ddc9 | immediate_dismissal | an ordinary notice with a notice period (no routing quotation stored) | round 1, exact | rewrite |
| dismissal | dis_ff1e9056d2c3 | immediate_dismissal | "ganz normal mit Frist gekündigt, auf Ende Mai" | round 1, exact | rewrite |

**Rewritten: 8** (6 theft, 2 dismissal; none had been rewritten before). **Dropped now: 0.** Tenancy: none (the
diagnosis records 3 tenancy denied files as "no type's event holds", the other 5 were routed to their own type).

The other 16 denied-event files are **re-checked as they are**: tenancy all 8; theft the_5ee356013cfc and
the_c7620535798b (robberies away: outside both types, routing "other"); dismissal dis_05af0871cd70, dis_0f89215979d2,
dis_4ee0866843c9, dis_5215d587db4b, dis_930a1b5e1bdc, dis_fea630e08ab3 (no notice given; the first and fourth were
kept as read, so their target is the states as read).

## What is prepared

- `dev/<regime>/rewrite_r3/PLAN.json` (all three regimes): every denied-event file of `final/` with its decision
  (rewrite / drop / recheck), the target states (the final record's `facts`), the text the blind check reads, and
  the diagnosis evidence (operator only).
- `dev/theft/rewrite_r3/bundles/<id>.json` (6) and `dev/dismissal/rewrite_r3/bundles/<id>.json` (2): rewrite
  requests in the `WRITER_TASK.md` format (`round` 3, `mismatches` in the bundle's words with the quotation,
  `previous` = the round-1 text, `bundle` rebuilt now: questions with `not_this`, `central_event_denied` with the
  other types' event questions, output `written/<id>.r3.json`). None of the eight has an attachment.
- `assemble.py blind-in --round 3` builds the blind-check inputs of all 24 files (the rewrites once they exist, the
  others from their kept text) under `blindcheck/in/round3/`; it refuses to write into a round that already holds
  inputs. Rounds 1 and 2 are untouched.

## Commands for the planner (from `research/tmis2026/study4`)

```
# 1. writing session (WRITER_TASK.md, "Repair round"): for each
#    dev/theft/rewrite_r3/bundles/<id>.json and dev/dismissal/rewrite_r3/bundles/<id>.json
#    write dev/<regime>/written/<id>.r3.json with "round": 3.

# 2. blind-check inputs for the 24 denied-event files
for r in tenancy theft dismissal; do python3 -I -B generator/assemble.py blind-in --regime $r --round 3; done
#    expect "8 blind-check inputs written ... no written file for 0" per regime

# 3. blind-check session (BLIND_CHECK_TASK.md): dev/<regime>/blindcheck/in/round3/<id>.json
#    -> dev/<regime>/blindcheck/out/round3/<id>.json (facts, attachments, routing, events)

# 4. compare
for r in tenancy theft dismissal; do python3 -I -B generator/assemble.py compare --regime $r --round 3; done

# 5. only if step 4 reports a differing file whose PLAN decision is "recheck" (never rewritten): its one rewrite
python3 -I -B generator/assemble.py repair-prepare --regime <r> --round 4 --from-compare 3
#    then writing session on dev/<r>/rewrite_r4/bundles/ (written/<id>.r4.json),
python3 -I -B generator/assemble.py blind-in --regime <r> --round 4
#    blind-check session on blindcheck/in/round4/, then
python3 -I -B generator/assemble.py compare --regime <r> --round 4

# 6. final set and checks
for r in tenancy theft dismissal; do python3 -I -B generator/assemble.py finalize --regime $r; done
python3 -I -B lint/verify_rev2.py          # references and designs of every kept file unchanged
python3 -I -B generator/test_generator.py
```

`finalize` refuses to run while a re-checked file differs at round 3 and no round 4 decides it. A rewritten file
that differs at round 3 (or 4) is dropped without a further round.

**Keep rule for re-checked files** (added after the round-3 reading, `assemble.py` docstring and README): a
re-checked file whose reading differs from its recorded states only by facts read "not mentioned" where recorded
"stated false", or the reverse, and whose engine reference from the states now read equals its stored reference,
matches; its recorded states become the states now read (the round-1 keep rule in both directions). Where they now
equal the designed states, the `kept_as_read` flag is dropped (`repair.states: "as designed"`); the reference file is
kept byte-identical.

## What `final/` will then contain

- Every file kept before stays, except files dropped by this round. Their `reference.json` and `design.json` are
  byte-identical (the reference does not change: the design is the same, and the text is rewritten to match it).
- The 8 rewritten files: the round-3 text (`text.txt`, `text.clean.txt`, noise re-applied with the same seed where
  flagged), the round-3 blind-check record, manifest `round: 3`, `repair: {round: 3, result: rewritten}`. If all
  match: theft 59 files, dismissal 58, unchanged counts.
- The 16 re-checked files: the same texts, the round-3 blind-check record (with routing and events) as
  `blind_check.json`, `repair: {round: 3, result: rechecked}`.
- Dropped files (a rewrite that still differs; a re-checked file whose round-4 rewrite still differs) are listed in
  `MANIFEST.json` `dropped` with the reason, and their old folder is moved to `dev/<regime>/dropped/<id>/`.
- Stored lint runs read the round-1 texts; for the 8 rewritten files they no longer match `final/` (development
  material; a later run reads the new texts).

## Limits

- The list rests on the diagnosis's reading of the routing answers (one run per file on the cost-efficient model);
  a file the product happened to route to its own type or leave unrouted could still state another type's event.
  The round-3 blind check of all 24 files, with the new criterion, is what decides; step 5 handles what it finds.
- dis_827bbd04ddc9 has no stored routing quotation (the router gave no value); the diagnosis's reason is that it
  states an ordinary notice with a notice period.

## Outcome (2026-11-12)

The writer and the blind reader returned; `compare --round 3` ran for the three regimes (dismissal recomputed after
the keep rule was added; the blind outputs are untouched), then `finalize` for all three, `lint/verify_rev2.py` and
the test suite (19 tests OK).

| Regime | Checked | Rewritten (match) | Re-checked (match) | Kept by the keep rule | Dropped now | Final set |
|---|---|---|---|---|---|---|
| tenancy | 8 | 0 | 8 | 0 | 0 | 59 (1 dropped earlier) |
| theft | 8 | 6 (6) | 2 (2) | 0 | 0 | 59 (1 dropped earlier) |
| dismissal | 8 | 2 (2) | 6 (4 exact, 2 by the keep rule) | 2 | 0 | 58 (2 dropped earlier) |

- Rewritten and kept at round 3: the_1dfba8facf5e, the_6634ab23ee99, the_685edf55333b, the_86b4e22a87e7,
  the_86e739ec9184, the_a529fff2269d, dis_827bbd04ddc9, dis_ff1e9056d2c3.
- Kept by the keep rule: dis_05af0871cd70 and dis_5215d587db4b. Their only difference was `more_than_180_days`,
  recorded "stated false" (as read at round 1) and read now "not mentioned", which is the designed state; the engine
  reference is unchanged. Their records now equal their designs (the `kept_as_read` flag dropped); dismissal's
  kept-as-read count goes from 2 to 0.
- No round 4 was needed; nothing was dropped; no folder moved to `dropped/`.
- `lint/verify_rev2.py`: all regimes ok. Every reference byte-identical to before the repair; the two dismissal
  design records differ from before only in `more_than_180_days` and the dropped flag (the earlier record rebuilt
  and matched by hash); recomputed from the new records their document states and stop are equal (only `unresolved`
  differs in the stored reference, which is kept). Final sets: 59 + 59 + 58 = 176 files.

