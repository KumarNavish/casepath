# Channel-Typed Evidential State (CTES)

## Contribution in one sentence
An evidence-acquisition agent should read *what a source says* with a language model but derive *how much
support that source can lend* from the channel the source arrived on, so that a party's report about a
record can direct acquisition but can never make the record received — a single typed constraint that
removes hearsay-grounded receipts and premature closure entirely, at no extra inference or acquisition cost.

## The failure it addresses
In document-heavy expert workflows the agent decides each turn what is established, what to request, and
whether it may proceed. The failure that survives strong models is not planning: it is treating a *claim
about* an artifact as the artifact. Measured here across two model tiers and three domains, every arm that
lets the model declare document state produces hearsay receipts (4–80 per split) and premature readiness
(up to 12 episodes of 24); CTES produces zero hearsay receipts in all six model × split configurations.
Prompting cannot fix this: models detect invalid support in isolation but suppress that check during
multi-source synthesis (arXiv:2606.05403), and benchmarks of the phenomenon (EnvTrustBench,
arXiv:2605.08828) propose no mechanism.

## Method
Each turn makes exactly one model call returning **local atoms only** — never a status, never a plan:

| atom | content |
|---|---|
| requirements R | `(id, alternative satisfying document sets, critical, standard, active)` read from the governing instructions |
| attestations T | for each text unit `u` and requirement `r`: does `u`'s own content cover `r` — `full / partial / contrary / none` |
| mentions M | what a unit says about a catalogue document — `exists, possessed_by_customer, held_by_third_party, promised, automatic, nonexistent, content_quoted, unreadable` |
| readability Y | for returned documents only |

A deterministic calculus then computes the state. Its single non-standard operation is the **channel cap**:

```
level(u) = 1 (reported)      if channel(u) = party_report          # the claim message, a relayed statement
         = 2 (observed)      if channel(u) = returned_artifact     # a document in the workspace
         = 3 (authenticated) if channel(u) = authenticated_artifact
         = 0                 if channel(u) = instruction

ℓ(r)         = max{ level(u) : u attests r fully }
observed(d)  = d returned ∧ readable(d)=full ∧ max level of d's full attestations ≥ 2
satisfied(r) = (∃ option ∈ sets_r : ∀d ∈ option, observed(d)) ∧ ℓ(r) ≥ standard(r)
ready        = ∀ r critical ∧ active : satisfied(r)
requests     = greedy cover of the unsatisfied active requirements over requestable documents (≤2)
```

`channel(u)` is read from metadata alone. In the CasePath product it is the artifact's declared role
(`customer_message` vs `attachment`) or its admission kind (`export` / `source_update`); in the arena it is
whether the source carries a delivered document id. Second-order reports are typed the same way: a delivery
promise suppresses a request only when it arrives *on* a returned artifact; the same words in a party report
raise availability to `exists` and the document is still requested.

Two conservative parsing rules make the contract robust without repairing semantics: document ids outside
the catalogue are dropped and a requirement left with no option becomes *unsatisfiable* (never satisfied,
never requested, blocks readiness); atoms naming a unit, requirement, document or status that does not exist
are dropped and counted. Both can only remove support, never create a receipt or a readiness.

**Ablation.** `channel_cap = False` keeps the identical model call and the identical atoms, and switches
the calculus from channel-based support to content-based support. It is a compound switch and the earlier
description of it as one flag was wrong; it changes three things at once, and the correction is recorded
here rather than quietly applied:

1. every non-instruction unit counts as observed, instead of carrying the level of its channel;
2. a delivery commitment (`promised`, `automatic`) reported by a party is believed, instead of being
   downgraded to bare existence unless it comes from a returned artifact;
3. a requirement is satisfied when the returned artifact establishes it **or** when an attestation attains
   the required level, instead of requiring both.

The third is the structural one: without the cap an attestation alone can satisfy a requirement with no
artifact on file. So the ablation is a faithful "decompose then verify over content" system, but it is not
a single-effect ablation of the cap, and the confirmatory result reports it as the former. A clean
one-effect ablation has not been run.

**What each part earns, measured one rule at a time.** The three rules were separated and each given its
own arm on the decisive split:

| rule | what disabling it costs |
|---|---|
| a requirement needs the returned artifact, not an attestation | premature readiness 2 to 11 episodes, +0.214 [+0.095, +0.357], 8 families won, 0 lost |
| a party's delivery promise is not believed | state accuracy +0.033 [+0.013, +0.056], p = 0.0012 |
| support level comes from the channel, not the content | **nothing measurable**: every paired difference exactly zero |

So the graded channel lattice, which the name "channel-typed" advertises, does no work. The load-bearing
content of the method is one binary rule about satisfaction and a second about delivery promises, sitting
on top of a typed representation that carries the state accuracy. Earlier text here claimed the lattice was
the contribution; that was wrong and is corrected.

## What it adds beyond the current CasePath product
The shipped six-role workflow (Facts → Orchestration → Source integrity → Process → Evidence →
Audit/readiness) is safe today only because the agent may not set evidence state at all: `SourceSpan`
carries `scope="source_statement_not_established_fact"` and the evidence class is taken from the existing
authority. The agent therefore cannot close a need from a returned document either. CTES supplies the rule
that makes agent-maintained evidence state safe, using signal the product already records
(`SourceSpan.extraction` is `message_body` exactly for the customer message and a document extraction for
every admitted artifact), so no new model output and no schema change is required.

## Product form
`casepath_api/agent_work/evidential_channel.py` with the gate wired into the live runtime's
`_tool_propose_document_requirement`: an evidence class asserting receipt is capped to `insufficient`
unless at least one selected span comes from an artifact extraction, and the cap is recorded as an
`exact_source_link` gate result on the persisted work event. A second integration,
`casepath_api/evidential_channel_gate_v1.py`, applies the same rule inside
`native_live_workspace_v1.decode_provisional_proposal` behind `CASEPATH_EVIDENTIAL_CHANNEL_V1=1`.
