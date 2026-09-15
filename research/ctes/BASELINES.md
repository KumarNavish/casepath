# Baselines (frozen with PREDICTIONS.md)
B0 controls: constant, random, static-checklist (E76 zero-model arms), keyword-router, domain-compiler (K0 analogue: knows the
domain pack's critical routes, reads nothing), family-mode (fits the modal t0 gold plan per family on dev gold — leakage probe).
B1 direct-end-to-end: frozen E76 direct prompt + format-only shape note; one call per turn; same actor JSON.
B2 document-first: omitted (E76 and the replay showed it ≈ direct; saves one call per turn).
B3 process-only: frozen E76 shared decision-ledger prompt, raw action.
B4 full: B3's proposal + frozen E76 deterministic compiler (project_full) — existing process-first + verification.
B5 strongest nearest work = decompose-then-verify without channel typing: identical extraction call as CTES (per-unit
   attestations, mentions, readability, requirement map) aggregated by the same calculus with the channel cap removed
   (every attestation counts at the observed level; party-reported promises honoured). This is also the mechanism ablation.
Matching: same model, same actor JSON (sources, catalog, static checklist, own prior plan), one model call per arm-turn,
same action space and request limit, same environment, no retries, no repair, no evaluator information in prompts.
