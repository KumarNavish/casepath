"""Evaluate the pre-registered hypotheses D1-D4 of the decisive run, exactly as written.

The primary endpoint is state accuracy, chosen and fixed before this split's episodes existed, after the
confirmatory run's composite-utility endpoint returned a negative. Nothing here selects a metric, a
comparator or a threshold after seeing data; every rule comes from PRE_REGISTRATION.md.
"""
from __future__ import annotations

import argparse, json, random
from pathlib import Path
from statistics import fmean

from casepath_api.arena_v1.analyze import load, family_means, paired
from casepath_api.arena_v1.decide_confirm import holm

ISOLATING = ("ctes-abl-levels", "ctes-abl-commitments", "ctes-abl-satisfaction")


def _boot_p(a: dict, b: dict, seed: int = 20260914, n: int = 5000) -> float:
    fams = sorted(set(a) & set(b))
    d = [a[f] - b[f] for f in fams]
    rng = random.Random(seed)
    boots = [fmean([d[rng.randrange(len(d))] for _ in d]) for _ in range(n)]
    below = sum(x <= 0 for x in boots) / n
    return round(min(1.0, 2 * min(below, 1 - below)), 4)


def _pair(pe, fam, arm_a, arm_b, key):
    a = family_means(pe[arm_a], fam, key)
    b = family_means(pe[arm_b], fam, key)
    r = paired(a, b)
    return {"metric": key, "comparator": arm_b, "families": r["families"],
            "mean_diff": round(r["mean_diff"], 4), "ci95": [round(x, 4) for x in r["ci95"]],
            "wins": r["wins"], "losses": r["losses"], "ties": r["ties"], "p_boot": _boot_p(a, b),
            "ci_excludes_zero": bool(r["ci95"][0] > 0 or r["ci95"][1] < 0)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    L = load(Path(a.run)); pe, fam = L["per_episode"], L["family"]

    report = {"contract": "casepath.arena-v1-decisive-decision/1.0.0",
              "run": a.run, "episodes": len(fam), "families": len(set(fam.values())),
              "arms": {}, "hypotheses": {}}
    for arm, per in sorted(pe.items()):
        fm = family_means(per, fam)
        report["arms"][arm] = {
            "family_weighted_state_accuracy": round(fmean(family_means(per, fam, "state_acc").values()), 4),
            "family_weighted_readiness_accuracy": round(fmean(family_means(per, fam, "readiness_acc").values()), 4),
            "family_weighted_U": round(fmean(fm.values()), 4),
            "premature_readiness_episodes": int(sum(m["P"] for m in per.values())),
            "hearsay_receipts": int(sum(m["hearsay"] for m in per.values())),
            "acquired_critical_evidence": round(sum(m["A"] for m in per.values()), 3),
            "requests": int(sum(m["requests"] for m in per.values())),
            "failures": int(sum(m["failures"] for m in per.values()))}

    d1 = _pair(pe, fam, "ctes", "full", "state_acc")
    d2 = _pair(pe, fam, "ctes", "full", "readiness_acc")
    adj = holm({"D1": d1["p_boot"], "D2": d2["p_boot"]})
    report["hypotheses"]["D1"] = {
        "statement": "state accuracy of ctes exceeds that of full (PRIMARY, pre-registered)",
        **d1, "p_holm": adj["D1"]["p_holm"],
        "established": bool(d1["ci_excludes_zero"] and d1["mean_diff"] > 0)}
    report["hypotheses"]["D2"] = {
        "statement": "readiness accuracy of ctes against full, two-sided; this metric rewards a correct "
                     "readiness call in both directions",
        **d2, "p_holm": adj["D2"]["p_holm"]}
    report["hypotheses"]["D3"] = {
        "statement": "which single rule carries the channel cap's effect on premature readiness",
        "prediction_made_in_advance": "ctes-abl-satisfaction costs the most",
        "per_rule": {arm: _pair(pe, fam, arm, "ctes", "P") for arm in ISOLATING if arm in pe},
        "compound": _pair(pe, fam, "ctes-ablation", "ctes", "P") if "ctes-ablation" in pe else None,
        "note": "oriented as comparator minus ctes, so a POSITIVE mean_diff means the ablated arm declares "
                "readiness prematurely more often than the method"}
    report["hypotheses"]["D4"] = {
        "statement": "composite utility, reported for continuity with the confirmatory run; not primary",
        "vs_full": _pair(pe, fam, "ctes", "full", "U"),
        "vs_ablation": _pair(pe, fam, "ctes", "ctes-ablation", "U") if "ctes-ablation" in pe else None}

    Path(a.out).write_text(json.dumps(report, indent=1))
    print(json.dumps({
        "episodes": report["episodes"], "families": report["families"],
        "D1": {k: report["hypotheses"]["D1"][k] for k in ("mean_diff", "ci95", "wins", "losses", "p_holm", "established")},
        "D2": {k: report["hypotheses"]["D2"][k] for k in ("mean_diff", "ci95", "wins", "losses", "p_holm")},
        "D3": {arm: {k: v[k] for k in ("mean_diff", "ci95", "wins", "losses")}
               for arm, v in report["hypotheses"]["D3"]["per_rule"].items()},
        "D4": {k: report["hypotheses"]["D4"]["vs_full"][k] for k in ("mean_diff", "ci95")}}, indent=1))


if __name__ == "__main__":
    main()
