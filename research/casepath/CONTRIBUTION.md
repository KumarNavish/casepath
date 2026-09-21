> **HISTORICAL RESEARCH RECORD — not the submission claim.** This file documents the earlier
> process-induction line, whose positive claims were **withdrawn** after a constant-oracle and
> wrong-pairing audit; see `PAIRED_DESIGN_DEGENERACY.md` for what failed and why. The submitted
> ICLR 2027 paper is `research/casepath/iclr2027-integrated/`, and its Study A benchmark reproduces
> offline from `research/casepath/branch-benchmark/`. `research/casepath/iclr2027/` is a separate,
> unsubmitted paper from this same historical line. Numbers in this file must not be quoted as
> current results.

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

**Measured on 28 held-out pairs across 6 scenarios.** Compared against each arm dropping the same number of its
own requested documents at random — the control that makes arms requesting different amounts comparable:

| arm | withdrawal recall | own random baseline | excess | 95% CI |
|---|---|---|---|---|
| direct prediction | 0.038 | 0.099 | **−0.061** | [−0.096, −0.026] |
| graph, then ask the model for a checklist | 0.121 | 0.110 | +0.011 | [−0.017, +0.038] |
| full pipeline | 0.591 | 0.473 | **+0.118** | **[+0.106, +0.126]** |

On `gpt-5.6-terra` direct prediction is *worse than chance*, and only the compiled chain carries signal. **That
pairing is not the method's property.** Re-run with the interpreting model changed and nothing else, the same
frozen artifact scores +0.119 and +0.109 on two reasoners and **−0.077 and −0.039 on the other two** — the
compiled chain becomes anti-correlated. Direct prediction is anti-correlated on one model of four. See
`MODEL_GENERALITY.md`. The contribution is therefore the measurement, not the method: a single-model result about a
structured method measures the pairing and attributes it to the structure.

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

- **Development data can be unrepresentative in a way a scenario split does not prevent.** On the development
  scenarios the compiler looked useless and I amended the preregistered primary away from it. On held-out data it
  is the only arm that works. All four development scenarios were form-defect disputes, which activate nodes
  carrying no evidentiary obligation, so the compiler requested 3.9 documents and had nothing to release; the
  held-out substantive-calculation scenarios activate the nodes that do carry obligations and it requests 10.0.
  The amendment was declared before the read, so the demoted comparison survives in the record — which is the only
  reason the result is recoverable.
- **Raw withdrawal recall is not comparable across arms that request different amounts.** The full pipeline's
  +0.553 over direct prediction is mostly volume: dropping the same number of its own documents at random scores
  0.473 of the 0.591. What survives the control is +0.118 [+0.106, +0.126] — real, and four times smaller than the
  raw number.
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
