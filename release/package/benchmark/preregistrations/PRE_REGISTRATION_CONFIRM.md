# Confirmatory split — pre-registration

Written **before** any confirmatory episode text existed and before any arm was run on it.
Method, arms, evaluator and analysis are frozen at the hashes below and are not touched again.

## 1. Why this run exists

`FINAL_SCIENTIFIC_DECISION.md` left exactly two boxes open.

- **B1 — superiority over the strongest baseline is not established.** Against `full`
  (process-first decomposition plus an explicit verifier step), 4 of 6 family-paired 95% intervals
  included zero. The mechanism result was clear; the utility gap was not.
- **B2 — the hidden split was read twice.** Once under strict atom validation, once after the
  fail-soft parsing fix. A split read twice is a development split, whatever it is called.

One fresh split answers both: it is larger, so the family-paired interval has usable width, and it is
read exactly once, under a rule fixed in advance.

## 2. What is frozen

| file | sha256 |
|---|---|
| `casepath_api/evidential_channel_v1.py` | `d8170df1b179740f393757c5bd4e553fbe39e8d6e86d57cd97c05b1b80a87d72` |
| `casepath_api/arena_v1/arms.py` | `2916ca8c2ae50180838ab90ad3305b49cbaf7be7251b8df1d3b0146688378256` |
| `casepath_api/arena_v1/evaluation.py` | `96fb4225f2834c24ad64c776693d2b144bc1fc400fcef3a26d223adf04cd6ff5` |
| `casepath_api/arena_v1/runner.py` | `9f5d8be43fdcf8bb7b0a96600b64495b5b5edb8be113f878d332d4e89d782c81` |
| `casepath_api/arena_v1/analyze.py` | `01d6ae5ea33fc3414823bf3af41f6120be69fa6e5217256876141b5eb5a74627` |
| `arena_v1_data_confirm/latents.json` | `d9b4a3ba067beae49ab4a0e49a3c9bde6ef21c972f67d6c4fdf3558cb889d036` |

The first five are byte-identical to the hashes recorded in `REPRODUCIBILITY_MANIFEST.json` for the
dev / hidden / transfer runs. Nothing about the method changes for this run.

`generator.py` is the one file that moved. It moved twice: to
`c6b9480d6989217c0eb4f1bde15db8a59f6889b3958e92651a85bc6d495c2e29` for the first twenty families and then
to `f5e00ff23eee2ea1dca1dbdaf339be1863ecb16ae915a240166e7dbcb85964de` for the twenty-one added under
Amendment 2. Both changes are appended family seeds and nothing else; re-assembling the three original splits
from the unchanged latents reproduces `cases_dev.json`, `cases_hidden.json` and `cases_transfer.json`
byte for byte (`eee7b0996ecf…`, `5229236adc08…`, `a174da29ddcf…`) after each change, and after the second
change the first confirmatory half reproduces byte for byte as well (`6c54fd6ca72f…`).

## 3. The confirmatory split

Forty episodes over twenty families that appear in no earlier split, drawn from the same three domains
and the same latent sampler: heating defect (7 families), termination and payment (7), rent increase (6),
two episodes each. Language is sampled per episode as before (17 German, 23 English) and the conditional
requirement is live in 22 of 40.

Episode prose is written by `openai/gpt-5.4-mini`, the same model the arms run on, and checked by
`openai/gpt-5.6-terra` against the decisive semantic properties only. Gold labels never depend on wording;
they come from the latent specification and the returned-source identities.

### 3.1 The writer choice, and the check that guards it

Using the evaluated model as its own episode writer invites one objection: a model may find its own
phrasings unusually legible, or share a blind spot with itself. The objection has a direction worth
stating. The channel cap never reads content — the support level of an atom is fixed by the slot the
bytes arrived in, which the harness controls and the prose cannot touch. Only the content-reading arms
(`direct-end-to-end`, `process-only`, `full`, `ctes-ablation`) can gain or lose from a shared-family
writer. So the confound, if it exists, moves the baselines, not the method, and its sign is not knowable
in advance: self-legible prose would help the baselines and shrink the gap, self-opaque prose would widen
it.

That is an empirical question, so it is settled empirically rather than argued. Twenty-six of the forty episodes,
covering thirteen of the twenty families, also exist in a second, independently written version produced
by `anthropic/claude-sonnet-5`
from the identical latent specification, held at `texts_sonnet.json` beside each episode. They were
written before this amendment and before any arm was run. The writer-swap check is pre-specified here:

- **H4 (writer robustness).** On the thirteen families (twenty-six episodes) present in both versions,
  the sign of
  `U(ctes) − U(full)` and the sign of `U(ctes) − U(ctes-ablation)` agree between the two writers, and
  `ctes` records zero hearsay receipts under both.
  *Confirmed* if all three hold. If any fails, the writer is reported as a material factor and the
  primary result is reported as writer-dependent.

The swap set runs four arms only (`direct-end-to-end`, `full`, `ctes-ablation`, `ctes`); the zero-model
controls are deterministic and are run on both versions for free.

## 4. Evaluated arms

Six zero-model controls (`random`, `static-checklist`, `constant`, `keyword-router`, `domain-compiler`,
plus the family-mode leakage probe) and five model arms: `direct-end-to-end`, `process-only`, `full`,
`ctes-ablation`, `ctes`. Model: `openai/gpt-5.4-mini`, temperature 0, `max_tokens` 8000, provider pinned
with fallbacks disabled, three turns, at most two requests per turn, no retries and no plan repair.
Byte-identical requests are shared across arms, as in every earlier run.

`full` is the strongest baseline: the same model, process-first decomposition, and an explicit
verification step over content. `ctes-ablation` is CTES with `channel_cap=False` — same call, same atoms,
same calculus, support level taken from content rather than from the channel.

## 5. Hypotheses and decision rules, fixed in advance

Primary endpoint is the family-weighted utility `U = A − P − 0.25·B`, and the test statistic is the mean
family-level paired difference with a 5000-sample bootstrap 95% interval, exactly as `analyze.paired`
already computes it. Twenty families enter each paired test.

- **H1 (mechanism).** `ctes` yields zero hearsay receipts; `ctes-ablation` yields more than zero.
  *Confirmed* if `ctes` records 0 hearsay receipts across all 40 episodes and `ctes-ablation` records ≥ 5.
- **H2 (strongest baseline).** `U(ctes) − U(full)` is positive.
  *Established* only if the 95% interval excludes zero after Holm correction across H2 and H3.
- **H3 (the channel cap carries the effect).** `U(ctes) − U(ctes-ablation)` is positive.
  *Established* only if the 95% interval excludes zero after Holm correction across H2 and H3.

Secondary, reported but not decisive: premature-readiness episodes, missed readiness, unnecessary and
repeat requests, and the paired comparisons against `direct-end-to-end` and `process-only`.

## 6. Stopping rule

The split is read once. Whatever the intervals say is what gets reported: if H2's interval includes zero,
the paper says superiority over the strongest baseline is not established on this arena and reports the
mechanism result as the contribution. No re-run, no added episodes, no post-hoc metric, no arm change,
no writer change. Any later change to this split is a new, separately named run and is disclosed as such.


## 7. Amendment log

**Amendment 1, before any arm was run and before the primary episode texts existed.** The writer was
changed from `anthropic/claude-sonnet-5` to `openai/gpt-5.4-mini`, and H4 (writer robustness) was added
with the twenty-six already-written Sonnet episodes (thirteen families) as the swap set. H4 is explicitly
a weaker test than H2 and H3: thirteen families is enough to catch a writer effect that reverses a sign,
and not enough to certify that no smaller writer effect exists. It is reported as what it is. Reason: the original choice spent
roughly eighteen times more per episode to buy an argument, where a matched writer-swap buys the same
assurance as evidence. Recorded here rather than silently applied, because an unlogged amendment to a
pre-registration is worth nothing.

**Amendment 2, before any confirmatory result was produced or read.** The confirmatory split is extended
from twenty families (forty episodes) to forty families (eighty episodes), all newly drawn and none
appearing in any earlier split. Nothing else changes: the same method hashes, the same arms, the same
model, the same metric, the same decision rules, the same single read.

Reason, computed from the earlier `gpt-5.4-mini` runs while the first forty confirmatory episodes were
still executing and before any `RESULT.json` existed (`POWER_ANALYSIS.json`): the family-level standard
deviation of `U(ctes) − U(full)` is about 0.374, so twenty families can only detect a mean difference of
about 0.24, while the plausible true effect is 0.15 to 0.25. Twenty families would therefore have
reproduced the earlier inconclusive answer for want of families rather than for want of an effect. Forty
families detect about 0.17.

This is a change of sample size decided from prior data and from no confirmatory data, and it moves the
decision threshold against the method, not for it: a wider net around zero is harder to escape, not
easier. The extension costs roughly two and a half dollars of model time, which is the only reason it is
available at all — at the price of the frontier model used earlier in this project the same extension
would have cost about fifty-five dollars and the underpowered answer would have had to stand.

H1 and H4 are unaffected in form; their counts and signs are computed over all eighty episodes.
