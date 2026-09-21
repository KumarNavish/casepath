> **HISTORICAL RESEARCH RECORD — not the submission claim.** This file documents the earlier
> process-induction line, whose positive claims were **withdrawn** after a constant-oracle and
> wrong-pairing audit; see `PAIRED_DESIGN_DEGENERACY.md` for what failed and why. The submitted
> ICLR 2027 paper is `research/casepath/iclr2027-integrated/`, and its Study A benchmark reproduces
> offline from `research/casepath/branch-benchmark/`. `research/casepath/iclr2027/` is a separate,
> unsubmitted paper from this same historical line. Numbers in this file must not be quoted as
> current results.

# A Case-Ignoring Constant Beats Every Arm: Degeneracy Survives the Move from Static Checklists to Paired Retraction

## Abstract

A structured, source-grounded representation is usually evaluated by pairing it with one language model and
reporting the resulting number as a property of the representation. We build such a system — it fetches Swiss
federal tenancy law, extracts propositions under a verbatim-substring gate, induces a process graph, and
deterministically compiles the obligations of still-active nodes into a document checklist that retracts a document
when every node requiring it closes — and we report two things about how it measures, both negative.

First, a static document-checklist task over our intake corpora is degenerate: two independently built legal scopes
each yield **exactly one** distinct ground-truth checklist across the cases measured, so a case-ignoring modal
predictor scores F1 1.000. We built a paired branch-intervention design to escape that, on the stated reasoning
that "a paired difference is unaffected by the constant level that saturates the static task." **That reasoning is
wrong and our own data refute it.** The release set inherits the constancy: across 28 held-out pairs the
pre-intervention reference set takes **one** distinct value and the release set takes **three**, with a single
5-document core accounting for 125 of 132 expected withdrawals. A policy that ignores the case entirely — request
the modal ten, always withdraw the same five — scores excess withdrawal recall **+0.447 [+0.429, +0.476]**, **3.8×
the best arm we measured**. A permutation null that shuffles which case's release set attaches to which arm
behaviour confirms the mechanism: the winning arm's statistic sits inside that null (p = 0.21) and the
second-placed arm's is *exactly invariant* to it. The dynamic task is degenerate in the same way as the static one.

Second, and true regardless: holding the induced graph, the reference contract, the corpus and the code fixed and
changing **only** the interpreting model, the identical artifact scores **+0.118** excess withdrawal recall on one
reasoner and **−0.078** on another. Whatever that statistic measures, it is not a function of the representation
alone, which is sufficient to refute the inference a single-model evaluation makes. What the four reasoners
actually differ in is narrow and we now state it as such: each emits a near-constant request set (1, 1, 1 and 2
distinct sets across 28 pairs) and drops a fixed block; two of those blocks intersect the near-constant release set
and two do not. We withdraw the word "anti-correlated" — the two negative arms have withdrawal recall identically
**0.000**, so their intervals cannot include zero by construction.

We also report a volume control, in exact closed form rather than by simulation, without which the headline reads
+0.553 rather than +0.118; a transfer failure to a second scope whose ceiling was computed from the contract before
the run; and a constitutive verbatim gate that caught a fabricated statutory article. We do not demonstrate a
general method, and we no longer claim to have measured correct retraction behaviour. The recommendation we do
stand behind is a diagnostic: before reporting any retraction metric, run the case-ignoring oracle and the
permutation null we describe here.

---

## 1 Introduction

We built a benchmark twice, and it was degenerate both times. The second time we did not notice until we ran the
oracle, which is the reason this paper is worth reading.

**The first time.** The obvious task for a document-checklist system is the static one: given a case, predict the
documents it needs. On both legal scopes we built, the ground truth takes exactly one value — one distinct
reference checklist across 30 rent-increase cases and across 49 termination cases — so a predictor that ignores the
case and emits the modal list scores F1 1.000 and every real arm loses to it (§5.1). We reported that, correctly,
as a reason not to score anything on the static task.

**The second time.** We therefore designed a paired task that scores *change* rather than level. Each unit is a
case and the same case plus a minimal factual addition that settles one branch predicate; an independently built
reference contract says which documents that addition releases; the question is whether the arm stops requesting
them. We wrote, in the design section, that "a paired difference is unaffected by the constant level that saturates
the static task." **That sentence is false, and the artifacts we committed refute it.** The degeneracy propagates
through the release set. Across the 28 held-out pairs the pre-intervention reference set takes **one** distinct
value, and the release set $E$ takes **three** — the same five documents on 18 pairs, those five plus one on 7, and
empty on 3 — so a single 5-document core supplies 125 of the 132 expected withdrawals (94.7%).

We did not compute the analogue of the modal-list oracle on the dynamic task before submission. It is the obvious
check and we should have. Running it now, under our own volume control: a policy that reads no case at all —
request the modal ten, always withdraw the same five — scores excess withdrawal recall **+0.447 [+0.429, +0.476]**,
against **+0.118** for the best arm we measured. A case-ignoring constant beats our system by a factor of 3.8 on a
task we presented as measuring case-sensitive retraction (§5.1).

A permutation null says the same thing mechanically. Shuffle which pair's release set is attached to which pair's
arm behaviour, holding each arm fixed, and the statistic barely moves: the winning arm's observed +0.118 sits
inside its own permutation null (mean +0.115, p = 0.21), and the second-placed arm's +0.108 is *exactly invariant*
to the shuffle — permutation range [+0.108, +0.108], zero case-specific information. What the metric rewards is the
alignment between a near-constant withdrawal habit and a near-constant release set.

**What survives, and it is not nothing.** The reasoner-dependence result does not depend on the metric measuring
retraction. We ran the same experiment four times with the graph, the contract, the corpus and the code frozen and
byte-identical, changing only the interpreting model. On `gpt-5.6-terra` the artifact scored **+0.118** excess
withdrawal recall; on `claude-haiku-4.5`, **−0.078**; on `gemini-2.5-flash` **+0.108** and on `deepseek-v3.2`
**−0.036**, all on the same 28 pairs. Whatever the number is measuring, it is not a function of the representation
alone — which is exactly the inference a single-model evaluation of a "grounded" method makes, and one
counterexample refutes it. We now state that as an existence proof rather than as a survey of reasoners.

**What we withdraw.** We previously described the two negative arms as withdrawing documents "anti-correlated"
with the released ones. They do not. Both have withdrawal recall of exactly **0.000**, which makes their excess
equal to minus their own baseline by algebraic identity and their intervals one-sided by construction. And all
four `b5` arms are near-constant functions of the case — 1, 2, 1 and 1 distinct pre-intervention request sets
across 28 pairs respectively. `gemini-2.5-flash`'s entire "+0.108 signal" is one document,
`property_management_statement`, dropped on 28 of 28 pairs; `claude-haiku-4.5`'s and `deepseek-v3.2`'s entire
"below chance" result is one document, `conciliation_request`, dropped on 28 of 28 pairs, which appears in no
decision of the contract and therefore can never be correct. The four-way split is four constants, and which side
of zero each lands on is decided once per model, not 28 times (§5.3).

The runs themselves did not break. Every model was asked the same nine branch predicates on each of 58 case runs,
and every model resolved 10–12% of them (10.5%, 11.5%, 11.7%, 11.3%). The pipeline executed the same way each
time. What differed was which fixed block of documents each reasoner asked for and let go.

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

**We state it as an existence proof, and we state its effective sample size honestly.** One counterexample is
logically sufficient to refute "a single-model number identifies a property of the representation," and we have a
clean one. But it is *one* counterexample, not a four-point survey of a population of reasoners, and the reason is
in the data rather than in the model count: each `b5` arm emits a near-constant request set and a near-constant
withdrawal, so the effective number of independent model decisions behind each cell is approximately **one**, not
28 pairs and not 6 scenarios (§5.3). The two negative models are not two independent replications of a phenomenon
— they withdraw the *identical single document type* on every pair, and their excesses differ (−0.036 against
−0.078) only because their request-set sizes differ, which changes the denominator of their own baselines. So
"two of four are actively wrong" is, at the level of behaviour, one behaviour counted twice, and we no longer
phrase it as a rate over reasoners.

Two of the usual defences against this reading do not apply, and one does not survive inspection.

It is not decoding noise: the spread far exceeds the bootstrap intervals, which resample over scenarios rather
than cases. It is not an artifact of a fragile representation: the representation is exactly the thing held
constant. It is **not**, however, a demonstration that the four models differ in *retraction* behaviour, because
the statistic they differ on is one a case-ignoring constant wins outright (§5.1). The defensible reading is that
they differ in which fixed block of documents the frozen artifact leads each of them to drop.

It is **not** true, however, that none of the observable proxies for engagement with the graph tracks the split.
We recorded three: mean documents requested, mean chains compiled, and predicate-resolution rate. Request volume
does not separate the groups (above zero: 6.52, 7.41; below zero: 6.50, 12.55) and neither does resolution rate
(above zero: 10.5%, 11.7%; below zero: 11.3%, 11.5%). **Chain count does separate them perfectly**: the two
reasoners scoring above zero compiled 31.0 and 34.0 chains per run, and the two scoring below zero compiled 39.0
and 67.6. With four models, a chance separation in that direction has probability 1/6 — but we examined **three**
proxies, so the probability that at least one of the three separates perfectly in the specified direction is
$1-(5/6)^3 \approx 0.42$, and that is the number this observation should be read against. It is a pattern worth
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

- **Degeneracy survives the move from a static task to a paired one — with the oracle and the permutation null
  that detect it.** Two independently gated scopes — rent increase (30 cases, 12 decisions, mean reference set
  10.0) and termination (49 cases, 21 decisions, mean 17.0) — each yield **exactly one distinct ground-truth
  checklist across the cases measured**, so a case-ignoring modal predictor scores **F1 1.000** on the
  rent-increase development cases and all six real arms lose to not looking (§5.1). We built a paired
  branch-intervention design to escape this and it did not: the release set takes **3 distinct values across 28
  pairs**, one 5-document core covers **125 of 132** expected withdrawals, a **case-ignoring modal-withdraw
  oracle scores +0.447 [+0.429, +0.476]** against the best arm's +0.118, and a permutation null over release sets
  leaves the two positive arms' statistics at p = 0.21 and *exactly invariant* respectively (§5.1). We report
  both diagnostics as the contribution, because both are cheap, neither requires new model calls, and we needed
  them ourselves.
- **Reasoner-dependence of a frozen artifact, as an existence proof.** One frozen artifact, four reasoners, the
  same 28 held-out pairs: excess withdrawal recall spans **+0.118 [+0.107, +0.125] to −0.078 [−0.091, −0.071]**,
  with near-identical predicate-resolution rates in every condition. Whatever that statistic measures, it is not a
  function of the representation alone. We bound the claim: each arm is a near-constant function of the case (1,
  2, 1, 1 distinct request sets over 28 pairs), so the effective number of independent model decisions per cell is
  about one; and a paired bootstrap on the same resample indices shows the two positive models are **not**
  separable from each other (+0.010 [−0.001, +0.018], includes zero) (§5.3).
- **A volume control is required, it is worth 4.7×, and it has an exact closed form.** Arms that request more
  documents have more to drop, so raw withdrawal recall is not comparable across them. Scoring each arm against
  **itself dropping the same number of its own requested documents at random** takes the pipeline's raw advantage
  over direct prediction from **+0.553 [+0.459, +0.613]** to a within-arm excess of **+0.118 [+0.107, +0.125]**,
  and flips direct prediction from a weakly positive raw recall of 0.038 to **−0.060 [−0.094, −0.024]**. We
  previously estimated the baseline by a 300-draw simulation; it is the mean of a hypergeometric,
  $\mathbb{E}|W_{\text{rand}} \cap E| = |W|\,|B \cap E| / |B|$, and we now compute it exactly. The simulation error
  ran to roughly half the reported interval half-width, so part of a published interval was a simulation artifact
  (§4.5).
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

**It does not claim to have measured correct retraction behaviour.** This is the largest thing we withdraw. The
dynamic task we built to measure retraction is won by a policy that never reads the case, by a factor of 3.8, and
its statistic is near-invariant to permuting which case's release set is scored against which arm's behaviour
(§5.1). Every number in §5.2–§5.4 should be read as describing *which fixed block of documents an arm drops*, and
whether that block happens to intersect a near-constant release set — not as evidence that any arm computed what
this case released. The `b5` arm's behaviour may well be case-sensitive in some respect this corpus cannot
exercise; nothing here shows that it is.

It does not demonstrate a general method. It makes no static-checklist claim, because the task cannot separate
methods on the corpora we built. It does not claim the induced graph is unique:
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
and **we found no precedent for it in the LLM literature our sweep covered**. That qualifier is doing real work and
we state it rather than hiding it, for the reason in the next paragraph.

**Goal-directed statutory interviewing, which our sweep missed.** Our sweep searched LLM-era arXiv and no
ICAIL/JURIX venue, and the retraction mechanism we describe is decades older than that literature. Sergot et al.'s
British Nationality Act logic program (CACM 1986) generates exactly the questions its unresolved goals require and
prunes them as facts settle — that *is* retraction of a requirement set, deterministic, in 1986. van Engers' POWER
programme compiled Dutch tax legislation into executable models driving required-evidence forms; commercial rule
engines in the DMN line we do cite retract required inputs when a branch closes; Breaux & Antón's semantic
parameterization of HIPAA and LegalRuleML derive obligations together with their evidentiary parameters from
statute. We therefore restate the claim: what we did not find elsewhere is **inducing** the process from primary
sources under a verbatim gate and then measuring release against an independently authored contract — not the idea
that a checklist should retract when a branch closes, which is established. This is consistent with what we say
elsewhere: the contribution is the measurement, not the method. The fact that two of our own sweeps returned
roughly 50% disjoint hit sets is exactly the blind spot this paragraph corrects.

**Belief revision and update consistency.** Wilie et al. (2024, *Belief Revision: The Adaptability of Large
Language Models Reasoning*, EMNLP 2024, arXiv:2406.19764) introduce Belief-R and ΔR, measuring whether models
revise answers when new premises arrive. Our measurement differs in object: we score retraction of a
*requirement set* against a reference contract built independently from primary sources, and we report a
three-rung ladder with a null middle rather than a single revision score.

**Random baselines for set-valued output.** De Vries, Geva & Trotman (2012, *Divergence from a Random Baseline*,
arXiv:1208.5654), with Hubert & Arabie (1985) and Vinh et al. (2010), establish correcting clustering measures
against chance. Every such construction randomizes over a *fixed external universe* while copying the system's size
structure. Our null instead draws from **the system's own request set**. We previously presented this as a
structurally new kind of null; it is not, and we demote it. Conditioning a set-overlap statistic on the observed
margins is precisely the construction behind the adjusted Rand index we cite (Hubert & Arabie 1985) and behind
margin-conditioned permutation tests; choosing the system's own request set as the conditioning pool is a *choice
of conditioning set*, not a new null. It has an exact closed form (§4.5) and is a two-line analysis convention. We
report it because it changes our own headline by 4.7×, not because it is novel.

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

**The adjudicator is a model, it is named here, and it is the same model as the winning reasoner.** Steps 4 and 5
are performed by `openai/gpt-5.6-terra` at `temperature=0.0` (`runners/conf_ref.py:29`, `runners/term_ref.py:29`).
The "three adjudicators" are three calls to that one model on the same prompt, differing only by the literal
string `(adjudicator k)` appended to the user message. `gpt-5.6-terra` is simultaneously the reasoner in the
condition that produces our highest score (§5.3). No previous draft of this paper named the model, and a reader
could not see that the top condition is graded against labels its own model wrote at temperature 0. **We name it
as an unresolved confound on the central comparison**: "the interpreting model decides the sign" is not
distinguishable, on this design, from "the model that wrote the labels agrees with itself."

Two consequences follow and we state both. First, every "adjudicator unanimity" figure in this paper — 93% on the
confirmatory read, 88% on development, 66% on transfer — is **not** an inter-rater reliability statistic. It is
self-consistency across three temperature-0 samples of one model on a near-identical prompt, which makes 93%
closer to a determinism check than to an agreement measure, and makes the 66% on termination a statement that the
model contradicted itself on a third of decisions. We relabel them accordingly throughout.

Second, one piece of evidence bounds the confound and we report it because it cuts against our own result: the
termination arms were **also** run on `gpt-5.6-terra` against `gpt-5.6-terra` ground truth
(`runners/term_arms.py:18`) and still produced an excess of −0.012 with an interval spanning zero (§5.4). Grading
affinity is therefore not *sufficient* to produce a positive result. It remains uncontrolled, and removing it
requires re-adjudication under a different model, which we did not run.

**The adjudicator reads a truncated narrative.** The prompt is built from `t["text"][:9200]`
(`runners/conf_ref.py:20`). Three of the 28 confirmatory pairs — `clm_0c7beda7583b3558`, `clm_1f1dffaac057e7e4`
and `clm_6ecae3f11685e3b2`, all `S8_nebenkosten_reclass` — carry narratives of 166,696 to 168,235 characters, and
the intervention sentence is appended at the end, far beyond the cut. For those three the adjudicator read
**byte-identical text** for original and variant and left all twelve decisions open, which is why their release
set is empty. Those three are the entire gap behind "25 of 28 pairs carry a non-empty expected withdrawal": it
records a truncation artifact, not the intervention's bite. The arms saw the full narrative while the adjudicator
saw 9,200 characters, so on those three units arm and ground truth were reading different evidence. Recomputed
without them, the primary figures are unchanged to three decimals, because the excluded units contribute zero to
both numerator and denominator. Separately, 166 KB "first-contact intake messages" are a corpus-generation defect
(§6.1).

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

**The contract is a completion set, not a triage list, and this is a property of the construct rather than a
footnote about one table.** The contract answers "what would a complete file for this scope contain," while every
claim in this paper about what a system should ask for next is a claim about triage. The two are different
constructs and we have ground truth only for the first. The document-to-decision mapping shows how sharply this
bites: on rent increase, D12 alone requires 8 of the 11 contract documents, D7 requires none from the party, D1
requires 1, and 6 of 11 documents are required by exactly one decision. The release set of any probe is therefore
the residue of whichever decision that probe closes, and for our primary probe it is almost entirely the residue
of D12. No triage ground truth exists in this work.

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
**retention**.

**A claim we made here is false and we retract it.** Earlier drafts closed this paragraph with: "A paired
difference is unaffected by the constant level that saturates the static task." That is the reasoning the whole
dynamic design rests on, and our own committed artifacts refute it. The degeneracy is not confined to the level;
it propagates through $E$, the release set. Over the 28 confirmatory pairs:

| quantity | distinct values across 28 pairs | modal value's share |
|---|---|---|
| per-case reference set on the originals (static gold) | **1** | 28 / 28 pairs |
| release set $E$ (dynamic gold) | **3** | 5-document core supplies **125 of 132** expected withdrawals (94.7%) |

The three values of $E$ are: the same five documents on 18 pairs; those five plus `tenant_correspondence` on 7;
and empty on 3 (and those 3 are the truncation artifact of §4.1, not a substantive null). So the dynamic gold
answer varies across 28 pairs in **one document**. A paired difference escapes a constant *level*; it does not
escape a constant *change*. §5.1 reports the case-ignoring oracle and the permutation null that make this
measurable.

**The intervention is not minimal, and we now have the data to say so rather than assume it.** The 28 variant
sentences are 28 *different* sentences, not one template. Several supply the notice receipt date as well as the
non-challenge — for example "Die Mitteilung über die Mietzinserhöhung erhielt ich am 30.04.2025; innerhalb der
folgenden 30 Tage habe ich keine Anfechtung eingereicht" — which settles D3's own predicate in addition to the
target, contradicting "settles exactly one branch predicate." Ten of the 28 are in the future or present tense ("I
will not bring a challenge within 30 days"), which is a materially different legal proposition from the past-tense
statement the probe intends. Comparing adjudicated statuses across each pair gives the flip table directly:

| decision | pairs on which its status changed | direction |
|---|---|---|
| D12 (abusiveness) | 25 | all `unknown` → `dead` |
| D11 | 10 | 5 `unknown`→`dead`, 3 `unknown`→`live`, 1 `live`→`dead`, 1 `live`→`unknown` |
| D3 (30-day challenge) | 7 | all `unknown` → `dead` |
| D1 (scope applicability) | 4 | 2 `live`→`unknown`, 2 `unknown`→`live` |

D1 is the scope-applicability decision and has nothing to do with the 30-day clock; it moves in **both**
directions. D11 moves in both directions too. §6.4 previously said that no independent check confirmed minimality;
the check exists, it is a groupby over the committed adjudications, and **the intervention is not minimal**.

One further legal risk sits on the single item the whole positive result rests on. The decision carrying 5 of the
6 releasable documents is D12, abusiveness, and the contract treats failure to challenge within 30 days as
extinguishing it. The same contract separately carries D7, whether the increase is *null* — and nullity for defect
of form is not subject to that deadline, which is exactly the scenario family our development split is built from.
No lawyer checked this. If D12 should not close on the probe, the primary outcome is measuring the contract's
error.

We also note that the e07 sentence is close to the literal negation of text the adjudicator is shown verbatim:
`conf_ref.py`'s prompt prints each decision's `live_when` and `dead_when`, and D12's `live_when` reads "A covered
increase is not ineffective and was challenged within 30 days, but its stated grounds … have not been assessed."
D12 flipping `dead` on 25 of 28 pairs is therefore closer to string negation than to legal adjudication.

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
adjudicator self-consistency 93%, with a non-empty expected withdrawal on 25 of 28 pairs — above the preregistered
threshold of 15 below which no primary comparison would have been reported. That 25-of-28 figure should not be
read as characterising the intervention's bite: the three exceptions are the truncation artifact of §4.1. The
contract releases a mean of 4.7 documents per pair, 132 in total.

**Intervals bootstrap over scenarios, not cases**, 5000 draws, 95% percentile interval \cite{efron1979}. Five
cases of one scenario are five variations on a single fact pattern; resampling cases would shrink every interval
by roughly $\sqrt{5}$ for no reason but how the corpus was generated.

**What the bootstrap's reference population actually is.** It resamples scenarios from `synthetic-150`, a
generated corpus in which every case registry carries the same hand-authored static rule template and each
scenario is German/English twins of one fact pattern (§4.4). The between-scenario variance being estimated is
therefore the *generator's*, not a population of tenancy cases. The per-scenario excess vectors make this visible:
`gemini-2.5-flash`'s `b5` arm gives (+0.114, +0.106, +0.106, +0.110, +0.114, +0.106) — the numerator is constant
across all six and the only variation is whether $|E|$ is 5 or 6. The interval's width is a property of the
generator's document counts, not sampling uncertainty about tenancy cases, and the tightness of our controlled
intervals should be read in that light rather than as precision.

**Seeds, stated exactly.** One RNG stream remains. The random-drop baseline is now computed in **exact closed
form** rather than simulated (§4.5), which removes the `20260916` stream from every excess figure and dissolves
the third-decimal disagreement between two of our scripts that an earlier draft carried as a footnote. The
bootstrap over scenarios that produces every confidence interval in §5.2, §5.3 and §5.4 is seeded `7`; the
bootstrap over the raw between-arm difference in §5.2 is seeded `20260916`. Our earlier blanket statement that all
intervals use seed 20260916 was wrong.

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

**A scoring dead zone, and how much of each arm it hides.** Withdrawal precision has $\sum|W \cap E|$ in the
numerator and $\sum|W \cap E| + \sum|W \cap K|$ in the denominator, so a withdrawal of a document that is in
neither $E$ nor $K$ counts in neither. **Five of the 16 rent-increase catalogue documents appear in no decision of
the contract** — `bank_statement`, `conciliation_request`, `index_publication`, `reference_rate_publication`,
`rent_payment_records` — and are therefore permanently invisible to precision and can never be a correct
withdrawal. This matters twice. `gpt-5.6-terra`'s `b5` arm makes 208 withdrawals of which **78 (37.5%) fall in the
dead zone**, invisible to its reported precision of 0.600. And the single document that `claude-haiku-4.5` and
`deepseek-v3.2` withdraw on 28 of 28 pairs is `conciliation_request`, a dead-zone document: their "below chance"
result is entirely produced by dropping something that could not have been right whatever the case said.

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
0.97 modal-oracle F1, its 84% per-decision self-consistency, and its per-decision settle counts. It was never re-measured
on clean cases. The saturation results we do report (§5.1) are computed on the clean 30-case and 49-case sets.

### 4.5 The volume control

Withdrawal recall as defined above is **not comparable across arms that request different numbers of documents**.
An arm that asks for more has more to drop, and therefore more chances to drop something the contract happened to
release. On the held-out read `b5_induced_graph` requests a mean of 10.0 documents where `b1_direct` requests 5.3
and `b3_graph_then_list` 5.5, and the reference set itself averages 10.0.

The control removes the confound by never comparing arms to each other. **Each arm is compared against itself
dropping the same number of its own requested documents at random.** For each pair, $|W|$ documents are sampled
without replacement from that arm's own pre-intervention request set $B$, and the expected number landing in $E$
is that arm's random baseline on that pair.

**The baseline is exact, not simulated, and we corrected this.** Sampling $|W|$ of $|B|$ without replacement is
hypergeometric, so the expectation has a closed form:

$$\mathbb{E}\big[|W_{\text{rand}} \cap E|\big] \;=\; |W| \cdot \frac{|B \cap E|}{|B|}.$$

Every figure in this paper now uses that identity. Earlier drafts estimated it with a 300-draw simulation, and the
simulation error was **not** propagated into any interval — both analysis scripts drew the baseline once per pair
and then held it fixed across all 5000 bootstrap resamples. The error was material relative to the intervals it
sat inside: on `deepseek-v3.2`'s `b5` arm the simulated baseline was 0.03414 against an exact 0.03571, an error of
0.00157 against a reported interval half-width of 0.0034, roughly half. On `gemini-2.5-flash` the error was
0.00122 against a half-width of 0.0024. So part of a published interval was a simulation artifact rather than a
property of the data, and two of our own scripts disagreed in the third decimal on the same quantity purely
because they drew from a shared RNG stream in a different order — a discrepancy an earlier draft carried as a
footnote and explained rather than fixed. The closed form dissolves it. The reported statistic is the *excess over
own random baseline*,

$$\text{excess} \;=\; \frac{\sum_{\text{pairs}} |W \cap E| \;-\; \sum_{\text{pairs}} \mathbb{E}\big[|W_{\text{rand}} \cap E|\big]}{\sum_{\text{pairs}} |E|},$$

bootstrapped over scenarios. Both the size of the request set and the number of withdrawals are held at the arm's
own observed values.

**What the statistic does and does not reward.** We previously wrote that "the only thing the statistic can reward
is the arm's choice of *which* documents to drop," and that "an interval above zero means that choice carries
information." The first half is right conditional on $|W|$ and $|B|$; the second is wrong on this corpus, and the
permutation null of §5.1 is what separates them. When $E$ is near-constant, a *constant* preference over document
types scores exactly as well as a case-sensitive one, so an interval above zero means only that the arm's fixed
habit happens to overlap the fixed release set. The corrected sentence is: **the statistic rewards a preference
over document types; only the permutation null distinguishes a preference computed from this case from a standing
habit, and on this corpus it does not.**

The control was **not preregistered**. It was added after the single held-out read, because the request counts in
the result table made the confound visible, and it is disclosed as an unplanned analysis rather than folded into
the plan. It is applied to every dynamic result reported in this paper.

Five limits of the control should be stated; the first three were in earlier drafts, the last two were not.

1. It equalises volume within the withdrawal metric only: retention is measured on each arm's own holdings and is
   reported separately.
2. It controls for how much an arm asks for, not for whether asking for more is itself the right behaviour.
3. It produces a **per-arm** statistic. Earlier drafts stopped here and reasoned from interval overlap. We now
   compute the differences directly: the design is fully paired — all conditions ran the same 28 pairs and the
   same 6 scenarios — so a paired cluster bootstrap on the *same* resample index set is both available and the
   correct, more powerful test. Those intervals are reported in §5.2 and §5.3 and the two TODOs are closed.
4. **It equalises level but not achievable range.** The denominator is $\sum|E| = 132$ for every arm, but an arm
   can only score on documents it actually requested, so its ceiling is
   $\big(\sum\min(|W|,|B\cap E|) - \sum\mathbb{E}[\cdot]\big)/\sum|E|$, which varies with the arm's own behaviour.
   Across the four `b5` conditions the ceiling ranges from +0.108 to +0.154, a factor of 1.4, so the headline
   spread is not a like-for-like comparison. We report excess as a percentage of ceiling alongside it in §5.2–§5.4.
5. **It does not equalise coverage.** An arm that never requested a releasable document cannot withdraw it. We
   therefore also report $|B \cap E|$ and coverage-normalised recall. This changes the reading of two cells:
   `claude-haiku-4.5`'s `b5` arm requested 125 of the 132 releasable documents — coverage 0.947, the highest of
   any condition — and withdrew **none** of them, which is a far sharper statement than "below chance"; and the
   two positive arms are not the comparable pair an equal denominator makes them look, with coverage-normalised
   recall of 0.951 for `gpt-5.6-terra` against 0.333 for `gemini-2.5-flash`.

---

## 5 Results

Every number in this section is read from the committed analysis outputs or recomputed from the run artifacts.
Four analysis scripts produce them (`development_analysis.py`, `confirmatory_analysis.py`, `transfer_analysis.py`,
`model_generality_analysis.py`), and none makes a network call.

**A reproducibility note, corrected.** Earlier drafts carried a caveat saying the per-case inputs were "not
currently committed" and that the analyses reproduced only because scratch files survived on one machine. That
caveat is **stale and we withdraw it**: 26 artifacts are committed under `research/casepath/artifacts/` with a
SHA-256 manifest, including the run records, the reference adjudications and the graph and proposition bundles,
and each script resolves the committed copy in preference to its original scratch path. Every number in this
section is recomputed from those committed artifacts. Two real defects remain and we name them instead. First,
`confirmatory_analysis.py` does not execute as committed from the repository root — the path shim it depends on is
defined below its first use, and the package import assumes a working directory — so the script must be fixed
before the table it produces can be regenerated. Second, `development_analysis.py` still reads two raw `/tmp`
paths and its loader silently skips a missing or partially written input rather than failing, which is the
mechanism behind the amendment-A3 non-reproduction discussed in §5.2 and §6.8.

### 5.1 Both task formulations are degenerate, and a case-ignoring constant wins the dynamic one

This subsection is the paper's central result and it was not in earlier drafts. We report the static degeneracy
first, because we found it first and it motivated the dynamic design; then the dynamic degeneracy, which we found
only by running the oracle that the static section already contains.

#### 5.1.1 The static checklist task is degenerate on both scopes

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

**Separating "the contract is degenerate" from "the corpus never exercises it."** The observed checklist count is
1, but the *structurally reachable* count is not: enumerating open-sets over the 12 rent-increase decisions
reaches 19 distinct checklists. The contract can express variation; this corpus does not elicit it. Reporting the
pair (reachable, observed) rather than the observed count alone is what makes this a diagnostic others can run
rather than an unfalsifiable claim about a domain, and we recommend it in that form.
**TODO[number not found: reachable checklist count on the 21-decision termination contract].**

What this licenses is narrower than what we previously claimed. We have two reference contracts, built by the same
authoring procedure, scored against one generated corpus, in one domain and one legal system. That is consistent
with a shared property of the domain, and equally consistent with a shared property of the procedure or of the
corpus generator — and §4.4 records that the generator uses one hand-authored rule template per case registry,
which would tend toward a single gold checklist by construction. We therefore claim that **a static
document-checklist task over intake messages was uninformative on both scopes we built**, and that anyone building
such a benchmark should check for this degeneracy before scoring on it. We do not claim that such a task is
impossible in this domain.

#### 5.1.2 The dynamic task is degenerate too, and we did not see it until we ran the oracle

We built the paired design of §4.2 specifically to escape §5.1.1, on reasoning we have now retracted. The
diagnosis extends to the release set:

| task | gold object | distinct values | modal share |
|---|---|---|---|
| static (§5.1.1) | per-case reference checklist, 28 originals | **1** | 28 / 28 |
| dynamic (§5.2–§5.4) | release set $E$, 28 pairs | **3** | 5-document core = **125 / 132** expected withdrawals (94.7%) |

The exact analogue of the modal-list oracle is a policy that reads no case: request the modal ten reference
documents, always withdraw the same modal five. Scored under our own volume control, on the same 28 pairs, with
the same scenario bootstrap:

| policy | recall | own random baseline | **excess** | 95% CI | % of its own ceiling |
|---|---|---|---|---|---|
| **modal-withdraw oracle (ignores the case)** | **0.947** | 0.500 | **+0.447** | **[+0.429, +0.476]** | 100% |
| best measured arm (`b5`, `gpt-5.6-terra`) | 0.591 | 0.473 | +0.118 | [+0.107, +0.125] | 100% |
| second (`b5`, `gemini-2.5-flash`) | 0.189 | 0.081 | +0.108 | [+0.106, +0.112] | 100% |

**The case-ignoring constant beats our best arm by a factor of 3.8 on the task we presented as measuring
case-sensitive retraction.** Every arm in §5.2 and §5.3 is far below it. This is the same `|distinct gold| = 1`
pathology we correctly diagnosed for the static task, one level down, and the honest reading of §5.2–§5.4 is that
they report *which fixed block of documents each pairing drops*, not whether the process graph computed what this
case released.

**A permutation null gives the mechanism.** Permute which pair's release set $E$ is attached to which pair's
$(B, W)$, holding each arm's behaviour fixed. This asks directly whether the arm is responding to *this* case
rather than exhibiting a standing habit. 5000 permutations:

| model | arm | observed | permutation null mean | 95% permutation range | p(perm ≥ obs) |
|---|---|---|---|---|---|
| gpt-5.6-terra | b5 | +0.118 | +0.115 | [+0.112, +0.120] | **0.21** |
| gemini-2.5-flash | b5 | +0.108 | +0.108 | **[+0.108, +0.108]** | 1.00 |
| claude-haiku-4.5 | b5 | −0.078 | −0.074 | [−0.078, −0.065] | 1.00 |
| deepseek-v3.2 | b5 | −0.036 | −0.034 | [−0.036, −0.029] | 1.00 |

Attaching a randomly chosen *other* case's release set reproduces the headline numbers. `gemini-2.5-flash`'s
statistic is **exactly invariant** to the permutation — it carries literally zero case-specific information — and
`gpt-5.6-terra`'s sits comfortably inside its own null. The excess measures the alignment between a constant
withdrawal habit and a near-constant release set.

**Two cheap diagnostics, which is the recommendation we stand behind.** Both run in seconds on committed
artifacts, neither needs a model call, and we needed both ourselves and ran neither before writing the first draft
of this paper. Before reporting any set-valued retraction metric: (i) score the case-ignoring constant that emits
the modal request set and the modal withdrawal, and report it in the same table as the arms; (ii) permute the gold
release sets across units and report the null beside every effect. An effect that does not clear both is a
description of a habit, not a measurement of retraction.

### 5.2 Confirmatory read on rent increase, with the volume control

**Read this section under §5.1.2.** Every figure below is below the case-ignoring oracle's +0.447, and the
permutation null does not separate the leading arm from a standing habit. What the section establishes is which
fixed block each arm drops and how the volume control changes the apparent size of that, not that any arm computed
a case-specific retraction.

One read, 28 pairs across the six held-out scenarios. The method was frozen at commit `c43bc22` and the
preregistration was written at `ee6f266`; earlier drafts attributed the preregistration to `c43bc22`, which is the
method freeze. Each pair is a case and the same case with a minimal factual addition establishing that the tenant
did not challenge within 30 days. Adjudicator self-consistency 93% (three temperature-0 samples of one model, §4.1); 25 of 28 pairs carry a
non-empty expected withdrawal, the three exceptions being the truncation artifact of §4.1; the contract releases
a mean of 4.7 documents (132 in total).

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

| arm | recall | coverage \|B∩E\| | own random baseline (exact) | **excess** | 95% CI | ceiling | % of ceiling |
|---|---|---|---|---|---|---|---|
| b1_direct | 0.038 | 41 (0.311) | 0.098 | **−0.060** | [−0.094, −0.024] | +0.159 | −38% |
| b3_graph_then_list | 0.121 | 47 (0.356) | 0.110 | +0.011 | [−0.017, +0.038] | +0.094 | 11% |
| b5_induced_graph | 0.591 | 82 (0.621) | 0.473 | **+0.118** | **[+0.107, +0.125]** | +0.118 | **100%** |
| *modal-withdraw oracle (§5.1.2)* | *0.947* | *125 (0.947)* | *0.500* | *+0.447* | *[+0.429, +0.476]* | *+0.447* | *100%* |

Baselines are the exact hypergeometric values of §4.5; earlier drafts simulated them and reported +0.061 and
+0.118 with slightly different third decimals.

**`b5` sits at exactly 100% of its own ceiling.** Its reported excess *is* the maximum the statistic could return
given how many documents it requested and dropped. That is the signature of a saturated metric rather than of a
measured effect, and it is what §5.1.2 predicts.

The control changes what the first table means, in three ways.

**The headline shrinks by a factor of 4.7.** The uncontrolled comparison of `b5_induced_graph` against `b1_direct`
is +0.553 [+0.459, +0.613] — a number that passes the preregistered support criteria and that would, reported
alone, be the paper's result. Of `b5`'s 0.591 recall, 0.473 — four fifths of it — is reproduced by dropping the
same number of its own documents at random. What survives is a within-arm excess of +0.118 [+0.107, +0.125],
about a fifth of the raw figure. We note that +0.553 and +0.118 are not the same kind of quantity: the first is a
between-arm difference of raw recalls, the second a within-arm excess. **The like-for-like controlled contrast is
now computed** rather than left as a TODO. Using a paired cluster bootstrap over scenarios on the same resample
index set, so that the positive correlation between the two estimates is carried rather than ignored:

| controlled contrast | difference | 95% CI |
|---|---|---|
| excess(b5) − excess(b1) | **+0.178** | [+0.132, +0.219] |
| excess(b3) − excess(b1) | +0.072 | [+0.028, +0.113] |
| excess(b5) − excess(b3) | +0.107 | [+0.084, +0.127] |

Both TODOs in §4.5 and §5.2 are closed. Reasoning from interval overlap, which earlier drafts did, is the wrong
tool for positively correlated estimates; these intervals replace it. They inherit §5.1.2 in full — a difference
between two standing habits is still a difference between two standing habits.

**One arm's sign changes.** `b1_direct`'s raw withdrawal recall is 0.038 — small but positive, reading as
occasionally correct. Against its own exact random baseline of 0.098 it is −0.060, with an interval lying entirely
below zero. That inversion is invisible in the raw number, and it is the one cell in this paper where a *nonzero*
hit rate genuinely falls below its own baseline, which is what "below chance" should mean. We flag immediately
that it does **not** generalise: it holds on one reasoner of four (§5.3) and does not reproduce on the second
scope (§5.4), so it is a property of this pairing and not of direct prediction. Note also that `b1_direct` is the
one arm here that is genuinely case-sensitive — 21 distinct request sets across the 28 pairs, against `b5`'s
**one** (§5.3).

**The preregistered primary is supported, with a qualification.** The amended primary comparison, `b3` against
`b1`, is +0.083 [+0.018, +0.151] with a retention difference of +0.068, and the preregistered verdict is
SUPPORTED. Under the control, `b3`'s excess over its own random baseline is +0.011 with an interval spanning zero,
while `b1`'s lies entirely below zero. The natural reading is that `b3` beats `b1` because `b1` is below chance
rather than because `b3` is informative, and the paired contrast above now tests it: +0.072 [+0.028, +0.113]. The
verdict stands as recorded — it was fixed in advance and is not revised after the fact — with the qualification
attached permanently.

**A per-scenario consistency claim we withdraw.** Earlier drafts wrote: "The effect is not carried by one
scenario: `b5_induced_graph` has the highest recall on all six held-out scenarios individually, ranging
0.481–0.630." That sentence reads consistency as robustness, and on a constant output it is **guaranteed**. `b5`
emits one distinct request set and two distinct withdrawal sets across all 28 pairs (§5.3), so per-scenario
agreement is a property of the arm being constant, not evidence that the effect replicates across fact patterns.
The same mechanism explains an interval width we previously read as strength: `b5`'s CI is tight because its
statistic is nearly constant under scenario resampling, while the genuinely case-varying arms `b1` and `b3` get
wider intervals. We delete the robustness reading and keep the numbers as description.

`b5`'s cost is real: it has the **worst retention** of the three (0.544 against 0.573 and 0.641), satisfying the
preregistered tolerance (−0.029, within −0.050) but dropping documents it should have kept.

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

**The mechanism of the non-reproduction, not just the symptom.** Earlier drafts reported that A3's numbers "no
longer reproduce" and left the reader to infer that data had drifted. What drifted was *which units the analysis
saw*. `development_analysis.py`'s loader guards each input with an existence check and swallows exceptions, so it
silently shrinks the pair set when an input is missing or half-written rather than failing. The development
originals file it pairs against completed **after** A3 was committed. Searching all 6188 twelve-pair subsets of
today's 17 pairs, no scenario-coherent subset reproduces A3's tallies exactly; the closest — `S1`+`S2`+`S3`, 12
pairs, 51 expected withdrawals — reproduces **both** recorded deltas to three decimals (+0.137 and +0.039). The
scenario missing from it, `S1_form_defective`, is the one most adverse to the amended primary, and restoring it is
what moves `b3 − b1` from +0.137 to +0.104 and the interval from excluding zero to including it. Corroborating
that this is a live failure mode rather than a reconstruction: the confirmatory-read commit message quotes
"development, where b5 scored 0.033 and b3 0.148", which are the recalls of a *different* three-of-four scenario
subset, so two different partial views of development were each called "development" thirty-five minutes apart.
A3 was therefore decided against a partially written output file, and the complete data sat on disk unre-analysed
before the held-out read.

A3 was declared before the held-out data was read and did not delete the comparison it demoted, so the original
primary survives in the record and is reported above — which is the reason to preregister. The amendment was
nonetheless a mistake twice over: it moved the primary away from the arm that turned out to be the only one with
a positive excess, and it rested on a figure computed from a subset the script chose silently. The fix is in the
tooling as much as in the discipline: the loader should fail loudly, and every table in this paper should print
$n$, the scenario names and per-scenario $|E|$ beneath it.

### 5.3 The same frozen artifact gives opposite answers under different reasoners — but each answer is a constant

The result in §5.2 is a property of a pairing, not of the artifact. Holding the induced process graph, the
reference contract, the case corpus and the code fixed on the same 28 held-out pairs, and changing **only the
model that interprets a case against them and compiles it**:

| model | arm | recall | correct / false | coverage \|B∩E\| | baseline (exact) | **excess** | 95% CI | % ceiling | perm. p |
|---|---|---|---|---|---|---|---|---|---|
| gpt-5.6-terra | b1_direct | 0.038 | 5 / 35 | 41 (0.311) | 0.098 | **−0.060** | [−0.094, −0.024] | −38% | 0.92 |
| | b5_induced_graph | 0.591 | 78 / 52 | 82 (0.621) | 0.473 | **+0.118** | [+0.107, +0.125] | **100%** | **0.21** |
| claude-haiku-4.5 | b1_direct | 0.038 | 5 / 21 | 32 (0.242) | 0.034 | +0.004 | [−0.009, +0.017] | 7% | 0.62 |
| | b5_induced_graph | **0.000** | 0 / 30 | **125 (0.947)** | 0.078 | −0.078 | *see below* | −61% | 1.00 |
| gemini-2.5-flash | b1_direct | 0.038 | 5 / 27 | 37 (0.280) | 0.038 | +0.000 | [−0.012, +0.013] | 0% | 0.99 |
| | b5_induced_graph | 0.189 | 25 / 3 | 75 (0.568) | 0.081 | **+0.108** | [+0.106, +0.112] | **100%** | **1.00** |
| deepseek-v3.2 | b1_direct | 0.045 | 6 / 21 | 28 (0.212) | 0.035 | +0.010 | [−0.026, +0.040] | 16% | 0.84 |
| | b5_induced_graph | **0.000** | 0 / 29 | 32 (0.242) | 0.036 | −0.036 | *see below* | −23% | 1.00 |
| *modal oracle* | *ignores the case* | *0.947* | *125 / 0* | *125 (0.947)* | *0.500* | *+0.447* | *[+0.429, +0.476]* | *100%* | — |

All four conditions ran on all 28 pairs. Baselines are exact (§4.5); earlier drafts simulated them and reported
+0.119, −0.077, +0.109 and −0.034 with a footnote explaining a third-decimal disagreement between two scripts,
which the closed form removes.

**Two intervals are suppressed because they are arithmetic, not evidence.** `claude-haiku-4.5` and
`deepseek-v3.2` both have withdrawal recall of exactly **0.000**. With the numerator identically zero the
statistic reduces to $-\sum\mathbb{E}[\cdot]/\sum|E|$, which is non-positive on every pair, therefore on every
scenario, therefore on every one of the 5000 resamples. Reporting "the interval lies entirely below zero" for
these cells states a fact about algebra. The evidential content is the count comparison, and we give it instead:
`claude-haiku-4.5` scored **0 correct withdrawals against 10.2 expected** under its own random dropping, and
`deepseek-v3.2` **0 against 4.7**. An exact scenario-level sign test, which *can* fail, gives p = 0.031 — the
minimum attainable at n = 6 — for all four `b5` rows and for `gpt-5.6-terra`'s `b1`, and p = 1.000 for every other
row.

**We withdraw "anti-correlated" and "actively wrong" throughout.** A constant is not anti-correlated with
anything; there is no negative association to estimate. What these two arms do is withdraw **one fixed
out-of-contract document on every pair**, and the correct phrasing is "no correct withdrawals; withdrew one fixed
document type that appears in no decision of the contract."

**The arms are near-constant functions of the case, and this is the diagnostic that governs the whole section:**

| model | arm | distinct request sets / 28 | distinct withdrawal sets / 28 | total withdrawals | distinct document types withdrawn |
|---|---|---|---|---|---|
| gpt-5.6-terra | b1_direct | 21 | 15 | 44 | 9 |
| | b5_induced_graph | **1** | **2** | 208 | 8 |
| claude-haiku-4.5 | b1_direct | 19 | 11 | 26 | 8 |
| | b5_induced_graph | **2** | **2** | 30 | **2** |
| gemini-2.5-flash | b1_direct | 22 | 12 | 32 | 12 |
| | b5_induced_graph | **1** | **1** | 28 | **1** |
| deepseek-v3.2 | b1_direct | 17 | 11 | 27 | 12 |
| | b5_induced_graph | **1** | **2** | 29 | **2** |

Read this table against the claims it supports. `gpt-5.6-terra`'s `b5` emits **one** request set across all 28
pairs and applies the *identical* 8-document withdrawal on 26 of them: the +0.118 is one event scored 26 times.
`gemini-2.5-flash`'s entire "+0.108" is `property_management_statement`, dropped on 28 of 28 pairs — one document.
`claude-haiku-4.5` and `deepseek-v3.2` both drop `conciliation_request` on 28 of 28, which is in the dead zone
(§4.3) and can never be correct; their excesses differ (−0.078 against −0.036) only because their request-set
sizes differ (mean |B| 13.07 against 7.00), which changes the denominator of their own baselines. **The
"four-model sign reversal" is four constants**, and the two negative cells are one behaviour counted twice, not
two independent replications. Meanwhile the arms the paper treats as uninformative — `b1_direct` — are the
genuinely case-sensitive ones, with 17 to 22 distinct request sets each.

The spread on one identical artifact is **+0.118 to −0.078**, and we now state what it does and does not license.
It licenses the existence proof: the number is not a function of the representation alone. It does not license a
ranking of four reasoners, for three reasons. The effective number of independent model decisions per cell is
about one (table above). The two "signal" arms both sit at exactly 100% of their achievable ceiling, which is
metric saturation rather than measured effect. And a paired bootstrap on the same resample indices shows the two
positive models are **not separable**:

| paired contrast on `b5` | difference | 95% CI | Bonferroni over the 8 intervals |
|---|---|---|---|
| gpt-5.6-terra − claude-haiku-4.5 | +0.196 | [+0.180, +0.213] | [+0.174, +0.218] |
| gpt-5.6-terra − gemini-2.5-flash | +0.010 | **[−0.001, +0.018]** | [−0.005, +0.020] |
| gpt-5.6-terra − deepseek-v3.2 | +0.154 | [+0.145, +0.161] | [+0.142, +0.162] |
| gemini-2.5-flash − deepseek-v3.2 | +0.144 | [+0.143, +0.146] | [+0.143, +0.147] |
| claude-haiku-4.5 − gemini-2.5-flash | −0.186 | [−0.203, −0.178] | [−0.211, −0.177] |
| claude-haiku-4.5 − deepseek-v3.2 | −0.042 | [−0.059, −0.033] | [−0.068, −0.031] |

Earlier drafts inferred non-separation of the two positive models from interval overlap; the paired test confirms
it properly, and the extreme-pair reversal survives Bonferroni correction.

**Multiplicity, which our own preregistration required and we did not apply.** The plan commits to "one primary
outcome, one comparison, one test," and states that if a secondary is promoted to an inferential claim, Holm
correction is applied across the whole family and the promotion is logged as an amendment. The eight intervals in
this table **are** inferential claims — the analysis code labels each cell by whether its interval excludes zero —
and the headline is constructed from the **maximum and minimum of those eight**. Neither correction nor promotion
was logged. We correct both: the corrected paired intervals are given above, we state plainly that the extreme
pair was selected from eight intervals, and the family is larger still if §5.2's three and §5.4's three are
counted.

**And the ground truth was written by one of the four models under test.** See §4.1: the adjudicator is
`gpt-5.6-terra` at temperature 0, the same model as the highest-scoring condition. On this design "the
interpreting model decides the sign" is not distinguishable from "the model that wrote the labels agrees with
itself." The one bound available at zero compute cost is that the same model, grading itself on the termination
scope, still scored −0.012 with an interval spanning zero (§5.4), so grading affinity is not sufficient. The
confound is not removed.

**Scope of the sentence we are careful about.** What changed between conditions is the model that performs the
case-dependent steps **and the compilation**. The compiler is a model step. The corpus, the propositions, the
induced graph, the reference contract, the catalogue, the case set and the pipeline code are what were held fixed.
Our earlier phrasing — that all artifacts produced by model steps were held fixed — was wrong, and the diagnostic
table below proves it: the per-model chain counts differ, which could not happen if the compiled artifact were
frozen.

Neither headline effect from §5.2 is a property of the method. `b1_direct` is below chance on **one model of
four**: on the other three its interval spans zero, uninformative rather than actively wrong. Its raw withdrawal
recall is identical to three decimals (0.038) on three of the four models; what differs is each model's own chance
level, set by how much that model drops — `gpt-5.6-terra`'s direct arm has a baseline of 0.098 against 0.034 and
0.038 for the others. We checked that this triple coincidence is a coincidence and not a bug: the three models'
withdrawal sets differ substantially, with 15, 11 and 12 distinct sets across the 28 pairs. `b5_induced_graph`
scores above zero on **two of four** and below on the other two.

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

**On what was held identical — an under-claim we correct.** Earlier drafts said the runner scripts for the three
non-`gpt` conditions "are not in the repository" and that prompt and temperature identity is "not verifiable from
anything on disk." That is stale. `runners/multimodel.py` and `runners/conf_arms.py` are both committed;
`multimodel.py` takes the model from a single environment variable, pins `temperature=0.0` and `max_tokens=8000`,
and constructs its prompts from the identical 16-document catalogue, the identical scope string, the identical
frozen graph and proposition bundle and the identical case file as `conf_arms.py`. That is precisely the evidence
for "only the model changed" that we said did not exist, and it is stronger than the assertion it replaces. What
remains genuinely unrecorded is per-run provenance: no run artifact stores the prompt text or the decoding
settings it was produced under, so the identity is established by reading the runners rather than by inspecting
the outputs. **TODO[verify: record prompt text and temperature in each run artifact, so identity is checkable from
outputs rather than from source].**

`claude-haiku-4.5` compiles about twice as many chains as the two positive models (67.6 against 31.0 and 34.0, and
1.7× deepseek's 39.0) and requests about 1.7× as many documents (12.6 against 6.5–7.4; over the 28 originals,
13.07 against `gpt-5.6-terra`'s 10.0), and still withdraws nothing correct — despite requesting **125 of the 132
releasable documents**, the highest coverage of any condition. That is a sharper statement than "below chance": it
asked for almost everything the intervention released and let go of none of it. As noted in §1.1, chain count is
the one recorded proxy that orders the four models consistently with the sign of their result, at a search-adjusted
chance of about 0.42.

We also note that the additive excess is not the only reasonable functional form, and the choice changes which
model looks strongest. As an observed/expected ratio, `gpt-5.6-terra` scores 78 correct against 62.4 expected
(1.25×) while `gemini-2.5-flash` scores 25 against 10.7 (2.36×) — so under the ratio form gemini is nearly twice
as informative, where the additive form puts them within +0.010 of each other. The ratio ordering (2.36, 1.25, 0,
0) matches the ascending chain-count ordering (31.0, 34.0, 39.0, 67.6) exactly, which sharpens the §1.1 hypothesis
without making it a finding.

**Stated carefully, and more narrowly than before.** Earlier drafts closed this section with: "a source-grounded
process representation does not by itself confer correct retraction behaviour … on two of four reasoners it
produces the only informative withdrawal behaviour observed anywhere in this work." We withdraw the second half.
No arm in this work demonstrated informative withdrawal behaviour, because on this corpus the metric cannot
distinguish informative withdrawal from a standing habit, and a case-ignoring constant outscores every arm by 3.8×
(§5.1.2). What this section establishes is the first half, as an existence proof and no more: **the same frozen
artifact, driving the same code, produces opposite signs of a preregistered metric under different interpreting
models, so that number is not a property of the representation.** Whether any of these models retracts correctly
is a question this design cannot answer.

### 5.4 Transfer to termination fails, and the failure was computable in advance

One read, 49 pairs across 8 scenarios, under a separate preregistration and its amendment T1 (a power decision
taken before any arm outcome existed). Adjudicator *self-consistency* is 66% (§4.1: three temperature-0 samples of
`gpt-5.6-terra`, not three raters), materially lower than the 93% on rent increase — which on the corrected
reading means the ground-truth model contradicted itself on a third of the decisions this null rests on. The
volume control is the primary outcome here, not an afterthought.

| arm | expected | correct | false | recall | own random baseline | **excess** | 95% CI | retention | requested |
|---|---|---|---|---|---|---|---|---|---|
| b1_direct | 77 | 5 | 80 | 0.065 | 0.049 | +0.016 | [−0.010, +0.050] | 0.723 | 6.4 |
| b3_graph_then_list | 77 | 6 | 70 | 0.078 | 0.060 | +0.018 | [−0.010, +0.057] | 0.756 | 6.3 |
| b5_induced_graph | 77 | **0** | 6 | 0.000 | 0.013 | **−0.013** | [−0.026, +0.000] | 0.992 | 16.0 |

Baselines and excesses are recomputed in exact closed form (§4.5); earlier drafts gave the simulated +0.015,
+0.019 and −0.012.

**Preregistered verdict: NOT SUPPORTED.** No arm's interval excludes zero. The rent-increase finding that
`b1_direct` is below chance does not reproduce here: its interval spans zero, consistent with §5.3, where that
effect held on one reasoner of four.

Two notes on the `b5` row. Its recall is again exactly 0.000, so its excess is again minus its own baseline by
identity and the upper bound of its interval is pinned at exactly zero — reached on resamples in which no
withdrawal occurred at all. And this condition ran `gpt-5.6-terra` arms against `gpt-5.6-terra` ground truth
(`runners/term_arms.py`), which is the one available bound on the adjudicator confound of §4.1: grading affinity
did not produce a positive result here.

**The sensitivity check the 66% figure demands cannot be run, and that is the finding.** The obvious robustness
analysis is to restrict to pairs where all three adjudicator samples agreed on every decision the probe touches
and ask whether the null survives. We ran it on `term_ref_raw.json`: **zero of the 49 pairs qualify.** The probe
touches 16 of the 21 decisions across the corpus, and no pair is unanimous on all of them; indeed no pair is
fully unanimous on *any* reading we tried. So the transfer null rests on ground truth in which not one unit
reached agreement, where "agreement" already means only that one model gave the same answer three times at
temperature 0. We report the null as measured and attach this to it permanently: the transfer result is a null
measured against unreliable labels, and this paper cannot distinguish a real transfer failure from a ground truth
too noisy to detect one.

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

### 6.1 The corpus is synthetic, and defective in one respect we did not previously report

Every case in this work comes from a generated 150-claim intake corpus, in German and English twins of the same
fact patterns, built from a hand-authored static rule template. No real claim was used. This bounds every number
in §5, and it bounds the degeneracy finding in particular: a corpus generated from one rule template per registry
will tend toward a single gold checklist by construction, so a plausible reading of §5.1 is that we measured the
generator rather than the domain. §5.1.1 gives the diagnostic that separates these — reachable versus observed
checklist counts, 19 against 1 on rent increase — and it points at the corpus rather than the contract.

**A generation defect.** Three cases in the `S8_nebenkosten_reclass` scenario carry "first-contact intake
messages" of 166,696 to 168,235 characters, against a median of 1,504 across the confirmatory originals. These
are the three pairs whose release set is empty, because the adjudicator prompt truncates at 9,200 characters and
their intervention sentence falls beyond the cut (§4.1). They are also in the 30-case set behind the §5.1.1
saturation figure. We report this as a corpus-generation defect rather than as a substantive property of those
cases.

### 6.2 Ground truth is model-adjudicated, by the model that wins

No lawyer reviewed any artifact in this work. The reference contracts' decisions were authored by an agent reading
the sources; the document layer came from three further authors voting two-of-three within a fixed catalogue; the
per-case live/dead/unknown marks came from three adjudicators reading the narrative.

**Those three adjudicators are three temperature-0 samples of `openai/gpt-5.6-terra`** (§4.1), which is also the
reasoner in our highest-scoring condition. This is the largest unresolved confound in the paper and we cannot
remove it with the data we hold. Two consequences, both stated in §4.1 and repeated here because a limitations
section is where a reader looks for them: every "unanimity" figure is self-consistency rather than inter-rater
reliability, so 93% on the rent-increase read is closer to a determinism check, and 66% on transfer means the
label-writing model contradicted itself on a third of decisions; and on the termination scope **no pair at all**
reaches full agreement, so the sensitivity analysis that would bound the transfer null cannot be run (§5.4). The
only bound available is that the same model grading itself on termination still produced a null.

**Removing this requires re-adjudicating the corpus under a different model family and re-running the analysis
against those labels. We did not do it, and no number in this paper substitutes for it.**

A further legal-validity risk sits on the single item the positive result rests on: the probe closes D12
(abusiveness) via the 30-day challenge deadline, while the same contract separately carries D7 (nullity for defect
of form), which is not subject to that deadline. Whether D12 should close on this probe is a question of Swiss
tenancy law that no lawyer in this project was qualified to answer (§4.2).

### 6.3 Scope of the evidence: one domain, two scopes, four reasoners

Every result comes from Swiss tenancy law. Two scopes were built and run end to end. Two further reference
contracts exist for insurance scopes (theft, legal expenses) and neither has been run through the pipeline.
Nothing here speaks to a second legal system, a second language regime, a common-law jurisdiction, or a domain
outside procedural law.

Within tenancy, the positive result rests on one scope of the two, and on two reasoners of four. Four points do
not characterise a population of reasoners, and we have no advance predictor of which side of the sign change a
given model falls on. Chain count orders the four models consistently with the sign of their result (§1.1); we
examined three proxies, so the search-adjusted chance of some proxy separating perfectly in the specified
direction is about 0.42, and this is a hypothesis rather than a finding.

**The binding limit is narrower than the scope count.** Even within the one scope where an arm scored above zero,
the metric is won by a case-ignoring constant (§5.1.2) and the leading arm's statistic is not separable from a
permutation null. So the evidence base for "this method retracts correctly anywhere" is not one scope of two — it
is zero scopes of two. What generalises from this work is the pair of diagnostics, not the system.

### 6.4 Scale, and the unit of independence

The rent-increase corpus is 50 cases in 10 scenarios of exactly 5, split 4 scenarios (20 cases) to development and
6 scenarios (30 cases) to the held-out set. Cases within a scenario are variations on one fact pattern, so all
intervals bootstrap over **scenarios**, which leaves the effective sample at 6 for the confirmatory read, 8 for
transfer and 4 for development. Nothing in this paper is a large-sample result, and the tightness of the
controlled intervals reflects the stability of the random-drop comparison within pairs, not a large number of
independent units.

The paired design assumed the intervention is minimal — that the added sentence settles the target predicate and
changes nothing else. Earlier drafts said no independent check confirmed this. **The check exists, we ran it, and
the assumption fails** (§4.2): D11 flips on 10 pairs in both directions, D1 — the scope-applicability decision,
unrelated to the 30-day clock — flips on 4 pairs in both directions, several variant sentences also supply the
notice receipt date and thereby settle D3, and ten of the 28 are in a tense that states a different proposition
from the one intended.

**The deepest limit of the unit count is not n = 6 but the effective n per cell.** Because each `b5` arm emits one
or two distinct request sets across 28 pairs (§5.3), the number of independent model decisions behind each
reported cell is approximately one. The tight intervals reflect a constant statistic under resampling, not
precision, and the bootstrap's reference population is the corpus generator rather than a population of tenancy
cases (§4.2).

### 6.5 The volume control is unplanned, and what it does not equalise

It was added after the single held-out read (§4.5) and is disclosed as an unplanned analysis. Earlier drafts also
listed "no interval on the difference between two arms' excesses exists" as a limit; those intervals are now
computed by paired cluster bootstrap and reported in §5.2 and §5.3, so that limit is discharged. Three remain: the
control equalises volume but not the achievable *ceiling*, which varies 1.4× across the four `b5` conditions; it
does not equalise *coverage*, which varies from 0.212 to 0.947; and — the limit that matters most — it says
nothing about whether a choice of documents was computed from the case, which only the permutation null of §5.1.2
can address, and on this corpus that null is not cleared.

### 6.6 Reproducibility: what is and is not in the repository

Earlier drafts of this section overstated the gaps, and we correct the record in both directions. The per-case run
records, reference adjudications and graph/proposition bundles **are** committed, 26 artifacts under
`research/casepath/artifacts/` with a SHA-256 manifest, and the multi-model runner **is** committed and pins
`temperature=0.0` with the model taken from one environment variable over an identical catalogue, scope, graph and
case set — which is better evidence for "only the model changed" than the assertion it replaces (§5.3).

What remains genuinely broken: `confirmatory_analysis.py` does not execute as committed (its path shim is defined
below its first use); `development_analysis.py` still reads raw `/tmp` paths and silently skips missing inputs,
which is the mechanism behind the A3 non-reproduction (§5.2); no run artifact records the prompt text or decoding
settings it was produced under; and there is no run log for the `gpt-5.6-terra` condition. Supporting documents in
the repository also still carry figures this paper retracts — a stale `n = 12` deepseek row, a "same prompts, same
temperature" assertion, a "zero errors anywhere" claim, and a `−0.039` where the canonical result is `−0.036` —
and should be regenerated or stamped superseded. Three committed documents state "8 of 13 nodes emitted no
obligation" where the graph artifact gives 9 of 13; the artifact is correct.

### 6.6a The scope-admission decision rests on a different contract from the results

Our scope-admission scoring evaluates `rent_increase.adjudicated-25node.json` — 25 decisions, 30 documents — and
scores the admission criterion C5 at 16/30 = 53.3%. Every result in this paper uses `rent_increase.json`: 12
decisions, 11 documents, with 6 of 11 documents required by exactly one decision. The same criterion scores the
same scope at 53.3%, 3/8 or 6/11 depending on which version and which granularity is used, so the criterion is a
function of contract granularity rather than of the scope. §1.4 makes the non-uniqueness point about
graph-versus-contract; the sharper instance is contract-versus-contract on the same scope, and the admission
decision and the results therefore rest on different artifacts.

### 6.7 Known defects in the system, unrepaired

The induced graph has no applicability gate (§3.8), so an out-of-scope case inherits the full modal document list
— the same mechanism that made a contaminated case bucket look like saturation (§4.4). Obligation coverage is
sparse: 6 obligations across 4 of 13 nodes. A re-induced graph addressing the latter exists but was excluded from
the held-out read and is unevaluated.

### 6.8 Research practice, including what went wrong

**Three** preregistration amendments and **five** errors are part of the record. Earlier drafts said two and
three; the undercount is itself an error and we correct it here. Amendment **A2** suspended the study outright —
"the confirmatory run is withheld, not run" — on the strength of the structural impossibility computation that
Error 1 describes, and set an explicit resumption condition: that the preregistration be rewritten, the changes
logged, and only then the held-out set read. A2 also named the specific method changes required before resumption — "obligation coverage across nodes, and a
node for the substantive OR 269/269a determination the graph currently omits." **Neither change was made, the
preregistration was never rewritten, A3 does not mention A2, and the held-out set was read anyway.** The re-induced
graph that would have addressed the first exists and was excluded from the read (§6.7). We record that the
resumption condition A2 set for itself was not met, and that A2 was suspended in practice by being superseded
rather than by being satisfied.

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

**Error 4 — the one that governs this revision.** We argued in the design section that a paired difference escapes
the degeneracy that saturates the static task, designed the entire dynamic evaluation on that argument, and did
not run the dynamic analogue of the oracle we had already written for the static task. The oracle wins by 3.8×
(§5.1.2). The check cost seconds, we had the artifacts, and we did not do it until a review forced the question.
The title, abstract, framing and central claim of this paper all changed as a result.

**Error 5.** We applied no multiplicity correction to the eight model×arm intervals and built the headline from
their maximum and minimum, in direct contradiction of our own preregistration's Multiplicity section, which
specifies Holm correction and an amendment log for exactly this promotion (§5.3).

We also withdraw, in this paper: a 15-case saturation measurement computed on a keyword-built bucket that an audit
showed to be one-third out of scope (§4.4); a claim that the verbatim gate's guarantee propagates to the graph,
the compiler and the product's justification prose, which the code does not support (§3.3); the word
"anti-correlated" applied to arms whose recall is identically zero (§5.3); the claim that per-scenario consistency
showed the effect was not carried by one scenario, which a constant output guarantees (§5.2); the claim that the
volume control is a structurally new kind of null (§2); and the claim that we found no precedent for a retracting
requirement checklist, which holds only within the LLM literature our sweep covered (§2).

---

## 7 Conclusion

**What this work establishes.**

Degeneracy is not escaped by scoring change instead of level. A static document-checklist task over intake
messages was uninformative on both scopes we built — one distinct ground-truth checklist across 30 and across 49
cases, a case-ignoring modal predictor at F1 1.000, five of six baselines within 0.034 F1. We designed a paired
branch-intervention task to escape that, argued in print that a paired difference is immune to the constant level,
and were wrong: the release set takes three values across 28 pairs, a 5-document core supplies 125 of 132 expected
withdrawals, and a policy that never reads the case scores +0.447 [+0.429, +0.476] against our best arm's +0.118.
A permutation null over release sets leaves the leading arm's statistic inside its own null (p = 0.21) and the
second's exactly invariant. **The strongest claim this paper can make about retraction is that we did not succeed
in measuring it, and here are the two diagnostics that would have told us sooner.**

Whatever that metric measures, it is not a property of the representation. Holding the induced graph, the
reference contract, the corpus and the code fixed and byte-identical, and changing only the interpreting model,
the same artifact scores +0.118 [+0.107, +0.125] on one reasoner and −0.078 on another. As an existence proof this
is sufficient to refute the inference a single-model evaluation of a grounded method makes, and we present it as
one counterexample rather than as a four-point survey — because each arm is a near-constant function of the case,
which puts the effective number of independent model decisions per cell at about one.

Retraction metrics require a per-arm volume control, and it has an exact closed form. Without one, the pipeline's
advantage over direct prediction reads +0.553 rather than a within-arm excess of +0.118, a 4.7-fold difference.
Estimating it by simulation, as we first did, injected error of roughly half the reported interval half-width into
intervals that never propagated it.

A constitutive verbatim gate — one that discards at authoring time rather than scoring later — caught a fabricated
statutory article that is indistinguishable by reading from the citations that verified. Artifacts that store
sources and quotes as unmapped parallel lists cannot be verified at all.

Transfer to a second scope produced no arm with signal, and the ceiling that explains it was computed from the
contract before the run.

**What this work does not establish.**

**It does not establish that any arm retracts correctly, anywhere.** This subsumes every other caveat below. On
the one scope where an arm scored above zero, the metric is won outright by a constant that ignores the case and
the arm's statistic is not separable from a permutation null. The evidence base for the method's retraction
behaviour is zero scopes of two, not one of two.

It does not demonstrate a general method. The ceiling computation correctly predicted one transfer failure; that
is one successful prediction on one scope, not a validated scope-selection criterion.

It does not establish that the ground truth is independent of the systems under test. The per-case labels were
written by `gpt-5.6-terra` at temperature 0, which is also the highest-scoring reasoner, and removing that
confound requires re-adjudication we did not run.

It does not establish a property of the domain. Two reference contracts built by the same procedure, scored
against one generated corpus, in one legal system, cannot distinguish a property of the domain from a property of
the procedure or of the corpus generator.

It does not establish that the corpus resembles real practice. Every case is synthetic.

It does not establish what governs the sign reversal. Chain count orders the four reasoners consistently with
their results; with four models that is a hypothesis, not an explanation.

It does not establish that the representation matters less than the reasoner. The representation was never varied.
What the design supports is a representation × interpreter interaction large enough to reverse a conclusion — not
a ranking of the two factors.

The practical recommendation is narrow and, we think, well supported by the measurements above — including and
especially by the measurements that cost us our headline. Before attributing a set-valued retraction result to a
representation:

1. **Score the case-ignoring constant.** Emit the modal request set and the modal withdrawal and put it in the
   same table as the arms. If it wins, the task is degenerate, and scoring change instead of level does not fix
   this — we assumed it did and were wrong by a factor of 3.8.
2. **Permute the gold.** Shuffle which unit's release set is scored against which unit's behaviour and report the
   null beside every effect. An effect inside its own permutation null is a description of a habit.
3. **Control volume within arm, in closed form.** $\mathbb{E}|W_{\text{rand}} \cap E| = |W|\,|B \cap E|/|B|$. Do
   not simulate it; the noise is comparable to the intervals.
4. **Report the degeneracy of your own arms.** Distinct request sets and distinct withdrawal sets per unit. An arm
   emitting one of each across 28 units has an effective sample size of one, whatever its confidence interval says.
5. **Report at least two interpreting models**, and name the model that wrote your ground truth.

We report these as a checklist because we failed four of the five ourselves, on committed data, and the failures
were each a few seconds of compute away from visible.

---

## Open TODOs in this draft

- ~~TODO[citation] §2 Related Work~~ — RESOLVED: written from an adversarial sweep of 24 agents; 13 opened-and-read citations. Coverage limits disclosed in §2. The uncited premise that single-model evaluation is *the norm* has been removed from the framing rather than left unsupported.
  norm in this literature is uncited and unsupported by any artifact in this repository.
- **TODO[citation: Fedlex filestore]** — §3.1.
- **TODO[number not found: per-reason drop counts for the 170-proposition extraction]** — §3.2.
- **TODO[number not found: modal-oracle F1 on the termination scope]** — §5.1.1.
- **TODO[number not found: reachable (as against observed) checklist count on the 21-decision termination
  contract]** — §5.1.1.
- ~~TODO[number not found: bootstrap interval on excess(b5) − excess(b1) and excess(b3) − excess(b1)]~~ —
  RESOLVED in §5.2 by paired cluster bootstrap on a shared resample index set: +0.178 [+0.132, +0.219] and
  +0.072 [+0.028, +0.113]. Cross-model contrasts added in §5.3.
- **TODO[code: `confirmatory_analysis.py` does not execute as committed — path shim defined below first use;
  `development_analysis.py` reads raw /tmp paths and silently skips missing inputs]** — §5, §5.2.
- **TODO[code: add the modal-withdraw oracle and the release-set permutation null to the committed analysis
  scripts, and a smoke test diffing all four scripts against CANONICAL_RESULTS.json]** — §5.1.2.
- **TODO[propagate: MODEL_GENERALITY.md, RESULTS.md, CONTRIBUTION.md and STATIC_TASK_SATURATION.md still carry
  figures and claims this paper retracts — a stale n=12 deepseek row, "same prompts, same temperature", "zero
  errors anywhere", −0.039 for −0.036, seed 20260916 for seed 7, "15 real cases", "a property of the domain"]** —
  §6.6.
- **TODO[verify: reading discipline for the rent-increase contract author against the proposition set]** — §4.1.
- **TODO[verify: termination contract's `scope_statement` (135 of 135 quotes) contradicts its audit block (91 of
  106)]** — §4.1.
- ~~TODO[verify: commit the per-case run records, reference adjudications and graph/proposition bundles]~~ —
  RESOLVED: 26 artifacts are committed under `research/casepath/artifacts/` with a SHA-256 manifest. The earlier
  caveat was stale and is withdrawn in §5 and §6.6.
- ~~TODO[verify: commit the multi-model runner]~~ — RESOLVED: `runners/multimodel.py` and `runners/conf_arms.py`
  are committed; identical catalogue, scope, graph and case set, `temperature=0.0`, model from one env var (§5.3).
- **TODO[verify: record prompt text and temperature in each run artifact, so model identity is checkable from
  outputs rather than from runner source]** — §5.3.
- **TODO[verify: per-unit error recording in the runner; no run log exists for the gpt-5.6-terra condition]** —
  §5.3.
- **TODO[design, cannot be answered with current data: re-adjudicate the corpus under a model family other than
  `gpt-5.6-terra` and re-run §5.2–§5.4 against those labels]** — §4.1, §6.2. This is the confound the paper
  concedes rather than resolves.
- **TODO[design, cannot be answered with current data: a corpus whose release set actually varies across units.
  Every claim about case-sensitive retraction is untestable until one exists]** — §5.1.2, §6.4.
