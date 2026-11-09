# Work log: CasePath TMIS paper (Claude session, 2026-11-09)

Newest entries at the bottom. Times are UTC.

## 2026-11-09 16:55 — Start
- Goal: rework the ICLR CasePath paper into a TMIS paper centred on the latest
  CasePath agent; address all three ICLR reviews and Joe's comments; run new
  decisive experiments.
- Base: `aa4fb25` (head of `claude/casepath-internal-20261027`), which contains
  the agent-native redesign, the autonomous controller (interpret -> verify ->
  admission gates -> causal process engine) and the internal-pilot packaging.
- `main` could not be fast-forwarded: the repository ruleset requires a pull
  request, the "CasePath regression" check and CodeQL. No PR was opened
  (awaiting the owner's decision). This work lives on branch
  `claude/casepath-tmis-paper-20261109`.
- Model for new runs: `openai/gpt-6.1-terra` via OpenRouter, used sparingly
  (owner's instruction). CPU-bound analyses run on sciCORE (`scicore-fast`).
- Inputs reused: Study A theft pairs (`data/casepath-theft-pairs`), Study B
  tenancy claims (`data/casepath-tenancy-claims`), the ICLR reproducibility
  archive (frozen original predictions and judgments).
