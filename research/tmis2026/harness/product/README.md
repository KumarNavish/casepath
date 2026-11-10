# Measuring the product as built

This folder evaluates `casepath-internal` itself, without any change to the product. It imports the product from a
read-only worktree at `/home/user/work/casepath-product-7ff7af64`, commit `7ff7af648279e58765732ab2e1ed8f36d7f3b155`
(branch `claude/casepath-internal-20261027`; package `casepath`, command `python -m casepath …`). Set
`CASEPATH_PRODUCT=<worktree>` to measure another commit. Earlier runs used `55b8030` (`casepath-ui3`), `c560a42` and
`844281c` (`casepath-sync`); their outputs keep their labels. Everything here is development data.

| File | What it does |
|---|---|
| `convert.py` | Converts the paper's tenancy templates into the product's `casepath.workflow/1` format (`--sync`: `must_show` from the pack's required fields, the fresh pack's silence clause as `presumptions`). Deterministic; validated with the product's own `validate_workflow`. |
| `convert_theft.py` | Converts the reviewed theft rule base (`rule_review/final/reviewed_rules.json`) into one workflow (`workflows/theft-reviewed`): one intake step, each rule condition a fact and the need's `required_when`, the cheapest route fixed at conversion, alternatives in the need's text. Its docstring states what the conversion loses. |
| `compare.py` | Exact semantic comparison over every true/false/unknown assignment of each tenancy family's flags: the product's `evaluate` against the paper engine's strong Kleene and exact-deferral semantics. No model calls. 7ff7af64: 5,076 of 5,076 document decisions agree with exact deferral (`results/semantic_serial_p7ff.json`). |
| `compare_theft.py` | The same check for the converted theft workflow against the CP4 engine (`TheftPack.plan_exact` on the reviewed rules): 81,000 of 81,000 decisions over 3,000 random assignments. |
| `run_api.py` | Runs the product through its HTTP API exactly as a case worker's browser does (`create_app`, POST case, files, run; GET run, case), `--k` runs per claim. The run manifest is the product's own `python -m casepath parity` output plus the run settings. |
| `run_product.py` | Shared pieces: the caching, cost-recording model transport and the mapping of a result to plans in two scoring views (below). Imports nothing from the product. |
| `run_theft.py` | Runs the product on fresh theft texts with the converted workflow (title "Theft claim"). |
| `baselines.py` | Baselines on the 72 fresh tenancy claims: self-consistency over the cached Rules-in-context runs, Chain-of-Logic-style "model executes rules" (Study 1's B2 on the fresh pack), a ReAct tool-using agent over the product's workflows, and two-valued rule execution from the product's recorded facts. |
| `score_all.py` | Scores every arm with the Study 2 measures (tenancy) and as `harness/v2/cp4_score.py` (theft pairs). |
| `diagnose.py` | Attributes each remaining product error to its pipeline cause by replay through the product's evaluator. |
| `pilot.py`, `score_product.py` | Earlier runner (superseded by `run_api.py`; `claims()` and `inputs()` are still used) and scorer. |

Scoring views of the product's result (`run_product.to_plan`):
- `plan` (conservative, primary): requests = every checklist need with required "yes" and status missing or unusable,
  including needs the process builder added on its own and marked required (an added need has its own id, so against the
  reference it is an unnecessary request unless the reference requires that id); holds = needs with required "depends".
- `plan_workflow_only`: the same, restricted to the workflow's own needs.

Spending is recorded only in `runs/product/ledger_dev_<model>.jsonl` (rows of baseline arms carry `arm`), with token
counts and cost from each provider response's `usage`. Responses are cached in `runs/product/cache/`, keyed by URL, body
and run, so a rerun of the same claim-run is free.

Interpreters: `convert*.py`, `compare*.py`, `score_all.py`, `diagnose.py` run with the system `python3`; `run_*.py` and
`baselines.py` need `httpx` and `fastapi` (the scratch virtualenv).
