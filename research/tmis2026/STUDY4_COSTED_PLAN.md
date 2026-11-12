# Costed plan for the replication study (to Navish, 2026-11-12)

Nothing below has been spent. Costs are model credits in USD, estimated from
the measured cost per case in Study 3. Work by planning and writing sessions
is not counted. The sample sizes come from `analysis/power_study4.md`
(computed from Study 3's stored outputs, no model calls).

## What Study 3's data say about the new rules

Three findings decide the order of the steps.

1. **Under honest scoring of holds, today's artefact does not lead the
   frontier prompt outside denied and open defining events.** Counting an
   unneeded hold as an error, CasePath is slightly behind the frontier prompt
   on files that state every fact (+0.09 errors per claim) and has no lead on
   files with only an open branch fact. Study 3's tenancy lead sat in the 33
   claims whose defining event is denied or open. A sweep over the share of
   files with an open fact, without that case type built in, removes most of
   it. The frontier cells have to be won in the design cycle; they are not won
   now.
2. **A condition the lint flags, treated as open, does not work as it
   stands.** With flags from development data it moved frontier theft from
   0.83 to 0.78, and on tenancy the lint flags 8 or 9 of 10 conditions, so it
   would hold nearly everything. Under honest scoring each of those holds is
   an error. Proposal below: the lint runs when rules are written, the rule is
   repaired at its cited source, and only a flag the author leaves undecided
   is held.
3. **One reading already costs 2.5 to 3.6 times a single prompt**, because a
   reading returns a value and a quotation for each condition. "Close to one
   prompt" is below today's floor. I can commit to a curve of error against
   cost that lies below budget-matched self-consistency (it does on Study 3's
   data) and to a target of at most three times a prompt; the paper states the
   ratio measured.

So "beats every fair alternative on the same model in every cell" is the
target of the design cycle, not something the sealed run can be made to say.
The plan below finds out cheaply, before the expensive steps, whether each
cell can be won.

## Steps

| # | Step | Credits | Worth on its own |
|---|---|---|---|
| 0 | Paper without the dossiers and the expert study; one Scope section; artefact is the minimal core; Study 3 re-scored with holds counted (stored data) | 0 | A cleaner Study 3 paper with the same claims as today |
| 1 | Fair-baseline check on Study 3's data, now development data: a single prompt with the corrected rules and an explicit option to hold, on both models; "Model executes rules" with the hold option on the frontier model | 4 (11 with budget-matched self-consistency on the frontier model) | Shows whether the lead survives a hold-capable prompt. Goes into the paper either way. Decides whether steps 3 to 5 are worth their cost |
| 2 | Three rule sets from public text, each clause citing its source (tenancy: Code of Obligations; theft: Insurance Contract Act and published household conditions; new: dismissal under the Code of Obligations). Clean-room evaluator per regime. File generator run in a session without access to the product, by a model family not evaluated, with scan noise on a fixed share and a sweep of the share of files with an open fact (0, 10, 25, 50%). Lint tested by planting defects in the three rule sets | 5 | A public benchmark others can run: cited rules, generator, references, lint with a measured detection and false-alarm rate. No new claim about CasePath |
| 3 | Second design cycle on development files from the generator: re-read a fact only when the first reading does not settle it; a tie-break reading instead of a hold when readings disagree; lint at rule-writing time; baselines given every improvement. About eight rounds on the cost-efficient model, four gate rounds on the frontier model | 45 | An improved artefact and a cost curve, as development evidence only |
| 4 | Freeze artefact, plan, order of hypotheses and generator seed. Timestamp outside our control (OpenTimestamps proof of the commit, pushed to GitHub; OSF registration in your name if you want one). At least three days before step 5 | 0 | — |
| 5 | Sealed run, once: 240 files per regime, 60 per share level, three regimes, both models, one run per file. Designs per model: CasePath core; single prompt with hold option; self-consistency at CasePath's budget; Model executes rules with hold option; ReAct | 55 (68 with three runs on the cost-efficient model) | The registered replication. The paper claims what comes out |
| 6 | Analysis once, paper, release that reproduces every table and runs the generator and the lint on a reader's own rules | 0 | — |

Total: about USD 110, or about USD 130 with the two options. Steps 0 to 2
together cost about USD 9.

## What the paper can claim at each stopping point

- **After 0:** what it claims today, stated once, with the limits in one Scope
  section.
- **After 1:** the same, plus whether the lead holds against a prompt that may
  hold requests (added after the test, on Study 3's data).
- **After 2:** the same, plus a public benchmark and a recipe: write rules
  from cited text, lint them, generate files, check references in a clean
  room.
- **After 3:** the same, plus a second design cycle reported as development.
- **After 5:** Study 3 as the first study and the sealed run as its registered
  replication on the improved artefact. "Every cell" is claimed only if every
  cell passes; the claim is an intersection of tests, so it needs no
  correction for multiplicity and fails as a whole if one cell fails.

## Design of the sealed run (to be frozen in step 4)

- **Unit and test:** the file. Per-file paired difference between two
  designs, sign-flip test over files, two-sided 0.05. Files are independent
  draws, each with its own story, so no cluster structure is needed.
- **Measure, the same in every regime:** errors per file against the
  clean-room reference: a request that should not be made, a request missed,
  a hold where the file settles the fact, a hold missed.
- **Hypotheses per cell (regime × model), against each fair alternative:**
  fewer errors over the files at shares 10, 25 and 50%; not worse at share 0
  (non-inferiority, margin 0.15 errors per file). The result is shown as a
  curve over the share.
- **Size:** 240 files per regime gives power 0.93 to 1.00 for the pooled
  same-model tests and 0.82 to 0.97 for non-inferiority at share 0, using
  Study 3's effects without its denied-event claims. Against the frontier
  prompt Study 3's data give no effect to power; the size needed there is set
  after step 3 from development data.
- **Budget rule:** self-consistency receives as many samples as CasePath's
  measured cost per file buys.

## Decisions I need from you

1. **Budget cap.** Approve steps 0 to 2 (about USD 9) now, and the rest after
   step 1's result; or approve the whole plan with a cap.
2. **Flagged conditions.** Agree that the lint works at rule-writing time,
   with a run-time hold only for a flag left undecided; or keep "flagged is
   open" as the design, knowing today's evidence is against it.
3. **Denied defining events.** Recommendation: the generator draws each
   deciding fact's state, the defining event included, from one stated
   distribution; files whose event is denied are a fixed 10% reported in their
   own row and kept out of the primary curve. Whether a denial ends the
   process is taken from the cited clause.
4. **Third regime.** Recommendation: dismissal under the Code of Obligations
   (notice, protected periods, documents such as the notice, the contract and
   a medical certificate). Alternative: air-passenger rights under Regulation
   261/2004.
5. **If a cell cannot be won in development.** I will tell you before the
   freeze. You decide whether to freeze and run anyway; the sealed run is
   reported whatever it shows.

## Schedule if approved today

Steps 0 and 1 by 13 November; step 2 by 16 November; step 3 by 19 November;
freeze on 20 November; sealed run on or after 23 November; paper by
27 November.
