# Study 3: one command for the confirmatory run

This folder holds the driver that runs every design of `analysis/study3_spec.json` on both regimes. It writes
exactly the files `analysis/study3.py` reads. Nothing here changes the runners in `harness/product/` or
`harness/v2/`; it imports them.

```
CASEPATH_PRODUCT=<product worktree> <venv>/bin/python harness/study3/run_all.py \
    --data fresh|fresh2 --label L [--designs a,b,…|all] [--k 3] [--limit N] [--cap-usd X] [--workers 6]
python3 analysis/study3.py --data <data> --label L
```

Run it with the virtualenv that has `httpx` and `fastapi` (the product runners need them). Run it from any
folder; paths are absolute.

## Files

| File | What it does |
|---|---|
| `run_all.py` | The driver: checks, settings, order of work, spend cap, one worker per design and regime, run log. |
| `worker.py` | Runs one design on one regime in its own process (the model client binds its model and ledger at import). |
| `product_case.py` | Runs the product on one case-run through `harness/product/run_api.run_case`, in its own process. |
| `checks.py` | The four checks before a `fresh2` run. |
| `lib.py` | Paths, the order of work, store files from the spec, atomic writes. |

## What a run writes, under `runs/study3/<label>/`

- The plan files the spec names, with its keys: `plans_<regime>_<design>.json` keyed `<ARM>|<case>|<run>`, and
  `samples_<regime>_ric_luna.json` keyed `<case>|<sample>` for self-consistency (five samples per run, so 15 per
  case with `--k 3`). Product entries also carry `keys` (the cache key of each model request), `agents`,
  `product_extra` and `plan_workflow_only`.
- `MANIFEST.json`: the data manifest's hash, the spec's hash, models, `k`, the catalogues and their file hashes,
  the product commit, its `python -m casepath parity` output for each product run, and every product setting a run
  uses (names and values; none is a secret, and environment values of the container are never written). Each
  invocation adds its start time, arguments and check lines. A resumed run must have the same settings; otherwise
  the driver refuses and asks for a new label.
- `RUNLOG.jsonl`: one line per invocation: start and end, designs, entries before and after per design, spend of
  the invocation and of the label so far, why it stopped, and the number of failed outputs.
- `checks/results/semantic_serial.json`: the output of `compare.py` for this product.

Cost rows go to the ledgers the spec names for each design (the analysis costs every design from them):
`runs/v2/ledger_<model>.jsonl` (Rules in context for tenancy, Core, original rules),
`runs/v2/cp4/ledger_dev_<model>.jsonl` (Rules in context for theft) and `runs/product/ledger_dev_gpt-6-luna.jsonl`
(the product under arm `STUDY3-<label>-<design>`, and the baselines under their arms `COL`, `REACT`,
`B1V2P_SAMPLE`, `RPACK`, …). Responses are cached as the existing runners cache them, so a rerun is free.

## Checks

On `fresh2` the driver refuses to start unless all four pass; on `fresh` it prints them and goes on. Each prints
one line.

- (a) `ANALYSIS_PLAN_STUDY3.md` is committed unmodified (`fresh2/guard.py`'s own function). This runs first;
  until it passes, the only file under `fresh2/` that is opened is `guard.py`.
- (b) The worktree in `CASEPATH_PRODUCT` is clean, at `product.commit` of the spec, and its parity source-tree hash
  is `product.source_tree_sha256`; `product_evaluator.*.package.commit` must be the same commit.
- (c) The tenancy rule templates of `fresh2` have the SHA-256 of those of `fresh` (both `MANIFEST.json`). Then
  `harness/product/workflows/fresh-serial-sync` applies unchanged (the case at the time of writing). Otherwise the
  driver converts the templates as `convert.py --sync` does into `harness/study3/workflows/fresh2-serial-sync`,
  records the hashes, and refuses until the spec names that folder.
- (d) `compare.py` (every assignment of each tenancy family; all document decisions must agree with exact
  deferral) and `compare_theft.py` (3,000 random assignments) pass against the product worktree.

## Order of work, spend and interruption

Cheap designs first, the full product last, tenancy before theft within each design, so that an early stop leaves
complete designs: Rules in context, original rules, Model executes rules, ReAct, Core, CasePath checklist only,
Self-consistency, original rules frontier, Rules in context frontier, CasePath. (Measured cost per case-run on the
development ledgers, from `analysis/study3.py --data fresh --label r3`.) Inside a design, cases run in parallel
(`--workers`) as the existing runners do; the product runs each case-run in its own process.

`--cap-usd` caps the spend of one invocation. No new case starts once the cap is reached; cases already running
finish, so the spend can exceed the cap by at most a few case-runs. The spend counts only paid calls, not cached
answers. Ctrl-C stops cleanly: finished cases are kept, unfinished ones run again on resume.

A failed output (no plan) is stored as failed and never run again; the transports' own retries are the only
retries. The driver lists every failed output at the end.

Two-valued designs need no model calls; `analysis/study3.py` derives them from the product's stored readings.

`--limit N` (smoke tests only; refused on `fresh2`) takes the first N tenancy claims and the texts of the first
theft story.

## Where code is copied instead of imported

- `product_case.py` adapts the child of `dev_probe/run_product_probe.py` (fixed to the probe claims there).
- `worker.py`: Core's pairing of two readings is copied from `harness/v2/cp4.py::cp4` (a script; importing it would
  run it). The tenancy self-consistency sample is copied from `harness/product/baselines_theft.py::main`, where it is
  an inline function.
- `checks.py`: the conversion loop of `convert.py::write` (fixed to the packs `original` and `fresh`) is copied for
  the case that (c) fails; `compare.py` is imported with its result folder (`HERE`) pointed to the run folder.
- `baselines.py` reads its tenancy data from a module-level loader (`F`); the worker sets it to the loader that
  `common.data` returns. Nothing else is changed.
