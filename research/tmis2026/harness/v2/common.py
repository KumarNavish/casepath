"""Shared setup for the Study 2 (CasePath v2) harness.

- Puts the Study 1 harness and the product package on the import path (the product is only imported).
- Redirects the model client's ledger to runs/v2/ledger_<model>.jsonl BEFORE any call. Study 1's
  analysis aggregates every row of runs/ledger.jsonl by (exp, method); writing v2 rows there would
  change Study 1's evidence files. The response cache (runs/cache) is shared, so an identical request
  is never paid twice. TMIS_BUDGET_USD therefore caps the spend recorded in this model's v2 ledger.
- Selects the dataset: --data original (the existing tenancy_data / theft_data modules) or
  --data fresh (research/tmis2026/fresh/{tenancy_data,theft_data}.py, loaded under distinct module
  names; this code never opens that folder unless asked to).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parent
HARNESS = V2.parent
TMIS = HARNESS.parent
REPO = TMIS.parents[1]
for p in (str(HARNESS), str(REPO / "casepath-api")):
    if p not in sys.path:
        sys.path.insert(0, p)

import llm  # noqa: E402  (binds TMIS_MODEL / TMIS_BUDGET_USD at import)

TAG = llm.MODEL.split("/")[-1]
OUT = TMIS / "runs" / "v2"
OUT.mkdir(parents=True, exist_ok=True)
llm.LEDGER = OUT / f"ledger_{TAG}.jsonl"
PACKS = V2 / "packs"
PACKS.mkdir(exist_ok=True)


def spent() -> float:
    return llm.spent()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def data(kind: str, which: str = "original"):
    """Return the data module for kind in {'tenancy', 'theft'}."""
    if which == "original":
        return __import__(f"{kind}_data")
    if which == "fresh":
        return _load(f"fresh_{kind}_data", TMIS / "fresh" / f"{kind}_fresh.py")
    raise ValueError(which)


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


# A provider error returned inside an HTTP 200 body ("no choices: ... 502") is cached by llm.call as if it were a
# final answer. For v2 calls such a transient failure is deleted from the cache and retried (at most 3 times).
_call = llm.call


def _body(system, user, schema, schema_name, max_tokens=3500, effort="low", model=None):
    return {"model": model or llm.MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
            "max_tokens": max_tokens, "reasoning": {"effort": effort, "exclude": True}, "usage": {"include": True},
            "provider": {"allow_fallbacks": False, "require_parameters": True, "data_collection": "deny"}}


def _retrying_call(**kw):
    import time
    for attempt in range(4):
        if attempt:
            time.sleep(15 * attempt)
        r = _call(**kw)
        if not (r.get("error") or "").startswith("no choices"):
            return r
        body = _body(kw["system"], kw["user"], kw["schema"], kw["schema_name"], kw.get("max_tokens", 3500),
                     kw.get("effort", "low"), kw.get("model"))
        key = llm._key(body, kw["run"])
        path = llm.CACHE / key[:2] / f"{key}.json"
        if path.exists():
            path.unlink()
    return r


llm.call = _retrying_call


def require_frozen_plan():
    """Refuse fresh-data runs unless ANALYSIS_PLAN_STUDY2.md exists, is tracked, and is committed unmodified."""
    import subprocess
    plan = TMIS / "ANALYSIS_PLAN_STUDY2.md"
    rel = str(plan.relative_to(REPO))
    ok = plan.exists()
    if ok:
        tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", rel], capture_output=True)
        clean = subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel], capture_output=True)
        ok = tracked.returncode == 0 and clean.returncode == 0
    if not ok:
        raise SystemExit("refusing to run on fresh data: research/tmis2026/ANALYSIS_PLAN_STUDY2.md must exist and be committed unmodified")
