"""Prior-work baselines on the fresh theft texts (stories 4-5), with the reviewed rules (the knowledge the product's
converted workflow holds), and budget-matched self-consistency on both regimes. Development data; gpt-6-luna.

    python baselines_theft.py col|react --cap USD [--k 1]          theft: model executes rules (CoL) / ReAct agent
    python baselines_theft.py samples --kind theft|tenancy --n N --runs R --cap USD
                                                                   Rules-in-context samples for self-consistency
    python baselines_theft.py offline --product-label L             theft SC3 and two-valued, no calls

Every call goes through baselines.chat (run_product.CachingTransport): cached, cost only in
runs/product/ledger_dev_gpt-6-luna.jsonl, rows tagged with the arm. Output runs/product/baselines_theft_gpt-6-luna_fresh.json
keyed "<ARM>|<text>|<run>" with plans in catalogue names (as the theft scorer reads them), and
runs/product/samples_<kind>_gpt-6-luna_fresh.json keyed "<text or claim>|<sample index>".

COL    "Model executes rules" (Chain-of-Logic style): one call. The Rules-in-context material (policy, source passages,
       catalogue, the reviewed rules) and a task that first judges every rule condition true, false or unresolved with
       a quote, then applies the rules exactly with exact deferral (a document applies if it applies under every way
       the unresolved conditions could turn out; held if under some).
REACT  ReAct agent over the product's converted theft workflow (workflows/theft-reviewed): the same loop, tools and
       decision rules as the tenancy ReAct arm (baselines.py), on the one theft workflow.
SC<N>  Self-consistency over N Rules-in-context samples (the reviewed-rules request of the CP4 harness, `Rpack`), per
       document majority: requested if more than half the samples request it, else held if more than half request or
       hold it. SC3 run 0 uses the three cached Rpack runs; other samples are new calls (sample index 3 onwards).
TWO_F  Two-valued rule execution from the product's recorded readings: the product's accepted facts, every unresolved
       condition false, through the product's evaluator. No calls.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
for p in (HERE, TMIS / "harness", TMIS / "harness" / "v2", TMIS / "fresh"):
    sys.path.insert(0, str(p))
import baselines as B  # noqa: E402
import run_product as rp  # noqa: E402

OUT = rp.RUNS / "baselines_theft_gpt-6-luna_fresh.json"
THEFT_WF = HERE / "workflows" / "theft-reviewed"


def theft_texts():
    import theft_fresh as T
    texts = T.texts()
    return texts, sorted(t for t, v in texts.items() if v["story"] in (4, 5))


def theft_material():
    import theft_methods as tm
    import load_reviewed
    import v3
    import convert_theft
    system = v3.TheftV3(load_reviewed.load(convert_theft.RULES))
    base = tm.POLICY + "\n\n" + tm.sources_block() + "\n\n" + tm.catalogue_block() + "\n\n" + system.tp.rules_block()
    return tm, system, base


def rpack_sample(t, index, texts, material):
    tm, _system, base = material
    res, _u, err = B.chat([{"role": "system", "content": base + "\n\n" + tm.PLAN_TASK}, {"role": "user", "content": "CASE:\n" + texts[t]["text"]}],
                          tm.PLAN_SCHEMA, "checklist", index, t, "RPACK")
    return tm._ids(res) if res else None


COL_TASK = """TASK (model executes rules): First, for EVERY rule condition, judge whether it holds for this case: true, false
or unresolved, with one short exact quotation from the case for true or false. Silence, tentative language and
contradictory statements mean unresolved, never false. Then apply the rules exactly: a document is needed when the
condition of a rule whose chosen evidence route contains it is true (or the rule is unconditional). Unresolved
conditions: consider every way each could turn out; a document needed under every such completion is requested, one
needed under some but not all is held (ask about its condition first), one needed under none is not listed."""


def col_schema(tm, system):
    cond = {"type": "array", "maxItems": 120, "items": {"type": "object", "additionalProperties": False, "required": ["guard_id", "verdict", "quote"],
            "properties": {"guard_id": {"type": "string", "enum": sorted(system.tp.guards)},
                           "verdict": {"type": "string", "enum": ["true", "false", "unresolved"]}, "quote": {"type": "string", "maxLength": 400}}}}
    plan = tm.PLAN_SCHEMA
    return {"type": "object", "additionalProperties": False, "required": ["conditions", *plan["required"]],
            "properties": {"conditions": cond, **plan["properties"]}}


def run_col(t, run, texts, material):
    tm, system, base = material
    res, _u, err = B.chat([{"role": "system", "content": base + "\n\n" + COL_TASK}, {"role": "user", "content": "CASE:\n" + texts[t]["text"]}],
                          col_schema(tm, system), "executed_plan", run, t, "COL_THEFT", max_tokens=6000)
    return {"plan": tm._ids({k: res[k] for k in ("requests", "holds", "questions")}) if res else None, "error": err, "calls": 1}


REACT_THEFT_SYSTEM = B.REACT_SYSTEM.replace("for a legal-expenses insurer's tenancy cases", "for a household insurer's theft claims") \
    .replace('- Choose the workflow whose applies_when matches the dispute ("family"); use "unsupported" if none does.',
             '- The workflow is household_theft; set "family" to "".')


def run_react(t, run, texts, wf, max_turns=12):
    wfs = {"household_theft": wf}
    files = {"message.txt": {"text": texts[t]["text"], "role": "claim"}}
    tools = B.react_tools(wfs, files)
    doc_ids = sorted(d["id"] for d in wf["documents"])
    system = REACT_THEFT_SYSTEM.format(workflows=f"- household_theft: {wf['title']}")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": "New case. Files: message.txt (claim).\n\nmessage.txt:\n" + texts[t]["text"]}]
    schema = B.react_schema(doc_ids)
    schema["properties"]["checklist"]["maxItems"] = 40
    trace = []
    for turn in range(max_turns):
        if turn == max_turns - 1 and trace:
            messages.append({"role": "user", "content": "This is your last turn: submit now."})
        res, _u, err = B.chat(messages, schema, "react_turn", run, t, "REACT_THEFT", max_tokens=4000)
        if res is None:
            return {"plan": None, "error": err, "calls": turn + 1}
        trace.append({k: res[k] for k in ("thought", "action", "argument")})
        if res["action"] == "submit":
            pick = lambda d: sorted({r["document"] for r in res["checklist"] if r["decision"] == d})
            return {"plan": {"requests": pick("request"), "holds": pick("hold")}, "error": None, "calls": turn + 1, "ids": True}
        obs = tools[res["action"]](res["argument"])
        messages.append({"role": "assistant", "content": json.dumps(res, ensure_ascii=False)})
        messages.append({"role": "user", "content": f"Observation (turn {turn + 1} of {max_turns}):\n{obs}"})
    return {"plan": None, "error": "no submit within 12 turns", "calls": max_turns}


def majority(plans):
    ok = [p or {"requests": [], "holds": []} for p in plans]
    n = len(ok)
    req = Counter(d for p in ok for d in p.get("requests", []))
    rh = Counter(d for p in ok for d in set(p.get("requests", [])) | set(p.get("holds", [])))
    requests = sorted(d for d, c in req.items() if c > n / 2)
    return {"requests": requests, "holds": sorted(d for d, c in rh.items() if c > n / 2 and d not in requests), "questions": [], "deferred": False}


def names(plan):
    """Workflow need ids (d07) -> catalogue names, as run_theft maps the product's plans."""
    from theft_data import doc_ids
    inv = {v.lower(): k for k, v in doc_ids().items()}
    return None if plan is None else {**plan, "requests": sorted(inv.get(d, d) for d in plan["requests"]), "holds": sorted(inv.get(d, d) for d in plan["holds"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", choices=["col", "react", "samples", "offline"])
    ap.add_argument("--kind", default="theft")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--k", type=int, default=1)
    ap.add_argument("--cap", type=float, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--product-label", default=None)
    a = ap.parse_args()
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    if a.arm == "offline":
        return offline(out, a.product_label)
    assert a.cap is not None
    jobs, fn = [], None
    if a.arm in ("col", "react"):
        texts, ids = theft_texts()
        material = theft_material() if a.arm == "col" else json.loads((THEFT_WF / "household_theft.json").read_text())
        name = "COL" if a.arm == "col" else "REACT"
        jobs = [(t, r) for r in range(a.k) for t in ids if f"{name}|{t}|{r}" not in out]
        fn = (lambda t, r: run_col(t, r, texts, material)) if a.arm == "col" else (lambda t, r: run_react(t, r, texts, material))
        store, key = out, lambda t, r: f"{name}|{t}|{r}"
    else:
        path = rp.RUNS / f"samples_{a.kind}_gpt-6-luna_fresh.json"
        store = json.loads(path.read_text()) if path.exists() else {}
        if a.kind == "theft":
            texts, ids = theft_texts()
            material = theft_material()
            fn = lambda t, i: {"plan": rpack_sample(t, i, texts, material)}
        else:
            import tenancy_fresh as F
            import tenancy_methods as s1
            import tenancy_v2 as t2
            ids, system = F.claim_ids("test"), t2.system_v2(t2.B1V2_TASK, t2.pack_for(F))

            def fn(c, i):
                res, _u, err = B.chat([{"role": "system", "content": system}, {"role": "user", "content": t2.case_block(F, c)}],
                                      s1.B1_SCHEMA, "evidence_plan", i, c, "B1V2P_SAMPLE")
                return {"plan": s1._plan_from_decisions(res, "documents") if res else None, "error": err}
        first = 3  # samples 0-2 are the cached runs of the earlier designs
        jobs = [(t, i) for i in range(first, first + a.n * a.runs) for t in ids if f"{t}|{i}" not in store]
        key = lambda t, i: f"{t}|{i}"
        OUT_S = path
    print(f"{len(jobs)} to do; ledger {rp.spent('gpt-6-luna'):.4f}", flush=True)
    with ThreadPoolExecutor(a.workers) as pool:
        futs = {pool.submit(lambda t, r: None if rp.spent("gpt-6-luna") >= a.cap else fn(t, r), t, r): (t, r) for t, r in jobs}
        for f in as_completed(futs):
            t, r = futs[f]
            try:
                res = f.result()
            except Exception as e:
                res = {"plan": None, "error": f"{type(e).__name__}: {e}"}
            if res is None:
                continue
            store[key(t, r)] = res
            (OUT if a.arm in ("col", "react") else OUT_S).write_text(json.dumps(store, indent=1, ensure_ascii=False))
    print(f"ledger {rp.spent('gpt-6-luna'):.4f}", flush=True)


def offline(out, product_label):
    """SC3 over the cached Rpack runs; two-valued (unresolved = false) from the product's recorded facts."""
    cp4 = json.loads((TMIS / "runs" / "v2" / "cp4" / "plans_theft_gpt-6-luna_fresh_reviewed.json").read_text())
    texts, ids = theft_texts()
    for t in ids:
        sc = majority([(cp4.get(f"Rpack|{t}|{r}") or {}).get("plan") for r in range(3)])
        out[f"SC3|{t}|0"] = {"plan": sc, "calls": 0}
    if product_label:
        sys.path.insert(0, "/home/user/work/casepath-sync-c-r3/casepath-internal")
        from casepath.process import workflows as W
        wf = json.loads((THEFT_WF / "household_theft.json").read_text())
        prod = json.loads((rp.RUNS / f"plans_theft_gpt-6-luna_fresh_{product_label}.json").read_text())
        for k, e in prod.items():
            _, t, r = k.split("|")
            extra = e.get("product_extra") or {}
            facts = {f: x["value"] for f, x in (extra.get("facts") or {}).items()
                     if (x["status"] == "established" and x.get("verdict") == "accepted") or x["status"] == "presumed"}
            for f in wf["facts"]:
                if facts.get(f["id"]) is None and f["type"] == "boolean":
                    facts[f["id"]] = False
            ev = W.evaluate(wf, facts, {}, checked=True)
            plan = {"requests": sorted(x["document"] for x in ev["documents"] if x["required"] == "yes" and x["status"] in {"missing", "unusable"}),
                    "holds": sorted(x["document"] for x in ev["documents"] if x["required"] == "depends")}
            out[f"TWO_F|{t}|{r}"] = {"plan": names(plan), "calls": 0}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("offline theft arms written", len(out))


if __name__ == "__main__":
    main()
