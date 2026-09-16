# What this work contributes, stated as operations rather than as a story

Each item names an operation the system performs and what would have to exist elsewhere to preempt it. Written so
a reviewer can check priority rather than take a claim on trust.

## 1. A verbatim-substring gate between a statute and every downstream artifact

**Operation.** Fetch the act as Akoma Ntoso XML from the Fedlex filestore under a recorded extraction identity;
hash the document and each extracted passage; require that every proposition, every contract quote, and every
predicate verdict carry a span that is a **verbatim substring** of the passage it names; discard anything that
fails, and record the discard.

**Why it is not just "citation checking".** The gate is *constitutive* rather than diagnostic: a failing quote
never enters the artifact, so downstream components never see unverified text. And it applies to three different
layers — proposition extraction, reference-contract authorship, and per-case predicate verdicts — with the same
mechanism.

**What it caught.** A fabricated statutory provision, VMWG Art. 19a, cited at a consolidation date Fedlex does not
serve, inside a reference contract authored specifically to be authoritative. Nine sibling citations recovered at
the real date; that article exists at no consolidation, and its quote is fluent, correctly styled Swiss regulatory
German, and sourceless. It is indistinguishable by reading from the 44 quotes that verified.

**To preempt this** one would need a system that gates legal artifacts on mechanical substring verification
against a hashed primary source at authoring time, not a system that post-hoc checks citations or scores
faithfulness.

## 2. Deriving a checklist through active process obligations, so that it retracts

**Operation.** Induce a process graph from the gated propositions; decide the graph's branch predicates against
one case under `true / false / unresolved` where unresolved never collapses to inactive; propagate activation
deterministically; compile each active node's obligations into required facts, then evidence capabilities, then
document routes restricted to a fixed catalogue. A document is required because a specific node is open, and is
released when every node requiring it closes.

**The measurable consequence** is retraction with a reason. The system can say *which* node stopped requiring a
document, and *which* predicate closed it. A predictor cannot, because it has no representation in which anything
closes — it re-predicts, and any change is incidental.

**Measured.** Direct prediction withdrew correctly **0 times in 61 opportunities** across 14 development pairs
while making 11 withdrawals. Supplying the source-grounded graph lifted withdrawal recall to 0.148, difference
+0.148 with a 95% interval of [+0.038, +0.267] over scenario-level resampling.

## 3. An evaluation that scores change rather than level

**Operation.** Build the ground truth — a reference contract with per-decision live/dead conditions — from the
sources by agents that never see the induced graph. Then pair each case with a minimal factual edit that settles
one predicate, and score whether the arm's request set moves the way the contract says it must.

**Why this is the load-bearing design choice.** The static checklist task on this corpus is saturated: one
distinct reference checklist across the cases, and a predictor that ignores the case scores F1 1.000. Five of six
baselines land within 0.034 F1 of one another. Any static comparison would be noise. Scoring the *difference*
between paired variants is unaffected by a constant level, and it is the only measurement here that separates
anything.

## 4. Negative results that constrain the design space

Reported because they are what the measurements support, not despite it.

- **The deterministic obligation compiler does not pay for itself.** Handing the model the graph and asking for a
  checklist beat the full pipeline on withdrawal recall. What compilation buys is retention, fewer false
  withdrawals, and the only auditable chains — not a better checklist. The value is in the **process structure**;
  the compiler makes the response *checkable*, not *better*.
- **Two independent source-grounded inductions of one scope partition it differently** — one downstream into
  procedure, one upstream into validity — so the induced graph is not uniquely determined by the sources, and no
  claim that the method recovers *the* implied process is available.
- **Structural discriminability and observed discriminability come apart.** A scope can have many
  branch-discriminating documents and still yield one checklist on real cases, because the decisions that actually
  close are the ones whose documents are shared. The admission protocol was amended for this after it failed to
  catch it.

## Deliberately not claimed

Better static checklists. A unique induced process. Transfer to the other three scopes whose contracts exist but
which have not been run. Any result from the confirmatory scenarios beyond the single preregistered read.
