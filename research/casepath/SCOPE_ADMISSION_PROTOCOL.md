# Scope admission protocol

Frozen before any scope was scored under it, and before any baseline comparison exists. Every criterion
below is computable from public sources and a source-based reference contract alone. **No criterion may be
computed from CasePath output.** That restriction is the point of the document: it is what stops the final
paper from resting on a scope that was chosen because the method happened to do well there.

## Standing disclosure about the two development scopes

Two scopes are already in hand and were **not** selected under this protocol. They were induced first and
measured afterwards, which is a post-hoc selection and is declared as such:

- **Tenancy termination and extension.** Induced first because the source-sufficiency survey rated it
  strongest on source coverage. Measured afterwards to have **no** branch-discriminating documents (0 of
  16 hang on a single node).
- **Tenancy rent increase.** Induced second, after termination failed to discriminate, and found to have 3
  of 8 documents on a single node. This is a **development witness** and its numbers are development
  numbers. It is not evidence for the paper's claim and will not be reported as confirmatory.

Both are retained: termination for process-identification metrics, where its richness is an advantage and
its non-discrimination is irrelevant; rent increase for developing the causal analysis. Neither may carry a
confirmatory result.

Every scope admitted from here is scored under the criteria below **before** CasePath is run on it.

## Criteria

A candidate scope is scored on seven properties. Each is computed from the public sources and the
independent reference contract, never from an induced graph.

| # | criterion | how it is measured | threshold |
|---|---|---|---|
| C1 | public-source sufficiency | number of public passages that supply an operational proposition for this scope, across at least two knowledge kinds (normative / contractual / operational) | ≥ 15 passages, ≥ 2 kinds |
| C2 | branching richness | branch predicates in the reference contract | ≥ 4 |
| C3 | conditional obligations | obligations in the reference contract whose applicability is conditional on a predicate | ≥ 3 |
| C4 | document/evidence rules | documents or document sets named or unambiguously implied by the sources | ≥ 6 distinct |
| C5 | **branch-discriminating documents** | documents in the reference contract justified by **exactly one** process node | **≥ 3, and ≥ 25% of the scope's documents** |
| C6 | redistributability | whether the source bundle can be shipped, or only URL + hash + extract | must be stateable; no scope is rejected for this alone |
| C7 | independent contract feasibility | whether a reference contract can be built from the sources without consulting CasePath | must be yes |

**C5 is the admission gate that matters** and it exists because of what termination taught. A scope where
every document is justified by several nodes cannot demonstrate that resolving the process changes the
checklist, however rich its graph. The diagnostic is stated as a question the reference contract answers on
its own: *does closing at least one meaningful branch remove at least one document obligation outright?*

## Procedure

1. Draw candidates from the admitted list in `SOURCE_SUFFICIENCY.md`, which was compiled before any of this
   and rated scopes on source coverage only.
2. Build the reference contract for each candidate from the public sources, independently of CasePath.
3. Score C1–C7 from that contract.
4. Admit the highest-scoring candidate that clears every threshold. Record the scores of those rejected.
5. Only then run CasePath on it.

## What admission does not license

An admitted scope is a scope on which the experiment is *measurable*. It is not a prediction that the
method will win there, and a loss on an admitted scope is a result to report rather than a reason to admit
another one. If the held-out scope is admitted and CasePath loses, that is the finding.

## Held-out use

The scope admitted under this protocol is read **once**, after the method is frozen, under
`FINAL_PREREGISTRATION.md`. No tuning may use it.
