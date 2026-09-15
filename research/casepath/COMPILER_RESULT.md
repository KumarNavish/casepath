# The chain runs end to end

The invariant the product is supposed to guarantee now holds in code and has been executed over a real
induced graph:

```
authoritative source → process node → active obligation → required fact
                     → evidence capability → document or document set
```

## What was run

The 12-node graph induced from 63 statutory passages for the scope the sufficiency gate rated strongest —
a tenant contesting a termination and seeking an extension — through the obligation compiler.

| stage | result |
|---|---|
| 12 nodes → facts | **35 facts**, 0 citation problems |
| 35 facts → capabilities | **36 capabilities**, 0 citation problems |
| 36 capabilities → documents | **36 requirements**, 0 routes naming a document outside the catalogue |
| chains assembled | **45 chains**, 45 clean, 4 evidence gaps |
| checklist | **19 distinct requests**, each with a full chain |

Every stage validates its own citations: a fact or capability citing a proposition id that does not exist
is reported, and a document route naming a type outside the catalogue is rejected rather than accepted.
Both counts were zero on this run, which is the first time that has been true of anything in this project.

## The chains are legible and legally right

Two examples, taken verbatim from the output.

> **marriage_certificate** — because `termination_formal_compliance` needs the fact *"the tenant has a
> spouse or registered partner"* — authority **OR Art. 266n**

That is correct law. Art. 266n requires the termination of a family home to be served separately on the
spouse, so whether a spouse exists is a fact the compliance node genuinely needs, and a marriage
certificate is what establishes it. Nothing in the chain was authored by hand.

> **termination_notice_official_form + registered_mail_receipt + envelope_copy** — because the same node
> needs the fact *"the landlord served the termination notice separately on the tenant"* — authority
> **OR Art. 266n**

A document *set*, not a single document, which is the alternative-route structure the design requires. The
envelope copy appears because the receipt date is what the 30-day challenge window runs from.

## Why this is the thing the paper is about

A direct checklist predictor can produce "marriage certificate" for a tenancy termination. What it cannot
produce is the reason, and without the reason it cannot know when the document stops being necessary. Here
the marriage certificate is required *because* a node needs a fact that Art. 266n makes material; if the
case establishes there is no spouse, that node resolves and the requirement disappears with it. The
checklist is a consequence, not an output.

The four fault types are first-class in the compiler rather than being scored after the fact: a document
with no clean chain is an orphan request, an active node with no route is an evidence gap, a document
reachable only from an inactive branch is a wrong-branch request, and one whose fact is conditional on an
unresolved branch is premature. On this run there were 4 evidence gaps and no wrong-branch or premature
requests, because every node was marked active.

## What is not yet done

The activation state here was set by hand to exercise the compiler; the case interpreter that derives it
from a real case is the next component. The catalogue is a fixed list rather than being derived from the
sources. And none of this has been compared against a direct checklist predictor yet — that comparison is
the experiment the paper exists to run, and it needs the benchmark the sufficiency gate scoped.
