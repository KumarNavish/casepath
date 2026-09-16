# Reproducing this

Everything below is in the repository. Nothing depends on a service that could change its answer without changing
its hash, except the model itself, which is pinned by name and provider.

## Fixed inputs

| what | where | how it is pinned |
|---|---|---|
| authority passages | `casepath-api/casepath_api/corpora/authority/swiss-authority-bundle-v1.json` | per-passage SHA-256, per-act document SHA-256, source URL, consolidation date, extraction identity |
| propositions | `research/casepath/INDUCTION_S1_propositions.json` | each carries the exact quote that passed the gate |
| induced graph (used for all reported experiments) | `research/casepath/INDUCTION_S2_graph.json` | induced once, reused unchanged |
| re-induced graph (development only, excluded from the confirmatory read) | `research/casepath/INDUCTION_S2_graph_v2.json` | |
| reference contract | `research/casepath/reference_contracts/rent_increase.json` | full audit block: every dropped quote, every vote count |
| corpus split | `research/casepath/splits/rent_increase_scenario_split.json` | frozen at commit `e28f1ed`, before any confirmatory case was read |

## Fixed procedure

- **Model**: `openai/gpt-5.6-terra`, temperature 0, `max_tokens` 8000, provider pinned to `openai` via OpenRouter.
  All arms share these; nothing is tuned per arm.
- **Method frozen** at commit `c43bc22`, before the preregistration was written.
- **Analysis scripts committed before the data existed**: `confirmatory_analysis.py` at `31a3397`, hardened at
  `8aacbe4`, while the confirmatory runs were still producing output.
- **Bootstrap** seed 20260916, 5000 draws, resampling scenarios.

## The order things happened, which is the part that matters

Preregistration is only worth anything if the sequence is checkable. The git history is the record:

| commit | what |
|---|---|
| `c43bc22` | method frozen (branch-consistency fix) |
| `e28f1ed` | corpus split frozen; confirmatory scenarios sealed |
| `ee6f266` | preregistration written |
| `68f0448` | amendment A1 — probe changed from `e03` to `e07`, on a computation from the contract alone, before any result |
| `202efeb` | development result recorded |
| `4709d9b` | amendment A3 — primary changed to `b3` vs `b1`, **declared** because it was found on development data |
| `31a3397`, `8aacbe4` | confirmatory scoring script committed while the data was still being generated |
| *(this run)* | the single confirmatory read |

Two amendments are logged rather than hidden. A1 was made for a structural reason computable in advance and
corrects an error in my own preregistration. A3 changes the primary comparison after seeing development data,
which is exactly the move that invalidates a claim if undeclared — so it is declared, and the original primary is
reported alongside as not separating rather than dropped.

## What cannot be reproduced exactly

Model outputs. Temperature 0 with a pinned provider is close to deterministic but is not guaranteed across
serving-stack changes. Every reported artifact — graphs, contracts, chains, per-case scores — is therefore
committed, so the *analysis* reproduces exactly from the committed intermediates even where regeneration would
drift.

## Re-running

    cd casepath-api
    python research/casepath/development_analysis.py   # tables from committed development intermediates
    python research/casepath/confirmatory_analysis.py  # the single held-out read

Both read committed JSON and make no network calls.
