# CTES — Channel-Typed Evidential State

Research contribution developed on, and integrated into, this CasePath checkout.

| file | content |
|---|---|
| `METHOD.md` | the method, its formal statement, and what it adds beyond the shipped product |
| `NOVELTY_AUDIT.md` | operation-level comparison, constructive reduction attempt, why it fails |
| `CLOSEST_WORK.md` | primary sources checked by operation |
| `PREDICTIONS.md` | primary utility, admission thresholds and the five predictions, frozen before any arm ran |
| `BASELINES.md` | the six controls and four baselines, and the matching rule |
| `TRANSFER_PROTOCOL.md` | what is frozen and what may change in fixed-core transfer |
| `DEV_REPORT.md`, `MAIN_RESULTS.json` | every arm on every split for both model tiers |
| `FAILURE_ANALYSIS.md` | losses, failed improvements, protocol deviations |
| `FINAL_SCIENTIFIC_DECISION.md` | what the evidence supports and what it does not |
| `COST_ACCOUNTING.json` | every provider call and dollar |
| `REPRODUCIBILITY_MANIFEST.json` | code, data, prompt and run hashes |
| `PRODUCT_CORPUS_STUDY.json` | the gate on 16 real 150-claim intake packets |
| `runs/` | per-run `RESULT.json.gz` and the analysis outputs |
| `LEDGER.md`, `STATE_CHECKSUM…`, `REDUCTION…`, `RESULT_F1…`, `RESULT_E76…`, `PILOT_NOTE.md` | the closed directions that preceded this one |

## Code in this checkout
- `casepath-api/casepath_api/agent_work/evidential_channel.py` — the channel rule for the six-role workflow,
  gated in `agent_work/runtime.py::_tool_propose_document_requirement`.
- `casepath-api/casepath_api/evidential_channel_gate_v1.py` — the same rule inside
  `native_live_workspace_v1.decode_provisional_proposal`, behind `CASEPATH_EVIDENTIAL_CHANNEL_V1=1`.
- `casepath-api/casepath_api/evidential_channel_v1.py` — the standalone calculus used by the arena arms.
- `casepath-api/casepath_api/arena_v1/` — arena generator, evaluator, arms, runner, transport, analysis.
- `casepath-api/arena_v1_data/` — frozen episodes, split identities, shortcut audit, manifests.
- tests: `tests/test_evidential_channel_agent_work.py`, `tests/test_evidential_channel_v1.py`,
  `tests/test_evidential_channel_gate_v1.py`, `tests/test_arena_v1.py`.

## Reproduce
```bash
cd casepath-api
python -m casepath_api.arena_v1.shortcut_audit --cases arena_v1_data/frozen/cases_dev.json --out /tmp/audit.json
export CASEPATH_OPENROUTER_KEY_FILE=~/.config/casepath/openrouter.key
python -m casepath_api.arena_v1.runner init --run /tmp/run --cases arena_v1_data/frozen/cases_hidden.json \
  --case-ids arena_v1_data/HIDDEN_IDS.txt --arms ctes,ctes-ablation,direct-end-to-end,full
python -m casepath_api.arena_v1.run_turn --run /tmp/run --turn 0 --model openai/gpt-5.4-mini --provider-only openai
python -m casepath_api.arena_v1.runner step --run /tmp/run --turn 0     # repeat for turns 1 and 2
python -m casepath_api.arena_v1.analyze --run /tmp/run --out /tmp/results.json
```
A full small-model matrix over all three splits costs about USD 2.
