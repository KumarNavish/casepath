# Channel-Typed Evidential State: A Party's Report About a Document Is Not the Document

## Abstract

An agent that gathers evidence must decide when a fact is established. We study one failure of that
decision: the agent records a document as received when its only support is a party saying so. Telling a
model the rule does not fix it. Three strong baselines built from the same model, each carrying the rule in
its prompt, make the error 45 to 60 times over 42 episodes. We propose Channel-Typed Evidential State, in
which one model call per turn returns only local typed atoms about each source and a deterministic calculus
computes the case state, so that how much support a source can lend is fixed by the channel its bytes
arrived on rather than by its content. On a pre-registered, singly-read arena of 21 families the method
holds the correct evidence state 0.147 more often than the strongest baseline, 95% CI [0.095, 0.205],
winning 19 of 21 families; an earlier split had measured 0.148 for the same comparison as an exploratory
quantity. Single-rule ablations attribute the effect precisely, and against our own framing: the graded
channel ordering the method is named after contributes nothing measurable, while one binary rule — a
requirement is satisfied only when the returned artifact establishes it — cuts premature readiness from 11
episodes to 2 without losing a family. Two pre-registered endpoints returned nulls and we report them: a
composite utility and a symmetric readiness score both fail to separate the method from the strongest
baseline, on two independent splits. Deployed in a production claims system, the rule changes 144 of 266
evidence receipts on one surface and nothing at all on another, which tells us where it is needed.

## 1 Introduction

An agent gathering evidence for a case reads a message from the claimant: *I found the notice at home; it shows 3 March.* The agent records the notice as **received**, treats the requirement that the notice satisfies as established, stops asking for it, and reports that the file may proceed. No notice has arrived. What arrived is a party's sentence about one. We call this a *hearsay receipt*: a document booked as obtained — recorded as `received`, or as `insufficient`, when no version of it has been returned — while its only support is a report that it exists or a quotation of what it says.

The error is a typing error. The agent holds no variable that separates a claim *about* an artifact from the artifact, and that separation cannot be recovered from the text, because the two can carry the same sentence. A returned notice and a paragraph about the notice may both assert the date; an entailment check over content that accepts the first has no ground on which to reject the second. The discriminating variable — which channel the bytes arrived on — lives in metadata, outside the language the model is asked to judge. This is an argument about representations, not a measurement: the run reported here fixes one model, so we do not claim that model scale is irrelevant, only that content is the wrong place to look.

Telling the model the rule does not work either. In the confirmatory arena reported here — 82 episodes, `openai/gpt-5.4-mini` at temperature 0, three turns, at most two document requests per turn, no retries — the three baselines that let the model declare document state record 77 (`full`), 68 (`process-only`) and 137 (`direct-end-to-end`) hearsay receipts, and each is told the rule in its own system prompt; on the later decisive split of 42 episodes the same three arms record 53, 45 and 60. The two ledger arms carry it as "Source provenance supports what a paragraph reports, not authenticity, current truth, legal effect, or another time/version" and "Received requires an exact observed source reference"; the direct arm carries its own wording, "Received requires an exact supplied `source_id#paragraph_id` reference", and "a promised future completion cannot make partial content sufficient". This is consistent with the nearest literature. EnvTrustBench (arXiv:2605.08828) defines the defect — an agent treating an environment-facing claim as sufficient evidence for action — and proposes no mitigation. "Trust, but Don't Verify" (arXiv:2606.05403) finds that models judge source validity in isolation but suppress that check during multi-source synthesis, and that prompting produces blanket skepticism rather than selective discernment. If the epistemic level is decided inside the model's synthesis step, instructing the synthesis step does not fix it.

**Channel-Typed Evidential State (CTES).** CTES makes exactly one model call per turn, which returns only *local typed atoms* about each source — the requirements read from the governing instructions, per-unit attestations (does this unit's own content cover this requirement), mentions of catalogue documents (exists, possessed by the customer, promised, quoted, unreadable), and readability of returned documents. The model never emits a status, a readiness verdict or a plan. A deterministic calculus computes the case state, the requests and the readiness decision from those atoms. Its one non-standard operation is the **channel cap**: how much support a source can lend is fixed by the channel its bytes arrived on — `instruction` (0) < `party_report` (1) < `returned_artifact` (2) < `authenticated_artifact` (3) — read from metadata alone, never from the content of the text and never from the model's judgement. A party's report can direct acquisition; it cannot make a document received.

**Two claims, and they are different in kind.** The first is a *design* claim, established by reading the code rather than by experiment: in this calculus every branch that assigns a document `received` or `insufficient` is gated on that document appearing in `returned`, and `returned` is built only from units whose channel is `returned_artifact`. Zero hearsay receipts is therefore a property of the representation, it holds for any data, and — importantly — it holds with the channel cap switched off. It is not evidence that the cap works, and we do not present it as such; it is also why pre-registered hypothesis H1, which required the ablation to record at least five hearsay receipts, could never have been met and was not. The empirical half of the claim is the other side: arms that *can* make the error make it 68 to 137 times over 82 episodes while being told the rule.

**The second is a measured claim, it is pre-registered, and the comparator must be named exactly.** State accuracy — whether the agent holds the correct state for each catalogue document — was fixed as the primary endpoint of a second, decisive split before any of that split's episodes existed, and that split was read once: 42 episodes over 21 families appearing in no earlier run. Against `full` — process-first decomposition plus an explicit deterministic verification step, the strongest baseline on the composite utility and the comparator named in both pre-registrations — the family-paired difference is **+0.147 [+0.095, +0.205]**, 19 of 21 families won and 1 lost, Holm p = 0.000. Against the other two model baselines it is +0.124 [+0.067, +0.196] and +0.120 [+0.076, +0.164]; the gap over the three is therefore +0.120 to +0.147, and +0.147 is its upper end, not a worst case. An earlier confirmatory split of 82 episodes over 41 families had measured +0.148 [+0.100, +0.195], 36 of 41 families, for the same comparison as an **exploratory** quantity, with +0.128 [+0.076, +0.177] and +0.120 [+0.065, +0.174] against the other two baselines; the decisive split reproduces the headline to the third decimal as a pre-registered one. Every state-accuracy figure we quote from the 41-family split is exploratory and carries no multiplicity correction; only the 21-family figures are confirmatory. The effect survives dropping every episode in which any arm produced a failed output, on both splits (+0.135 [+0.091, +0.181], 34/6 on the confirmatory; +0.136 [+0.084, +0.189], 18/2 on the decisive), and holds at nearly the same size when the episodes are rewritten by a second model (+0.139 [+0.062, +0.218], against +0.156 [+0.075, +0.244] under the original writer on those same families) — a control covering 13 of the 41 confirmatory families, seven from heating defect and six from rent increase, with all seven termination-payment families absent, and none of the decisive split's families.

Against B5 — decompose-then-verify with the identical atoms and support derived from content, our implementation of the nearest algorithmic neighbour (ProvenanceGuard, arXiv:2606.18037) and simultaneously this method's compound ablation — state accuracy barely separates: +0.019 [−0.006, +0.044], p = 0.114 on the confirmatory split, and +0.039 [+0.006, +0.071], 12 families to 4, on the decisive one. What separates there is readiness: premature readiness falls from 24 episodes to 6, a family-paired difference of 0.220 [0.134, 0.317] with 15 families won and **none lost**, p < 0.0001, and readiness accuracy rises 0.081 [0.016, 0.155], p = 0.013. Two bounds on that claim: against `full`, readiness accuracy does not separate (−0.024 [−0.094, +0.041], p = 0.478), and CTES still declares readiness prematurely in 6 of 82 episodes, against a frozen prediction of zero. It is paid for in acquisition — 353 document requests against 285, 0.610 [0.366, 0.866] more per family, p < 0.0001 — because the agent cannot take a party's word that a document exists or is on its way. And because `channel_cap=False` changes three things at once (it removes the channel levels, believes party-reported delivery promises, and loosens requirement satisfaction from a conjunction to a disjunction), that contrast is between channel-typed and content-based support, not a one-effect isolation of the cap. The three rules were afterwards made separately settable and each given its own arm on the decisive split, and the attribution is not the one the method's name implies. Disabling the satisfaction rule alone — *a requirement is satisfied only when the returned artifact establishes it* — takes premature readiness from 2 episodes to 11, +0.214 [+0.095, +0.357] family-paired with eight families won and none lost, while the compound ablation reaches only 10, so this one binary rule carries essentially the whole compound effect. Disabling the commitments rule costs +0.033 [+0.013, +0.056] of state accuracy, p = 0.0012. Disabling the graded channel ordering costs nothing measurable at all: every paired difference against the full method is exactly zero on state accuracy, readiness accuracy, evidence acquired, premature readiness and hearsay receipts.

**The composite utility endpoint returned a negative on both splits, and we report it as one.** The confirmatory split's primary endpoint was a composite utility, `U = A − P − 0.25·B`, fixed before the run. It does not separate CTES from `full` (+0.129, 95% CI [−0.011, +0.271], 21/16, Holm p = 0.133) or from the ablation (+0.127 [−0.009, +0.273], 17/15). It does separate CTES from the two weaker model baselines, also pre-registered: +0.300 [+0.166, +0.430] over `process-only` and +0.345 [+0.194, +0.497] over `direct-end-to-end`. Of that split's four pre-registered hypotheses, three were not confirmed: H1 for the structural reason above, H4 — a sign-agreement test across writers on 13 families — by flipping between two null results (+0.048 under one writer, −0.096 under the other). The decisive split carried the composite forward for continuity only and reproduced the same non-separation, +0.135 [−0.040, +0.316]; the symmetric readiness accuracy pre-registered there to repair the composite's asymmetry also returns a null, +0.024 [−0.056, +0.119], five families won and five lost. Two endpoints fixed in advance therefore stand as negatives beside the one that was established. We claim no equivalence from the utility null: at 41 families the design detects about 0.169 at 80% power and the observed difference is +0.129. What we claim is narrower — two independent confirmatory reads now agree that this comparison does not separate, while its components move decisively in opposite directions (more evidence acquired, far fewer premature declarations, more requests) and cancel at a burden weight of 0.25. One further qualification belongs in the same breath: a zero-model arm that requests everything and never declares readiness ties CTES on evidence acquired (+0.003, p = 0.94), losing on state accuracy by 0.181 (39/2) and on 29 missed readiness decisions to CTES's 20 — and the decisive split repeats the pattern, 31.17 units of critical evidence acquired against our 31.08, no premature declarations at all, 240 requests against 161, and a state-accuracy deficit of 0.218 over 21 families of 21 — which the utility never charges, because it penalises premature readiness and does not reward correct readiness, and because on a three-turn budget with the burden term capped at four, asking for everything is nearly free.

**Contributions.**

1. **A mechanism.** Channel-typed evidential state: one model call per turn for local typed atoms only, a deterministic calculus for the case state, and a cap on attainable support fixed by channel metadata. The representation makes a hearsay receipt unrepresentable; this is established by inspecting the calculus, holds with the cap switched off, and is therefore not evidence for the cap.
2. **A measured accuracy effect, pre-registered and replicated.** +0.147 [+0.095, +0.205] in state accuracy against `full` on a singly-read 21-family split that fixed the metric as its primary endpoint in advance, 19 families won and 1 lost, Holm p = 0.000, with +0.124 and +0.120 against the other two model baselines; this reproduces the confirmatory split's exploratory +0.148 [+0.100, +0.195] over 36 of 41 families. Robust to harness failures on both splits (+0.135; +0.136) and to a second episode writer (+0.139, on 13 of 41 confirmatory families and 2 of 3 domains). Against the compound ablation the effect is small: +0.019 [−0.006, +0.044], no separation, on the confirmatory split and +0.039 [+0.006, +0.071] on the decisive one.
3. **What the cap buys, attributed to a single binary rule.** Three single-rule arms replace the compound switch. *Requiring the artifact* carries readiness: disabling it alone moves premature readiness from 2 episodes to 11, +0.214 [+0.095, +0.357], eight families won and none lost, while the compound ablation reaches only 10. *Not believing a party's delivery promise* carries a small state-accuracy effect, +0.033 [+0.013, +0.056], p = 0.0012. *The graded channel ordering the method is named after moves nothing measurable*, every paired difference exactly zero. The confirmatory split's compound contrast (premature readiness 24 → 6 episodes, family-paired 0.220 [0.134, 0.317], 15 families won and none lost, p < 0.0001; readiness accuracy +0.081 [0.016, 0.155]) is not an isolation and is not restated as one. Against `full`, readiness accuracy does not separate on either split (−0.024, p = 0.478; +0.024 [−0.056, +0.119]).
4. **Two endpoints fixed in advance that returned nulls.** The composite utility separates CTES from neither `full` nor B5, on two independent splits (+0.129 [−0.011, +0.271]; +0.135 [−0.040, +0.316]), and the symmetric readiness score pre-registered to repair it returns +0.024 [−0.056, +0.119], five families won and five lost. We report both pre-registrations, the two logged amendments, the power analysis that forced the second, the power analysis computed before the decisive run, the failure of H1 and H4, and the adversarial audit alongside the result, and we state which metric was chosen in advance on which split and which was not.
5. **Two product measurements, one positive and one null.** Replayed offline over the product's own 150-claim corpus (149 decoded; 45 claims carry any attachment), the workspace decoder books 266 receipts of which 144 — 54% — rest only on a customer-message pointer, across 85 of 149 claims; with the rule on, 122 remain. On the shipped six-role agent runtime, replayed against the one preserved external-model run (one claim, ten document requirements), the rule is a **no-op**: nothing is capped, because that workflow already scopes its single span as a source statement rather than an established fact. The rule earns its place where a model states evidence status directly from sources, and is redundant where per-span scoping already exists.

## 2 Related Work

**Benchmarks that name the failure.** EnvTrustBench (arXiv:2605.08828v2) defines evidence-grounding defects — an agent treats an environment-facing claim as sufficient evidence for action without resolving it against current evidence — and measures them across 55 generated cases, 11 scenarios, 6 backbones and 5 scaffolds; it proposes no mitigation. CTES addresses the same defect with a mechanism rather than a measurement: how much support a source can lend is fixed by the channel its bytes arrived on, so a party's report about a record can direct acquisition but can never make the record received.

**Why a prompt-level provenance rule is not enough.** "Trust, but Don't Verify: Epistemic Blind Spots in LLM Source Evaluation" (arXiv:2606.05403) finds, over six models in four families, that models assess source validity accurately in isolation but suppress that assessment during multi-source synthesis, and that prompting and oracle checklists yield blanket skepticism rather than selective discernment. We do not replicate that study; our arena is consistent with its second finding and does not test the first. Each of the three model-driven baselines permitted to declare document state is told the provenance rule in its own system prompt — the ledger prompt shared by B3 and B4 states that "Source provenance supports what a paragraph reports, not authenticity, current truth, legal effect, or another time/version" and that "Received requires an exact observed source reference", and the direct baseline carries the same rule in its own wording — and they still record 77, 68 and 137 hearsay receipts over the same 82 episodes, on a deliberately broad metric that counts a catalogue document called *received* **or** *insufficient* when no version of it has been returned. The contrast is if anything conservative: in 8 of those 82 episodes the customer paragraph verbalises the hearsay condition ("from memory, the notice is dated…"), which makes provenance legible to an arm that reads content. CTES removes the status and the support level from the synthesis step, not the model's judgement as such: the single call still rates what each unit attests, and never what any document's state is.

**Decompose-then-verify and attribution checking.** ProvenanceGuard (arXiv:2606.18037) is the nearest algorithmic neighbour — decompose the answer into atomic claims, route each to source-specific evidence, check support by entailment, compare attributions, allow or block — and FActScore-style claim decomposition shares its shape. CTES differs in the discriminating variable rather than the pipeline: content entailment cannot separate "the notice shows 3 March", reported by the customer, from the notice itself, because both entail the same proposition, while the channel is metadata outside the text. We implement this family as baseline B5 — the identical extraction call and atoms, aggregated by the same calculus with `channel_cap=False` — which is also our mechanism ablation, and it is a strong system. **The pre-registered comparison against it returns a negative:** composite utility +0.127, 95% CI [−0.009, +0.273], 17 families to 15, Holm p = 0.133, not established. State accuracy barely separates them (+0.019, CI [−0.006, +0.044], p = 0.114 on the confirmatory split, exploratory and uncorrected; +0.039 [+0.006, +0.071], 12 families to 4, on the decisive one). B5 likewise records zero hearsay receipts, but that zero is inherited, not earned: in the shared calculus every branch assigning `received` or `insufficient` requires the document to be in `returned`, which is built only from returned-artifact units and is not gated on the flag, so the zero is a property of the representation, checkable by inspection, holding for any data and with the cap switched off. It is not evidence that the cap works; our pre-registered hypothesis that B5 would make the error was unfalsifiable for exactly this reason and is withdrawn. The separation between them appears on readiness alone: premature readiness 24 episodes versus 6, family-paired 0.220 [0.134, 0.317], with strictly fewer premature declarations in 15 families, more in none and 26 tied — bought with a burden term 0.610 [0.366, 0.866] higher per family (353 requests against 285), which is why the two components nearly cancel in the composite. Finally, `channel_cap=False` is a compound switch — it changes unit level, belief in party-reported delivery commitments, and whether a requirement needs the returned artifact *and* an attestation or either — so B5 is a faithful content-based-support system but not a one-effect isolation of the cap. That experiment has since been run: the three rules were made separately settable and each given its own arm on the decisive split (§5.5, §6.2), and what separates CTES from B5 is the third of them alone. Disabling only the conjunctive satisfaction rule takes premature readiness from 2 episodes to 11, +0.214 [+0.095, +0.357] with eight families won and none lost, against the compound ablation's 10; the level gradation that distinguishes channel-typed from content-based support in the formal sense contributes nothing measurable.

**Evidence taxonomies and evidence logics.** "An Evidence Model for Agentic Processes" (arXiv:2609.08481) gives a conceptual taxonomy of 14 evidence-claim types for agentic systems without an inference procedure or experiments, and dynamic logics of evidence-based belief (van Benthem and Pacuit, 2011) supply neighbourhood semantics for belief from possibly conflicting sources together with evidence-management actions. CTES differs by operationalising a small subset of these distinctions — three graded levels above instruction, of which the arena exercises two — as a computable state update with a decision rule over requests and readiness. The gradation itself turns out to be inert: §6.2 reports that removing it changes no measured quantity, so what the arena tests of this taxonomy is a single binary distinction.

**The legal rule.** The best-evidence and hearsay rules (FRE 1002, 801) — the content of a writing is proved by the writing; an out-of-court statement is not proof of its content — are the direct ancestor of the channel cap. CTES differs by giving the rule an agent-side computational form with an acquisition consequence: a capped source does not merely fail to establish the fact, it generates the request that would.

**Belief-state acquisition planning.** CGDP (arXiv:2605.07042), InfoGatherer (arXiv:2603.05909), EC²/HEC and adaptive-cover methods plan observations against a belief state and, given a correctly specified observation model, subsume the acquisition part of this problem. CTES differs by supplying that observation model generically from channel metadata instead of assuming it per domain. Our fixed-core protocol tests this by holding the calculus, prompts, runner, evaluator and scoring byte-identical and binding only data: the third domain entered the confirmatory arena under that protocol at an adaptation cost of zero changed lines of algorithm, configuration or prompt. That is an adaptation-cost observation, not a separately powered cross-domain endpoint.

**Source credibility.** Truth-discovery methods weight sources by learned or estimated reliability. The channel cap is deliberately weaker than credibility learning: a fixed, metadata-only, monotone ceiling on attained support, never learned and never judged by the model, applied as a hard constraint on action readiness.

**The system it replaces.** The E76 decision ledger and its deterministic compiler (CasePath, 2026) are the strongest existing structure of this kind in our own product and appear as baseline B4 (`full`), pairing a process-first proposal with a verification pass. CTES differs by never consuming a model-declared status: the model supplies atoms, the calculus supplies the state, and a party-reported delivery promise raises availability without suppressing the request. The pre-registered utility comparison against B4 is also a negative (+0.129, CI [−0.011, +0.271]); the accuracy comparison that separates them is reported in §6, exploratory on the confirmatory split and pre-registered on the decisive one (+0.147 [+0.095, +0.205], 19 families of 21).

## 3 Method

### 3.1 The per-turn decision

At each turn the agent receives an actor packet $A=(S,D,C,\pi,t)$: a set of text sources $S$, a document catalogue $D$, a static category checklist $C$, its own output from the previous turn $\pi$, and the turn index with the case's awareness date. Every source contributes one or more paragraphs; a source that *is* a returned document additionally carries the catalogue id of that document. The agent must emit a state for every $d\in D$ drawn from {`missing`, `insufficient`, `received`, `pending`, `not_required`}, the subset of $D$ still outstanding, the documents it requests this turn (at most two, a limit enforced identically for every arm), a readiness bit, and an action in {`request`, `wait`, `proceed`, `clarify`}.

CTES makes exactly one model call per turn, on the same packet and through the same transport as every model baseline in §4 — temperature 0, 8000 output tokens, no reasoning parameter; the per-arm `reasoning` and `max_tokens` fields left inside the baseline request builders are dead and never reach the provider. That call returns only *local typed atoms* about individual text units. It never returns a document state, a readiness verdict, a request, or a plan. Everything the agent emits is a deterministic function of those atoms and of packet metadata. The atoms are themselves fallible model output and the calculus cannot detect a wrong one: what the design removes is the model's authority over status, not its capacity to misread a paragraph.

### 3.2 Channels

A *unit* $u$ is a (source, paragraph) pair. Its channel $\kappa(u)$ is inherited from its source and read from metadata alone: never from the content of the text, and never from the model's judgement. Channels carry the epistemic level $\lambda$ they may lend:

$$\lambda(\texttt{instruction})=0 \;<\; \lambda(\texttt{party\_report})=\lambda(\texttt{third\_party\_report})=1 \;<\; \lambda(\texttt{returned\_artifact})=2 \;<\; \lambda(\texttt{authenticated\_artifact})=3 .$$

The same scale names the support standards a requirement may demand: *reported* $=1$, *observed* $=2$, *authenticated* $=3$. In the arena, $\kappa(u)=\texttt{returned\_artifact}$ iff the source carries a delivered document id, `instruction` iff it is a governing-instruction source, and `party_report` otherwise; any unrecognised source is typed as a party report, the conservative direction, since a lower level can only withhold support.

Two disclosures about the scale, because the section is otherwise read as claiming more than the runs exercise. First, the arena instantiates two of the four levels and one of the three standards: the channel function above cannot emit `authenticated_artifact` or `third_party_report`, and on the decisive split every requirement the model emitted demanded the `observed` standard. Second, §6.2 reports that disabling the gradation by itself — taking a unit's level from its content rather than its channel, with the rest of the calculus untouched — changes state accuracy, readiness accuracy, evidence acquired, premature readiness and hearsay receipts by exactly nothing; every paired difference against the full method is zero. The operative content of the cap in every run reported here is therefore binary: a unit either is a returned artifact or it is not. We state the ordering because the calculus is defined over it and the implementation admits the other names, and we make no claim that its gradation is what earns the result. An earlier version of this work did make that claim, and it was wrong.

### 3.3 Atoms

One call returns four sets, all local:

- **Requirements** $R=\{(r,\ \mathrm{sets}_r\subseteq 2^{D},\ \mathrm{crit}_r,\ \mathrm{std}_r,\ \mathrm{act}_r)\}$, read from the governing instructions: alternative satisfying document sets, whether the requirement is critical, the support standard it demands, and whether its triggering circumstance is active.
- **Attestations** $T=\{(u,r,c)\}$ with $c\in$ {full, partial, contrary, none}: whether unit $u$'s *own content* covers requirement $r$. The model judges content only, irrespective of who wrote the unit. Only `full` and `partial` have any effect downstream; `contrary` and `none` are inert.
- **Mentions** $M=\{(u,d,\sigma)\}$ with $\sigma\in$ {exists, possessed_by_customer, held_by_third_party, promised, automatic, nonexistent, content_quoted, unreadable}: what a unit *says about* a catalogue document.
- **Readability** $Y=\{(d,y)\}$, $y\in$ {full, partial, unreadable}, for returned documents only; an absent entry defaults to `full`.

### 3.4 The calculus

Let $\mathrm{ret}(d)$ be the set of units whose channel is `returned_artifact` and whose document id is $d$; $\mathrm{ret}(d)\neq\emptyset$ is what "the document is in the workspace" means. Define

$$\mathrm{lev}(u)=\lambda(\kappa(u)),\qquad \ell(r)=\max\{\mathrm{lev}(u):(u,r,\text{full})\in T\}\ (0\text{ if none}),$$
$$\phi(d)=\max\{\mathrm{lev}(u): u\in \mathrm{ret}(d),\ (u,\cdot,\text{full})\in T\},\qquad \rho(d)=\big[\exists u\in \mathrm{ret}(d):(u,\cdot,\text{partial})\in T\big].$$

**Observation.** $\mathrm{obs}(d)\equiv \mathrm{ret}(d)\neq\emptyset\ \wedge\ y(d)=\text{full}\ \wedge\ \phi(d)\geq 2$.

**Availability.** Each $d$ takes the highest-precedence mention status under the order $\text{unreadable}<\{\text{exists},\text{content\_quoted}\}<\{\text{possessed\_by\_customer},\text{held\_by\_third\_party}\}<\text{promised}<\text{automatic}<\text{nonexistent}$, ties going to the later mention. Before that ordering, the channel rule applies to second-order reports: a `promised` or `automatic` status is demoted to `exists` unless the unit carrying it is itself a returned artifact. A party's promise therefore raises belief in the document's existence but does not suppress the request for it; the same words on a returned artifact do.

**Satisfaction.** With $\mathrm{sets}_r\neq\emptyset$,

$$\mathrm{sat}(r)\equiv\Big(\exists\,o\in \mathrm{sets}_r:\forall d\in o,\ \mathrm{obs}(d)\Big)\ \wedge\ \ell(r)\geq \mathrm{std}_r ,$$

and $\mathrm{sat}(r)=\text{false}$ when $\mathrm{sets}_r=\emptyset$. Both conjuncts are required: an artifact on file whose content does not cover the requirement does not satisfy it, and an attestation without an artifact does not either.

**Document state.** For $d\in D$ with related requirements $\mathcal{R}_d=\{r: d\in o\text{ for some }o\in\mathrm{sets}_r\}$, in order: `received` if $\mathrm{obs}(d)$; else `insufficient` if $\mathrm{ret}(d)\neq\emptyset$ and ($\rho(d)$ or $y(d)\in\{\text{partial},\text{unreadable}\}$); else `received` if $\mathrm{ret}(d)\neq\emptyset$ (a returned artifact whose content was not needed); else `not_required` if availability is `nonexistent`, or $\mathcal{R}_d=\emptyset$, or every $r\in\mathcal{R}_d$ is satisfied; else `pending` if every $r\in\mathcal{R}_d$ is inactive or availability $\in\{\text{promised},\text{automatic}\}$; else `missing`.

**Readiness and requests.** $\mathrm{ready}\equiv R\neq\emptyset\wedge\forall r$ critical and active, $\mathrm{sat}(r)$. A document is *requestable* if its state is `missing` or `insufficient`, its availability is not `promised`/`automatic`, and it was not requested on the previous turn without returning. Requests are a greedy cover of the still-unsatisfied critical active requirements: while fewer than two documents are chosen and requirements remain uncovered, pick the requestable $d$ maximising $\sum_{r}\sum_{o:\,d\in o_{\text{open}}}\big(1/|o_{\text{open}}| + 0.5\cdot[\text{possessed\_by\_customer}] - 0.75\cdot[\text{nonexistent}]\big)$ over those requirements, where $o_{\text{open}}$ are the not-yet-observed, not-yet-chosen documents of option $o$; stop when no positive gain remains. The action is `proceed` if ready, else `request` if any document was chosen, else `clarify` if $R=\emptyset$, else `wait`. (An optional redundancy rule that spends an unused slot on a disjoint alternative route exists in the implementation, is off by default, and is off in every run reported in this paper.)

**Conservative parsing.** Document ids outside the catalogue are dropped; a requirement left with no option is retained as *unsatisfiable* — never satisfied, never requested, permanently blocking readiness. Atoms naming a unit, requirement, document or status that does not exist are dropped and counted. Each rule can only remove support or availability knowledge; none can create a receipt or a readiness, and all are applied identically with and without the cap. The direction is not free: an unsatisfiable requirement buys its safety with missed readiness decisions, which §6 counts rather than discounts.

### 3.5 A hearsay receipt is not representable

The failure of interest is booking a party's report *about* a document as the document. In this representation that outcome is unreachable rather than merely discouraged. Both branches that can assign `received` and the branch that can assign `insufficient` are gated on $\mathrm{ret}(d)\neq\emptyset$, and $\mathrm{ret}$ is constructed only from units whose channel is `returned_artifact`; no model output enters that construction. Hence for any atoms whatsoever, a document with no returned unit cannot be assigned either state. The evaluator's hearsay-receipt metric counts `received` *or* `insufficient` recorded for a document not in the returned set, so the broader reading does not weaken the argument. The guarantee is conditional on the packet's channel metadata: a mis-typed source would break it, which is why an unrecognised source is typed as a party report.

We state plainly what this is and is not. It is a **design property**, checkable by inspection of the state rule, not a measurement; it holds for the ablation as well, since the channel cap appears in none of those branches. It is therefore not evidence that the cap works. The empirical companion claim — that arms permitted to express the state make the error repeatedly despite being told the provenance rule both in their prompts and in the governing-instruction paragraphs of every episode — is a measurement, and is reported in §6.

### 3.6 The ablation is a compound switch, and what replaced it

Setting `channel_cap = False` keeps the same prompt and the same extraction procedure and switches the calculus from channel-based to content-based support. An earlier description of it as a single flag was wrong; it changes three things at once:

1. $\mathrm{lev}(u)=2$ for every non-instruction unit, instead of $\lambda(\kappa(u))$;
2. party-reported delivery commitments (`promised`, `automatic`) are believed instead of demoted to `exists`;
3. $\mathrm{sat}(r)$ becomes $\big(\exists o:\forall d\in o,\ \mathrm{obs}(d)\big)\ \vee\ \ell(r)\geq\mathrm{std}_r$ — a disjunction, so an attestation alone can satisfy a requirement with no artifact on file.

The third is the structural one. The resulting arm is a faithful "decompose, then verify over content" system, and §6 reports it as that rather than as an isolation of the cap. The two arms consume the same atoms while their histories still coincide — the harness issues one physical call for byte-identical requests — and diverge thereafter only through their own prior outputs, which are part of the packet.

Because a compound switch cannot attribute, the three rules were afterwards made individually settable — `levels_from_content`, `believe_party_commitments`, `satisfy_by_attestation_alone` — each defaulting to `not channel_cap`, so `channel_cap=True/False` behaves exactly as before. That refactor touched the calculus and the runner after the confirmatory run was frozen, so it was checked rather than asserted: all 162 frozen final-turn CTES and ablation decisions replay through the refactored code with identical document states, requests, action and readiness, 162 of 162. Three single-rule arms were then pre-registered (§5.5) and read once on the decisive split.

The attribution §6.2 reports is not the one the method's name implies, and the correction belongs here rather than in a footnote. The three rules are separable and they do separate jobs. *Satisfaction* — a requirement is satisfied only when the returned artifact establishes it, never because a party attests that it would — carries the readiness discipline by itself: disabling only that conjunct takes premature readiness from 2 episodes to 11, +0.214 [+0.095, +0.357] family-paired with eight families won and none lost, while the compound ablation with all three rules off reaches only 10. *Commitments* — the demotion of a party-reported `promised` or `automatic` to `exists` — carries a small state-accuracy effect, +0.033 [+0.013, +0.056], p = 0.0012, and moves readiness not at all. *Levels* — the graded ordering $\lambda$ written above, the operation the method is named for — carries nothing measurable: with support levels read from content instead of channel and the rest of the calculus untouched, state accuracy, readiness accuracy, evidence acquired, premature readiness and hearsay receipts are all identical to the full method, every paired difference exactly zero, and the only trace is 0.048 fewer requests per family. Earlier versions of this work presented the graded lattice as the contribution. That was wrong: the load-bearing content is one binary rule about satisfaction sitting on a typed representation, and the lattice is decoration. The confirmatory split's compound ablation remains uninterpretable as an isolation of the cap, and it is not restated as one anywhere in this paper.

### 3.7 Product instantiation

The same rule is instantiated twice in a deployed system, using signal the product already records and adding no model output and no schema change. The two instantiations differ in status and in effect, and both differences are reported. On the six-role agent runtime the rule is always on: a span's channel comes from its extraction kind (`message_body` → party report; `pdf_text`, `office_text`, `utf8`, `image_metadata` → artifact; anything unknown → party report), a proposed class asserting receipt is lowered to `insufficient` unless at least one supporting span is an artifact, and the decision is recorded as an `exact_source_link` gate result on the persisted work event. On the native live workspace decoder the rule is off by default, behind `CASEPATH_EVIDENTIAL_CHANNEL_V1=1`: the channel comes from the admission receipt (`customer_message` → party report, `attachment` → artifact; later admissions of kind `export`, `source_update` or `unsolicited_source_update` → returned artifact), a `received` need without artifact support is lowered to `partial` if any support span exists and to `missing` otherwise, and the gate receipt is written into the proposal material before it is hashed and journalled. What both surfaces implement is the load-bearing rule — a receipt requires the artifact — and neither depends on the graded ordering that §6.2 shows does no measurable work. §7 reports what each instantiation does on the product's real data, including the surface on which the rule never fires at all.

## 4 Benchmark and Protocol

### 4.1 Latent-first generation

Every episode is drawn as a latent specification and only afterwards written as prose. For each `(domain, family, episode, split)` seed the generator samples the episode language; an availability profile from `{final_t1, partial_auto, partial_followup, unreadable_followup, unavailable, final_t2}` at weights `[5,3,2,2,1,2]` for each of the six catalogue documents that carry evidential weight, the seventh being fixed as the pack's irrelevant document; two to four narrative motifs, each bound to a named document; whether the domain's one conditional requirement is live; and zero to two documents whose first return is already attached to the intake packet. Three sampling guards keep the episode solvable: the trigger document of the conditional requirement is never left unavailable, every *unconditional* critical requirement keeps at least one obtainable route, and the authenticated export is forced to `final_t1` with probability 0.3 so that the alternative-route branch is exercised. The second guard does not extend to the conditional requirement, which is itself critical once activated; in one of the 82 confirmatory episodes an activated critical requirement has no obtainable route, and that episode's acquired-evidence term cannot reach one.

The motif vocabulary is the failure mode under study, written as instructions to the writer rather than as labels. `possession_report` has the customer say they hold the document; `content_quote` has them quote its content from memory; `third_party_relay` has them repeat what the manager or the bank said by telephone; `promise_automatic` has the holder promise to send it unasked. `denial_nonexistent`, `conflict`, `ambiguous_reference`, `existence_only` and `stale_then_correct` cover the remaining cases. In every one of them the paragraph is a report *about* a document rather than the document; whether the document itself has also arrived is sampled separately, and in 34 of the 82 confirmatory episodes at least one motif-bound document is also in the intake packet, so an arm cannot treat mention as proof of absence any more than as proof of receipt. Two motifs are dropped when their precondition is absent (`denial_nonexistent` without an unavailable document, `promise_automatic` without a pending one); two others, `possession_report` and `stale_then_correct`, instead rewrite the sampled availability to create theirs. Motifs are bound to documents independently and the brief carries one motif paragraph per document, so motifs that collide on a document collapse: the 82 episodes sample two, three, four and one motif in 32, 29, 17 and 4 episodes, which reach the prose as one, two, three and four motif-bearing documents in 15, 35, 28 and 4 episodes.

The writer model receives a paragraph brief carrying semantics only: what each paragraph must convey and what it must not. Writer rules forbid the meta-labels (`partial`, `final`, `hearsay`) and the document identifiers, require varied register and sentence length, and forbid revealing whether a document will turn out to be sufficient. Prose for the confirmatory split was written by `openai/gpt-5.4-mini` — the same model the arms run on. The change from `anthropic/claude-sonnet-5` is logged as Amendment 1 of the pre-registration, made because the original writer cost roughly eighteen times more per episode, and it is the most attackable choice in this section. Its direction is statable in advance: the channel cap never reads content, so a shared-family writer moves the content-reading arms rather than the method, with a sign that is not knowable beforehand. §6 reports the writer-swap control that tests it. That control was later run in full: all 21 families and all 42 episodes of the decisive split were rewritten from the identical latents by `anthropic/claude-sonnet-5`, and the primary effect moved from +0.147 to +0.162 [+0.116, +0.209], 20 of 21 families won — inside the original interval, and in the direction that makes the original estimate conservative. Each confirmatory episode was checked by a model outside the writer's family against the decisive semantic properties only — the motif semantics of each customer paragraph, the scope semantics of each return, the provenance sentence in the instructions. The check is a measurement, not a gate that was cleared: `openai/gpt-5.6-luna-pro` flags at least one property in 39 of the first 40 episodes and in all 42 of the second half, `anthropic/claude-haiku-4.5` in 24 of the first 40, and the two verifiers agree on almost nothing outside the motif rule (Jaccard 0.14 there, 0.00 on return scopes). No episode was removed: all 41 families appear with both episodes. The definitive form of this comparison uses identical latents, an identical verifier and 42 episodes per writer: on the one rule that carries cross-verifier signal the violation rate is **0.333 per episode for `gpt-5.4-mini` and 0.310 for `claude-sonnet-5`**, a difference of 0.024, while the expensive writer stays cleaner on return-scope semantics (2 flags against 10). The cheap writer is not the weaker writer. Earlier drafts quoted 0.400 against 0.385 from mismatched denominators and different latents; that comparison is superseded.

Gold labels never read that prose. The reference is computed from the latent specification and from the identities of the sources visible at the current turn; return sources carry opaque identifiers (a truncated SHA-256 of the case id and the paragraph id) so that neither the document nor its scope leaks through the identifier. A badly phrased paragraph changes what the arms see; it cannot change what is correct. Every assembled episode stores the SHA-256 of the latent it came from. The same latent specification can therefore be handed to a second writer and scored against the identical gold, which is how the writer-swap control of §6 is constructed.

### 4.2 Families and the confirmatory split

A *family* is one scenario seed with two episodes. Episodes inside a family share a domain pack and a narrative situation, so their gold is strongly correlated; the leakage probe below measures how strongly. Every comparison is therefore family-paired: utilities are averaged over episodes within a family and then over families with equal family weight, and the test statistic is the mean family-level paired difference with a 5000-sample bootstrap 95% interval.

The confirmatory split comprises 82 episodes over 41 families that appear in no earlier split: 14 heating-defect, 14 termination-and-payment and 13 rent-increase families, giving 28, 28 and 26 episodes. Forty-five episodes are in English and 37 in German; the conditional requirement is live in 42 of the 82; episodes carry two to four critical requirements (13, 40 and 29 episodes respectively); 22 episodes begin with no intake attachment, 34 with one and 26 with two. The pre-registration's second amendment describes the extension as "forty families (eighty episodes)"; the executed split, pooled from halves of 20 and 21 families, is 41 and 82. The evaluator, arm definitions, runner and analysis code were frozen at SHA-256 hashes published in the pre-registration before any confirmatory episode text existed, together with the latents of the first twenty families (`d9b4a3ba…`); the latents of the twenty-one families added under Amendment 2 carry a hash (`aa9cc4e5…`) that the published table does not list. `generator.py` is the one file that was not frozen: it moved twice, each time by appended family seeds only, with the three earlier splits and the first confirmatory half reproducing byte for byte after each change.

A second, **decisive** split was drawn later under the same generator, the same latent-first procedure and the same frozen evaluator, arms and analysis code: 42 episodes over 21 further families that appear in no earlier split, written by `openai/gpt-5.4-mini` and checked by the same two verifier families. Its pre-registration, which fixes state accuracy as the primary endpoint and adds the three single-rule ablation arms, is described in §5.5; §6 reports both splits, and every comparison on it is family-paired over the 21 families in the same way.

### 4.3 The three-turn action-conditioned harness

Each episode runs three decision turns. At every turn the arm sees the customer sources, the governing handling instructions, the document catalogue, a static category checklist, any returned documents, and its own previous plan; it emits one state per catalogue document from `{missing, insufficient, received, pending, not_required}`, a checklist, at most two requested documents, one next action from `{request, wait, proceed, clarify}`, a readiness boolean, and per-document justifications carrying `source_id#paragraph_id` references.

The environment then advances on the requests alone. Returns are action-conditioned. A first request at turn 0 for a partial-profile document delivers the incomplete version at turn 1 — an illegible one under `unreadable_followup` — and the complete version at turn 2, automatically for `partial_auto` and only against a follow-up request for `partial_followup` and `unreadable_followup`. The same first request made at turn 1 delivers the complete version at turn 2. An unavailable document returns a written statement from its holder that it was never issued. Re-requesting a document that is already received, already scheduled, or that carries no open follow-up returns nothing and is charged as repeat burden. Turn 2 is terminal.

Malformed plans are neither repaired nor retried, and one of them ends the episode for that arm. A plan that misses or duplicates a catalogue document, uses a state or action outside the vocabulary, requests more than two documents, or whose declared action and request list disagree is scored as a failure with zeros on every scored key — `hearsay_receipts` and `premature_readiness` among them — with `unnecessary_document_rate` set to 1 and one unit of burden; every remaining turn is then recorded as `unexecuted_after_plan_failure` with the same zeros and no model call. Over the confirmatory run this cost `process-only` 11 of its 246 turn-records, `full` 6, `ctes` 3, `ctes-ablation` 3 and `direct-end-to-end` 1; the zero-model controls, being deterministic, none. Those records come from 6, 3, 1, 1 and 1 distinct episodes, and 8 of the 82 episodes contain a failure by some arm. The CTES arm's single failure is raised by the calculus on the returned atoms, not by plan validation. Because a failure zeroes the error counts, the hearsay and premature-readiness totals of the arms that fail most are conservative. §6 reports a sensitivity analysis that drops all eight episodes.

### 4.4 Matched budget and byte-identical request sharing

Every model arm receives the same model, the same actor JSON, one model call per arm-turn, the same action space, the same two-request cap and the same environment, with no evaluator information in any prompt. The confirmatory run pinned `openai/gpt-5.4-mini` at temperature 0 with 8,000 output tokens and provider fallbacks disabled. The baseline prompts state the provenance rule explicitly. The prompt shared by `full` and `process-only` carries "Source provenance supports what a paragraph reports, not authenticity, current truth, legal effect, or another time/version" and "Received requires an exact observed source reference"; `direct-end-to-end`, the arm that books the most hearsay, has its own prompt carrying "Received requires an exact supplied `source_id#paragraph_id` reference; pending is not received, and a promised future completion cannot make partial content sufficient". The comparison is not against arms that were never told.

The runner buckets provider requests by canonical JSON and issues one physical call per distinct byte string; arms whose histories have not yet diverged share that call, and each pays separately once its history differs. This is primarily a cost measure, but it has a methodological consequence worth stating, in its exact scope: the CTES arm and its ablation build their request from the same system prompt and the same actor JSON, so up to the turn at which their plans first differ they read identical model output, and the onset of their divergence cannot be an artefact of sampling. After that turn their inputs differ and each pays for its own call, so the guarantee bounds the cause of the divergence, not its size. Transport parameters are symmetric by construction. The arm builder carries `reasoning`, `max_tokens` and `response_format` fields, but the runner extracts only the message list and the transport script sends every arm at the same command-line parameters; those fields never reach the provider.

### 4.5 Shortcut audit

Five zero-model controls are run through the complete episodes as a pre-registered admission gate — the arena is repaired before any method comparison unless all of them clear it: `constant` (everything not already returned is missing, request it, never declare readiness), `random`, `static-checklist` (the category intake list), `keyword-router` (lexical overlap between the source text and the catalogue descriptions), and `domain-compiler`, which knows the domain pack's critical routes and reads no text at all. A sixth probe, `family-mode`, predicts each episode's turn-0 gold from the modal gold of the *other* episodes in its family, and measures leakage directly.

Admission requires every control at family-weighted $U \le 0.35$ and turn-0 state accuracy $\le 0.75$; the pre-registered criteria add a headroom condition on the direct strong-model baseline, $U \le 0.85$, which can only be evaluated once the model arms have run and is not part of the recorded admission. All three splits are recorded as admitted. The binding quantity is the *largest* control value, since both thresholds are upper bounds. The largest control utility is $-0.050$, $-0.065$ and $-0.038$ (`constant`) on the two confirmatory halves and the frozen development split; the largest turn-0 state accuracy is $0.636$, $0.687$ and $0.696$, reached by the `family-mode` probe, with `domain-compiler` the highest of the other five at $0.600$, $0.633$ and $0.643$. On the pooled 82 episodes the best zero-model arm reaches $U = -0.058$ (`constant`) and turn-0 state accuracy $0.617$ (`domain-compiler`), and the direct baseline reaches $U = -0.321$. The decisive split was admitted under the same gate, with every zero-model control far below both thresholds.

The informative result is that the probe which comes closest to the state-accuracy ceiling is the leakage probe. `family-mode` reaches a turn-0 checklist F1 of 0.766, 0.854 and 0.914 on the three splits: family membership alone predicts most of the turn-0 checklist. That ceiling is the reason every comparison in this paper is family-paired rather than episode-paired, and the reason families, not episodes, are the unit in the power analysis.

### 4.6 Metrics

The confirmatory split's pre-registered primary endpoint — its only pre-registered endpoint — is the per-episode utility $U = A - P - 0.25B$. $A$ is read from the final turn's record and is the fraction of the episode's critical requirements the reference counts as satisfied there, where satisfaction requires that some accepted document set has actually arrived in complete form (or that the requirement has been switched off by an observed return); an arm whose episode ended early therefore scores $A = 0$. $P$ is an episode-level indicator: 1 if the arm declared readiness at any turn while the reference was not ready. $B$ is the sum over turns of unnecessary and repeat requests, capped at 4 — unnecessary counting requested documents outside the best-matching valid request route, repeat counting re-requests that the environment cannot honour.

Two properties of this endpoint matter for reading §6. It charges premature readiness but never rewards correct readiness, and $B$ saturates at four over three turns, so an arm that requests everything and never declares readiness pays almost nothing. Both facts were fixed in advance and are not repaired post hoc.

Secondary metrics are state accuracy (the fraction of the seven catalogue documents whose declared state equals the reference state, averaged over the episode's three turns before family aggregation), readiness accuracy and its two directional errors, and `hearsay_receipts`. On the confirmatory split the family-paired comparisons on these metrics are exploratory: they were not pre-registered there and carry no multiplicity correction. Two of them were then fixed in advance for the decisive split (§5.5) and are confirmatory on it: state accuracy against `full` as the primary endpoint, and readiness accuracy against `full` as the secondary, Holm-corrected across the pair. Readiness accuracy rewards a correct readiness call in both directions, which $U$ does not; it was added for exactly that reason and it returns a null.

`hearsay_receipts` counts, per turn, each catalogue document the arm records as `received` **or** `insufficient` while that document is not among those whose bytes have actually been returned. The `insufficient` disjunct is deliberate: booking a party's description of a damaged document as possession of an unreadable one is the same error as booking a receipt. This broader reading is used throughout. One fact about it belongs here rather than among the results: CTES records zero under it, and that zero is structural rather than measured. Every branch of the calculus that assigns `received` or `insufficient` is gated on the document appearing in the returned set, and that set is built only from units arriving on the `returned_artifact` channel; the channel cap appears in none of those branches. The zero is therefore a property of the state representation, provable by reading the code, it holds with the cap switched off, and it is equally guaranteed for the ablation — which is why the pre-registered mechanism hypothesis written as a contrast on this metric is withdrawn in §6. It is not evidence that the channel cap works, and no narrower reading of the metric can change it. What the metric measures is the arms that *can* make the error, and how often they make it having been told the rule.

## 5 Pre-registration and Analysis Plan

### 5.1 What was frozen

The method, the arms, the evaluator, the runner, the analysis code and the latent specification were frozen at named SHA-256 digests before any arm ran on the confirmatory split: `evidential_channel_v1.py` `d8170df1…`, `arms.py` `2916ca8c…`, `evaluation.py` `96fb4225…`, `runner.py` `9f5d8be4…`, `analyze.py` `01d6ae5e…`, and `latents.json` `d9b4a3ba…`. The first five are recorded as byte-identical to the digests held for the earlier development splits, so nothing about the method changed for this run. Two qualifications belong here rather than in a footnote. The freeze preceded the *primary* episode texts, not every text: twenty-six episodes covering thirteen of the families already existed in a second writer's version and later became the writer-swap set, as the amendment log states. And the pre-registration is internal — the ordering rests on the repository record and the named digests, not on an external registry.

One file moved. `generator.py` was extended twice — to `c6b9480d…` for the first twenty families and to `f5e00ff2…` for the twenty-one added under Amendment 2 — and both changes append family seeds and nothing else. Re-assembling the three earlier splits from the unchanged latents reproduces `cases_dev.json`, `cases_hidden.json` and `cases_transfer.json` byte for byte after each change (`eee7b099…`, `5229236a…`, `a174da29…`), and after the second change the first confirmatory half reproduces byte for byte as well (`6c54fd6c…`). An adversarial audit found the generator digest stale in an earlier draft of the pre-registration; it was corrected and both versions are now named.

### 5.2 Endpoint, statistic, and decision rules

The primary endpoint is the family-weighted composite utility `U = A − P − 0.25·B`, where `A` is the fraction of critical requirements satisfied by actually returned artifacts at the final turn, `P` is 1 if the arm declared readiness at any turn while the reference was not ready, and `B` is unnecessary-unique plus repeat requests summed over turns and capped at 4. Episode scores are averaged within a family and families are then weighted equally. The test statistic is the mean family-level paired difference with a 5000-sample bootstrap 95% interval, computed by the frozen `analyze.paired`.

Four hypotheses were fixed in advance. **H1** (mechanism): `ctes` records zero hearsay receipts and `ctes-ablation` at least five. **H2**: `U(ctes) − U(full) > 0`, established only if the interval excludes zero after Holm correction across H2 and H3. **H3**: the same for `U(ctes) − U(ctes-ablation)`. **H4** (writer robustness): on the thirteen families written twice — which, as §9.5 details, cover two of the three domains and no termination-payment family — the signs of both differences agree between writers and `ctes` records zero hearsay receipts under both; the plan adds that if any clause of H4 fails, the writer is reported as a material factor and the primary result as writer-dependent. Premature readiness, missed readiness, request counts, and the comparisons against `direct-end-to-end` and `process-only` were declared secondary and non-decisive. State accuracy, the metric Section 6 reports as the headline, is not among them: it is named as a secondary endpoint in the older frozen predictions for the development arena and in this split's plan it is not named at all. It became a primary endpoint only in the separate pre-registration of §5.5, written before the decisive split's episodes existed.

Arena admission was pre-specified in those same earlier predictions, under a heading that names the development arena: every zero-model control must score family-weighted `U ≤ 0.35` and turn-0 state accuracy `≤ 0.75`, and the direct baseline `U ≤ 0.85`, or the arena is repaired before any method comparison is run. Carried over to the confirmatory split, the five zero-model controls that appear in the result table clear the utility threshold with room — the highest of them scores −0.058 — and `direct-end-to-end` scores −0.321. Two gaps should be named rather than left for a reader to find: no turn-0 state-accuracy figure is reported for this split, and the family-mode leakage probe, the sixth control listed in the pre-registration, appears in no confirmatory arm table.

### 5.3 Two amendments, both logged before any result existed

**Amendment 1** changed the episode writer from `anthropic/claude-sonnet-5` to `openai/gpt-5.4-mini`, the same model the arms run on, and added H4 using the twenty-six Sonnet episodes (thirteen families) already written. The stated reason is cost: the original writer spent $0.1396 per episode against $0.0073, roughly nineteen times more by the logged figures — the amendment's own text says eighteen — to buy by argument what a matched writer-swap buys as evidence. The amendment declares H4 "explicitly a weaker test than H2 and H3": thirteen families suffice to catch a writer effect that reverses a sign and do not suffice to certify that no smaller effect exists.

**Amendment 2** extended the split from twenty families to forty, motivated by a power analysis computed from the earlier `gpt-5.4-mini` runs while the first forty confirmatory episodes were still executing and before any confirmatory `RESULT.json` existed. The pooled family-level standard deviation of `U(ctes) − U(full)` is 0.374, so twenty families detect a mean difference of only 0.239 at 80% power against a two-sided .05 test, while forty detect 0.169. Two things about that argument are weaker than they look. The comparison effect of "0.15 to 0.25" is the power analysis's own reading of three earlier runs whose family-mean differences were +0.205, +0.41 and −0.042, not an estimate with an interval. And the executed split ran at forty-one families and eighty-two episodes (twenty plus twenty-one), not the forty and eighty the amendment specifies; the record gives no reason for the extra family, and we report the deviation rather than round it away. The amendment notes correctly that a larger sample moves the threshold against the method, not for it. By the cost accounting, acting on the power analysis cost $3.43 in arm execution; at the frontier-model price used earlier in this project it would have cost about $49, and the underpowered answer would have had to stand. The amendment's own prospective estimates, $2.50 and $55, differ from what the accounting later recorded.

### 5.4 Single read, and what it returned

The confirmatory split was read once. After the read there was no re-run, no added episode, no change to the primary endpoint, no arm change and no writer change; episodes were added once, under Amendment 2, while the first forty were still executing and before any result existed. The pre-registration commits in advance that if H2's interval includes zero, the paper says superiority over the strongest baseline is not established and reports the mechanism result instead.

**None of the four hypotheses was confirmed or established.** H2 returned +0.129 [−0.011, +0.271], 21 families won, 16 lost, 4 tied, Holm p = 0.133; H3 returned +0.127 [−0.009, +0.273], 17 / 15 / 9, Holm p = 0.133. H1 failed on a clause that, as the audit established and Section 4 explains, no data could satisfy: no CTES-family arm can record a hearsay receipt at all, so the ablation's zero was guaranteed in advance. The information needed to see this was in our own earlier splits, which already showed the ablation at zero, and it was not read before the threshold was set. The fallback the pre-registration names therefore does not survive intact either; what stands in its place is the mechanism as a design property provable from the code, the baselines' measured error counts, and the cap's effect on readiness.

H4 failed on both clauses of its sign test. `U(ctes) − U(full)` is +0.048 under one writer and −0.096 under the other, both null. `U(ctes) − U(ctes-ablation)` is +0.417 [+0.115, +0.718] under the mini writer and −0.055 [−0.250, +0.151] under Sonnet — not a flip between two nulls, and the stronger reason to treat the writer question as open. The pre-registered consequence was to report the primary result as writer-dependent. We do not, and we name the departure: Section 6 answers the writer question on the metric that separates, where the effect is +0.156 under one writer and +0.139 under the other. That is an argument offered in place of a rule fixed in advance, and a reader is entitled to discount it accordingly.

Three further candours are owed. The bootstrap p-value and the bootstrap interval are one statistic read twice, so the Holm step across H2 and H3 is decorative rather than a second gate; neither hypothesis was near its threshold under any reading, so nothing turns on it. The extended design was sized to detect 0.169 and observed +0.129, so the negative on H2 is consistent both with a smaller true effect and with a design still underpowered for it; the follow-up pre-registration states this in as many words. And the state-accuracy result *on this split* was **not** pre-registered. It appears in the exploratory file under an explicit status line — none of those comparisons was pre-registered, and no multiplicity correction is applied across them — and on this split it is reported as explanation of the pre-registered outcome, not as a replacement for it. What makes it the paper's headline separator is not this split but the next one: a further split that re-registers state accuracy as the primary endpoint, with a symmetric readiness score and three single-rule ablations, was pre-registered before its episodes existed, has since been run and read once, and is described in §5.5 and reported in §6.

### 5.5 The decisive pre-registration

The second split has its own pre-registration, written before any of its episodes existed and before any
arm ran on it, and it was read exactly once. It exists because of §5.4: an endpoint fixed in advance
returned a negative, and the quantity that separated the arms was exploratory.

**The primary endpoint is state accuracy.** D1, fixed in advance:
`state_accuracy(ctes) − state_accuracy(full) > 0`, established if the family-paired 95% bootstrap interval
over the split's 21 families excludes zero. D2 is readiness accuracy against the same baseline, reported
two-sided; it rewards a correct readiness call in both directions, which `U` did not, and it was named as
the fix for the arm that never decides and is never punished. Holm correction is applied across {D1, D2}.
D3, the attribution — premature readiness for each of the three single-rule ablation arms against the
method — and D4, the composite utility carried forward against `full` and `ctes-ablation` for comparability
with the confirmatory split, are descriptive and gate nothing. The plan records a prediction for D3 before
the data existed: that `ctes-abl-satisfaction` would cost the most, because requiring the artifact rather
than accepting an attestation is the structurally largest of the three. §6.2 reports that it was right, and
by a wider margin than the plan expected.

**Power was computed before the run, not after.** The family-level standard deviation of the state-accuracy
difference `ctes − full` on the confirmatory split is 0.156, so 21 families detect a difference of about
0.097 at 80% power, against a confirmatory observation of 0.148 — 0.135 with failed-output episodes
dropped. This design is powered for the effect it tests, which the composite-utility design was not: there
the standard deviation was 0.374 against an effect near 0.13, and 41 families were still not enough. For D3
the corresponding standard deviation is 0.082, giving a detectable difference of about 0.051.

**What was frozen, and the one thing that moved.** `arms.py`, `evaluation.py` and `analyze.py` are
byte-identical to every earlier run, so the baselines, the scorer and the statistics did not move.
`generator.py` gained twenty-one appended family seeds and nothing else, and the three original splits
still reassemble byte for byte. The calculus and the runner did change, by the refactor of §3.6 that
replaced the compound `channel_cap` switch with three separately settable rules, each defaulting to
`not channel_cap`. That refactor is behaviour-preserving by verification rather than by assertion: all 162
frozen final-turn CTES and ablation decisions from the confirmatory runs were replayed through the
refactored calculus, and 162 of 162 reproduce the stored document states, requests, next action and
readiness flag.

**The stopping rule, fixed with the endpoint.** The split is read once; if D1's interval includes zero the
paper reports that state accuracy is not established either and the contribution reduces to the design
property plus the product measurements; no re-run, no added episode, no new metric, no arm change, and any
later change is a new and separately named run. D1's interval excluded zero — +0.147 [+0.095, +0.205], 19
families won and 1 lost, Holm p = 0.000 — and D2's included it, +0.024 [−0.056, +0.119], five families won
and five lost, Holm p = 0.58. Nothing was re-run.

**Two candours carry over from §5.4 unchanged.** The bootstrap p-value and the bootstrap interval are one
statistic read twice, so the Holm step across {D1, D2} is decorative rather than a second gate; neither
endpoint was near its threshold under any reading, so nothing turns on it. And this pre-registration is
internal exactly as the first one is: the ordering rests on the repository record and the named digests,
not on an external registry.

## 6 Results

Two independent arenas were read once each under pre-registrations fixed before their episodes existed:
a **confirmatory** split of 82 episodes over 41 families, and a **decisive** split of 42 episodes over 21
further families that no earlier split used. All numbers below are family-paired differences with
5000-sample bootstrap 95% intervals. The model is `gpt-5.4-mini` throughout, at temperature 0, with
byte-identical requests shared across arms and identical budgets.

### 6.1 The primary endpoint

The confirmatory split pre-registered a composite utility and returned a negative (§6.4). The quantity
that separated the arms there — **state accuracy**, whether the agent holds the correct state for each
document in the catalogue — was exploratory. The decisive split pre-registered it as primary.

**State accuracy, ours over the strongest baseline: +0.147, 95% CI [+0.095, +0.205], 19 of 21 families
won and 1 lost, Holm-corrected p = 0.000.**

The strongest baseline is process-first decomposition with an explicit verification step, running the same
model, given the provenance rule in its prompt in plain words, with the same token budget and the same
number of calls per turn. The confirmatory split had measured +0.148 for this comparison as an exploratory
quantity; the decisive split reproduces it to the third decimal as a pre-registered one.

| comparator | mean difference | 95% CI | won / lost | p |
|---|---|---|---|---|
| process-first + verifier (strongest) | **+0.147** | [+0.095, +0.205] | 19 / 1 | 0.0000 |
| process-first only | +0.124 | [+0.067, +0.196] | 17 / 2 | 0.0000 |
| direct end-to-end | +0.120 | [+0.076, +0.164] | 18 / 3 | 0.0000 |
| request-everything control | +0.218 | [+0.176, +0.262] | 21 / 0 | 0.0000 |
| full ablation (all rules off) | +0.039 | [+0.006, +0.071] | 12 / 4 | 0.0200 |

The same check for harness asymmetry runs on this split. The baselines produce malformed outputs and we do
not — `process-only` failed 4 times and `full` once over 1638 turn-records, every arm in our family zero —
and a failed turn is scored with zero state accuracy, which flatters us. Dropping the 3 episodes in which
any arm failed leaves **+0.136 [+0.084, +0.189], 18 families won and 2 lost** over the remaining 39
episodes. The run itself was clean: 509 requests over three turns, zero truncations, zero transport
failures, no retries.

Two further robustness checks come from the confirmatory split, where more episodes were available.
Dropping every episode in which any arm produced a malformed output — the baselines fail more often than we
do there too, 11 and 6 against 3 of 246 turn-records — moves the same comparison from +0.148 to +0.135
[+0.091, +0.181], 34 of 41 families, which is the decisive split's +0.136 to within a thousandth. Rewriting
thirteen families' episodes with a different model family gives +0.139 [+0.062, +0.218] against +0.156
[+0.075, +0.244] on the originals. The effect depends on neither the harness nor the writer.

### 6.2 Which rule does the work

The calculus was described in §3 as three rules. Each was given an arm that disables exactly that rule and
nothing else. The prediction registered in advance — that requiring the artifact would cost the most — is
confirmed, and the decomposition is sharper than we expected.

| arm | rule disabled | premature readiness (of 42) | state accuracy | readiness accuracy |
|---|---|---|---|---|
| ours | none | **2** | 0.804 | 0.897 |
| −levels | support level from content, not channel | **2** | 0.804 | 0.897 |
| −commitments | a party's delivery promise is believed | 1 | 0.771 | 0.913 |
| −satisfaction | an attestation may satisfy with no artifact | **11** | 0.796 | 0.857 |
| −all three | the compound ablation | 10 | 0.765 | 0.881 |

**The satisfaction rule carries readiness.** Disabling it alone takes premature readiness from 2 episodes
to 11: +0.214 [+0.095, +0.357] family-paired, 8 families won and none lost. The compound ablation reaches
only 10, so this single rule accounts for essentially all of it. It does not move state accuracy
(+0.008, p = 0.53).

**The commitments rule carries state accuracy**, +0.033 [+0.013, +0.056], 10 families won and 1 lost,
p = 0.0012, and does not move readiness.

**The graded channel ordering does nothing measurable.** Its arm is identical to ours on state accuracy
(+0.0000, CI [−0.007, +0.007]), on readiness accuracy, on acquired evidence, on premature readiness and on
hearsay receipts — every paired difference exactly zero. Its only trace is 0.048 fewer requests per family.

This corrects our own framing. The contribution is not a graded lattice over channels, which is what the
name advertises and what our earlier drafts claimed. It is one binary rule — *a requirement is satisfied
only when the returned artifact establishes it, never because a party attests that it would* — together
with a second about delivery promises, both sitting on a typed representation that carries the accuracy.
We found this only because an adversarial audit of our own design pointed out that the original ablation
switched three things at once.

### 6.3 The error the representation cannot make

Every arm in our family records zero hearsay receipts, on both splits. This is **structural, not measured**:
in the state rule every branch that marks a document received or insufficient requires that document to be
in the returned set, so the state cannot express the error. It holds with every rule switched off, and it
is checkable by reading §3 rather than by running anything. It is not evidence that the rules work.

The measured half is the other side. Over the decisive split's 42 episodes the arms that *can* make the
error do: 53 for the strongest baseline, 60 for direct end-to-end, 45 for process-first. All three carry
the provenance rule in their prompts.

### 6.4 What we could not establish

**The composite utility does not separate the arms.** `A − P − 0.25·B` gives +0.129 [−0.011, +0.271] on
the confirmatory split and +0.135 [−0.040, +0.316] on the decisive one. Two independent reads agree.

**Nor does a symmetric readiness score.** We introduced readiness accuracy, which rewards a correct
readiness call in both directions, precisely because the composite charges premature readiness without
rewarding correct readiness. Against the strongest baseline it returns +0.024 [−0.056, +0.119], five
families won and five lost. Our method is the more conservative of the two — 2 premature declarations
against 6 — and pays for that in missed ones.

**A trivial arm matches us on evidence acquired.** A zero-model arm that requests every outstanding
document and never declares readiness acquires 31.17 units of critical evidence against our 31.08, with no
premature declarations at all. It loses on state accuracy by 0.218, winning no families, and issues 240
requests against our 161. Any acquisition-weighted metric on a short horizon will flatter such an arm; we
report it rather than omit it.

### 6.5 Every episode rewritten by a different model

The most attackable choice in this work is that the evaluated model wrote its own episodes. All 21 families
and all 42 episodes of the decisive split were therefore rewritten from the identical latents by
`anthropic/claude-sonnet-5`, with gold, evaluator, arms and analysis untouched, and read once under a
pre-registration fixed while the rewriting was still running. All three hypotheses were confirmed.

| | result |
|---|---|
| state accuracy over the strongest baseline stays positive, interval excluding zero | +0.162 [+0.116, +0.209], **20 of 21 families**, p = 0.000 |
| the swapped estimate falls inside the original interval [+0.095, +0.205] | 0.162 against the original 0.147 |
| the satisfaction rule still carries premature readiness | 3 episodes against 8 with the rule disabled |

Against the other baselines under the new writer: +0.115 [+0.060, +0.170] over direct end-to-end, 17
families to 4; +0.202 [+0.153, +0.252] over the request-everything control, 21 to none. Hearsay receipts are
34 for the strongest baseline and 57 for direct end-to-end, against zero for every arm in our family.

The writer does not produce the result, and the original estimate was the conservative one. What this does
not establish is robustness across a writer *population*: two writers are two writers, and every arm still
runs on a single model family.

## 7 Deployment in a Production System

We integrated the channel cap into CasePath, a legal-intake system, on branch
`product/agentic-experience-20260915` at commit `fac1f4c` (integration commit `dc5dd4f`); the integration
receipt records `fac1f4c` as the product team's own accepted functional commit on that team's statement
rather than on a check we performed. Nothing in this section is pre-registered. Both pre-registrations
cover the arena only, both studies below are descriptive, and neither measures whether a capped receipt
was wrong.

The product exposes two surfaces on which an evidence state is decided, and the rule was wired into both.
On the six-role `agent_work` workflow the cap is always on and reads the channel off
`SourceSpan.extraction`: `message_body` is a party report, `utf8`, `pdf_text`, `office_text` and
`image_metadata` are artifacts, and any unrecognised extraction is treated conservatively as a party
report. Because the product already carries that signal, the integration required no new model output and
no schema change; a `received` class whose support is all party reports is lowered to `insufficient`,
which leaves the requirement live and still requested rather than closing it. The deployed check is
coarser than the method: the support set it inspects is every span the run produced, not the spans
selected for that requirement, so one artifact span anywhere in a run would un-cap every requirement in
it. On the `native_live_workspace_v1` decoder the same rule is applied to a provisional proposal before it
is hashed and journalled, behind the flag `CASEPATH_EVIDENTIAL_CHANNEL_V1=1`. That flag is an operational
kill switch and the paired off-condition for the study below; it is not the arena's `ctes-ablation`, which
changes three things at once. There the channel comes from admission metadata: `customer_message` is a
party report, `attachment` is a returned artifact, a later `export`, `source_update` or
`unsolicited_source_update` is a returned artifact, and anything unrecognised is a party report. An
unsupported `received` falls to `partial` when any supporting span exists and to `missing` otherwise. Both
deployments collapse the four-level lattice to two: neither reads `instruction` or
`authenticated_artifact`. That collapse costs nothing the arena can measure — §6.2 finds the gradation
inert — and what both surfaces implement is the rule that does the work, that a receipt requires the
artifact. Both gates are pure functions over already-decoded output and add no model call.

**Regression.** The full `casepath-api` suite was run with an identical invocation at the untouched
baseline and after integration. The baseline reports 7 failed, 917 passed, 10 skipped; with the
integration, 7 failed, 934 passed, 10 skipped. The failure sets are identical: all seven concern adapter
source-drift detection and a static byte cap in `tests/test_cli_v1.py`, all are present at `fac1f4c`, and
none touches a file this work modifies. Twenty-four tests were added — six on the `agent_work` surface,
six on the workspace gate, nine on the research kernel and three in the arena suite — of which seventeen
are net-new passes, the receipt attributing the remainder to assertions that already existed. One test
drives a real provisional proposal through the mounted route with the flag on and asserts both the lowered
state and the gate receipt in the journalled material. Wall clock went from 915.9 s to 1023.4 s; that is a
single unreplicated timing of two different test sets and is not a measurement of the rule's cost. No UI
work was required: the receipt states that the review console already renders a rejected gate with its
scope and reason, so a capped receipt is inspectable as a `Gate rejected · exact_source_link` entry beside
the console's existing caption, "A reported source statement, not an established fact." That console is
in-flight product work left uncommitted here, and no added test covers the rendering.

**Surface 1: the workspace decoder, where the rule binds.** We ran the decoder over the product's shipped
150-claim intake corpus, `synthetic-150` — 150 customer messages, 57 attachments, 207 sources — using
`openai/gpt-5.4-mini` at $1.24. The corpus is synthetic and was inspected during product development; it
is the product's operational workspace, not held-out data. Because the gate is a pure function over the
decoded proposal, one decode per claim was scored with the gate off and on, so the two conditions differ
by the gate alone. One claim failed to decode (`clm_bbe4806aa3607ee3`, `KeyError: 'need_id'`), leaving 149
scored claims and 795 evidence needs. With the gate off the decoder books 266 receipts; with it on, 122
survive, so 144 receipts, 54.1% of the total, rested only on a pointer into the customer's own message.
They are spread across 85 of the 149 claims. Recomputing the per-claim transitions, the gate's entire
effect is 144 `received`→`partial` moves; 122 receipts, 161 `partial`, 297 `missing`, 36 `pending`, 29
`uncertain`, 5 `contested` and 1 `conditional` need are unchanged. No need is ever raised, which is
structural rather than observed: only `received` is capped, so the gate is monotone downward by
construction. Three limits should be read with the 54.1%. First, it is driven by corpus composition: 104
of the 149 claims carry no attachment, and all 116 receipts booked in those claims are capped because no
artifact channel exists in them, while in the 45 claims that do carry an attachment 28 of 150 receipts are
capped. Second, the corpus has no reference states, so this is a rate at which the rule binds, not an
accuracy; and the lowering-to-`missing` branch and the `export`/`source_update` channel never fired here,
the only admission roles present being `customer_message` and `attachment`. Third, the gate writes its
receipt into every need and into the proposal envelope, so the proposal hash changes on all 149 claims and
downstream consumers keyed on it see a change even where the state does not.

**Surface 2: the six-role runtime, where the rule is a no-op.** We replayed the product's own preserved
external-model acceptance run (`work.fd6b8e0ec7af40d6826a8ff62ba1f1c8`, claim `clm_526d6c802e28b1da`,
external model `cohere/north-mini-code:free`) through the cap. Zero of ten document requirements were
capped. The Facts specialist produced a single span, from a customer message, and scoped it
`source_statement_not_established_fact` with `supports_receipt` false; the downstream roles proposed one
`insufficient` and nine `conditional`, and no role proposed `received`. There was nothing for the cap to
lower.

We report this as a result about placement, and the reading is post hoc: no prediction registered in
advance concerns either surface. The two surfaces differ in the property the method targets — the
workspace decoder asks a model to state evidence status directly from rendered sources, while the six-role
workflow attaches provenance scope to each span and, today, does not let the agent set evidence state at
all, the class being taken from the existing authority. The cap is a way of enforcing that discipline
where it is not already enforced, and it is what would keep agent-maintained state safe if that
restriction were lifted. The replay does not establish that the six-role path never needs the rule: it is
one claim, and a run that produced a single span and nine `conditional` classes is as consistent with an
evidence-poor run as with scoping that works. What it establishes is that on the product's own accepted
acceptance run the cap changed nothing, which is the claim we make.

## 8 Cost and Reproducibility

Every experiment in this paper ran on `gpt-5.4-mini` through a single provider-pinned endpoint at
temperature 0. The confirmatory phase cost $14.44 and the decisive phase $4.19, including three additional
ablation arms. The 150-claim production study cost $1.24. Episode writing costs about $0.0073 each and
episode verification about $0.011.

This is not an aside. An earlier phase of this work ran its development loop on a frontier model at $85.05,
of which roughly $49.72 was iteration the small model could have performed. The small model was not merely
cheaper: it exhibited the phenomenon far more strongly, because a weaker model makes the hearsay error more
often, and it exposed a parser brittleness the frontier model had masked. It also made a mid-course
correction affordable. When a power analysis computed from prior runs showed that 20 families could not
detect the effect in play, extending the confirmatory split to 41 families cost $3.43 to act on; at frontier
prices the same extension would have cost about $49, and an underpowered answer would have had to stand.

Every split is frozen with the sha256 of its cases, its latents, and of the method, arm, evaluator and
analysis code. Across all runs `arms.py`, `evaluation.py` and `analyze.py` are byte-identical, so the
baselines, the scorer and the statistics never moved. The generator gained family seeds between splits and
each addition was verified to leave every earlier split reassembling byte for byte. The one refactor of the
calculus, which separated a compound switch into three named rules, was verified by replaying all 162
frozen final-turn decisions from the previous splits: 162 of 162 reproduce the stored document states,
requests, action and readiness flag.

## 9 Limitations

We state these more sharply than a reader would.

**9.1 The pre-registered primary endpoint of the confirmatory split did not separate the method.** That split fixed the composite utility `U = A − P − 0.25·B` in advance. Over 41 families it returns `ctes − full` = **+0.129, 95% CI [−0.011, +0.271]** (21 wins / 16 losses, Holm p = 0.133) and `ctes − ctes-ablation` = **+0.127 [−0.009, +0.273]** (17 / 15). Neither is established, and the decisive split reproduces the first result, +0.135 [−0.040, +0.316], where `U` had been demoted to a descriptive endpoint that gates nothing. We do not read this as "more families would fix it": the components of `U` move in opposite directions — more evidence acquired and far fewer premature declarations, against more burden — and at a burden weight of 0.25 they cancel. (Against the ablation the decisive split's `U` does exclude zero, +0.189 [+0.040, +0.337]; that comparison was pre-specified as descriptive and we claim nothing from it.) The consequence for the headline is a two-part status that must not be collapsed. On the 41-family split, **+0.148 [+0.100, +0.195]** for state accuracy was **exploratory**: not pre-registered, and carrying no multiplicity correction across the exploratory family, as that artifact states in its own status field. It became a primary endpoint only by being re-registered before its episodes existed and read once on a fresh 21-family split, where it returned **+0.147 [+0.095, +0.205]**, 19 families won and 1 lost, Holm p = 0.000 across {D1, D2}. Every state-accuracy number we report from the 41-family split is exploratory; only the 21-family replication is confirmatory. (Amendment 2's text says "forty families (eighty episodes)" while §2 of the same pre-registration names twenty-one appended family seeds; the split as drawn and analysed is 41 families and 82 episodes, and every analysis uses the 41.)

**9.2 The utility function is itself part of the negative, and the metric built to replace it also returns a null.** `U` charges premature readiness and gives no credit for correct readiness, and its burden term — unnecessary plus repeat requests summed over turns — is capped at four, so an agent that requests everything and never declares runs almost free. `constant`, a zero-model arm that does exactly this, ties CTES on acquired critical evidence (+0.003, p = 0.94) and beats it on premature readiness, 6 families to 0. It loses on state accuracy by 0.181 (39 families to 2), the widest gap in that table, and it misses 29 readiness decisions to CTES's 20 — which `U` does not charge. The decisive split repeats the pattern exactly: 31.17 units acquired against 31.08, zero premature declarations, a 0.218 [0.176, 0.262] state-accuracy deficit over 21 of 21 families, and 240 requests against 161. We therefore pre-registered a symmetric readiness accuracy on that split, and **it does not separate the method from `full` either**: +0.024 [−0.056, +0.119], five families won and five lost, Holm p = 0.58. Replacing the defective metric did not convert the negative; it reproduced it on a metric that rewards a correct readiness call in both directions. We report `constant` in every table rather than drop it.

**9.3 Zero hearsay receipts is a property of the representation, not a result.** In `compute_state`, every branch assigning a document `received` or `insufficient` carries the conjunct "the document is in `returned`", and `returned` is built only from `returned_artifact` units. The zero therefore holds with the cap switched off — the ablation records zero, and so do all five zero-model controls, so the metric does not separate CTES from "ask for everything" either — and it would hold for any data. It is checkable by inspection, and it is **not** evidence that the channel cap works. It is also the broad reading of the metric, which counts a document called `received` *or* `insufficient` when no version of it was returned; the narrow reading cannot raise a zero. The measured half is the other side: over the same 82 episodes the arms that can make the error make it 77 (`full`), 68 (`process-only`) and 137 (`direct-end-to-end`) times, and 53 / 45 / 60 over the decisive split's 42, while being told the provenance rule in their prompts.

**9.4 The confirmatory ablation is a compound switch, and once decomposed the graded ordering the method is named after does nothing.** `channel_cap=False` changes three things at once: a unit's support level is taken from its text rather than its channel, a party-reported delivery promise is taken at face value, and — the structural one — a requirement can be satisfied by attestation with no artifact on file. That comparator is content-based support, not the same calculus with one flag flipped, so the confirmatory contrast attributes to the compound switch what the decomposition assigns to one rule: premature readiness 24 → 6 episodes, family-paired 0.220 [0.134, 0.317], 15 families won and none lost, bought with 0.610 [0.366, 0.866] more burden units per family, p = 0.0000. The decisive split gave each rule its own arm, after a refactor verified by replaying all 162 frozen confirmatory decisions identically. *Requiring the artifact* carries readiness: disabling it alone takes premature readiness from 2 episodes to 11, +0.214 [+0.095, +0.357], eight families won and none lost, while the compound ablation reaches only 10. *Not believing a party's delivery promise* carries state accuracy, +0.033 [+0.013, +0.056], p = 0.0012. **The graded channel ordering moves nothing measurable**: its arm is identical to the method on state accuracy (+0.0000 [−0.007, +0.007]), readiness accuracy, acquired evidence, premature readiness and hearsay receipts — every paired difference exactly zero — leaving a 0.012 edge in family-weighted `U` from marginally lower burden. The load-bearing content is one binary rule about satisfaction, not a lattice over channels, and the method's name oversold it. Finally, the readiness result is a comparison against the ablation, not against the strongest baseline: against `full`, neither premature readiness (−0.061 [−0.146, +0.024]) nor readiness accuracy (−0.024 [−0.094, +0.041], 13 families won and 16 lost) separates at all.

**9.5 The writer-swap control is narrow, drawn from one half of the split, and the arms do not move together.** Twenty-six episodes over 13 families exist in a second, independently written version — and they are 13 of the twenty families drawn before Amendment 2, so none of the 21 added afterwards is covered. They span **two of three domains** — seven heating-defect and six rent-increase families, with all termination-payment families absent because the second writer was stopped part-way through an alphabetical queue — and one writer pair. A writer effect confined to termination payment would be invisible to this control. The state-accuracy effect is stable across writers (+0.156 [+0.075, +0.244] and +0.139 [+0.062, +0.218] against `full`) and the utility comparison against `full` is null under both (+0.048 [−0.234, +0.333]; −0.096 [−0.253, +0.061]). The arms nonetheless do not shift together: `ctes − ctes-ablation` on `U` is +0.417 [+0.115, +0.718] on the mini-written episodes and −0.055 [−0.250, +0.151] on the Sonnet-written ones, where CTES ranks third of the four model arms run on the swap set (+0.183, against +0.237 for the ablation and +0.279 for `full`). We ran no test of a writer × arm interaction and claim none; the absolute scores of every arm are higher on the Sonnet set, which is a difficulty shift, but a difficulty shift does not by itself explain a paired difference that excludes zero under one writer and not the other. One writer difference runs the other way and we disclose it: eight of the 82 mini-written episodes state the hearsay condition in words where none of the 26 Sonnet-written ones does, which helps the arms that read content and shrinks the measured gap.

**9.6 One model family, one arena, one product.** Every confirmatory and decisive arm ran on a single model, `openai/gpt-5.4-mini`, at temperature 0. The earlier dev, hidden and transfer splits are development data — the hidden split was read twice, once under strict atom validation and once after the fail-soft fix, with only the CTES arms re-run on the second reading — and across those splits, under Claude Opus 5 and `gpt-5.4-mini` both, the family-paired utility interval against `full` includes zero in four of six model × split configurations. Every split comes from one synthetic arena: three domains, one latent sampler, two languages, three turns, at most two requests per turn. The product evidence is one product, one corpus, and model-dependent in the same way. On the 150-claim workspace corpus the decoder (`gpt-5.4-mini`, 149 of 150 claims scored) books 266 receipts over 795 evidence needs, of which the cap removes 144 and leaves 122, touching 85 claims; an earlier pass over 16 claims of the same corpus under `claude-opus-5` booked 8 of 113 and capped 2 — a different model *and* a different claim subset, so the two bound the receipt rate rather than isolate a model effect. That study reads document text but not page images, so an image-only attachment would be invisible to it. On the six-role runtime the rule is a **no-op** — 0 of 10 requirements capped — because that workflow already scopes spans by provenance; that measurement is one preserved run of a single claim under one external model, so it shows the rule can be redundant on that surface, not how often it is.

**9.7 Harness asymmetry.** A failed model output scores zero acquired evidence and zero state accuracy, and the baselines fail more often than the method (confirmatory: process-only 11, full 6, ctes 3 of 246 turn-records each; decisive: process-only 4, full 1, every CTES-family arm 0 over 1638 turn-records). Dropping the eight confirmatory episodes in which any arm failed moves that split's figure from +0.148 to +0.135 [+0.091, +0.181], 34 wins to 6; the same check on the decisive split moves +0.147 to +0.136 [+0.084, +0.189], 18 families to 2. About a tenth of the gap is the harness; nine tenths is not.

---

## Appendix A — Claims ledger

Every quantitative claim in this paper, with its value, its status, and the file it was read from. Path
prefixes: **R/** = `research/ctes/`, **API/** = `casepath-api/casepath_api/`, **DATA/** =
`casepath-api/arena_v1_data/`.

Status vocabulary — **PRE-REG(C)**: pre-registered in `R/PRE_REGISTRATION_CONFIRM.md` and read once on the
confirmatory split. **PRE-REG(D)**: pre-registered in `R/PRE_REGISTRATION_DECISIVE.md` and read once on the
decisive split. **EXPLORATORY**: not pre-registered, no multiplicity correction, so labelled in the source
artifact's own status field. **STRUCTURAL**: a property of the code, checkable by inspection, not a
measurement. **DESCRIPTIVE**: measured but not pre-registered and not a gate. **DEV**: development data,
carries no confirmatory weight. **RECOMPUTED**: derived from raw records, not printed in any published
table — flagged as such wherever it appears.

### A.1 Scope of the runs

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 1 | Confirmatory split size | 82 episodes, 41 families | PRE-REG(C) | R/CONFIRMATORY_DECISION.json |
| 2 | Confirmatory domain split | heating_defect 14, termination_payment 14, rent_increase 13 families | RECOMPUTED | R/runs/confirm_pooled/RESULT.json.gz |
| 3 | Turns per episode; requests per turn | 3; ≤ 2 | PRE-REG(C) | R/PRE_REGISTRATION_CONFIRM.md §4 |
| 4 | Turn-records per arm, confirmatory | 246 | RECOMPUTED | R/runs/confirm_pooled/RESULT.json.gz |
| 5 | Model, both splits | `openai/gpt-5.4-mini`, temp 0, 8000 max tokens, provider pinned, no retries, no plan repair | PRE-REG(C), PRE-REG(D) | R/PRE_REGISTRATION_CONFIRM.md §4; R/PRE_REGISTRATION_DECISIVE.md §4 |
| 6 | Confirmatory language / conditional / attachment composition | 45 EN, 37 DE; conditional live 42/82; 22/34/26 episodes with 0/1/2 intake attachments | DESCRIPTIVE | R/CONFIRMATORY_RESULT.md |
| 7 | Decisive split size | 42 episodes, 21 families, 14 episodes per domain | PRE-REG(D) | R/DECISIVE_DECISION.json; R/PRE_REGISTRATION_DECISIVE.md §3 |
| 8 | Decisive language / conditional | 23 EN, 19 DE; conditional live 20/42 | DESCRIPTIVE | R/PRE_REGISTRATION_DECISIVE.md §3 |
| 9 | Decisive turn-records, all arms | 1638 | DESCRIPTIVE | R/DECISIVE_RESULT.md §1.1 |
| 10 | Writer-swap set | 26 episodes, 13 families, 7 heating_defect + 6 rent_increase, 0 termination_payment | PRE-REG(C) (as H4) | R/CONFIRMATORY_RESULT.md §4; RECOMPUTED from run data |
| 11 | Primary utility definition | `U = A − P − 0.25·B`, B capped at 4 | PRE-REG(C) | R/PREDICTIONS.md; API/arena_v1/evaluation.py |
| 12 | Test statistic | mean family-paired difference, 5000-sample bootstrap 95% CI | PRE-REG(C) | R/PRE_REGISTRATION_CONFIRM.md §5 |

### A.2 The pre-registered negative (confirmatory split)

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 13 | H2, `U(ctes) − U(full)` | +0.129 [−0.011, +0.271], 21/16/4, Holm p = 0.133 — **not established** | PRE-REG(C) | R/CONFIRMATORY_DECISION.json |
| 14 | H3, `U(ctes) − U(ctes-ablation)` | +0.127 [−0.009, +0.273], 17/15/9, Holm p = 0.133 — **not established** | PRE-REG(C) | R/CONFIRMATORY_DECISION.json |
| 15 | H1 | `ctes` 0 hearsay, ablation 0 (needed ≥ 5) — **not confirmed, unfalsifiable by construction** | PRE-REG(C) | R/CONFIRMATORY_DECISION.json; R/AUDIT_RESPONSE.md |
| 16 | H4 writer sign agreement | vs `full` +0.048 → −0.096; vs ablation +0.417 → −0.055; signs disagree — **not confirmed** | PRE-REG(C) | R/CONFIRMATORY_DECISION.json `swap` |
| 17 | `U` vs `process-only` | +0.300 [+0.166, +0.430], 30/9/2, p = 0.0000 | PRE-REG(C) (secondary) | R/CONFIRMATORY_DECISION.json |
| 18 | `U` vs `direct-end-to-end` | +0.345 [+0.194, +0.497], 33/7/1, p = 0.0000 | PRE-REG(C) (secondary) | R/CONFIRMATORY_DECISION.json |
| 19 | `U` vs `constant` | +0.082 [−0.018, +0.183], 25/11/5, p = 0.112 — does not separate | PRE-REG(C) (secondary) | R/CONFIRMATORY_DECISION.json |
| 20 | Holm correction is decorative | bootstrap p and CI are one statistic read twice | DESCRIPTIVE | R/AUDIT_RESPONSE.md |
| 21 | Design sensitivity at 41 families | detects ≈ 0.169 at 80% power; observed +0.129 | PRE-REG(C) | R/POWER_ANALYSIS.json |

### A.3 State accuracy

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 22 | vs `full`, confirmatory | **+0.148 [+0.100, +0.195]**, 36/4/1, p = 0.0000 | **EXPLORATORY** | R/CONFIRMATORY_EXPLORATORY.json |
| 23 | vs `direct-end-to-end`, confirmatory | +0.128 [+0.076, +0.177], 32/8/1 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 24 | vs `process-only`, confirmatory | +0.120 [+0.065, +0.174], 32/8/1 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 25 | vs `constant`, confirmatory | +0.181 [+0.141, +0.214], 39/2/0 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 26 | vs `ctes-ablation`, confirmatory | +0.019 [−0.006, +0.044], 20/10/11, p = 0.114 — **no separation** | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 27 | Failure-episode sensitivity, confirmatory | +0.135 [+0.091, +0.181], 34/6/1, over 74 episodes | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 28 | **D1, vs `full`, decisive** | **+0.147 [+0.095, +0.205]**, 19/1/1, Holm p = 0.000 — **established** | **PRE-REG(D), PRIMARY** | R/DECISIVE_DECISION.json |
| 29 | vs `process-only`, decisive | +0.124 [+0.067, +0.196], 17/2 | PRE-REG(D) (secondary) | R/DECISIVE_RESULT.md §1 |
| 30 | vs `direct-end-to-end`, decisive | +0.120 [+0.076, +0.164], 18/3 | PRE-REG(D) (secondary) | R/DECISIVE_RESULT.md §1 |
| 31 | vs `constant`, decisive | +0.218 [+0.176, +0.262], 21/0 | PRE-REG(D) (secondary) | R/DECISIVE_RESULT.md §1 |
| 32 | vs `ctes-ablation`, decisive | +0.039 [+0.006, +0.071], 12/4, p = 0.020 | PRE-REG(D) (secondary) | R/DECISIVE_RESULT.md §1 |
| 33 | Failure-episode sensitivity, decisive | +0.136 [+0.084, +0.189], 18/2, over 39 episodes | PRE-REG(D) (secondary) | R/DECISIVE_RESULT.md §1.1 |
| 34 | Per-arm state accuracy, decisive | `ctes` .804, `ctes-abl-levels` .804, `ctes-abl-satisfaction` .796, `ctes-abl-commitments` .771, `ctes-ablation` .765, `direct` .684, `process-only` .680, `full` .657, `constant` .586 | PRE-REG(D) | R/DECISIVE_DECISION.json |

### A.4 Readiness and the channel cap's contribution

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 35 | Premature readiness, `ctes` vs `ctes-ablation`, confirmatory | 6 vs 24 episodes; family-paired 0.220 [0.134, 0.317], 15 won / 0 lost / 26 tied, p = 0.0000 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 36 | Readiness accuracy vs `ctes-ablation`, confirmatory | +0.081 [+0.016, +0.155], 13/6/22, p = 0.013 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 37 | Premature readiness vs `full`, confirmatory | −0.061 [−0.146, +0.024], p = 0.140 — no separation | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 38 | Readiness accuracy vs `full`, confirmatory | −0.024 [−0.094, +0.041], 13/16/12, p = 0.478 — no separation | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 39 | **D2, readiness accuracy vs `full`, decisive** | +0.024 [−0.056, +0.119], 5/5/11, Holm p = 0.58 — **null** | **PRE-REG(D)** | R/DECISIVE_DECISION.json |
| 40 | D3, `ctes-abl-satisfaction` premature readiness | 11 vs 2 episodes; +0.214 [+0.095, +0.357], 8 won / 0 lost | PRE-REG(D) | R/DECISIVE_DECISION.json |
| 41 | D3, `ctes-abl-levels` | every paired difference exactly 0.000 [0.000, 0.000], 21/21 ties, on P, state accuracy, readiness accuracy, A and hearsay | PRE-REG(D) | R/DECISIVE_DECISION.json; R/DECISIVE_RESULT.md §2 |
| 42 | D3, `ctes-abl-commitments` state-accuracy cost | +0.033 [+0.013, +0.056], 10 won / 1 lost, p = 0.0012 | PRE-REG(D) | R/DECISIVE_RESULT.md §2 |
| 43 | D3, compound ablation | +0.190 [+0.095, +0.286], 8/0/13 on premature readiness | PRE-REG(D) | R/DECISIVE_DECISION.json |
| 44 | `ctes-abl-levels` residual | 0.048 fewer requests per family, +0.012 in `U` | PRE-REG(D) (descriptive) | R/DECISIVE_RESULT.md §2 |
| 45 | Burden price vs ablation, confirmatory | 0.610 [0.366, 0.866] burden units per family, p = 0.0000; 353 vs 285 raw requests | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json; R/CONFIRMATORY_DECISION.json |
| 46 | CTES still declares prematurely | 6 of 82 episodes (confirmatory); 2 of 42 (decisive); frozen prediction P1 was zero | PRE-REG(C)/(D) | R/CONFIRMATORY_DECISION.json; R/DECISIVE_DECISION.json; R/PREDICTIONS.md |

### A.5 Hearsay receipts

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 47 | `ctes` hearsay receipts | 0, every split, every model tier | **STRUCTURAL** | API/evidential_channel_v1.py l. 188–191, 249–253 |
| 48 | Structural zero holds with the cap off | `ctes-ablation` 0; all five zero-model controls 0 | STRUCTURAL | API/evidential_channel_v1.py; R/CONFIRMATORY_DECISION.json |
| 49 | Baseline hearsay, confirmatory | `full` 77, `process-only` 68, `direct-end-to-end` 137 over 82 episodes | DESCRIPTIVE | R/CONFIRMATORY_DECISION.json |
| 50 | Baseline hearsay, decisive | `full` 53, `process-only` 45, `direct-end-to-end` 60 over 42 episodes | DESCRIPTIVE | R/DECISIVE_DECISION.json; R/DECISIVE_RESULT.md §3 |
| 51 | Metric definition is the broad reading | counts `received` **or** `insufficient` for a document not in `returned_docs` | STRUCTURAL | API/arena_v1/evaluation.py l. 480–483 |
| 52 | Baselines were told the rule | provenance sentences in `SHARED_SYSTEM_PROMPT` and the direct prompt | DESCRIPTIVE | API/arena_v1/arms.py, via R/AUDIT_RESPONSE.md |
| 53 | Hearsay per family vs `full` / `direct`, confirmatory | −0.939 [−1.293, −0.622]; −1.671 [−2.207, −1.183]; 0 families lost | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |

### A.6 The trivial arm and the metric's defect

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 54 | `constant` ties on acquired evidence | +0.003 [−0.059, +0.063], 13/14/14, p = 0.94 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 55 | `constant` beats `ctes` on premature readiness | +0.073 [+0.024, +0.134], 6 families to 0, p = 0.0024 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 56 | Missed readiness, `constant` vs `ctes` | 29 vs 20 at turn level (26 vs 18 at episode level) | **RECOMPUTED** | R/runs/confirm_pooled/RESULT.json.gz |
| 57 | `constant` request count, confirmatory | 466 vs `ctes` 353 | DESCRIPTIVE | R/CONFIRMATORY_DECISION.json |
| 58 | `constant`, decisive | A 31.167 vs 31.083; 0 premature; 240 vs 161 requests; state accuracy −0.218 over 21/21 | PRE-REG(D) (descriptive) | R/DECISIVE_DECISION.json |
| 59 | `U` never rewards correct readiness; B caps at 4 | by construction | STRUCTURAL | R/PREDICTIONS.md; API/arena_v1/evaluation.py |

### A.7 Writer swap and episode validity

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 60 | State accuracy vs `full`, mini writer | +0.156 [+0.075, +0.244], 11/1/1 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 61 | State accuracy vs `full`, Sonnet writer | +0.139 [+0.062, +0.218], 11/2/0 | EXPLORATORY | R/CONFIRMATORY_EXPLORATORY.json |
| 62 | `U` vs `full` under both writers | +0.048 [−0.234, +0.333]; −0.096 [−0.253, +0.061] — null under both | PRE-REG(C) (H4) | R/CONFIRMATORY_EXPLORATORY.json |
| 63 | `U` vs `ctes-ablation` under both writers | +0.417 [+0.115, +0.718]; −0.055 [−0.250, +0.151] | PRE-REG(C) (H4) | R/CONFIRMATORY_EXPLORATORY.json |
| 64 | Swap-set arm order | `full` +0.279, `ctes-ablation` +0.237, `ctes` +0.183, `constant` +0.112 | DESCRIPTIVE | R/CONFIRMATORY_DECISION.json `swap` |
| 65 | Arms do **not** shift uniformly across writers | 4 arms byte-identical, 2 worse, and +0.013 / +0.157 / +0.484 for the three that improve | **RECOMPUTED — contradicts `R/CONFIRMATORY_RESULT.md` §4's "level shift, not an interaction"** | R/runs/confirm_pooled/RESULT.json.gz |
| 66 | Hearsay verbalised in prose | 8 of 82 mini-written episodes, 0 of 26 Sonnet-written; direction shrinks the gap | DESCRIPTIVE | R/AUDIT_RESPONSE.md; R/CONFIRMATORY_RESULT.md §4 |
| 67 | Writer validity, rule-1 rate | **0.315/episode mini pooled over 124**; 0.400 on the first 40 alone; 0.385 Sonnet (26); 0.370 original Claude-written (46) | DESCRIPTIVE | R/WRITER_VALIDITY.json `pooled_mini_written_all_splits` |
| 68 | Rule-1 rate over all 82 confirmatory episodes | 25 violations / 82 = 0.305 per episode — not the figure the artifact prints | **RECOMPUTED** | R/CONFIRM_VERIFY_luna.json + R/CONFIRM2_VERIFY_luna.json |
| 69 | Cross-verifier agreement | Jaccard rule1 0.143, rule2 0.000, rule3 0.026, rule4 0.067 | DESCRIPTIVE | R/WRITER_VALIDITY.json |
| 70 | Verifier flag counts | luna 39/40 and 42/42; haiku 24/40; no episode removed | DESCRIPTIVE | R/CONFIRM_VERIFY_*.json |

### A.8 Harness, arena admission, failures

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 71 | Failures, confirmatory | `process-only` 11, `full` 6, `ctes` 3, `ctes-ablation` 3, `direct` 1 of 246 turn-records; controls 0 | **RECOMPUTED** (published sources quote only the first three) | R/runs/confirm_pooled/RESULT.json.gz; cf. R/CONFIRMATORY_RESULT.md |
| 72 | Failure episodes | 8 of 82, from 6/3/1/1/1 distinct episodes | RECOMPUTED | R/CONFIRMATORY_EXPLORATORY.json `sensitivity_clean_74_episodes` |
| 73 | Failures, decisive | `process-only` 4, `full` 1, every CTES-family arm 0, over 1638 turn-records | PRE-REG(D) (descriptive) | R/DECISIVE_RESULT.md §1.1 |
| 74 | Decisive run cleanliness | 509 requests, 0 truncations, 0 transport failures, no retries | DESCRIPTIVE | R/DECISIVE_RESULT.md §1.1 |
| 75 | Admission thresholds | every zero-model control `U ≤ 0.35` and t0 state accuracy `≤ 0.75`; direct `U ≤ 0.85` | PRE-REG (dev predictions) | R/PREDICTIONS.md |
| 76 | Worst control, pooled 82 episodes | `U = −0.058` (`constant`); t0 state accuracy 0.617 (`domain-compiler`); `direct` `U = −0.321` | RECOMPUTED | R/runs/confirm_pooled/RESULT.json.gz; DATA/*/SHORTCUT_AUDIT.json |
| 77 | Leakage ceiling | `family-mode` t0 checklist F1 0.766 / 0.854 / 0.914 across three splits | DESCRIPTIVE | DATA/confirm/SHORTCUT_AUDIT.json, .../confirm2/, .../frozen/ |
| 78 | Confirmatory 10-arm `U` table | `ctes` +0.024, `constant` −0.058, `ctes-ablation` −0.103, `full` −0.105, `process-only` −0.275, `direct` −0.321, `random` −0.348, `keyword-router` −0.443, `domain-compiler` −0.484, `static-checklist` −0.923 | PRE-REG(C) | R/CONFIRMATORY_DECISION.json |

### A.9 Code-provable facts

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 79 | Channel levels | instruction 0; party_report 1; third_party_report 1; returned_artifact 2; authenticated_artifact 3 | STRUCTURAL | API/evidential_channel_v1.py l. 22–28 |
| 80 | `third_party_report` exists in code, absent from METHOD.md's four-level chain | — | STRUCTURAL | API/evidential_channel_v1.py; R/METHOD.md |
| 81 | Ablation is three flags, individually settable | `levels_from_content`, `believe_party_commitments`, `satisfy_by_attestation_alone`, each defaulting to `not channel_cap` | STRUCTURAL | API/evidential_channel_v1.py l. 166–185 |
| 82 | Refactor is behaviour-preserving | 162 of 162 frozen final-turn decisions replay identically | PRE-REG(D) (verification) | R/PRE_REGISTRATION_DECISIVE.md §2 |
| 83 | Transport symmetry | `reasoning` / `max_tokens` in `build_request` never reach the provider; runner extracts only `messages` | STRUCTURAL | API/arena_v1/arms.py l. 253–254; runner.py l. 146–171; run_turn.py l. 14–15, 28 |
| 84 | Byte-identical call sharing | one physical call per distinct canonical request | STRUCTURAL | API/arena_v1/runner.py l. 160–170 |
| 85 | Conservative parse rules can only lower | catalogue-external ids dropped; optionless requirement retained as unsatisfiable | STRUCTURAL | API/evidential_channel_v1.py l. 92–101 |
| 86 | Product rule, six-role surface | `PARTY_EXTRACTIONS = {message_body}`; `ARTIFACT_EXTRACTIONS = {utf8, pdf_text, office_text, image_metadata}`; unknown → party_report; always on | STRUCTURAL | API/agent_work/evidential_channel.py |
| 87 | Product rule, workspace surface | `RETURNED_KINDS = {export, source_update, unsolicited_source_update}`; `customer_message` → party, `attachment` → artifact; `received` → `partial` / `missing`; behind a flag | STRUCTURAL | API/evidential_channel_gate_v1.py |

### A.10 Product

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 88 | Corpus | 150 claims, 150 customer messages, 57 attachments, 207 sources | DESCRIPTIVE | R/PRODUCT_INTEGRATION_RECEIPT.json |
| 89 | Decode coverage | 149 of 150 scored; 1 failure `clm_bbe4806aa3607ee3` (`KeyError: 'need_id'`) | DESCRIPTIVE | R/PRODUCT_CORPUS_STUDY_FULL150.json |
| 90 | Receipts and cap | 795 needs; 266 receipts gate-off; 122 gate-on; 144 capped = 54.1%; 85 of 149 claims affected | DESCRIPTIVE | R/PRODUCT_CORPUS_STUDY_FULL150.json |
| 91 | State transitions | the gate's entire effect is 144 `received`→`partial`; no need is ever raised | **RECOMPUTED** (published nowhere) | R/PRODUCT_CORPUS_STUDY_FULL150.json `results` |
| 92 | Composition driver | 104 of 149 claims carry no attachment and all 116 receipts booked there are capped; in the 45 with an attachment, 28 of 150 | **RECOMPUTED** | R/PRODUCT_CORPUS_STUDY_FULL150.json |
| 93 | Proposal hash changes on all 149 claims | gate writes `channel_gate` material into every need | RECOMPUTED | R/PRODUCT_CORPUS_STUDY_FULL150.json |
| 94 | Six-role replay | 10 document requirements, **0 capped**; 1 span, channel `party_report`, scope `source_statement_not_established_fact`; 1 `insufficient` + 9 `conditional`; no role proposed `received` | DESCRIPTIVE | R/EXTERNAL_RUN_REPLAY.json |
| 95 | Earlier 16-claim product pass | 113 needs, 8 receipts, 2 capped, under `claude-opus-5` — different model and subset | DESCRIPTIVE | R/PRODUCT_CORPUS_STUDY.json |
| 96 | Regression suite | baseline 7 failed / 917 passed / 10 skipped; integrated 7 failed / 934 passed / 10 skipped; failure sets identical | DESCRIPTIVE | R/PRODUCT_INTEGRATION_RECEIPT.json |
| 97 | Tests added | 24 (6 + 9 + 6 + 3), of which 17 net-new passes | DESCRIPTIVE | R/PRODUCT_INTEGRATION_RECEIPT.json |
| 98 | Wall clock | 915.9 s → 1023.4 s, single unreplicated timing of two different test sets | DESCRIPTIVE | R/PRODUCT_INTEGRATION_RECEIPT.json |
| 99 | Commits | baseline `fac1f4c`, integration `dc5dd4f`, branch `product/agentic-experience-20260915`; `fac1f4c` accepted on the product team's own statement | DESCRIPTIVE | R/PRODUCT_INTEGRATION_RECEIPT.json |

### A.11 Cost and reproducibility

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 100 | Confirmatory phase total | **$14.44** on `openai/gpt-5.4-mini` | DESCRIPTIVE | R/COST_ACCOUNTING.json `confirmatory_phase` |
| 101 | Episode writing cost per episode | $0.0073 mini (84 eps, $0.6124) vs $0.1396 Sonnet (27 eps, $3.77) | DESCRIPTIVE | R/COST_ACCOUNTING.json |
| 102 | Arm execution | confirm $2.5509, confirm2 $3.4292, swap $1.7206 | DESCRIPTIVE | R/COST_ACCOUNTING.json |
| 103 | Verification | luna-pro $0.7781 + haiku-4.5 $0.3369 over 108 episode versions | DESCRIPTIVE | R/COST_ACCOUNTING.json |
| 104 | Decisive phase total | **$4.19** including three extra ablation arms (13 arms) | DESCRIPTIVE | R/COST_ACCOUNTING.json `decisive_phase` |
| 105 | Per-run table total | $93.4194 over 1,592 calls; Opus-5 phase $85.05; mini matrices $4.946 | DESCRIPTIVE / RECOMPUTED sums | R/COST_ACCOUNTING.json `per_run` |
| 106 | Frontier ratio, one named basis | **14.3×** (matched matrices, $53.58 Opus vs $3.74 mini); other bases in the record give ≈19× and "18 to 20×" | DESCRIPTIVE | R/COST_ACCOUNTING.json |
| 107 | Confirmatory phase at frontier price | ≈ $189 | ESTIMATE in source | R/COST_ACCOUNTING.json |
| 108 | Amendment-2 extension | $3.43 actual, ≈ $49 at frontier price (amendment predicted $2.50 / $55) | DESCRIPTIVE | R/COST_ACCOUNTING.json; R/PRE_REGISTRATION_CONFIRM.md §7 |
| 109 | Product study cost | $1.2413 (FULL150) superseding $2.5102 (16 claims) | DESCRIPTIVE | R/COST_ACCOUNTING.json |
| 110 | Cost totals do not close | itemised $112.05 ($93.42 per-run + $14.44 confirmatory + $4.19 decisive) against an authoritative key usage of **$129.54**; gap $17.49 | **DISCLOSED, NOT RECONCILED** — the gap is the two product corpus studies, the aborted Sonnet writer run, provider-rejected calls and one-off exploratory calls | R/COST_ACCOUNTING.json `reconciliation` |
| 111 | Confirmatory frozen digests | `evidential_channel_v1.py` d8170df1, `arms.py` 2916ca8c, `evaluation.py` 96fb4225, `runner.py` 9f5d8be4, `analyze.py` 01d6ae5e, `latents.json` d9b4a3ba | PRE-REG(C) | R/PRE_REGISTRATION_CONFIRM.md §2 |
| 112 | Decisive frozen digests | `evidential_channel_v1.py` bb355763, `runner.py` fde1548e, `generator.py` fde5e815, `latents.json` 1d367961; arms / evaluation / analyze unchanged | PRE-REG(D) | R/PRE_REGISTRATION_DECISIVE.md §2 |
| 113 | Generator moves reproduce earlier splits byte for byte | eee7b099, 5229236a, a174da29; first confirmatory half 6c54fd6c | PRE-REG(C)/(D) | R/PRE_REGISTRATION_CONFIRM.md §2; R/PRE_REGISTRATION_DECISIVE.md §2 |
| 114 | Amendment-2 latents hash unlisted | `aa9cc4e5…` not in the published table | DISCLOSURE | R/PRE_REGISTRATION_CONFIRM.md §2 |
| 115 | Manifest describes the earlier runs | its `model` block says `claude-opus-5` / 3000 tokens; its `generator.py` digest `b9d992f0…` is a third value | **DISCLOSURE — do not cite for either evaluation split** | R/REPRODUCIBILITY_MANIFEST.json |
| 116 | Pooled `aggregate` block is stale | carries the first 40-episode run's aggregate verbatim; all published numbers come from `records` | **DISCLOSURE** | R/runs/confirm_pooled/RESULT.json.gz |

### A.12 Development data (no confirmatory weight)

| # | Claim | Value | Status | Source |
|---|---|---|---|---|
| 117 | `ctes` hearsay across all six model × split configurations | 0 in all six | DEV | R/DEV_REPORT.md |
| 118 | Utility interval vs `full` includes zero | in 4 of 6 model × split configurations | DEV | R/DEV_REPORT.md; R/FAILURE_ANALYSIS.md |
| 119 | Power inputs | pooled family SD of `U(ctes) − U(full)` = 0.374; prior means +0.205, +0.410, −0.042 | PRE-REG(C) input | R/POWER_ANALYSIS.json |
| 120 | Decisive power inputs | family SD of the state-accuracy difference 0.156 → MDE ≈ 0.097 at n = 21; for D3, SD 0.082 → MDE ≈ 0.051 | PRE-REG(D) input | R/PRE_REGISTRATION_DECISIVE.md §6 |
| 121 | Episode-verifier flag count | 40 of 46 flagged (`ok: 6`), not the 30 that `R/FAILURE_ANALYSIS.md` states | **DISCLOSURE — sources disagree** | DATA/EPISODE_VERIFICATION.json; R/WRITER_VALIDITY.json |

### A.13 Claims deliberately NOT made

| Claim we do not make | Why |
|---|---|
| That zero hearsay receipts is evidence the channel cap works | Structural; holds with the cap off (§3.5, ledger #47–48) |
| That the graded channel lattice earns the result | Its single-rule arm moves nothing measurable (#41) |
| That `U` establishes superiority over `full` | Negative on two independent splits (#13, and decisive +0.135 [−0.040, +0.316]) |
| Equivalence from the utility null | The design detects ≈ 0.169 and observed +0.129 (#21) |
| That the confirmatory ablation isolates the cap | Compound switch (#81) |
| That the method beats "ask for everything" on evidence acquired | `constant` ties (#54) |
| A writer × arm interaction test | Not run; the differential is reported descriptively (#65) |
| That the six-role surface never needs the rule | One claim, one run, one external model (#94) |
| That `METHOD.md`'s "no extra acquisition cost" holds | Contradicted by 353 vs 285 requests and #45; the clause is dropped from this paper |
| That hearsay ranged 4–80 per split | `R/METHOD.md`'s range is true only for the `direct-end-to-end` arm; the observed per-arm range is 1–80 (R/DEV_REPORT.md) |
