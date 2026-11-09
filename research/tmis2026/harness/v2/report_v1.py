"""Run only AFTER induce.py has written and hashed its output: how V1 treated the five rules that Study 1
traced to wrong changes (named by the coordinator), and how many other rules it changed or quarantined."""
import hashlib, json
from pathlib import Path
P = Path(__file__).resolve().parent / "packs"
digest = json.loads((P / "theft_v2_pack.sha256").read_text())
for name, h in digest.items():
    assert hashlib.sha256((P / name).read_bytes()).hexdigest() == h, name
FIVE = ["overlay_rule_074", "overlay_rule_084", "overlay_rule_010", "overlay_rule_042", "overlay_rule_003"]
prov = json.loads((P / "theft_v2_provenance.json").read_text())
pack = json.loads((P / "theft_v2_pack.json").read_text())
logs = {l["rule_id"]: l for l in prov["rules"]}
out = {"five": {}, "others": {}}
for rid in FIVE:
    l = logs[rid]
    out["five"][rid] = {"first_verdict": l["verify"]["result"]["verdict"],
                        "issues": [i["kind"] for i in l["verify"]["result"]["issues"]],
                        "applied": [(o["op"], o.get("capability_id"), o.get("document_type") or o.get("proposition_id")) for o in l.get("applied_operations", [])],
                        "rejected": [(o["op"], o["rejected"]) for o in l.get("rejected_operations", [])],
                        "reverify": [r["result"]["verdict"] if r["result"] else None for r in l.get("reverify", [])],
                        "status": l["status"], "change": l["change"], "after": l.get("after")}
others = [l for r, l in logs.items() if r not in FIVE]
out["others"] = {"n": len(others), "changed_and_admitted": sum(l["status"] == "admitted" and l["change"] == "repaired" for l in others),
                 "quarantined": sum(l["status"] == "quarantined" for l in others),
                 "changed_any": sum(bool(l.get("applied_operations")) for l in others),
                 "quarantined_conditional": sum(l["status"] == "quarantined" and any(f["condition"] != "none (always applies)" for f in l["before"][0]["facts"]) for l in others)}
print(json.dumps(out, indent=1, ensure_ascii=False))
(P / "theft_v2_report_five.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
