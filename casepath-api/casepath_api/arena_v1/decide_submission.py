"""Evaluate S1-S4 across actor model families, and the pre-chosen practical trade-off.

The composite utility is not used. Two splits showed it does not separate and it rewards an arm that never
decides. It is replaced by the analysis fixed in FINAL_PREREGISTRATION.md before any number existed:
burden-constrained correctness, plus the Pareto frontier over (state accuracy, premature readiness,
requests). Writer family is carried as a nuisance variable.
"""
from __future__ import annotations

import argparse, json, random
from pathlib import Path
from statistics import fmean

from casepath_api.arena_v1.analyze import load, family_means, paired
from casepath_api.arena_v1.decide_confirm import holm

METHOD, OBVIOUS, BASE = "ctes", "full-artifact-gate", "full"
FRONTIER = ("state_acc", "P", "requests")


def _bp(a, b, seed=20260914, n=5000):
    fams = sorted(set(a) & set(b)); d = [a[f] - b[f] for f in fams]
    if not d:
        return 1.0
    rng = random.Random(seed)
    boots = [fmean([d[rng.randrange(len(d))] for _ in d]) for _ in range(n)]
    below = sum(x <= 0 for x in boots) / n
    return round(min(1.0, 2 * min(below, 1 - below)), 4)


def _pair(pe, fam, a_arm, b_arm, key, keep=None):
    sub = (lambda per: {c: m for c, m in per.items() if keep is None or c in keep})
    a = family_means(sub(pe[a_arm]), keep or fam, key)
    b = family_means(sub(pe[b_arm]), keep or fam, key)
    r = paired(a, b)
    return {"mean_diff": round(r["mean_diff"], 4), "ci95": [round(x, 4) for x in r["ci95"]],
            "wins": r["wins"], "losses": r["losses"], "families": r["families"], "p_boot": _bp(a, b),
            "ci_excludes_zero": bool(r["ci95"][0] > 0 or r["ci95"][1] < 0)}


def _totals(per):
    return {"state_acc": round(fmean(m["state_acc"] for m in per.values()), 4),
            "readiness_acc": round(fmean(m["readiness_acc"] for m in per.values()), 4),
            "premature": int(sum(m["P"] for m in per.values())),
            "requests": int(sum(m["requests"] for m in per.values())),
            "burden": round(sum(m["B"] for m in per.values()), 2),
            "acquired": round(sum(m["A"] for m in per.values()), 2),
            "hearsay": int(sum(m["hearsay"] for m in per.values())),
            "failures": int(sum(m["failures"] for m in per.values()))}


def pareto(points: dict[str, dict]) -> dict[str, bool]:
    """Non-dominated on (state accuracy up, premature down, requests down)."""
    out = {}
    for a, pa in points.items():
        dominated = False
        for b, pb in points.items():
            if a == b:
                continue
            ge = (pb["state_acc"] >= pa["state_acc"] and pb["premature"] <= pa["premature"]
                  and pb["requests"] <= pa["requests"])
            gt = (pb["state_acc"] > pa["state_acc"] or pb["premature"] < pa["premature"]
                  or pb["requests"] < pa["requests"])
            if ge and gt:
                dominated = True
                break
        out[a] = not dominated
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True, help="tag=path")
    ap.add_argument("--latents", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    writers = {}
    for lat in json.loads(Path(a.latents).read_text()):
        writers[f"{lat['domain']}.{lat['family']}.e{lat['episode']}"] = lat.get("writer_model")

    report = {"contract": "casepath.arena-v1-submission-decision/1.0.0", "actor_models": {}, "hypotheses": {}}
    s1 = {}
    for spec in a.run:
        tag, path = spec.split("=", 1)
        L = load(Path(path)); pe, fam = L["per_episode"], L["family"]
        model = L["result"]["model_label"]
        arms = {arm: _totals(per) for arm, per in sorted(pe.items())}
        entry = {"model": model, "episodes": len(fam), "families": len(set(fam.values())), "arms": arms,
                 "vs_obvious_fix": _pair(pe, fam, METHOD, OBVIOUS, "state_acc"),
                 "vs_baseline": _pair(pe, fam, METHOD, BASE, "state_acc"),
                 "obvious_fix_vs_baseline_hearsay": {"full": arms[BASE]["hearsay"], "gated": arms[OBVIOUS]["hearsay"]},
                 "mechanism_premature": {METHOD: arms[METHOD]["premature"],
                                         "ctes-abl-satisfaction": arms.get("ctes-abl-satisfaction", {}).get("premature")},
                 "pareto_non_dominated": pareto({k: v for k, v in arms.items()}),
                 "by_writer": {}}
        for w in sorted({x for x in writers.values() if x}):
            keep = {c: f for c, f in fam.items() if writers.get(c) == w}
            if len(set(keep.values())) >= 5:
                entry["by_writer"][w] = _pair(pe, fam, METHOD, OBVIOUS, "state_acc", keep=keep)
        report["actor_models"][tag] = entry
        s1[tag] = entry["vs_obvious_fix"]

    positives = [t for t, v in s1.items() if v["ci_excludes_zero"] and v["mean_diff"] > 0]
    signs = {t: (1 if v["mean_diff"] > 0 else -1 if v["mean_diff"] < 0 else 0) for t, v in s1.items()}
    pooled = round(fmean(v["mean_diff"] for v in s1.values()), 4)
    report["hypotheses"] = {
        "S1": {"statement": "state accuracy of the method over the obvious fix is positive per actor model",
               "per_model": s1, "models_with_interval_excluding_zero": positives,
               "pooled_mean_diff": pooled,
               "confirmed": bool(len(positives) >= 2 and pooled > 0)},
        "S2": {"statement": "the sign is the same on every actor model", "signs": signs,
               "confirmed": bool(len(set(signs.values())) == 1)},
        "S3": {"statement": "the obvious fix removes hearsay receipts on every actor model",
               "per_model": {t: v["obvious_fix_vs_baseline_hearsay"] for t, v in report["actor_models"].items()},
               "confirmed": all(v["obvious_fix_vs_baseline_hearsay"]["gated"] < v["obvious_fix_vs_baseline_hearsay"]["full"]
                                for v in report["actor_models"].values())},
        "S4": {"statement": "disabling the satisfaction rule raises premature readiness on every actor model",
               "per_model": {t: v["mechanism_premature"] for t, v in report["actor_models"].items()},
               "confirmed": all((v["mechanism_premature"].get("ctes-abl-satisfaction") or 0) > v["mechanism_premature"][METHOD]
                                for v in report["actor_models"].values())}}
    Path(a.out).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "statement"} for k, v in report["hypotheses"].items()}, indent=1)[:2600])


if __name__ == "__main__":
    main()
