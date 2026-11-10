"""Load a reviewed theft rules file (format of /home/user/work/rule_review/rules.json, see its schema.md) as a pack.

The result has the structure theft_v2.TheftPack expects (overlay.compiled / guards / rules, requirements, resolvers,
quarantined_rules = []), so CasePath (CPv2p) and Rules in context (Rv2p) run on it unchanged. Conditions:
- a rule's condition with an unchanged text keeps its original guard id;
- changed text -> a new guard '<guard_id>.rev-<sha8>' (a new statement the interpreter judges);
- a new condition (guard_id null) -> '<rule_id as guard>.rev-<sha8>';
- every guard present in the pack is judged (load with TheftPack(pack, judge_all=True)).
No model calls.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import common

PREP = json.loads((common.REPO / "data" / "casepath-theft-pairs" / "representation" / "PREPARED.json").read_text())
ORIGINAL_GUARDS = {g["guard_id"]: g["statement"] for g in PREP["overlay"]["guards"]}


def _guard_id(rule_id, condition):
    text = condition["text"].strip()
    gid = condition.get("guard_id")
    if gid and ORIGINAL_GUARDS.get(gid) == text:
        return gid
    stem = gid or rule_id.replace("overlay_rule", "overlay_guard")
    return f"{stem}.rev-{hashlib.sha256(text.encode()).hexdigest()[:8]}"


def load(path) -> dict:
    data = json.loads(Path(path).read_text())
    compiled, guards, rules, requirements, resolvers = [], {}, [], [], []
    for rule in sorted(data["rules"], key=lambda r: r["rule_id"]):
        rid = rule["rule_id"]
        cond = rule.get("condition")
        gid = None
        if cond:
            gid = _guard_id(rid, cond)
            guards[gid] = {"exclusive_group": None, "guard_id": gid, "statement": cond["text"].strip(),
                           "support": "supported", "supported_by": list(cond.get("cited", []))}
        facts = []
        for f in rule["facts"]:
            facts.append({"fact_id": f["fact_id"], "statement": f["statement"], "guard_id": gid,
                          "from_propositions": list(f.get("cited", [])), "node_id": rule.get("process_node"),
                          "capabilities": [{"capability_id": e["capability_id"], "must_show": e["must_show"],
                                            "from_propositions": list(e.get("cited", []))} for e in f["evidence"]]})
            for e in f["evidence"]:
                requirements.append({"capability_id": e["capability_id"],
                                     "routes": [{"route_id": rt["route_id"], "document_types": list(rt["documents"]),
                                                 "why": rt.get("why", "")} for rt in e["routes"]]})
        compiled.append({"node_id": rid, "problems": [], "facts": facts})
        rules.append({"rule_id": rid, "condition": cond["text"].strip() if cond else "", "guard_id": gid,
                      "condition_supported_by": list(cond.get("cited", [])) if cond else [],
                      "requirement": rule.get("title", ""), "requirement_kind": rule.get("requirement_kind"),
                      "parent_node_id": rule.get("process_node"), "supported_by": [], "facts": facts})
        ce = rule.get("confirming_evidence")
        if ce and gid:
            resolvers.append({"capability_id": ce["capability_id"], "guard_id": gid, "rule_id": rid,
                              "must_show": ce["must_show"], "from_propositions": list(ce.get("cited", []))})
            requirements.append({"capability_id": ce["capability_id"],
                                 "routes": [{"route_id": rt["route_id"], "document_types": list(rt["documents"]),
                                             "why": rt.get("why", "")} for rt in ce["routes"]]})
    return {"contract": "casepath.v2.theft-rule-pack/reviewed", "source_file": str(path),
            "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "overlay": {"compiled": compiled, "guards": list(guards.values()), "rules": rules, "non_evidentiary": []},
            "requirements": requirements, "resolvers": resolvers, "catalogue": PREP["catalogue"], "quarantined_rules": []}
