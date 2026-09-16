# Two independent inductions of the same law cut the process in different places

The reference contract and the induced process graph were built from the same Swiss federal sources, for the same
scope, by agents that could not see each other's output. That independence is what makes the contract usable as
ground truth. It also produced a result worth stating on its own.

## What they produced

**Induced graph — 13 nodes.** Three cover notification and validity (`rent_increase_notified`,
`notice_complies_with_prescribed_form`, `increase_void`). Seven cover what happens afterwards: the decision to
challenge, the conciliation request, the hearing, agreement or its absence, the recording of an agreement, the
authorization to sue, the landlord's court action.

**Reference contract — 12 decisions.** Ten cover applicability, characterisation of the communication, the date of
receipt, the prescribed form, its mandatory content, the threat of termination, nullity, the timing rule, and the
staggered and index-linked variants. Two touch the procedure that follows.

The graph runs **downstream** into procedure. The contract stays **upstream** on validity and substance. Both were
given a scope statement that spans the whole path from applicability to the court stage, and each chose a different
half of it.

## Why this is not a defect in either

Both artifacts are source-grounded and both verify. The graph's nodes are supported by propositions whose quotes
passed the exact-quote gate; twelve of thirteen are marked `supported` and one `uncertain`. The contract's
decisions rest on 44 verified Fedlex quotes. Neither contains a step the law does not authorise.

They differ because the scope statement admits more process than either artifact can carry at a usable grain, and
nothing in the sources says where to stop. A tenancy rent-increase dispute genuinely runs from OR 253a to a court
judgment. An author who resolves the validity questions finely has no room left for the procedure; an author who
maps the procedure compresses validity into three nodes. Both are faithful readings. The law does not specify a
granularity, and neither author invented one badly — they invented different ones.

## What it costs the evaluation

Any metric that compares node identifiers to decision identifiers measures agreement on vocabulary, not on law,
and would score near zero here for a reason that has nothing to do with whether the system is right.

The justification metric therefore aligns through the **authority layer**, which is the one vocabulary the two
artifacts share and neither one chose: Fedlex passage identifiers, fixed by the corpus. A chain counts as grounded
when the authority it rests on is an authority the contract also relies on for the same document. This compares
what the two artifacts say the law requires, rather than what they named the step.

## What it costs the claim

More than the metric. If two competent, independent, source-grounded inductions of one scope partition it
differently, then **the induced graph is not uniquely determined by the sources**, and the paper cannot claim that
it is. What the sources determine is which steps are *permissible* and what each rests on — not which steps a
correct system must contain.

The defensible claim is narrower and still worth making: every node, obligation and document request is traceable
to authoritative text that verifies verbatim, and the requirement set responds correctly when the case changes.
Neither of those needs the graph to be unique. A claim that the method recovers *the* process a body of law
implies is not supported by this evidence, and is not made.

This also sets a real bound on reproducibility that the paper must report: re-running induction is expected to
produce a differently-partitioned graph, and the stability of the *document requirements* it yields — not of the
graph — is the thing to measure. That measurement is not yet done.
