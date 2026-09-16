# Scope selection, decided by discriminating power rather than graph size

Two scopes were induced from the same 63-passage corpus and put through the same compiler. They look
equally good by every structural measure and only one of them can carry the paper's claim.

## The two graphs

| | S1 termination + extension | S2 rent increase |
|---|---|---|
| nodes | 12 (12 supported) | 13 (12 supported, 1 uncertain) |
| transitions | 11 | 14 |
| deadlines | 3 | 4 |
| facts compiled | 35 | 39 |
| capabilities | 36 | 40 |
| grounding problems | 1 | **0** |
| citation problems in compilation | 0 | 0 |

By size and grounding they are equivalent. S2 is marginally cleaner.

**The induction also recovered a non-obvious procedural fact about S2 on its own.** Its graph ends with
`authorization_issued_to_landlord` and `landlord_may_file_court_action` — in a rent-increase challenge it
is the *landlord* who must bring the action after conciliation fails, the reverse of the usual direction.
The source-sufficiency survey had independently flagged that role reversal as this scope's signature
feature. Nothing in the prompt mentioned it; it came out of the ZPO passages.

## The measure that separates them

How many documents hang on exactly one process node? A document justified by three nodes cannot be removed
by resolving one of them, so a scope where every document is over-determined cannot demonstrate that
process resolution reduces the checklist.

| | documents justified by exactly one node |
|---|---|
| S1 termination | **0 of 16** |
| S2 rent increase | **3 of 8** |

## S2 demonstrates the claim; S1 cannot

Walking S2 through three states of knowledge, with the compiler recomputing the checklist each time:

| state of the case | clean chains | wrong-branch | requests | documents | justifications |
|---|---|---|---|---|---|
| nothing determined yet | 26 | 0 | 9 | 7 | 24 |
| official form valid, so the nullity branch closes | 25 | 1 | 9 | 7 | 23 |
| tenant does not challenge, so the conciliation route closes | 17 | **10** | **5** | **5** | 17 |

Closing the conciliation route removes **two documents outright** — the conciliation request and the
landlord correspondence — and converts ten chains into wrong-branch requests. The checklist shrinks from
nine requests to five *because the process resolved*, and the system can say exactly which node's
resolution removed each one.

The same walk on S1 removes nothing at all. Both behave correctly; only one is measurable.

## Consequence

**S2 is the primary benchmark scope.** S1 remains useful as a second scope for process-identification
metrics, where its richness is an advantage and its non-discrimination does not matter, but the causal
experiment — does going through the process graph improve the checklist — has to be run where a checklist
can actually change.

This was found by running the pipeline on both, not by inspecting the graphs. Choosing S1 on the strength
of the sufficiency gate's rating, which rated it strongest on source coverage, would have produced a
benchmark that could not measure the thing the paper claims.
