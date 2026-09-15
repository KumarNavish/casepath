# FINAL NOVELTY DETERMINATION

**Question audited (and nothing else):** is it known, in prior work, to CONFINE the model to local
per-source observations and DERIVE the aggregate evidence state deterministically, rather than letting the
model assert the state and then checking or repairing it?

**Verdict: NO RESIDUAL.** The operation is prior art in at least five independent lines, one of which is in
the same application domain with a *stricter* confinement than this implementation achieves. The empirical
claim is prior art too, with a proper isolating control arm this submission does not have. And the
submission's own data show the measured advantage is not located where the claimed operation is.

Written hostile, as requested. Every arXiv identifier in §1 was fetched this session; §6 lists what was not.

---

## 1. The nearest works — eleven-field comparison

| # | Work / identifier (verification) | What it does | State representation | Update rule | Decision rule | Model authority | Artifact vs report | Multi-turn acquisition | Reduction to this method | Residual after reduction |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **ATA** — arXiv:2510.16381, Peer & Stabinger, 18 Oct 2025. *Abstract + HTML fetched; insurance eval and runtime constraint confirmed verbatim.* | LLM compiles spec → human-verified symbolic KB offline; at runtime LLM does **only NER + RE**, "constrained to a predefined schema of predicates and sorts"; symbolic engine derives coverage. Eval: **insurance claims** — travel 130, electronics 240, dental 230 = 600. | Ground FOL literals over a fixed many-sorted signature + static axiom KB | Resolution over KB ∪ input literals | Entailment of `is_covered` | **Decisive, and stricter than CTES.** Runtime LLM cannot touch the rules. CTES's model re-emits `satisfying_document_sets`, `critical`, `standard`, `active` every turn. | No (confirmed absent) | No (single-shot) | Add channel as a sort argument; put `compute_state` in the KB as definite clauses; add the greedy cover (already disclaimed in NOVELTY_AUDIT §2 as "standard set-cover planning") | **Nothing.** Same domain, stricter confinement, 600 claims vs 42 episodes. |
| 2 | **EoG / "Think Locally, Explain Globally"** — arXiv:2601.17915v2, Jha et al., 25 Jan 2026. *Abstract fetched; quote verbatim.* | "an LLM performs bounded local evidence mining and labeling … while a **deterministic controller** manages traversal, state, and belief propagation to compute a minimal explanatory frontier." ITBench; 7× Majority@k entity F1 over ReAct. | Per-entity multi-valued belief L_v ∈ {Healthy, Origin, Symptom, Defer} + append-only ledger | Controller commits state; belief propagation re-activates neighbours | Controller loop; termination on queue convergence / budget | **Decisive, and iterative.** LLM emits local node labels only; never the global explanation, never termination. | No | Yes (iterative investigation; LLM proposes candidates, controller executes) | Nodes = catalogue docs + requirements; local label = CTES atoms; controller commit = `compute_state`; ActiveSet cap 2 = request plan | **Nothing.** This is the audited operation in a multi-turn evidence agent, 8 months before submission. |
| 3 | **InfoGatherer** — arXiv:2603.05909, Taranukhin et al., 6 Mar 2026. *Abstract + HTML fetched; all three quotes confirmed verbatim.* | Multi-turn document-grounded acquisition (MedQA, BarExamQA). Per-snippet DS mass elicitation; Yager fusion + Shenoy-Shafer propagation; VOI question selection; pignistic stop. | DS BBAs over an evidential network; mass on Θ = explicit ignorance | Deterministic conjunctive fusion + message passing | **Both derived.** Stop: "max_h BetP_t(h) ≥ τ_conf". Request: "We select Z_t by lexicographic maximization of (Δ_nonsp, Δ_disc)" — LLM only *phrases* the chosen question. | **Decisive over state, request AND stopping.** "we prompt the LLM to identify the subset A⊆Θ_Y supported by the snippet … and to allocate belief mass over focal sets." | **No — confirmed absent.** "No explicit source reliability weighting or discounting appears in the paper." | **Yes.** T_max=15, τ=0.85, documents + questioned party. | See §2 — single-work, near-total | **Nothing.** The only gap is Shafer discounting (1976). See §2. |
| 4 | **CALM / TOD with In-Context Learning** — arXiv:2402.12234, Bocklisch, Werkmeister, Varshneya, Nichol, 19 Feb 2024. *Abstract fetched.* | LLM translates each turn into DSL commands (SetSlot, StartFlow, Correct, Cancel); deterministic dialogue manager holds slots + flow stack and executes business logic. | Slot values + flow stack, written only by the DM | Deterministic command application | **Which collect step to ask next AND whether the flow may complete are both computed.** | **Decisive.** Model may emit only commands derived from the latest message. Never names state, completion, or the next request. | No | **Yes.** | Slots = catalogue docs; collection predicates = requirements; two guards on the predicates = the two weighted rules; batch 2 requests | **Nothing.** Holds the *entire conjunction* — lowest-level local atoms + derived per-item state + derived acquisition + derived completion — in 2024, as shipped commercial architecture. |
| 5 | **Structured Decomposition** — arXiv:2601.01609, Sadowski & Chudziak, 4 Jan 2026. *Abstract + HTML fetched; SD-Direct definition and numbers verbatim.* | LLM populates an OWL 2 ABox; SWRL reasoner derives classification. 11 models, 3 domains (incl. LegalBench **hearsay** and clinical eligibility). | ABox over an expert TBox | Deterministic SWRL inference | Class membership derived | **Decisive**, and it ran the isolating arm: **SD-Direct** = "identical entity and assertion specifications as SD … but bypasses the OWL/SWRL verification step. Instead, the LLM directly determines the final classification based on extracted predicates." | Yes — FRE 801 hearsay encoded as ontology predicates + SWRL rule | No | TBox = requirements/docs/units; SWRL clauses transliterate `compute_state` 225–264 | **Nothing — and worse.** SD 79.8 vs SD-Direct 70.1 F1, **+9.7pp, t(32)=3.71, p=0.001, d=0.65**; SD-Direct (70.1) falls *below* plain few-shot (75.2). **The submission's own empirical claim, isolated properly, is prior work.** |
| 6 | **PolicyGuard** — arXiv:2606.32004v1, Malik, Singh, Azad, 30 Jun 2026. *Abstract fetched verbatim.* | Policy text → typed relational logic rules + atom-level extraction questions; LLMs answer only local questions; symbolic evaluator applies rules. 95 guidelines × 5 NDAs. | Typed ground relational atoms + rule metadata | Symbolic evaluation of atom truth values | Compliance verdict, derived | **Decisive.** "LLMs answer these local questions using retrieved document evidence, and a symbolic evaluator applies the formal rules." | No (flagged as a limitation) | No (single-pass review) | One rulecard per requirement; `returned(D)` bound from actor metadata (= B6's one line) | **Nothing** on authority or atom/rule vocabulary. |
| 7 | **Omni-Decision** — arXiv:2607.11433, Ma et al., 13 Jul 2026. *Abstract fetched verbatim.* | Training-free multi-turn evidence-closure; per-need records (need, preferred_source, closure_level, status, filled_by, depends_on). | Confirmed evidence, conflicts, dependencies, **open evidence needs** | "Heterogeneous observations … are normalized, judged, and committed through **deterministic state updates**." | Readiness derived from state; planner picks the action from a derived actionable set | **Partial** — critic emits per-need status; reducer is sole writer | Not demonstrably | **Yes.** | Needs = requirements; keep the reducer; push status computation down one level; greedy cover over the derived set | **Nothing that counts.** Per-item acquisition state, derived readiness, multi-turn — published, and B6 already beats the method on readiness. |
| 8 | **RGE / Ontological Trust** — arXiv:2608.17718, He, Wang, Zhang, 18 Aug 2026. *Abstract fetched verbatim.* | Online monitor; Role/Goal/Evidence decomposition over trajectory prefixes; OSWorld + FinanceBench + EICU-AC; >93% Drift F1. | Factored trust state over a prefix | Deterministic updates + projections | **Deterministic intervention decisions** | **Decisive, stated as the contribution:** "RGE uses LLMs only to derive structured task and step representations; trust-state updates, projections, and intervention decisions are deterministic … rather than a single end-to-end judge verdict." | Partial (authorization scope, not delivery channel) | Prefix-online, not acquisition | Swap the schema; extend the deterministic layer with cover + request | **Nothing.** One month before submission, this sentence is the rejection, and costs a reviewer zero work. |
| 9 | **SMCalFlow / TOD as Dataflow Synthesis** — arXiv:2009.11423, Semantic Machines et al., TACL 8 (2020). *Abstract fetched.* | "A dialogue agent maps each user utterance to a program that extends this graph." Graph evaluated; unresolvable nodes surface as exceptions the agent turns into requests. | Dataflow graph extended non-destructively per turn | Deterministic topological evaluation | Evaluated result or exception node determines the response | Local per-turn emission (a program — weaker confinement than ATA) | No | **Yes** | Docs = nodes; requirement = function node; unresolvable node → exception → request; ready = goal node evaluates | **Nothing on the composition.** Local emission + derived aggregate + derived request-for-missing-information, in one 2020 paper. |
| 10 | **TrialGPT** — arXiv:2307.15051v5, Jin, Wang, Floudas et al.; Nature Communications 2024. *Abstract fetched.* | Per-**criterion** eligibility predictions with explanations; trial-level score aggregated from them. 183 patients, >75,000 annotations, 1,015 manually evaluated pairs. | Vector of per-criterion labels | Single pass | Trial score by fixed aggregation over criterion labels — and LLM-aggregation variants run as comparators | Local per-criterion judgments in the matching module | Partial (cited sentence locations) | No | Criteria = requirements; aggregation = `satisfied()` with a different combiner | **Nothing** — and it makes the axis *contested*: the criterion-level/aggregate split is 2023, and their LLM aggregation of the same labels **beat** the deterministic ones. |
| 11 | **CGDP** — arXiv:2605.07042, Kausik, Swaminathan, Kallus, 7 May 2026. *Abstract fetched verbatim.* | POMDP formalization of agentic search + two plug-ins: persistent predicate belief state, programmatic exhaustion gate. | Facts + open predicates, orchestrator-curated | Extractor appends/marks; orchestrator compresses | **"a programmatic exhaustion gate that halts unproductive search"** — stopping removed from the LLM | Mixed (extractor marks resolution) | No | **Yes** | Open predicates = requirements; invert the exhaustion gate into the readiness gate | **Nothing on readiness.** Derived stopping is published. |
| 12 | **The parse-and-solve / ISU lineage** — Logic-LM arXiv:2305.12295; LLM+P arXiv:2304.11477; LINC arXiv:2310.15164; SatLM arXiv:2305.09656; ISU/TRINDI (Larsson & Traum, NLE 6(3–4), 2000); POMDP-SDS (Young et al., Proc. IEEE 101(5), 2013) | LLM emits a local declarative fragment; a solver/planner/tracker/policy produces the aggregate **and the action**. | PDDL / FOL / SMT / slot belief state | Solver, prover, or hand-written update rules | Plan, entailment, or system act — derived | **Decisive since 2023 (and 2000 for the architecture).** LLM+P: the model emits the problem, the *planner* emits the action sequence. | No | LLM+P: yes (plans) | Requirements = constraints/goals; atoms = facts; the ≤2 cover = a MaxSMT objective, strictly better than the greedy heuristic | **Nothing.** "Confine the model to local observations and derive the aggregate" is the genus. The submission claims the genus. |

---

## 2. The strongest single reduction offered, at full strength, in its proponent's voice

> **InfoGatherer (arXiv:2603.05909) plus Shafer discounting is the whole method, and it needs no union of
> papers.**
>
> Set the hypothesis frames to Θ_D = {missing, insufficient, received, pending, not_required} per catalogue
> document and Θ_R = {satisfied, open} per requirement. **Keep the per-snippet elicitation prompt
> unchanged.** It already returns your attestations — full / contrary / partial-or-none is exactly mass on
> {satisfied}, mass on {open}, and mass on the frame, and the paper's focal-set family already permits all
> three — and it already returns your mentions as mass over Θ_D. Your `satisfied(r) = ⋁_options ⋀_d
> observed(d)` is a deterministic Boolean function of the document nodes, i.e. a degenerate conditional BBA
> on the document→requirement edges (mass 1 on {satisfied} when the conjunction holds, mass 1 on the frame
> otherwise); Shenoy-Shafer propagation computes it exactly. Your calculus is strictly *inside* DST's
> conditional-BBA parameterisation — less expressive, not new. Set τ_conf = 1.0 on a readiness node whose
> parents are the active critical requirement nodes: BetP = 1 iff all are satisfied, which **is** your
> `ready`. Replace the Deng-entropy selector with greedy set cover capped at 2 — a substitution your own
> NOVELTY_AUDIT.md §2 already labels "none claimed: standard set-cover planning."
>
> What is left to add is **one metadata field and one discount**: type each evidence unit as returned
> artifact or party report, and discount before fusion. This is not an invention; it is Shafer's discounting
> operator, textbook since 1976: m^α(A) = (1−α)m(A) for A ⊊ Θ, m^α(Θ) = (1−α)m(Θ) + α. **And "a discount is
> not a hard cap" is false.** At α = 1 the discounted BBA is *vacuous* (m(Θ)=1), and the vacuous BBA is the
> neutral element of Dempster's rule: m ⊕ vacuous = m, exactly, for any number of combinations. A hundred
> party reports move the pignistic distribution by *exactly zero*. Total discounting **is** your
> "an attestation alone cannot satisfy a requirement," with no modification to the fusion rule. An
> intermediate α on the availability variables **is** your "a party-reported promise is demoted to bare
> existence." And you do not even need the discount to get there: InfoGatherer's elicitation already offers
> the full frame Θ_Y as one of three focal forms for non-committal evidence, so the cap is a channel-metadata
> conditional on an existing code path.
>
> So: one paper, same setting (multi-turn acquisition from returned documents *and* a questioned party),
> with experiments and baselines, supplies local-only emission, derived aggregate, derived request, and
> derived stopping. Your two weight-bearing rules are the α=1 and partial-α cases of a fifty-year-old
> operator. There is no "different domain" escape and no "a union of three papers is not prior art" escape.
> And it is cited in your own CLOSEST_WORK.md, dismissed in one clause — "they do not supply the observation
> model" — which is **false**: §2.1's LLM-generated per-snippet BBAs are an observation model derived
> generically from text, which is precisely what you claim to contribute generically from channel metadata.
> A reviewer who opens your own citation list finds this in ten minutes.

*(Its two remaining flanks are closed by works on the same page: CALM holds the same conjunction in 2024
with a deterministic rather than probabilistic aggregate, and ATA holds it in the same insurance-claims
domain with a stricter confinement. The reduction does not depend on them.)*

---

## 3. Determination

**No concrete residual operation survives.** The single sentence: *confining the model to local per-source
observations and deriving the aggregate deterministically* is the defining move of ATA (same domain, 2025),
EoG (multi-turn, Jan 2026), InfoGatherer (multi-turn acquisition with derived request and derived stop, Mar
2026), CALM (2024), and the parse-and-solve / ISU lineage before all of them — and the submission's own
implementation does not even perform it, because the model emits `satisfying_document_sets`, `critical`,
`standard` and `active` every turn, and those four fields *are* the definition of satisfaction, the search
space of the planner, and the gate on readiness.

**What the paper should claim instead — a representation-and-cost result, not an authority result:**

> Asking the model for a typed, catalogue-bound, per-case representation — a requirement→document-set
> coverage map plus per-paragraph coverage and custody observations — and reading document status off that
> representation deterministically, is worth **+0.067 [+0.017, +0.119] state accuracy, 14 families to 6,
> p = 0.0088** over the same model asked for a plan and then given the obvious deterministic artifact gate,
> at a cost of **0.81 more document requests per family**. The gain is entirely in *relevance* and
> *availability* states and there is **no gain on receipt**. Two negative results accompany it: the graded
> channel lattice is **exactly inert**, and the obvious twenty-line gate (B6) eliminates the hearsay error
> completely (48 → 0) and **beats** the method on readiness accuracy at lower burden.

Position it as the multi-turn, external-acquisition analogue of arXiv:2601.01609's single-turn SD/SD-Direct
finding, with a cost accounting that paper lacks — not as a new operation. And **run the missing arm first**
(§4).

---

## 4. Acceptance test

### (a) Is the residual operation absent from the closest prior art under the same assumptions? **NO.**

Verified this session, verbatim:

- **ATA** (arXiv:2510.16381): runtime LLM "constrained to a predefined schema of predicates and sorts",
  doing only "NER and RE on unstructured claim data"; symbolic engine derives the result. Evaluated on
  **insurance claims — 130 travel, 240 electronics, 230 dental**. Same domain. *Stricter confinement than
  this submission*, because its rules are compiled once and human-verified while CTES re-derives them from
  the model every turn.
- **EoG** (arXiv:2601.17915v2): "an LLM performs bounded local evidence mining and labeling … while a
  deterministic controller manages traversal, state, and belief propagation." Multi-turn.
- **InfoGatherer** (arXiv:2603.05909): local mass elicitation per snippet; "We terminate … when
  max_h BetP_t(h) ≥ τ_conf"; "We select Z_t by lexicographic maximization of (Δ_nonsp, Δ_disc)". State,
  request and stop all derived; multi-turn; documents plus a questioned party.
- **RGE** (arXiv:2608.17718): "RGE uses LLMs **only** to derive structured task and step representations;
  trust-state updates, projections, and intervention decisions are deterministic … rather than a single
  end-to-end judge verdict." One month before submission.
- **CALM** (arXiv:2402.12234): the full conjunction — local per-message commands, derived per-slot state,
  derived next request, derived completion — in 2024.

The submission's stated foil ("decompose a model-produced answer into claims and verify each") is correctly
excluded — but every work above is on the submission's *own* side of that dichotomy. Being on the correct
side of a known dichotomy that five verified works already occupy is not novelty.

### (b) Does removing the operation remove the corresponding advantage? **NO — and this is fatal independently of prior art.**

There is no arm anywhere in the run that varies *who names the aggregate* while holding everything else
fixed. `MODEL_ARMS` contains `ctes`, `ctes-ablation`, `ctes-abl-levels`, `ctes-abl-commitments`,
`ctes-abl-satisfaction` — **all five run `compute_state`.** The ablations toggle rules *inside* the
calculus. `method` vs `B6` varies the prompt, the atom schema, the case representation, the state
derivation and the planner simultaneously, and the method issues 0.81 more requests and acquires +0.226
more critical evidence per family — more evidence in hand mechanically raises state accuracy.

**Three pieces of the author's own evidence say the advantage is not where the claimed operation is.**

1. **Removing the entire channel machinery costs almost nothing.** CONFIRMATORY_RESULT.md: `ctes` vs
   `ctes-ablation` on state accuracy is **+0.019 [−0.006, +0.044], 20/10, p = 0.1136**. The interval
   contains zero. `ctes-abl-levels` (the graded lattice) contributes **exactly zero**.

2. **Per-gold-state accuracy, recomputed independently from `runs/b6_diagnostic/RESULT.json.gz`.** Turn 0
   only, where I verified the gold document states are **byte-identical across all six arms (0 of 42 cases
   differ)**, so the comparison is like-for-like:

   | gold state | n | direct | baseline | **B6** | **method** |
   |---|---|---|---|---|---|
   | missing | 154 | 0.597 | 0.747 | 0.805 | **0.961** |
   | insufficient | 19 | 0.579 | 0.579 | 0.579 | **0.842** |
   | **received** | 23 | **1.000** | 0.957 | **0.957** | **0.870** |
   | pending | 39 | 0.205 | 0.077 | 0.077 | **0.359** |
   | not_required | 59 | 0.712 | 0.746 | 0.746 | **0.847** |
   | **ALL** | **294** | 0.599 | 0.663 | 0.694 | **0.844** |

   `received` is the **one** state the deterministic artifact rule exclusively governs (`doc_observed_ok`:
   returned ∧ readable ∧ full-attested). There the method is **20/23 against B6's 22/23 and direct
   end-to-end's 23/23** — no advantage, nominally worse. Every state where the method wins —
   missing (+24 over B6), pending (+11), not_required (+6), insufficient (+5) — is determined by atoms the
   **model** emits: `missing` vs `not_required` turns almost entirely on whether any requirement's
   `satisfying_document_sets` names the document (`compute_state` line 257–258: `elif not related:
   not_required`); `pending` turns on model-emitted `promised`/`automatic` mentions and the model's `active`
   flag (line 261); `insufficient` on model-emitted readability and partial coverage.

3. **The advantage does not survive the horizon.** At turn 2 the method is **0.643** overall against direct
   end-to-end's **0.721** — below the arm it is supposed to dominate. (Trajectories diverge after turn 0, so
   this is directional, not paired; it is still the wrong sign.)

**Conclusion of the test.** Removing the model's authority to name the aggregate is *not* what buys the
+0.067. What buys it is asking the model for a richer, typed, catalogue-bound case representation — which is
the model *asserting aggregate-bearing structure*, the opposite of the claim. The operation fails limb (a)
against five verified works and limb (b) against the author's own numbers.

**Do this before submission:** build **B7** — hand the CTES atom schema to the strongest baseline and let
the **model** compute states, readiness and requests from its own atoms (the SD-Direct analogue). If B7
captures most of the gap, there is no paper. If it does not, you have the isolating result — and you must
then present it as a replication of arXiv:2601.01609 in a multi-turn acquisition setting, citing
arXiv:2307.15051 as the counterexample that makes the question live.

---

## 5. Recommended name

The old name foregrounded the channel typing. **`ctes-abl-levels` ablates to exactly zero.** It must not be
reused, in any variant, including as a subtitle.

The surviving, measured operation is: *the model induces a per-case, catalogue-bound map of which document
sets can discharge which requirement, plus local per-paragraph coverage and custody observations; document
status is then read off that map.* The effect lives in coverage (relevance: `missing` / `not_required`) and
custody (availability: `pending`). Name that, and nothing else.

**Recommended: Coverage-and-Custody State Induction (CCSI).**
Both halves name a component the data credits: coverage (+24 `missing`, +6 `not_required` over B6) and
custody (+11 `pending`). It claims no channel, no lattice, and no authority removal — so nothing in the name
is falsified by an ablation or owned by ATA, EoG, InfoGatherer or CALM.

Alternatives:
- **Requirement-Coverage Induction (RCI)** — narrower, foregrounds only the requirement→document map, the
  single largest contributor. Safest if the custody column is dropped.
- **Catalogue-Bound Evidence Typing (CBET)** — foregrounds that atoms are bound to a fixed document
  catalogue rather than free-form, which is also the mechanism behind the 0-vs-5 output-failure result.

Do **not** use any name containing "channel", "evidential channel", "provenance", "derived state",
"deterministic state construction", or "the model never states the aggregate": the first two are inert, and
the last three are owned by RGE, PolicyGuard, EoG and the 2000 ISU architecture respectively.

---

## 6. Citations to verify

**Verified by me this session** (abstract and/or HTML fetched; quotes in §1–§4 are verbatim):
2510.16381, 2601.17915, 2603.05909, 2601.01609, 2606.32004, 2607.11433, 2608.17718, 2608.24667, 2605.07042,
2605.12694, 2402.12234, 2307.15051, 2009.11423.

**Could NOT confirm — do not cite, or verify first:**

| Claim | Status |
|---|---|
| 2605.12694's stratified ordering "model ⊑K located ⊑K applicable ⊑K corroborated ⊑K checked", and whether it has an implementation/evaluation | Abstract fetched; ordering **not** visible on the abs page. Two auditors report it verbatim from HTML. Verify before citing as a published provenance lattice. |
| 2607.11433's `ready(S_t) = (U_t=∅) ∧ complete(F_t) ∧ (C_t=∅)` and "All non-reducer modules are state readers or event producers" | Abstract confirms "deterministic state updates"; the formula and the quote are **not** on the abs page. Two auditors report them from the full text. |
| 2009.11423's exception→request quotes ("When an exception occurs, the generation model is invoked on the exceptional node") | Abstract confirms the program/graph mapping only. Verify the Database/exception semantics before quoting. |
| 2608.24667's computed MISSING set and who decides termination | Abstract confirms frozen verifier, verbatim spans with polarity, deterministic structural validator. MISSING set **not** confirmed. |
| TrialGPT NDCG@10 figures (≈0.725 LLM aggregation vs 0.393–0.610 linear) | From one auditor's automated read of PMC10418514. **Architecture confirmed; numbers not.** Do not quote the numbers without checking the tables. |
| 1604.04562 Database Operator verbatim ("6-bin 1-hot encoding", entity pointer) | Reported verbatim by one auditor; not re-fetched here. Load-bearing for the claim that TOD already has an artifact/report asymmetry — verify. |
| GSAR 2604.23366 claim C2 and the n=50 / n=200 weight-uniform numbers | Not re-fetched. **Do not cite GSAR as a replicated null for the inert lattice** — one auditor reports a *positive* effect at n=200. |
| 2606.25622 "Probability Isolation" | Phrase came from a search snippet, not the paper. Cite only "Decoupled Reasoning Pipeline", and only after fetching. |
| ACL Anthology / journal items: W04-3240 (Cohen, Carvalho & Mitchell 2004), W13-4067 (Wang & Lemon 2013), P94-1001 (Traum & Allen 1994), Larsson & Traum NLE 6(3–4) 2000, Young et al. Proc. IEEE 101(5) 2013, Hull et al. DEBS 2011 (10.1145/2002259.2002270), Sauri & Pustejovsky LRE 43(3) 2009 | Not re-verified this pass. All are well-established and low-risk, but confirm pagination/DOIs. |
| Yolum & Singh referral networks, IEEE TSMC-A 2005 — **exact title** | One auditor confirmed venue+year from the author archive but **not the title**. |
| Black & Hunter "An inquiry dialogue system", AAMAS 2009 — pagination | Not confirmed. |
| Golovin & Krause arXiv:1003.3967 / JAIR 42; Chen et al. AAAI 2015 submodular surrogates | Not re-verified. |
| MediQ arXiv:2406.00922; UoT arXiv:2402.03271 | Not re-verified directly (InfoGatherer's baseline list corroborates that both exist as named methods). |
| SURE-RAG arXiv:2605.03534 — **author list** | Paper verified by one auditor; author names explicitly unconfirmed. |
| 2606.18037 (ProvenanceGuard), 2607.12650, 2606.20895, 2604.05539, 2606.01435, 2604.15558, 2603.14643, 2605.17596, 2606.00671, 2601.06181, 2606.04903, 2605.11436, 2607.07405, 2607.27083, 2606.13405, 2605.08828, 2606.05403, 2609.00652, 2605.30335, 2609.08481, 2606.04990, 2607.20827, 2604.19895 | Reported real by one or more auditors; **not verified by me this pass**. None is load-bearing for this determination. Verify any that reach the paper. |

---

## 7. Three edits the existing notes need regardless

1. **NOVELTY_AUDIT.md §3–§4.** "Entailment over content has no variable that distinguishes the report from
   the artifact; the discriminating variable is the channel, which is metadata outside the text" is sound
   against ProvenanceGuard only and **false in general** — PolicyGuard's rule atoms, EG-VAR's per-source
   lifts and B6's own one-line metadata read all have that variable in hand, and FactBank represents it in
   text with nested source chains. Narrow to the decompose-then-verify family or delete.
2. **CLOSEST_WORK.md row 7.** "they do not supply the observation model" is **false** for InfoGatherer —
   §2.1's per-snippet BBA elicitation is exactly an LLM-supplied, inference-time observation model. Also
   delete "CTES supplies the missing mechanism" for EnvTrustBench (B6 supplies it in twenty lines), and
   demote ProvenanceGuard from nearest-neighbour: it is on the *excluded* side of the dichotomy while every
   dangerous work is on the submission's own side and none appears in the table.
3. **Delete `hedge_spare_slot`** from `evidential_channel_v1.py`. It defaults to `False`, is never passed by
   `runner.py`, and is dead code in every reported run. A reviewer reading the artifact will ask why the
   file implementing the claimed method contains an untested, unclaimed planner branch. Separately, the
   conservative parse (a requirement whose options are all dropped is retained as permanently
   UNSATISFIABLE) blocks readiness and mechanically inflates request counts — a plausible partial source of
   the +0.81 requests, and a defect rather than a feature. Logic-LM's solver-feedback specification repair
   is the published fix.
