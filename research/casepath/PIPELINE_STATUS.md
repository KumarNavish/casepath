# Where the work stands — 2026-09-16

## The claim, as currently supportable

A source-grounded process graph produces document requirements that carry a verifiable chain back to authoritative
text, and that change when the case changes. **The second half is not yet demonstrated.** On development data the
effect is small, its interval includes zero, and the arm with the best withdrawal recall has no obligation compiler
at all.

Two things the paper can state without qualification, because they are measured:

- Every request traces to a passage fetched from Fedlex and hashed, and every quoted span verifies as a verbatim
  substring of it. The gate that enforces this caught a **fabricated statutory article** — VMWG Art. 19a, cited at
  a consolidation date Fedlex does not serve, with a fluent and sourceless quote — inside a reference contract
  authored to be authoritative.
- The direct baseline's apparent responsiveness to the case is largely noise: of the documents it changed between
  two materially different variants, **76% were ones the contract says should not have changed**.

## What is settled

| | |
|---|---|
| Authority corpus | 86 passages, OR / VMWG / ZPO / VVG, one extraction identity, hashed |
| Reference contract | 12 decisions, 11 documents, 44 of 58 quotes verbatim-verified, voted document layer |
| Corpus | 10 scenarios × exactly 5 cases = 50 clean rent-increase cases |
| Split | 4 scenarios development, 6 confirmatory and **unread** |
| Static task | saturated — 1 to 2 distinct checklists across cases; carries no claim |
| Product surface | composes the four pipeline modules and adds no logic of its own |

## Three defects found by measurement, not inspection

1. **No applicability gate.** The graph's entry node had no incoming condition, so the process assumed a rent
   increase existed and could not be told otherwise. Still open.
2. **Contradictory branch verdicts.** Alternatives out of one step were decided independently, so a claim and its
   negation could both hold and every branch stayed alive. **Fixed** at `c43bc22`; the fix visibly unfreezes the
   arm.
3. **Coverage.** 8 of 13 nodes emitted no obligation and the graph modelled the forum where abusiveness is argued
   but never the determination itself. **Repair in progress**: synthesis now requires a node for every substantive
   standard the propositions state, and obligations wherever a party must show something. Re-induction yields
   `determine_non_abusive_grounds` carrying the landlord's justification obligation — the mechanism the experiment
   was looking for. Evaluation on development pairs is running.

## One analytical error, corrected

I computed that B5's maximum achievable withdrawal recall was 0.000 and committed a document calling the primary
outcome structurally impossible. The computation pooled each node's document supply across cases when the compiler
recompiles it per case, which turns an upper bound on supply into a false lower bound on release. Development data
refuted it directly: B5 correctly withdrew two documents the computation said it never could. Corrected at
`df63478`; the wrong version is retained in history and named in the corrected document.

## Held-out data

Unread. It will be read once — after the coverage repair is evaluated on development and the preregistration is
rewritten with the changes logged, or to report a preregistered null if the repair does not move the development
picture. Not spent on a system with known, specific, in-progress defects.

## Honest assessment

The measurement apparatus is sound and has repeatedly caught real faults, including two of my own. The headline
claim is not yet earned. What would earn it is the coverage repair working on development, followed by one clean
read of the held-out scenarios — and if it does not work, the paper is a negative result with three well-diagnosed
failure modes and a verification gate that caught a fabricated law, which is worth publishing and is not what was
originally hoped for.
