# A Source-Grounded Process Representation Does Not Confer Correct Retraction Behaviour: The Interpreting Model Decides the Sign

## Abstract

A structured, source-grounded representation is usually evaluated by pairing it with one language model and
reporting the resulting number as a property of the representation. We show this measures the pairing. We build a
system that fetches Swiss federal tenancy law, extracts propositions under a verbatim-substring gate, induces a
process graph, and deterministically compiles the obligations of still-active nodes into a document checklist that
retracts a document when every node requiring it closes. Holding the induced graph, the reference contract, the
case corpus and the pipeline code fixed, and changing only the model that interprets a case against them, the
identical artifact scores **+0.119** excess withdrawal recall over its own random-drop baseline on one reasoner and
**−0.077** on another; across four reasoners the two positive intervals lie entirely above zero and the two
negative intervals entirely below it. This is a measurement paper. We also report a volume control without which
the headline comparison reads +0.553 rather than +0.118, a 4.7-fold difference, and under which one arm's sign
inverts; two independently built legal scopes on which the static checklist task is degenerate — one distinct
ground-truth checklist across 30 and across 49 cases respectively, with a case-ignoring modal predictor at F1
1.000 on the rent-increase development cases; a transfer failure to a second scope whose ceiling was computed from
the contract before the run; and a constitutive verbatim gate that caught a fabricated statutory article. We do
not demonstrate a general method. The positive result is bounded by one scope of two and two reasoners of four,
and we have no test that predicts the boundary short of running it.

---

## 1 Introduction

We ran the same experiment four times. The induced process graph was frozen and byte-identical. So were the
reference contract it was scored against, the case corpus, and the pipeline code. The only thing we changed was
the model that reads a case, decides the graph's branch predicates against it, and compiles the resulting
obligations into documents.

On `gpt-5.6-terra` the artifact scored **+0.119** excess withdrawal recall over its own random-drop baseline, 95%
CI [+0.108, +0.125]. On `claude-haiku-4.5` the same artifact scored **−0.077**, CI [−0.092, −0.070]. These two
intervals do not overlap and they lie on opposite sides of zero: on one reasoner the compiled checklist withdraws
the documents the legal process actually released, and on the other it withdraws documents anti-correlated with
them. Two further reasoners split the same way — `gemini-2.5-flash` at +0.109 [+0.107, +0.112] and `deepseek-v3.2`
at −0.034 [−0.037, −0.031]. All four ran on the same 28 held-out pairs. Two of four carry signal; two of four are
actively wrong. The two positive intervals lie entirely above zero and the two negative intervals entirely below
it, so the signal and anti-correlated groups are cleanly separated, though the two positive intervals overlap each
other over nearly their whole width and the reversal claim rests on the extreme pair.

This is not a run that broke. Every model was asked the same nine branch predicates on each of 58 case runs, and
every model resolved 10–12% of them and left the rest unresolved — near-identical rates (10.5%, 11.5%, 11.7%,
11.3%). The pipeline executed the same way each time; what differed was which documents each reasoner asked for
and which it let go.

### 1.1 Why a single-model result about a "grounded" method is not a result about the method

A structured representation is not self-executing. A process graph, a knowledge graph, a program sketch, a plan —
each is inert until some interpreter decides what it says about the instance in hand. The claim such papers make
("grounding the reasoning in an explicit structure improves *X*") is therefore a claim about a composite of two
factors, representation and interpreter, and a single-model experiment estimates that composite at one level of
the second factor while attributing the estimate to the first. If the two factors interact, the reported main
effect is not identified. Our four runs show an interaction large enough to reverse the sign of the conclusion.

We state the finding as a **representation × interpreter interaction**, not as dominance of one factor over the
other. The design never varies the representation: the graph, the contract, the catalogue and the code are frozen
across all four runs. An experiment that holds one factor fixed can establish that the outcome depends on the
other; it cannot rank their contributions. Claiming the reasoner "dominates" the representation would repeat, in
the opposite direction, exactly the composite-attribution error this section is about.

Two of the usual defences against this reading do not apply, and one does not survive inspection.

It is not decoding noise: the spread far exceeds the bootstrap intervals, which resample over scenarios rather
than cases. It is not an artifact of a fragile representation: the representation is exactly the thing held
constant.

It is **not** true, however, that none of the observable proxies for engagement with the graph tracks the split.
We recorded three: mean documents requested, mean chains compiled, and predicate-resolution rate. Request volume
does not separate the groups (signal: 6.52, 7.41; anti-correlated: 6.50, 12.55) and neither does resolution rate
(signal: 10.5%, 11.7%; anti-correlated: 11.3%, 11.5%). **Chain count does separate them perfectly**: the two
reasoners carrying signal compiled 31.0 and 34.0 chains per run, and the two anti-correlated ones compiled 39.0
and 67.6. With four models, a chance separation in that direction has probability 1/6, so this is a pattern worth
recording and far short of an explanation. We report it because it is in our own diagnostic table and because it
is the most obvious candidate for the predictor we otherwise lack.

What we cannot do is predict the split in advance. We can only report it, which is the practical point: a paper
reporting one model's number has not established that its structure helps, and has no way to know, from within its
own design, whether a second model would have reversed it. Our own confirmatory read was single-model before we
ran the generality check.

### 1.2 What we measure

The system is agentic and source-grounded end to end. It fetches Swiss federal acts as Akoma Ntoso XML, hashes
every passage, extracts typed propositions each carrying a verbatim span, induces a process graph from them,
locates a case in that graph under a `true / false / unresolved` verdict scheme in which an unknown never
collapses to a false, and deterministically compiles each still-active node's obligations into required facts,
then evidence capabilities, then documents drawn from a fixed catalogue. A document is requested because a
specific node is open, and released when every node requiring it closes.

That last property is what we score. The static question — *which documents does this case need* — turns out to be
unmeasurable on the corpora we built (§5.1). The discriminating question is what happens when a fact arrives. We
pair each case with the same case plus a minimal factual addition that settles one predicate; an independently
built reference contract says which documents that settles free; and we ask whether each arm stops requesting
them.

### 1.3 Contributions

- **Reasoner-dependence of a frozen artifact.** One frozen artifact, four reasoners, 28 held-out pairs across 6
  scenarios each: excess withdrawal recall spans **+0.119 [+0.108, +0.125] to −0.077 [−0.092, −0.070]**, with
  near-identical predicate-resolution rates in every condition. Neither headline effect replicates: "direct
  prediction is anti-correlated with correct withdrawals" holds on one model of four; "the compiled chain carries
  signal" holds on two of four and is anti-correlated on the other two (§5.3).
- **A volume control is required, and it is worth 4.7×.** Arms that request more documents have more to drop, so
  raw withdrawal recall is not comparable across them. Scoring each arm against **itself dropping the same number
  of its own requested documents at random** takes the pipeline's raw advantage over direct prediction from
  **+0.553 [+0.459, +0.613]** to a within-arm excess of **+0.118 [+0.106, +0.126]**, and flips direct prediction
  from a weakly positive raw recall of 0.038 to **−0.061 [−0.096, −0.026]** — worse than chance. It also
  qualifies the preregistered primary, which is supported (+0.083 [+0.018, +0.151]) while the arm it favours has a
  within-arm excess of only +0.011 [−0.017, +0.038] (§5.2).
- **The static checklist task is degenerate on both scopes we built.** Two independently gated scopes — rent
  increase (30 cases, 12 decisions, mean reference set 10.0) and termination (49 cases, 21 decisions, mean 17.0)
  — each yield **exactly one distinct ground-truth checklist across the cases measured**, so a predictor that
  ignores the case and emits the modal list scores **F1 1.000** on the rent-increase development cases. On a
  six-arm floor check, five arms fall within **0.034 F1** of one another (0.601–0.635) and all six lose to not
  looking (§5.1).
- **Transfer fails, and the failure was computable before the run.** On the second scope, 49 pairs across 8
  scenarios, **no arm's interval excludes zero** (+0.015, +0.019, −0.012). The ceiling was computed from the
  contract alone and recorded in the preregistration: the probed decision releases 3 documents and no other single
  decision releases more than 1, against 6 for the rent-increase probe. Measured, the contract released a mean of
  **1.57** documents per pair (§5.4).
**Not a contribution: the verbatim gate.** Our pipeline admits a quote only if it is a verbatim substring of a
fetched, hashed primary source, discarding failures at authoring time. An adversarial literature check established
that this is preempted — Wang (2026) performs the same admission-gate-with-discard into a persisted registry,
GopherCite (2022) and CHyD (2026) enforce verbatim-ness at decoding rather than by scoring, and CANONIC (2026)
states the constitutive-versus-diagnostic framing directly (§2). We describe the gate in §3.2 as system
description. The single element we did not find elsewhere — that the predicate also resolves the cited authority
against a consolidation-versioned source, so it rejects a provision existing at *no* consolidation — is reported
there with its n=1 catch and the aggregate discard rate, as an illustration rather than a result.

### 1.4 What this paper does not claim

It does not demonstrate a general method. The positive result is bounded by one scope of two and two reasoners of
four, and we have no test that predicts the boundary short of running it. It makes no static-checklist claim,
because the task cannot separate methods on the corpora we built. It does not claim the induced graph is unique:
two independently source-grounded constructions of the same scope — the induced process graph and the reference
contract — partitioned it differently, and nothing in the sources fixes the granularity. We note that these two
artifacts are not two instances of the same procedure: the graph is induced by the pipeline, while the contract is
ground truth built by a separate authoring procedure. Only one induction of the scope exists.

Three errors we made are reported in the body rather than repaired out of the record, because they are what the
measurements cost. We computed that the primary outcome was structurally impossible and committed a document
acting on it; the computation pooled per-node document supply across cases when the compiler recomputes it per
case, and the data refuted it. We nearly reported a set of cross-scope citation *verification* rates (25.6–59.6%)
as if they were fabrication rates — which would have implied fabrication at 40–74% — before establishing that they
were an artifact of contracts storing sources and quotes as unmapped parallel lists, and retracted them. And we
amended the preregistered primary away from the arm that later turned out to be the only informative one, on
development data that no longer reproduces as recorded (§5.2).

---

## 2 Related Work

Positioning here rests on an automated adversarial sweep (24 agents; five claims × four search angles, then a
per-claim adversary instructed to preempt the claim). **Coverage is incomplete and we say so:** two independent
sweeps of the same claim returned roughly 50% disjoint hit sets, so a reviewer may surface work neither pass found.
Only sources an agent opened and read are cited; anything returned as a search snippet only is excluded.

**Verbatim grounding as an admission gate — this is not our contribution.** Making verbatim-ness *constitutive*
rather than diagnostic is established at least four ways. Wang (2026, arXiv:2606.00994) uses substring
correspondence as an admission gate into a persisted registry with failures discarded — the same operation we
perform. Menick et al. (2022, GopherCite, arXiv:2203.11147) enforce verbatim-ness by constrained sampling rather
than by scoring. Signé et al. (2026, Constrained Hybrid Decoding, arXiv:2609.10046) impose it as a hard decoding
constraint. Hadley (2026, CANONIC, arXiv:2607.05410) states the constitutive-versus-diagnostic thesis in nearly the
words we first used. Related: CAMS (arXiv:2606.23989) anchors claims to quotations but relaxes to windowed indel
similarity above a threshold; Slobodkin et al. (2024, ACL, arXiv:2403.17104) constrain selection and planning but
not the final sentence; Zhang et al. (2024, Quote-Tuning, arXiv:2404.03862) reward quoting instead of gating it.
We therefore report our gate in the Method section, not as a contribution. The one element we did not find
elsewhere is that the predicate is *ternary*: it resolves the cited authority against a consolidation-versioned
primary source, so the same rule rejects both non-matching text and a provision that exists at no consolidation.
Context-bound quote guarantees cannot detect the latter because they never ask whether the cited provision exists.
Windisch et al. (2026, Cureus 18(5):e108666) make the further point we adopt: a byte-exact span does not entail
that the span *supports* the proposition, so mechanical validity and semantic support must be reported separately.

**Structure induced from law, and what it is used for.** GraphCompliance (arXiv:2510.26309) aligns a GDPR policy
graph with a scenario graph; Dutch environmental-law work generates DMN decision models benchmarked against
gold-standard models in production (arXiv:2604.17153); LLM civil-legal-aid intake screens eligibility
(arXiv:2410.03762). All three decide *outcomes* or *eligibility*. None derives document or evidence requirements,
none has an evidence-capability layer, and none routes over a closed document catalogue. Falkor-IRAC
(arXiv:2605.14665) vetoes answers lacking a graph path, and Italian tax-court extraction (arXiv:2607.03325) gates
citation identifiers rather than propositional spans. The typed chain we compile — active node → required facts →
evidence capabilities → document routes over a fixed catalogue — is what makes document-level *release* computable,
and we found no precedent for it.

**Belief revision and update consistency.** Wilie et al. (2024, *Belief Revision: The Adaptability of Large
Language Models Reasoning*, EMNLP 2024, arXiv:2406.19764) introduce Belief-R and ΔR, measuring whether models
revise answers when new premises arrive. Our measurement differs in object: we score retraction of a
*requirement set* against a reference contract built independently from primary sources, and we report a
three-rung ladder with a null middle rather than a single revision score.

**Random baselines for set-valued output.** De Vries, Geva & Trotman (2012, *Divergence from a Random Baseline*,
arXiv:1208.5654), with Hubert & Arabie (1985) and Vinh et al. (2010), establish correcting clustering measures
against chance. Every such construction randomizes over a *fixed external universe* while copying the system's size
structure. Our null instead draws from **the system's own request set**, which is what lets it separate an
anti-correlated arm from a merely weak one — a distinction a universe-level null cannot make.

**Degenerate benchmarks.** Kaushik & Lipton (2018, *How Much Reading Does Reading Comprehension Require?*, EMNLP),
with Tsoumakas & Katakis (2007) on distinct-label-set counts and Meding et al. (ICLR 2022), establish
partial-input and majority-class critiques. Each measures a partial-input model against a *varying* label. We
report the limit case: `|distinct gold label sets| = 1` across two independently constructed scopes.

---

## 3 Method and System

The system reads authoritative law, reconstructs the operational process that law implies as a source-grounded
graph, locates a case inside that process, and derives the documents the still-active parts of the process
require. The chain it maintains is

> authoritative passage → proposition → process node → active obligation → required fact → evidence capability →
> document route

Every arrow is either a model step with a mechanical gate behind it, or a deterministic assembly. No arrow is
both.

| stage | model? | gate | on failure |
|---|---|---|---|
| corpus extraction | no | SHA-256 per passage; per-act SHA-256 of the fetched document | — |
| proposition extraction | yes, per passage | quote must be a substring of the passage; kind must be in a fixed vocabulary | proposition discarded, logged |
| graph synthesis | yes, once per scope | every `supported_by` must resolve to a supplied proposition id; every transition endpoint must be an existing node | recorded on the artifact as `grounding_problems` |
| predicate verdicts | yes, per case | a `true`/`false` verdict must quote the case materials verbatim; alternatives out of one step must not both hold | verdict reverts to `unresolved`, logged in `ungrounded` |
| facts and capabilities | yes, once per graph | cited proposition ids must be known | recorded as `problems` |
| capability → document routes | yes, once per graph | route may name only catalogue entries | route discarded, logged |
| activation, chain assembly, fault classification, checklist | no | — | — |

Three of these gates are *constitutive* — the ungated object never enters the artifact. Proposition quotes and
document routes are discarded outright; a predicate verdict whose quote is not found in the case materials is
replaced by `unresolved` before anything downstream sees it, so the ungated verdict likewise never enters the
artifact, even though the attempt is logged. (The reference contract of §4.1 adds a fourth, on evidence quotes.)
**Two** are *reporting* gates — graph synthesis and the facts/capabilities step — which annotate the artifact
rather than discard, and whose annotations are carried through to the intermediates. We distinguish the two kinds
because only the first supports a claim of the form "nothing of this kind in this artifact is unverified".

### 3.1 Authority corpus

Swiss federal acts are fetched as Akoma Ntoso XML from the Fedlex filestore **TODO[citation: Fedlex filestore]**,
not from the ELI landing pages, which are JavaScript shells returning HTTP 200 with no law text. The failure mode
is worth naming precisely: a checker that tests only whether the URL resolves records a success against a page
containing no law at all, while a substring check against the same page fails for a reason unrelated to the
citation's correctness. Either way the check is uninformative. The HTML twin does contain the text but drops the
space before lettered list items (`Vermieter: a. sie` → `Vermieter:a. sie`), which is fatal to a substring gate;
five of nineteen reference passages failed to reproduce from it. The XML twin reproduces 18 of those 19 byte for
byte. The nineteenth is a defect in the third-party data rather than in the extractor: its text of OR Art. 259g
Abs. 1 carries two commas the consolidation it names does not have, and it is recorded rather than overwritten.

Extraction runs under one recorded identity,
`fedlex-akn3-visible-text-blockspaced-whitespace-normalization/1.1.0`: visible text of the paragraph, authorial
notes dropped, a separator inserted at block boundaries so list items keep their spacing, whitespace normalised.
The per-act XML file index is not constant — 4 for the Code of Obligations, 1 for the tenancy ordinance — so the
resolver probes rather than assumes. Every passage carries its act, article, authority id, exact text, a snapshot
id that encodes the consolidation (for example `fedlex-or-20260101-de`), its source URL, and the SHA-256 of its
own text. The SHA-256 of the fetched document is recorded once per act on the act record, not per passage, and the
artifact checker verifies the per-passage text hash only.

The committed bundle holds **130 passages** across four acts: OR (SR 220, consolidation 2026-01-01, 61 passages),
ZPO (SR 272, 2025-01-01, 43), VMWG (SR 221.213.11, 2025-01-01, 17) and VVG (SR 221.229.1, 2024-01-01, 9). Artifact
verification reports **0 hash mismatches**. One requested passage, VMWG Art. 19a, is absent from the act at that
consolidation and is recorded as missing rather than approximated — a fact that reappears in §5.5 as the article a
reference-contract author cited and quoted.

### 3.2 Proposition extraction under the verbatim gate

Each passage is read in isolation and yields typed operational propositions in a fixed eight-kind vocabulary
(condition, obligation, prerequisite, deadline, exception, allowed action, required decision, dependency). The
prompt forbids completing a passage from background knowledge or importing a step from how such matters are
usually handled, and asks for an empty list where a passage establishes nothing operational.

The gate is mechanical and unconditional: the quoted span is stripped of surrounding whitespace and tested for
substring containment against the passage's exact text; on failure the proposition is discarded. We note for
accuracy that no whitespace *normalisation* is applied at this gate — the test is a raw substring test on
unnormalised text. (Whitespace normalisation is applied at the reference contract's evidence gate, §4.1.) **A
proposition whose quoted span is not a substring of its own passage is dropped, not flagged.** A second, separate
check drops any proposition whose `kind` is outside the fixed vocabulary.

The extraction pool used for both scope syntheses is **170 propositions citing 63 distinct passages** — by kind,
55 conditions, 52 obligations, 26 allowed actions, 18 deadlines, 17 exceptions, 1 prerequisite and 1 dependency.
This is the whole extraction pool as it stood at induction time, not a tenancy subset: 9 of the 63 passages and 21
of the 170 propositions come from the VVG, the Insurance Contract Act, which is needed only for a
legal-expenses scope that was never run. The by-act split of the 63 passages is OR 28, ZPO 17, VMWG 9, VVG 9.

Our prose record states that 7 propositions were dropped during this extraction.
**TODO[number not found: per-reason drop counts for the 170-proposition extraction].** The committed proposition
file is a bare list with no `dropped` block, so the drops cannot be recovered from the artifact, and the extractor
drops for two distinct reasons (unknown kind as well as quote failure), so the 7 cannot be attributed to the quote
gate alone.

### 3.3 Process synthesis

Synthesis sees the propositions and a one-line scope label. The payload per proposition carries its id, kind,
English statement, party, governs field and citation — so synthesis does see article-level statutory addressing
(for example `Art. 269d Abs. 1`), though it sees no hand-authored process template, which is the shortcut this
work exists to remove. It emits nodes, transitions with branch conditions, deadlines, obligations, and an explicit
`unsupported_gaps` list. Each element declares a support level (supported / uncertain / unsupported) and the
proposition ids behind it; anything marked unsupported must also appear in the gaps list.

One property of the payload matters for what the artifact can claim. **Synthesis never sees the gated quotes.**
The verbatim spans that passed §3.2 are not sent; only the model-written English `statement` is. The obligation
compiler's payload is likewise restricted to proposition id, kind, statement and citation. Everything the graph
and compiler emit — node labels, the `why` field, obligation statements, fact statements, capability `must_show`
strings — is therefore model prose summarising German statute, not gated span. The verbatim property attaches to
the terminal authority text, which the product resolves by authority id at display time, and to the propositions
themselves. It does **not** propagate to the graph, the compiler, or the natural-language parts of the
justification trace, and we do not claim that it does.

The validator checks every `supported_by` against the supplied proposition ids and every transition endpoint
against the node set. On the termination scope it caught one violation (a transition citing two proposition ids
that do not exist) and that graph carries it as a `grounding_problem`.

The graph used for the rent-increase experiments was induced once and reused unchanged: **13 nodes** (12
supported, 1 uncertain), **14 transitions** (12 supported, 2 uncertain) of which 9 carry branch conditions, 4
deadlines, 6 obligations, 3 declared gaps, **0 grounding problems** and 0 dangling transitions. The six
obligations attach to **4 of the 13 nodes**. The transfer experiment of §5.4 does **not** use this graph: the
termination scope has its own separately induced graph of 12 nodes and 11 transitions, carrying the one grounding
problem noted above.

### 3.4 Locating a case in the process

Branch predicates are decided against the case materials with three verdicts — `true`, `false`, `unresolved` —
under two rules that do most of the work.

**An unknown is not a false.** A predicate the materials do not settle is `unresolved`, and a node reachable only
through an unresolved predicate stays unresolved rather than being dropped. Collapsing unresolved to inactive is
exactly how an evidence-gathering system silently stops asking for the thing that would have settled the question.

**Alternatives are decided together.** Predicates are grouped by the step they branch from and presented as a
group; at most one alternative out of a step may hold. If two still return `true`, the *whole group* reverts to
unresolved and the contradiction is recorded — the only reading that does not invent a choice the case never made,
and one that keeps both branches' evidence requirements alive. This was added after contradictory verdicts were
observed keeping every branch alive at once, which stopped the system withdrawing anything at all.

A `true` or `false` verdict must quote the case materials verbatim; one whose quote is not found reverts to
`unresolved` and the attempt is logged. Predicates the model does not return at all default to `unresolved`.

Activation is then computed deterministically: roots are the nodes with no incoming transition; a fixpoint
iteration propagates state over edges under the order `inactive < unresolved < active`; an edge whose verdict is
`false` is not traversed; an unconditional edge behaves as `true`; and a target is `active` only if the verdict is
`true` *and* the source is active, otherwise `unresolved`. The model decides predicates; it does not decide
activation.

A representative run on the termination graph illustrates the conservatism: 9 predicates decided, all
`unresolved`, yielding 1 active node, 11 unresolved and 0 inactive — the system asks for everything, and says for
each predicate what would settle it.

### 3.5 Compiling obligations into documents

Compilation is case-independent given a graph: it is computed once per graph and reused across every case in a
run. It proceeds in two model steps with different vocabularies, deliberately separated.

First, for each node and its obligations, the model names the **facts** that must be established — propositions
about the case that are true or false, never documents and never actions — and for each fact the **evidence
capabilities** that could establish it, stated as what the evidence must *show* ("shows the date a notice was
received by the addressee"). Naming a document here is forbidden.

Second, capabilities are mapped to **document routes** against a fixed catalogue (16 document types for the
rent-increase scope, of which the reference contract admits 11; 18 for termination). A route is a set of documents
that jointly suffice; alternatives are permitted; the smallest sufficient set is preferred. **A route naming
anything outside the catalogue is discarded**, and a capability left with no route is an **evidence gap** —
reported, not dropped. On the frozen rent-increase graph this yields 13 nodes compiled, **39 facts, 40
capabilities, 27 routes, 22 capabilities carrying at least one route, and 18 capabilities with no route in the
catalogue**. Surfacing that last number is the point: a system that silently omits what it cannot evidence looks
more competent and serves the handler worse.

The 16-document rent-increase catalogue is attested in our prose record rather than enumerated in a committed
artifact; it is corroborated by the run data, in which the arms request exactly 16 distinct document types with
zero out-of-catalogue rejections. The 18-document termination catalogue is enumerated in the gated contract.

One claim we previously made about this stage is false and we withdraw it. The 9 rent-increase nodes carrying no
obligation do **not** bound what the compiler can release: the compiler is invoked over every node unconditionally,
and in the committed artifact **14 of the 39 facts and 15 of the 40 capabilities come from those 9 obligation-less
nodes** (one node alone yields 6 facts and 6 capabilities). Sparse obligation coverage is still a defect, but it is
not the bound we described.

### 3.6 Deterministic chain assembly and fault types

Assembly is pure code. A chain is emitted for each **(capability, route) pair** — so the 22 capabilities carrying
at least one route produce 27 chains on the frozen graph, because 5 capabilities carry two routes each. Each chain
carries the document types, the route, the capability and what it must show, the fact, the node and its activation
state, the propositions behind the fact and the authority ids those propositions resolve to. Four faults are
first-class objects rather than filtered-out noise:

- **evidence gap** — a capability with no catalogue route;
- **wrong-branch request** — a chain whose node is `inactive`;
- **premature request** — a chain whose node is `unresolved` *and* whose fact is conditional (`only_if`);
- **orphan request** — a requested document that no clean chain justifies.

The orphan rate is `|requested − justified| / |requested|`. We flag that this metric is **definitional, not
empirical, for arms that emit no chains**: with an empty chain list every request is an orphan automatically. We
previously described orphan requests as "the fault a direct predictor cannot avoid"; that is true by construction
of the scoring, not a measured property of direct prediction, and we withdraw the empirical reading.

The requestable checklist is clean chains only, deduplicated by document set, each entry carrying its
justifications. Held documents are handled by skipping a chain **only when every document in its route is already
held**; otherwise the entry keeps its full document list and records the residue separately as `still_missing`, so
a partially-held route is still shown in full. The deduplication key is the full document set including held
items. (This is distinct from the *scoring* convention of §4.1, under which held documents are removed from both
the reference set and every arm's request set.)

Note the interaction with §3.4: a chain from an *unresolved* node whose fact is unconditional is clean and stays in
the checklist. Unresolved branches keep asking; that is the retraction-safety rule expressed at the checklist
level, and it is also the reason the compiler over-requests.

Retraction is an event, not a recomputation. A diff over two states returns what was withdrawn, what was added,
which predicates flipped and which nodes closed — the audit record shown when a fact arrives and a requirement
goes away. This is what §5.2–§5.4 measure.

### 3.7 The product surface

The service layer composes the case interpreter and the obligation compiler and defines no reasoning of its own,
so that "the product runs the method" is a property of the code rather than a claim to audit. For each request it
returns the node and its activation state, the authority with its exact text and Fedlex URL, the required fact,
the capability the document establishes, and the predicate whose resolution would withdraw it. On a traced
development case it produced **3 document requests, 11 clean chains, 11 evidence gaps and 2 wrong-branch chains**
— the weaknesses are surfaced at the interface rather than suppressed. (We previously also reported "24 compiled
capabilities" for this trace; the trace carries no compiled-capability block and we drop the figure.)

### 3.8 What this system is not

The pipeline induces one graph per scope from one corpus and interprets cases against it. It has no applicability
gate: the entry node of the rent-increase graph has no incoming condition, so the process cannot be told that the
scope does not apply, and a case outside the scope inherits the full modal document list. The sources condition
exactly this (OR 253a, 253b, and the reference contract's first decision), the passages were available to
synthesis, and no node was built from them. The defect is unrepaired and is reported as measured; repairing it is
a method change and would require re-induction and re-measurement. This defect interacts with a corpus problem
documented in §4.4: an out-of-scope case produces the full modal list, which is what made a contaminated case
bucket look like evidence of saturation.

---

## 4 Evaluation Design

### 4.1 Ground truth is built from the sources, not from the system

The object the system is scored against is a **reference contract**: for a claim scope, the set of decisions a
handler must reach, the documents each decision needs from the party, and the condition under which each decision
closes. If the induced process graph authored its own ground truth, every number below would measure
self-consistency. The contract is therefore constructed from the primary sources by an agent that did not see the
induced graph, and is built in stages separated by what each stage is permitted to read.

1. **Spine.** An independent agent reads the Swiss federal sources for the scope and emits the decisions the law
   requires, each carrying the authorities it rests on and the exact span it relies on.
2. **Verbatim quote gate.** A quote is admitted only if it is a verbatim substring of a passage fetched from
   Fedlex, hashed, and cited by that same decision; whitespace is normalised and nothing else is. Failures are
   discarded at authoring time and logged with the citation that failed to support them. The gate is
   *constitutive*: downstream stages never see unverified text, and a document author cannot rescue a quote the
   gate dropped because the ungated spine is never exposed. On the rent-increase scope, 44 of 58 proposed quotes
   verified and 14 were dropped; all 12 decisions retained at least one verified quote.
3. **Voted document layer.** Three authors, working only from the gated spine, independently state which documents
   each decision needs from the party. Proposals outside a fixed 16-document catalogue are rejected; none
   occurred. A document is admitted on two of three votes: 27 document–decision pairs were unanimous, 3 were
   admitted 2–1, and 7 singletons were dropped. The resulting contract uses 11 of the 16 catalogue documents
   across 12 decisions.
4. **Adjudicated conditions.** One adjudicator reduces the three authors' `live_when` / `dead_when` formulations
   to a single checkable pair per decision. These conditions are what make a requirement *retractable*.
5. **Per-case ground truth.** Three further adjudicators, who see neither the induced graph nor any arm's output,
   mark every decision `live` / `dead` / `unknown` against the case narrative alone. A decision is settled on a
   two-of-three majority.

**What the blind is, and what it is not.** For the rent-increase contract the recorded provenance states that the
spine was authored from Swiss federal sources with *no access to the induced process graph*, and that the
document layer worked from the gated spine alone. A stricter reading discipline — that no file whose name
contains INDUCTION, COMPILER, PIPELINE or SCOPE_SELECTION was opened — is recorded only for the **termination**
contract. We therefore claim independence from the induced graph and the pipeline outputs, and we do **not** claim
a recorded blind against the proposition set for the rent-increase contract.
**TODO[verify: reading discipline for the rent-increase contract author against the proposition set].**

Two scoring conventions fix what the resulting numbers mean, and both are decided in favour of leaving work open.

**`unknown` is not `dead`.** A decision the adjudicators cannot settle from the narrative stays in the reference
set, and ties fall open. The alternative — reading "cannot tell" as "not needed" — would reward a system for
ignoring everything a case does not spell out. The per-case reference set is the union of documents required by
all decisions that are `live` or `unknown`.

**Held documents leave the reference set, not the score.** A document already on file (here `lease_contract`) is
not a request, so it can be neither a hit nor a miss; it is removed from the reference set and from every arm's
request set before scoring.

The contract procedure was run a second time on a different scope (termination: 21 decisions, an 18-document
catalogue, 21 of 21 decisions retained; document votes 34 unanimous, 13 majority-only, 16 singletons dropped).
Its audit block records 106 quotes in, 91 kept, 15 dropped. **TODO[verify: the termination contract's own
`scope_statement` asserts "135 of 135 candidate quotes passed", contradicting its audit block's 91 of 106; the
91/106 figure used here is the audit block's.]** We describe this second run as independent *of the induced
graph*, not as independent of the first contract's author: the termination contract records its author as
"Annotator 1" and the rent-increase contract records no author identity, so we cannot claim the two contracts were
built by different people.

### 4.2 The branch-intervention paired design

The static task — predict the document checklist for a case — cannot separate methods on these corpora. Both
gated scopes yield exactly **one** distinct ground-truth checklist across the cases measured (30 rent-increase
cases, 49 termination cases); a predictor that ignores the case and emits the modal list scores F1 1.000 on the
rent-increase development cases; and five of six matched baselines land within 0.034 F1 of one another (§5.1).

The cause is structural but it is **not the same structure on both scopes**, and we correct an earlier account
that said it was. On termination, 14 of 18 documents are required by two or more decisions, so a document is
rarely released by settling one decision. On rent increase the mapping is the opposite shape: **6 of 11 documents
are required by exactly one decision**, and only 3 of 11 by six or more. What the two scopes share is the second
half of the diagnosis — the decisions a first-contact intake message actually settles are not the decisions that
own documents uniquely. We therefore state the structural claim per scope rather than as a single mechanism.

The evaluation scores **change rather than level**. Each unit is a *pair*: a case, and the same case with a
minimal factual addition that settles exactly one branch predicate. The reference contract says which decisions
that addition closes and hence which documents it releases. The question put to each arm is whether it stops
requesting those documents — **withdrawal** — while continuing to request the ones the contract still requires —
**retention**. A paired difference is unaffected by the constant level that saturates the static task.

**The intervention is chosen from the contract, in advance, not from outcomes.** Because a document is released
only when every decision requiring it settles, the ceiling of any probe is computable from the contract alone
before a single case is run:

| intervention | decisions it settles | documents it can release |
|---|---|---|
| `e03` the notice does use the prescribed form | D4, D7 | **0** |
| `e06` the tenant did challenge within 30 days | D3 | 1 |
| `e07` the tenant did not challenge within 30 days | D3, D11, D12 | **6** |

The originally preregistered probe, `e03`, can release nothing: `rent_increase_official_form` is required by eight
of the twelve decisions, and D7 requires no document from the party at all. A withdrawal comparison on `e03` would
have measured zero against zero. The primary probe is therefore `e07` — a minimal factual addition establishing
that the tenant did not bring a challenge to the conciliation authority within 30 days — amended (A1) before any
confirmatory case was run or read, on a computation with no experimental outcome in it.

On the held-out read this yields 28 pairs across 6 scenarios (30 originals, of which 28 have an `e07` variant),
adjudicator unanimity 93%, with a non-empty expected withdrawal on 25 of 28 pairs — above the preregistered
threshold of 15 below which no primary comparison would have been reported. The contract releases a mean of 4.7
documents per pair, 132 in total.

**Intervals bootstrap over scenarios, not cases**, 5000 draws, 95% percentile interval \cite{efron1979}. Five
cases of one scenario are five variations on a single fact pattern; resampling cases would shrink every interval
by roughly $\sqrt{5}$ for no reason but how the corpus was generated.

**Seeds, stated exactly.** Two RNG streams are involved and they are not the same seed. The 300-draw random-drop
simulation is seeded `20260916`, as is the bootstrap over the raw between-arm difference. The bootstrap that
produces every **excess-over-own-random** confidence interval reported in this paper — that is, every interval in
§5.2, §5.3 and §5.4 — is seeded `7`. Our earlier blanket statement that all intervals use seed 20260916 was wrong.

### 4.3 Three metric families

**Level.** Precision, recall and F1 of an arm's request set against the per-case reference set, plus two counts
kept separate from F1 because they name distinct faults: *burden*, the number of documents requested, and
*unjustified burden*, the number requested that the contract does not require. Reported as a floor check only, and
carrying no comparative claim, for the reason in §4.2.

**Change.** On each pair, let $E$ be the documents the contract releases, $K$ those it still requires, $B$ the
arm's request set before the intervention and $A$ after, with $W = B \setminus A$ its withdrawals. All three
change metrics are **pooled over pairs**, not averaged per pair:

$$\text{withdrawal recall} = \frac{\sum |W \cap E|}{\sum |E|}, \qquad
\text{withdrawal precision} = \frac{\sum |W \cap E|}{\sum |W \cap E| + \sum |W \cap K|}, \qquad
\text{retention} = \frac{\sum |(B \cap K) \cap A|}{\sum |B \cap K|}.$$

Withdrawal recall is the primary outcome; retention is the guardrail that prevents correct withdrawal from being
bought by dropping documents that are still needed (preregistered tolerance: not worse than the comparator by more
than 0.05).

**Justification.** Whether a request that was right was right *for a reason the contract also holds*. Node
identifiers cannot be compared directly: the induced graph and the reference contract partition the same law
differently — the graph runs downstream into the conciliation and court stages while the contract stays upstream
on form, timing and substance — and requiring their names to match would measure agreement on vocabulary. They
share exactly one vocabulary that neither author chose: the Fedlex authority identifiers, fixed by the corpus. A
chain therefore counts as grounded when the authority it rests on is an authority the contract also relies on for
a decision requiring that same document. *Chain rate* is the fraction of reference documents arriving with any
chain; *grounded rate* the fraction whose chain shares an authority with the contract. Arms that emit no chains
score zero by construction, which is the honest reading: they offer no justification to check, rather than one
offered and found wanting.

### 4.4 Corpus and split

The corpus is **synthetic**. The cases are drawn from a generated 150-claim intake corpus (`synthetic-150`); every
case registry carries the same hand-authored static rule template identifier, and each scenario is emitted in
German and English twins of one fact pattern. Earlier drafts of this work described these as "real Swiss tenancy
claims"; that is wrong and is corrected throughout. Nothing here is a measurement on real claims, and the external
validity of every number below is bounded accordingly.

The rent-increase portion is 50 cases in 10 scenarios of exactly 5. The split is on *scenarios*, not cases, and
was frozen before any held-out case was read: 4 scenarios (20 cases) development — `S1_form_defective`,
`S2_form_no_reason`, `S3_retroactive_start`, `S10_grant_allocation` — and 6 scenarios (30 cases) confirmatory —
`S4_miscalculated`, `S5_refrate_inconsistent`, `S6_refrate_double_count`, `S7_renovation_unclear`,
`S8_nebenkosten_reclass`, `S9_provisional_budget`. The family key is the scenario rather than the raw subject
line, because keying on the subject would have placed a scenario's German cases in development and its English
twins in the held-out set, introducing exactly the leak a family-paired design exists to prevent.

**A contaminated bucket, and what we withdraw because of it.** The working case bucket originally used for the
saturation measurement was built by keyword match, and Swiss tenancy termination and rent increase share the
phrase *amtliches Formular*. An audit found that 5 of those 15 cases were termination cases, not rent-increase
cases. The contamination inflated exactly the property being measured: asked to evaluate a termination narrative
against a rent-increase contract, adjudicators correctly answer `unknown` almost everywhere, `unknown` keeps a
decision open, and an out-of-scope case therefore produces the *full* modal document list. We accordingly
**withdraw the entire 15-case saturation measurement** — its 2 distinct checklists, its 14-of-15 modal share, its
0.97 modal-oracle F1, its 84% per-decision unanimity, and its per-decision settle counts. It was never re-measured
on clean cases. The saturation results we do report (§5.1) are computed on the clean 30-case and 49-case sets.

### 4.5 The volume control

Withdrawal recall as defined above is **not comparable across arms that request different numbers of documents**.
An arm that asks for more has more to drop, and therefore more chances to drop something the contract happened to
release. On the held-out read `b5_induced_graph` requests a mean of 10.0 documents where `b1_direct` requests 5.3
and `b3_graph_then_list` 5.5, and the reference set itself averages 10.0.

The control removes the confound by never comparing arms to each other. **Each arm is compared against itself
dropping the same number of its own requested documents at random.** For each pair, $|W|$ documents are sampled
without replacement from that arm's own pre-intervention request set $B$, 300 draws, and the expected number
landing in $E$ is recorded as that arm's random baseline on that pair. The reported statistic is the *excess over
own random baseline*,

$$\text{excess} \;=\; \frac{\sum_{\text{pairs}} |W \cap E| \;-\; \sum_{\text{pairs}} \mathbb{E}\big[|W_{\text{rand}} \cap E|\big]}{\sum_{\text{pairs}} |E|},$$

bootstrapped over scenarios. Both the size of the request set and the number of withdrawals are held at the arm's
own observed values, so the only thing the statistic can reward is the arm's choice of *which* documents to drop.
An interval above zero means that choice carries information; an interval below zero means the arm's withdrawals
are worse than dropping at random.

The control was **not preregistered**. It was added after the single held-out read, because the request counts in
the result table made the confound visible, and it is disclosed as an unplanned analysis rather than folded into
the plan. It is applied to every dynamic result reported in this paper.

Three limits of the control should be stated. First, it equalises volume within the withdrawal metric only:
retention is measured on each arm's own holdings and is reported separately. Second, it controls for how much an
arm asks for, not for whether asking for more is itself the right behaviour. Third — and this bears on how we
phrase comparisons — the control produces a **per-arm** statistic with a per-arm interval. No interval on the
*difference* between two arms' excesses was ever computed.
**TODO[number not found: bootstrap interval on excess(b5) − excess(b1) and on excess(b3) − excess(b1)].**
Comparisons between arms' excesses in §5 are therefore stated as a difference in what each interval shows, not as
a tested difference.

---

## 5 Results

Every number in this section is read from the committed analysis outputs or recomputed from the run artifacts.
Four analysis scripts produce them (`development_analysis.py`, `confirmatory_analysis.py`, `transfer_analysis.py`,
`model_generality_analysis.py`), and none makes a network call.

**A reproducibility caveat, stated up front.** All four scripts read their per-case inputs from scratch paths
outside the repository (run records, reference adjudications, the graph and proposition bundles). Those inputs are
**not currently committed**, so the claim in our reproducibility note that "every reported artifact is committed"
and that the analyses "read committed JSON" does not hold as written. The analyses reproduce today only because
the scratch files still exist on the machine that produced them.
**TODO[verify: commit the per-case run records, reference adjudications, and graph/proposition bundles, or
restate the reproducibility claim].**

### 5.1 The static checklist task is degenerate on both scopes

Six arms on the eight clean development originals, matched on everything but what the arm sees:

| arm | F1 | precision | recall | documents requested | unjustified | chain rate | grounded rate |
|---|---|---|---|---|---|---|---|
| b1_direct | 0.605 | 1.000 | 0.438 | 4.4 | 0.00 | 0.000 | 0.000 |
| b2_retrieval | 0.601 | 1.000 | 0.438 | 4.4 | 0.00 | 0.000 | 0.000 |
| b3_graph_then_list | **0.635** | 1.000 | 0.475 | 4.8 | 0.00 | 0.000 | 0.000 |
| b3t_summary_then_list | 0.601 | 1.000 | 0.438 | 4.4 | 0.00 | 0.000 | 0.000 |
| b6_prior_composition | 0.618 | 1.000 | 0.450 | 4.5 | 0.00 | 0.000 | 0.000 |
| b5_induced_graph | 0.488 | 0.925 | 0.337 | 3.8 | 0.38 | **0.400** | **0.300** |
| **modal-list oracle** | **1.000** | **1.000** | **1.000** | 10.0 | 0.00 | — | — |

There is one distinct reference checklist across these eight cases, so a predictor that ignores the case entirely
and emits the modal ten documents scores a perfect 1.000. **Five of the six arms** sit within 0.034 F1 of one
another (0.601–0.635); the sixth, `b5_induced_graph` at 0.488, sits 0.147 below the best and is the one arm that
is *not* within that band. **No comparative claim is drawn from this table**; reporting the 0.635 as the graph arm
winning would be reporting noise on a task whose correct answer is the same every time.

Two descriptions of the ablation arms in earlier drafts were wrong and are corrected here.
`b3t_summary_then_list` summarises the **authoritative sources**, not the graph — it never sees the graph, and it
controls for whether the gain is just more intermediate tokens. `b6_prior_composition` composes prior *methods*,
not prior cases: it runs retrieval over the authoritative passages and then an extraction step over them, so it
does use law, and it uses no prior cases at all.

Two facts the table does establish: every arm is precise and partial — precision 1.000 for five of six, asking for
about four of the ten documents the contract requires, because the reference set is a completion set rather than a
triage list — and only `b5_induced_graph` emits justification chains at all. The other arms score zero on chain
metrics by construction.

The same measurement on the clean case sets of both scopes:

| scope | cases | distinct reference checklists | mean reference set | contract documents | catalogue |
|---|---|---|---|---|---|
| rent increase | 30 | **1** | 10.0 | 11 | 16 |
| termination | 49 | **1** | 17.0 | 18 | 18 |

Termination has its own spine, its own gate pass, its own voted document layer, 21 decisions and a catalogue of
18, and is the more saturated of the two. We state its figure precisely: the contract requires **all 18** of its
documents in every case measured, and the *reference set* is 17 because `lease_contract` is treated as already
held and removed before scoring under the convention of §4.1. Both scopes fail C8, the observed-branch-closure
admission criterion added as amendment A1 after rent increase exposed the gap — and A1 was written before
termination existed, so the criterion is catching a second case rather than being fitted to one.

The modal-oracle F1 of 1.000 was measured on the **rent-increase development cases only**. No modal-oracle F1 was
ever computed on termination. **TODO[number not found: modal-oracle F1 on the termination scope].**

What this licenses is narrower than what we previously claimed. We have two reference contracts, built by the same
authoring procedure, scored against one generated corpus, in one domain and one legal system. That is consistent
with a shared property of the domain, and equally consistent with a shared property of the procedure or of the
corpus generator. We therefore claim that **a static document-checklist task over intake messages was
uninformative on both scopes we built**, and that anyone building such a benchmark should check for this
degeneracy before scoring on it. We do not claim that such a task is impossible in this domain; our own
saturation note says a third scope with a flatter document-to-decision mapping is needed before the point can be
generalised.

### 5.2 Confirmatory read on rent increase, with the volume control

One read, 28 pairs across the six held-out scenarios. The method was frozen at commit `c43bc22` and the
preregistration was written at `ee6f266`; earlier drafts attributed the preregistration to `c43bc22`, which is the
method freeze. Each pair is a case and the same case with a minimal factual addition establishing that the tenant
did not challenge within 30 days. Adjudicator unanimity 93%; 25 of 28 pairs carry a non-empty expected withdrawal;
the contract releases a mean of 4.7 documents (132 in total).

| arm | expected | correct | false | **withdrawal recall** | precision | retention | documents requested |
|---|---|---|---|---|---|---|---|
| b1_direct | 132 | 5 | 35 | 0.038 | 0.125 | 0.573 | 5.3 |
| b3_graph_then_list | 132 | 16 | 28 | 0.121 | 0.364 | 0.641 | 5.5 |
| b5_induced_graph | 132 | **78** | 52 | **0.591** | **0.600** | 0.544 | 10.0 |

| preregistered comparison | Δ recall | 95% CI | retention Δ | verdict |
|---|---|---|---|---|
| **primary (A3)** b3 − b1 | +0.083 | [+0.018, +0.151] | +0.068 | **SUPPORTED** |
| **secondary** (original primary, `ee6f266`) b5 − b1 | +0.553 | [+0.459, +0.613] | −0.029 | passes the same criteria |

These raw recalls are not comparable across arms. Each arm is therefore compared against **itself dropping the
same number of its own requested documents at random**:

| arm | recall | own random baseline | **excess over random** | 95% CI | reading |
|---|---|---|---|---|---|
| b1_direct | 0.038 | 0.099 | **−0.061** | [−0.096, −0.026] | **below chance** |
| b3_graph_then_list | 0.121 | 0.110 | +0.011 | [−0.017, +0.038] | no signal |
| b5_induced_graph | 0.591 | 0.473 | **+0.118** | **[+0.106, +0.126]** | **signal** |

The control changes what the first table means, in three ways.

**The headline shrinks by a factor of 4.7.** The uncontrolled comparison of `b5_induced_graph` against `b1_direct`
is +0.553 [+0.459, +0.613] — a number that passes the preregistered support criteria and that would, reported
alone, be the paper's result. Of `b5`'s 0.591 recall, 0.473 — four fifths of it — is reproduced by dropping the
same number of its own documents at random. What survives is a within-arm excess of +0.118 [+0.106, +0.126],
about a fifth of the raw figure. We note that +0.553 and +0.118 are not the same kind of quantity: the first is a
between-arm difference of raw recalls, the second a within-arm excess. The like-for-like controlled contrast would
be excess(b5) − excess(b1) = 0.118 − (−0.061) = +0.179, and no interval for it was computed (§4.5).

**One arm's sign changes.** `b1_direct`'s raw withdrawal recall is 0.038 — small but positive, reading as
occasionally correct. Against its own random baseline of 0.099 it is −0.061, with an interval lying entirely below
zero. On this arm, on this scope, under this reasoner, the documents direct prediction stops requesting are
anti-correlated with the documents the process released. That inversion is invisible in the raw number. We flag
immediately that this does **not** generalise: it holds on one reasoner of four (§5.3) and does not reproduce on
the second scope (§5.4), so it is a property of this pairing and not of direct prediction.

**The preregistered primary is supported, with a qualification.** The amended primary comparison, `b3` against
`b1`, is +0.083 [+0.018, +0.151] with a retention difference of +0.068, and the preregistered verdict is
SUPPORTED. Under the control, `b3`'s excess over its own random baseline is +0.011 with an interval spanning zero,
while `b1`'s lies entirely below zero. The natural reading is that `b3` beats `b1` because `b1` is below chance
rather than because `b3` is informative — but we state this as what the two intervals show, not as a tested
difference: the gap between the two excesses is 0.072 and no interval on that difference exists. The verdict
stands as recorded — it was fixed in advance and is not revised after the fact — with the qualification attached
permanently.

The effect is not carried by one scenario: `b5_induced_graph` has the highest recall on all six held-out scenarios
individually, ranging 0.481–0.630. Its cost is real: it has the **worst retention** of the three (0.544 against
0.573 and 0.641), satisfying the preregistered tolerance (−0.029, within −0.050) but dropping documents it should
have kept.

**The development result this was amended on no longer reproduces.** Amendment A3 moved the preregistered primary
from `b5` to `b3` on the strength of a development read recorded at the time as 12 pairs across 3 scenarios, 51
expected withdrawals, `b1` correct **zero** times in 51 while making 10 withdrawals, `b3` at 0.137 with a
bootstrap interval of [+0.038, +0.267] against `b1` that excluded zero, and `b5` at 0.039 with [+0.000, +0.133].
Re-running the committed development script against the data on disk today gives a different picture: **17 pairs
across 4 scenarios**, 77 expected withdrawals, `b1` correct **once** (recall 0.013) with 11 of its withdrawals
landing on documents the contract still required, `b3` at 0.117 and `b5` at 0.039. The deltas against `b1` are now
+0.104 [+0.000, +0.229] for `b3` and +0.026 [+0.000, +0.092] for `b5` — **both intervals include zero.** The
interval-excludes-zero finding that justified A3 does not reproduce. We report the figures as measured today and
mark the earlier ones as superseded.

| arm | development recall (as re-measured) | confirmatory recall | documents requested, dev → conf |
|---|---|---|---|
| b1_direct | 0.013 | 0.038 | 4.4 → 5.3 |
| b3_graph_then_list | 0.117 | 0.121 | 4.2 → 5.5 |
| b5_induced_graph | 0.039 | **0.591** | 4.3 → **10.0** |

The mechanism of the reversal is in the last column: the compiler requests 4.3 documents on development and 10.0
on the confirmatory scenarios. Our earlier explanation for this — that *all four* development scenarios are
form-defect disputes, which activate graph nodes carrying no evidentiary obligation — is wrong as stated. **Two**
of the four are form-defect disputes (`S1_form_defective`, `S2_form_no_reason`); `S3_retroactive_start` is a
receipt-and-timing dispute and `S10_grant_allocation` is a dispute about allocating a renovation grant. The
confirmatory scenarios are substantive rent-calculation disputes (miscalculation, reference rate inconsistent,
reference rate double-counted, renovation, ancillary-charge reclassification, provisional budget), which activate
the nodes that do carry obligations. The direction of the explanation survives; its strength does not, and with it
goes part of our account of why A3 was a mistake.

A3 was declared before the held-out data was read and did not delete the comparison it demoted, so the original
primary survives in the record and is reported above — which is the reason to preregister. The amendment was
nonetheless a mistake, and it was a mistake because development data can be unrepresentative of a scope in a way
that splitting on scenarios does not prevent.

### 5.3 The same frozen artifact gives opposite answers under different reasoners

The result in §5.2 is a property of a pairing, not of the artifact. Holding the induced process graph, the
reference contract, the case corpus and the code fixed on the same 28 held-out pairs, and changing **only the
model that interprets a case against them and compiles it**:

| model | arm | recall | own random baseline | **excess** | 95% CI | |
|---|---|---|---|---|---|---|
| gpt-5.6-terra | b1_direct | 0.038 | 0.099 | **−0.061** | [−0.096, −0.026] | **below chance** |
| | b5_induced_graph | 0.591 | 0.472 | **+0.119** | [+0.108, +0.125] | **signal** |
| claude-haiku-4.5 | b1_direct | 0.038 | 0.035 | +0.003 | [−0.011, +0.016] | none |
| | b5_induced_graph | 0.000 | 0.077 | **−0.077** | [−0.092, −0.070] | **below chance** |
| gemini-2.5-flash | b1_direct | 0.038 | 0.037 | +0.001 | [−0.010, +0.012] | none |
| | b5_induced_graph | 0.189 | 0.080 | **+0.109** | [+0.107, +0.112] | **signal** |
| deepseek-v3.2 | b1_direct | 0.045 | 0.035 | +0.010 | [−0.026, +0.041] | none |
| | b5_induced_graph | 0.000 | 0.034 | **−0.034** | [−0.037, −0.031] | **below chance** |

All four conditions ran on all 28 pairs.[^rng]

The spread on one identical artifact is **+0.119 to −0.077**. We state the interval claim precisely: the two
positive intervals lie entirely above zero and the two negative intervals entirely below it, so the signal and
below-chance groups are separated; the extreme pair (`gpt-5.6-terra` and `claude-haiku-4.5`) does not overlap. The
two positive intervals do overlap each other over nearly their whole width, so the four models do not form four
distinguishable levels.

**Scope of the sentence we are careful about.** What changed between conditions is the model that performs the
case-dependent steps **and the compilation**. The compiler is a model step. The corpus, the propositions, the
induced graph, the reference contract, the catalogue, the case set and the pipeline code are what were held fixed.
Our earlier phrasing — that all artifacts produced by model steps were held fixed — was wrong, and the diagnostic
table below proves it: the per-model chain counts differ, which could not happen if the compiled artifact were
frozen.

Neither headline effect from §5.2 is a property of the method. `b1_direct` is below chance on **one model of
four**: on the other three its interval spans zero, uninformative rather than actively wrong. Its raw withdrawal
recall is identical to three decimals (0.038) on three of the four models; what differs is each model's own chance
level, set by how much that model drops — `gpt-5.6-terra`'s direct arm has a random baseline of 0.099 against
0.035 and 0.037 for the others. `b5_induced_graph` carries signal on **two of four** and is below chance on the
other two: the same artifact, driving the same code, withdraws the wrong documents.

This is not a failure of the runs:

| model | mean documents requested | mean chains | predicate verdicts (true / false / unresolved) | resolved |
|---|---|---|---|---|
| gpt-5.6-terra | 7.4 | 34.0 | 27 / 28 / 467 | 10.5% |
| claude-haiku-4.5 | 12.6 | 67.6 | 32 / 28 / 462 | 11.5% |
| gemini-2.5-flash | 6.5 | 31.0 | 32 / 29 / 461 | 11.7% |
| deepseek-v3.2 | 6.5 | 39.0 | 30 / 29 / 463 | 11.3% |

Means are over all 58 case runs per model, originals and intervened variants together; the request counts in the
result table above are over the 28 originals only. Every model was asked the same 9 predicates on each of the 58
runs (522 verdicts per model), and every model resolved 10–12% of them.

**On execution errors.** We previously reported "zero execution errors in all four conditions". We weaken that
claim to what the artifacts support. The arm records contain no error field — the runner catches exceptions and
continues without writing an error record — so a silently dropped unit is not distinguishable from one that never
existed. What is verifiable is that every one of the four conditions produced a complete set of 58 case runs with
58 populated `b5` arm records, and that the run logs for three of the four conditions contain no failure lines.
There is no run log for the `gpt-5.6-terra` condition. **TODO[verify: per-unit error recording in the multi-model
runner; no run log exists for the gpt-5.6-terra condition].**

**On what was held identical.** The claims that the prompts were character-identical and the temperature fixed
across the four conditions are **not verifiable from anything on disk**: no prompt text or temperature is recorded
in any run record, and the runner scripts for the three non-`gpt` conditions are not in the repository. Only the
`gpt-5.6-terra` runner, itself uncommitted, pins `temperature=0.0`. We therefore assert that the four conditions
shared prompts and decoding settings on the basis of how they were run, and we mark it as unevidenced rather than
presenting it as checkable. **TODO[verify: commit the multi-model runner and record prompt identity and
temperature in each run artifact].**

`claude-haiku-4.5` compiles about twice as many chains as the two signal models (67.6 against 31.0 and 34.0, and
1.7× deepseek's 39.0) and requests about 1.7× as many documents (12.6 against 6.5–7.4; over the 28 originals,
13.07 against `gpt-5.6-terra`'s 10.0, a factor of 1.31), and still withdraws nothing correct. As noted in §1.1,
chain count is the one recorded proxy that orders the four models consistently with the sign of their result.

Stated carefully: a source-grounded process representation **does not by itself confer correct retraction
behaviour**. The representation is frozen and identical; the outcome depends on the reasoner that interprets a
case against it. The finding is not that the method fails — on two of four reasoners it produces the only
informative withdrawal behaviour observed anywhere in this work — but that **which reasoner it is paired with
decides the sign of the result**, and that a single-model experiment cannot see this. The confirmatory result of
§5.2 therefore stands as reported *for `gpt-5.6-terra` on rent increase*, and must be stated with that scope.

[^rng]: The `gpt-5.6-terra` rows differ from §5.2 in the third decimal (+0.119 against +0.118; baseline 0.472
against 0.473) because the two scripts draw the random-drop baseline from the shared stream in a different order.
Both figures reproduce; the difference is simulation noise of order 0.001. The `b1` rows, drawn first in both, are
identical.

### 5.4 Transfer to termination fails, and the failure was computable in advance

One read, 49 pairs across 8 scenarios, under a separate preregistration and its amendment T1 (a power decision
taken before any arm outcome existed). Adjudicator unanimity is 66%, materially lower than the 93% on rent
increase. The volume control is the primary outcome here, not an afterthought.

| arm | expected | correct | false | recall | own random baseline | **excess** | 95% CI | retention | requested |
|---|---|---|---|---|---|---|---|---|---|
| b1_direct | 77 | 5 | 80 | 0.065 | 0.050 | +0.015 | [−0.011, +0.051] | 0.723 | 6.4 |
| b3_graph_then_list | 77 | 6 | 70 | 0.078 | 0.059 | +0.019 | [−0.008, +0.057] | 0.756 | 6.3 |
| b5_induced_graph | 77 | **0** | 6 | 0.000 | 0.012 | **−0.012** | [−0.024, +0.000] | 0.992 | 16.0 |

**Preregistered verdict: NOT SUPPORTED.** No arm's interval excludes zero. The rent-increase finding that
`b1_direct` is below chance does not reproduce here: its interval spans zero, consistent with §5.3, where that
effect held on one reasoner of four.

The ceiling was computed from the contract alone and recorded in the preregistration before the run: settling
`DEC-09` releases 3 documents (`bank_statement`, `payment_deadline_warning_letter`, `rent_payment_records`) and no
other single decision releases more than 1, against 6 for the rent-increase probe. Measured, the contract released
a mean of **1.57** documents per pair, non-empty on 22 of 49. The matching graph predicate `e05` closes 4 nodes
carrying 1 obligation between them. Against that, `b5_induced_graph` requests **16.0 of the 18** catalogue
documents and retains **0.992** of what it should keep: it withdrew 6 documents in total across 49 pairs, none of
them correct. The arm behaved consistently with its design, and the design had no room to act — a process-derived
checklist can only retract where the process attaches obligations to the branch that closes.

Termination was not a weak attempt: same procedures, its own gated contract, its own voted catalogue-restricted
document layer, its own induced graph (12 nodes, 11 transitions), and a probe chosen structurally in advance. Two
readings remain, and this evidence does not separate them: either the method works where the process attaches
evidentiary obligations densely to branches that real facts close, or the rent-increase result is scope-specific
in a way not yet understood. The first reading suggests a scope-selection criterion computable in advance from the
contract alone, and the ceiling computation above is **one successful prediction on one scope** — a hypothesis
worth testing, not a validated criterion. We previously wrote that the ceiling computation "demonstrates" such a
criterion; from a single prediction it does not.

### 5.5 What the verification gate caught

Of 58 quotes proposed for the rent-increase reference contract, 44 verified verbatim against the Fedlex passage
each was attributed to, and 14 were dropped. Thirteen of the fourteen cited sources outside the fetched corpus —
cantonal court leaflets and guides, correctly sourced but not in the statute bundle. The fourteenth is a
fabrication that reading cannot catch: the spine cited `vmwg-art-19a-20251001-de`.

- Fedlex serves **no VMWG consolidation dated 2025-10-01**. Ten citations carried that date; re-resolved against
  the real consolidation, nine recovered — the article text was right and only the date was invented.
- **VMWG has no Art. 19a at any consolidation.** The tenth had nothing behind it. Its quote is fluent, correctly
  styled Swiss regulatory German, and sourceless, and is indistinguishable by reading from the 44 that verified.

This is the case for fetching and checking rather than reading carefully: a wrong date is recoverable and a
careful reader would likely catch it, while a fabricated article carrying a plausible quote looks exactly like the
ones that verify.

**A retracted measurement.** Running the same gate across four scope contracts produced quote-match rates of
59.6% (68 of 114), 50.6% (43 of 85), 35.5% (11 of 31) and 25.6% (11 of 43). We nearly reported these as evidence
of widespread fabrication; read that way they would have implied fabrication at 40–74%. They are **verification
rates**, and they are an artifact of artifact design rather than a property of models: those four contracts store
`authorities` and `quotes` as parallel lists with no mapping between them, so every quote is tested against every
statutory citation of its decision, and a quote correctly taken from a cantonal court leaflet cannot appear in a
statute. Inspecting the failures confirmed this as the dominant mode. We retract the cross-scope rate. The lesson
is that a legal artifact listing sources and quotes separately cannot be verified at all, by any checker; pairing
them costs nothing at authoring time. The gated contracts store `{authority_id, quote}` pairs, which is why their
gate is constitutive and their reported rate means something.

---

## 6 Limitations and Threats to Validity

### 6.1 The corpus is synthetic

Every case in this work comes from a generated 150-claim intake corpus, in German and English twins of the same
fact patterns, built from a hand-authored static rule template. No real claim was used. This bounds every number
in §5, and it bounds the saturation finding in particular: a generated intake corpus may express less variation
than real intake, and one plausible reading of §5.1 is that we measured the generator rather than the domain.

### 6.2 Ground truth is model-adjudicated

No lawyer reviewed any artifact in this work. The reference contracts' decisions were authored by an agent reading
the sources; the document layer came from three further authors voting two-of-three within a fixed catalogue; the
per-case live/dead/unknown marks came from three adjudicators reading the narrative. Adjudicator unanimity was 93%
on the rent-increase confirmatory read, 88% on the development originals, and **66%** on the termination transfer
— the last low enough that the transfer null should be read with the ground truth's own reliability in mind.

### 6.3 Scope of the evidence: one domain, two scopes, four reasoners

Every result comes from Swiss tenancy law. Two scopes were built and run end to end. Two further reference
contracts exist for insurance scopes (theft, legal expenses) and neither has been run through the pipeline.
Nothing here speaks to a second legal system, a second language regime, a common-law jurisdiction, or a domain
outside procedural law.

Within tenancy, the positive result rests on one scope of the two, and on two reasoners of four. Four points do
not characterise a population of reasoners, and we have no advance predictor of which side of the sign change a
given model falls on. Chain count orders the four models consistently with the sign of their result (§1.1), which
with n=4 has a 1-in-6 chance of arising at random and is a hypothesis rather than a finding.

### 6.4 Scale, and the unit of independence

The rent-increase corpus is 50 cases in 10 scenarios of exactly 5, split 4 scenarios (20 cases) to development and
6 scenarios (30 cases) to the held-out set. Cases within a scenario are variations on one fact pattern, so all
intervals bootstrap over **scenarios**, which leaves the effective sample at 6 for the confirmatory read, 8 for
transfer and 4 for development. Nothing in this paper is a large-sample result, and the tightness of the
controlled intervals reflects the stability of the random-drop comparison within pairs, not a large number of
independent units.

The paired design also assumes the intervention is minimal — that the added sentence settles the target predicate
and changes nothing else. Interventions were authored to that standard, but no independent check confirms that a
variant differs from its original in exactly one respect.

### 6.5 The volume control is unplanned and per-arm

It was added after the single held-out read (§4.5). It is disclosed as an unplanned analysis. It yields a per-arm
statistic only; no interval on the difference between two arms' excesses exists, so every cross-arm reading in
§5.2 is a comparison of what two intervals show rather than a test.

### 6.6 Reproducibility gaps

The per-case run records, reference adjudications and graph/proposition bundles that all four analysis scripts
read are not committed to the repository, contrary to our own reproducibility note (§5). The multi-model runner is
not committed either, and no prompt text or temperature is recorded in any run artifact, so "only the model
changed" is asserted from how the runs were performed rather than evidenced by them. Three committed documents
state "8 of 13 nodes emitted no obligation" where the graph artifact gives 9 of 13; the artifact is correct.

### 6.7 Known defects in the system, unrepaired

The induced graph has no applicability gate (§3.8), so an out-of-scope case inherits the full modal document list
— the same mechanism that made a contaminated case bucket look like saturation (§4.4). Obligation coverage is
sparse: 6 obligations across 4 of 13 nodes. A re-induced graph addressing the latter exists but was excluded from
the held-out read and is unevaluated.

### 6.8 Research practice, including what went wrong

Two preregistration amendments and three errors are part of the record.

**Amendment A1** changed the probe from `e03` to `e07` on a ceiling computed from the contract alone, before any
result existed. It corrected an error in our own preregistration: `e03` could release nothing, so the planned
comparison would have measured zero against zero.

**Amendment A3** changed the primary comparison from `b5 − b1` to `b3 − b1` after seeing development data. It was
declared as such, and it did not delete the comparison it demoted, which is why the original primary survives in
the record and is reported in §5.2. A3 was a mistake twice over: it moved the primary away from the arm that
turned out to be the only informative one, and the development finding it rested on no longer reproduces — the
interval that excluded zero now includes it (§5.2).

**Error 1.** We computed that the primary outcome was structurally impossible and committed a document acting on
it. The computation pooled each node's document supply across cases when the compiler recomputes it per case. The
data refuted it.

**Error 2.** We nearly reported cross-scope citation verification rates as fabrication rates (§5.5), and retracted
them once the parallel-list artifact was identified.

**Error 3.** We described all four development scenarios as form-defect disputes, and built our account of why A3
was a mistake on that description. Two of the four are form-defect disputes; the other two are a
receipt-and-timing dispute and a grant-allocation dispute (§5.2).

We also withdraw, in this paper, a 15-case saturation measurement computed on a keyword-built bucket that an audit
showed to be one-third out of scope (§4.4), and a claim that the verbatim gate's guarantee propagates to the
graph, the compiler and the product's justification prose, which the code does not support (§3.3).

---

## 7 Conclusion

**What this work establishes.**

A frozen, source-grounded process representation does not by itself confer correct retraction behaviour. Holding
the induced graph, the reference contract, the corpus and the code fixed, and changing only the model that
interprets a case against them and compiles it, the identical artifact scores +0.119 [+0.108, +0.125] excess
withdrawal recall on one reasoner and −0.077 [−0.092, −0.070] on another, with two of four reasoners carrying
signal and two below chance. A single-model experiment on a method of this kind measures the pairing of method and
model and attributes it to the method; ours did, until we ran the check.

Retraction metrics require a per-arm volume control. Without one, the pipeline's advantage over direct prediction
reads +0.553 rather than a within-arm excess of +0.118, a 4.7-fold difference, and one arm's reading inverts from
weakly positive to below chance.

A static document-checklist task over intake messages was uninformative on both scopes we built: one distinct
ground-truth checklist across 30 and across 49 cases, a case-ignoring modal predictor at F1 1.000 on the
rent-increase development cases, and five of six baselines within 0.034 F1.

A constitutive verbatim gate — one that discards at authoring time rather than scoring later — caught a fabricated
statutory article that is indistinguishable by reading from the citations that verified. Artifacts that store
sources and quotes as unmapped parallel lists cannot be verified at all.

Transfer to a second scope produced no arm with signal, and the ceiling that explains it was computed from the
contract before the run.

**What this work does not establish.**

It does not demonstrate a general method. The positive effect holds on one scope of two and two reasoners of four,
and we have no test that predicts the boundary short of running it. The ceiling computation correctly predicted
one transfer failure; that is one successful prediction on one scope, not a validated scope-selection criterion.

It does not establish a property of the domain. Two reference contracts built by the same procedure, scored
against one generated corpus, in one legal system, cannot distinguish a property of the domain from a property of
the procedure or of the corpus generator.

It does not establish that the corpus resembles real practice. Every case is synthetic.

It does not establish what governs the sign reversal. Chain count orders the four reasoners consistently with
their results; with four models that is a hypothesis, not an explanation.

It does not establish that the representation matters less than the reasoner. The representation was never varied.
What the design supports is a representation × interpreter interaction large enough to reverse a conclusion — not
a ranking of the two factors.

The practical recommendation is narrow and, we think, well supported by the measurements above: a paper proposing
a structured or source-grounded representation should report at least two interpreting models before attributing
any result to the representation, and should report a volume control before attributing any retraction result to
anything at all.

---

## Open TODOs in this draft

- ~~TODO[citation] §2 Related Work~~ — RESOLVED: written from an adversarial sweep of 24 agents; 13 opened-and-read citations. Coverage limits disclosed in §2. The uncited premise that single-model evaluation is *the norm* has been removed from the framing rather than left unsupported.
  norm in this literature is uncited and unsupported by any artifact in this repository.
- **TODO[citation: Fedlex filestore]** — §3.1.
- **TODO[number not found: per-reason drop counts for the 170-proposition extraction]** — §3.2.
- **TODO[number not found: modal-oracle F1 on the termination scope]** — §5.1.
- **TODO[number not found: bootstrap interval on excess(b5) − excess(b1) and excess(b3) − excess(b1)]** — §4.5,
  §5.2.
- **TODO[verify: reading discipline for the rent-increase contract author against the proposition set]** — §4.1.
- **TODO[verify: termination contract's `scope_statement` (135 of 135 quotes) contradicts its audit block (91 of
  106)]** — §4.1.
- **TODO[verify: commit the per-case run records, reference adjudications and graph/proposition bundles, or
  restate the reproducibility claim]** — §5.
- **TODO[verify: commit the multi-model runner; record prompt text and temperature in each run artifact]** — §5.3.
- **TODO[verify: per-unit error recording in the runner; no run log exists for the gpt-5.6-terra condition]** —
  §5.3.
