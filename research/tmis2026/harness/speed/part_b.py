"""Part B live measurement summary (no model call): runs/speed/live_partb.json -> runs/speed/part_b.json / .md.

Per configuration and regime, over the same cases: time from POST /runs to the checklist on the run (speed branch:
the stored `checklist`; tested commit: the end of the run) and to the end of the run, and the cost of the paid calls
(provider usage.cost), median and range. Also the paired difference per case (branch minus tested commit) for full and
checklist only.
"""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "runs" / "speed"


def summary(vals):
    return {"n": len(vals), "median": st.median(vals), "min": min(vals), "max": max(vals)} if vals else None


def main():
    d = json.loads((OUT / "live_partb.json").read_text())
    by = defaultdict(dict)
    for k, v in d.items():
        if v.get("status") != "completed":
            continue
        calls = (v.get("transport") or {}).get("calls") or []
        by[(v["regime"], v["config"])][v["case"]] = {
            "to_checklist_s": v["timing"]["to_checklist_s"], "to_result_s": v["timing"]["to_result_s"],
            "usd": sum(c.get("usd") or 0 for c in calls if not c.get("cached")), "calls": len(calls),
            "cached_calls": sum(1 for c in calls if c.get("cached")),
            "output": sum(c.get("output") or 0 for c in calls), "input": sum(c.get("input") or 0 for c in calls),
            "cached_input": sum(c.get("cached_tokens") or 0 for c in calls)}
    res = {"configs": {}, "paired": {}, "failed": [k for k, v in d.items() if v.get("status") != "completed"]}
    for (regime, config), rows in sorted(by.items()):
        res["configs"][f"{regime}/{config}"] = {f: summary([r[f] for r in rows.values()]) for f in
                                               ("to_checklist_s", "to_result_s", "usd", "calls", "output", "input", "cached_input")}
        res["configs"][f"{regime}/{config}"]["usd_mean"] = sum(r["usd"] for r in rows.values()) / len(rows)
        res["configs"][f"{regime}/{config}"]["cached_calls_total"] = sum(r["cached_calls"] for r in rows.values())
    for regime in ("tenancy", "theft"):
        for a, b in (("branch-full", "base-full"), ("branch-check", "base-check"), ("branch-full", "base-check")):
            A, B = by.get((regime, a), {}), by.get((regime, b), {})
            common = sorted(set(A) & set(B))
            res["paired"][f"{regime}: {a} - {b}"] = {f: summary([A[c][f] - B[c][f] for c in common]) for f in ("to_checklist_s", "to_result_s", "usd")}
    (OUT / "part_b.json").write_text(json.dumps(res, indent=1))
    lines = ["| regime/config | n | to checklist s: median (range) | to result s: median (range) | USD mean | USD median (range) |", "|---|---|---|---|---|---|"]
    for k, v in res["configs"].items():
        c, r, u = v["to_checklist_s"], v["to_result_s"], v["usd"]
        lines.append(f"| {k} | {c['n']} | {c['median']:.1f} ({c['min']:.1f}-{c['max']:.1f}) | {r['median']:.1f} ({r['min']:.1f}-{r['max']:.1f}) | "
                     f"{v['usd_mean']:.4f} | {u['median']:.4f} ({u['min']:.4f}-{u['max']:.4f}) |")
    lines.append("\n| paired (per case) | n | to checklist s: median diff (range) | to result s: median diff (range) | USD median diff |\n|---|---|---|---|---|")
    for k, v in res["paired"].items():
        if v["to_checklist_s"]:
            lines.append(f"| {k} | {v['to_checklist_s']['n']} | {v['to_checklist_s']['median']:.1f} ({v['to_checklist_s']['min']:.1f} to {v['to_checklist_s']['max']:.1f}) | "
                         f"{v['to_result_s']['median']:.1f} ({v['to_result_s']['min']:.1f} to {v['to_result_s']['max']:.1f}) | {v['usd']['median']:.4f} |")
    (OUT / "part_b.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
