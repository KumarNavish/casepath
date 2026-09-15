# Decisive result

Forty-two episodes over twenty-one families that appear in no earlier split, read once, under rules fixed
in `PRE_REGISTRATION.md` before any of these episodes existed. `openai/gpt-5.4-mini`, temperature 0, three
turns, at most two requests per turn, no retries, no plan repair. Every zero-model control is far below the
shortcut-audit thresholds. No arm suffered a single output failure except `process-only` (4) and `full` (1).

### 0. The split as executed

Recorded because the confirmatory split's plan and execution differed by one family, and that discrepancy
is itself a disclosure in this work. This split's execution matches its plan exactly:

| | planned | executed |
|---|---|---|
| episodes | 42 | 42 |
| families | 21 | 21 |
| families per domain | 7 / 7 / 7 | 7 / 7 / 7 |
| episodes per domain | 14 / 14 / 14 | 14 / 14 / 14 |
| German / English | 19 / 23 | 19 / 23 |
| conditional requirement live | 20 of 42 | 20 of 42 |

## 1. The pre-registered primary endpoint is established

**D1. State accuracy, `ctes` over `full`: +0.147, 95% CI [+0.095, +0.205], nineteen of twenty-one families
won and one lost, Holm p = 0.000.**

The confirmatory split measured +0.148 for the same comparison as an exploratory quantity. This split
measured +0.147 for it as a pre-registered one, on families the method had never seen. That is a
replication to the third decimal place, and it is the result the paper rests on.

State accuracy, `ctes` minus each comparator, twenty-one families:

| comparator | mean difference | 95% CI | won / lost | p |
|---|---|---|---|---|
| `full` (strongest baseline) | **+0.147** | [+0.095, +0.205] | 19 / 1 | 0.0000 |
| `process-only` | +0.124 | [+0.067, +0.196] | 17 / 2 | 0.0000 |
| `direct-end-to-end` | +0.120 | [+0.076, +0.164] | 18 / 3 | 0.0000 |
| `constant` (ask for everything) | +0.218 | [+0.176, +0.262] | 21 / 0 | 0.0000 |
| `ctes-ablation` (all three rules off) | +0.039 | [+0.006, +0.071] | 12 / 4 | 0.0200 |

### 1.1 The result does not come from the harness

The baselines produce malformed outputs and the method does not: over 1638 turn-records, `process-only`
failed 4 times and `full` once, while every arm in the method's family failed zero times. A failed turn is
scored with zero state accuracy, so the asymmetry flatters the method. Dropping the three episodes in which
any arm failed leaves **+0.136 [+0.084, +0.189], eighteen families won and two lost, p = 0.0000** over
thirty-nine episodes. The confirmatory split's equivalent check gave +0.135. About a tenth of the headline
is the harness; the rest is not.

The run itself was clean: 509 requests over three turns, zero truncations, zero transport failures, no
retries.

## 2. The channel cap is one rule, not three, and not the one it was named after

The compound switch was separated into three independently settable rules and each given its own arm. The
prediction registered in advance — that requiring the artifact would cost the most — is confirmed, and the
decomposition is sharper than expected.

Premature-readiness episodes, out of forty-two:

| arm | rule disabled | premature | state accuracy | readiness accuracy |
|---|---|---|---|---|
| `ctes` | none | **2** | 0.804 | 0.897 |
| `ctes-abl-levels` | support level from content, not channel | **2** | 0.804 | 0.897 |
| `ctes-abl-commitments` | believe a party's delivery promise | 1 | 0.771 | 0.913 |
| `ctes-abl-satisfaction` | an attestation may satisfy without the artifact | **11** | 0.796 | 0.857 |
| `ctes-ablation` | all three | 10 | 0.765 | 0.881 |

Each rule has a distinct and separable job:

- **The satisfaction rule carries readiness.** Removing it alone takes premature readiness from 2 episodes
  to 11, a family-paired +0.214 [+0.095, +0.357] with eight families won and **none lost**. The compound
  ablation reaches 10, so this single rule accounts for essentially the whole compound effect. It does not
  move state accuracy (+0.008, p = 0.53).
- **The commitments rule carries state accuracy.** Removing it costs +0.033 [+0.013, +0.056], ten families
  won and one lost, p = 0.0012. It does not move readiness.
- **The graded channel ordering does nothing measurable at all.** `ctes-abl-levels` is identical to `ctes`
  on state accuracy (+0.0000 [−0.007, +0.007]), on readiness accuracy, on acquired evidence, on premature
  readiness and on hearsay receipts — every paired difference is exactly zero. The only trace it leaves is
  0.048 fewer requests per family, worth +0.012 of utility.

This corrects the method's own headline. The contribution is **not** a graded lattice over channels, which
is what "channel-typed" suggests and what earlier drafts claimed. It is two binary rules, of which the
load-bearing one is: *a requirement is satisfied only when the returned artifact establishes it, never
because a party attests that it would.* The lattice is decoration. This was only visible because an
adversarial audit pointed out that the original ablation switched three things at once.

## 3. What is still not established

**D2. Readiness accuracy against the strongest baseline is null**: +0.024 [−0.056, +0.119], five families
won and five lost, Holm p = 0.58. This metric rewards a correct readiness call in both directions, and was
introduced precisely because the earlier composite charged premature readiness without rewarding correct
readiness. On it, the method and `full` are indistinguishable. The method is more conservative — 2
premature declarations against 6 — and pays for it in missed ones.

**D4. The composite utility still does not separate**: +0.135 [−0.040, +0.316] against `full`, consistent
with the confirmatory split's +0.129 [−0.011, +0.271]. Two independent splits now agree that this endpoint
does not distinguish the arms. Reported for continuity only.

**Hearsay receipts remain structural.** Every CTES-family arm records zero, and so does every zero-model
control, because the state representation cannot express a receipt for a document that never arrived. The
empirical half is unchanged: `full` records 53, `direct-end-to-end` 60, `process-only` 45, over the same
forty-two episodes, while being told the provenance rule in their prompts.

**The trivial arm still acquires as much.** `constant`, which requests every outstanding document and never
declares readiness, acquires 31.17 units of critical evidence against the method's 31.08 and has zero
premature declarations. It loses on state accuracy by 0.218, the largest gap in the table, winning no
families at all, and it issues 240 requests against 161.

## 4. Summary of the claim

On a fresh, singly-read arena the method is right about the state of the evidence 0.147 more often than the
strongest baseline built from the same model, told the same rule in prose, on nineteen of twenty-one
families. That advantage comes from the typed representation and the deterministic calculus. Separately,
one binary rule inside that calculus — the artifact must be on file before a requirement counts as
satisfied — cuts premature readiness from 11 episodes to 2 without losing a single family. Neither the
composite utility nor a symmetric readiness score separates the method from the strongest baseline, and
both negatives are reported.
