"""Evaluate the pre-registered hypotheses H1-H4 of the confirmatory run, exactly as written.

Nothing here chooses a metric, a threshold or a comparison after seeing data: every quantity and every
decision rule comes from PRE_REGISTRATION.md, which was fixed before any confirmatory episode text
existed. Holm correction is applied across {H2, H3} as pre-registered.
"""
from __future__ import annotations

import argparse, json, random
from pathlib import Path
from statistics import fmean

from casepath_api.arena_v1.analyze import load, family_means, paired

HOLM_FAMILY = ("H2", "H3")


def _boot_p(a: dict, b: dict, seed: int = 20260914, n: int = 5000) -> float:
    """Two-sided bootstrap p: the fraction of resampled means on the wrong side of zero, doubled."""
    fams = sorted(set(a) & set(b))
    d = [a[f] - b[f] for f in fams]
    rng = random.Random(seed)
    boots = [fmean([d[rng.randrange(len(d))] for _ in d]) for _ in range(n)]
    below = sum(x <= 0 for x in boots) / n
    return min(1.0, 2 * min(below, 1 - below))


def _arm_metric(episodes: dict, key: str) -> float:
    return sum(m[key] for m in episodes.values())


def run(run_dir: Path, label: str) -> dict:
    L = load(run_dir)
    pe, fam = L["per_episode"], L["family"]
    fm = {arm: family_means(p, fam) for arm, p in pe.items()}
    out: dict = {"label": label, "run": str(run_dir), "episodes": len(fam), "families": len(set(fam.values())),
                 "arms": {}, "paired_vs_ctes": {}}
    for arm, p in sorted(pe.items()):
        out["arms"][arm] = {"family_weighted_U": round(fmean(fm[arm].values()), 4),
                            "hearsay_receipts": int(_arm_metric(p, "hearsay")),
                            "premature_readiness_episodes": int(_arm_metric(p, "P")),
                            "acquired_critical_evidence": round(_arm_metric(p, "A"), 3),
                            "requests": int(_arm_metric(p, "requests")),
                            "failures": int(_arm_metric(p, "failures"))}
    for arm in sorted(fm):
        if arm != "ctes" and "ctes" in fm:
            r = paired(fm["ctes"], fm[arm])
            r["p_boot"] = round(_boot_p(fm["ctes"], fm[arm]), 4)
            r["mean_diff"] = round(r["mean_diff"], 4)
            r["ci95"] = [round(x, 4) for x in r["ci95"]]
            out["paired_vs_ctes"][arm] = r
    return out


def holm(pvals: dict[str, float]) -> dict[str, dict]:
    order = sorted(pvals, key=lambda k: pvals[k])
    m = len(order)
    adjusted: dict[str, dict] = {}
    running = 0.0
    for i, k in enumerate(order):
        a = min(1.0, max(running, (m - i) * pvals[k]))
        running = a
        adjusted[k] = {"p_raw": pvals[k], "p_holm": round(a, 4), "reject_at_05": a < 0.05}
    return adjusted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--swap-run")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    primary = run(Path(a.run), "confirm")
    report = {"contract": "casepath.arena-v1-confirmatory-decision/1.0.0", "primary": primary, "hypotheses": {}}

    ctes_h = primary["arms"]["ctes"]["hearsay_receipts"]
    abl_h = primary["arms"]["ctes-ablation"]["hearsay_receipts"]
    report["hypotheses"]["H1"] = {
        "statement": "ctes yields zero hearsay receipts; ctes-ablation yields at least five",
        "ctes_hearsay_receipts": ctes_h, "ablation_hearsay_receipts": abl_h,
        "confirmed": bool(ctes_h == 0 and abl_h >= 5)}

    pv = {"H2": primary["paired_vs_ctes"]["full"]["p_boot"],
          "H3": primary["paired_vs_ctes"]["ctes-ablation"]["p_boot"]}
    adj = holm(pv)
    for key, arm, text in (("H2", "full", "U(ctes) - U(full) > 0"),
                           ("H3", "ctes-ablation", "U(ctes) - U(ctes-ablation) > 0")):
        p = primary["paired_vs_ctes"][arm]
        report["hypotheses"][key] = {
            "statement": text, "comparator": arm, "families": p["families"],
            "mean_diff": p["mean_diff"], "ci95": p["ci95"], "wins": p["wins"], "losses": p["losses"], "ties": p["ties"],
            "p_raw": adj[key]["p_raw"], "p_holm": adj[key]["p_holm"],
            "ci_excludes_zero": bool(p["ci95"][0] > 0 or p["ci95"][1] < 0),
            "established": bool((p["ci95"][0] > 0 or p["ci95"][1] < 0) and adj[key]["reject_at_05"] and p["mean_diff"] > 0)}

    if a.swap_run:
        swap = run(Path(a.swap_run), "swap")
        report["swap"] = swap
        # restrict the primary comparison to the families present in the swap set, so the signs are matched
        Lp, Ls = load(Path(a.run)), load(Path(a.swap_run))
        fmp = {arm: family_means(p, Lp["family"]) for arm, p in Lp["per_episode"].items()}
        fms = {arm: family_means(p, Ls["family"]) for arm, p in Ls["per_episode"].items()}
        shared = sorted(set(fmp["ctes"]) & set(fms["ctes"]))
        def sign_on(fmx, arm):
            d = [fmx["ctes"][f] - fmx[arm][f] for f in shared if f in fmx.get(arm, {})]
            mean = fmean(d) if d else 0.0
            return (1 if mean > 0 else (-1 if mean < 0 else 0)), round(mean, 4)
        signs = {}
        for arm in ("full", "ctes-ablation"):
            sp, mp = sign_on(fmp, arm); ss, ms = sign_on(fms, arm)
            signs[arm] = {"primary_sign": sp, "primary_mean_diff": mp, "swap_sign": ss, "swap_mean_diff": ms,
                          "agree": bool(sp == ss)}
        report["hypotheses"]["H4"] = {
            "statement": "on the shared families the sign of U(ctes)-U(full) and U(ctes)-U(ctes-ablation) agrees "
                         "between writers, and ctes records zero hearsay receipts under both",
            "shared_families": len(shared), "signs": signs,
            "ctes_hearsay_primary": ctes_h, "ctes_hearsay_swap": swap["arms"]["ctes"]["hearsay_receipts"],
            "confirmed": bool(all(v["agree"] for v in signs.values()) and ctes_h == 0
                              and swap["arms"]["ctes"]["hearsay_receipts"] == 0)}

    Path(a.out).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in
                          ("confirmed", "established", "mean_diff", "ci95", "p_holm", "ctes_hearsay_receipts",
                           "ablation_hearsay_receipts", "families", "wins", "losses")}
                      for k, v in report["hypotheses"].items()}, indent=1))


if __name__ == "__main__":
    main()
