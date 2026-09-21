# The CasePath branch-intervention benchmark

A document-request benchmark that a static checklist cannot pass.

Every case here exists twice. The two versions differ in **one sentence** — a sentence that decides
which rule of the source applies. The question is not "which documents look plausible for this
claim?" but "which documents does *this* fact justify, and which stop being justified when it is
removed?"

```
"No stolen item is separately scheduled in the policy with an insured value of CHF 1,000 or more."
"A stolen watch is separately scheduled in the policy with an insured value of CHF 4,000."
```

Everything else in the two case texts is identical. Under the frozen source wording the second
version activates one obligation: the value of the scheduled valuable must be established. So the
justified change is `+receipt` **or** `+expert valuation` — either route satisfies it, and asking
for both is scored as an unnecessary request. A system is graded on the *signed difference*
between the two checklists it produces, not on either checklist alone.

This directory contains the benchmark, the recorded predictions of all four evaluated systems, the
frozen analysis code, and a single command that recomputes every Study A number in the paper.

```bash
python3 reproduce.py
```

No network, no API key, no provider account. It verifies file hashes, prints the benchmark's
admission controls, reruns the frozen statistics on the recorded predictions, and diffs the result
against the preserved held-out report. Runtime is about seven seconds.

To read the benchmark case by case instead, open `explore.html` — it carries its own data, so it
works straight from disk with no server.

Each pair shows the sentence that changed, the justified change with its alternative routes, and
what all four systems asked for, marked correct / spurious / missed. The marks are read from the
frozen scorer's preserved report, and `build_explorer_data.py` asserts that they sum to the totals
the paper reports. It is the fastest way to see *why* a score is what it is: on the scheduled-valuable
pairs, for instance, CasePath requests the receipt (correct) and also the expert valuation
(spurious) because the frozen planner unions alternative routes instead of selecting one.

## Why signed changes

A checklist metric rewards a system for listing what usually appears in claims of this kind. Such a
system scores well while being unable to explain a single request, and it fails silently exactly
where it matters: on the case whose facts are unusual. Scoring the *change* between two nearly
identical cases removes that reward. A constant answer earns zero by construction, whatever it
contains.

For a pair of case versions `(x⁻, x⁺)` and a system producing document sets `D(·)`:

```
Δ(D) = { +d : d ∈ D(x⁺) \ D(x⁻) }  ∪  { −d : d ∈ D(x⁻) \ D(x⁺) }
```

The scorer compares `Δ` against every acceptable realisation in the reference contract and keeps the
best under a frozen lexicographic rule, so alternative evidence routes stay alternatives. Requesting
the union of two alternatives is not credited as correct. True positives, predictions and references
are then pooled across pairs into micro precision, recall and F1. A **spurious** change is an
addition or withdrawal the sources do not justify; a **missed** change is a justified one the system
did not make.

## How the benchmark was built

1. **Sources.** 197 exact passages of Swiss insurance law and public household-insurance policies and
   forms (Fedlex, CSS, AXA, Generali, Simpego, the Swiss Insurance Association), each stored with its
   URL and content hash in `benchmark/SOURCE_SNAPSHOT_V2.json`. The snapshot deliberately federates
   statute wording with several insurers, so a pair is a **rule-unit conformance test**, not a legally
   complete checklist for one policyholder under one policy.
2. **Branch concepts.** Nine predicates whose truth value changes at least one evidence requirement:
   a scheduled valuable at or above the policy threshold, a bicycle among the stolen items, SIM-card
   theft with misuse, an identifiable third-party causer, a formal expert procedure, a repair above
   the consent threshold, a written demand with a forfeiture period (*Nachfrist*), recovery of stolen
   goods, and insurer declination.
3. **Contexts.** Each concept is instantiated in four neutral household-theft narratives → 36 pairs,
   72 case units (`benchmark/BENCHMARK_V3.json`).
4. **Reference contract.** Authored from the sources *before any system was run* and independent of
   any system output. Where the wording admits alternatives they are preserved as alternatives. Both
   pre-hidden amendments are kept with their predecessors (`benchmark/BENCHMARK_AMENDMENT_V*.json`)
   rather than silently replacing them.
5. **Split and freeze.** One context per concept is development (9 pairs); the other three (27 pairs)
   stayed sealed until the method, benchmark, analysis code and success criteria were hash-frozen
   (`freezes/`), and were then read **once**.

## The falsifiers, and what they rule out

Benchmarks of this shape are vulnerable to shortcuts, so the controls run *before* the evaluation and
their results are part of the release.

| Control | Result | Rules out |
|---|---|---|
| **Input-free predictor.** A constant signed-set predictor is fitted on eight branch families and scored on the ninth, leave-one-out. | max held-out micro-F1 **0.0** | A system scoring well by emitting a fixed set. There is no such set. |
| **Target diversity.** Distinct acceptable target signatures across families. | **9/9 distinct**, 3.17 bits over 12 signed document atoms | A degenerate label distribution where one answer fits most families. |
| **Wrong-family pairing.** CasePath's own outputs are held fixed and reassigned to other branch families (8 cyclic shifts + 5,000 seeded derangements). | correct **0.667** vs null max **0.083**, mean 0.011 | Changes that are not specific to the intervened branch. It does **not** prove the internal representation is the unique cause: a family-specific lookup would also pass. |
| **One-shot read against a preregistered gate.** Eight conditions fixed before the sealed read. | 5 pass, **3 fail** | Post-hoc selection of the criterion that happened to be met. |

What the controls do **not** establish: that the source text is necessary at inference time (no
case-only ablation was frozen), or that results transfer to unseen rules, unseen policies or another
domain. The held-out split varies the narrative context of concepts already seen in development.

## The result, and the claim it does not support

Reproduced by `reproduce.py` on the 27 held-out pairs and 33 reference changes:

| Method | Prec | Recall | F1 | Exact | Predicted | Spurious | Missed |
|---|---|---|---|---|---|---|---|
| **CasePath** | **0.615** | 0.727 | **0.667** | **0.444** | 39 | **15** | 9 |
| Direct | 0.481 | 0.758 | 0.588 | 0.333 | 52 | 27 | 8 |
| Graph as context | 0.431 | 0.939 | 0.590 | 0.148 | 72 | 41 | 2 |
| Evidence-first | 0.235 | 0.485 | 0.317 | 0.074 | 68 | 52 | 17 |

All four arms share the same model setting, provider restriction, temperature 0, source snapshot,
document catalogue and case texts. They are matched on inputs, **not** on compute.

The practical contrast with Direct is precise: **twelve fewer unjustified changes for one fewer
correct change**. Graph as context recovers the most reference changes and makes the most spurious
ones — handing a generator the process representation as context makes it ask for *more*, not for
the right things.

**The preregistered gate fails**, and that failure is part of the result. F1 margins of +0.078 and
+0.076 over the two strongest comparators fall short of the required 0.10; precision 0.615 falls
short of 0.70; Holm-adjusted family-swap p-values are 0.797, 0.797 and 0.129. `claim_status` in the
preserved report is `UNSUPPORTED` for broad superiority. The supported claim is selectivity and
traceability, not statistical dominance.

Two structural facts are reported separately from accuracy, because they are invariants of the
architecture rather than evidence of correctness: **39/39** predicted changes are attributed to a
changed guard (including the wrong ones), and **27/33** reference changes are reachable through a
source chain in the frozen representation (81.8%).

Per-concept, CasePath is exact on four concepts and scores **zero** on two (third-party causation,
formal expert procedure). The zeros are systematic: an alternative route over-requested where one
would suffice, a condition attached at the wrong granularity, or an adjacent procedural guard
activating the wrong confirmation document. Because the method was frozen before the read, these are
reported rather than repaired.

## Files

```
benchmark/     BENCHMARK_V3.json (36 pairs), both amendments, the 33-document catalogue,
               the 197-passage source snapshot, and SHORTCUT_PREFLIGHT_V3.json (admission controls)
predictions/   recorded document sets per pair, per arm, for both splits — the inputs to scoring
analysis/      the frozen scorer and statistics, plus THEFT_STATISTICAL_PROTOCOL_V5.md
expected/      the preserved held-out report that reproduce.py diffs against
freezes/        method, development and held-out execution freezes (hash bindings)
parity/        the product-replay verifier and its report: all 72 units and 36 pair changes
               reproduce through the product service using the recorded guard decisions
MANIFEST.json  sha256 of every file with its path inside the original release archive
```

Bytes are unchanged from the frozen release archive; only the directory layout was reorganised for
reading, so hashes in `MANIFEST.json` remain checkable against it.

`reproduce.py` compares numeric values to within 1e-9 rather than bit-for-bit, because floating-point
summation order differs between Python builds; it prints the largest deviation it saw (about 1e-16).
Every quantity the paper reports is given to three decimals.

## Reproducing model outputs

`reproduce.py` recomputes *scores* from recorded predictions. Regenerating the predictions themselves
requires provider access and is **not** deterministic — temperature 0 is not a determinism guarantee.
The per-call receipts (model, provider, token counts, cost, prompt hashes, latency) are in the full
release archive; they record prompt *hashes*, not prompt text, and contain no credentials.

## Relation to the paper and the product

This benchmark is Study A of *CasePath: An Agentic, Process-First Architecture for Determining
Evidence Requirements*. The manuscript source and its numerical audit are in
[`../iclr2027-integrated/`](../iclr2027-integrated/README.md). Study B evaluates complete plans on
the 150-claim corpus that ships with this repository and is reported separately; the two studies are
never pooled.

The planner evaluated here is the same code the product runs: `parity/` records that replaying all
72 benchmark units through the product service with the recorded guard decisions reproduces the
research document sets, guard states and next actions, and all 36 signed pair changes. That
certifies research/product agreement **conditional on recorded assessments** — not fresh-inference
identity, legal correctness or field utility. Re-running `parity/verify_product_method_parity_v5.py`
needs a local product service with the hash-bound method pack installed; the preserved report it
produced is included so the outcome can be read without one.
