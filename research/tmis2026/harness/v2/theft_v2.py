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
import match
import llm
import theft_methods as tm
import verify as v3

PACK = json.loads((common.PACKS / "theft_v2p_pack.json").read_text())  # V1' (no quarantine)
CP_TASK_V3 = tm.VERIFY_TASK.replace("Conditions:\n", "") + "\n" + v3.RULE.replace(
    "in the contradicting quotation field", "in contradicting_quote") + "\nConditions:\n"


class TheftPack:
    """A theft rule pack (V1 output, possibly with V5 repairs) and the CasePath v2 / Rules-in-context designs on it."""

    def __init__(self, pack, judge_all=False):
        self.pack = pack
        self.judge_all = judge_all
        self.quarantined = set(pack["quarantined_rules"])
        self.admitted = [b for b in pack["overlay"]["compiled"] if not self.is_quarantined(b["node_id"])]
        self.req = {r["capability_id"]: r["routes"] for r in pack["requirements"]}
        self.resolvers = [r for r in pack["resolvers"] if not self.is_quarantined(r["rule_id"])]
        used = {f["guard_id"] for b in self.admitted for f in b["facts"] if f.get("guard_id")} | {r["guard_id"] for r in self.resolvers}
        if judge_all:  # V5 arm: judge every guard of the pack so that a readmitted rule can be replayed
            used |= {f["guard_id"] for b in pack["overlay"]["compiled"] for f in b["facts"] if f.get("guard_id")}
            used |= {r["guard_id"] for r in pack["resolvers"]}
        self.guards = {g["guard_id"]: g["statement"] for g in pack["overlay"]["guards"] if g["guard_id"] in used}
        self.note_docs = sorted({d for b in pack["overlay"]["compiled"] if self.is_quarantined(b["node_id"]) for f in b["facts"]
                                 for c in f["capabilities"] for rt in self.req.get(c["capability_id"], []) for d in rt["document_types"]})
        self.cp_schema = tm.obj({"conditions": tm.arr(tm.obj({"guard_id": {"type": "string", "enum": sorted(self.guards)},
                                                              "verdict": {"type": "string", "enum": ["true", "false", "unresolved"]},
                                                              "quote": {"type": "string", "maxLength": 400}}), 90)})

    def is_quarantined(self, node_id):
        return node_id.split(".x")[0] in self.quarantined

    def rules_block(self) -> str:
        ids = tm.IDS
        rules = []
        for rule in self.admitted:
            for fact in rule["facts"]:
                rules.append({"rule": rule["node_id"], "condition": fact.get("guard_id") or "always", "fact": fact["statement"],
                              "evidence": [{"must_show": c["must_show"],
                                            "routes": [[ids[d] for d in rt["document_types"]] for rt in self.req.get(c["capability_id"], [])]}
                                           for c in fact["capabilities"]]})
        confirm = {r["guard_id"]: [[ids[d] for d in rt["document_types"]] for rt in self.req.get(r["capability_id"], [])] for r in self.resolvers}
        return ("EXTRACTED RULES (verified against their cited sources). Conditions:\n" + json.dumps(self.guards, ensure_ascii=False) +
                "\nRules (a rule applies when its condition holds; each evidence item can be met by ANY one route, a route is a set of documents):\n"
                + json.dumps(rules, ensure_ascii=False) +
                "\nRoutes that confirm a condition once it holds:\n" + json.dumps({k: v for k, v in confirm.items() if v}, ensure_ascii=False) +
                ("\nNot admitted (failed verification against their sources; do not request documents on their basis, a handler reviews them): "
                 + json.dumps(sorted(self.quarantined)) if self.quarantined else ""))

    def run_rv2(self, text_id, text, run, memory=""):
        system = (tm.POLICY + "\n\n" + tm.sources_block() + "\n\n" + tm.catalogue_block() + "\n\n" + self.rules_block()
                  + memory + "\n\n" + tm.PLAN_TASK)
        r = llm.call(system=system, user="CASE:\n" + text, schema=tm.PLAN_SCHEMA, schema_name="checklist", run=run,
                     tag={"exp": "v2-theft", "method": "Rv2p" + ("+mem" if memory else ""), "case": text_id})
        return {"plan": tm._ids(r["result"]), "error": r["error"]}

    def run_cpv2(self, text_id, text, run, verifier=False):
        """CPv2p (frozen plan): one interpretation call -> V6 admission -> exact execution. verifier=True is the
        development variant with the V3 verifier."""
        cond_text = json.dumps(self.guards, ensure_ascii=False)
        interp = llm.call(system=tm.POLICY + "\n\n" + tm.CP_TASK + cond_text, user="CASE:\n" + text, schema=self.cp_schema,
                          schema_name="casepath_conditions", run=run, tag={"exp": "v2-theft", "method": "CPv2p-interpret", "case": text_id},
                          max_tokens=6000)
        out = {"interpret_error": interp["error"], "verify_error": None}
        if not interp["result"]:
            return out
        rows = {}
        for row in interp["result"]["conditions"]:
            rows.setdefault(row["guard_id"], row)
        out["raw_judgments"] = {g: {"verdict": r["verdict"], "quote": r["quote"]} for g, r in rows.items()}
        out["judgments_no_verifier"] = self.admit(rows, text, None)
        out["plan_no_verifier"] = self.plan_exact(out["judgments_no_verifier"])
        if not verifier:
            out["judgments"], out["plan"] = out["judgments_no_verifier"], out["plan_no_verifier"]
            return out
        established = {g: r for g, r in rows.items() if r["verdict"] in {"true", "false"}}
        proposal = [{"item_id": f"condition:{g}", "verdict": r["verdict"], "quote": r["quote"]} for g, r in sorted(established.items())]
        ver = llm.call(system=tm.POLICY + "\n\n" + CP_TASK_V3 + cond_text,
                       user="CASE:\n" + text + "\n\nPROPOSAL:\n" + json.dumps(proposal, ensure_ascii=False),
                       schema=v3.THEFT_SCHEMA, schema_name="casepath_verify_v3", run=run,
                       tag={"exp": "v2-theft", "method": "CPv2p-verify", "case": text_id}, max_tokens=4000)
        out["verify_error"] = ver["error"]
        if ver["result"]:
            accepted, diag = v3.effective_theft(ver["result"]["checks"], text)
            out["verifier_diagnostics"] = diag
            out["judgments"] = self.admit(rows, text, accepted)
            out["plan"] = self.plan_exact(out["judgments"])
        return out

    def plan_kleene(self, nu, on_file=frozenset()):
        """Strong Kleene ablation; identical to plan_exact for these flat rules (monotone OR of literals)."""
        return self.plan_exact(nu, on_file)

    def admit(self, rows, text, accepted):
        nu = {}
        for g in self.guards:
            r = rows.get(g)
            v = r["verdict"] if r else "unresolved"
            if v in {"true", "false"}:
                ok_quote = bool(r["quote"]) and match.contains(text, r["quote"])  # V6
                ok_ver = True if accepted is None else accepted.get(f"condition:{g}", True)
                if not (ok_quote and ok_ver):
                    v = "unresolved"
            nu[g] = v
        return nu

    def support(self, nu, on_file=frozenset()):
        """document -> [(condition verdict, origin)] for the chosen route of every evidence item containing it."""
        support = {}

        def add(routes, condition, origin):
            if routes:
                chosen = min(routes, key=lambda rt: tm._route_key(rt, on_file))
                for d in chosen["document_types"]:
                    support.setdefault(d, []).append((condition, origin))

        for rule in self.admitted:
            for fact in rule["facts"]:
                g = fact.get("guard_id")
                cond = nu.get(g, "unresolved") if g else "true"
                for cap in fact["capabilities"]:
                    add(self.req.get(cap["capability_id"], []), cond, {"rule": rule["node_id"], "guard": g, "capability": cap["capability_id"]})
        for res in self.resolvers:
            add(self.req.get(res["capability_id"], []), nu.get(res["guard_id"], "unresolved"),
                {"rule": res["rule_id"], "guard": res["guard_id"], "capability": res["capability_id"], "confirms": True})
        return support

    def plan_exact(self, nu, on_file=frozenset()):
        state = {d: tm._kor([c for c, _ in rows]) for d, rows in self.support(nu, on_file).items()}
        return {"requests": sorted(d for d, v in state.items() if v == "true" and d not in on_file),
                "holds": sorted(d for d, v in state.items() if v == "unresolved" and d not in on_file),
                "questions": sorted(g for g, v in nu.items() if v == "unresolved"),
                "handler_notes": self.note_docs, "mode": "exact (monotone disjunction of literals)"}


DEFAULT = TheftPack(PACK)
GUARDS = DEFAULT.guards


def run_rv2(text_id, text, run):
    return DEFAULT.run_rv2(text_id, text, run)


def run_cpv2(text_id, text, run):
    return DEFAULT.run_cpv2(text_id, text, run)


def run_r(text_id, text, run):
    o = tm.run_rules(text_id, text, run)
    return {"plan": o["plan"], "error": o["raw"]["error"]}


def run_cpv1(text_id, text, run):
    o = tm.run_casepath(text_id, text, run)
    res = {"interpret_error": o["interpret"]["error"], "verify_error": (o["verify"] or {}).get("error")}
    if o.get("judgments"):
        res.update(judgments=o["judgments"], plan=tm.plan(o["judgments"]))
    return res


DESIGNS = {"CPv2p": run_cpv2, "Rv2p": run_rv2, "R": run_r, "CPv1": run_cpv1}
