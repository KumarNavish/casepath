"""Independent verification of extracted rules against their own source passages.

For each of the 98 extracted theft rules, the model sees only the rule
(condition, fact, evidence items and document routes) and the passages the rule
cites, and checks whether the condition and the routes are supported. The check
is blind to the benchmark, its references and its known errors.
"""
import json
from concurrent.futures import ThreadPoolExecutor

import llm
import theft_methods as tm
from theft_data import passages

PASS = {p["authority_id"]: p["exact_text"] for p in passages()}
PROPS = {}
for rule in tm.PREP["overlay"]["rules"]:
    pass


def cited(ids):
    out = []
    for pid in sorted(set(ids)):
        aid = pid.split("#")[0]
        if aid in PASS and PASS[aid] not in out:
            out.append(PASS[aid])
    return out


def rule_material(rule):
    facts = []
    ids = []
    for fact in rule["facts"]:
        caps = []
        for cap in fact["capabilities"]:
            ids += cap.get("from_propositions", [])
            caps.append({"must_show": cap["must_show"],
                         "routes": [rt["document_types"] for rt in tm.REQ.get(cap["capability_id"], [])]})
        ids += fact.get("from_propositions", [])
        g = fact.get("guard_id")
        facts.append({"condition": tm.GUARDS.get(g) if g else "none (always applies)", "fact": fact["statement"],
                      "evidence": caps})
    guard_ids = {f.get("guard_id") for f in rule["facts"] if f.get("guard_id")}
    for g in tm.PREP["overlay"]["guards"]:
        if g["guard_id"] in guard_ids:
            ids += g.get("supported_by", [])
    return {"rule_id": rule["node_id"], "facts": facts}, cited(ids)


ISSUE = {"type": "string", "enum": ["none", "condition_broader_than_source", "condition_narrower_than_source",
                                    "condition_missing", "condition_unsupported", "route_joint_where_alternatives",
                                    "route_asks_more_than_source", "route_missing_alternative", "fact_unsupported"]}
SCHEMA = tm.obj({"issues": tm.arr(tm.obj({"kind": ISSUE, "explanation": {"type": "string", "maxLength": 300}}), 6),
                 "verdict": {"type": "string", "enum": ["supported", "flag"]}})
SYSTEM = """You independently verify one evidence rule extracted from Swiss insurance law and policy terms.
Compare the rule ONLY with the cited source passages. Check: (1) whether the rule's condition is what the sources
make the requirement depend on (not broader, not narrower, not missing where the sources make it conditional);
(2) whether each evidence route asks for exactly what the sources require: several documents in one route mean
all are needed together, separate routes mean any one suffices; flag a route that demands documents jointly where
the sources accept either, or that adds a document the sources do not require for this fact. Be conservative:
flag only issues the passages show. Return verdict 'flag' if any issue, else 'supported'."""


def verify(rule, run=0):
    material, texts = rule_material(rule)
    user = "RULE:\n" + json.dumps(material, ensure_ascii=False) + "\n\nCITED SOURCE PASSAGES:\n" + "\n".join(
        f"- {t}" for t in texts)
    r = llm.call(system=SYSTEM, user=user, schema=SCHEMA, schema_name="rule_check", run=run, max_tokens=2000,
                 tag={"exp": "rule_verify", "method": "verifier", "case": rule["node_id"]})
    return rule["node_id"], r["result"], r["error"]


if __name__ == "__main__":
    rules = tm.PREP["overlay"]["compiled"]
    with ThreadPoolExecutor(10) as ex:
        res = list(ex.map(verify, rules))
    out = {rid: {"result": r, "error": e} for rid, r, e in res}
    implicated = {"overlay_rule_074": "route_joint", "overlay_rule_084": "route_more", "overlay_rule_010": "condition_missing",
                  "overlay_rule_042": "condition_broad", "overlay_rule_003": "condition_broad"}
    flagged = {rid for rid, v in out.items() if v["result"] and v["result"]["verdict"] == "flag"}
    print("rules", len(out), "flagged", len(flagged), "errors", sum(1 for v in out.values() if v["error"]))
    for rid, why in implicated.items():
        v = out[rid]["result"]
        print(rid, why, "->", v["verdict"] if v else None, [i["kind"] for i in (v or {}).get("issues", [])])
    json.dump({"implicated": implicated, "results": out}, open("../analysis/rule_verification.json", "w"), indent=1, ensure_ascii=False)
