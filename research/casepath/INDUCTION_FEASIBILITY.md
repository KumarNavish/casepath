# Can the statutes alone induce a process? Yes — the legal process, not the handler's

I doubted this a turn ago, and I was wrong in a specific and correctable way. The doubt was that statutes
do not describe a workflow. They do not describe the *insurer's* workflow. They describe the *legal*
process precisely, and that process is executable.

## What was run

The 19 Fedlex tenancy passages already in the corpus, through a two-stage induction that never sees the
hand-authored template.

**Stage A, per passage.** Each passage is read on its own and yields typed operational propositions —
condition, obligation, prerequisite, deadline, exception, allowed action, required decision, dependency —
each carrying an exact quoted substring of that passage. A proposition whose quote is not verbatim in the
passage is dropped, which is the one hard grounding gate.

**Stage B, over the propositions only.** The propositions, and nothing else, are assembled into nodes,
transitions, deadlines and obligations. Every object cites the proposition ids that carry it and is marked
supported, uncertain or unsupported. Anything the model believes belongs but cannot ground must be declared
as a gap rather than added as a node.

## Result

19 passages → **48 propositions**, one dropped by the quote gate. By kind: 18 conditions, 14 obligations,
11 allowed actions, 5 deadlines.

All 48 were then given to stage B for a single scope — termination of a residential tenancy for rent
arrears — so the model had to select what was relevant rather than being handed a curated subset.

| | total | supported | uncertain | unsupported |
|---|---|---|---|---|
| nodes | 14 | 11 | 3 | 0 |
| transitions | 13 | 6 | 7 | 0 |
| obligations | 7 | 7 | 0 | 0 |
| deadlines | 3 | — | — | — |

**Zero grounding problems**: every `supported_by` citation resolves to a real proposition, and every
transition endpoint is a real node. **Zero unsupported nodes**: nothing was invented to make the process
look complete.

The induced process is legally correct and operationally usable:

```
arrears established
  → landlord sets a written payment period and threatens termination   (≥30 days, residential)
  → period expires unpaid
  → landlord terminates                                                (≥30 days, month end)
  → formal compliance with Art. 266l–266o          → if not: termination void
  → good-faith challenge                            (within 30 days of receipt)
  → hardship extension                              → authority balances interests
```

Three deadlines came out exactly right, including the two that differ by premises type, and the 30-day
challenge window running from receipt of the termination.

The model flagged three gaps honestly, and they are the right three: what happens if the tenant pays
within the period, the adjudicative procedure for a challenge, and the outcome and duration of an
extension. None of those is in the passages, and none was invented.

## What this settles, and what it does not

**Settled.** The normative layer induces. A grounded 14-node graph with correct deadlines and branch
predicates came out of 19 statutory passages with no template and no domain hint beyond a scope label. The
hand-authored template it replaces has 11 nodes and cites no source at all.

**Not settled.** This is the legal process, not the claims-handling process. Nothing here says what a
handler does first, what is requested at intake, or which documents establish which fact. That is the
contractual and operational layer, and it has to come from published insurer conditions, claim forms and
claims guidance. The source-sufficiency survey for that layer is running separately.

**The correction to my earlier position.** I said the statutes would yield something much thinner than the
hand-authored graph and that the honest paper would be about what law cannot supply. The first half is
false: the graph is comparable in size and far better grounded. The second half survives in narrower form,
as the boundary between the normative layer, which induces well, and the operational layer, which needs
different sources.
