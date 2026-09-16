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

---

# Amendment log

The protocol is frozen. Amendments are appended here with the date, the evidence that forced them, and an explicit
statement of which already-admitted scopes would not have passed the amended form. Nothing above is edited.

## A1 — 2026-09-16 — add C8, observed branch closure

**What forced it.** Rent increase passes C5 comfortably: 6 of its 11 contract documents are required by exactly one
decision (55%, against a 25% threshold). Yet on 15 real cases the reference contract produced only **2 distinct
checklists**, with 14 of 15 identical. The static task is saturated and cannot separate any two methods.

**Why C5 missed it.** C5 asks whether closing a branch *would* remove a document. It never asks whether any such
branch *does* close in the case distribution. Rent increase has six uniquely-owned documents, but all six belong to
just two decisions — D3 (date of receipt) and D12 (substantive abusiveness) — and a first-contact customer message
settles neither. The decisions that do get settled (D11 nine times, D5 and D6 four times each) own no document
uniquely, so closing them changes nothing. Structural discriminability and observed discriminability came apart.

**C8.** On a sample of at least 15 real cases of the scope, the reference contract must yield **≥ 3 distinct
reference checklists**, and at least one branch-discriminating decision must be settled in **≥ 20%** of them.

| | measured on rent increase |
|---|---|
| distinct reference checklists over 15 cases | 2 |
| branch-discriminating decisions settled | D3 in 1/15 (7%), D12 in 1/15 (7%) |
| C8 | **fails** |

**Consequence, stated plainly.** Rent increase was admitted before C8 existed and **would not be admitted under it**.
It is retained, because the work is done and the dynamic result on it is real, but it is hereafter reported as a
scope that fails observed discriminability, and **no static-checklist claim is drawn from it**. Its role is the
branch-intervention experiment, where the requirement is not that branches close on their own but that the system
responds correctly when a fact closes one.

C8 applies prospectively to every scope admitted after this date, including the held-out scope and the insurance
transfer scope. A scope that fails C8 may still be used for intervention experiments, and may not carry a static
claim.

**Cost of the amendment.** C8 cannot be scored from sources alone — it needs a reference contract *and* an
adjudicated sample of real cases. Admission therefore becomes more expensive than C1–C7 implied. That is the price
of the criterion being about the case distribution rather than about the law.
