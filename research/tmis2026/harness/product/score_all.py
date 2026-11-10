"""Score the product (commit 7ff7af64) and every baseline on the fresh development data. No model calls.

    python3 score_all.py [--label p7ff]
Tenancy: Study 2 measures (analysis/study2.ten_row) per claim-run, averaged per claim-run; the product in both scoring
views (conservative = workflow needs + process-builder needs marked required; workflow needs only).
Theft (stories 4-5): pairs scored as harness/v2/cp4_score.py (best_realization over the off -> variant delta).
Writes results/score_all_<label>.json and prints both tables.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
for p in (HERE, TMIS / "harness", TMIS / "harness" / "v2", TMIS / "fresh", TMIS / "analysis"):
    sys.path.insert(0, str(p))
RUNS = TMIS / "runs"
K = 3
TASK_START_ROW = 8218  # ledger rows before this index were paid before this task (earlier product commits)


def load(p):
    return json.loads(Path(p).read_text()) if Path(p).exists() else {}


def ledger_rows(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] if Path(path).exists() else []


# ------------------------------------------------------------------ tenancy
def tenancy(label):
    import study2
    import tenancy_fresh as F
    ids = F.claim_ids("test")
    prod = load(RUNS / "product" / f"plans_tenancy_gpt-6-luna_fresh_{label}.json")
    base = {}
    for arm in ("COL", "REACT"):
        base.update(load(RUNS / "product" / f"baselines_tenancy_gpt-6-luna_fresh_{arm}.json"))
    base.update(load(RUNS / "product" / "baselines_tenancy_gpt-6-luna_fresh.json"))
    v2 = {m: load(RUNS / "v2" / f"plans_tenancy_{m}_fresh_heldout.json") for m in ("gpt-6-luna", "gpt-6.1-terra")}
    get = lambda raw, key, field="plan": (raw.get(key) or {}).get(field)
    arms = {
        "PRODUCT conservative (luna)": lambda c, r: get(prod, f"PRODUCT|{c}|{r}"),
        "PRODUCT workflow needs only (luna)": lambda c, r: get(prod, f"PRODUCT|{c}|{r}", "plan_workflow_only"),
        "Rules in context B1v2p (luna)": lambda c, r: get(v2["gpt-6-luna"], f"B1v2p|{c}|{r}"),
        "Rules in context B1v2p (terra)": lambda c, r: get(v2["gpt-6.1-terra"], f"B1v2p|{c}|{r}"),
        "CPv2p (luna)": lambda c, r: get(v2["gpt-6-luna"], f"CPv2p|{c}|{r}"),
        "CPv2p (terra)": lambda c, r: get(v2["gpt-6.1-terra"], f"CPv2p|{c}|{r}"),
        "(a) self-consistency over B1v2p (luna)": lambda c, r: get(base, f"SC|{c}|{r}"),
        "(b) model executes rules, CoL/B2 (luna)": lambda c, r: get(base, f"COL|{c}|{r}"),
        "(c) ReAct agent (luna)": lambda c, r: get(base, f"REACT|{c}|{r}"),
        "(d) two-valued, unknown=false (product facts)": lambda c, r: get(base, f"TWO_F|{c}|{r}"),
        "(d) two-valued, unknown=true (product facts)": lambda c, r: get(base, f"TWO_T|{c}|{r}"),
    }
    present = {"PRODUCT conservative (luna)": prod, "PRODUCT workflow needs only (luna)": prod}
    table = {}
    for name, fn in arms.items():
        rows, missing = [], 0
        for c in ids:
            for r in range(K):
                p = fn(c, r)
                key_exists = p is not None
                missing += not key_exists
                rows.append(study2.ten_row(F.reference(c), p))
        n = len(rows)
        S = lambda k: sum(x[k] for x in rows)
        table[name] = {"claim_runs": n, "empty_or_failed": missing, "requested_share": S("requested") / S("req_now"),
                       "held": S("correct_hold") / n, "held_required_now": S("held_req") / n, "handed": S("handed") / n,
                       "missed": S("missed") / n, "unnecessary": S("unnecessary") / n, "premature": S("premature") / n,
                       "silent_skip": S("silent_skip") / n, "strict_unsafe": S("strict_unsafe") / n,
                       "spurious_hold": S("spurious_hold") / n, "handoff_runs": S("deferred")}
    table["_costs"] = tenancy_costs(ids, prod, base)
    return table


def tenancy_costs(ids, prod, base):
    idset = set(ids)
    out = {}
    rows = ledger_rows(RUNS / "product" / "ledger_dev_gpt-6-luna.jsonl")[TASK_START_ROW:]
    by = defaultdict(float)
    for r in rows:
        if r["case"] in idset:
            by[r.get("arm", "PRODUCT")] += r["usd"] or 0
    n = len(ids) * K
    pc = [v.get("calls", 0) for k, v in prod.items() if k.split("|")[1] in idset]
    out["PRODUCT"] = {"calls_per_case": sum(pc) / max(1, len(pc)), "usd_per_case": by["PRODUCT"] / max(1, len(pc)),
                      "claim_runs": len(pc), "note": "calls paid in this task (commit 7ff7af64); interrupted runs re-served from cache"}
    for arm in ("COL", "REACT"):
        calls = [v.get("calls", 0) for k, v in base.items() if k.startswith(arm + "|")]
        out[arm] = {"calls_per_case": sum(calls) / max(1, len(calls)), "usd_per_case": by[arm] / n}
    for m in ("gpt-6-luna", "gpt-6.1-terra"):
        v2 = ledger_rows(RUNS / "v2" / f"ledger_{m}.jsonl")
        for meth in ("B1v2p", "CPv2p-interpret"):
            x = [r for r in v2 if r["tag"].get("method") == meth and r["tag"].get("case") in idset]
            out[f"{meth} {m}"] = {"calls_per_case": len(x) / n, "usd_per_case": sum(float(r.get("cost") or 0) for r in x) / n}
    b1 = out["B1v2p gpt-6-luna"]
    out["SC"] = {"calls_per_case": 3 * b1["calls_per_case"], "usd_per_case": 3 * b1["usd_per_case"]}
    return out


# ------------------------------------------------------------------ theft
def theft(stories=(4, 5)):
    import common
    from theft_data import best_realization
    from theft_score import delta
    D = common.data("theft", "fresh")
    pairs = [p for p in D.pairs() if p["story"] in stories]
    prod = load(RUNS / "product" / "plans_theft_gpt-6-luna_fresh_reviewed.json")
    cp4 = {m: load(RUNS / "v2" / "cp4" / f"plans_theft_{m}_fresh_reviewed.json") for m in ("gpt-6-luna", "gpt-6.1-terra")}
    base = {m: load(RUNS / "v2" / f"plans_theft_{m}_fresh_heldout.json") for m in ("gpt-6-luna", "gpt-6.1-terra")}
    get = lambda raw, key, field="plan": (raw.get(key) or {}).get(field)
    arms = {
        "PRODUCT conservative (luna, k=1)": ([0], lambda t, r: get(prod, f"PRODUCT|{t}|{r}")),
        "PRODUCT workflow needs only (luna, k=1)": ([0], lambda t, r: get(prod, f"PRODUCT|{t}|{r}", "plan_workflow_only")),
        "Rules in context, original pack R (luna)": ([0, 1, 2], lambda t, r: get(base["gpt-6-luna"], f"R|{t}|{r}")),
        "Rules in context, original pack R (terra)": ([0, 1, 2], lambda t, r: get(base["gpt-6.1-terra"], f"R|{t}|{r}")),
        "Rules in context, reviewed rules (luna)": ([0, 1, 2], lambda t, r: get(cp4["gpt-6-luna"], f"Rpack|{t}|{r}")),
        "CP4, reviewed rules (luna)": ([0, 1, 2], lambda t, r: get(cp4["gpt-6-luna"], f"CP4|{t}|{r}")),
        "CP4, reviewed rules (terra)": ([0, 1, 2], lambda t, r: get(cp4["gpt-6.1-terra"], f"CP4|{t}|{r}")),
        "CP4, reviewed rules (luna, run 0 only)": ([0], lambda t, r: get(cp4["gpt-6-luna"], f"CP4|{t}|{r}")),
    }
    empty = {"requests": [], "holds": []}
    table = {}
    for name, (runs, fn) in arms.items():
        on, un = [], []
        for p in pairs:
            for r in runs:
                off, var = fn(p["off"], r), fn(p["variant"], r)
                if off is None and var is None:
                    continue
                off, var = off or empty, var or empty
                pred = delta(set(off["requests"]), set(var["requests"]))
                sel, _ = best_realization(pred, p["reference"])
                w, m = sorted(set(pred) - set(sel)), sorted(set(sel) - set(pred))
                on_docs = {d.lstrip("+") for o in p["reference"]["acceptable_signed_deltas"] for d in o}
                row = {"pair": p["pair_id"], "run": r, "wrong": w, "missed": m,
                       "missed_held": [x for x in m if x[1:] in set(var.get("holds", []))],
                       "stable": not pred, "premature": bool((set(var["requests"]) - set(off["requests"])) & on_docs)}
                (on if p["kind"] == "on" else un).append(row)
        w, m = sum(len(x["wrong"]) for x in on), sum(len(x["missed"]) for x in on)
        table[name] = {"pair_runs": len(on), "wrong": w, "missed": m, "wm_per_pair": (w + m) / max(1, len(on)),
                       "wrong_per_pair": w / max(1, len(on)), "missed_per_pair": m / max(1, len(on)),
                       "missed_because_held": sum(len(x["missed_held"]) for x in on),
                       "unchanged_when_open": sum(x["stable"] for x in un) / max(1, len(un)),
                       "premature_when_open": sum(x["premature"] for x in un) / max(1, len(un)), "rows": on}
    table["_costs"] = theft_costs(stories)
    return table


def theft_costs(stories):
    pre = tuple(f"s{s}-" for s in stories)
    out = {}
    rows = [r for r in ledger_rows(RUNS / "product" / "ledger_dev_gpt-6-luna.jsonl")[TASK_START_ROW:] if str(r["case"]).startswith(pre)]
    texts = {r["case"] for r in rows}
    out["PRODUCT"] = {"usd_per_text": sum(r["usd"] or 0 for r in rows) / max(1, len(texts)), "calls_per_text": len(rows) / max(1, len(texts))}
    for m in ("gpt-6-luna", "gpt-6.1-terra"):
        v2 = ledger_rows(RUNS / "v2" / f"ledger_{m}.jsonl")
        for meth, mult, name in (("R", 1, "R"), ("CPv3-read", 2, "CP4 (2 readings)")):
            x = [r for r in v2 if r["tag"].get("method") == meth and str(r["tag"].get("case")).startswith(pre)]
            if x:
                out[f"{name} {m}"] = {"usd_per_text": mult * sum(float(r.get("cost") or 0) for r in x) / len(x), "calls_per_text": mult}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="p7ff")
    ap.add_argument("--skip-theft", action="store_true")
    a = ap.parse_args()
    ten = tenancy(a.label)
    th = {} if a.skip_theft else theft()
    keys = ["requested_share", "held", "handed", "missed", "unnecessary", "premature", "silent_skip", "strict_unsafe",
            "spurious_hold", "empty_or_failed"]
    print("TENANCY".ljust(48) + " ".join(k[:9].rjust(9) for k in keys))
    for name, row in ten.items():
        if not name.startswith("_"):
            print(name[:48].ljust(48) + " ".join(f"{row[k]:9.3f}" for k in keys))
    print(json.dumps(ten["_costs"], indent=1))
    if th:
        tk = ["pair_runs", "wrong", "missed", "wm_per_pair", "missed_because_held", "unchanged_when_open", "premature_when_open"]
        print("THEFT".ljust(48) + " ".join(k[:9].rjust(9) for k in tk))
        for name, row in th.items():
            if not name.startswith("_"):
                print(name[:48].ljust(48) + " ".join(f"{row[k]:9.3f}" if isinstance(row[k], float) else f"{row[k]:9d}" for k in tk))
        print(json.dumps(th["_costs"], indent=1))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"score_all_{a.label}.json").write_text(json.dumps({"tenancy": ten, "theft": th}, indent=1, default=str))


if __name__ == "__main__":
    main()
