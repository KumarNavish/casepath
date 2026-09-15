# Decisive split — pre-registration

Written **before** any episode of this split existed and before any arm was run on it.

## 1. Why this run exists

The confirmatory run answered its pre-registered question with a negative. On a composite utility
`U = A − P − 0.25·B` the method did not separate from the strongest baseline (+0.129, CI [−0.011, +0.271])
or from its own ablation. The quantity that did separate — **state accuracy**, whether the agent is right
about the state of each document — was exploratory, and a headline resting on an exploratory metric is not
a result. This run pre-registers it.

The confirmatory run also could not attribute its mechanism effect, because `channel_cap=False` turned off
three rules at once. Those rules are now separable and each gets its own arm.

## 2. What is frozen

| file | sha256 |
|---|---|
| `casepath_api/evidential_channel_v1.py` | `bb355763b7b79c5134844ddef57f6cf419d16a0a4820561ca221daae92e18394` |
| `casepath_api/arena_v1/arms.py` | `2916ca8c2ae50180838ab90ad3305b49cbaf7be7251b8df1d3b0146688378256` |
| `casepath_api/arena_v1/evaluation.py` | `96fb4225f2834c24ad64c776693d2b144bc1fc400fcef3a26d223adf04cd6ff5` |
| `casepath_api/arena_v1/runner.py` | `fde1548ecad8aa576534f48f87829480046887badcfb8c3308d4f3bbf2b93503` |
| `casepath_api/arena_v1/analyze.py` | `01d6ae5ea33fc3414823bf3af41f6120be69fa6e5217256876141b5eb5a74627` |
| `casepath_api/arena_v1/generator.py` | `fde5e815aa56bd5a1298a0c17c7c1f2e177a479701fcbdf2c5f2304742275ed2` |
| `arena_v1_data_decisive/latents.json` | `1d3679612fba93cd34aadff1dc27c6160a42371c1516f94c726d4e54b27184de` |

`arms.py`, `evaluation.py` and `analyze.py` are byte-identical to every earlier run: the baselines, the
scorer and the statistics are untouched.

`evidential_channel_v1.py` and `runner.py` changed, and the change is a refactor with no behavioural
delta. The compound `channel_cap` switch now delegates to three named rules — `levels_from_content`,
`believe_party_commitments`, `satisfy_by_attestation_alone` — each defaulting to `not channel_cap`, so
`channel_cap=True/False` behaves exactly as before. This was verified by replaying **all 162 frozen
final-turn CTES and ablation decisions** from the confirmatory runs through the refactored calculus: 162 of
162 reproduce the stored document states, requests, next action and readiness identically.

`generator.py` gained twenty-one appended family seeds and nothing else; the three original splits still
reassemble byte-identically (`eee7b0996ecf…`, `5229236adc08…`, `a174da29ddcf…`).

## 3. The split

Forty-two episodes over twenty-one families appearing in no earlier split, fourteen per domain across
heating defect, termination and payment, and rent increase. Nineteen German, twenty-three English; the
conditional requirement is live in twenty of forty-two. Episodes are written by `openai/gpt-5.4-mini` and
checked by two independent verifier families, as in the confirmatory run, and the split is admitted only if
the shortcut audit passes.

## 4. Arms

Unchanged zero-model controls, and the model arms `direct-end-to-end`, `process-only`, `full`, `ctes`,
`ctes-ablation`, plus three new arms that each disable exactly one rule:

| arm | rule disabled |
|---|---|
| `ctes-abl-levels` | support level read from content instead of from the channel |
| `ctes-abl-commitments` | a delivery promise reported by a party is believed |
| `ctes-abl-satisfaction` | an attestation alone can satisfy a requirement, with no artifact on file |
| `ctes-ablation` | all three at once, as before |

Model `openai/gpt-5.4-mini`, temperature 0, 8000 output tokens, provider pinned, three turns, at most two
requests per turn, no retries, no plan repair, byte-identical requests shared across arms.

## 5. Hypotheses, fixed in advance

Family-paired differences over twenty-one families with a 5000-sample bootstrap 95% interval, as
`analyze.paired` already computes. **Primary endpoint: state accuracy.**

- **D1 (primary).** `state_accuracy(ctes) − state_accuracy(full) > 0`.
  *Established* if the 95% interval excludes zero.
- **D2 (readiness, symmetric).** `readiness_accuracy(ctes) − readiness_accuracy(full)`, reported two-sided.
  This metric rewards a correct readiness call in both directions, which the confirmatory run's utility did
  not, and it is the fix for the arm that never decides and is never punished.
- **D3 (attribution).** Premature-readiness episodes for `ctes` against each of the three single-rule
  ablations. The rule whose removal costs the most carries the channel cap's effect. Pre-specified
  prediction, recorded before the data: `ctes-abl-satisfaction` costs the most, because requiring the
  artifact rather than accepting an attestation is the structurally largest of the three.
- **D4 (continuity).** The composite utility `U`, reported against `full` and `ctes-ablation` for
  comparability with the confirmatory run. **Not primary, and not a gate on anything.**

Holm correction across {D1, D2}. D3 and D4 are descriptive and carry no claim of significance.

## 6. Power, computed before the run

From the confirmatory run, the family-level standard deviation of `state_accuracy(ctes) − state_accuracy(full)`
is 0.156, so twenty-one families detect a difference of about **0.097** at 80% power. The effect observed on
the confirmatory split was 0.148, and 0.135 with failed-output episodes dropped. This design is therefore
powered for the effect it is testing, which the composite-utility design was not: there the standard
deviation was 0.374 against an effect near 0.13, and forty-one families were still not enough.

For D3 the corresponding standard deviation is 0.082, giving a detectable difference of about 0.051.

## 7. Stopping rule

The split is read once. If D1's interval includes zero, the paper reports that state accuracy is not
established either, and the contribution reduces to the design property plus the product measurements. No
re-run, no added episodes, no new metric, no arm change. Any later change is a new, separately named run.
