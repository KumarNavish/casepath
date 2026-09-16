# Scope admission scoring

Scored against the frozen criteria in `SCOPE_ADMISSION_PROTOCOL.md`, applied exactly as written. Every
figure below is computed **from the reference contracts alone**, by a script that walks
`documents -> establishes_capabilities -> capabilities.for_fact -> facts.for_decision`. No CasePath
artefact was opened, and no criterion was computed from an induced graph.

Contracts scored (exact paths — see §7, the rent_increase filename is **not** the obvious one):

- `reference_contracts/rent_increase.adjudicated-25node.json`
- `reference_contracts/termination.json`
- `reference_contracts/theft.json`
- `reference_contracts/legal_expenses.json`

## 1. Scores against all seven criteria

| # | criterion | threshold | rent_increase | termination | theft | legal_expenses |
|---|---|---|---|---|---|---|
| C1 | public-source sufficiency | ≥ 15 passages, ≥ 2 kinds | **105 / 2 kinds** PASS | **91 / 2 kinds** PASS | **111 / 3 kinds** PASS | **86 / 3 kinds** PASS |
| C2 | branching richness | ≥ 4 predicates | **24** PASS | **22** PASS | **28** PASS | **25** PASS |
| C3 | conditional obligations | ≥ 3 | **56** PASS | **45** PASS | **52** PASS | **66** PASS |
| C4 | document/evidence rules | ≥ 6 distinct | **30** PASS | **21** PASS | **33** PASS | **36** PASS |
| C5 | **branch-discriminating documents** | **≥ 3 and ≥ 25 %** | **16/30 = 53.3 %** PASS | **18/21 = 85.7 %** PASS | **22/33 = 66.7 %** PASS | **23/36 = 63.9 %** PASS |
| C6 | redistributability | must be stateable | stateable PASS | stateable PASS | stateable PASS | stateable PASS |
| C7 | independent contract feasibility | must be yes | yes PASS | yes PASS | yes PASS | yes PASS |

Contract size, for context:

| scope | decisions | predicates | facts | capabilities | documents | deadlines | terminals |
|---|---|---|---|---|---|---|---|
| rent_increase | 25 | 24 | 53 | 51 | 30 | 13 | 16 |
| termination | 21 | 22 | 61 | 29 | 21 | 15 | 15 |
| theft | 32 | 28 | 58 | 60 | 33 | 13 | 18 |
| legal_expenses | 22 | 25 | 70 | 70 | 36 | 20 | 13 |

### How each criterion was computed

- **C1** counts *distinct authority ids* cited by a decision, predicate, fact or deadline — i.e. passages
  that actually carry an operational proposition, not every passage in the source bundle. Kinds:
  *normative* (`or-`, `zpo-`, `vmwg-`, `vvg-`, `avo-`, `vag-`), *contractual* (published general
  conditions / policy wordings), *operational* (forms, checklists, cantonal guidance pages).
  Breakdown — rent_increase: 96 normative + 9 operational. termination: 86 + 5. theft: 15 normative +
  84 contractual + 12 operational. legal_expenses: 26 + 56 + 4.
- **C3** counts elements with a live `conditional_on` (facts + decisions); `""` and `"none"` are not live.
- **C5** counts documents whose capability→fact→decision trace resolves to **exactly one** decision.
- **C6/C7** are read off each contract's own `sources_used` block (see §5).

## 2. Scopes that clear every threshold

**All four.** No scope fails any criterion of C1–C7.

That is itself a finding and it qualifies C5. The protocol's standing disclosure records termination at
**0 of 16** branch-discriminating documents and rent_increase at **3 of 8**. The contracts scored here
give 18/21 and 16/30 for the same two scopes. The difference is not a change in Swiss law; it is contract
granularity. C5 is a function of how finely the reference contract splits capabilities per fact: a
contract with one capability per fact discriminates far more than one with a few broad capabilities
spanning many facts. **C5 therefore no longer separates these four candidates**, and the earlier 0/16 and
3/8 figures are not comparable with the table above. C5 still does the job the protocol designed it for —
it certifies that closing a branch removes documents outright — but it cannot be used to *rank* scopes
against one another at this level of granularity.

### C5 robustness

Because C5 is the admission gate, it was recomputed three ways. All four scopes pass under all three.

| scope | strict (structured `for_fact`) | prose-expanded | strict **and** branch-removable |
|---|---|---|---|
| rent_increase | 16/30 (53.3 %) | 16/30 (53.3 %) | 15/30 (50.0 %) |
| termination | 18/21 (85.7 %) | 14/21 (66.7 %) | 14/21 (66.7 %) |
| theft | 22/33 (66.7 %) | 22/33 (66.7 %) | 16/33 (48.5 %) |
| legal_expenses | 23/36 (63.9 %) | 23/36 (63.9 %) | 19/36 (52.8 %) |

- *strict* is the protocol's measure and the primary figure in §1.
- *prose-expanded* additionally honours capabilities whose `must_show` text declares extra facts
  ("Serves F02, F03, …"). Only termination has any (7 of 29 capabilities); the other three have none, so
  their figures are unchanged. Termination drops from 85.7 % to 66.7 % and still passes.
- *strict and branch-removable* is stricter than the protocol requires: it keeps only documents whose sole
  decision is itself gated by a predicate (or whose facts are), so that closing a branch genuinely deletes
  the obligation. This is the protocol's own diagnostic question — *does closing at least one meaningful
  branch remove at least one document obligation outright?* — and every scope answers yes.

## 3. Recommended held-out scope

### → `theft` (household contents insurance: a theft claim)

Both tenancy scopes are ineligible by the protocol's standing disclosure, not by any criterion. Of the two
eligible candidates, theft ranks first.

**Ranking rule, stated before applying it:** C5 on the protocol's own primary measure first, ties broken on
the strength of the *document layer's* provenance, because the document checklist is the benchmark's
outcome measure.

1. **C5, primary measure: theft 66.7 % vs legal_expenses 63.9 %.** A 2.8-point gap — too thin to decide on
   its own, which is why the tie-break below carries the weight.
2. **Its document layer is anchored in a public, hashed artefact.** The CSS *Schadenanzeige Hausrat /
   Gebäude* is fetchable and its sha256 was independently matched, and the contract cites it at section
   level (Sachbranchen, Polizeimeldung, the payee block, the signed declaration). Five of theft's sources
   carry matched hashes.
3. **Its removable branches are physically distinct and cleanly gated** — scheduled valuable ≥ CHF 1 000,
   bicycle/e-bike, SIM card, jewellery in a safe, third-party causer, recovery of stolen goods, repair over
   CHF 500. Each closes a named decision and deletes named documents: e.g. `PR_bicycle_claimed` false
   removes the bicycle estimate-with-photo outright; `PR_sim_card_stolen` false removes the 24-hour report;
   `PR_scheduled_valuable_1000` false removes the receipt-or-valuation alternative pair.
4. **Highest C1 (111 passages) and the broadest kind mix**, with all three knowledge kinds represented and
   no single kind carrying the scope alone.
5. It also carries the largest decision set (32) and predicate set (28) of the four.

**`legal_expenses` is admitted but not selected.** It clears every threshold and should be kept in reserve
as a second held-out scope. It is not selected because its own contract records the disqualifying weakness
for a document-layer benchmark:

- *"There is NO public tenancy legal-expenses claim form in Switzerland"* — the `Schadenanzeige` is in the
  contract as a document type with no public schema.
- *"The actual waiting period, product tier, module composition and sum insured for any particular
  insured … the answer lives in a document the public does not hold."* The operative parameters are
  delegated to the policy, which is not public.
- Provenance is the weakest of the four: Protekta is reachable only through a third-party **mirror**, the
  AXA-ARAG `accesscode` URL *"can be silently re-pointed at a new edition"*, CAP's own AVB is not
  obtainable first-party, and several wordings carry no recorded hash.
- It deliberately leaves a live legal tension unresolved (whether a 14- or 20-day disagreement window
  survives VVG Art. 46(2)), so part of its deadline gold is indeterminate by design.
- Four of its 23 discriminating documents hang on `d08_disclosure_and_documents`, which is unconditional —
  they discriminate by node but are not removable by closing a branch.

**Both insurance scopes clear C5**, so the contingency the admission question anticipated does not arise:
there is no need to report that the held-out confirmation cannot be run on these sources.

## 4. Rejected scopes — exactly what and by how much

**No scope was rejected on a criterion.** All four clear C1–C7. Recording this plainly rather than
manufacturing a failure is the honest result; the margins above threshold are:

| scope | status | C1 | C2 | C3 | C4 | C5 | C6 | C7 |
|---|---|---|---|---|---|---|---|---|
| rent_increase | **ineligible as held-out** (development witness, protocol §standing disclosure) | +90 | +20 | +53 | +24 | +28.3 pts | ok | ok |
| termination | **ineligible as held-out** (development scope, protocol §standing disclosure) | +76 | +18 | +42 | +15 | +60.7 pts | ok | ok |
| theft | **ADMITTED — held out** | +96 | +24 | +49 | +27 | +41.7 pts | ok | ok |
| legal_expenses | admitted, **reserved** (ranked second) | +71 | +21 | +63 | +30 | +38.9 pts | ok | ok |

C5 margin is stated in percentage points above the 25 % floor; all four also clear the absolute ≥ 3 limb
by a wide margin (16, 18, 22, 23 against 3).

The two tenancy scopes are excluded for the reason the protocol already fixed in advance — they were
induced first and measured afterwards, so they cannot carry a confirmatory result — **not** because they
scored badly. On the numbers, termination is the strongest of the four on C5.

## 5. C6 — redistributability, per scope

Stateable for all four; no scope is rejected on C6 alone, per the protocol.

- **rent_increase.** Bundle passages and the three Fedlex consolidated texts (OR, ZPO, VMWG) are federal
  law and shippable. The five cantonal artefacts (ZH form, ZH judiciary pages, ZH Merkblatt, AG
  Schlichtungsgesuch, GE Requête, TI page) are recorded as URL + sha256 + extract, five hashes matched.
- **termination.** Same statutory position. All five operational sources carry recorded sha256 values;
  Bern is expressly flagged *"not an amtlicher Erlass — URL + hash + short extract only."* The Solothurn
  Merkblatt was read but **not** quoted, because its PDF text layer inserts spurious intra-word spaces.
- **theft.** VVG Art. 38a/38b/41a are expressly *"Redistributable in full under URG Art. 5(1)(a)."* All
  five private wordings are *"Copyrighted: URL + hash + extract only"*; the SVV model wording is
  *"URL + extract only"* (no hash) and is self-described as non-binding model conditions.
- **legal_expenses.** AVO, VAG and VVG shippable. Weakest private-source provenance of the four: one
  mirror-only wording, one re-pointable `accesscode` URL, one AVB not obtainable first-party, several
  without hashes. Stateable, but the statement is the least stable.

## 6. C7 — independence

Every contract carries an explicit attestation that no file whose name contains INDUCTION, COMPILER,
PIPELINE or SCOPE_SELECTION was opened, and that no induced graph, proposition set, interpreter run or
compiler output was read. rent_increase adds that a directory listing displays such filenames and that
none was read; theft records the Suisse ePolice gate as a settled negative rather than an authority;
legal_expenses carries the attestation twice, once as a source line and once as an explicit statement.
All four: **yes**.

## 7. Recorded incident — a second writer owns `rent_increase.json`

While these contracts were being written, **another process was actively managing
`reference_contracts/rent_increase.json`** and it holds a *different* contract for that scope. The sequence
observed: it truncated a partial write of this file; it later replaced the installed file with its own; and
after the second install it moved this file aside under the name `_unverified_richer_draft.json` and
restored its own. That is deliberate curation by another agent, not a race artefact.

**No edit war was started.** The final state is:

| file | contract | owner |
|---|---|---|
| `rent_increase.json` | 12 decisions, no `documents` array (an 11-name `documents_in_contract` catalogue and per-decision `required_documents`), plus `provenance` / `audit` blocks | the other writer — left untouched |
| `rent_increase.adjudicated-25node.json` | 25 decisions, 24 predicates, 53 facts, 51 capabilities, 30 documents — the adjudicated contract, scored above | this run |
| `rent_increase.CONFLICT-other-writer-2026-09-16T1140.json.bak` | the other writer's file as it stood at 11:40, preserved before the first install | snapshot |

`termination.json`, `theft.json` and `legal_expenses.json` were written once and verified byte-identical to
the validated builds; the other writer has not touched them.

Three consequences worth stating plainly:

1. **The rent_increase row in §1 is computed from `rent_increase.adjudicated-25node.json`**, not from the
   file currently at `rent_increase.json`. Re-running the scorer against the plain filename will not
   reproduce those numbers — the other writer's contract exposes no `documents` array at all, so C4 and C5
   are not computable from it without first mapping its `documents_in_contract` / `required_documents`
   schema onto the capability→fact→decision chain.
2. **The two artefacts are different documents, not versions of one.** Anyone reconciling them should
   decide which is authoritative for the scope before either is used; that decision was not mine to make
   and was not made here.
3. **None of this touches the recommendation.** rent_increase is ineligible as a held-out scope under the
   protocol's standing disclosure regardless of which artefact is authoritative, and the held-out
   candidates — theft and legal_expenses — sit in files no other process has written to.
