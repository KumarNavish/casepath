"""Score Study 2 plans with Study 1's scoring code (no model calls).

Usage: python3 score.py <model_tag> [--data original] [--split dev]
Tenancy per claim-run: requested (required and requested), held, handed over, silently missed, unnecessary,
strict unsafe (unnecessary + missed + handed over), using analysis/analyze.py's tenancy_row / summ.
Theft: off->on pairs pooled with the frozen scorer (wrong, missed, F1) and off->open pairs (unchanged = stable).
Failed outputs are scored as empty plans, as in Study 1.
"""
import argparse
import json
import sys

import common

ap = argparse.ArgumentParser()
ap.add_argument("tag")
ap.add_argument("--data", default="original")
ap.add_argument("--split", default="dev")
ap.add_argument("--stories", default=None)
args = ap.parse_args()
sys.argv = [sys.argv[0], args.tag]
sys.path.insert(0, str(common.TMIS / "analysis"))
from analyze import summ, tenancy_row  # noqa: E402
from theft_score import score_pair, pooled  # noqa: E402

K_MAX = 10
VARIANTS = {"CPv2": ["plan", "plan_no_verifier", "plan_no_presumption"], "CPv1": ["plan", "plan_exact"],
            "B1v2": ["plan"], "B1": ["plan"], "Rv2": ["plan"], "R": ["plan"],
            "CPv2p": ["plan", "plan_no_verifier", "plan_no_presumption"], "B1v2p": ["plan"], "Rv2p": ["plan"]}


def load(exp):
    p = common.OUT / f"plans_{exp}_{args.tag}_{args.data}_{args.split}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def tenancy():
    P, D = load("tenancy"), common.data("tenancy", args.data)
    from tenancy_score import unscored
    out = {}
    for design, fields in VARIANTS.items():
        for field in fields:
            rows = []
            for key, v in P.items():
                d, c, r = key.split("|")
                if d != design or not any(field in (x or {}) for kk, x in P.items() if kk.startswith(design + "|")):
                    continue
                R = set(D.reference(c)["request_set"]) - unscored(c)
                rows.append(tenancy_row(c, (v or {}).get(field), R))
            if rows:
                s = summ(rows)
                n = s["n"]
                out[f"{design}:{field}"] = {"claim_runs": n, "requested": s["tp"] / n, "held": s["held"] / n,
                                            "handed_over": s["handed"] / n, "missed": s["miss"] / n,
                                            "unnecessary": s["fp"] / n, "strict_unsafe": s["unsafe_strict_per_claim"],
                                            "required": s["nR"] / n, "failed": s["failed_outputs"],
                                            "nonrequired_holds": s["holds_nonrequired"] / n}
    return out


def theft():
    P, D = load("theft"), common.data("theft", args.data)
    T = D.texts()
    dev_story = min(v["story"] for v in T.values())
    pairs = [p for p in D.pairs() if (p["story"] == dev_story) == (args.split == "dev")]
    if args.stories:
        pairs = [p for p in D.pairs() if str(p["story"]) in args.stories.split(",")]
    out = {}
    for design, fields in VARIANTS.items():
        for field in fields:
            runs = sorted({int(k.split("|")[2]) for k in P if k.startswith(design + "|")})
            if not runs or not any(field in (v or {}) for k, v in P.items() if k.startswith(design + "|")):
                continue
            rows = []
            empty = {"requests": [], "holds": []}
            for r in runs:
                get = lambda t: ((P.get(f"{design}|{t}|{r}") or {}).get(field) or empty)
                for p in pairs:
                    if f"{design}|{p['variant']}|{r}" in P and f"{design}|{p['off']}|{r}" in P:
                        rows.append(score_pair(p, get(p["off"]), get(p["variant"])))
            on = pooled(rows)
            un = [x for x in rows if x["kind"] == "unresolved"]
            out[f"{design}:{field}"] = {"pair_runs_on": on["pairs"], "wrong": on["wrong"], "missed": on["missed"],
                                        "correct": on["correct"], "f1": round(on["f1"], 3),
                                        "wrong_per_pair": on["wrong"] / max(1, on["pairs"]),
                                        "missed_per_pair": on["missed"] / max(1, on["pairs"]),
                                        "open_pair_runs": len(un), "unchanged_when_open": (sum(x["stable"] for x in un) / len(un)) if un else None,
                                        "premature_when_open": (sum(x["premature"] for x in un) / len(un)) if un else None}
    return out


if __name__ == "__main__":
    res = {"tenancy": tenancy(), "theft": theft()}
    print(json.dumps(res, indent=1))
    common.dump(common.OUT / f"scores_{args.tag}_{args.data}_{args.split}{'_s' + args.stories.replace(',', '') if args.stories else ''}.json", res)
