# Strong-model replay of the E76 action-conditioned pilot (diagnostic, 2026-09-14)

Setting: the frozen E76 harness (`casepath-end-to-end-loop-20260912`: evaluation.py, method.py, EVALUATION_DRAFT.json,
3 authored public-development carriers 007/022/043, 3 turns, action-conditioned returns, request limit 2, no repair,
no retry). The provider call was replaced by Claude Opus subagents inside this Claude Code session (label
`claude-opus-subagent`; no provider receipts, temperature/seed not controllable). Every request/answer pair is retained
under `e76_replay/run_opus_v2/pending/turn-*/…` (system.txt, user.json, answer.json). RESULT.json sha256
7491e2fd…e061; driver sha256 9c586fcb…16a7.

Disclosed deviation: the two direct prompts (direct-end-to-end, document-first) never show the row shape of
`document_states`; the strong model emitted a map and both arms failed the frozen validator on all three carriers
(run `run_opus_aborted_pending`, retained). The replay was restarted with a semantics-neutral shape note appended to
those two prompts only (`FORMAT_NOTE` in the driver). The shared-ledger requests are byte-identical between runs and
their turn-0 answers were reused. This is a diagnostic, not the frozen experiment.

## Aggregate (9 records per arm = 3 carriers × 3 turns; Opus replay / original gpt-5.4-mini E76)

| arm | crit. evidence recall | unnecessary rate | state acc. | next-action acc. | readiness acc. | exact provenance | unnecessary unique req. | repeats |
|---|---|---|---|---|---|---|---|---|
| direct-end-to-end | 0.79 / 1.00 | 0.08 / 0.25 | 0.80 / 0.58 | 0.67 / 0.67 | 0.89 / 1.00 | 0.84 / 0.63 | 1 / 3 | 1 / 3 |
| document-first | 0.64 / 1.00 | 0.10 / 0.29 | 0.73 / 0.57 | 0.67 / 0.78 | 0.78 / 1.00 | 0.74 / 0.70 | 1 / 3 | 1 / 3 |
| process-only (ledger, raw action) | 0.79 / 0.94 | 0.00 / 0.00 | 0.81 / 0.86 | 0.78 / 0.89 | 0.89 / 1.00 | 0.50 / 0.36 | 0 / 0 | 0 / 0 |
| full (ledger + compiled action) | 0.81 / 0.71 | 0.00 / 0.36 | 0.79 / 0.81 | 0.56 / 0.56 | 0.89 / 0.78 | 0.43 / 0.41 | 0 / 4 | 0 / 4 |
| static-checklist | 0.30 | 0.43 | 0.62 | 0.33 | 0.78 | 0.00 | 4 | 0 |
| random | 0.26 | 0.44 | 0.67 | 0.33 | 1.00 | 0.00 | 7 | 0 |

(Recall means exclude turns with no active critical requirement; the original E76 reported acquired critical evidence
7/8 for direct and full.)

## What changed with a strong model
1. The E76 failure classes that motivated the "compile the ledger" mechanism largely disappear for the *full* arm
   (4 → 0 unnecessary/repeat requests, readiness accuracy 0.78 → 0.89) and shrink for *direct* (3 → 1).
2. The structured arms show no separation from direct on critical recall (0.79–0.81 vs 0.79) or readiness (0.89 for
   all three). The only structural edge left is one avoided repeat request on 022 (direct re-requested the bank
   export while its automatic confirmation was pending; the ledger arms requested the notice documents instead).
3. A failure shared by all four model arms appears on carrier 043, turn 2: every arm marked the signed notice
   (D043-A) as `received` because the customer wrote that they had *found* the last rent notice, then declared
   readiness although the document was never requested or returned. This is a source-semantics error (a statement
   about a document is not the document) that neither prompting order nor the deterministic ledger compiler touches.
4. Remaining state disagreements are convention-level (`insufficient` vs `missing` before any return; `pending`
   for an inactive future obligation) and are shared across arms.

## Interpretation (n = 3 authored carriers; no statistical claim)
With a strong model, the acquisition-time mechanism family tested by the loop (decision ledger + compiled
requests/readiness) has no measurable advantage over a direct planner on these carriers; the residual errors are
semantic sufficiency/relevance judgments that all arms share. This does not establish equivalence at scale, and it is
not a frozen or receipted experiment. It does say that the premise "strong models still need structured obligation
state to avoid E76-type errors" is not supported on the only longitudinal data the project has.
