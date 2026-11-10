# The outside check on the synthetic claims

What this session does on each product commit the product session names, what it needs, and what it returns. Verified
against `harness/product/` (`README.md`, `run_api.py`, `run_product.py`, `score_all.py`) and the product at
`6f3de061`.

## 1. What runs

| | |
|---|---|
| Claims | The 72 sealed tenancy claims of `fresh/` (18 families of 4; `tenancy_fresh.claim_ids("test")`) and the theft pairs of stories 4 and 5 (`fresh/theft`, as `score_all.py` scores them today) |
| Workflows | The paper's tenancy templates converted to the product's workflow format (`harness/product/convert.py --sync`) and the reviewed theft rules (`convert_theft.py`). Not the insurer's catalogue. |
| Product | The named commit in a read-only worktree; `run_api.py` imports it, asserts that the imported package's source-tree hash equals the `python -m casepath parity` output of the worktree and that the worktree is unmodified |
| Path | The product's own HTTP API in process: `create_app`, POST `/api/cases`, POST `/api/cases/{id}/files`, POST `/api/cases/{id}/runs`, GET `/api/runs/{id}`, GET `/api/cases/{id}`; one fresh store per claim-run, no Knowledge |
| Model | `gpt-6-luna` through the product's chat connector, with a caching, cost-recording transport |
| Scoring | `score_all.py`, model-free |
| Cost (measured at `7ff7af64`) | USD 0.0176 per tenancy claim-run (35 model calls), so about **USD 1.3 per run of the 72 claims**; USD 0.020 per theft text (25 calls). Three runs when a difference needs confirming: about USD 4. |

## 2. What is returned after each round

One file per round, `results/score_all_<label>.json`, and a short table:

| Measure | Definition (as `score_all.py` computes it) |
|---|---|
| Strict unsafe errors per claim-run | `strict_unsafe` mean |
| Requested share | requested / required-now documents |
| Held required documents | `held_required_now` |
| Premature and unnecessary requests | `premature`, `unnecessary` per claim-run |
| Missed, silent skips, spurious holds | `missed`, `silent_skip`, `spurious_hold` |
| Theft | wrong + missed per pair, unchanged and premature when a fact is open |
| Cost and calls | USD and model calls per claim-run, from the ledger |
| Run failures | `empty_or_failed` |
| **Claims that got worse** | Paired by claim against the previous round: a claim is listed if its strict unsafe count is higher than in every earlier run of that claim at the previous commit. With one run per claim, a listed claim is re-run twice more before it is called worse. The run-to-run spread at the previous commit (three runs) is reported beside it. |

Both scoring views are reported: conservative (workflow needs and needs the agent added as required) and workflow
needs only.

## 3. What is needed from the product, what exists, what is missing

| Need | Exists today | Missing |
|---|---|---|
| A commit hash reachable from this session | The harness reads `7ff7af64` from a local worktree; the extract read here is `6f3de061`. Equal code is shown by the parity source-tree hash, not by commit hash (the internal copy has other commits). | Each round: the commit, pushed where this session can fetch it, and its source-tree hash. |
| A stable command line | No product command is needed: the harness drives the HTTP API above, and the parity command (`python -m casepath parity --catalogue <dir>`). | Notice before a route or a field below changes. |
| A stable run record | The adapter (`run_product.to_plan`) reads: `run.status`, `error`, `routing` (`status`, `needs`, `candidates`, `facts`), `workflow_id`, `workflow_version`; `result.evaluation` (`documents[]`: `document`, `title`, `step`, `required`, `status`, `condition_facts`; `waiting_for[].fact`; `unmet[].fact`; `current.step`; `outcome.id`; `reached` or `path[].step`; `deferral`); `result.process.documents[]` (`id`, `edit`, `legal_basis`, `knowledge`); `result.agent_edits[]` (`id`, `op`, `args`, `reason`); `result.facts[]` (`fact`, `status`, `value`, `verdict`, `by`, `second_value`, `presumed`, `citations`); `result.documents[]` (`document`, `status`, `verdict`, `shows`); `result.usage[]` (`input_tokens`, `cached_tokens`, `output_tokens`); `result.answer`, `result.reply.clauses`, `result.warnings`. | A `schema` field on the run result, so a changed shape is detected rather than mis-scored. |
| Deterministic ids, so the response cache is reused | No. Ids come from `uuid4` (`web/store.py`, `new_id`). File ids enter every model request as the allowed values of the citation schema (`agents/team.py`, `_citations`), and the cache key is the hash of URL, body and run (`run_product.py`, `CachingTransport`). A claim-run on a fresh store therefore produces new request bodies and misses the cache. (Read from the code; not confirmed by a test run.) | A setting, for research and tests only, that derives case and file ids from a seed and the file's hash, e.g. `CASEPATH_ID_SEED`. |
| A model-free replay command that applies a Knowledge version to stored runs | No command. The building block exists: `agents/core.py` `evaluate(workflow, knowledge, edits, result, case_id)` computes the process and checklist from a stored result with no model; `quality/evaluate.py` `rescore` rescores stored benchmark stores but does not change Knowledge. HANDLER_BAR L3 plans the replay. | `python -m casepath replay --runs <dir of stored run records> --catalogue <dir> --knowledge <items.json> [--edits <edits.json>] --out <dir>`: for each stored run, the evaluation before and after, the `casegraph.diff`, and which Knowledge items applied (`provenance.knowledge`), plus the parity manifest and the content hash of the Knowledge version. No model, no network. |

**Missing on this session's side.** `run_api.py` stores only the mapped plans and `product_extra`, not the full run
result. For a replay bundle it must also store each claim-run's full run record (`run` and `GET /api/cases/{id}`).
This session will add that before the next round.

## 4. The bundle handed to the insurer

So that Knowledge that must stay inside can be tested on the synthetic claims with no tokens:

| Part | Content |
|---|---|
| Claims | The 72 tenancy claims and the theft texts, as files (synthetic, no insurer data) |
| Stored runs | Full run records at the frozen commit, three runs per claim, with the parity manifest |
| Workflows | The converted tenancy and theft workflows |
| References | The claims' reference plans |
| Scorer | `score_all.py` with its imports, and a script that maps replay output to plans with `run_product.to_plan` |
| Hashes | SHA-256 of every file |

Inside, the replay command applies a Knowledge version to the stored runs; the scorer compares before and after. Only
the content-free score table leaves.

## 5. What this check can and cannot show

- **Can show:** that a code change does not make the product worse on fresh synthetic claims, with the paper's model, paired by claim and against run-to-run spread; the cost of a change.
- **Cannot show:** anything about the insurer's processes, cases or model. The synthetic claims use the paper's tenancy and theft workflows, not the insurer's catalogue.
- **Knowledge transfer:** Knowledge applies only within its process family. Knowledge learned on the insurer's processes will not apply to the tenancy and theft families unless the family ids match, so the replay on the bundle shows only that Knowledge stays in its family (no harm), not that it transfers.
- The synthetic claims were sealed before the product ran on them, but every round run on them uses them again; after many rounds they become development data. The round count is reported.
