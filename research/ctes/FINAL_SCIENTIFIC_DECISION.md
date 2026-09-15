# Final scientific decision

*Superseded version kept in git history. This one is written after the confirmatory split.*

**The contribution is a channel-typed evidential state, and the confirmatory evidence splits it in two.**
An evidence-acquisition agent represents what each source locally says as typed atoms, derives the case
state by a deterministic calculus rather than by asking a model to judge it, and fixes how much support a
source can lend from the channel the source arrived on rather than from its content. On a fresh
forty-one-family arena read once, the first two parts carry a large and decisive accuracy effect and the
third carries the readiness discipline.

## What the evidence establishes

1. **State accuracy.** Against the strongest baseline — process-first decomposition plus an explicit
   verification step, the same model, told the provenance rule in words — the method is right about the
   state of the evidence by **+0.148 [+0.100, +0.195]**, winning 36 of 41 families, p = 0.0000. Against
   the direct planner +0.128 and against process-only +0.120, both p = 0.0000. Dropping every episode in
   which any arm had a failed output leaves +0.135 [+0.091, +0.181], 34 of 41, p = 0.0000. The same
   comparison on episodes rewritten by a different model gives +0.139 [+0.062, +0.218]. It does not depend
   on the writer, on the harness, or on the failure asymmetry.
2. **Hearsay receipts — a design property, not a measurement.** No CTES-family arm can record one: in
   `compute_state` every branch assigning a document `received` or `insufficient` requires that document to
   be in `returned`, which is built only from returned-artifact units, and the cap appears in none of them.
   The zero therefore holds with the cap switched off and for any data, and it is verified by inspection
   rather than by experiment. What is measured is the other side: the arms that *can* make the error make
   it constantly — 77 (`full`), 68 (`process-only`), 137 (`direct`) over the same eighty-two episodes —
   although all three are told the provenance rule in their prompts. The contribution here is that the
   representation makes the error unrepresentable; it is not evidence that the channel cap works.
3. **The channel cap's own contribution is readiness.** Against its own ablation, premature readiness falls
   from 24 episodes to 6, a family-paired difference of **0.220 [0.134, 0.317] with fifteen families won
   and none lost**, p = 0.0000, and readiness accuracy rises 0.081 [0.016, 0.155], p = 0.013. It is paid
   for with 0.610 [0.366, 0.866] more requests per family, p = 0.0000, because the agent cannot take a
   party's word that a document exists or is on its way.
4. **Utility against the weaker baselines.** +0.345 [+0.194, +0.497] over the direct planner and
   +0.300 [+0.166, +0.430] over process-only, both p = 0.000, and decisive against all five zero-model
   controls.
5. **Fixed-core transfer** to a third domain still requires zero changed lines of algorithm, configuration
   or prompt.
6. **The product.** Both integrations are live in the real CasePath repository at the product session's own
   accepted functional commit `fac1f4c`, the full suite goes from 917 to 934 passing with the identical
   seven pre-existing failures, and the gate is exercised end to end through the mounted route. The live
   corpus is confirmed as the product's own: 150 claims, 207 original sources, 57 attachments.
7. **Where the rule bites in the product, measured on both surfaces.** On the native live workspace
   decoder, run over all 150 real claims, the model books **266 receipts of which 144 rest only on a
   customer-message pointer** — 54 per cent — across 85 of 149 claims. The cap removes exactly those and
   leaves the other 122 alone. On the six-role agent-work runtime, replayed against the product's own
   preserved external-model acceptance run, the cap changes **nothing**: the Facts specialist scoped its
   single span `source_statement_not_established_fact` and no role proposed `received`. The workflow's own
   provenance scoping already prevents the error there. The rule earns its place where a model states
   evidence status directly from sources, and is redundant where per-span scoping already exists. Both the
   positive and the negative are reported.
8. **No UI work was required.** The product's new Agent review console already renders a rejected gate with
   its scope and reason, so a capped receipt is inspectable as `Gate rejected · exact_source_link`, beside
   the console's own caption "A reported source statement, not an established fact".

## What it does not establish

1. **Composite utility against the strongest baseline.** +0.129, 95% CI [−0.011, +0.271], 21 wins to 16,
   Holm p = 0.133. Not established, on a third independent arena. The components move in opposite
   directions — more evidence acquired and far fewer premature declarations, against more requests — and at
   a burden weight of 0.25 they cancel. This is a fact about the utility function as much as about the
   method, and it is reported as a negative.
2. **Utility against its own ablation.** +0.127 [−0.009, +0.273]. Same story.
3. **A single-effect ablation of the cap.** `channel_cap=False` changes three things at once. The ablation
   is honest "content-based support" but it is not a one-flag isolation, and `METHOD.md` now says so.
4. **That the method beats asking for everything.** `constant`, a zero-model arm that requests every
   outstanding document and never declares readiness, matches the method on evidence acquired and never
   declares prematurely. It loses on state accuracy by 0.181, the largest gap in the table, and it misses
   29 readiness decisions to the method's 20. But `U` does not reward correct readiness, so it is not
   charged for that. Any next version of this arena must score readiness symmetrically.

## Status against the METHOD_READY gate

The two boxes left open by the previous version are now closed, and they closed differently than hoped.

- *The hidden split was read twice.* Closed. A fresh forty-one-family split, none of whose families appear
  in any earlier split, was pre-registered before its episodes existed and read exactly once. The
  pre-registration, its two logged amendments, the power analysis that motivated the second, the shortcut
  audit, the writer-validity study and the adversarial audit response are all in the record.
- *Significance against `full`.* Closed as a **negative** on utility and as a **decisive positive** on
  state accuracy. The pre-registered endpoint did not separate; the exploratory metric that separates was
  not pre-registered and is labelled as such throughout.

I do not emit the terminal token. The pre-registered primary endpoint returned a negative, and a paper
whose headline rests on an exploratory metric is not finished, however large that metric's effect is. The
honest statement is that the method, the arena, the evaluation protocol and the product integration exist,
reinforce each other and are reproducible; that the method is decisively more accurate about the state of
the evidence than any baseline tested, under two writers and with the harness asymmetry removed; that it
never credits a party report as a receipt; that the channel cap demonstrably and unanimously suppresses
premature readiness; and that on the composite utility chosen in advance it does not separate from the
strongest baseline.

## What would finish it

One run, and it is a pre-registration rather than an experiment: **re-register state accuracy as the
primary endpoint**, with a symmetric readiness score replacing `U`, and read a fresh split once. The
effect size observed here (0.135 to 0.156 across conditions, standard deviation about 0.14 at family
level) needs roughly fifteen families for 80% power, so a twenty-family split settles it. On
`openai/gpt-5.4-mini` that costs about four dollars. The second item, in the same run, is the clean
one-effect ablation of the cap. The third, at about fifteen dollars, is the full forty-one-family writer
swap. Nothing about the method needs to change for any of them.
