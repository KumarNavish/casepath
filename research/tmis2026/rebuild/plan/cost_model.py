#!/usr/bin/env python3
"""Cost model for planning a new study, built only from stored ledgers, stored run results and the response caches.
No model calls, no network, no spending. Writes COST_MODEL.json and COST_MODEL.md next to this file.

    python3 rebuild/plan/cost_model.py            # recompute everything from the stored material
    python3 -c "import sys; sys.path.insert(0, 'rebuild/plan'); import cost_model as c; print(c.estimate('core_three', 'gpt-6-luna', 800, 3, 6, None, 'three'))"

Inputs (read only):
- Study 3 sealed runs (fresh2, label confirm): the run entries through analysis/study3.py (Study, spec, cases, entries)
  and the ledgers its spec names (runs/product/ledger_dev_*.jsonl, runs/v2/ledger_*.jsonl, runs/v2/cp4/ledger_dev_*.jsonl);
  the product's response cache runs/product/cache (to classify calls by stage and to read the individual fact readings).
- Fair-prompt check: study4/baseline_check/runs/ledger_*.jsonl (design A = prompt that may hold, B = Model executes rules).
- Benchmark runs of the checklist-only core: study4/lint/runs/results_<arm>_<regime>_<model>.json, ledger_dev_*.jsonl,
  cache/, and the file texts study4/dev/<regime>/final/<id>/text.txt and attachments/*.txt (not *.clean.txt, not
  reference.json or any other gold file).
Ledger fields used: product and benchmark ledgers: key, case, run, arm, input_tokens (includes cached), cached_tokens,
output_tokens, usd. v2 and fair-prompt ledgers: key, tag.case, tag.method, tag.exp, run, prompt_tokens (includes cached),
cached_tokens, completion_tokens (includes reasoning_tokens), reasoning_tokens, cost, latency_s, error.
"""
from __future__ import annotations

import gzip
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
LINT = TMIS / "study4" / "lint" / "runs"
DEV = TMIS / "study4" / "dev"
BC = TMIS / "study4" / "baseline_check"
LUNA, TERRA = "gpt-6-luna", "gpt-6.1-terra"
MODELS = (LUNA, TERRA)
MODEL_LABEL = {LUNA: "cost-efficient model (gpt-6-luna)", TERRA: "frontier model (gpt-6.1-terra)"}
OUT_JSON, OUT_MD = HERE / "COST_MODEL.json", HERE / "COST_MODEL.md"


# ======================================================================= small helpers
def jl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def dist(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"n": len(xs), "mean": sum(xs) / len(xs), "median": q(xs, 0.5), "p90": q(xs, 0.9), "min": min(xs), "max": max(xs)}


def norm(r):
    """One ledger row in a common form. Input tokens include cached tokens in both ledger formats."""
    if "tag" in r:
        return {"key": r.get("key"), "case": r["tag"].get("case"), "run": r.get("run"), "method": r["tag"].get("method"),
                "exp": r["tag"].get("exp"), "data": r["tag"].get("data"), "inp": r.get("prompt_tokens"),
                "cached": r.get("cached_tokens") or 0, "out": r.get("completion_tokens"), "reasoning": r.get("reasoning_tokens"),
                "usd": r.get("cost"), "latency": r.get("latency_s"), "error": r.get("error")}
    return {"key": r.get("key"), "case": r.get("case"), "run": r.get("run"), "method": r.get("arm"), "exp": None, "data": None,
            "inp": r.get("input_tokens"), "cached": r.get("cached_tokens") or 0, "out": r.get("output_tokens"), "reasoning": None,
            "usd": r.get("usd"), "latency": r.get("latency_s"), "error": None}


_LEDGERS = {}


def ledger(rel):
    if rel not in _LEDGERS:
        _LEDGERS[rel] = [norm(r) for r in jl(TMIS / rel)]
    return _LEDGERS[rel]


def ols(X, y, names):
    X, y = np.asarray(X, float), np.asarray(y, float)
    n, k = X.shape
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    dof = max(n - k, 1)
    s2 = float(res @ res) / dof
    try:
        cov = s2 * np.linalg.inv(X.T @ X)
        se = np.sqrt(np.clip(np.diag(cov), 0, None))
    except np.linalg.LinAlgError:
        se = np.full(k, float("nan"))
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float(res @ res) / tss if tss > 0 else None
    return {"n": n, "coef": {nm: float(v) for nm, v in zip(names, b)}, "se": {nm: float(v) for nm, v in zip(names, se)},
            "r2": r2, "residual_sd": math.sqrt(s2), "_b": b}


def words(text):
    return len(text.split())


def normtext(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


# ======================================================================= 1. implied token prices
PRICE_LEDGERS = {
    LUNA: ["runs/v2/cp4/ledger_dev_gpt-6-luna.jsonl", "study4/baseline_check/runs/ledger_gpt-6-luna.jsonl",
           "runs/v2/ledger_gpt-6-luna.jsonl", "runs/product/ledger_dev_gpt-6-luna.jsonl", "study4/lint/runs/ledger_dev_gpt-6-luna.jsonl"],
    TERRA: ["runs/v2/cp4/ledger_dev_gpt-6.1-terra.jsonl", "study4/baseline_check/runs/ledger_gpt-6.1-terra.jsonl",
            "runs/v2/ledger_gpt-6.1-terra.jsonl", "runs/product/ledger_dev_gpt-6.1-terra.jsonl", "study4/lint/runs/ledger_dev_gpt-6.1-terra.jsonl"]}


def prices():
    out = {}
    for m, files in PRICE_LEDGERS.items():
        fits = {}
        for f in files:
            rows = [r for r in ledger(f) if r["usd"] is not None and r["inp"] is not None and r["out"] is not None]
            X = [[r["inp"] - r["cached"], r["cached"], r["out"]] for r in rows]
            y = [r["usd"] for r in rows]
            fit = ols(X, y, ["uncached_input", "cached_input", "output"])
            pred = np.asarray(X, float) @ fit["_b"]
            fits[f] = {"rows": len(rows), "usd_per_million": {k: round(v * 1e6, 5) for k, v in fit["coef"].items()},
                       "max_abs_residual_usd": float(np.max(np.abs(np.asarray(y) - pred))), "r2": fit["r2"]}
        # the provider-billed ledgers (cost field) fit exactly; take the first file as the price list
        ref = fits[files[0]]["usd_per_million"]
        price = {k: round(v, 3) for k, v in ref.items()}
        # check: the product/benchmark ledgers' usd against this price list
        checks = {}
        for f in files:
            rows = [r for r in ledger(f) if r["usd"] is not None and r["inp"] is not None and r["out"] is not None]
            pred = sum(((r["inp"] - r["cached"]) * price["uncached_input"] + r["cached"] * price["cached_input"]
                        + r["out"] * price["output"]) / 1e6 for r in rows)
            checks[f] = {"usd_in_ledger": sum(r["usd"] for r in rows), "usd_at_price_list": pred}
        out[m] = {"usd_per_million_tokens": price, "fits_by_ledger": fits, "ledger_total_vs_price_list": checks}
    return out


PRICE = {}


def usd_of(model, unc, cac, out):
    p = PRICE[model]
    return (unc * p["uncached_input"] + cac * p["cached_input"] + out * p["output"]) / 1e6


# ======================================================================= Study 3 loading
_S3 = None


def study3():
    global _S3
    if _S3 is None:
        sys.path.insert(0, str(TMIS / "analysis"))
        import study3 as s3  # noqa: E402
        spec = json.loads((TMIS / "analysis" / "study3_spec.json").read_text())
        s3.configure(spec)
        st = s3.Study(spec, "fresh2", "confirm", s3.load_data("fresh2"))
        _S3 = (s3, spec, st)
    return _S3


def s3_case_text(regime, case):
    """[(text, is_attachment)] of a Study 3 case."""
    _, _, st = study3()
    if regime == "tenancy":
        return [(s["text"], s.get("role") != "customer_message") for s in st.D["tenancy"].sources(case)]
    return [(st.D["theft"].texts()[case]["text"], False)]


def s3_size(regime, case):
    parts = s3_case_text(regime, case)
    return {"words": sum(words(t) for t, _ in parts), "attachments": sum(a for _, a in parts)}


# ======================================================================= response caches and call classes
class Cache:
    def __init__(self, root):
        self.root, self.memo = Path(root), {}

    def get(self, key):
        """(kind, parsed content or None): kind in routing, conditions, documents, items, tools, other, missing."""
        if key not in self.memo:
            p = self.root / f"{key}.json"
            if not p.exists():
                self.memo[key] = ("missing", None)
            else:
                try:
                    body = json.loads(json.loads(p.read_text())["body"].strip())
                    msg = body["choices"][0]["message"]
                except (ValueError, KeyError, IndexError, TypeError):
                    self.memo[key] = ("other", None)
                    return self.memo[key]
                if msg.get("tool_calls"):
                    self.memo[key] = ("tools", None)
                else:
                    t = msg.get("content") or ""
                    try:
                        j = json.loads(t) if t.lstrip().startswith("{") else None
                    except ValueError:
                        j = None
                    if not isinstance(j, dict):
                        self.memo[key] = ("other", None)
                    elif isinstance(j.get("conditions"), list):
                        self.memo[key] = ("conditions", j["conditions"])
                    elif "other_topic" in j or ("facts" in j and len(j) <= 3):
                        self.memo[key] = ("routing", j)
                    elif isinstance(j.get("documents"), list):
                        self.memo[key] = ("documents", j)
                    elif isinstance(j.get("items"), list):
                        self.memo[key] = ("items", j)
                    else:
                        self.memo[key] = ("other", j)
        return self.memo[key]


STAGES = ("routing", "fact reading 1", "fact readings 2-3", "document judgment: finder", "document judgment: second",
          "quote check", "other (brief, process builder, result checker)", "not attributed")
STAGE_GROUP = {"routing": "routing", "fact reading 1": "fact readings", "fact readings 2-3": "fact readings",
               "document judgment: finder": "document judgments", "document judgment: second": "document judgments",
               "quote check": "quote check", "other (brief, process builder, result checker)": "other",
               "not attributed": "other"}


def split_readings(responses):
    """Reading responses in call order -> groups of response indices; a response answering more than half the facts
    opens a reading, a smaller one is the requote of the reading before it (analysis/study3_feedback.split_readings)."""
    n_facts = max((len({c.get("id") for c in r}) for r in responses), default=0)
    groups = []
    for i, conds in enumerate(responses):
        ids = {c.get("id") for c in conds}
        if len(ids) > n_facts / 2 or not groups:
            groups.append([i])
        else:
            groups[-1].append(i)
    return groups


def classify_run(keys, agents, cache, checklist_scope):
    """keys: distinct call keys in call order; agents: the stored agent list (used only when it lines up).
    Returns ([stage per key], reading groups as lists of key indices)."""
    aligned = agents is not None and len(agents) == len(keys)
    kinds = [cache.get(k) for k in keys]
    stage = [None] * len(keys)
    cond_idx = [i for i, (k, _) in enumerate(kinds) if k == "conditions"]
    groups = split_readings([kinds[i][1] for i in cond_idx])
    reading_groups = [[cond_idx[j] for j in g] for g in groups]
    for gi, g in enumerate(reading_groups):
        for i in g:
            stage[i] = "fact reading 1" if gi == 0 else "fact readings 2-3"
    for i, (kind, _) in enumerate(kinds):
        if stage[i]:
            continue
        a = agents[i] if aligned else None
        if kind == "routing" or a == "router":
            stage[i] = "routing"
        elif kind == "documents":
            stage[i] = "document judgment: second"
        elif kind == "items":
            stage[i] = "quote check"
        elif a == "document_finder" or (kind == "tools" and checklist_scope):
            stage[i] = "document judgment: finder"
        elif a in ("claim_reader", "process_builder", "result_checker", "lead"):
            stage[i] = "other (brief, process builder, result checker)"
        else:
            stage[i] = "not attributed"
    return stage, reading_groups


# ======================================================================= per-file units
def unit(rows, model, words_=None, atts=None, seconds=None, latency=None, extra=None, multiplier=1.0):
    rows = [r for r in rows if r is not None]
    inp = sum(r["inp"] or 0 for r in rows)
    cac = sum(r["cached"] or 0 for r in rows)
    out = sum(r["out"] or 0 for r in rows)
    u = {"usd": multiplier * sum(float(r["usd"] or 0) for r in rows), "calls": multiplier * len(rows),
         "input": multiplier * inp, "cached": multiplier * cac, "uncached": multiplier * (inp - cac), "output": multiplier * out,
         "reasoning": multiplier * sum(r["reasoning"] or 0 for r in rows) if any(r["reasoning"] is not None for r in rows) else None,
         "words": words_, "attachments": atts, "seconds": seconds, "model": model}
    lat = [r["latency"] for r in rows if r["latency"] is not None]
    u["latency_sum"] = multiplier * sum(lat) if lat and len(lat) == len(rows) else latency
    if extra:
        u.update(extra)
    return u


def summarize(units):
    def d(f):
        return dist([u[f] for u in units if u.get(f) is not None])
    return {"files": len(units), "usd_per_file": d("usd"), "paid_calls_per_file": d("calls"),
            "input_tokens_per_file": d("input"), "uncached_input_tokens_per_file": d("uncached"),
            "cached_input_tokens_per_file": d("cached"), "output_tokens_per_file": d("output"),
            "reasoning_tokens_per_file": d("reasoning"), "words_per_file": d("words"), "attachments_per_file": d("attachments"),
            "wall_seconds_per_file (whole run, from the run record)": d("seconds"),
            "latency_seconds_per_file (sum over paid calls, from the ledger)": d("latency_sum")}


# ======================================================================= Study 3 designs
S3_LABEL = {"casepath": "Product, full scope", "casepath_checklist": "Product core (checklist only)",
            "casepath_frontier_checklist": "Product core (checklist only)", "ric": "Rules in context",
            "ric_frontier": "Rules in context", "ric_original": "Rules in context (original rules)",
            "ric_original_frontier": "Rules in context (original rules)", "self_consistency": "Self-consistency (5 samples)",
            "model_executes_rules": "Model executes rules", "react": "ReAct", "core": "Core reading (two readings)"}


def study3_units(cache):
    s3, spec, st = study3()
    out, checks, stage_units = {}, {}, {}
    stored = json.loads((TMIS / "analysis" / "study3_results_fresh2_confirm.json").read_text())
    for d in spec["designs"]:
        key, model = d["key"], d["model"]
        if model not in MODELS:
            continue
        for regime in d["regimes"]:
            if not st.load(key, regime):
                continue
            c = st.cost_spec(key, regime)
            units = []
            if c.get("method") == "plan_keys":
                rows_by_key = {}
                for r in ledger(c["ledger"]):
                    rows_by_key.setdefault(r["key"], r)
                for case, entries in st.entries[(key, regime)].items():
                    sz = s3_size(regime, case)
                    for e in entries:
                        if e is None:
                            continue
                        keys = list(dict.fromkeys(e.get("keys") or []))
                        rows = [rows_by_key.get(k) for k in keys]
                        stage, groups = classify_run(keys, e.get("agents"), cache, key != "casepath")
                        u = unit(rows, model, sz["words"], sz["attachments"], seconds=e.get("seconds"))
                        u["case"] = case
                        u["n_facts_read"] = len({cc.get("id") for i in (groups[0] if groups else []) for cc in cache.get(keys[i])[1]})
                        u["readings"] = len(groups)
                        u["stage"] = {}
                        for k_, s_, r_ in zip(keys, stage, rows):
                            if r_ is None:
                                continue
                            x = u["stage"].setdefault(s_, {"calls": 0, "usd": 0.0, "uncached": 0, "cached": 0, "output": 0})
                            x["calls"] += 1
                            x["usd"] += float(r_["usd"] or 0)
                            x["uncached"] += (r_["inp"] or 0) - (r_["cached"] or 0)
                            x["cached"] += r_["cached"] or 0
                            x["output"] += r_["out"] or 0
                        u["_keys"], u["_groups"], u["_entry"] = keys, groups, e
                        units.append(u)
            elif c.get("method") == "ledger":
                rows = ledger(c["ledger"])
                cases = set(st.cases[regime])
                seen, by = set(), defaultdict(list)
                for r in rows:
                    tagrow = r
                    raw_case = r["case"]
                    if raw_case not in cases:
                        continue
                    ok = True
                    for f, v in c["match"].items():
                        got = {"tag.exp": r["exp"], "tag.method": r["method"], "arm": r["method"]}.get(f)
                        if got != v:
                            ok = False
                    if not ok or (r["key"] is not None and r["key"] in seen):
                        continue
                    seen.add(r["key"])
                    by[(raw_case, tagrow["run"])].append(r)
                mult = float(c.get("multiplier", 1))
                runs = st.runs(key, regime)
                per_run = all(r_ in range(runs) for (_, r_) in by)
                for case in st.cases[regime]:
                    sz = s3_size(regime, case)
                    if per_run:
                        for run in range(runs):
                            u = unit(by.get((case, run), []), model, sz["words"], sz["attachments"], multiplier=mult)
                            u["case"] = case
                            units.append(u)
                    else:  # rows not keyed by run (self-consistency samples): the case's rows shared over its runs
                        rr = [r_ for (cs, _), v in by.items() if cs == case for r_ in v]
                        for run in range(runs):
                            u = unit(rr, model, sz["words"], sz["attachments"], multiplier=mult / runs)
                            u["case"] = case
                            units.append(u)
            else:
                continue
            name = f"study3/{key}/{regime}"
            out[name] = {"design": S3_LABEL.get(key, key), "design_key": key, "model": model, "data": "Study 3 sealed (fresh2)",
                         "regime": regime, "unit": "case-run", "cost_method": c.get("method"),
                         "ledger": c.get("ledger"), "match": c.get("match"), "multiplier": c.get("multiplier", 1),
                         "_units": units}
            mine = sum(u["usd"] for u in units) / len(units)
            ref = (((stored["designs"].get(key) or {}).get("regimes") or {}).get(regime) or {}).get("cost", {}).get("cost_per_case_run")
            checks[name] = {"mean_usd_here": mine, "stored_cost_per_case_run": ref,
                            "equal": ref is not None and abs(mine - ref) < 1e-9}
    return out, checks


# ======================================================================= fair-prompt check
def baseline_units():
    _, _, st = study3()
    out = {}
    for model in MODELS:
        rows = ledger(f"study4/baseline_check/runs/ledger_{model}.jsonl")
        for method, label in (("A", "Prompt that may hold"), ("B", "Model executes rules (with hold rule)")):
            for regime in ("tenancy", "theft"):
                cases = set(st.cases[regime])
                by, seen = defaultdict(list), set()
                for r in rows:
                    if r["method"] != method or r["data"] != "fresh2" or r["case"] not in cases or r["key"] in seen:
                        continue
                    seen.add(r["key"])
                    by[(r["case"], r["run"])].append(r)
                if not by:
                    continue
                units = []
                for (case, run), rr in sorted(by.items()):
                    sz = s3_size(regime, case)
                    u = unit(rr, model, sz["words"], sz["attachments"])
                    u["case"] = case
                    units.append(u)
                out[f"baseline_check/{method}/{regime}/{model}"] = {
                    "design": label, "design_key": {"A": "hold_prompt", "B": "mer_hold"}[method], "model": model,
                    "data": "Study 3 data (fresh2), fair-prompt check", "regime": regime, "unit": "case-run",
                    "cost_method": "ledger rows tag.method == %s, tag.data == fresh2, one per key" % method,
                    "ledger": f"study4/baseline_check/runs/ledger_{model}.jsonl", "_units": units}
    return out


# ======================================================================= benchmark runs of the core (lint)
def dev_size(regime, fid):
    d = DEV / regime / "final" / fid
    if not (d / "text.txt").exists():
        return None, None, []
    texts = [(d / "text.txt").read_text(encoding="utf-8")]
    atts = sorted(p for p in (d / "attachments").glob("*.txt") if not p.name.endswith(".clean.txt")) if (d / "attachments").is_dir() else []
    texts += [p.read_text(encoding="utf-8") for p in atts]
    return sum(words(t) for t in texts), len(atts), texts


def lint_units(cache):
    rows_by_key, paid_by_arm = {}, {}
    for m in MODELS:
        for r in jl(LINT / f"ledger_dev_{m}.jsonl"):
            n = norm(r)
            n["arm"] = r.get("arm")
            rows_by_key.setdefault(n["key"], n)
    out = {}
    for p in sorted(LINT.glob("results_*_*_gpt-*.json")):
        m = re.match(r"results_(.+)_(tenancy|theft|dismissal)_(gpt-.+)\.json$", p.name)
        arm, regime, model = m.groups()
        res = json.loads(p.read_text())
        armname = f"LINT-{arm}-{regime}" + ("" if model == LUNA else f"-{model}")
        units = []
        for fid, e in sorted(res.items()):
            w, na, _ = dev_size(regime, fid)
            keys = list(dict.fromkeys(e.get("keys") or []))
            rows = [rows_by_key.get(k) for k in keys]
            stage, groups = classify_run(keys, None, cache, True)
            u = unit(rows, model, w, na, seconds=e.get("seconds"))
            u["case"], u["status"] = fid, e.get("status")
            u["paid_in_this_arm_usd"] = sum(float(r["usd"] or 0) for r in rows if r is not None and r.get("arm") == armname)
            u["calls_including_repeats"] = e.get("calls")
            u["n_facts_read"] = len({cc.get("id") for i in (groups[0] if groups else []) for cc in cache.get(keys[i])[1]})
            u["readings"] = len(groups)
            u["stage"] = {}
            for s_, r_ in zip(stage, rows):
                if r_ is None:
                    continue
                x = u["stage"].setdefault(s_, {"calls": 0, "usd": 0.0, "uncached": 0, "cached": 0, "output": 0})
                x["calls"] += 1
                x["usd"] += float(r_["usd"] or 0)
                x["uncached"] += (r_["inp"] or 0) - (r_["cached"] or 0)
                x["cached"] += r_["cached"] or 0
                x["output"] += r_["out"] or 0
            u["_keys"], u["_groups"], u["_entry"], u["regime"] = keys, groups, e, regime
            units.append(u)
        out[f"lint/{arm}/{regime}/{model}"] = {
            "design": "Product core (checklist only), benchmark" + ("" if arm == "clean" else f", arm {arm}"),
            "design_key": "core_three", "arm": arm, "model": model, "data": "public-rule benchmark (study4/dev)", "regime": regime,
            "unit": "file (one run)", "cost_method": "each distinct key of the run's stored key list joined to the benchmark ledgers (whoever paid it)",
            "ledger": f"study4/lint/runs/ledger_dev_{model}.jsonl", "_units": units}
    return out


# ======================================================================= stage split
def stage_split(groups):
    out = {}
    for name, g in groups.items():
        units = [u for u in g["_units"] if "stage" in u]
        if not units:
            continue
        n = len(units)
        tot = sum(u["usd"] for u in units)
        st_ = {}
        for s in STAGES:
            calls = sum(u["stage"].get(s, {}).get("calls", 0) for u in units)
            usd = sum(u["stage"].get(s, {}).get("usd", 0.0) for u in units)
            if calls:
                st_[s] = {"calls_per_file": calls / n, "usd_per_file": usd / n, "share_of_cost": usd / tot if tot else None}
        grp = defaultdict(float)
        for s, v in st_.items():
            grp[STAGE_GROUP[s]] += v["share_of_cost"] or 0
        out[name] = {"files": n, "usd_per_file": tot / n, "by_stage": st_, "share_by_group": dict(grp),
                     "readings_per_file": dict(Counter(u.get("readings") for u in units))}
    return out


# ======================================================================= regressions on the benchmark runs
def regressions(units, label):
    us = [u for u in units if u["words"] is not None and u.get("status", "completed") == "completed"]
    y = [u["usd"] for u in us]
    W = [u["words"] for u in us]
    A = [u["attachments"] for u in us]
    F = [u["n_facts_read"] for u in us]
    out = {"label": label, "files": len(us),
           "range": {"words": [min(W), max(W)], "attachments": [min(A), max(A)], "facts_read": [min(F), max(F)],
                     "usd": [min(y), max(y)]}}
    specs = {"words": (["intercept", "words"], [[1, w] for w in W]),
             "facts_read": (["intercept", "facts_read"], [[1, f] for f in F]),
             "attachments": (["intercept", "attachments"], [[1, a] for a in A]),
             "joint": (["intercept", "words", "attachments", "facts_read"], [[1, w, a, f] for w, a, f in zip(W, A, F)])}
    for nm, (names, X) in specs.items():
        f = ols(X, y, names)
        f.pop("_b")
        out[nm] = f
    # correlations among the predictors (collinearity check)
    M = np.array([W, A, F], float)
    C = np.corrcoef(M)
    out["predictor_correlation"] = {"words~attachments": float(C[0, 1]), "words~facts_read": float(C[0, 2]),
                                    "attachments~facts_read": float(C[1, 2])}
    return out


# ======================================================================= adaptive readings
def reading_values(conds, texts):
    """{fact: (value or None, quoted)} of one reading's responses (later answers for a fact replace earlier ones).
    value: the verdict true/false of a boolean, or the value of an enum answered true; quoted: a non-empty quote that
    occurs in the file (case and whitespace normalized)."""
    hay = [normtext(t) for t in texts]
    out = {}
    for c in conds:
        fid = c.get("id")
        v, verdict = c.get("value"), c.get("verdict")
        if verdict == "true" and v not in (None, ""):
            val = v
        elif verdict in ("true", "false") and v in (None, ""):
            val = verdict == "true"
        else:
            val = None
        qt = normtext(c.get("quote"))
        quoted = bool(qt) and any(qt in h for h in hay)
        out[fid] = (val, quoted)
    return out


def adaptive_from(units, cache, texts_of, model):
    """Per fact read in the first reading: is the first reading a quoted true/false (or quoted enum value)? Does it equal
    the value the product admitted after three readings? What did readings 2 and 3 say?"""
    c = Counter()
    file_costs = []
    for u in units:
        keys, groups, e = u["_keys"], u["_groups"], u["_entry"]
        if len(groups) < 1:
            continue
        texts = texts_of(u)
        reads = [reading_values([cc for i in g for cc in cache.get(keys[i])[1]], texts) for g in groups]
        final = ((e.get("product_extra") or {}).get("facts") or {})
        first = reads[0]
        need = 0
        for fid, (val, quoted) in first.items():
            fin = final.get(fid) or {}
            if fin.get("by") == "routing":
                continue  # the routing fact is admitted by routing, not by the readings
            c["facts read"] += 1
            admitted = fin.get("status") == "established" and fin.get("verdict") != "rejected"
            adm_val = fin.get("value") if admitted else None
            settled = val is not None and quoted
            if not settled:
                c["first reading not a quoted value (re-read under adaptive)"] += 1
                need += 1
                continue
            c["first reading a quoted value"] += 1
            if admitted and adm_val == val:
                c["  ... equals the admitted value"] += 1
            elif admitted:
                c["  ... admitted value differs"] += 1
            else:
                c["  ... nothing admitted after three readings"] += 1
            others = [r.get(fid) for r in reads[1:3]]
            if len(others) == 2 and all(o is not None for o in others):
                vals = [o[0] if (o[0] is not None and o[1]) else None for o in others]
                if vals[0] == vals[1] and vals[0] != val:
                    c["  ... readings 2 and 3 agree with each other against it"] += 1
                    if vals[0] is None:
                        c["      (both give no quoted value)"] += 1
                    else:
                        c["      (both give the same other value)"] += 1
                elif vals[0] != val or vals[1] != val:
                    c["  ... at least one of readings 2 and 3 differs"] += 1
        # counterfactual cost of this file under adaptive re-reading
        n = len([f for f in first if (final.get(f) or {}).get("by") != "routing"])
        later = [i for g in groups[1:] for i in g]
        stage_r23 = 0.0
        adapt_r23 = 0.0
        for i in later:
            r = u["_rowmap"].get(keys[i])
            if r is None:
                continue
            stage_r23 += float(r["usd"] or 0)
            if need:
                adapt_r23 += usd_of(model, (r["inp"] or 0) - (r["cached"] or 0), r["cached"] or 0, 0) + \
                    usd_of(model, 0, 0, (r["out"] or 0)) * (need / n if n else 1)
        file_costs.append({"usd": u["usd"], "usd_adaptive": u["usd"] - stage_r23 + adapt_r23, "any_reread": need > 0,
                           "n": n, "need": need})
    tot = c["facts read"]
    s = c["first reading a quoted value"]
    res = {"counts": dict(c),
           "share_first_reading_quoted_value": s / tot if tot else None,
           "share_first_reading_alone_equals_admitted (of all facts read)": c["  ... equals the admitted value"] / tot if tot else None,
           "share_needing_rereading_under_adaptive (p)": 1 - s / tot if tot else None,
           "of quoted first readings: share where three readings admitted nothing (adaptive would admit the first value)":
               c["  ... nothing admitted after three readings"] / s if s else None,
           "of quoted first readings: share where readings 2 and 3 agreed against it (first alone 'wrong' against three)":
               c["  ... readings 2 and 3 agree with each other against it"] / s if s else None,
           "files": len(file_costs),
           "share_of_files_with_any_reread": sum(f["any_reread"] for f in file_costs) / len(file_costs) if file_costs else None,
           "usd_per_file_three": statistics.mean(f["usd"] for f in file_costs) if file_costs else None,
           "usd_per_file_adaptive_counterfactual": statistics.mean(f["usd_adaptive"] for f in file_costs) if file_costs else None}
    if file_costs:
        res["saving_share"] = 1 - res["usd_per_file_adaptive_counterfactual"] / res["usd_per_file_three"]
    return res


# ======================================================================= single prompts: fixed text vs file
RULE_SHARE_CHARS = {}


def rule_share_from_rendered():
    """Share of the fixed prompt that is rule material (policy, rule packs, source passages), by characters of the
    rendered prompts of the prompt that may hold: 1 - (task + schema) / (system + schema); the task is part of system."""
    R = BC / "prompts" / "rendered"
    out = {}
    for regime in ("tenancy", "theft"):
        sysc = len((R / f"A_{regime}_system.txt").read_text())
        sch = len((R / f"A_{regime}_schema.txt").read_text())
        task = len((BC / "prompts" / f"A_{regime}_task.txt").read_text())
        out[regime] = {"system_chars": sysc, "schema_chars": sch, "task_chars": task, "rule_share": 1 - (task + sch) / (sysc + sch)}
    return out


def single_prompt_fit(group_by_regime, label):
    """Per call: input tokens = fixed(regime) + tokens_per_word * words; output per call; cached share."""
    rows = []
    for regime, units in group_by_regime.items():
        for u in units:
            if u["calls"] == 0 or u["words"] is None:
                continue
            rows.append((regime, u["words"], u["input"] / u["calls"], u["output"] / u["calls"], u["cached"] / max(u["input"], 1),
                         u["calls"]))
    regs = sorted({r[0] for r in rows})
    X = [[1 if r[0] == g else 0 for g in regs] + [r[1]] for r in rows]
    f = ols(X, [r[2] for r in rows], [f"fixed_{g}" for g in regs] + ["tokens_per_word"])
    fo = ols([[1 if r[0] == g else 0 for g in regs] + [r[1]] for r in rows], [r[3] for r in rows],
             [f"output_{g}" for g in regs] + ["output_per_word"])
    f.pop("_b"), fo.pop("_b")
    per = {}
    for g in regs:
        rr = [r for r in rows if r[0] == g]
        per[g] = {"files": len(rr), "words_range": [min(r[1] for r in rr), max(r[1] for r in rr)],
                  "input_per_call_mean": statistics.mean(r[2] for r in rr), "output_per_call_mean": statistics.mean(r[3] for r in rr),
                  "cached_share_mean": statistics.mean(r[4] for r in rr), "calls_per_file_mean": statistics.mean(r[5] for r in rr)}
    return {"label": label, "input_fit": f, "output_fit": fo, "by_regime": per}


# ======================================================================= main build
def build():
    global PRICE
    pr = prices()
    PRICE = {m: pr[m]["usd_per_million_tokens"] for m in MODELS}
    pcache = Cache(TMIS / "runs" / "product" / "cache")
    lcache = Cache(LINT / "cache")

    s3g, s3checks = study3_units(pcache)
    bcg = baseline_units()
    lg = lint_units(lcache)
    groups = {**s3g, **bcg, **lg}

    # row maps for the adaptive counterfactual
    rk = {}
    for f in ("runs/product/ledger_dev_gpt-6-luna.jsonl", "runs/product/ledger_dev_gpt-6.1-terra.jsonl"):
        for r in ledger(f):
            rk.setdefault(r["key"], r)
    lk = {}
    for m in MODELS:
        for r in ledger(f"study4/lint/runs/ledger_dev_{m}.jsonl"):
            lk.setdefault(r["key"], r)
    for name, g in groups.items():
        for u in g["_units"]:
            if "_keys" in u:
                u["_rowmap"] = lk if name.startswith("lint/") else rk

    # 1. table per design x model x data set
    table = {}
    for name, g in groups.items():
        table[name] = {k: v for k, v in g.items() if not k.startswith("_")}
        table[name].update(summarize(g["_units"]))
        if name.startswith("lint/"):
            table[name]["paid_in_this_arm_usd_per_file"] = dist([u["paid_in_this_arm_usd"] for u in g["_units"]])
            table[name]["calls_including_cache_repeats_per_file"] = dist([u["calls_including_repeats"] for u in g["_units"]])
            table[name]["status"] = dict(Counter(u["status"] for u in g["_units"]))
        if any("n_facts_read" in u for u in g["_units"]):
            table[name]["facts_read_per_file"] = dist([u.get("n_facts_read") for u in g["_units"]])

    # summary for today's short files: design x model, pooled over regimes (Study 3 and fair-prompt check: case-runs;
    # benchmark: clean arm files)
    pools = defaultdict(list)
    for name, g in groups.items():
        if name.startswith("lint/") and g.get("arm") != "clean":
            continue
        src = "benchmark" if name.startswith("lint/") else "Study 3 data"
        pools[(g["design"].replace(", benchmark", ""), g["model"], src)].extend(g["_units"])
    summary = [{"design": d, "model": m, "data": src, "files": len(us), "usd": dist([u["usd"] for u in us]),
                "calls": statistics.mean(u["calls"] for u in us),
                "words": [min(u["words"] for u in us if u["words"] is not None), max(u["words"] for u in us if u["words"] is not None)]}
               for (d, m, src), us in pools.items()]

    # 2. stage split (core and full product)
    core_groups = {n: g for n, g in groups.items() if n.startswith("lint/clean/") or n.startswith("study3/casepath")}
    stages = stage_split(core_groups)
    # pooled benchmark, clean arm, per model
    for m in MODELS:
        pooled = [u for n, g in groups.items() if n.startswith("lint/clean/") and g["model"] == m for u in g["_units"]]
        stages[f"lint/clean/ALL/{m}"] = stage_split({"x": {"_units": pooled}})["x"]

    # regressions on the benchmark runs (clean arm)
    reg = {}
    for m in MODELS:
        pooled = [u for n, g in groups.items() if n.startswith("lint/clean/") and g["model"] == m for u in g["_units"]]
        reg[f"lint/clean/ALL/{m}"] = regressions(pooled, f"benchmark, clean arm, {MODEL_LABEL[m]}, all regimes")
        regs_here = sorted({u["regime"] for u in pooled})
        if len(regs_here) == 1:
            reg[f"lint/clean/ALL/{m}"]["label"] = f"benchmark, clean arm, {MODEL_LABEL[m]}, {regs_here[0]} only"
            continue
        for regime in ("tenancy", "theft", "dismissal"):
            us = [u for u in pooled if u["regime"] == regime]
            if len(us) >= 10:
                reg[f"lint/clean/{regime}/{m}"] = regressions(us, f"benchmark, clean arm, {MODEL_LABEL[m]}, {regime}")
    s3c = [u for n, g in groups.items() if n == "study3/casepath_checklist/tenancy" for u in g["_units"]]
    for u in s3c:
        u.setdefault("status", "completed")
    reg["study3/casepath_checklist/tenancy/gpt-6-luna"] = regressions(s3c, "Study 3, core (checklist only), cost-efficient model, tenancy (case-runs)")

    # 4. adaptive shares
    _, _, st = study3()
    adaptive = {}
    for n, g in groups.items():
        if not (n.startswith("lint/clean/") or n.startswith("study3/casepath_checklist/") or n.startswith("study3/casepath_frontier_checklist/")):
            continue
        if n.startswith("lint/"):
            texts_of = lambda u, reg_=g["regime"]: dev_size(reg_, u["case"])[2]
            cache = lcache
        else:
            texts_of = lambda u, reg_=g["regime"]: [t for t, _ in s3_case_text(reg_, u["case"])]
            cache = pcache
        units = [u for u in g["_units"] if u.get("status", "completed") == "completed"]
        adaptive[n] = adaptive_from(units, cache, texts_of, g["model"])
    for m in MODELS:
        tot = Counter()
        for n, a in list(adaptive.items()):
            if g_model(n) == m and n.startswith("lint/"):
                tot.update(a["counts"])
        fr = tot["facts read"]
        adaptive[f"BENCHMARK/{m}"] = {"counts": dict(tot),
                                "share_needing_rereading_under_adaptive (p)": 1 - tot["first reading a quoted value"] / fr if fr else None,
                                "share_first_reading_alone_equals_admitted (of all facts read)": tot["  ... equals the admitted value"] / fr if fr else None}

    # 3. single prompts: fixed text vs file
    rs = rule_share_from_rendered()
    sp = {}

    def byreg(prefix_fn):
        out = defaultdict(list)
        for n, g in groups.items():
            if prefix_fn(n, g):
                out[g["regime"]].extend(g["_units"])
        return out
    sp_defs = {
        ("hold_prompt", LUNA): lambda n, g: n.startswith("baseline_check/A/") and g["model"] == LUNA,
        ("hold_prompt", TERRA): lambda n, g: n.startswith("baseline_check/A/") and g["model"] == TERRA,
        ("mer", LUNA): lambda n, g: n.startswith("study3/model_executes_rules/"),
        ("mer", TERRA): lambda n, g: n.startswith("baseline_check/B/") and g["model"] == TERRA,
        ("ric", LUNA): lambda n, g: n.startswith("study3/ric/"),
        ("ric", TERRA): lambda n, g: n.startswith("study3/ric_frontier/"),
        ("sc_sample", LUNA): lambda n, g: n.startswith("study3/self_consistency/"),
        ("react", LUNA): lambda n, g: n.startswith("study3/react/"),
    }
    for (d, m), fn in sp_defs.items():
        sp[f"{d}/{m}"] = single_prompt_fit(byreg(fn), f"{d} on the {MODEL_LABEL[m]}")
        fit = sp[f"{d}/{m}"]["input_fit"]["coef"]
        sp[f"{d}/{m}"]["rule_text_tokens_by_regime (fixed x rule share)"] = {
            g: fit[f"fixed_{g}"] * rs[g]["rule_share"] for g in ("tenancy", "theft") if f"fixed_{g}" in fit}
    params = estimator_params(groups, sp, rs, adaptive, stages)
    grid = make_grid(params)
    timing = {n: {"design": t["design"], "model": t["model"], "regime": t["regime"], "data": t["data"],
                  "wall_seconds_per_file": t["wall_seconds_per_file (whole run, from the run record)"],
                  "latency_seconds_per_file": t["latency_seconds_per_file (sum over paid calls, from the ledger)"]}
              for n, t in table.items()}
    res = {"generated_by": "rebuild/plan/cost_model.py", "model_calls": 0, "prices": pr, "ledger_fields": __doc__.split("Ledger fields used:")[1].strip(),
           "summary_today": summary, "per_design": table, "study3_cost_check_against_stored_results": s3checks, "core_stage_split": stages,
           "regressions": reg, "single_prompts": sp, "rule_share_of_fixed_prompt": rs, "adaptive_readings": adaptive,
           "estimator_params": params, "grid": grid, "timing": timing}
    return res


def g_model(name):
    return TERRA if TERRA in name or "frontier" in name else LUNA


# ======================================================================= estimator
def estimator_params(groups, sp, rs, adaptive, stages):
    """Token models behind estimate(). Core: per stage, tokens (uncached input, cached input, output) per file =
    b0 + b_w * words + b_a * attachments + b_f * facts_read, fitted on the benchmark's clean arm (cost-efficient model,
    176 files); the frontier model's tokens = the cost-efficient model's x the per-stage ratio on the 38 tenancy files
    both models ran. Routing's fixed input scales with the rule catalogue (the only call that sees more than the
    selected workflow). Single prompts: input per call = instructions + rule text + tokens_per_word x words."""
    luna = [u for n, g in groups.items() if n.startswith("lint/clean/") and g["model"] == LUNA for u in g["_units"]
            if u["status"] == "completed" and u["words"] is not None]
    terra = {u["case"]: u for n, g in groups.items() if n.startswith("lint/clean/") and g["model"] == TERRA for u in g["_units"]
             if u["status"] == "completed"}
    core = {}
    for s_ in STAGES:
        withc = [u for u in luna if u["stage"].get(s_, {}).get("calls")]
        if not withc:
            continue
        # input per call = base + per_word x words (each call carries the instructions and, for most stages, the file)
        fi = ols([[1, u["words"]] for u in withc],
                 [(u["stage"][s_]["uncached"] + u["stage"][s_]["cached"]) / u["stage"][s_]["calls"] for u in withc],
                 ["base", "per_word"])
        # calls per file and output per file: linear in attachments and facts read (output also in words)
        fc = ols([[1, u["attachments"], u["n_facts_read"]] for u in luna], [u["stage"].get(s_, {}).get("calls", 0) for u in luna],
                 ["intercept", "attachments", "facts_read"])
        fo = ols([[1, u["attachments"], u["n_facts_read"]] for u in luna],
                 [u["stage"].get(s_, {}).get("output", 0) for u in luna], ["intercept", "attachments", "facts_read"])
        fow = ols([[1, u["words"], u["attachments"], u["n_facts_read"]] for u in luna],
                  [u["stage"].get(s_, {}).get("output", 0) for u in luna], ["intercept", "words", "attachments", "facts_read"])
        ti = sum(u["stage"][s_]["uncached"] + u["stage"][s_]["cached"] for u in withc)
        core[s_] = {"input_per_call": {"coef": fi["coef"], "r2": fi["r2"]}, "calls": {"coef": fc["coef"], "r2": fc["r2"]},
                    "output": {"coef": fo["coef"], "r2": fo["r2"]},
                    "output_with_words (sensitivity)": {"coef": fow["coef"], "r2": fow["r2"]},
                    "cached_share": sum(u["stage"][s_]["cached"] for u in withc) / ti if ti else 0.0}
    ratio = {}
    paired = [(u, terra[u["case"]]) for u in luna if u["case"] in terra and u["regime"] == "tenancy"]
    for s in STAGES:
        ratio[s] = {}
        for k in ("input", "output"):
            if k == "input":
                a = sum(lu["stage"].get(s, {}).get("uncached", 0) + lu["stage"].get(s, {}).get("cached", 0) for lu, _ in paired)
                b = sum(te["stage"].get(s, {}).get("uncached", 0) + te["stage"].get(s, {}).get("cached", 0) for _, te in paired)
            else:
                a = sum(lu["stage"].get(s, {}).get("output", 0) for lu, _ in paired)
                b = sum(te["stage"].get(s, {}).get("output", 0) for _, te in paired)
            ratio[s][k] = b / a if a else None
        ci = sum(te["stage"].get(s, {}).get("cached", 0) for _, te in paired)
        ti = sum(te["stage"].get(s, {}).get("uncached", 0) + te["stage"].get(s, {}).get("cached", 0) for _, te in paired)
        ratio[s]["cached_share_frontier"] = ci / ti if ti else None
    ranges = {"words": [min(u["words"] for u in luna), max(u["words"] for u in luna)],
              "attachments": [min(u["attachments"] for u in luna), max(u["attachments"] for u in luna)],
              "facts_read": [min(u["n_facts_read"] for u in luna), max(u["n_facts_read"] for u in luna)],
              "facts_read_median": statistics.median(u["n_facts_read"] for u in luna)}
    p_adapt = {m: adaptive[f"BENCHMARK/{m}"]["share_needing_rereading_under_adaptive (p)"] for m in MODELS}
    # one regime's rule text: the prompt that may hold, cost-efficient model, mean of tenancy and theft
    rt = sp[f"hold_prompt/{LUNA}"]["rule_text_tokens_by_regime (fixed x rule share)"]
    R1 = statistics.mean(rt.values())
    singles = {}
    for key, fit in sp.items():
        d, m = key.split("/")
        c = fit["input_fit"]["coef"]
        regs = [g for g in ("tenancy", "theft") if f"fixed_{g}" in c]
        instr = statistics.mean(c[f"fixed_{g}"] * (1 - rs[g]["rule_share"]) for g in regs)
        rule = statistics.mean(c[f"fixed_{g}"] * rs[g]["rule_share"] for g in regs)
        br = fit["by_regime"]
        words_all = [x for g in regs for x in br[g]["words_range"]]
        singles[key] = {"instructions_tokens": instr, "rule_tokens_measured": rule, "tokens_per_word": c["tokens_per_word"],
                        "output_per_call": statistics.mean(br[g]["output_per_call_mean"] for g in regs),
                        "cached_share": statistics.mean(br[g]["cached_share_mean"] for g in regs),
                        "calls_per_file": statistics.mean(br[g]["calls_per_file_mean"] for g in regs),
                        "words_range": [min(words_all), max(words_all)]}
    # ReAct: input per file relative to one Rules-in-context call (same model, same regime), averaged over regimes
    react_mult = statistics.mean(sp[f"react/{LUNA}"]["by_regime"][g]["input_per_call_mean"] * sp[f"react/{LUNA}"]["by_regime"][g]["calls_per_file_mean"]
                                 / sp[f"ric/{LUNA}"]["by_regime"][g]["input_per_call_mean"] for g in ("tenancy", "theft"))
    return {"core_stage_tokens_luna": core, "frontier_over_cost_efficient_token_ratio_by_stage": ratio,
            "paired_tenancy_files_for_ratio": len(paired), "core_ranges_benchmark": ranges,
            "core_routing_fixed_input_scales_with_rule_text": True, "adaptive_p_needing_rereading": p_adapt,
            "rule_text_tokens_one_regime": R1, "rule_text_tokens_by_regime_hold_prompt": rt,
            "single_prompts": singles, "react_input_per_file_over_one_ric_call": react_mult,
            "measured_rule_text_tokens_max": max(max(v["rule_text_tokens_by_regime (fixed x rule share)"].values()) for v in sp.values()),
            "prices": PRICE}


PARAMS = None


def _params():
    global PARAMS, PRICE
    if PARAMS is None:
        PARAMS = json.loads(OUT_JSON.read_text())["estimator_params"]
        PRICE = PARAMS["prices"]
    return PARAMS


def core_cost(model, words_, n_att, n_facts, rule_tokens, policy, output_scales_with_words=False):
    P = _params()
    core, ratio = P["core_stage_tokens_luna"], P["frontier_over_cost_efficient_token_ratio_by_stage"]
    R1 = P["rule_text_tokens_one_regime"]
    p = P["adaptive_p_needing_rereading"][model]
    tot, parts = 0.0, {}
    for s, m_ in core.items():
        c, ip, o = m_["calls"]["coef"], m_["input_per_call"]["coef"], m_["output"]["coef"]
        calls = max(0.0, c["intercept"] + c["attachments"] * n_att + c["facts_read"] * n_facts)
        per_call = max(0.0, ip["base"] + ip["per_word"] * words_)
        if s == "routing" and rule_tokens is not None:
            per_call += max(0.0, ip["base"]) * (rule_tokens / R1 - 1)
        inp = calls * per_call
        if output_scales_with_words:
            o = m_["output_with_words (sensitivity)"]["coef"]
            out = max(0.0, o["intercept"] + o["words"] * words_ + o["attachments"] * n_att + o["facts_read"] * n_facts)
        else:
            out = max(0.0, o["intercept"] + o["attachments"] * n_att + o["facts_read"] * n_facts)
        cs = m_["cached_share"]
        if s == "fact readings 2-3" and policy == "adaptive":
            any_re = 1 - (1 - p) ** max(n_facts, 1)
            inp, out = inp * any_re, out * p
        if model == TERRA:
            r = ratio.get(s) or {}
            if r.get("input") is not None:
                inp, out, cs = inp * r["input"], out * (r.get("output") or 1.0), r.get("cached_share_frontier") or 0.0
        usd = usd_of(model, inp * (1 - cs), inp * cs, out)
        parts[s] = usd
        tot += usd
    return tot, parts


def single_cost(key, model, words_, rule_tokens, calls=None):
    P = _params()
    s = P["single_prompts"].get(f"{key}/{model}")
    price_scaled = False
    if s is None:  # no run on this model: the cost-efficient model's tokens at this model's prices
        s = P["single_prompts"][f"{key}/{LUNA}"]
        price_scaled = True
    rule = s["rule_tokens_measured"] if rule_tokens is None else rule_tokens
    inp = s["instructions_tokens"] + rule + s["tokens_per_word"] * words_
    if key == "react":
        ric = P["single_prompts"][f"ric/{LUNA}"]
        inp = P["react_input_per_file_over_one_ric_call"] * (ric["instructions_tokens"] + rule + ric["tokens_per_word"] * words_)
        n = 1
    else:
        n = calls if calls is not None else s["calls_per_file"]
    cac = inp * s["cached_share"]
    out = s["output_per_call"] if key != "react" else s["output_per_call"] * s["calls_per_file"]
    return n * usd_of(model, inp - cac, cac, out), price_scaled, s


DESIGNS = ("core_three", "core_adaptive", "hold_prompt", "self_consistency_matched", "mer", "react", "ric")


def estimate(design, model, words, n_attachments, n_facts, rule_text_tokens=None, readings_policy="three"):
    """USD per file with its assumptions.
    design: core_three | core_adaptive | core (with readings_policy) | hold_prompt (prompt that may hold) | ric (Rules in
    context) | self_consistency_matched (Rules-in-context samples, as many as the core's cost buys) | mer (Model executes
    rules) | react. model: gpt-6-luna | gpt-6.1-terra. words: words in the file plus attachments. rule_text_tokens: tokens
    of the whole rule catalogue a single prompt carries (None = as measured for one regime). readings_policy: three |
    adaptive (core only)."""
    P = _params()
    R1 = P["rule_text_tokens_one_regime"]
    rng = P["core_ranges_benchmark"]
    flags = []
    if design in ("core_three", "core_adaptive", "core"):
        pol = {"core_three": "three", "core_adaptive": "adaptive"}.get(design, readings_policy)
        usd, parts = core_cost(model, words, n_attachments, n_facts, rule_text_tokens, pol)
        if not rng["words"][0] <= words <= rng["words"][1]:
            flags.append(f"words outside the benchmark's {rng['words']}")
        if not rng["attachments"][0] <= n_attachments <= rng["attachments"][1]:
            flags.append(f"attachments outside the benchmark's {rng['attachments']}")
        if not rng["facts_read"][0] <= n_facts <= rng["facts_read"][1]:
            flags.append(f"facts read outside the benchmark's {rng['facts_read']}")
        if rule_text_tokens is not None and rule_text_tokens > P["measured_rule_text_tokens_max"]:
            flags.append("rule catalogue larger than any measured (routing input scaled)")
        if model == TERRA:
            flags.append("frontier tokens = cost-efficient tokens x per-stage ratio from 38 tenancy files")
        return {"usd": usd, "by_stage": parts, "extrapolated": bool([f for f in flags if "outside" in f or "larger" in f]),
                "flags": flags, "assumptions": [
                    "per stage: calls x (base + per_word x words) input tokens, calls and output linear in attachments and facts read; fitted on the benchmark's clean arm (cost-efficient model, 173 files with texts)",
                    "adaptive: readings 2-3 are paid for a file with probability 1-(1-p)^facts, their output in proportion p, "
                    f"p = {P['adaptive_p_needing_rereading'][model]:.3f} (share of facts whose first reading is not a quoted value)"
                    if pol == "adaptive" else "three readings of every deciding fact, as tested",
                    "only routing sees the whole catalogue; its fixed input scales with rule_text_tokens / one regime's"]}
    key = {"self_consistency_matched": "sc_sample"}.get(design, design)
    if design == "self_consistency_matched":
        core_usd = core_cost(model, words, n_attachments, n_facts, rule_text_tokens, "three")[0]
        one, scaled, s = single_cost("sc_sample", model, words, rule_text_tokens, calls=1)
        m = max(1, int(core_usd // one)) if one > 0 else 1
        usd = m * one
        flags.append(f"{m} samples at USD {one:.6f} each match the core's USD {core_usd:.6f}")
    else:
        usd, scaled, s = single_cost(key, model, words, rule_text_tokens)
    if scaled:
        flags.append("no run on this model: cost-efficient model's tokens at this model's prices")
    if not s["words_range"][0] <= words <= s["words_range"][1]:
        flags.append(f"words outside the measured {s['words_range']}")
    if rule_text_tokens is not None and rule_text_tokens > P["measured_rule_text_tokens_max"]:
        flags.append("rule text larger than any measured")
    return {"usd": usd, "extrapolated": any(("outside" in f or "larger" in f or "no run" in f) for f in flags), "flags": flags,
            "assumptions": ["input per call = instructions + rule text + tokens_per_word x words; output per call and the "
                            "cached share of input as measured (mean over regimes)",
                            "attachments enter only through their words"]}


GRID_WORDS = (250, 800, 2500)
GRID_ATT = (0, 3, 6)
GRID_REGIMES = (1, 3, 4)
GRID_DESIGNS = (("core_three", "Product core, three readings"), ("core_adaptive", "Product core, adaptive readings"),
                ("hold_prompt", "Prompt that may hold"), ("self_consistency_matched", "Self-consistency, cost-matched to the core"),
                ("mer", "Model executes rules"), ("react", "ReAct"))


def make_grid(params):
    global PARAMS
    PARAMS = params
    R1 = params["rule_text_tokens_one_regime"]
    nf = params["core_ranges_benchmark"]["facts_read_median"]
    rows = []
    for d, label in GRID_DESIGNS:
        for m in MODELS:
            for w in GRID_WORDS:
                for a in GRID_ATT:
                    for nr in GRID_REGIMES:
                        e = estimate(d, m, w, a, nf, R1 * nr)
                        rows.append({"design": d, "label": label, "model": m, "words": w, "attachments": a, "regimes": nr,
                                     "rule_text_tokens": R1 * nr, "facts_read": nf, "usd": e["usd"], "extrapolated": e["extrapolated"],
                                     "flags": e["flags"]})
    return {"facts_read_assumed": nf, "rule_text_tokens_one_regime": R1, "rows": rows}


# ======================================================================= markdown
def f6(x):
    return "–" if x is None else f"{x:.6f}" if abs(x) < 0.01 else f"{x:.4f}"


def fnum(x, nd=0):
    return "–" if x is None else f"{x:,.{nd}f}"


def markdown(res):
    L = []
    P = res["prices"]
    L += ["# Cost model for planning (stored ledgers only)", "",
          "Generated by `rebuild/plan/cost_model.py` from stored ledgers, run results and response caches. No model was called "
          "and nothing was spent. Every number below is reproducible with `python3 rebuild/plan/cost_model.py`.", "",
          "## Ledger fields used", "", res["ledger_fields"].replace("\n", " "), "",
          "Cost per file is the sum of the `usd` (or `cost`) field of the file's paid calls. For the product, the file's stored "
          "list of call keys is joined to the ledger whoever paid the call (as analysis/study3.py does), so a call answered from "
          "the cache in one arm still counts at what it cost when first paid. Other designs: the ledger rows of the design's "
          "tag or arm, one per key, grouped by (case, run). The Study 3 means reproduce the stored cost table exactly "
          f"({sum(v['equal'] for v in res['study3_cost_check_against_stored_results'].values())} of "
          f"{len(res['study3_cost_check_against_stored_results'])} design × regime cells equal).", "",
          "## Implied token prices (USD per million tokens)", "",
          "| Model | Uncached input | Cached input | Output |", "|---|---|---|---|"]
    for m in MODELS:
        p = P[m]["usd_per_million_tokens"]
        L.append(f"| {MODEL_LABEL[m]} | {p['uncached_input']} | {p['cached_input']} | {p['output']} |")
    L += ["", "Fitted by least squares of the billed cost on (uncached input, cached input, output) tokens per call; the "
          "provider-billed ledgers (runs/v2/cp4, fair-prompt check) fit exactly. Reasoning tokens are billed as output "
          "(completion_tokens includes them). The product and benchmark ledgers' `usd` is within about 0.5 % of this list "
          "(they count about 25 input tokens per call more than were billed):", ""]
    L += ["| Model | Ledger | Rows | Fitted uncached / cached / output | Max abs. residual (USD) |", "|---|---|---|---|---|"]
    for m in MODELS:
        for f, v in P[m]["fits_by_ledger"].items():
            c = v["usd_per_million"]
            L.append(f"| {m} | `{f}` | {v['rows']:,} | {c['uncached_input']} / {c['cached_input']} / {c['output']} | {v['max_abs_residual_usd']:.2e} |")
    L += ["", "## Summary: USD per file at today's file sizes (pooled over regimes)", "",
          "| Design | Model | Data | Files | Words per file | Calls | USD mean | USD median | USD p90 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in res["summary_today"]:
        L.append(f"| {r['design']} | {r['model']} | {r['data']} | {r['files']} | {r['words'][0]}-{r['words'][1]} | {r['calls']:.1f} | "
                 f"{f6(r['usd']['mean'])} | {f6(r['usd']['median'])} | {f6(r['usd']['p90'])} |")
    L += ["", "## 1. USD per file by design × model × data set", "",
          "Files = case-runs on Study 3 and the fair-prompt check (each case run 1 or 3 times), files on the benchmark (one run). "
          "Tokens are per file, summed over paid calls; input includes cached.", "",
          "| Design | Model | Data | Regime | Files | Calls | Uncached in | Cached in | Output | USD mean | USD median | USD p90 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, t in res["per_design"].items():
        u = t["usd_per_file"]
        L.append(f"| {t['design']} | {t['model']} | {t['data']} | {t['regime']} | {t['files']} | {fnum(t['paid_calls_per_file']['mean'], 1)} | "
                 f"{fnum(t['uncached_input_tokens_per_file']['mean'])} | {fnum(t['cached_input_tokens_per_file']['mean'])} | "
                 f"{fnum(t['output_tokens_per_file']['mean'])} | {f6(u['mean'])} | {f6(u['median'])} | {f6(u['p90'])} |")
    L += ["", "Benchmark rows other than the clean arm (blunt, subtle, clean_rev1, clean_rev3) are reruns that answered many "
          "calls from the cache; their USD counts those calls at their first price. What each arm itself paid per file:", ""]
    L += ["| Benchmark arm | Regime | Model | Files | USD paid in the arm (mean) | USD full (mean) |", "|---|---|---|---|---|---|"]
    for n, t in res["per_design"].items():
        if n.startswith("lint/"):
            L.append(f"| {t['arm']} | {t['regime']} | {t['model']} | {t['files']} | {f6(t['paid_in_this_arm_usd_per_file']['mean'])} | {f6(t['usd_per_file']['mean'])} |")
    # 2. stages
    L += ["", "## 2. The core's cost by stage", "",
          "Calls classified from the cached answer of each call: routing (an answer with `other_topic`), fact readings "
          "(`conditions` answers; a reading opens with an answer covering more than half the facts, a smaller one is its "
          "requote), document judgments (the document finder's tool calls; the second judgment's `documents` answer), "
          "quote check (`items`), other (brief, process builder, result checker; full product only).", "",
          "| Run | Files | USD/file | Routing | Reading 1 | Readings 2-3 | Doc. finder | Doc. 2nd | Quote check | Other | Calls/file |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, s in res["core_stage_split"].items():
        bs = s["by_stage"]

        def sh(k):
            v = bs.get(k)
            return "–" if not v else f"{100 * v['share_of_cost']:.0f} % ({v['calls_per_file']:.1f})"
        other = sum((bs.get(k) or {}).get("share_of_cost", 0) or 0 for k in ("other (brief, process builder, result checker)", "not attributed"))
        oc = sum((bs.get(k) or {}).get("calls_per_file", 0) for k in ("other (brief, process builder, result checker)", "not attributed"))
        calls = sum(v["calls_per_file"] for v in bs.values())
        L.append(f"| {n} | {s['files']} | {f6(s['usd_per_file'])} | {sh('routing')} | {sh('fact reading 1')} | {sh('fact readings 2-3')} | "
                 f"{sh('document judgment: finder')} | {sh('document judgment: second')} | {sh('quote check')} | "
                 f"{'–' if not other else f'{100 * other:.0f} % ({oc:.1f})'} | {calls:.1f} |")
    L += ["", "Cells: share of the run's cost (calls per file).", "", "### Regressions of USD per file (benchmark, clean arm)", ""]
    L += ["| Data | Files | Predictor | Coefficient (USD per unit) | SE | Intercept | R² | Range of predictor |", "|---|---|---|---|---|---|---|---|"]
    for n, r in res["regressions"].items():
        for p_ in ("words", "facts_read", "attachments"):
            f = r[p_]
            L.append(f"| {r['label']} | {r['files']} | {p_} | {f['coef'][p_]:.3e} | {f['se'][p_]:.1e} | {f6(f['coef']['intercept'])} | "
                     f"{f['r2']:.2f} | {r['range'][p_]} |")
        j = r["joint"]
        L.append(f"| {r['label']} | {r['files']} | joint: words / attachments / facts | {j['coef']['words']:.2e} / {j['coef']['attachments']:.2e} / "
                 f"{j['coef']['facts_read']:.2e} | {j['se']['words']:.0e} / {j['se']['attachments']:.0e} / {j['se']['facts_read']:.0e} | "
                 f"{f6(j['coef']['intercept'])} | {j['r2']:.2f} | – |")
    L += ["", VERDICT, ""]
    # 3. single prompts
    L += ["## 3. Single prompts: fixed rule text against the file", "",
          "Per call, input tokens = fixed text of the regime + tokens per word × words of the file (least squares over "
          "case-runs, one intercept per regime). The rule share of the fixed text is taken from the rendered prompt that "
          "may hold (characters of policy, rule packs and source passages over all fixed characters: "
          + ", ".join(f"{g} {100 * v['rule_share']:.0f} %" for g, v in res["rule_share_of_fixed_prompt"].items()) + ").", "",
          "| Design / model | Fixed tokens tenancy | Fixed tokens theft | Tokens per word of file | File tokens at 250 / 2,500 words | Output per call | Cached share | Calls/file | R² |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["single_prompts"].items():
        c = v["input_fit"]["coef"]
        L.append(f"| {v['label']} | {fnum(c.get('fixed_tenancy'))} | {fnum(c.get('fixed_theft'))} | {c['tokens_per_word']:.2f} | "
                 f"{fnum(250 * c['tokens_per_word'])} / {fnum(2500 * c['tokens_per_word'])} | "
                 f"{fnum(statistics.mean(x['output_per_call_mean'] for x in v['by_regime'].values()))} | "
                 f"{statistics.mean(x['cached_share_mean'] for x in v['by_regime'].values()):.2f} | "
                 f"{statistics.mean(x['calls_per_file_mean'] for x in v['by_regime'].values()):.1f} | {v['input_fit']['r2']:.3f} |")
    L += ["", SINGLE_NOTE, ""]
    # 4. adaptive
    L += ["## 4. Adaptive re-reading: what the first reading alone would have given", "",
          "Per deciding fact read (the routing fact excluded): is the first reading a quoted value (true/false, or an enum "
          "value answered true, whose quote occurs in the file text after case and whitespace normalization)? Admitted = "
          "the product's stored fact after three readings (status established and not rejected by the source check). Readings 2 and 3 are "
          "the later reading groups of the same run. Without the evaluator's gold, 'wrong' can only mean 'against what "
          "three readings gave'.", "",
          "| Run | Facts read | First reading quoted value | = admitted value | Nothing admitted after three | 2 and 3 agree against it | Needs re-reading (p) | Files with any re-read | USD three → adaptive |",
          "|---|---|---|---|---|---|---|---|---|"]
    for n, a in res["adaptive_readings"].items():
        if n.startswith("BENCHMARK/"):
            continue
        c = a["counts"]
        fr = c.get("facts read", 0)
        s = c.get("first reading a quoted value", 0)
        L.append(f"| {n} | {fr} | {100 * s / fr:.1f} % | {100 * c.get('  ... equals the admitted value', 0) / fr:.1f} % | "
                 f"{100 * c.get('  ... nothing admitted after three readings', 0) / max(s, 1):.1f} % of quoted | "
                 f"{100 * c.get('  ... readings 2 and 3 agree with each other against it', 0) / max(s, 1):.1f} % of quoted | "
                 f"{100 * a['share_needing_rereading_under_adaptive (p)']:.1f} % | {100 * a['share_of_files_with_any_reread']:.0f} % | "
                 f"{f6(a['usd_per_file_three'])} → {f6(a['usd_per_file_adaptive_counterfactual'])} ({100 * a['saving_share']:.0f} % less) |")
    for m in MODELS:
        a = res["adaptive_readings"][f"BENCHMARK/{m}"]
        L.append(f"| benchmark pooled, {m} | {a['counts'].get('facts read')} | – | {100 * a['share_first_reading_alone_equals_admitted (of all facts read)']:.1f} % | – | – | "
                 f"{100 * a['share_needing_rereading_under_adaptive (p)']:.1f} % | – | – |")
    L += ["", ADAPTIVE_NOTE, ""]
    # 5. grid
    g = res["grid"]
    L += ["## 5. Grid of estimate() (USD per file)", "",
          f"Facts read fixed at the benchmark's median ({g['facts_read_assumed']}). One regime's rule text = "
          f"{g['rule_text_tokens_one_regime']:,.0f} tokens (the prompt that may hold, mean of tenancy and theft); three and "
          "four regimes = 3× and 4×. * = extrapolated beyond the stored range (words, attachments, rule text, or a model the "
          "design never ran on). Self-consistency is cost-matched to the core by construction; the cell shows its USD and samples.", ""]
    for m in MODELS:
        L += [f"### {MODEL_LABEL[m]}", "", "| Design | Words | Att. | 1 regime | 3 regimes | 4 regimes |", "|---|---|---|---|---|---|"]
        for d, label in GRID_DESIGNS:
            for w in GRID_WORDS:
                for a in GRID_ATT:
                    cells = []
                    for nr in GRID_REGIMES:
                        r = next(x for x in g["rows"] if x["design"] == d and x["model"] == m and x["words"] == w and x["attachments"] == a and x["regimes"] == nr)
                        extra = ""
                        if d == "self_consistency_matched":
                            mm = re.match(r"(\d+) samples", r["flags"][0])
                            extra = f" (m={mm.group(1)})" if mm else ""
                        cells.append(f"{f6(r['usd'])}{'*' if r['extrapolated'] else ''}{extra}")
                    L.append(f"| {label} | {w:,} | {a} | " + " | ".join(cells) + " |")
        L.append("")
    # 6. timing
    L += ["## 6. Measured time per file", "",
          "Wall time of the whole run from the run record (product designs; calls run one after another within a file, "
          "cache hits included) and the sum of the paid calls' latency from the ledger (where the ledger records `latency_s`). "
          "Study 3's ledger rows for Self-consistency, Model executes rules and ReAct carry no latency.", "",
          "| Design | Model | Data | Regime | Wall s (mean / median / p90) | Latency of paid calls s (mean / median / p90) |", "|---|---|---|---|---|---|"]
    for n, t in res["timing"].items():
        ws, ls_ = t["wall_seconds_per_file"], t["latency_seconds_per_file"]
        if not ws and not ls_:
            continue
        def trio(d, nd):
            return "–" if not d else f"{d['mean']:.{nd}f} / {d['median']:.{nd}f} / {d['p90']:.{nd}f}"
        L.append(f"| {t['design']} | {t['model']} | {t['data']} | {t['regime']} | {trio(ws, 0)} | {trio(ls_, 1)} |")
    L += ["", "## Limits", "", LIMITS, ""]
    return "\n".join(L)


VERDICT = ""      # filled in after the numbers are known (see the end of main)
ADAPTIVE_NOTE = ""
SINGLE_NOTE = ""
LIMITS = ""


def texts(res):
    """Prose that cites the computed numbers."""
    reg = res["regressions"]
    rl, rt = reg[f"lint/clean/ALL/{LUNA}"], reg[f"lint/clean/ALL/{TERRA}"]
    P = res["estimator_params"]
    rng = P["core_ranges_benchmark"]
    global PARAMS, PRICE
    PARAMS, PRICE = P, P["prices"]
    nf = rng["facts_read_median"]
    base = core_cost(LUNA, 2500, 6, nf, None, "three")[0]
    sens = core_cost(LUNA, 2500, 6, nf, None, "three", output_scales_with_words=True)[0]
    base_t = core_cost(TERRA, 2500, 6, nf, None, "three")[0]
    sens_t = core_cost(TERRA, 2500, 6, nf, None, "three", output_scales_with_words=True)[0]
    verdict = (
        f"**Verdict on extrapolation.** The benchmark files are short and narrow: {rng['words'][0]}-{rng['words'][1]} words "
        f"(file plus attachments), {rng['attachments'][0]}-{rng['attachments'][1]} attachments, {rng['facts_read'][0]}-"
        f"{rng['facts_read'][1]} deciding facts read; Study 3's claims are 77-367 words with 0-2 attachments. Within that "
        f"range the per-file fits are usable but loose: on the cost-efficient model words alone explain R² {rl['words']['r2']:.2f}, "
        f"attachments {rl['attachments']['r2']:.2f}, facts read {rl['facts_read']['r2']:.2f}, all three {rl['joint']['r2']:.2f} "
        f"(residual SD USD {rl['joint']['residual_sd']:.4f} on a mean of USD {res['core_stage_split'][f'lint/clean/ALL/{LUNA}']['usd_per_file']:.4f}); "
        f"words and attachments are correlated (r {rl['predictor_correlation']['words~attachments']:.2f}), so their separate "
        f"coefficients are not well identified. The frontier model's fit (R² {rt['joint']['r2']:.2f}) rests on {rt['files']} tenancy files. "
        "The single-predictor lines have negative intercepts and cannot be read outside the range in either direction. "
        "Document judgments are the largest stage and grow with attachments (about three finder calls per attachment) and, per "
        "call, with the file's length, so the shape of cost on long files is set by how many tool turns the document finder "
        "takes on a long document, which these files never show. The estimator therefore uses a structural form (calls × "
        "(base + tokens per word × words), calls and output linear in attachments and facts) instead of the per-file lines, "
        "but every cell above 575 words or 4 attachments is an extrapolation by a factor of up to 4.3 in words and 1.5 in "
        "attachments. Sensitivity for 2,500 words and 6 attachments: if output also grows with words, the core's cost on the "
        f"cost-efficient model goes from USD {base:.4f} to {sens:.4f} (frontier {base_t:.4f} to {sens_t:.4f}). Treat the 800- and "
        "2,500-word cells as order of magnitude and cost a study only after a priced pilot on 10-20 long files.")
    a_l, a_t = res["adaptive_readings"][f"BENCHMARK/{LUNA}"]["counts"], res["adaptive_readings"][f"BENCHMARK/{TERRA}"]["counts"]

    def risk(c):
        sq = c.get("first reading a quoted value", 0)
        return (c.get("  ... nothing admitted after three readings", 0) + c.get("  ... readings 2 and 3 agree with each other against it", 0)
                + c.get("  ... admitted value differs", 0)) / sq if sq else 0
    ad = res["adaptive_readings"]
    sav = [v["saving_share"] for k, v in ad.items() if k.startswith("lint/") and v.get("saving_share") is not None]
    sav3 = [v["saving_share"] for k, v in ad.items() if k.startswith("study3/") and v.get("saving_share") is not None]
    anyre = [v["share_of_files_with_any_reread"] for k, v in ad.items() if k.startswith("lint/")]
    note = (
        f"**What adaptive re-reading saves and risks.** On the benchmark the first reading alone is a quoted value for "
        f"{100 * a_l['first reading a quoted value'] / a_l['facts read']:.0f} % of deciding facts on the cost-efficient model and "
        f"{100 * a_t['first reading a quoted value'] / a_t['facts read']:.0f} % on the frontier model, so p = "
        f"{100 * P['adaptive_p_needing_rereading'][LUNA]:.0f} % and {100 * P['adaptive_p_needing_rereading'][TERRA]:.0f} % of facts would "
        f"still be read twice more. Because {100 * min(anyre):.0f}-{100 * max(anyre):.0f} % of files have at least one such fact and every "
        "re-reading call carries the whole file, the saving is small: "
        f"{100 * min(sav):.0f}-{100 * max(sav):.0f} % of the core's cost per file on the benchmark (counterfactual on the stored calls: "
        "re-reading calls kept in full input, their output cut to the share of facts re-read), "
        f"{100 * min(sav3):.0f}-{100 * max(sav3):.0f} % on Study 3 (largest on theft, where readings of about 90 rule conditions "
        "are most of the cost). The risk: of the quoted first readings, "
        f"{100 * risk(a_l):.1f} % (cost-efficient) and {100 * risk(a_t):.1f} % (frontier) end differently after three readings "
        "(nothing admitted, or readings 2 and 3 agreeing against the first); adaptive reading would admit those first values. "
        "Whether they are right cannot be said here: that needs the evaluator's gold, which this model does not read.")
    sp = res["single_prompts"]
    hl = sp[f"hold_prompt/{LUNA}"]
    tpw = hl["input_fit"]["coef"]["tokens_per_word"]
    fx_t, fx_h = hl["input_fit"]["coef"]["fixed_tenancy"], hl["input_fit"]["coef"]["fixed_theft"]
    single = (
        f"The fixed text dominates. For the prompt that may hold, the fixed part is {fx_t:,.0f} tokens on tenancy and {fx_h:,.0f} on "
        f"theft; the file adds {tpw:.2f} tokens per word, so a 250-word file adds {250 * tpw:,.0f} tokens "
        f"({100 * 250 * tpw / (fx_t + 250 * tpw):.0f} % of a tenancy prompt) and a 2,500-word file {2500 * tpw:,.0f} "
        f"({100 * 2500 * tpw / (fx_t + 2500 * tpw):.0f} %). One regime's rule text is taken as {P['rule_text_tokens_one_regime']:,.0f} "
        "tokens; three and four regimes multiply it. Token counts are linear in text, so scaling by words is safe in form even "
        "though the fitted files are 77-367 words; what is not known is whether output and accuracy hold on a 2,500-word file "
        "or a 50,000-token prompt. With prefix caching as measured (95-100 % of single-prompt input billed as cached), the rule "
        "text costs about a tenth of its uncached price; without caching a single prompt costs several times more (input "
        f"{PRICE[LUNA]['uncached_input'] / PRICE[LUNA]['cached_input']:.1f}x / {PRICE[TERRA]['uncached_input'] / PRICE[TERRA]['cached_input']:.0f}x "
        "the cached price on the cost-efficient / frontier model).")
    limits = "\n".join([
        "- Prices are those the ledgers billed (uncached, cached input and output per million tokens); the cached share of input "
        "is what these runs got from prefix caching and will differ with batch order and deployment.",
        "- The product and benchmark ledgers count about 25 more input tokens per call than were billed; their `usd` is used as recorded.",
        "- The frontier model ran the benchmark core on 38 completed tenancy files only (one failed); its per-stage token ratios "
        "to the cost-efficient model come from those files and are applied to all regimes. Self-consistency and ReAct never "
        "ran on the frontier model: their frontier cells are the cost-efficient model's tokens at frontier prices (marked *).",
        "- Three benchmark theft files (59 runs) have no text under study4/dev/theft/final (56 folders); they are in the cost "
        "tables but not in the regressions or the estimator fit.",
        "- Study 3's self-consistency ledger rows are not keyed by run; each case's 15 samples are spread evenly over its three "
        "case-runs (the mean reproduces the stored table; the per-case-run spread is understated).",
        "- Study 3's core on theft reads about 90 rule conditions per file and calls no document finder (no attachments); the "
        "estimator is fitted to the benchmark's workflows (0-10 deciding facts) and does not cover theft-style guard catalogues.",
        "- Only routing sees the whole catalogue in the product; a larger catalogue is modelled as a proportionally larger routing "
        "prompt. Single prompts are assumed to carry the whole catalogue. Larger workflows (more facts or documents per "
        "workflow) enter only through facts read and attachments.",
        "- Wall time is the run record's elapsed time of a file (calls in sequence, cache hits included, other files running in "
        "parallel); latency is the sum of the paid calls' `latency_s`. Neither is a throughput figure.",
        "- No evaluator gold, expected answers or reference files were read; 'wrong' in the adaptive analysis means 'different "
        "from what three readings gave'."])
    return verdict, note, single, limits


def strip_private(x):
    if isinstance(x, dict):
        return {k: strip_private(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, list):
        return [strip_private(v) for v in x]
    return x


def main():
    res = build()
    OUT_JSON.write_text(json.dumps(strip_private(res), indent=1, ensure_ascii=False, default=float) + "\n")
    global VERDICT, ADAPTIVE_NOTE, SINGLE_NOTE, LIMITS
    VERDICT, ADAPTIVE_NOTE, SINGLE_NOTE, LIMITS = texts(res)
    OUT_MD.write_text(markdown(strip_private(res)) + "\n")
    print("written", OUT_JSON, "and", OUT_MD)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()
