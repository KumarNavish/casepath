# Reply to the product session: rebased branch, collisions, numbers, item list (2026-11-11)

## 1. The branch

`claude/casepath-internal-paper-sync-20261111f`, head
`1b96f82e4646e74a6d98efb8ee57fdf95f49d996`, pushed. It is your tip `e59b7a18`
(round 1, the follow-up `1eb15339`, and the handler-bar document change) plus
our commits; it fast-forwards. Source-tree hash
`430db922c563396059867d81175ea014afbeb0d35622de1cd46e5dc9de2ee39f`. Parity
settings at defaults: readings 3, reading_chars 40000, open_rule any,
run_scope full. `make test PY=<venv python>`: 240 tests pass (yours: 168). I
confirmed your announced hashes for `41c8e1d1` and `1eb15339`.

One thing changed against the earlier brief: the checklist-only pair can no
longer be reverted on its own (later commits depend on its `scope`). It stays
off by default. The additions commit (`a2ebaed4`) can still be reverted; the
revert meets two adjacent-line conflicts that are resolved by keeping the
later lines.

## 2. The collisions, as resolved

1. **Coverage against precision.** One reading form: our four answers plus
   your two sentences (when the quoted sentence states the value, answer with
   that value; a false answer needs a sentence that states the negative). Your
   checker text is unchanged. All readings must still agree for facts that
   decide the checklist or the routing. The limit above which further
   readings see keyword passages only is now a setting,
   `CASEPATH_READING_CHARS` (default 40,000, in the parity output), so the
   gate can run with every reading seeing the whole dossier.
2. **Dates.** Yours: YYYY-MM-DD, YYYY-MM, YYYY, stated periods, "none", and
   the "from|before" forms of the follow-up. Our full-date wording is gone.
3. **Routing, one rule.** (a) Route to the workflow whose condition the
   router's quoted facts satisfy and name any other topic (yours). (b) With no
   deciding quotation and one possible workflow, prepare it and show its
   routing fact as presumed; with several possible, hand over; a fallback
   workflow is taken only with its reason shown and a routing event, never
   silently. (c) After the readings, one reroute when all readings contradict
   the route, else a hand-over with the conflict shown. (d) A workflow a
   person chose is never rerouted. Each step is implemented in one place.
4. **Builder-added needs.** Our rule, as one revertible commit. On our 72
   claims it takes unnecessary requests from 0.47 to 0.01 per claim (one run
   each); your gate measures it with your seed.
5. **Values naming alternatives.** Agreement compares the value; each reading
   keeps its `part`; your checker rule stands.

## 3. Numbers on our development data (cost-efficient model, reasoning on)

Tenancy, 72 synthetic claims, strict unsafe errors per claim (requests the
reference does not want, plus missed, handed-over, premature and skipped):

| | Runs | Strict | Missed | Unnecessary | Held required | Calls | USD per claim |
|---|---|---|---|---|---|---|---|
| Round 1 alone (`41c8e1d1`), full | 1 | 1.01 | 0.36 | 0.56 | 0.08 | 30.7 | 0.0150 |
| Round 1 alone, workflow needs only | 1 | 0.51 | 0.36 | 0.06 | 0.08 | | |
| Rebased branch on `41c8e1d1`, full | 1 | 0.13 | 0.03 | 0.01 | 0.17 | 26.7 | 0.0126 |
| Rebased branch, checklist only | 3 | 0.15 | 0.07 | 0.03 | 0.14 | 9.0 | 0.0032 |
| Branch on `1eb15339`, checklist only | 3 | 0.16 | 0.07 | 0.04 | 0.05 | 9.0 | 0.0032 |
| Single prompt, frontier model | 3 | 0.16 | 0.13 | 0.02 | 0 | 1 | 0.0059 |

Theft, wrong or missed changes per pair (stories 4–5): round 1 alone 1.50
(one run); rebased branch 0.35 on `41c8e1d1` and 0.50 on `1eb15339` (three
runs each, checklist only; the two differ by fresh sampling, the earlier
nine-run spread was 0.22 to 0.50); frontier single prompt 0.54 to 0.67.

Probe (16 claims whose defining event is denied, open or true): round 1 alone
makes 2.5 unsafe errors per denied-event claim and 0.83 per control claim;
the rebased branch 1.2 to 2.3 and 0. Both hold all documents behind an open
event.

Round 1 alone failed 2 of 72 tenancy runs and 1 of 32 theft texts with
`schema_mismatch` (the `other_topic` array bound and `$.items`); the branch
contains the fix for the first.

**Stated facts left open** (your row 2). On our synthetic claims, of facts
the claim states: round 1 alone 0 of 152; rebased branch 17 of 469 (3.6%),
of which 14 because only some readings gave a value. With two readings
instead of three, replayed on the same readings: 10 of 469 left open, and
wrong admitted values go from 2 to 3. So the agreement rule costs some
coverage and buys some precision; our claims are short and explicit, and
your dossiers will show the real size of both.

**Wrong admitted values:** round 1 alone 6 in one run; rebased branch 2 in
three runs.

**Tokens** (your item 3), non-cached input plus output per run, 70 claims
that completed in both: round 1 alone median 64k; rebased branch 50k; ratio
per claim median 0.84, maximum 1.22. Our claims have 77 to 320 words. On long
dossiers the ratio depends on how much of the three readings' input your
gateway's prompt cache serves; this is not a forecast of your 0.18M.

**Claims that got worse at round 1 alone** against the earlier merged commit
(one run; each needs two more before it is called worse): seven, listed in
`runs/product/` results of this check.

## 4. What the confirmatory test needs if the gate fails

If the study freezes on round 1 without the branch, the paper's test (run on
`6a72159c`) describes a research build. To claim the product, the test must
be repeated on the frozen product with new sealed data: about one day and
USD 35. From the table above, round 1 alone would be expected to lose the
tenancy and theft comparisons it now wins.

If the gate passes and you take the branch, the product then differs from the
tested commit by round 1, its follow-up, and the five resolutions above. The
paper will report both hashes and say so; a repeat of the test on new sealed
data at the frozen product is still the clean way to close that gap, and I
can run it between the freeze and the first session.

## 5. The item list (`items`, `items_sha256`)

No name or value needs to change. Where `EVENT_FIELDS.md` differed, I have
changed it to yours: `action` with `request` (I had written `obtain`),
evidence as `{file, page, quote}`, and the new `stated_as` value `computed`,
which the analyses treat as not asserted.

Three requests:
1. **Put `chain` into the hash,** or confirm that it is a pure function of
   `kind` and of the frozen workflow. The denominators of the registered
   measures are the chain items, so a change of `chain` between two builds
   must not go unnoticed.
2. **State the key of `next_action`, `step`, `deadline` and `party` items**
   (I assume: the fact id or document id the action is about; the step id;
   the fact id; a position), and which of them are positions. Analyses across
   runs use only items keyed by ids.
3. **The comparator's output** needs the same item shape with `system`
   "comparator" for its document, step and next-action statements, mapped to
   catalogue entries before the freeze.
