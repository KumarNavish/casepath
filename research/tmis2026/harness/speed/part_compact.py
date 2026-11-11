"""The compact answer (CASEPATH_READING_FORM=compact) against the long form at the same commit, checklist only. No model call.

    <venv>/bin/python harness/speed/part_compact.py   -> runs/speed/part_compact.json

Long form: the stored runs of the tested commit 6a72159c (theft stories 4-5: plans_theft_gpt-6-luna_fresh_e-check.json runs
0-2; tenancy: plans_tenancy_gpt-6-luna_fresh_e-check.json). The speed branch sends exactly these requests (cache-only
replay, runs/speed/replay_summary.md), so they are the branch's long-form baseline. Compact: runs/speed/live_compact-theft.json
(runs 60-62) and live_compact-tenancy.json (run 60). Measures as harness/speed/part_d.py. Answer counts per reading: from
each reading response in the cache (a compact response decoded with the branch's own decode_compact); a quotation retry
(a response answering fewer conditions than the reading before it) is not counted as a reading.
"""
import json
import random
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(HERE))
import part_d as D  # noqa: E402

sys.path.insert(0, "/home/user/work/casepath-speed/casepath-internal")
from casepath.agents.team import COMPACT_CODES  # noqa: E402

R, OUT = TMIS / "runs", TMIS / "runs" / "speed"
CACHE = R / "product" / "cache"


def content(key):
    p = CACHE / f"{key}.json"
    if not p.exists():
        return None
    try:
        return json.loads(json.loads(json.loads(p.read_text())["body"])["choices"][0]["message"]["content"])
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def reading_counts(entry):
    """Per reading of one case-run: counts of true / false / open / not_stated, and the reading's output tokens."""
    out, most = [], 0
    for k in D.keys_of(entry):
        c = content(k)
        if not isinstance(c, dict):
            continue
        if "conditions" in c:
            verdicts = [r["verdict"] for r in c["conditions"]]
        elif "codes" in c:
            verdicts = [COMPACT_CODES.get(x, "?") for x in "".join(str(c["codes"]).split()).upper()]
        else:
            continue
        most = max(most, len(verdicts))
        if len(verdicts) < 0.8 * most:
            continue  # a quotation retry
        n = Counter(verdicts)
        out.append({"true": n["true"], "false": n["false"], "open": n["open"], "not_stated": n["not_stated"], "n": len(verdicts),
                    "output_tokens": D.usage(k)[1]})
    return out


def main():
    tested, compact = {}, {}
    for f in ("plans_theft_gpt-6-luna_fresh_e-check.json", "plans_tenancy_gpt-6-luna_fresh_e-check.json"):
        for k, v in D.load(R / "product" / f).items():
            _, c, r = k.split("|")
            tested[(c, int(r))] = v
    for f in ("live_compact-theft.json", "live_compact-tenancy.json"):
        if (OUT / f).exists():
            for k, v in D.load(OUT / f).items():
                _, c, r = k.split("|")
                compact[(c, int(r) - 60)] = v
    theft_ids = {c for c, _ in compact if c.startswith("s")}
    ten_ids = sorted({c for c, _ in compact if c.startswith("fcl_")})
    A = {"tested": {k: v for k, v in tested.items() if k[0] in theft_ids}, "short": {k: v for k, v in compact.items() if k[0] in theft_ids}}
    res = {"coverage": {a: len(v) for a, v in A.items()}, "failed": [f"{c}|{r}" for (c, r), v in compact.items() if v.get("status") != "completed"]}
    res["theft"] = D.theft(A, stories=(4, 5))
    res["theft"]["per_run"] = {}
    for r in range(3):
        one = {a: {k: v for k, v in P.items() if k[1] == r} for a, P in A.items()}
        x = D.theft(one, stories=(4, 5))["per_pair_run"]
        res["theft"]["per_run"][r] = {a: {m: x[a][m] for m in ("wrong_plus_missed_per_pair", "open_unchanged_share")} for a in x}
    counts = {}
    for name, P in (("long", A["tested"]), ("compact", A["short"])):
        per_run = defaultdict(list)
        for (c, r), v in P.items():
            per_run[r] += reading_counts(v)
        counts[name] = {r: {m: st.mean(x[m] for x in rows) for m in ("true", "false", "open", "not_stated", "output_tokens")} | {"readings": len(rows)}
                        for r, rows in sorted(per_run.items())}
    res["theft"]["answers_per_reading_by_run"] = counts
    res["theft"]["cost"] = D.cost_time(A, {"theft": theft_ids})["theft"]
    if ten_ids:
        T = {"tested": {k: v for k, v in tested.items() if k[0] in ten_ids and k[1] == 0},
             "short": {k: v for k, v in compact.items() if k[0] in ten_ids}}
        import tenancy_fresh as F
        res["tenancy_run0"] = D.tenancy({a: {(c, r): v for (c, r), v in P.items()} for a, P in T.items()}, ten_ids, F.reference,
                                        lambda c: F.reference(c)["family"])
        T3 = {"tested": {k: v for k, v in tested.items() if k[0] in ten_ids}}
        res["tenancy_tested_3runs"] = D.tenancy({"tested": T3["tested"], "short": T3["tested"]}, ten_ids, F.reference,
                                                lambda c: F.reference(c)["family"])["per_claim_run"]["tested"]
        tc = {}
        for name, P in (("long", T["tested"]), ("compact", T["short"])):
            rows = [x for v in P.values() for x in reading_counts(v)]
            tc[name] = {m: st.mean(x[m] for x in rows) for m in ("true", "false", "open", "not_stated", "output_tokens")} | {"readings": len(rows)}
        res["tenancy_answers_per_reading"] = tc
        res["tenancy_cost"] = D.cost_time(T, {"tenancy": set(ten_ids)})["tenancy"]
    (OUT / "part_compact.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
