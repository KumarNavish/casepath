# Reproducing the paper

Everything below runs from the repository root. Nothing needs a GPU. The only external dependency is an
OpenRouter key for the steps that call a model; every analysis step is deterministic and offline.

## 0. Environment

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r casepath-api/requirements.lock
export CASEPATH_OPENROUTER_KEY_FILE=~/.config/casepath/openrouter.key   # chmod 600, never logged
```

## 1. Verify the package matches the code that produced it

```bash
cd release/package && shasum -a 256 -c SHA256SUMS && cat MANIFEST.json
```

`MANIFEST.json` names the exact repository commit. `missing_inputs` must be empty.

## 2. Reproduce every number without calling a model

The recorded plans and metrics for every arm on every split are in `benchmark/raw_results/*/RESULT.json.gz`.
All statistics in the paper are computed from these, so the full analysis reproduces offline:

```bash
python release/reproduce_analysis.py
```

It regenerates each decision file and diffs it against the committed one. Exit code 0 means every
pre-registered and exploratory number in the paper was reproduced from the raw records.

## 3. Re-run the arms against a provider

Only needed to reproduce the raw records themselves. Costs real money; the per-split figure is in
`COST_ACCOUNTING_FINAL.json`.

```bash
# one split, one actor model, all arms
release/run_split.sh benchmark/data/submission openai/gpt-5.4-mini openai /tmp/rerun-mini
```

The episodes, the gold, the arms, the evaluator and the analysis are all frozen in this package, so a
re-run differs from the committed records only in what the provider returns.

## 4. Regenerate the benchmark from scratch

Only needed to audit the generator. The latents are deterministic from their seeds; the prose is not, so a
regenerated split will have different wording and identical gold.

```bash
python -m casepath_api.arena_v1.write_episodes --data <dir> --workers 10     # renders prose
python -m casepath_api.arena_v1.assemble       --data <dir> --out <dir>/frozen
python -m casepath_api.arena_v1.shortcut_audit --cases <dir>/frozen/cases_*.json --out <dir>/SHORTCUT_AUDIT.json
```

A regenerated split must pass the shortcut audit before it is usable.

## 5. Reproduce the product claim

```bash
cd casepath-api && python -m pytest tests/ -q -k "artifact_gate or evidential or agent_work or arena"
python -m casepath_api.arena_v1.product_corpus_study \
  --with-attachment 45 --message-only 105 --model openai/gpt-5.4-mini --provider-only openai \
  --workers 10 --assets /tmp/assets --out /tmp/corpus.json
```

The second command reproduces the 150-claim binding-rate study on the shipped corpus. Note this measures
how often the rule *binds*, not production accuracy; the paper says so.

## 6. The full product suite

```bash
cd casepath-api && python -m pytest tests/ -q
```

Seven failures in `tests/test_cli_v1.py` predate this work and are unrelated to it: they concern adapter
source-drift detection and a CLI byte cap. `release/RELEASE_TEST.md` records them and gives the clean
target that must print PASS.
