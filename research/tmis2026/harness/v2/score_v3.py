"""Development scoring of CPv3 against the recorded arms on the same cases (no model calls).

Usage: python3 score_v3.py <model> --theft-stories 0,1,2,4,5,6,7 [--tenancy]
Writes runs/v2/v3/scores_<model>.json.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict

import common

ap = argparse.ArgumentParser()
ap.add_argument("model")
ap.add_argument("--theft-stories", default="")
ap.add_argument("--tenancy", action="store_true")
args = ap.parse_args()
sys.argv = [sys.argv[0], args.model]
from theft_data import best_realization  # noqa: E402
from theft_score import delta  # noqa: E402

K = 3
OUT = common.OUT / "v3"


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def theft_sources(data):
    v3 = load(OUT / f"plans_theft_{args.model}_{data}_original.json")
    base = load(common.OUT / (f"plans_theft_{args.model}_original_dev.json" if data == "original"
                              else f"plans_theft_{args.model}_fresh_heldout.json"))
    return v3, base


def theft_errors(pair, off, var):
    pred = delta(set(off["requests"]), set(var["requests"]))
    sel, _ = best_realization(pred, pair["reference"])
    return sorted(set(pred) - set(sel)), sorted(set(sel) - set(pred))


def theft():
    stories = [int(s) for s in args.theft_stories.split(",") if s]
    res, corr = {}, defaultdict(Counter)
    getters = {"CPv3": lambda v3, b, k: (v3.get(k) or {}).get("plan"), "CPv3-draft": lambda v3, b, k: (v3.get(k) or {}).get("draft"),
               "R": lambda v3, b, k: (b.get(k.replace("CPv3", "R")) or {}).get("plan"),
               "Rv2p": lambda v3, b, k: (b.get(k.replace("CPv3", "Rv2p")) or {}).get("plan"),
               "CPv2p": lambda v3, b, k: (b.get(k.replace("CPv3", "CPv2p")) or {}).get("plan"),
               "CPv1": lambda v3, b, k: (b.get(k.replace("CPv3", "CPv1")) or {}).get("plan")}
    rows = defaultdict(list)
    for data in ("original", "fresh"):
        D = common.data("theft", data)
        v3, base = theft_sources(data)
        pairs = [p for p in D.pairs() if p["story"] in stories]
        for name, get in getters.items():
            for p in pairs:
                for r in range(K):
                    ko, kv = f"CPv3|{p['off']}|{r}", f"CPv3|{p['variant']}|{r}"
                    if ko not in v3 or kv not in v3:
                        continue  # CPv3 not run here: compare on the same cases only
                    off, var = get(v3, base, ko), get(v3, base, kv)
                    if off is None and var is None and name not in ("CPv3", "CPv3-draft"):
                        continue  # arm not recorded for these cases
                    empty = {"requests": [], "holds": []}
                    off, var = off or empty, var or empty
                    w, m = theft_errors(p, off, var)
                    on_docs = {d.lstrip("+") for o in p["reference"]["acceptable_signed_deltas"] for d in o}
                    rows[name].append({"kind": p["kind"], "story": p["story"], "run": r, "wrong": w, "missed": m,
                                       "stable": not delta(set(off["requests"]), set(var["requests"])),
                                       "premature": bool((set(var["requests"]) - set(off["requests"])) & on_docs)})
        # correction correctness: counterfactual removal of each applied correction
        for key, entry in v3.items():
            if not entry or not entry.get("applied"):
                continue
            _, t, r = key.split("|")
            r = int(r)
            for c in entry["applied"]:
                others = [x for x in entry["applied"] if x is not c]
                plan_wo = _apply_without(entry, others)
                d_err = 0
                for p in pairs:
                    if t not in (p["off"], p["variant"]) or p["kind"] != "on":
                        continue
                    o = v3.get(f"CPv3|{p['off']}|{r}") or {}
                    v = v3.get(f"CPv3|{p['variant']}|{r}") or {}
                    off_w, var_w = (plan_wo if p["off"] == t else o.get("plan")), (plan_wo if p["variant"] == t else v.get("plan"))
                    if not off_w or not var_w or not o.get("plan") or not v.get("plan"):
                        continue
                    a = sum(map(len, theft_errors(p, o["plan"], v["plan"])))
                    b = sum(map(len, theft_errors(p, off_w, var_w)))
                    d_err += a - b
                verdict = "right" if d_err < 0 else "wrong" if d_err > 0 else "neutral"
                corr[(c.get("rule") or "?", c["type"])][verdict] += 1
                corr[("ALL", c["type"])][verdict] += 1
        props = sum(len(e.get("proposed") or []) for e in v3.values() if e)
        apps = sum(len(e.get("applied") or []) for e in v3.values() if e)
        res.setdefault("_corrections", {})[data] = {"proposed": props, "applied": apps,
                                                    "ignored_reasons": Counter(i["ignored"] for e in v3.values() if e for i in (e.get("ignored") or []))}
    for name, rs in rows.items():
        on = [x for x in rs if x["kind"] == "on"]
        un = [x for x in rs if x["kind"] == "unresolved"]
        once = defaultdict(set)
        for x in on:
            for w in x["wrong"]:
                once[(x["story"], x["run"])].add(w)
        w, m = sum(len(x["wrong"]) for x in on), sum(len(x["missed"]) for x in on)
        res[name] = {"pair_runs": len(on), "wrong": w, "missed": m, "wm_per_pair": round((w + m) / max(1, len(on)), 3),
                     "wm_per_pair_counted_once": round((sum(len(v) for v in once.values()) + m) / max(1, len(on)), 3),
                     "unchanged_when_open": round(sum(x["stable"] for x in un) / max(1, len(un)), 3),
                     "premature_when_open": round(sum(x["premature"] for x in un) / max(1, len(un)), 3)}
    res["_correction_outcomes"] = {f"{k[0]}|{k[1]}": dict(v) for k, v in sorted(corr.items())}
    return res


def _apply_without(entry, applied):
    """Draft with only the given corrections applied (same semantics as v3.apply_corrections)."""
    req, held = set(entry["draft"]["requests"]), set(entry["draft"]["holds"])
    for c in applied:
        doc = c["document_name"]
        if c["type"] in {"drop", "replace_with_alternative"}:
            req.discard(doc)
        elif c["type"] == "add":
            req.add(doc); held.discard(doc)
        elif c["type"] == "hold":
            req.discard(doc); held.add(doc)
        else:
            held.discard(doc); req.add(doc)
    return {"requests": sorted(req), "holds": sorted(held)}


def tenancy_row(R, plan):
    if plan is None:
        return {"tp": 0, "fp": 0, "miss": len(R), "held": 0, "handed": 0, "nR": len(R)}
    P, H = set(plan.get("requests", [])), set(plan.get("holds", []))
    if plan.get("deferred"):
        return {"tp": len(P & R), "fp": len(P - R), "miss": 0, "held": 0, "handed": len(R - P), "nR": len(R)}
    return {"tp": len(P & R), "fp": len(P - R), "miss": len(R - P - H), "held": len((H - P) & R), "handed": 0, "nR": len(R)}


def tenancy():
    res, corr = {}, Counter()
    for data, split in (("original", "dev"), ("fresh", "heldout")):
        D = common.data("tenancy", data)
        v3 = load(OUT / f"plans_tenancy_{args.model}_{data}_v2p.json")
        base = load(common.OUT / f"plans_tenancy_{args.model}_{data}_{split}.json")
        if data == "original":
            from tenancy_score import unscored
        else:
            unscored = lambda c: set()  # noqa: E731
        sums = defaultdict(lambda: Counter())
        for key, entry in v3.items():
            _, c, r = key.split("|")
            R = set(D.reference(c)["request_set"]) - unscored(c)
            for name, plan in (("CPv3", (entry or {}).get("plan")), ("CPv3-draft", (entry or {}).get("draft")),
                               ("CPv2p", (base.get(f"CPv2p|{c}|{r}") or {}).get("plan")),
                               ("B1v2p", (base.get(f"B1v2p|{c}|{r}") or {}).get("plan")),
                               ("CPv1", (base.get(f"CPv1|{c}|{r}") or {}).get("plan_exact") or (base.get(f"CPv1|{c}|{r}") or {}).get("plan"))):
                sums[name].update({**tenancy_row(R, plan), "n": 1})
            for cc in (entry or {}).get("applied") or []:
                others = [x for x in entry["applied"] if x is not cc]
                a, b = tenancy_row(R, entry["plan"]), tenancy_row(R, _apply_without(entry, others) if entry.get("draft") else None)
                ua, ub = a["fp"] + a["miss"], b["fp"] + b["miss"]
                corr[(cc["type"], "right" if ua < ub else "wrong" if ua > ub else "neutral")] += 1
        res[data] = {name: {"claim_runs": s["n"], "requested_share": round(s["tp"] / max(1, s["nR"]), 3),
                            "held_per_claim": round(s["held"] / max(1, s["n"]), 3),
                            "strict_unsafe_per_claim": round((s["fp"] + s["miss"] + s["handed"]) / max(1, s["n"]), 3)}
                     for name, s in sums.items()}
        res[data]["_corrections"] = {"proposed": sum(len((e or {}).get("proposed") or []) for e in v3.values()),
                                     "applied": sum(len((e or {}).get("applied") or []) for e in v3.values())}
    res["_correction_outcomes"] = {f"{k[0]}|{k[1]}": v for k, v in sorted(corr.items())}
    return res


def costs():
    rows = [json.loads(l) for l in (common.OUT / f"ledger_{args.model}.jsonl").read_text().splitlines()]
    agg = defaultdict(lambda: [0, 0.0])
    for r in rows:
        k = r["tag"].get("method")
        if k in ("CPv3-check", "CPv3-read", "CP-interpret", "CPv2p-interpret", "R", "Rv2p", "B1v2p"):
            agg[(r["tag"].get("exp"), k)][0] += 1
            agg[(r["tag"].get("exp"), k)][1] += float(r.get("cost") or 0)
    return {f"{e}|{m}": round(c / n, 5) for (e, m), (n, c) in agg.items() if n}


if __name__ == "__main__":
    out = {"theft": theft() if args.theft_stories else None, "tenancy": tenancy() if args.tenancy else None,
           "usd_per_call": costs()}
    print(json.dumps(out, indent=1, default=dict))
    common.dump(OUT / f"scores_{args.model}.json", json.loads(json.dumps(out, default=dict)))
