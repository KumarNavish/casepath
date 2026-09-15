# Final scientific decision

> **Superseded by the submission-closure pass.** Three closure experiments — a minimal obvious-fix
> baseline, a multi-actor generalization split, and a hostile operation-level novelty audit — returned
> results that the sections below do not reflect. Read `TURN_TRAJECTORY_FINDING.md`,
> `MINIMAL_RULE_BASELINE.md` and `FINAL_NOVELTY_AUDIT.md` first. The short version: the obvious fix removes
> the hearsay error entirely and beats the method on readiness accuracy; the state-accuracy advantage is
> not established on a strong actor model; the averaged headline metric reverses by the final turn; and the
> audited operation has verified prior art. The status is **not submission-ready**, and not for reasons of
> packaging.

*Superseded versions kept in git history. This one is written after the decisive split.*

**The contribution is a channel-typed evidential state, and the confirmatory evidence splits it in two.**
An evidence-acquisition agent represents what each source locally says as typed atoms, derives the case
state by a deterministic calculus rather than by asking a model to judge it, and fixes how much support a
source can lend from the channel the source arrived on rather than from its content. On a fresh
forty-one-family arena read once, the first two parts carry a large and decisive accuracy effect and the
third carries the readiness discipline.

## What the evidence establishes

1. **State accuracy, now pre-registered and replicated.** On a fresh twenty-one-family split read once,
   with state accuracy fixed in advance as the primary endpoint, the method is right about the state of the
   evidence **+0.147 [+0.095, +0.205]** more often than the strongest baseline, winning **nineteen of
   twenty-one families and losing one**, Holm p = 0.000. The confirmatory split had measured +0.148 for the
   same comparison as an exploratory quantity; the decisive split reproduces it to the third decimal as a
   pre-registered one. It also survives dropping every episode where any arm failed (+0.135) and rewriting
   the episodes with a different model (+0.139), so it depends on neither the harness nor the writer.
2. **Hearsay receipts — a design property, not a measurement.** No CTES-family arm can record one: in
   `compute_state` every branch assigning a document `received` or `insufficient` requires that document to
   be in `returned`, which is built only from returned-artifact units, and the cap appears in none of them.
   The zero therefore holds with the cap switched off and for any data, and it is verified by inspection
   rather than by experiment. What is measured is the other side: the arms that *can* make the error make
   it constantly — 77 (`full`), 68 (`process-only`), 137 (`direct`) over the same eighty-two episodes —
   although all three are told the provenance rule in their prompts. The contribution here is that the
   representation makes the error unrepresentable; it is not evidence that the channel cap works.
3. **The mechanism is one binary rule, and it is not the graded one.** The compound switch was separated
   into three independently settable rules, each given its own arm on the decisive split. *A requirement is
   satisfied only when the returned artifact establishes it* carries the whole effect: disabling it alone
   takes premature readiness from 2 episodes to 11, +0.214 [+0.095, +0.357] family-paired, eight families
   won and **none lost**, and the compound ablation reaches only 10. *Do not believe a party's delivery
   promise* carries state accuracy, +0.033 [+0.013, +0.056], p = 0.0012. The **graded channel ordering
   contributes nothing measurable**: its arm is identical to the method on state accuracy, readiness
   accuracy, acquired evidence, premature readiness and hearsay receipts, every paired difference exactly
   zero. The method's own name oversold it, and the correction is recorded rather than buried.
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

1. **Composite utility against the strongest baseline.** +0.129 [−0.011, +0.271] on the confirmatory split
   and +0.135 [−0.040, +0.316] on the decisive one. Two independent splits agree it does not separate.
   Not established.
1b. **A symmetric readiness score does not separate either.** +0.024 [−0.056, +0.119], five families won
   and five lost. Introduced precisely to fix the composite's asymmetry, and it returns a null. The components move in opposite
   directions — more evidence acquired and far fewer premature declarations, against more requests — and at
   a burden weight of 0.25 they cancel. This is a fact about the utility function as much as about the
   method, and it is reported as a negative.
2. **Utility against its own ablation.** +0.127 [−0.009, +0.273]. Same story.
3. ~~A single-effect ablation of the cap.~~ **Discharged.** The compound switch was separated into three
   independently settable rules and each given its own arm on the decisive split; see item 3 of what the
   evidence establishes. The confirmatory split's compound ablation remains uninterpretable as an isolation
   of the cap and is not restated as one anywhere.
4. **That the method beats asking for everything.** `constant`, a zero-model arm that requests every
   outstanding document and never declares readiness, matches the method on evidence acquired and never
   declares prematurely. It loses on state accuracy by 0.181, the largest gap in the table, and it misses
   29 readiness decisions to the method's 20. But `U` does not reward correct readiness, so it is not
   charged for that. Any next version of this arena must score readiness symmetrically.

## Status against the METHOD_READY gate

Three boxes have now closed, across two pre-registered splits.

- *The hidden split was read twice.* Closed. The confirmatory split — forty-one families, none appearing in
  any earlier split — was pre-registered before its episodes existed and read once. Its pre-registration,
  two logged amendments, power analysis, shortcut audit, writer-validity study and adversarial audit
  response are all in the record.
- *The headline rested on an exploratory metric.* Closed. State accuracy was pre-registered as the primary
  endpoint of a second, decisive split of **twenty-one further families, forty-two episodes**, with the
  power computed in advance, and read once. It returned +0.147 [+0.095, +0.205], nineteen families won and
  one lost. The confirmatory split's exploratory +0.148 is a replication of it, not the basis for it.
- *No single-effect ablation existed.* Closed, and against the method's own framing: the graded channel
  ordering contributes nothing measurable, while one binary rule carries the readiness effect.
- *The writer-swap control was partial.* Closed. All 21 families and 42 episodes of the decisive split were
  rewritten from identical latents by a different model family and read once. The primary effect moved from
  +0.147 to **+0.162 [+0.116, +0.209], 20 of 21 families** — inside its own interval, in the direction that
  makes the original conservative. The mechanism attribution survives, and on identical latents the two
  writers differ by 0.024 motif violations per episode.

What remains open is narrower than what closed. Two endpoints fixed in advance returned nulls — the
composite utility on both splits, and the symmetric readiness score introduced to repair it — and a
zero-model arm that requests everything ties the method on evidence acquired. The zero hearsay receipts
remain a property of the representation rather than a measurement.

I still do not emit the terminal token, for a different and smaller reason than before. The science is
where a submission needs it: a pre-registered primary endpoint established and replicated, a clean
mechanism attribution, honest nulls, and a production deployment measured on two surfaces. What is not yet
done is the writing — the draft at `PAPER_DRAFT.md` is a first full draft, not a submission — and the
single-family-model caveat stands, since every number here comes from one model.

## What would finish it

One run, and it is a pre-registration rather than an experiment: **re-register state accuracy as the
primary endpoint**, with a symmetric readiness score replacing `U`, and read a fresh split once. The
effect size observed here (0.135 to 0.156 across conditions, standard deviation about 0.14 at family
level) needs roughly fifteen families for 80% power, so a twenty-family split settles it. On
`openai/gpt-5.4-mini` that costs about four dollars. The second item, in the same run, is the clean
one-effect ablation of the cap. The third, at about fifteen dollars, is the full forty-one-family writer
swap. Nothing about the method needs to change for any of them.
