# Reference contracts: construction, gate, and what the gate caught

A reference contract is the ground truth this work is scored against: for a claim scope, the decisions a handler
must reach, the documents each decision needs from the party, and the condition under which each decision closes.

The contract must not come from the system it judges. If the induced process graph authored its own ground truth,
every metric would be a measure of self-consistency. So the contract is built from the sources directly, by agents
that never see the induced graph, and every factual claim in it passes a gate before it is admitted.

## Construction

1. **Spine.** An independent agent reads the Swiss federal sources for the scope and emits the decisions the law
   requires, each with the authorities it rests on and the exact text it relies on. No access to the induced graph,
   the compiler, or any pipeline output.
2. **Quote gate.** A quote is admitted only if it is a verbatim substring of a passage fetched from Fedlex, hashed,
   and cited by that same decision. Whitespace is normalised; nothing else is. A quote that fails is dropped and
   logged with the citation that failed to support it.
3. **Document layer.** Three authors, working only from the gated spine, independently say which documents each
   decision needs from the party. Proposals outside the fixed catalogue are rejected. A document is admitted on
   two of three votes.
4. **Conditions.** One adjudicator reduces the three authors' `live_when` / `dead_when` formulations to one
   checkable pair per decision. These are what make a requirement retractable, and they are what the dynamic
   metric scores against.
5. **Per-case ground truth.** Three further adjudicators mark each decision live / dead / unknown against the case
   narrative alone. `unknown` is not `dead`: a decision that cannot be settled on the stated facts is still open.

Every step is separated from the next by what it is allowed to see. The document authors cannot rescue a quote the
gate dropped, because they never see the ungated spine.

## What the gate caught

The first spine cited 40 distinct authorities and 58 exact quotes across 12 decisions.

| | count |
|---|---|
| quotes proposed | 58 |
| verbatim in the authority the decision cited | **44 (76%)** |
| dropped | 14 |

Of the 14 dropped, 13 were attributed to cantonal forms and official guides that the agent cited but that are not
in the fetched corpus — unverifiable here, not necessarily false. **One was a fabrication of a different kind.**

Decision D9 cited `vmwg-art-19a-20251001-de` for a rule about notice periods for staggered rents. Two things are
wrong with that citation, and they are independent:

- **The consolidation date does not exist.** Fedlex serves no VMWG consolidation at 2025-10-01. Ten of the spine's
  citations carried this date. Re-resolved against the real consolidation, nine of the ten recovered — the article
  text was right and only the date label was invented.
- **The article does not exist.** VMWG has no Art. 19a at any consolidation. The tenth citation had nothing behind
  it. The quote attributed to it is fluent, plausible, correctly styled Swiss regulatory German, and sourceless.

This is the case for the gate rather than a decoration on it. A wrong date is recoverable and a careful reader
would likely catch it. A fabricated article carrying a fluent quote is not visible by reading: it looks exactly
like the 44 that verified. Only fetching the act and testing for the substring separates them.

That a *fabricated* provision reached a reference contract authored specifically to be authoritative is the reason
no quote in this work is admitted on an agent's assertion.

## What survived

All 12 decisions retained at least one verified quote, so none was dropped for want of evidence. The 14 dropped
quotes were corroborating, not load-bearing — the cantonal forms colour the argument but nothing structural rests
on them alone. The contract covers 11 of the 16 catalogue documents.

The three document authors agreed unanimously on 27 document-decision pairs, split 2–1 on 3, and produced 7
singletons that were dropped — 73% unanimity. No author proposed a document outside the catalogue.

One decision, D7 (whether the increase is null), requires no document from the party at all. That is correct and
worth stating: nullity is a conclusion drawn from the form already obtained under D4–D6, not a separate evidentiary
burden. A contract that could not express "this decision needs nothing further" would inflate every checklist it
scores.

## Corpus

Verifying this spine required 25 statutory passages the corpus did not hold. They were extracted with the same
pipeline and identity as the rest (`fedlex-akn3-visible-text-blockspaced-whitespace-normalization/1.1.0`), taking
the corpus from 63 to 86 passages across OR, VMWG, ZPO and VVG.

## Files

- `reference_contracts/rent_increase.json` — the contract, with the full audit block and every dropped quote
- `reference_contracts/_superseded_draft_fragment.txt` — the first run's document layer, which emitted free-text
  document types instead of catalogue identifiers and lost the capability layer it referenced; retained for audit,
  not used
