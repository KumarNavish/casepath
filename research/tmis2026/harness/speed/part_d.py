"""Part D: the shorter answer (CASEPATH_READING_FORM=addressed) against the tested commit, checklist only, development data.
No model call.

    <venv>/bin/python harness/speed/part_d.py   -> runs/speed/part_d.json, runs/speed/part_d.md

Arms (three runs each):
- tested: the tested commit 6a72159c, checklist only: tenancy runs/product/plans_tenancy_gpt-6-luna_fresh_e-check.json,
  theft plans_theft_gpt-6-luna_fresh_e-check.json (stories 4-5) and _e67-check.json (stories 6-7), probe
  runs/speed/live_probe-base.json (the tested commit, checklist only, runs 0-2);
- short: the speed branch with the shorter answer, checklist only, runs/speed/live_partd.json (runs 50-52).
Measures: tenancy and probe with analysis/study2.py::ten_row (strict unsafe errors, held required documents, unneeded
holds = spurious holds, premature requests) per claim-run; theft pairs as harness/product/score_all.py (wrong + missed
per changed-fact pair, share of open pairs whose requests stay unchanged). Cost, output tokens: from the provider's usage
of every distinct request of a case-run (runs/product/cache), so cached and paid calls count alike.
Paired differences (short minus tested): per claim (tenancy) or pair (theft), the mean over its runs; mean over claims;
95% interval from a cluster bootstrap (2000 draws) over families (tenancy, probe: workflow family of the reference)
or changed facts (theft: the pair's condition).
"""
import json
import random
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

TMIS = Path(__file__).resolve().parents[2]
for p in (TMIS / "harness" / "product", TMIS / "harness", TMIS / "harness" / "v2", TMIS / "fresh", TMIS / "analysis", TMIS / "dev_probe"):
    sys.path.insert(0, str(p))
R = TMIS / "runs"
OUT = R / "speed"
CACHE = R / "product" / "cache"
load = lambda p: json.loads(Path(p).read_text())
_usage = {}


def usage(key):
    if key not in _usage:
        p = CACHE / f"{key}.json"
        u = (json.loads(json.loads(p.read_text())["body"]).get("usage") or {}) if p.exists() else {}
        _usage[key] = (u.get("cost") or 0.0, u.get("completion_tokens") or 0, (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
    return _usage[key]


def keys_of(entry):
    return list(dict.fromkeys(entry.get("keys") or (entry.get("transport") or {}).get("keys") or []))


def arms():
    tested = {}
    for f in ("plans_tenancy_gpt-6-luna_fresh_e-check.json", "plans_theft_gpt-6-luna_fresh_e-check.json", "plans_theft_gpt-6-luna_fresh_e67-check.json"):
        for k, v in load(R / "product" / f).items():
            _, c, r = k.split("|")
            tested[(c, int(r))] = v
    for k, v in load(OUT / "live_probe-base.json").items():
        _, c, r = k.split("|")
        tested[(c, int(r))] = v
    short = {}
    for k, v in load(OUT / "live_partd.json").items():
        _, c, r = k.split("|")
        short[(c, int(r) - 50)] = v
    return {"tested": tested, "short": short}


def boot(diffs_by_cluster, B=2000, seed=1):
    clusters = sorted(diffs_by_cluster)
    allv = [d for c in clusters for d in diffs_by_cluster[c]]
    rng = random.Random(seed)
    draws = []
    for _ in range(B):
        s = [d for c in (rng.choice(clusters) for _ in clusters) for d in diffs_by_cluster[c]]
        draws.append(sum(s) / len(s))
    draws.sort()
    return {"mean": sum(allv) / len(allv), "lo": draws[int(0.025 * B)], "hi": draws[int(0.975 * B) - 1], "units": len(allv), "clusters": len(clusters)}


def tenancy(A, ids, ref_of, family_of, kind_of=None):
    from study2 import ten_row
    measures = ("strict_unsafe", "held_req", "spurious_hold", "premature", "missed", "unnecessary", "correct_hold", "handed")
    per = {}
    for arm, P in A.items():
        per[arm] = {}
        for c in ids:
            rows = [ten_row(ref_of(c), (P.get((c, r)) or {}).get("plan")) for r in range(3) if (c, r) in P]
            per[arm][c] = {m: sum(x[m] for x in rows) / len(rows) for m in measures} if rows else None
    res = {"per_claim_run": {}, "paired": {}}
    for arm in A:
        ok = [c for c in ids if per[arm][c]]
        res["per_claim_run"][arm] = {m: sum(per[arm][c][m] for c in ok) / len(ok) for m in measures}
        res["per_claim_run"][arm]["claims"] = len(ok)
    both = [c for c in ids if per["tested"][c] and per["short"][c]]
    for m in measures:
        by = defaultdict(list)
        for c in both:
            by[family_of(c)].append(per["short"][c][m] - per["tested"][c][m])
        res["paired"][m] = boot(by)
    if kind_of:
        res["by_kind"] = {}
        for arm in A:
            groups = defaultdict(list)
            for c in ids:
                if per[arm][c]:
                    groups[kind_of(c)].append(per[arm][c])
            res["by_kind"][arm] = {k: {m: sum(x[m] for x in v) / len(v) for m in measures} | {"claims": len(v)} for k, v in groups.items()}
    return res


def theft(A, stories=(4, 5, 6, 7)):
    import common
    from theft_data import best_realization
    from theft_score import delta
    pairs = [p for p in common.data("theft", "fresh").pairs() if p["story"] in stories]
    empty = {"requests": [], "holds": []}
    per = {}
    for arm, P in A.items():
        per[arm] = {}
        for p in pairs:
            vals = []
            for r in range(3):
                off, var = (P.get((p["off"], r)) or {}).get("plan"), (P.get((p["variant"], r)) or {}).get("plan")
                if (p["off"], r) not in P or (p["variant"], r) not in P:
                    continue
                off, var = off or empty, var or empty
                pred = delta(set(off["requests"]), set(var["requests"]))
                if p["kind"] == "on":
                    sel, _ = best_realization(pred, p["reference"])
                    vals.append(len(set(pred) - set(sel)) + len(set(sel) - set(pred)))
                else:
                    vals.append(0 if pred else 1)  # 1 = the requests stay unchanged
            per[arm][p["pair_id"]] = (p["kind"], p["condition"], sum(vals) / len(vals)) if vals else None
    res = {"per_pair_run": {}, "paired": {}}
    for arm in A:
        on = [v[2] for v in per[arm].values() if v and v[0] == "on"]
        un = [v[2] for v in per[arm].values() if v and v[0] != "on"]
        res["per_pair_run"][arm] = {"wrong_plus_missed_per_pair": sum(on) / len(on), "open_unchanged_share": sum(un) / len(un),
                                    "on_pairs": len(on), "open_pairs": len(un)}
    for kind, name in (("on", "wrong_plus_missed_per_pair"), ("open", "open_unchanged_share")):
        by = defaultdict(list)
        for pid, v in per["short"].items():
            t = per["tested"].get(pid)
            if v and t and (v[0] == "on") == (kind == "on"):
                by[v[1]].append(v[2] - t[2])
        res["paired"][name] = boot(by)
    return res


def cost_time(A, groups):
    out = {}
    for g, ids in groups.items():
        out[g] = {}
        for arm, P in A.items():
            rows = [v for (c, r), v in P.items() if c in ids]
            usd = [sum(usage(k)[0] for k in keys_of(v)) for v in rows]
            outp = [sum(usage(k)[1] for k in keys_of(v)) for v in rows]
            reason = [sum(usage(k)[2] for k in keys_of(v)) for v in rows]
            out[g][arm] = {"case_runs": len(rows), "usd_per_case_run": sum(usd) / len(rows), "output_tokens_per_case_run": sum(outp) / len(rows),
                           "reasoning_tokens_per_case_run": sum(reason) / len(rows)}
            times = [v["timing"]["to_checklist_s"] for v in rows if v.get("timing")]
            if times:
                out[g][arm].update(time_to_checklist_median_s=st.median(times), time_min_s=min(times), time_max_s=max(times))
            reading_out = []
            for v in rows:  # output tokens of the reading calls (answers with "conditions")
                for c in (v.get("transport") or {}).get("calls") or []:
                    if not c.get("cached") and c.get("output") is not None and c.get("key"):
                        reading_out.append(c)
            out[g][arm]["paid_calls_logged"] = len(reading_out)
    return out


def main():
    A = arms()
    import tenancy_fresh as F
    import tenancy_probe as PR
    ten_ids = sorted({c for c, _ in A["tested"] if c.startswith("fcl_")})
    probe_ids = sorted({c for c, _ in A["tested"] if c.startswith("pcl_")})
    theft_ids = sorted({c for c, _ in A["tested"] if c.startswith("s")})
    res = {"coverage": {arm: len(P) for arm, P in A.items()}}
    res["tenancy"] = tenancy(A, ten_ids, F.reference, lambda c: F.reference(c)["family"])
    res["probe"] = tenancy(A, probe_ids, PR.reference, lambda c: PR.reference(c)["family"], kind_of=lambda c: PR.reference(c)["probe"]["kind"])
    res["theft"] = theft(A)
    res["cost"] = cost_time(A, {"tenancy": set(ten_ids), "theft": set(theft_ids), "probe": set(probe_ids)})
    (OUT / "part_d.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
