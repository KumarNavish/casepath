"""Evaluate D5-D7: does the primary result survive rewriting every episode with a different model?

The swapped split shares the decisive split's latents, gold, evaluator, arms and analysis exactly; only the
prose differs. So a difference between the two runs is a writer effect and nothing else.
"""
from __future__ import annotations

import argparse, json, random
from pathlib import Path
from statistics import fmean

from casepath_api.arena_v1.analyze import load, family_means, paired

DECISIVE_CI = (0.0952, 0.2052)


def _bp(a, b, seed=20260914, n=5000):
    fams = sorted(set(a) & set(b)); d = [a[f] - b[f] for f in fams]
    rng = random.Random(seed)
    boots = [fmean([d[rng.randrange(len(d))] for _ in d]) for _ in range(n)]
    below = sum(x <= 0 for x in boots) / n
    return round(min(1.0, 2 * min(below, 1 - below)), 4)


def _pair(pe, fam, a_arm, b_arm, key):
    a, b = family_means(pe[a_arm], fam, key), family_means(pe[b_arm], fam, key)
    r = paired(a, b)
    return {"mean_diff": round(r["mean_diff"], 4), "ci95": [round(x, 4) for x in r["ci95"]],
            "wins": r["wins"], "losses": r["losses"], "families": r["families"], "p_boot": _bp(a, b),
            "ci_excludes_zero": bool(r["ci95"][0] > 0 or r["ci95"][1] < 0)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--swap-run", required=True)
    ap.add_argument("--original-run", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    Ls, Lo = load(Path(a.swap_run)), load(Path(a.original_run))
    ps, fs = Ls["per_episode"], Ls["family"]
    po, fo = Lo["per_episode"], Lo["family"]

    d5 = _pair(ps, fs, "ctes", "full", "state_acc")
    orig = _pair(po, fo, "ctes", "full", "state_acc")
    inside = DECISIVE_CI[0] <= d5["mean_diff"] <= DECISIVE_CI[1]
    prem_swap = {arm: int(sum(m["P"] for m in ps[arm].values())) for arm in ps if arm.startswith("ctes")}

    report = {
     "contract": "casepath.arena-v1-writer-swap-decision/1.0.0",
     "swap_writer": "anthropic/claude-sonnet-5", "original_writer": "openai/gpt-5.4-mini",
     "arm_model": "openai/gpt-5.4-mini", "episodes": len(fs), "families": len(set(fs.values())),
     "hypotheses": {
       "D5": {"statement": "state accuracy of ctes over full stays positive with an interval excluding zero "
                           "when every episode is rewritten by a different model",
              **d5, "confirmed": bool(d5["ci_excludes_zero"] and d5["mean_diff"] > 0)},
       "D6": {"statement": "the swapped estimate falls inside the decisive split's own interval",
              "decisive_ci95": list(DECISIVE_CI), "decisive_mean": orig["mean_diff"],
              "swapped_mean": d5["mean_diff"], "confirmed": bool(inside)},
       "D7": {"statement": "the satisfaction rule still carries premature readiness under the new writer",
              "premature_by_arm": prem_swap,
              "confirmed": bool(prem_swap.get("ctes-abl-satisfaction", 0) > prem_swap.get("ctes", 0))}},
     "same_split_original_writer": orig,
     "other_baselines_swapped": {c: _pair(ps, fs, "ctes", c, "state_acc")
                                 for c in ("direct-end-to-end", "constant") if c in ps},
     "arms": {arm: {"state_accuracy": round(fmean(family_means(per, fs, "state_acc").values()), 4),
                    "premature": int(sum(m["P"] for m in per.values())),
                    "hearsay": int(sum(m["hearsay"] for m in per.values()))}
              for arm, per in sorted(ps.items())}}
    Path(a.out).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "statement"}
                      for k, v in report["hypotheses"].items()}, indent=1))


if __name__ == "__main__":
    main()
