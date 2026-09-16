# Limitations

Stated as constraints on what the evidence supports, not as hedges.

## The induced graph is not unique, and the paper does not claim it is

Two competent, independent, source-grounded inductions of the same scope partitioned it differently: one ran
downstream into conciliation and the court stage, the other stayed upstream on form, timing and substance. Both
verify against Fedlex; both are faithful readings of a scope statement that admits more process than either can
carry at a usable grain. Nothing in the sources fixes the granularity.

So what the sources determine is which steps are *permissible* and what each rests on — not which steps a correct
system must contain. A claim that the method recovers *the* process a body of law implies is not supported here
and is not made. It also means reproducibility must be measured on the **document requirements** rather than on
the graph, and that measurement has not been done.

## One scope carries the causal result

The intervention result rests on rent increase, and within it on one predicate — whether the tenant challenged in
time. The four scope contracts built for admission (termination, theft, legal expenses) have not been run through
the pipeline. Transfer is asserted nowhere.

## The static task cannot separate methods on this corpus

One distinct reference checklist across 12 development cases; a predictor that ignores the case and emits the
modal list scores F1 1.000. This is a property of the domain — five of eleven documents are required by six or
more decisions, so closing any one decision releases nothing — and of intake messages, which settle the redundant
decisions and not the discriminating ones. No static claim is drawn, and the admission protocol was amended (C8,
observed branch closure) because it could not have caught this in advance.

## The development half was unrepresentative, and the split did not prevent it

All four development scenarios were form-defect disputes. Those activate graph nodes that carry no evidentiary
obligation, so the compiler requested 3.9 documents and could release almost nothing — it scored 0.033 while the
graph-only arm scored 0.148, and I amended the preregistered primary away from the compiler on that basis. The six
held-out scenarios are substantive rent-calculation disputes, the compiler requests 10.0 documents, and it is the
only arm with signal.

Splitting on scenarios prevented case leakage and did not prevent the development half being systematically
unlike the held-out half in the property that determined the outcome. Nothing in the admission protocol checks
that development and held-out scenarios exercise the same parts of the process, and they did not.

## Raw withdrawal recall is not comparable across arms

The compiler requests about twice as many documents as the other arms, so it has more to drop. Its raw +0.553 over
direct prediction is mostly that: its own random-drop baseline is 0.473 of the 0.591. The controlled figure is
+0.118. Any withdrawal metric reported without this control overstates whichever arm asks for more, and the
preregistration did not require it — it was added after the read because the request counts made it obviously
necessary.

## Coverage bounds what any intervention can show

In the graph used for the main experiments, 8 of 13 nodes emitted no obligation and so demanded nothing whatever
their activation; one node produced 10 of 18 chains. A node that demands nothing releases nothing when it closes.
The repaired synthesis produces a node for the substantive determination the first graph lacked, but its evaluation
is incomplete and it is excluded from the confirmatory read.

## The reference contract is a completion set, not a triage list

Its per-case reference set is what would be needed to close every still-open decision, because an unsettled
decision keeps its documents. Every arm requests about four documents where it requires ten, at precision near
1.000 — they are not wrong about what they ask for, they ask for less. Recall against this target is therefore not
a measure of triage quality, and the intervention metric is used for the substantive claim precisely because it
scores *change*, which the level cannot distort.

## Ground truth is model-adjudicated

The reference contract's decisions come from agents and its per-case live/dead marks from three adjudicators at
88% unanimity. The exact-quote gate constrains the authority layer, and the catalogue constrains the document
layer, but no lawyer has reviewed either. The gate caught a fabricated provision inside this very pipeline, which
is evidence for the gate and equally a reason not to treat unverified layers as settled.

## Scale

Development: 3–4 scenarios, 12–14 pairs. Confirmatory: 6 scenarios, 28 pairs. Intervals bootstrap over scenarios,
which is correct and leaves them wide. Nothing here is a large-sample result.

## Two errors made and corrected in this work

Recorded because they bear on how the rest should be read. I computed a structural impossibility that the data
refuted, and committed a document acting on it before catching the flaw (`df63478`). And I nearly reported a
cross-scope citation-fabrication rate that was an artifact of contracts storing sources and quotes as unmapped
parallel lists (`b6c9195`). Both were caught by checking against data rather than by review.
