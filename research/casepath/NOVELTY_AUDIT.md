# Novelty audit — what survives a hostile literature check

24 agents: five contribution claims × four independent search angles, then a per-claim adversary instructed to kill
the claim, then synthesis. Full per-claim output in `NOVELTY_AUDIT_raw.txt`.

## Verdicts

| # | claim | adversary verdict | action |
|---|---|---|---|
| 1 | Constitutive verbatim-substring gate | **PREEMPTED** | **demote to Method** |
| 2 | Retractable requirements via executable source-grounded process graph | not preempted | keep |
| 3 | Per-arm random-drop baseline for set retraction | not preempted | keep |
| 4 | Direct LLM requirement updates anti-correlated | not preempted | keep |
| 5 | Static checklist benchmarks degenerate | not preempted | keep |

## 1. The gate is preempted — it leaves the contributions list

The adversary returned `does_it_actually_preempt: true`. The claim "constitutive rather than diagnostic" is
preempted **four independent ways**, all verified by opening the source:

- **Wang (2026), *A Registry-Bound LLM Pipeline for Evidence-Grounded Trait Extraction*** (arXiv:2606.00994) —
  substring correspondence as an *admission gate into a persisted registry*, failures discarded. This is the
  closest and it is the same operation.
- **Menick et al. (2022), GopherCite** (arXiv:2203.11147) — enforces verbatim-ness by *constrained sampling, not by
  scoring*.
- **Signé et al. (2026), Constrained Hybrid Decoding** (arXiv:2609.10046) — hard decoding constraint guaranteeing a
  quoted span is a verbatim substring of retrieved context.
- **Hadley (2026), *CANONIC: Governance Is Compilation*** (arXiv:2607.05410) — states the constitutive-vs-diagnostic
  thesis in almost the same words.

**What survives** is narrow and is a systems detail, not a contribution: the predicate is *ternary*. Prior work
tests `substring(quote, supplied_document)`. Ours additionally resolves the cited authority against a
consolidation-versioned primary source, so one rule rejects both "this text is not in the passage" and "**this
article exists at no consolidation**" — which is the failure it actually caught. Context-bound quote guarantees
cannot detect the second at all, because they never ask whether the cited provision exists.

The fabricated-statute incident is therefore reported as an **illustration in the Method section**, n=1, alongside
the aggregate discard rate — not as a result.

## 2–5. What survives, with the closest prior work named

**Process graph → retractable requirements.** Closest: GDPR compliance-graph alignment (arXiv:2510.26309), Dutch
DMN decision-model generation from environmental law (arXiv:2604.17153), LLM civil-legal-aid intake
(arXiv:2410.03762). All decide *outcomes* or *eligibility*; none derives document or evidence requirements, none
has an evidence-capability layer, none has a closed document catalogue. The typed chain *active node → required
facts → evidence capabilities → document routes over a closed catalogue* is what makes document-level release
computable, and has no found precedent.

**Per-arm random-drop baseline.** Closest: De Vries, Geva & Trotman (2012), *Divergence from a Random Baseline*,
with Hubert & Arabie (1985) and Vinh et al. (2010). The adversary's judgement: the null here is **structurally
different**, not domain-shifted. Every prior instance randomizes over a *fixed external universe* and copies only
the system's size structure; here the candidate pool **is the system's own request set**, which is why it can
detect that an arm is anti-correlated rather than merely weak.

**Anti-correlated updates.** Closest: Wilie et al. (2024), *Belief Revision: The Adaptability of LLM Reasoning*,
EMNLP 2024 (Belief-R, ΔR). Survives because Belief-R measures answer revision on synthetic premises; this measures
*requirement-set retraction against an independently source-built contract*, and reports a three-rung ladder with a
**null middle** — direct anti-correlated, graph-then-list null, compiled signal.

**Benchmark degeneracy.** Closest: Kaushik & Lipton (2018), *How Much Reading Does Reading Comprehension Require?*,
with Tsoumakas & Katakis (2007) and Meding et al. (ICLR 2022). Survives as a **limit case**: every precedent
measures a partial-input model against a *varying* label. Reporting `|distinct gold label sets| = 1` across two
independently constructed scopes in a professional-services setting has no published instance the sweep could find.

## Two defects in this audit, recorded

**The synthesizer was starved.** The workflow sliced its input at 40 000 characters, so the final synthesis agent
saw only claim 1 and then drew on unrelated superseded material from elsewhere in the project record. Its ranking
is not usable and is disregarded; the per-claim adversary verdicts above were extracted directly from the run
journal, which is complete.

**Coverage is incomplete.** Two independent sweeps of the same claim returned roughly 50% disjoint hit sets. Two
passes disagreeing that much means a reviewer will surface a paper neither pass found. The related-work section
should be written to survive that rather than to claim exhaustiveness.

## Binding rules for the write-up

1. Never write "constitutive rather than diagnostic" as though the distinction were ours. Cite Wang, GopherCite,
   CHyD and CANONIC in the sentence that introduces it.
2. Never let verbatim validity stand in for semantic support. Windisch et al. (2026) is explicit that a byte-exact
   span does not entail that the span supports the proposition. Report mechanical validity and semantic support
   separately, and report the coverage cost of discarding.
3. Cite nothing the audit marked `search_result_only` or `recalled_uncertain`. Only sources marked
   `verified_source_read` may appear.
