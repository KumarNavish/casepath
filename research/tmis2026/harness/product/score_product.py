"""Score the product's tenancy plans next to the cached arms, with the Study 1 (dev12) and Study 2 (fresh) measures,
and attribute every lost or extra document to its cause. No model calls.

    python3 score_product.py --set dev12|fresh [--model gpt-6-luna] [--label sync]
Writes results/score_<set>_<model>[_<label>].json and prints the table. With --label, the labelled product run
(runs/product/plans_tenancy_<model>_<set>_<label>.json) is scored and attributed, beside the as-built row.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(TMIS / "fresh"))
sys.path.insert(0, str(TMIS / "analysis"))
sys.path.insert(0, str(HERE))

RUNS = TMIS / "runs"


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def arm_plans(raw, design, ids, runs):
    out = {}
    for cid in ids:
        out[cid] = [((raw.get(f"{design}|{cid}|{r}") or {}).get("plan")) for r in runs]
    return out


def dev12(model, label=None):
    saved = sys.argv
    sys.argv = [saved[0], model]
    from analyze import summ, tenancy_row
    sys.argv = saved
    import tenancy_data as D
    from tenancy_score import unscored
    from pilot import DEV12
    as_built = load(RUNS / "product" / f"plans_tenancy_{model}_dev12.json")
    arms = {f"PRODUCT as built {model} (k=1)": arm_plans(as_built, "PRODUCT", DEV12, [0])}
    product = as_built
    if label:
        product = load(RUNS / "product" / f"plans_tenancy_{model}_dev12_{label}.json")
        arms[f"PRODUCT {label} {model} (k=1)"] = arm_plans(product, "PRODUCT", DEV12, [0])
    for m, runs in (("gpt-6-luna", [0, 1, 2]), ("gpt-6.1-terra", [0])):
        raw = load(RUNS / "v2" / f"plans_tenancy_{m}_original_dev.json")
        for design in ("CPv2p", "B1v2p"):
            arms[f"{design} {m} (k={len(runs)})"] = arm_plans(raw, design, DEV12, runs)
    table = {}
    for name, plans in arms.items():
        rows = []
        for cid, ps in plans.items():
            R = set(D.reference(cid)["request_set"]) - unscored(cid)
            for p in ps:
                rows.append(tenancy_row(cid, p, R))
        s = summ(rows)
        n = s["n"]
        table[name] = {"claim_runs": n, "requested_share": s["tp"] / s["nR"], "held": s["held"] / n, "handed": s["handed"] / n,
                       "missed": s["miss"] / n, "unnecessary": s["fp"] / n, "premature": None, "silent_skip": None,
                       "strict_unsafe": s["unsafe_strict_per_claim"], "required_per_claim": s["nR"] / n,
                       "failed": s["failed_outputs"]}
    refs = {cid: {"family": D.reference(cid)["family"], "scenario": D.reference(cid)["scenario"],
                  "required": set(D.reference(cid)["request_set"]) - unscored(cid), "held": set(), "on_file": set()}
            for cid in DEV12}
    return table, product, refs


def fresh(model, label=None):
    import study2
    import tenancy_fresh as F
    ids = F.claim_ids("test")
    as_built = load(RUNS / "product" / f"plans_tenancy_{model}_fresh.json")
    arms = {f"PRODUCT as built {model} (k=1)": arm_plans(as_built, "PRODUCT", ids, [0])}
    product = as_built
    if label:
        product = load(RUNS / "product" / f"plans_tenancy_{model}_fresh_{label}.json")
        arms[f"PRODUCT {label} {model} (k=1)"] = arm_plans(product, "PRODUCT", ids, [0])
    for m in ("gpt-6-luna", "gpt-6.1-terra"):
        raw = load(RUNS / "v2" / f"plans_tenancy_{m}_fresh_heldout.json")
        for design in ("CPv2p", "B1v2p"):
            arms[f"{design} {m} (k=3)"] = arm_plans(raw, design, ids, [0, 1, 2])
    table = {}
    for name, plans in arms.items():
        rows = [study2.ten_row(F.reference(cid), p) for cid, ps in plans.items() for p in ps]
        n = len(rows)
        S = lambda k: sum(r[k] for r in rows)
        table[name] = {"claim_runs": n, "requested_share": S("requested") / S("req_now"), "held": S("correct_hold") / n,
                       "held_required_now": S("held_req") / n, "handed": S("handed") / n, "missed": S("missed") / n,
                       "unnecessary": S("unnecessary") / n, "premature": S("premature") / n, "silent_skip": S("silent_skip") / n,
                       "strict_unsafe": S("strict_unsafe") / n, "spurious_hold": S("spurious_hold") / n,
                       "correct_hold_share": S("correct_hold") / S("ref_held") if S("ref_held") else None,
                       "required_now_per_claim": S("req_now") / n, "handoff_runs": S("deferred")}
    refs = {}
    for cid in ids:
        r = F.reference(cid)
        st = r["document_states"]
        refs[cid] = {"family": r["family"], "scenario": r["scenario"], "open_fact": r.get("open_fact"),
                     "required": {d for d, s in st.items() if s in {"required_now", "supplied_insufficient"}},
                     "held": {d for d, s in st.items() if s == "held"},
                     "on_file": {d for d, s in st.items() if s == "supplied_sufficient"}}
    return table, product, refs


def attribute(product, refs, catalogue_dir):
    """Why each reference-required document was not requested, and why each extra request was made."""
    sys.path.insert(0, "/home/user/work/casepath-ui3/casepath-internal")
    from casepath_internal.workflows import Catalogue
    cat = Catalogue.load(catalogue_dir)
    lost, gained, added = Counter(), Counter(), Counter()
    blockers = Counter()
    for cid, ref in refs.items():
        entry = product.get(f"PRODUCT|{cid}|0") or {}
        plan, extra = entry.get("plan"), entry.get("product_extra") or {}
        if plan is None:
            lost["failed run"] += len(ref["required"])
            continue
        if plan.get("deferred"):
            lost["routing: whole claim handed over"] += len(ref["required"] - set(plan["requests"]))
            continue
        if plan["family"] != ref["family"]:
            lost["routing: wrong family"] += len(ref["required"] - set(plan["requests"]))
            gained["routing: wrong family"] += len(set(plan["requests"]) - ref["required"] - ref["held"])
            continue
        wf = cat.get(plan["family"])
        step_of = {}
        for s in wf["steps"]:
            for d in s.get("documents", []):
                step_of.setdefault(d, set()).add(s["id"])
        reached = set(extra.get("reached") or [])
        facts = extra.get("facts") or {}
        req_flag = {d["id"]: (d.get("required_when") or {}).get("fact") for d in wf["documents"]}
        for d in sorted(ref["required"] - set(plan["requests"])):
            if d in plan["holds"]:
                lost["held behind an open question"] += 1
            elif d in extra.get("on_file", []):
                lost["document finder: judged on file"] += 1
            elif not (step_of.get(d, set()) & reached) and extra.get("waiting_for"):
                for f in extra["waiting_for"]:
                    st = facts.get(f, {})
                    why = ("source checker rejected" if st.get("verdict") == "rejected" else
                           "second reading conflict" if st.get("status") == "conflicting" else
                           "left unknown by the claim reader")
                    blockers[f"{f}: {why}"] += 1
                lost["stop at unknown: step beyond the waiting question"] += 1
            elif not (step_of.get(d, set()) & reached):
                lost["branch not taken: a fact judged against the reference"] += 1
            elif req_flag.get(d) and facts.get(req_flag[d], {}).get("value") is not True:
                lost[f"condition {req_flag[d]} judged false / not accepted"] += 1
            else:
                lost["other"] += 1
        for d in sorted(set(plan["requests"]) - ref["required"]):
            if d in ref["held"]:
                gained["premature: requested a document the reference holds"] += 1
            elif d in ref["on_file"]:
                gained["document finder: supplied sufficient file not accepted"] += 1
            else:
                flag = req_flag.get(d)
                gained[f"condition {flag} judged true against the reference" if flag else "unconditional need the reference does not require"] += 1
        for a in extra.get("agent_added_needs", []):
            added[("statute article" if a["legal_basis"] and re.search(r"Art", a["legal_basis"] or "") else "no article") +
                  f" / {a['required']} / {a['status']}"] += 1
    return {"lost": dict(lost), "gained": dict(gained), "blocking_facts": dict(blockers), "agent_added_needs": dict(added)}


def costs(product):
    calls = [v.get("calls", 0) for v in product.values()]
    tok = [v.get("tokens", {}) for v in product.values()]
    return {"cases": len(calls), "calls_per_case": sum(calls) / max(1, len(calls)),
            "input_tokens_per_case": sum(t.get("input", 0) for t in tok) / max(1, len(tok)),
            "cached_per_case": sum(t.get("cached", 0) for t in tok) / max(1, len(tok)),
            "output_tokens_per_case": sum(t.get("output", 0) for t in tok) / max(1, len(tok)),
            "failed": sum(1 for v in product.values() if v.get("status") != "completed"),
            "handed_over": sum(1 for v in product.values() if (v.get("plan") or {}).get("deferred"))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True, choices=["dev12", "fresh"])
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--label", default=None)
    a = ap.parse_args()
    table, product, refs = dev12(a.model, a.label) if a.set == "dev12" else fresh(a.model, a.label)
    catalogue = HERE / "workflows" / (("original-serial" if a.set == "dev12" else "fresh-serial") + ("-sync" if a.label else ""))
    att = attribute(product, refs, catalogue)
    ledger = RUNS / "product" / f"ledger_dev_{a.model}.jsonl"
    cases = {f"PRODUCT|{c}|0" for c in refs}
    usd = 0.0
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            row = json.loads(line)
            if f"PRODUCT|{row['case']}|{row['run']}" in cases:
                usd += row["usd"] or 0
    c = costs({k: v for k, v in product.items() if k in cases})
    c["usd_total"], c["usd_per_case"] = usd, usd / max(1, c["cases"])
    out = {"set": a.set, "model": a.model, "table": table, "attribution": att, "cost": c}
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"score_{a.set}_{a.model}{'_' + a.label if a.label else ''}.json").write_text(json.dumps(out, indent=1))
    keys = ["claim_runs", "requested_share", "held", "handed", "missed", "unnecessary", "premature", "silent_skip", "strict_unsafe"]
    print("arm".ljust(36) + " ".join(k[:10].rjust(10) for k in keys))
    for name, row in table.items():
        print(name.ljust(36) + " ".join(("-" if row.get(k) is None else f"{row[k]:.2f}").rjust(10) for k in keys))
    print(json.dumps(att, indent=1))
    print(json.dumps(c, indent=1))


if __name__ == "__main__":
    main()
