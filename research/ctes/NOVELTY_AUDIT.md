# Novelty audit — Channel-Typed Evidential State (CTES)   [draft written before dev results; §5/§6 numbers filled after]

## 1. Exact algorithm
Inputs per turn: actor A = (sources S with metadata, catalog D, own prior plan). Each source s ∈ S carries
channel κ(s) ∈ {party_report, instruction, returned_artifact} taken from metadata only (in the arena: whether the
source is a delivered document; in the product: the admission receipt of the artifact the pointer belongs to).
One model call (same information as every other arm) returns local atoms:
  R = {(r, sets_r ⊆ 2^D, critical_r, standard_r, active_r)}          requirements read from instructions
  T = {(u, r, coverage ∈ {full, partial, contrary, none})}            attestations: unit u's own content vs requirement r
  M = {(u, d, status ∈ {exists, possessed_by_customer, held_by_third_party, promised, automatic, nonexistent, content_quoted, unreadable})}
  Y = {(d, readability ∈ {full, partial, unreadable})}                for returned documents only
Calculus (deterministic):
  level(u) = 1 if κ(u) = party_report; 2 if κ(u) = returned_artifact; 0 if instruction                    (channel cap)
  ℓ(r) = max{ level(u) : (u, r, full) ∈ T }
  observed(d) = d has a returned unit ∧ readability(d) = full ∧ max{level(u): u returned for d, (u,·,full) ∈ T} ≥ 2
  satisfied(r) = ∃ option ∈ sets_r : ∀ d ∈ option observed(d)  ∧  ℓ(r) ≥ standard_r
  availability(d) from M with the rule: promised/automatic count only when κ(u) = returned_artifact, otherwise → exists
  state(d): received | insufficient | pending | not_required | missing by the rules in evidential_channel_v1.compute_state
  ready = ∀ r critical ∧ active: satisfied(r)
  requests = greedy cover of {r active ∧ ¬satisfied} over requestable documents (not pending/automatic; not re-requested one turn
             after a request unless its return was insufficient), ≤ 2, preferring documents reported possessed by the customer
  action = proceed if ready, else request if requests ≠ ∅, else wait (pending deliveries) / clarify (no requirements)
Ablation (B5): identical atoms; level(u) = 2 for every non-instruction unit; party-reported promises honoured.
Product form (evidential_channel_gate_v1): a need's proposed state `received` is kept only if a supporting pointer belongs
to a returned artifact (admission kind export/source_update); otherwise partial (party report) or missing.

## 2. Operation-level comparison
| candidate operation | closest prior operation | relation | residual |
|---|---|---|---|
| level(u) from channel metadata | source-credibility weights (truth discovery), hearsay/best-evidence rule (law) | weaker than credibility learning; identical in spirit to the legal rule | first use as a hard cap on *action readiness* in an evidence-acquisition agent; metadata-only, never model-judged |
| local attestations per unit | claim decomposition + NLI support (ProvenanceGuard, FActScore) | comparable | decomposition is over *evidence units against requirements*, not over answer claims; the model never emits a status |
| availability from second-order reports | pending_deliveries field in the E76 ledger (model-declared) | stronger: channel-conditioned | party-reported promises never suppress requests; artifact-reported promises do |
| satisfied/ready/request rules | E76 compiler (project_full), CGDP exhaustion gate, EC²-style cover | comparable / weaker (greedy) | none claimed: standard set-cover planning |

## 3. Constructive reduction attempt (strongest prior implements CTES)
Take decompose-then-verify with a strong model (ProvenanceGuard-style): decompose the planner's proposed states into
claims ("D is received", "requirement r is established"), route each claim to source units, and check support by
entailment. To reproduce CTES it must reject "D is received" when the only supporting unit is the customer's report
"I found D at home; it shows 3 March" — but that unit *does* entail that D exists, that the customer holds it, and (for a
reader that accepts reported content) that D shows 3 March. Entailment over content has no variable that distinguishes
the report from the artifact; the discriminating variable is the channel, which is metadata outside the text. The reduction
therefore needs an extra input (the channel) and an extra rule (the cap) — which is the candidate.
Take a belief-state planner (CGDP/InfoGatherer/EC²) with a per-domain observation model: it reproduces CTES if the
observation model maps party reports to availability variables and returned artifacts to content variables. That model
is exactly what CTES supplies generically; the planner does not derive it, and re-specifying it per domain is the
adaptation cost measured in the transfer pilot.

## 4. Why the reduction fails (concrete)
The failure is informational, not terminological: in the E76 replay the customer's paragraph and a returned notice can carry
the *same sentence*; four Opus arms (direct, document-first, ledger, ledger+compiler) all marked the notice received from
the paragraph alone. Any procedure whose inputs are the texts and the model's judgement of them can be fooled by
identical content; a procedure that also reads the admission channel cannot. "Trust, but Don't Verify" (2606.05403) shows
that instructing the model to apply such a rule during synthesis does not work (blanket skepticism or none), so the cap must
be applied outside the model. Hence the residual is (i) an additional input variable (channel metadata) and (ii) its use as a
monotone cap on attained support, with the consequence that readiness and requests are computed from capped support.

## 5. Distinct prediction (frozen in final/PREDICTIONS.md before the dev run)
P1–P5: CTES never declares premature readiness and has zero hearsay receipts; every content-only arm (direct, ledger, ledger+
compiler, and the ablation with the same atoms) does so on episodes with possession/quotation reports; CTES gains ≥0.10
utility at equal request volume; removing the cap removes at least half of the gain.

## 6. Practical consequence in CasePath
A claim handler's "I found the notice" must trigger a request for the notice from the customer, not readiness. The gate is
wired into the native live workspace's proposal decoder behind CASEPATH_EVIDENTIAL_CHANNEL_V1, so canonical fact
interpretation (fact_state known ⇔ state received) can no longer be reached from party reports alone.
