"""Two-valued execution on CasePath's recorded, admitted judgments (no model calls):
unresolved verdicts read as false (closed world) or as true (eager)."""
import json, sys
from copy import deepcopy
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
from tenancy_data import claim_ids, reference, sources, templates
from tenancy_score import unscored
from tenancy_methods import run_cp
from casepath_tenancy import validate_interpretation, plan_from_verified
import llm
import theft_methods as tm
from theft_data import pairs
from theft_score import score_pair

import os
out = json.loads((HERE / "two_valued.json").read_text()) if (HERE / "two_valued.json").exists() else {}
for tag in [llm.MODEL.split("/")[-1]]:  # one model per process: llm.call binds its model at import
    res = {}
    for mode, fill in (("closed", "false"), ("eager", "true")):
        tp = fp = miss = nR = nP = 0
        for cid in claim_ids("test"):
            R = set(reference(cid)["request_set"]) - unscored(cid)
            for r in range(3):
                o = run_cp(cid, r)  # cached; no new calls
                it, ver = o["interpret"]["result"], (o["verify"] or {}).get("result")
                if not it or not ver:
                    miss += len(R); nR += len(R); continue
                prop = {**it, "steps": [], "knowledge_candidates": []}
                try:
                    v = validate_interpretation(templates(), sources(cid), prop, ver)
                except ValueError:
                    miss += len(R); nR += len(R); continue  # claim deferred: nothing requested
                from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS
                verdicts = {c["flag"]: c for c in v["conditions"]}
                for f in FAMILY_FLAGS[v["category"]["family"]]:
                    c = verdicts.setdefault(f, {"flag": f, "verdict": "unresolved", "summary": "", "citations": []})
                    if c["verdict"] == "unresolved":
                        c["verdict"] = fill
                v["conditions"] = list(verdicts.values())
                pl = plan_from_verified(cid, v, sources(cid))
                P = set(pl["requests"]) - unscored(cid)
                tp += len(P & R); fp += len(P - R); miss += len(R - P); nR += len(R); nP += len(P)
        res[f"tenancy_{mode}"] = {"recall": tp / nR, "unnecessary_rate": fp / nP if nP else 0, "silent_miss_rate": miss / nR,
                                  "fp": fp, "miss": miss, "nR": nR}
    P = json.loads((HERE.parent / "runs" / f"plans_theft_{tag}.json").read_text())
    for mode, fill in (("closed", "false"), ("eager", "true")):
        rows = []
        for p in pairs():
            if p["split"] != "heldout":
                continue
            for r in range(3):
                a, b = P.get(f"CP|{p['off']}|{r}", {}), P.get(f"CP|{p['variant']}|{r}", {})
                if not a.get("judgments") or not b.get("judgments"):
                    continue
                f2 = lambda nu: {g: (fill if v == "unresolved" else v) for g, v in nu.items()}
                rows.append(score_pair(p, tm.plan(f2(a["judgments"])), tm.plan(f2(b["judgments"]))))
        on = [x for x in rows if x["kind"] == "on"]; un = [x for x in rows if x["kind"] == "unresolved"]
        c, w, m = (sum(x[k] for x in on) for k in ("correct", "wrong", "missed"))
        pr = c / (c + w) if c + w else 0; rc = c / (c + m) if c + m else 0
        res[f"theft_{mode}"] = {"wrong": w, "missed": m, "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0,
                                "premature_rate": sum(x["premature"] for x in un) / len(un),
                                "stable_rate": sum(x["stable"] for x in un) / len(un)}
    out[tag] = res
(HERE / "two_valued.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
