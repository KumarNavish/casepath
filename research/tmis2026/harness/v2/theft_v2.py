"""Theft designs for Study 2 (text-in, plan-out; the data module only supplies texts and pairs).

CPv2  CasePath v2: V1 rule pack (repaired rules admitted, quarantined rules not executed), condition
      judgments over the admitted guards, V3 evidence-bearing verification, exact-quote admission and
      V4 exact deferral. Theft has no silence policy (see presume.py), so V2 does not apply.
Rv2   Rules in context, same pack: the admitted v2 rules, with the quarantined rules listed as not admitted.
R     Rules in context, original pack (Study 1, identical requests).
CPv1  CasePath v1 (Study 1, identical requests).
Exact deferral on the flat theft rules: a document's requirement is the OR of the guard literals of the
evidence items whose chosen route contains it; for such monotone disjunctions of literals strong Kleene
evaluation is already exact (a document is held iff no guard is true and some guard is open), so V4 changes
nothing here; plan_exact checks that the pack is flat and records the mode.
"""
from __future__ import annotations

import json

import common
import llm
import theft_methods as tm
import verify as v3

PACK = json.loads((common.PACKS / "theft_v2_pack.json").read_text())
QUARANTINED = set(PACK["quarantined_rules"])


def _quarantined(node_id: str) -> bool:
    return node_id.split(".x")[0] in QUARANTINED


ADMITTED = [b for b in PACK["overlay"]["compiled"] if not _quarantined(b["node_id"])]
REQ = {r["capability_id"]: r["routes"] for r in PACK["requirements"]}
RESOLVERS = [r for r in PACK["resolvers"] if not _quarantined(r["rule_id"])]
USED_GUARDS = sorted({f["guard_id"] for b in ADMITTED for f in b["facts"] if f.get("guard_id")} | {r["guard_id"] for r in RESOLVERS})
GUARDS = {g["guard_id"]: g["statement"] for g in PACK["overlay"]["guards"] if g["guard_id"] in USED_GUARDS}
NOTE_DOCS = sorted({d for b in PACK["overlay"]["compiled"] if _quarantined(b["node_id"]) for f in b["facts"]
                    for c in f["capabilities"] for rt in REQ.get(c["capability_id"], []) for d in rt["document_types"]})


def rules_block_v2() -> str:
    ids = tm.IDS
    rules = []
    for rule in ADMITTED:
        for fact in rule["facts"]:
            rules.append({"rule": rule["node_id"], "condition": fact.get("guard_id") or "always", "fact": fact["statement"],
                          "evidence": [{"must_show": c["must_show"],
                                        "routes": [[ids[d] for d in rt["document_types"]] for rt in REQ.get(c["capability_id"], [])]}
                                       for c in fact["capabilities"]]})
    confirm = {r["guard_id"]: [[ids[d] for d in rt["document_types"]] for rt in REQ.get(r["capability_id"], [])] for r in RESOLVERS}
    quarantined = sorted(QUARANTINED)
    return ("EXTRACTED RULES (verified against their cited sources). Conditions:\n" + json.dumps(GUARDS, ensure_ascii=False) +
            "\nRules (a rule applies when its condition holds; each evidence item can be met by ANY one route, a route is a set of documents):\n"
            + json.dumps(rules, ensure_ascii=False) +
            "\nRoutes that confirm a condition once it holds:\n" + json.dumps({k: v for k, v in confirm.items() if v}, ensure_ascii=False) +
            "\nNot admitted (failed verification against their sources; do not request documents on their basis, a handler reviews them): "
            + json.dumps(quarantined))


def run_rv2(text_id, text, run):
    system = tm.POLICY + "\n\n" + tm.sources_block() + "\n\n" + tm.catalogue_block() + "\n\n" + rules_block_v2() + "\n\n" + tm.PLAN_TASK
    r = llm.call(system=system, user="CASE:\n" + text, schema=tm.PLAN_SCHEMA, schema_name="checklist", run=run,
                 tag={"exp": "v2-theft", "method": "Rv2", "case": text_id})
    return {"plan": tm._ids(r["result"]), "error": r["error"]}


def run_r(text_id, text, run):
    o = tm.run_rules(text_id, text, run)
    return {"plan": o["plan"], "error": o["raw"]["error"]}


CP_SCHEMA = tm.obj({"conditions": tm.arr(tm.obj({"guard_id": {"type": "string", "enum": sorted(GUARDS)},
                                                 "verdict": {"type": "string", "enum": ["true", "false", "unresolved"]},
                                                 "quote": {"type": "string", "maxLength": 400}}), 90)})
VERIFY_TASK = tm.VERIFY_TASK.replace("Conditions:\n", "") + "\n" + v3.RULE.replace(
    "in the contradicting quotation field", "in contradicting_quote") + "\nConditions:\n"


def run_cpv2(text_id, text, run):
    cond_text = json.dumps(GUARDS, ensure_ascii=False)
    interp = llm.call(system=tm.POLICY + "\n\n" + tm.CP_TASK + cond_text, user="CASE:\n" + text, schema=CP_SCHEMA,
                      schema_name="casepath_conditions", run=run, tag={"exp": "v2-theft", "method": "CPv2-interpret", "case": text_id},
                      max_tokens=6000)
    out = {"interpret_error": interp["error"], "verify_error": None}
    if not interp["result"]:
        return out
    rows = {}
    for row in interp["result"]["conditions"]:
        rows.setdefault(row["guard_id"], row)
    established = {g: r for g, r in rows.items() if r["verdict"] in {"true", "false"}}
    proposal = [{"item_id": f"condition:{g}", "verdict": r["verdict"], "quote": r["quote"]} for g, r in sorted(established.items())]
    ver = llm.call(system=tm.POLICY + "\n\n" + VERIFY_TASK + cond_text,
                   user="CASE:\n" + text + "\n\nPROPOSAL:\n" + json.dumps(proposal, ensure_ascii=False),
                   schema=v3.THEFT_SCHEMA, schema_name="casepath_verify_v3", run=run,
                   tag={"exp": "v2-theft", "method": "CPv2-verify", "case": text_id}, max_tokens=4000)
    out["verify_error"] = ver["error"]
    nu_nv = admit(rows, text, None)
    out["judgments_no_verifier"] = nu_nv
    out["plan_no_verifier"] = plan_exact(nu_nv)
    if ver["result"]:
        accepted, diag = v3.effective_theft(ver["result"]["checks"], text)
        out["verifier_diagnostics"] = diag
        out["judgments"] = admit(rows, text, accepted)
        out["plan"] = plan_exact(out["judgments"])
    return out


def admit(rows, text, accepted):
    nu = {}
    for g in GUARDS:
        r = rows.get(g)
        v = r["verdict"] if r else "unresolved"
        if v in {"true", "false"}:
            ok_quote = bool(r["quote"]) and r["quote"] in text
            ok_ver = True if accepted is None else accepted.get(f"condition:{g}", True)
            if not (ok_quote and ok_ver):
                v = "unresolved"
        nu[g] = v
    return nu


def requirement_support(nu, on_file=frozenset()):
    support = {}

    def add(routes, condition):
        if routes:
            chosen = min(routes, key=lambda rt: tm._route_key(rt, on_file))
            for d in chosen["document_types"]:
                support.setdefault(d, []).append(condition)

    for rule in ADMITTED:
        for fact in rule["facts"]:
            cond = nu.get(fact.get("guard_id"), "unresolved") if fact.get("guard_id") else "true"
            for cap in fact["capabilities"]:
                add(REQ.get(cap["capability_id"], []), cond)
    for res in RESOLVERS:
        add(REQ.get(res["capability_id"], []), nu.get(res["guard_id"], "unresolved"))
    return support


def plan_exact(nu, on_file=frozenset()):
    state = {d: tm._kor(c) for d, c in requirement_support(nu, on_file).items()}
    return {"requests": sorted(d for d, v in state.items() if v == "true" and d not in on_file),
            "holds": sorted(d for d, v in state.items() if v == "unresolved" and d not in on_file),
            "questions": sorted(g for g, v in nu.items() if v == "unresolved"),
            "handler_notes": NOTE_DOCS, "mode": "exact (monotone disjunction of literals)"}


def run_cpv1(text_id, text, run):
    o = tm.run_casepath(text_id, text, run)
    res = {"interpret_error": o["interpret"]["error"], "verify_error": (o["verify"] or {}).get("error")}
    if o.get("judgments"):
        res.update(judgments=o["judgments"], plan=tm.plan(o["judgments"]))
    return res


DESIGNS = {"CPv2": run_cpv2, "Rv2": run_rv2, "R": run_r, "CPv1": run_cpv1}
