"""For each product claim-run on the probe: the router's decision, both structured readings of the defining event (from the
cached model responses of that claim-run), the recorded fact, whether a presumption applied, and the document states.

    python3 diagnose_probe.py [--label p90a] [--all]
No model calls: reads runs/product/plans_..., outcomes_... and the response cache.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent / "runs" / "product"
sys.path.insert(0, str(HERE))
import tenancy_probe as D  # noqa: E402

ROUTING = {"lease_termination_dispute": "termination_received", "rent_increase_dispute": "claim_received"}


def readings(entry, fact):
    """The structured condition readings in call order: [(agent, verdict, value, quote)]."""
    keys, agents, out = [], entry.get("agents") or [], []
    for k in entry.get("keys", []):
        if not keys or keys[-1] != k:
            keys.append(k)
    for i, k in enumerate(keys):
        path = RUNS / "cache" / f"{k}.json"
        if not path.exists():
            continue
        msg = json.loads(json.loads(path.read_text())["body"])["choices"][0]["message"]
        try:
            content = json.loads(msg.get("content") or "")
        except ValueError:
            continue
        if isinstance(content, dict) and "conditions" in content:
            for c in content["conditions"]:
                if c.get("id") == fact:
                    q = c.get("quote") or c.get("quotes") or c.get("citations")
                    out.append((agents[i] if i < len(agents) else "?", c.get("verdict"), c.get("value"), q))
        if isinstance(content, dict) and "facts" in content and i == 0:
            for c in content["facts"]:
                if c.get("fact") == fact:
                    out.append(("router", "value", c.get("value"), c.get("citations")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="p90a")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    plans = json.loads((RUNS / f"plans_tenancy_gpt-6-luna_probe_{a.label}.json").read_text())
    out_dir = RUNS / f"outcomes_tenancy_gpt-6-luna_probe_{a.label}"
    report = []
    for key in sorted(plans, key=lambda k: (D.reference(k.split("|")[1])["probe"]["slug"], k)):
        _, cid, run = key.split("|")
        ref = D.reference(cid)
        entry = plans[key]
        plan = entry.get("plan") or {}
        fact = ROUTING[ref["family"]]
        req, holds = set(plan.get("requests", [])), set(plan.get("holds", []))
        ok = (req == set(ref["request_set"]) and holds - req == set(ref["held_set"]) and not plan.get("deferred"))
        if ok and not a.all:
            continue
        o_path = out_dir / f"{cid}_{run}.json"
        outcome = json.loads(o_path.read_text()) if o_path.exists() else {}
        result = outcome.get("result") or {}
        row = next((f for f in result.get("facts", []) if f["fact"] == fact), None)
        docs = [(d["document"], d["required"], d["status"]) for d in (result.get("evaluation") or {}).get("documents", [])]
        rec = {"key": key, "slug": ref["probe"]["slug"], "kind": ref["probe"]["kind"], "mode": ref["probe"]["mode"], "ok": ok,
               "routing": {"status": (outcome.get("routing") or {}).get("status"),
                           "workflow": ((outcome.get("routing") or {}).get("workflow") or {}).get("id"),
                           "facts": [(f["fact"], f.get("value"), f.get("presumed")) for f in (outcome.get("routing") or {}).get("facts", [])]},
               "readings": readings(entry, fact),
               "fact_row": {k: row.get(k) for k in ("status", "value", "second_value", "readings", "verdict", "by", "agreed",
                                                     "reason_code", "raised_by_one_reading", "presumption", "verdict_reason")
                            if row and k in row} if row else None,
               "fact_quotes": [c.get("quote") for c in (row or {}).get("citations", [])],
               "waiting_for": [w["fact"] for w in (result.get("evaluation") or {}).get("waiting_for", [])],
               "documents": docs, "plan_requests": sorted(req), "plan_holds": sorted(holds),
               "ref_requests": ref["request_set"], "ref_held": ref["held_set"], "status": entry.get("status"), "error": entry.get("error")}
        if rec["fact_row"] and isinstance(rec["fact_row"].get("presumption"), dict):
            rec["fact_row"]["presumption"] = {k: rec["fact_row"]["presumption"].get(k) for k in ("applies", "code", "by")}
        report.append(rec)
        print(json.dumps(rec, ensure_ascii=False))
    (RUNS / f"diagnosis_tenancy_probe_{a.label}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
