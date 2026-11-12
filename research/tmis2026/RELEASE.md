# Release package: CasePath for ACM TMIS

This file says what the release of the paper "CasePath" (folder `research/tmis2026/`) contains, how to run the
tested product, how to reproduce the paper's tables without model calls, how to re-run Study 3 with model calls,
and what is not released. Paths below are relative to `research/tmis2026/` unless they start with the repository
root (`casepath-internal/`, `data/`).

Before anything is made public, read `release/SCRUB_REPORT.md`. It lists what must be removed or decided first.

## 1. What the release contains

| Part | Where | How to check it |
|---|---|---|
| The tested product | Package `casepath` in `casepath-internal/` at commit `6a72159cdb35a01059d0549b1d437c0b3d5c20cb`, branch `claude/casepath-internal-paper-sync-20261110d`. This commit is **not** on the paper branch. The paper branch's own `casepath-internal/` is an older copy (package `casepath_internal`) and is not the tested product. | `python -m casepath parity` in that folder prints `source_tree_sha256` `030480203f7d10b364e4ecc34e0c0b544c4038e107f489bc2080aba6b349ab4d`. `reproduce.sh` checks this. |
| Tenancy workflow catalogue | `harness/product/workflows/fresh-serial-sync/` (converted by `harness/product/convert.py --sync`) | `harness/product/compare.py` (every truth assignment, against the reference engine) |
| Theft workflow catalogue | `harness/product/workflows/theft-reviewed/` (converted by `harness/product/convert_theft.py` from `rule_review/final/reviewed_rules.json`) | `harness/product/compare_theft.py` (3,000 random assignments) |
| Reviewed theft rules and both editors' reviews | `rule_review/` | `rule_review/SHA256SUMS` |
| Study 1 data | Repository root: `data/casepath-tenancy-claims/`, `data/casepath-theft-pairs/` | `verify.py` in each folder |
| Study 2 data | `fresh/` | `fresh/MANIFEST.json` (hash of every file), `fresh/tenancy/oracle_check.py` |
| Study 3 development probe | `dev_probe/` | `dev_probe/build.py` rebuilds `claims.json` and `references.json` |
| Study 3 data (sealed) | `fresh2/` | `fresh2/check.py` (oracle, loaders, novelty, manifest); `fresh2/guard.py` refuses data access unless the Study 3 plan is committed unmodified and no model client is loaded |
| Harness | `harness/` (Study 3 driver in `harness/study3/`, product runners in `harness/product/`, Study 2 in `harness/v2/`) | READMEs in `harness/study3/` and `harness/product/` |
| Analysis | `analysis/` (Study 3 analyses added after review: `study3_review.py`, `make_numbers_study3_review.py`, `fig_review.py`; Appendix A check: `check_fragment.py`) | `analysis/test_study3.py` (43 tests), `analysis/test_study3_review.py` (36), `analysis/test_study2.py` |
| Stored outputs and ledgers | Study 1: `runs/plans_*.json`, `runs/ledger.jsonl`, `runs/responses_cache.tar.gz`. Study 2: `runs/v2/`. Study 3: `runs/study3/confirm/` (plans, `MANIFEST.json`, `RUNLOG.jsonl`) and the ledgers in `runs/product/` and `runs/v2/`. | `reproduce.sh` re-scores them |
| Frozen plans | `ANALYSIS_PLAN.md` (Study 1), `ANALYSIS_PLAN_STUDY2.md`, `ANALYSIS_PLAN_STUDY3.md` with `analysis/study3_spec.json`, `expert_study/PREREGISTRATION_DRAFT.md` with `expert_study/EVENT_FIELDS.md` | Freeze commits are named in `paper/sections/app_g_repro.tex` |
| Paper sources | `paper/` (LaTeX, `results/numbers*.tex`, `figures/`) | `analysis/verify_paper.py` compiles a clean copy |

The release must be a git clone, not a file archive: the Study 3 data guard checks the plan with git, and the
two-valued designs read the product's evaluator from commit `6a72159c` with `git archive`.

## 2. Quickstart: run the product

Needs Python 3.10 or later, git, make and curl. From an empty folder:

```sh
git clone <repository URL> casepath && cd casepath
git fetch origin claude/casepath-internal-paper-sync-20261110d
git worktree add ../casepath-product 6a72159cdb35a01059d0549b1d437c0b3d5c20cb
cd ../casepath-product/casepath-internal && make setup   # .venv with the product's dependencies
.venv/bin/python -m casepath parity    # source_tree_sha256 must be 030480203f7d10b3...
make test                              # 232 tests, no network, no model
make preview                           # http://127.0.0.1:8790: synthetic cases, scripted model; Ctrl-C stops it
# One synthetic claim through the HTTP API, with your own chat-completions model endpoint:
T=../../casepath/research/tmis2026
export CASEPATH_DATA_DIR=$(mktemp -d) CASEPATH_DEV_USER="Case handler" CASEPATH_MODEL_REASONING=true
export CASEPATH_WORKFLOW_CATALOGUE=$(cd $T/harness/product/workflows/fresh-serial-sync && pwd)
export CASEPATH_MODEL_PROVIDER=databricks CASEPATH_MODEL_API=chat CASEPATH_MODEL=<model name>
export CASEPATH_MODEL_ENDPOINT=https://<host> CASEPATH_CHAT_PATH=<path, e.g. /v1/chat/completions> CASEPATH_MODEL_GATEWAY_HOSTS=<host>
export DATABRICKS_TOKEN=<your API key>  # sent as "Authorization: Bearer <key>"
export CASEPATH_ORGANISATION="the legal-expenses insurer's" CASEPATH_WRITING_LANGUAGE="in the language of the case files"
.venv/bin/python -m casepath serve --port 8765 &
python3 -c "import json,sys;print(next(iter(json.load(open(sys.argv[1])).values()))['customer_message']['body'])" $T/dev_probe/claims.json > claim.txt
C=$(curl -s -XPOST localhost:8765/api/cases -H 'content-type: application/json' -d '{"title":"Tenancy claim","intake":{}}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s -XPOST localhost:8765/api/cases/$C/files -F file=@claim.txt
R=$(curl -s -XPOST localhost:8765/api/cases/$C/runs | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
curl -s localhost:8765/api/runs/$R | python3 -m json.tool | head   # repeat until "status" is no longer queued or running
curl -s localhost:8765/api/cases/$C > case.json                    # the checklist, facts with quotes, evaluation
```

The settings are those of `harness/product/run_api.py::settings_env` and of `analysis/study3_spec.json`
(`CASEPATH_MODEL_REASONING=true`). The value `databricks` selects the product's chat-completions connector; it
works with any endpoint that speaks that protocol. All other settings keep the product's defaults (three readings,
open rule `any`, full run scope); `docs/PARITY.md` at the product commit lists them.

What was tested, on 2026-11-11, from a local clone: every line except the model call. `make setup`, `parity`
(hash as above), `make test` (232 tests, 1 skipped, OK) and `make preview` (HTTP 200, two seeded cases) ran. The
server started with these settings and a placeholder endpoint; case creation, upload and run start answered; the
run then ended `failed` with "The model endpoint could not be reached", as expected without a model. **Not tested:**
`git clone <repository URL>` from the public address (it does not exist yet), a run against a real model endpoint
with a real key, and therefore the content of `case.json` after a completed run.

## 3. Reproduce the paper's tables (no model calls)

```sh
git clone <repository URL> casepath && cd casepath
git fetch origin claude/casepath-internal-paper-sync-20261110d    # the product commit; needed by two steps
python3 -m venv .venv-repro && .venv-repro/bin/pip install -r research/tmis2026/requirements-reproduce.txt
PYTHON=.venv-repro/bin/python research/tmis2026/reproduce.sh       # options: --keep, --skip-latex
```

`requirements-reproduce.txt` states the Python version and the four packages. The analysis itself uses only the
standard library. `pypdf==5.9.0` is needed for Study 1 (with another version the PDF text differs and the cached
model responses are not found); matplotlib, numpy and pillow only draw the figures.

The script writes nothing into the checkout. It prints one line per step and exits with status 1 if any step
fails. It blocks model calls: `TMIS_MODEL` is removed, `TMIS_BUDGET_USD` is 0, and the proxy variables point to a
closed local port. Steps:

1. Data: `fresh2/check.py`; the `fresh/` manifest hashes and `fresh/tenancy/oracle_check.py`; `dev_probe/build.py`
   rebuilt into a temporary folder and compared byte for byte; `verify.py` of both Study 1 data sets;
   `rule_review/SHA256SUMS`.
2. Product: the commit `6a72159c` is in the clone, and its `python -m casepath parity` hash is the one in
   `analysis/study3_spec.json`. Then `analysis/check_fragment.py` checks the claims of Appendix A ("The tested
   workflows are flow workflows", "The plain walk on theft") with the product's own `process/workflows.py` taken
   from that commit by `git archive`, as `analysis/study3.py` takes it. For the three tenancy workflows it compares
   the product's walk with Equations (1)–(2) under every complete assignment (32, 32 and 8) and the product's
   evaluation with exact deferral, Equation (4), under every three-valued assignment (243, 243 and 27). For the
   theft workflow it checks that it is one step without transitions and compares the product's evaluation with
   exact deferral on 5,000 random three-valued assignments (seed 1; 4,881 of them go through the plain walk). It
   fails on any disagreement and on any count that differs from the appendix.
3. Study 3: `analysis/study3.py --data fresh2 --label confirm` into a temporary folder, compared byte for byte with
   `analysis/study3_results_fresh2_confirm.json` and `.md`; the same for `analysis/study3_posthoc.py`
   (`study3_posthoc.json`, `.md`) and `analysis/make_numbers_study3.py` (`paper/results/numbers_study3.tex`);
   the Study 3 figures (`fig_s6.py`: `fig_main`, `fig_cost`) and the Section 4 figures (`fig_s4.py`) are built
   into a temporary folder (built, not compared).
4. Study 3, analyses added after review: `analysis/study3_review.py` into a temporary folder. Two of its parts read
   the product's response cache (`runs/product/cache/`, ignored by git, so absent from a clone): the individual
   readings in R3 (`readings_agreement`, `readings_per_case_run`, `all_readings_agree_on_wrong_value`,
   `admitted_wrong_with_all_readings_agreeing`, for both product designs) and the cost split by component in R7
   (`R7.cost`), and the count `cache_missing`. The script runs without the cache; those parts then come out
   different. The step compares everything else with the stored `analysis/study3_review.json` and `.md`
   (the JSON entry by entry, the Markdown section by section outside R3 and R7). When every cache file the
   analysis reads is present (`cache_missing` is 0) it also compares both files byte for byte; otherwise these
   two lines are SKIP and say how many cache files are missing. Then `make_numbers_study3_review.py` is compared
   with `paper/results/numbers_study3_review.tex` (it reads the stored JSON), and `fig_review.py` builds
   `fig_families`.
5. Study 3, checks added after the outside review (post hoc): `analysis/study3_feedback.py`,
   `analysis/decomposition.py` and `analysis/lint_followup.py`. All three re-read the product's response cache
   (`runs/product/cache/`); none makes a model call (the lint's mutation arm ran once in development, for USD 0.15,
   and is read from its stored runs and ledger). With the cache in place each is re-run into the temporary folder and
   its JSON, Markdown and (lint_followup) `posthoc_numbers.tex` are compared byte for byte; without it these three
   lines are SKIP. Either way, `make_numbers_study3_feedback.py` is regenerated from the stored
   `study3_feedback.json` and compared with `paper/results/numbers_study3_feedback.tex`, the post-hoc macros are
   regenerated from the stored `lint_followup.json` and `decomposition.json` and compared with
   `analysis/posthoc_numbers.tex` and `paper/results/numbers_posthoc.tex`, `analysis/test_posthoc.py` runs, and
   `analysis/test_study3_feedback.py` runs in full with the cache and without its one replay test (which reads the
   cache) otherwise.
6. Tests: `analysis/test_study3.py` (43), `analysis/test_study3_review.py` (36), `analysis/test_study2.py`.
   The development ledger `runs/product/ledger_dev_gpt-6-luna.jsonl` is append-only and grew after the registered
   and review analyses recorded its hash; the comparison of `study3_results_fresh2_confirm.json` and
   `study3_review.json` accepts a different recorded hash for a development ledger only if the stored hash is that of
   a line-ending prefix of the current file, and says so.
7. Studies 1 and 2 and the paper: `analysis/verify_paper.py` in a temporary copy of this folder with
   `runs/responses_cache.tar.gz` unpacked. It re-runs 18 scripts and checks that every `analysis/*.json`
   evidence file and `paper/results/numbers.tex` come out byte for byte the same; regenerates
   `numbers_study3.tex` and `numbers_sharc.tex`; checks the structure of the included sections and that every
   citation key resolves; and builds the two documents of the paper, `main.tex` and `supplement.tex`, in the order
   they need (main, supplement, main, each with BibTeX, because each reads the other's `.aux`), then checks both
   logs for errors, undefined references, multiply defined labels and overfull boxes over 5 pt. The compile lines
   are SKIP when pdflatex is missing or with `--skip-latex`. Then `make_numbers_sharc.py` is compared with
   `paper/results/numbers_sharc.tex`, and `figures.py` is built.

**What Studies 1 and 2 re-check, and what not.** Re-checked from stored outputs: every number in
`paper/results/numbers.tex` and every `analysis/*.json` that `verify_paper.py` regenerates (Study 1 scoring and
tests from `runs/plans_*.json` and the Study 1 response cache; Study 2 scoring and tests from `runs/v2/plans_*`
and its ledgers), and the ShARC macros from `runs/sharc/summary.json`. Not re-checked: the model runs themselves
(the stored plans are inputs); the inputs that `verify_paper.py` takes as given, namely
`analysis/rule_verification.json`, `analysis/reference_rederivation.json`, `scicore/out_local/*.json` (cluster
jobs) and the tenancy entries of `analysis/error_causes.json`; `runs/sharc/summary.json` itself (only formatted
into macros); and the Study 1 and 2 figures (built, not compared).

Run time of the fresh-clone test: see section 8.

**What needs the cache archive.** The two cache-dependent parts of the review analysis (step 4), the readings
of R3 and the cost split of R7, and the re-runs of the three post-hoc scripts of step 5. To check them, put the product's response cache (79,404 files, 0.9 GB; not in the
repository) at `runs/product/cache/` and run `reproduce.sh` again; the two SKIP lines then become byte-for-byte
comparisons. Every other step needs only the repository.

## 4. Re-run Study 3 with model calls

```sh
CASEPATH_PRODUCT=<product worktree at 6a72159c> <venv>/bin/python harness/study3/run_all.py \
    --data fresh2 --label <new label> --k 3 --cap-usd 32 --cap-frontier-product-usd 8
```

The venv needs `httpx` and `fastapi`; the product's own `.venv` from the quickstart has both. The driver first runs
four checks (`--check-only` runs only these): the plan is committed unmodified; the product is at the tested commit
with the expected parity hash and settings; the tenancy templates have the recorded hash; the converted workflows
agree with the reference engines. Details: `harness/study3/README.md`.

Cost and time of the stored run (`runs/study3/confirm/RUNLOG.jsonl`): five invocations between 2026-11-10 22:30
and 2026-11-11 04:17 UTC, about 5 h 40 min of running time (29, 118, 47, 110 and 38 minutes; four invocations
stopped early, two deliberately and two by failures of the environment). Spend USD 34.33 according to the ledgers
(USD 22.41 on the cost-efficient model, USD 11.92 on the frontier model); the run log's own totals are incomplete
because three invocations could not log their end. Section 6 of the paper gives the cost per case of each design.

Four limits for anyone outside the original container:

- **Credentials.** The harness's model clients (`harness/llm.py`, `harness/product/run_product.py`) send the
  placeholder `Authorization: Bearer proxy-injected` to a fixed model router and trust the CA bundle at
  `/root/.ccr/ca-bundle.crt`. The key was added by the container's outbound proxy. Elsewhere these calls fail until
  the two files are adapted to read a key and a CA bundle from the environment. No such change is in the release.
- **Response caches are not in git.** `runs/product/cache/` and `runs/cache/` are ignored by `.gitignore`. None of
  the 22,999 cached product responses that Study 3's stored plans reference is tracked. A re-run from a clone
  therefore pays for every call again, and its answers can differ because the models are not deterministic.
- **Absolute paths.** `harness/product/compare_theft.py` (run by the driver's fourth check) and
  `harness/v2/cp4_score.py` now find their files relative to their own location; their output is unchanged. Other
  defaults still point outside the repository and must be given on the command line or in the environment:
  the product worktree (`--product`, `CASEPATH_PRODUCT`; the driver passes it), the CA bundle
  `/root/.ccr/ca-bundle.crt` (`harness/product/run_product.py:62`, `run_api.py:51`), and three development-only
  paths (`harness/product/baselines_theft.py:208`, `harness/parity_original.py:7`,
  `harness/v2/build_review_bundle.py:15`) that no step of Study 3 or of `reproduce.sh` uses.
- **Stored labels are not overwritten.** Use a new `--label`; a resumed run must keep its settings.

## 5. Licences

- Code: Apache License 2.0 (`LICENSE` at the repository root; the same file exists at the product commit).
- Study 1 data (`data/casepath-tenancy-claims/`, `data/casepath-theft-pairs/`): data under CC BY 4.0
  (`LICENSE-DATA`), code under Apache 2.0 (`LICENSE-CODE`). Excluded from the data licence: quoted policy terms,
  a claim form and industry model conditions (`data/casepath-theft-pairs/SOURCES.md`) and the Canton of Zurich form
  templates in 34 tenancy attachments (`THIRD_PARTY_NOTICES.md`).
- The product's interface font: `casepath-internal/casepath/web/ui/assets/fonts/Mulish-OFL.txt` (SIL OFL).
- **No licence is stated** for: `fresh/` (Study 2 data), `fresh2/` (Study 3 data), `dev_probe/`, `rule_review/`
  (reviewed rules and reviews), `runs/` (stored plans, ledgers, response caches; they hold model output),
  `expert_study/`, `inputs/` and the paper sources in `paper/`. The paper's appendix
  (`paper/sections/app_g_repro.tex`) also flags this for `fresh/`, `dev_probe/` and `fresh2/`. The owner should add
  a licence file to each before release, or state that the root licence covers them.

## 6. How to cite

The repository, as the paper cites it (`paper/references.bib`, key `casepath2026repo`):

```bibtex
@misc{casepath2026repo,
  author       = {Kumar, Navish and Hoesli, Tobias and Javadov, Aydin and Ollier, Joseph},
  title        = {{CasePath}: Source Code, Datasets, Experiment Harness and Analysis Plan},
  year         = {2026},
  howpublished = {GitHub repository},
  url          = {https://github.com/KumarNavish/casepath},
  note         = {Experiments and paper source in \texttt{research/tmis2026}}
}
```

Cite the paper itself once it has a venue and a DOI; the entry is to be added here then. The repository's
top-level `README.md` still carries an anonymous citation from the earlier submission; it should be replaced by
the entry above.

## 7. What is not released, and why

- **The insurer's material.** Its process catalogue, its Knowledge and its case files belong to the insurer, and
  the case files are real claims (`paper/sections/app_g_repro.tex`). The expert study's records leave the insurer
  only as the pre-registered pseudonymous export; the content export stays inside.
- **Model credentials.** None are stored; see section 4.
- **The full response caches** (`runs/product/cache/`, most of `runs/cache/`): ignored by git, so not in a clone.
  The Study 1 subset that the re-analysis needs is in `runs/responses_cache.tar.gz`. Whether to add the rest
  (79,404 files under `runs/product/cache/`, 0.9 GB) is the owner's decision; see `release/SCRUB_REPORT.md`.
- **Screen captures** under `paper/figures/ui/` (ignored, about 94 MB). The figures use the tracked crops in
  `paper/figures/ui_used/`, so nothing in the paper depends on them.
- **Items to remove before publication** (names of the insurer, internal documents, a Knowledge file derived from
  the insurer's letters, local paths): `release/SCRUB_REPORT.md`.

## 8. Tests of `reproduce.sh`

Both runs on 2026-11-11 in a container (Linux, CPython 3.13.18, pdflatex present), with a new virtual environment
holding only `requirements-reproduce.txt` (it installed pypdf 5.9.0, matplotlib 3.11.2, numpy 2.5.3, pillow 12.3.0
and their dependencies).

**Fresh clone, cache absent.** `git clone --single-branch --branch claude/casepath-tmis-paper-20261109` of the
local repository at commit `1104e1f8`, then `git fetch` of the product branch; the files changed for this release
(`release/reproduce.py`, `analysis/check_fragment.py`, `analysis/verify_paper.py`,
`harness/product/compare_theft.py`, `harness/v2/cp4_score.py`) copied in at their current state. Result: 59 steps
passed, 2 skipped, none failed, in 11 min 20 s of wall time. The two SKIP lines are the cache-dependent parts of
the review analysis (21,667 cache files missing). The Study 1–2 re-analysis and the paper build in
`verify_paper.py` took 612 s of that; the review analysis 32 s; everything else about 40 s. Afterwards
`git status` showed no new or changed file in the clone apart from the copied files.

**Working repository, cache present.** The same files in the working repository at commit `f0450649`, with the product's
response cache in `runs/product/cache/`. Result: 61 steps passed, none skipped, none failed, in 11 min 27 s of wall
time; the review analysis's JSON and Markdown both reproduced byte for byte, including R3 and R7. The run wrote
nothing into the checkout (`git status`, ignored files included, was the same before and after).

**Working repository, cache present, 2026-11-12.** After the post-hoc steps (step 5) and the ledger check were
added: 83 steps passed, none skipped, none failed, in 597 s. The registered results and the review analysis compare
equal except for the recorded hashes of the two development ledgers, which grew by appended rows after those
analyses ran; the recorded versions are byte prefixes of the current files. Not repeated in a fresh clone.

An earlier run in a virtual environment without the pypdf pin failed the Study 1–2 step: pypdf 7.0.0 extracts the
Study 1 PDFs with different spacing, so the cached model responses were not found. That is why the pin is there.
