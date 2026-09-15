# Failure analysis and negative results

## Where CTES loses or fails to separate
- **Against process-first + deterministic verifier (`full`)** the family-level bootstrap interval includes
  zero in 4 of 6 model × split configurations (Opus hidden +0.278 [-0.049, +0.569]; Opus transfer
  +0.158 [-0.075, +0.383]; mini hidden +0.243 [-0.042, +0.542]; mini transfer +0.158 [-0.108, +0.358]).
  CTES wins on the point estimate everywhere and on every safety metric, but with 5–8 families the study
  is not powered to separate them.
- **Against the direct planner in the transfer domain with Opus** the difference is +0.083 [-0.100, +0.275].
  A strong model in that domain simply does not close early, so the safety benefit has nothing to convert.
- **Acquired evidence in transfer** is lower than direct (0.583 vs 0.750) while burden is far lower
  (2 vs 12) and requests fewer (23 vs 32): CTES trades coverage for restraint there.

## Attempted improvements that did not work (preserved)
- **Hedged spare request slot.** When a single authenticated export covers every open requirement, spend the
  unused second slot on a disjoint alternative route. Implemented, tested, and run on all three splits with
  Opus: neutral on hidden (+0.639 → +0.618) and it *raised the ablation more than the candidate* on dev
  (CTES +0.625 → +0.556, ablation +0.462 → +0.583). Reverted to an off-by-default flag
  (`hedge_spare_slot`), and the frozen method is the unhedged one.
- **Strict atom validation.** The first contract rejected the whole extraction on any invalid atom. With a
  small model this killed 21/72 dev, 3/36 hidden and 12/30 transfer trajectories. Replaced by conservative
  dropping, which removed every failure (0 in all splits) and is reported as part of the method.

## Protocol deviations, stated plainly
- **The hidden split was read twice.** It was first opened with the strict-parse method, then re-run with
  the final fail-soft method after the small-model experiments exposed the brittleness. The second reading
  is a confirmatory re-run, not an untouched first look. Only the CTES arms were re-run; every baseline
  number comes from the first, untouched pass.
- **The two direct prompts carry a format-only note.** The frozen E76 prompts never show the row shape of
  `document_states`; without the note a strong model emits a map and the arm fails the validator on every
  case. The note adds no task semantics and is disclosed in `BASELINES.md`.
- **Baselines keep their published fail-closed contract** while CTES parses atoms conservatively. This is an
  asymmetry in favour of CTES on robustness; the per-arm failure counts are reported in every table so the
  reader can see it (`full` and `process-only` lose 1–3 records with the small model; CTES loses 0).
- **The episode verifier flagged 30 of 46 episodes**, almost all from an over-broad rule of mine (it demanded
  that the exclusion paragraph also state facts to establish) or from benign phrasings such as a customer
  offering to send a record they hold. The decisive guard — that no paragraph claims a document is attached
  or enclosed — passes in all 46 episodes by exact string check. The full verifier output is retained.

## Residual limitations
- 8 dev / 6 hidden / 5 transfer families is small; all intervals are wide.
- The arena is synthetic: episodes are generated from a latent specification and written by a model. The
  real-corpus study is on genuine intake packets but is small (16 claims) and text-only.
- The product corpus study passes PDF text but not page images, so an image-only attachment would be
  invisible to the reader; the corpus attachments checked all carried text views.
- `A` (acquired critical evidence) and `state accuracy` move in opposite directions in transfer; the frozen
  utility does not credit state accuracy, which is where CTES is strongest (0.919 vs 0.752).
