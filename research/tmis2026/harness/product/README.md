# Measuring the product as built

This folder evaluates `casepath-internal` itself, without any change to the product. It imports the product from a
read-only worktree at `/home/user/work/casepath-ui3`, commit `55b80304dadb8a2b2671568f37fb28a39e989bdb`
(branch `claude/casepath-internal-20261027`).

| File | What it does |
|---|---|
| `convert.py` | Converts the paper's tenancy templates into the product's `casepath.workflow/1` format. It is deterministic and writes `workflows/<pack>-<layout>/`. Its docstring lists the mapping and what cannot be expressed. |
| `compare.py` | Exact semantic comparison over every true/false/unknown assignment of each family's flags. It compares the product's `workflows.evaluate` with the paper engine's strong Kleene and exact-deferral semantics, and makes no model calls. Output goes to `results/semantic_<layout>.json`. |
| `run_product.py` | Headless adapter. `run_product(case_text, attachments, catalogue_dir, model, run, case_id)` runs `core.prepare` through the product's chat connector, which points at OpenRouter. The adapter keeps a response cache and a dev ledger, and maps the result to the harness plan format. Its docstring documents the mapping. |
| `pilot.py` | Runs the product on the 12 dev claims (`--set dev12`) or on the 72 fresh claims (`--set fresh`). Output goes to `runs/product/plans_tenancy_<model>_<set>.json`. |
| `score_product.py` | Scores the product next to the cached arms using the Study 1 (dev12) and Study 2 (fresh) measures, and attributes each lost or extra document to a cause. Output goes to `results/score_<set>_<model>.json`. |

Spending is recorded only in `runs/product/ledger_dev_<model>.jsonl`, which takes its token counts and cost from each provider response's `usage` fields. Responses are cached in `runs/product/cache/`, keyed by URL, body and run, so a rerun of the same claim-run is free.

Interpreters:
- `compare.py` and `convert.py` run with the system `python3`, which has the `casepath-api` dependencies.
- `run_product.py`, `pilot.py` and `score_product.py` need `httpx`, `pypdf` and `reportlab`. They run with the scratch virtualenv (`…/scratchpad/ui/venv/bin/python`).
