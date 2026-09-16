# Method

An agentic system reads authoritative law, reconstructs the operational process it implies as a source-grounded
executable graph, locates a case inside that process, and derives the documents the still-active parts of the
process require. The chain it maintains is:

    authoritative passage -> proposition -> process node -> active obligation -> required fact
                          -> evidence capability -> document or document set

Each arrow is either a model step with a verification gate behind it, or a deterministic assembly. No arrow is
both.

## 1. Authority corpus

Swiss federal acts are fetched as Akoma Ntoso XML from the Fedlex filestore, not from the ELI landing pages, which
are JavaScript shells. Article and paragraph text is extracted from the visible content with block-boundary
spacing and whitespace normalisation, under a single recorded extraction identity
(`fedlex-akn3-visible-text-blockspaced-whitespace-normalization/1.1.0`). Every passage carries its act, article,
consolidation date, source URL, and the SHA-256 of both its own text and the fetched document.

The per-act XML filename suffix is not constant across acts — OR resolves at 4, VMWG at 1 — so the resolver probes
rather than assuming. 86 passages across OR, VMWG, ZPO and VVG.

This step has already found a defect in third-party data: a passage of OR Art. 259g Abs. 1 as cited elsewhere in
the repository differs from the Fedlex consolidation it names by two commas.

## 2. Proposition extraction, with an exact-quote gate

Each passage is read into typed propositions — condition, obligation, prerequisite, deadline, exception,
allowed action, required decision, dependency — and each proposition must carry the exact span it rests on. **A
proposition whose quote is not a verbatim substring of its passage is dropped**, not flagged. This is the gate the
rest of the method depends on, and it is mechanical: normalise whitespace, test for substring, discard on failure.

## 3. Synthesis into a process graph

Propositions are assembled into nodes, transitions with branch conditions, deadlines and obligations. Every
`supported_by` must resolve to a supplied proposition and every transition endpoint must exist, or the graph is
rejected. Support is declared per element as supported / uncertain / unsupported, and anything unsupported must
also appear in `unsupported_gaps`.

Synthesis is instructed that a sparse grounded graph is correct and a plausible ungrounded one is wrong, and
additionally that two kinds of coverage are required: a node that *determines* every substantive standard the
propositions state, not merely the procedure around it; and an obligation wherever the propositions say a party
must show, prove, justify or notify something.

## 4. Locating the case

Branch predicates are decided against the case materials with three verdicts — true, false, unresolved — under two
rules that do most of the work.

**An unknown is not a false.** A predicate the materials do not settle is `unresolved`, and a node reachable only
through an unresolved predicate stays unresolved rather than being dropped. Dropping it is how an
evidence-gathering system silently stops asking for the thing that would have settled the question.

**Alternatives are decided together.** Predicates are grouped by the step they branch from, and at most one
alternative out of a step may hold. If two still come back true, the whole group reverts to unresolved and the
contradiction is recorded — the only reading that does not invent a choice the case never made. This was added
after a contradiction between a claim and its negation was observed keeping every branch alive, which stopped the
system withdrawing anything at all.

A verdict of true or false must quote the case materials verbatim; one that does not **reverts to unresolved**.
Activation is then propagated deterministically.

## 5. Compiling obligations into documents

For each node with obligations: the facts that must be established, and for each fact the evidence capabilities
that could establish it — what the evidence must *show*, never a document name. Capabilities are mapped to
document routes in a second step restricted to a fixed catalogue; a route naming anything outside it is rejected.
A capability with no route is an **evidence gap** and is reported rather than dropped.

Chains are then assembled deterministically and classified: clean, orphan request (no chain), evidence gap,
wrong-branch request (reachable only from an inactive node), premature request (from an unresolved branch).

## 6. Baselines

All arms share model, temperature, catalogue, held documents and scope statement.

| arm | what it sees |
|---|---|
| `b1_direct` | the case, the catalogue — predict the checklist |
| `b2_retrieval` | the case, the catalogue, retrieved authority passages |
| `b3_graph_then_list` | the case, the catalogue, **the induced graph** — produce the checklist |
| `b3t_summary_then_list` | as B3 but with a prose summary of the graph instead of the graph |
| `b6_prior_composition` | the minimal obvious fix: compose from prior cases |
| `b5_induced_graph` | the full pipeline — interpret, compile, assemble chains |

`b3_graph_then_list` is the critical ablation: it isolates whether the value is in the **process structure** or in
the deterministic compilation built on top of it. Arms other than B5 emit no chains, so chain metrics score them
zero by construction — which is the honest reading, since they offer nothing to check.

## 7. Evaluation

Ground truth is a **reference contract** built from the sources by agents that never see the induced graph, under
the same quote gate, with a voted document layer and adjudicated live/dead conditions per decision
(`REFERENCE_CONTRACTS.md`). Per case, three further adjudicators mark each decision live / dead / unknown from the
narrative alone; unknown keeps a decision open.

The discriminating measurement is the **branch intervention**: one case, and the same case with a minimal factual
addition that settles one predicate. The contract says which documents that releases. The question is whether an
arm stops asking for them — withdrawal recall — while keeping the ones still required, retention.

Intervals bootstrap over **scenarios**, not cases: five cases of one scenario are five variations on one fact
pattern, and resampling cases would shrink every interval by roughly √5 for no reason but how the corpus was
generated.
