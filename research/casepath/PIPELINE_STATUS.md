# The pipeline runs end to end, and one scope does not discriminate

Every component of the chain now exists and has been executed on real Swiss law and a real claim from the
150-claim corpus. This records what works, and the one finding that changes how the benchmark must be built.

## Components built

| stage | module | what it does |
|---|---|---|
| A + B | `process_induction_v1` | passages → typed propositions with exact quotes → graph, every object citing its propositions |
| D | `case_interpreter_v1` | branch predicates → true / false / unresolved against a case, then deterministic activation |
| E + F | `obligation_compiler_v1` | active node → required facts → evidence capabilities → document routes, with the four faults |
| corpus | `authority_corpus_v1` | Fedlex Akoma Ntoso → exact passages, verified against the repository's own 19 |

Three grounding gates run automatically and all were clean on the full run: a proposition whose quote is
not verbatim in its passage is dropped, a fact or capability citing an unknown proposition is reported, and
a document route naming a type outside the catalogue is rejected.

## The interpreter's rule holds

At intake the real claim leaves **all nine branch predicates unresolved**, so eleven of twelve nodes are
unresolved and none is inactive. That is correct: a first customer message cannot establish whether a
termination complied with the formalities or violated good faith. Those are exactly the determinations the
process exists to make, and leaving them open is what keeps the evidence requests alive. An absence of
evidence never became a false.

When a returned document arrives — the cantonal official form, served separately on the spouse — three
predicates resolve, `termination_void` goes **inactive**, and two chains become wrong-branch requests.

## The finding that matters for the benchmark

| | intake | after the form |
|---|---|---|
| clean chains | 38 | 36 |
| wrong-branch chains | 0 | **2** |
| justifications | 35 | **33** |
| distinct requests | 19 | **19** |
| distinct document types | 16 | **16** |

Resolving the branch withdrew two justifications and produced two wrong-branch requests, exactly as
designed. **But no document dropped off the checklist**, because on this scope the documents are
over-determined: most are justified by several nodes at once, so losing one justification leaves the
document still required by another.

That is a real limitation of this scope, not of the machinery. The causal claim the paper wants — that
resolving the process removes unnecessary requests — cannot be demonstrated on a graph where every document
has three reasons to exist.

**What the benchmark must therefore contain**, and what the sufficiency gate already flagged as available:
cases where a document is justified by exactly one branch, so that resolving that branch removes it. The
gate's S2 (rent increase, where a nullity finding under VMWG 19 forecloses the whole justification route)
and S7 (legal-expenses cover, where a waiting-period exclusion removes the entire downstream obligation)
both have that shape. The termination scope, for all its richness, does not.

This is the difference between a benchmark that measures the claim and one that cannot. It was found by
running the pipeline rather than by reasoning about it, and it is why the next step is scope selection on
discriminating power rather than on graph size.
