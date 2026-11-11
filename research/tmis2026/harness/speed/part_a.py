"""Part A of the speed work: where the cost and the time of a product run go, from stored records only (no model call).

    python3 harness/speed/part_a.py            -> runs/speed/part_a.json and runs/speed/part_a.md

Inputs (read only):
- runs/study3/confirm/plans_{tenancy,theft}_casepath{,_checklist}.json: per case-run the request keys in call order
  ("keys": a paid call is listed twice, a call answered from the response cache once, as harness/study3/product_case.py
  recorded them), the agent of each usage row ("agents"), the stored wall-clock time ("seconds");
- the development runs of the tested commit 6a72159c (runs/product/plans_*_{e-check,e-full12,e-full-s4,e67-check,probe_e}.json);
- runs/product/cache/<key>.json: the provider's response, with its usage (prompt, cached, completion and reasoning
  tokens, cost);
- runs/product/ledger_dev_gpt-6-luna.jsonl: the time ("at", whole seconds) each paid response arrived.

Stage of a call: the agent of its usage row, refined by what the response is: a reading answers a "conditions" list
(the claim reader's first is reading 1, a second claim-reader conditions answer is its quotation retry; the source
checker's conditions answers are readings 2 and 3, a conditions answer that answers fewer than 80% of the most
conditions any answer of that case-run gives is the quotation retry of the reading before it); the source checker's
"documents" answer is the second judgment of documents, its "items" answer is the source check; the claim reader's
non-reading calls before its first reading are the brief, after it the re-recording after the check.

Latency of a call (estimate): the ledger time of its paid response minus the ledger time of the previous paid response
of the same case-run and design, when every call between them was answered from the cache (instant). Whole seconds,
includes the product's own work between the calls, and the calls ran while 20 case-runs ran in parallel. The first
paid call of a case-run (usually the router) has no estimate.
"""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from datetime import datetime
from pathlib import Path

TMIS = Path(__file__).resolve().parents[2]
CACHE = TMIS / "runs" / "product" / "cache"
LEDGER = TMIS / "runs" / "product" / "ledger_dev_gpt-6-luna.jsonl"
OUT = TMIS / "runs" / "speed"

STUDY = {("tenancy", "full"): ("runs/study3/confirm/plans_tenancy_casepath.json", "STUDY3-confirm-casepath"),
         ("tenancy", "checklist"): ("runs/study3/confirm/plans_tenancy_casepath_checklist.json", "STUDY3-confirm-casepath_checklist"),
         ("theft", "full"): ("runs/study3/confirm/plans_theft_casepath.json", "STUDY3-confirm-casepath"),
         ("theft", "checklist"): ("runs/study3/confirm/plans_theft_casepath_checklist.json", "STUDY3-confirm-casepath_checklist")}
DEV = {("tenancy", "checklist"): ["runs/product/plans_tenancy_gpt-6-luna_fresh_e-check.json"],
       ("tenancy", "full"): ["runs/product/plans_tenancy_gpt-6-luna_fresh_e-full12.json", "runs/product/plans_tenancy_gpt-6-luna_probe_e.json"],
       ("theft", "checklist"): ["runs/product/plans_theft_gpt-6-luna_fresh_e-check.json", "runs/product/plans_theft_gpt-6-luna_fresh_e67-check.json"],
       ("theft", "full"): ["runs/product/plans_theft_gpt-6-luna_fresh_e-full-s4.json"]}
STAGES = ["router", "brief", "process builder", "reading 1", "reading 1 retry", "reading 2", "reading 2 retry", "reading 3",
          "reading 3 retry", "document finder", "second judgment", "source check", "re-recording", "result checker", "other"]


class Cache:
    def __init__(self):
        self.memo = {}

    def body(self, key):
        if key not in self.memo:
            p = CACHE / f"{key}.json"
            self.memo[key] = json.loads(json.loads(p.read_text())["body"]) if p.exists() else None
        return self.memo[key]

    def usage(self, key):
        b = self.body(key) or {}
        u = b.get("usage") or {}
        return {"input": u.get("prompt_tokens") or 0, "cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0,
                "output": u.get("completion_tokens") or 0,
                "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0,
                "usd": u.get("cost") or 0.0,
                "usd_input": (u.get("cost_details") or {}).get("upstream_inference_prompt_cost"),
                "usd_output": (u.get("cost_details") or {}).get("upstream_inference_completions_cost")}

    def content(self, key):
        b = self.body(key)
        try:
            text = b["choices"][0]["message"].get("content") or ""
            return json.loads(text) if text.lstrip().startswith("{") else None
        except (TypeError, KeyError, IndexError, ValueError):
            return None


def stages_of(keys, agents, cache):
    """Stage of each distinct call of one case-run (keys and agents aligned)."""
    contents = [cache.content(k) for k in keys]
    nconds = [len(c["conditions"]) if isinstance(c, dict) and isinstance(c.get("conditions"), list) else None for c in contents]
    most = max([n for n in nconds if n is not None] or [0])
    out, seen_reading, sc_readings = [], False, 0
    for agent, c, n in zip(agents, contents, nconds):
        if agent == "router":
            s = "router"
        elif agent == "claim_reader":
            if n is not None:
                s = "reading 1" if not seen_reading else "reading 1 retry"
                seen_reading = True
            else:
                s = "brief" if not seen_reading else "re-recording"
        elif agent == "source_checker":
            if n is not None:
                if n >= 0.8 * most or sc_readings == 0:
                    sc_readings += 1
                    s = f"reading {1 + sc_readings}"
                else:
                    s = f"reading {1 + sc_readings} retry"
            elif isinstance(c, dict) and "documents" in c:
                s = "second judgment"
            else:
                s = "source check"
        elif agent in ("document_finder", "process_builder", "result_checker"):
            s = agent.replace("_", " ")
        else:
            s = "other"
        if s.startswith("reading") and int(s.split()[1]) > 3:
            s = "other"
        out.append(s)
    return out


def ledger_times(arms):
    t = {}
    for line in LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm") in arms:
            t[(r["arm"], r["key"])] = datetime.strptime(r["at"], "%Y-%m-%dT%H:%M:%SZ").timestamp()
    return t


def summarise(entries, cache, times=None, arm=None):
    """entries: stored plan entries of one design and regime."""
    agg = defaultdict(lambda: defaultdict(float))
    lat = defaultdict(list)
    n = aligned = 0
    totals = defaultdict(float)
    secs = []
    per_run = []  # for projections: [(stage, usage, latency or None, paid)]
    for e in entries:
        if not e or not e.get("keys"):
            continue
        n += 1
        raw = e["keys"]
        counts = defaultdict(int)
        for k in raw:
            counts[k] += 1
        keys = list(dict.fromkeys(raw))
        for k in keys:
            u = cache.usage(k)
            for f in ("input", "cached", "output", "reasoning", "usd"):
                totals[f] += u[f]
        if e.get("seconds") is not None:
            secs.append(e["seconds"])
        agents = e.get("agents") or []
        if len(agents) != len(keys):
            continue
        aligned += 1
        stg = stages_of(keys, agents, cache)
        prev_t, between_cached = None, True
        calls = []
        for k, s in zip(keys, stg):
            u = cache.usage(k)
            a = agg[s]
            a["calls"] += 1
            for f in ("input", "cached", "output", "reasoning", "usd"):
                a[f] += u[f]
            a["usd_input"] += u["usd_input"] or 0
            a["usd_output"] += u["usd_output"] or 0
            paid = counts[k] >= 2
            a["paid"] += paid
            latency = None
            if times is not None and paid and (arm, k) in times:
                t = times[(arm, k)]
                if prev_t is not None and between_cached and 0 <= t - prev_t < 600:
                    latency = t - prev_t
                    lat[s].append(latency)
                prev_t, between_cached = t, True
            calls.append((s, u, latency, paid))
        per_run.append({"seconds": e.get("seconds"), "calls": calls})
    stages = {}
    for s in STAGES:
        if s not in agg:
            continue
        a = agg[s]
        stages[s] = {"calls_per_case_run": a["calls"] / aligned, "paid_share": a["paid"] / a["calls"],
                     "input_per_case_run": a["input"] / aligned, "cached_input_per_case_run": a["cached"] / aligned,
                     "cached_share_of_input": a["cached"] / a["input"] if a["input"] else None,
                     "output_per_case_run": a["output"] / aligned, "reasoning_per_case_run": a["reasoning"] / aligned,
                     "usd_per_case_run": a["usd"] / aligned, "usd_input_per_case_run": a["usd_input"] / aligned,
                     "usd_output_per_case_run": a["usd_output"] / aligned,
                     "latency_s_median_per_call": st.median(lat[s]) if lat[s] else None, "latency_calls": len(lat[s]),
                     "latency_s_mean_per_call": st.mean(lat[s]) if lat[s] else None}
    tot_usd = sum(a["usd"] for a in agg.values())
    return {"case_runs": n, "aligned": aligned,
            "usd_per_case_run_all": totals["usd"] / n if n else None,
            "tokens_per_case_run_all": {f: totals[f] / n for f in ("input", "cached", "output", "reasoning")} if n else None,
            "usd_input_share": sum(a["usd_input"] for a in agg.values()) / tot_usd if tot_usd else None,
            "usd_output_share": sum(a["usd_output"] for a in agg.values()) / tot_usd if tot_usd else None,
            "seconds_median": st.median(secs) if secs else None, "stages": stages}, per_run, lat


def fit_latency(lat_by_stage, per_runs):
    """Least squares latency = a + b * output tokens over the calls with a latency estimate (one regime)."""
    xs, ys = [], []
    for runs in per_runs:
        for r in runs:
            for s, u, latency, paid in r["calls"]:
                if latency is not None:
                    xs.append(u["output"])
                    ys.append(latency)
    mx, my = st.mean(xs), st.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b, len(xs)


def projections(per_run, model, stage_median):
    """Per case-run: modelled sequential time (each call's own latency estimate where it has one, otherwise the fit on its
    output tokens; the router's from the fit), and the same with the three readings (each with its retry) concurrently."""
    a, b, _ = model
    seq, par, chains_saved = [], [], []
    for r in per_run:
        total = 0.0
        chain = defaultdict(float)
        for s, u, latency, paid in r["calls"]:
            t = latency if latency is not None else a + b * u["output"]
            total += t
            if s.startswith("reading"):
                chain[s.split()[1]] += t
        seq.append(total)
        if chain:
            saved = sum(chain.values()) - max(chain.values())
        else:
            saved = 0.0
        chains_saved.append(saved)
        par.append(total - saved)
    return {"modelled_sequential_s_median": st.median(seq), "projected_parallel_readings_s_median": st.median(par),
            "saved_s_median": st.median(chains_saved), "saved_share_median": st.median([s / t for s, t in zip(chains_saved, seq) if t])}


def main():
    cache = Cache()
    arms = {v[1] for v in STUDY.values()}
    times = ledger_times(arms)
    res = {"study3_confirm": {}, "dev_tested_commit": {}, "projections": {}, "latency_fit": {}}
    per_runs = defaultdict(list)
    lats = {}
    for (regime, design), (path, arm) in STUDY.items():
        entries = list(json.loads((TMIS / path).read_text()).values())
        summ, per_run, lat = summarise(entries, cache, times, arm)
        res["study3_confirm"][f"{regime}/{design}"] = summ
        per_runs[regime].append(per_run)
        lats[(regime, design)] = (per_run, lat)
    for regime in ("tenancy", "theft"):
        model = fit_latency(None, per_runs[regime])
        res["latency_fit"][regime] = {"intercept_s": model[0], "s_per_output_token": model[1], "calls": model[2]}
        for design in ("full", "checklist"):
            per_run, lat = lats[(regime, design)]
            med = {s: st.median(v) for s, v in lat.items() if v}
            res["projections"][f"{regime}/{design}"] = projections(per_run, model, med)
    for (regime, design), paths in DEV.items():
        entries = []
        for p in paths:
            entries += list(json.loads((TMIS / p).read_text()).values())
        summ, _, _ = summarise(entries, cache)
        res["dev_tested_commit"][f"{regime}/{design}"] = summ
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "part_a.json").write_text(json.dumps(res, indent=1))
    lines = []
    for block in ("study3_confirm", "dev_tested_commit"):
        for name, s in res[block].items():
            lines.append(f"\n### {block} {name}: {s['case_runs']} case-runs ({s['aligned']} attributed), USD {s['usd_per_case_run_all']:.5f} per case-run, "
                         f"input share of cost {s['usd_input_share']:.1%}, output {s['usd_output_share']:.1%}, median stored seconds {s['seconds_median']}\n")
            lines.append("| stage | calls | paid share | input | cached | cached share | output | reasoning | USD | USD in | USD out | median latency s (n) |")
            lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for stg, v in s["stages"].items():
                cs = f"{v['cached_share_of_input']:.0%}" if v["cached_share_of_input"] is not None else "–"
                la = f"{v['latency_s_median_per_call']:.0f} ({v['latency_calls']})" if v["latency_s_median_per_call"] is not None else "–"
                lines.append(f"| {stg} | {v['calls_per_case_run']:.2f} | {v['paid_share']:.0%} | {v['input_per_case_run']:.0f} | {v['cached_input_per_case_run']:.0f} | {cs} | "
                             f"{v['output_per_case_run']:.0f} | {v['reasoning_per_case_run']:.0f} | {v['usd_per_case_run']:.5f} | {v['usd_input_per_case_run']:.5f} | "
                             f"{v['usd_output_per_case_run']:.5f} | {la} |")
    lines.append("\n### Latency fit and projections (PROJECTED)\n")
    lines.append(json.dumps({"fit": res["latency_fit"], "projections": res["projections"]}, indent=1))
    (OUT / "part_a.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
