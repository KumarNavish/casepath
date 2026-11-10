"""Shared pieces of the Study 3 driver (run_all.py) and its workers. No model calls, no data access.

Everything about the study (designs, store files, keys, runs, models, cost ledgers) is read from
analysis/study3_spec.json. This module only knows how each design is run, and in which order.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
TMIS = HARNESS.parent
REPO = TMIS.parents[1]
SPEC = TMIS / "analysis" / "study3_spec.json"
PRODUCT_DIR = HARNESS / "product"
RUNS = TMIS / "runs" / "study3"

# Order of work: cheapest designs first (measured cost per case-run on the development ledgers, see README.md),
# the full product last; inside a design, tenancy before theft. An early stop leaves complete designs behind.
# The secondary design "CasePath on the frontier model, checklist only" runs after all of them, only once every other
# selected design is complete, and has its own spend cap (run_all.py --cap-frontier-product-usd).
ORDER = ["ric", "ric_original", "model_executes_rules", "react", "core", "casepath_checklist", "self_consistency",
         "ric_original_frontier", "ric_frontier", "casepath", "casepath_frontier_checklist"]
LAST = "casepath_frontier_checklist"
REGIMES = ["tenancy", "theft"]
PRODUCT_DESIGNS = {"casepath", "casepath_checklist", "casepath_frontier_checklist"}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_spec(path=SPEC) -> dict:
    return json.loads(Path(path).read_text())


def designs(spec) -> dict:
    return {d["key"]: d for d in spec["designs"]}


def store_of(spec, design, regime, label) -> dict:
    """Where the analysis expects this design's output: {"path", "key", "samples_per_run"?} (path absolute)."""
    st = designs(spec)[design]["store"][regime]
    if "derive" in st:
        if st["derive"] != "majority":
            return None  # two-valued: derived by the analysis, no model calls
        src = st["samples"]
        return {"path": TMIS / src["path"].format(label=label), "key": src["key"], "samples_per_run": int(st["samples_per_run"])}
    return {"path": TMIS / st["path"].format(label=label), "key": st["key"]}


def units(spec, wanted=None) -> list[tuple[str, str]]:
    """(design, regime) pairs that need model calls, in the order of work."""
    D = designs(spec)
    missing = [k for k in D if k not in ORDER and any(store_of(spec, k, r, "x") for r in D[k]["regimes"])]
    if missing:
        raise SystemExit(f"designs with model calls but no place in the order of work: {missing}")
    out = []
    for d in ORDER:
        if d not in D or (wanted is not None and d not in wanted):
            continue
        for r in REGIMES:
            if r in D[d]["regimes"] and store_of(spec, d, r, "x") is not None:
                out.append((d, r))
    return out


def read_json(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text()
    return json.loads(text) if text.strip() else {}


def write_json(path, obj) -> None:
    """Atomic write: an interrupt never leaves a half-written store file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    os.replace(tmp, p)


def failed(entry) -> bool:
    if entry is None:
        return True
    return entry.get("plan") is None or entry.get("status") in {"failed", "adapter_error"}


def git(*args, cwd=REPO) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True).stdout.strip()
