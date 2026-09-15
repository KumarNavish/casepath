# Frozen predictions and decision criteria — Arena v1 (written before any model arm ran on the arena; 2026-09-14)

## Arena
Arena v1 episodes (`casepath-api/arena_v1_data`): dev = 24 episodes (heating_defect 4 families × 3, termination_payment 4 × 3);
hidden = 12 episodes (3 + 3 new families, same two domains); transfer = 10 episodes (rent_increase, 5 families × 2,
never used for any development decision). Identities frozen in DEV_IDS.txt / HIDDEN_IDS.hash before any arm ran.
Each episode: 3 decision turns, ≤2 requests per turn, action-conditioned returns (frozen E76 mechanics + activation
rules + unavailable artifacts). Model for every model arm: Claude Opus via the Claude Code Agent tool
(same model, same actor JSON, one call per arm-turn; the ctes and ctes-ablation arms share one call).

## Primary utility (per episode, computed by the frozen evaluator, no post-hoc changes)
U = A − P − 0.25·B, where
 A = acquired_critical_evidence at the final turn (fraction of critical requirements satisfied by actually returned artifacts),
 P = 1 if the arm declared readiness at any turn while the reference was not ready (premature_readiness), else 0,
 B = (unnecessary_unique_requests + repeat_requests) summed over turns, capped at 4.
Family-level aggregation: mean U over episodes within a family, then mean over families (equal family weight).
Secondary endpoints reported: state accuracy, checklist F1, next-action accuracy, replanning accuracy, readiness accuracy,
exact provenance, hearsay_receipts, total requests, output tokens/characters.

## Shortcut-audit admission thresholds (dev)
The arena is admitted only if every zero-model control (constant, static-checklist, random, keyword-router,
domain-compiler, family-mode) has family-weighted U ≤ 0.35 and t0 state accuracy ≤ 0.75, and the direct strong-model
baseline leaves headroom: family-weighted U ≤ 0.85. Otherwise the arena is repaired before any method comparison.

## Candidate: channel-typed evidential state (CTES); ablation = same extraction, no channel cap
Predictions (dev, family-weighted):
 P1  CTES has P = 0 on every episode (no premature readiness) — structural.
 P2  CTES hearsay_receipts = 0 on every turn; direct, process-only, full and the ablation have hearsay_receipts > 0
     on episodes containing a possession_report or content_quote motif (rate > 0.2 of such episode-turns).
 P3  CTES U exceeds direct-end-to-end, process-only, full and ctes-ablation U by ≥ 0.10 with the paired
     family-level sign test favouring CTES in ≥ 6 of 8 dev families.
 P4  CTES total requests ≤ direct total requests + 1 per episode (the gain is not bought by requesting more).
 P5  ctes-ablation loses at least half of the CTES − direct gain (mechanism-specific).
Kill: P3 false (no ≥0.10 gain over the best baseline) or P5 false (ablation retains the gain) → CTES is closed.
