"""Tenancy designs for Study 2, on any data module with the tenancy_data interface.

CPv2  CasePath v2: interpretation (same prompt as v1 plus the v2 pack and its silence clause) ->
      V3 evidence-bearing verification -> product admission (validate_interpretation) ->
      V2 presumptions for uncited unresolved facts -> product compilation -> V4 exact deferral.
B1v2  Rules in context, same pack: Study 1's B1 with the v2 pack and the identical silence clause.
CPv1  CasePath v1 (Study 1): identical requests to Study 1's CP; plan (strong Kleene) and plan_exact.
B1    Rules in context, original pack (Study 1's B1, identical requests).
For the original data the CPv1 and B1 requests are byte-identical to Study 1, so cached responses are reused.
"""
from __future__ import annotations

import copy
import json

import common
import llm
import presume
import verify as v3
import tenancy_methods as s1
from casepath_tenancy import _apply_document_reviews, supervaluate, REQUEST_STATES
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS
from casepath_api.autonomous_policy_v1 import (OPERATIONAL_CONDITION_QUESTIONS, REQUIRED_FACTS, compile_process,
                                               proposal_items, validate_interpretation)

PACK = presume.load_pack()

POLICY_V2 = s1.POLICY + """
Judge each fact from the sources as stated above. The admitted silence policy (in the rule packs) then says how a fact
that the claim does not mention at all is treated when the evidence plan is decided; a fact the claim raises but leaves
open is not covered by it and stays unresolved."""


def rules_block_v2(pack=None) -> str:
    pack = pack or PACK
    packs = [{"family": t["domain"], "template_id": t["template_id"], "title": t["title"], "content": t["content"],
              "process_catalog": {k: [{kk: vv for kk, vv in row.items() if kk != "assertion"} for row in rows]
                                  for k, rows in t["process_catalog"].items()}} for t in pack["templates"]]
    silence = {t["domain"]: {"clause_id": t["presumptions"]["clause_id"], "clause": presume.CLAUSE,
                             "presumed_when_unmentioned": t["presumptions"]["verdicts"]} for t in pack["templates"]}
    material = {"rule_packs": packs, "condition_catalog": FAMILY_FLAGS,
                "operational_condition_questions": OPERATIONAL_CONDITION_QUESTIONS,
                "required_facts_by_document": REQUIRED_FACTS, "silence_policy": silence}
    return "ADMITTED RULES (identical for every claim):\n" + json.dumps(material, ensure_ascii=False, sort_keys=True)


def system_v2(task: str, pack=None, memory: str = "") -> str:
    return POLICY_V2 + "\n\n" + rules_block_v2(pack) + memory + "\n\n" + task


def case_block(D, claim_id: str) -> str:
    rows = [{k: s[k] for k in ("artifact_id", "file_name", "media_type", "role", "text", "complete")}
            for s in D.sources(claim_id)]
    return "CLAIM SOURCES:\n" + json.dumps({"claim_id": claim_id, "sources": rows}, ensure_ascii=False)


B1V2_TASK = s1.B1_TASK + """
Apply the silence policy: a condition the claim does not mention at all takes its presumed value; a condition the claim
raises but leaves open is unresolved (hold its documents and ask)."""
CPV2_INTERPRET_TASK = s1.CP_INTERPRET_TASK + """
Report a condition the claim does not mention at all as unresolved with no citations; the engine applies the silence
policy to it. Cite whatever the claim says about a condition, even when it leaves the condition open."""
CPV2_VERIFY_TASK = s1.CP_VERIFY_TASK + "\n" + v3.RULE


def _tag(design, claim_id, step=None):
    return {"exp": "v2-tenancy", "method": design + (f"-{step}" if step else ""), "case": claim_id}


# ---------------------------------------------------------------- plans
def handoff(reason):
    return {"family": None, "requests": [], "holds": [], "established": [], "questions": [], "presumptions": [],
            "deferred": True, "deferral_reason": reason}


def plan_v2(D, claim_id, verified, raw_proposal, srcs, pack=None):
    pack = pack or PACK
    verified, records = presume.apply(verified, raw_proposal, pack)
    graph, _f, _o = compile_process(pack, claim_id, verified)
    graph = _apply_document_reviews(graph, verified, srcs)
    sv = supervaluate(graph)
    docs = sv["states"]
    return {"family": verified["category"]["family"], "document_states": docs, "mode": sv["mode"],
            "requests": sorted(k for k, v in docs.items() if v in REQUEST_STATES),
            "holds": sorted(k for k, v in docs.items() if v == "held_behind_question"),
            "established": sorted(k for k, v in docs.items() if v == "established"),
            "questions": sv["questions"], "presumptions": records, "deferred": False}


def run_cpv2(D, claim_id, run, pack=None):
    PACK_ = pack or PACK
    srcs = D.sources(claim_id)
    interp = llm.call(system=system_v2(CPV2_INTERPRET_TASK, pack), user=case_block(D, claim_id), schema=s1.CP_INTERPRET_SCHEMA,
                      schema_name="casepath_interpret", run=run, tag=_tag("CPv2", claim_id, "interpret"))
    out = {"interpret_error": interp["error"], "verify_error": None, "plan": None}
    if not interp["result"]:
        return out
    proposal = {**interp["result"], "steps": [], "knowledge_candidates": []}
    try:
        items = list(proposal_items(proposal))
    except ValueError as error:
        out["plan"] = handoff(str(error))
        return out
    payload = json.dumps({"context": json.loads(case_block(D, claim_id).split("\n", 1)[1]), "proposal": interp["result"],
                          "item_ids": items}, ensure_ascii=False)
    ver = llm.call(system=system_v2(CPV2_VERIFY_TASK, pack), user="VERIFICATION INPUT:\n" + payload, schema=v3.TENANCY_SCHEMA,
                   schema_name="casepath_verify_v3", run=run, tag=_tag("CPv2", claim_id, "verify"))
    out["verify_error"] = ver["error"]
    if not ver["result"]:
        return out
    rows = {f"condition:{r['flag']}": r for r in interp["result"]["conditions"]}
    checks, diag = v3.effective_tenancy(ver["result"], rows, srcs)
    out["verifier_diagnostics"] = diag
    out["judgments"] = {"family": interp["result"]["category"]["family"],
                        "conditions": {x["flag"]: {"verdict": x["verdict"], "cited": bool(x["citations"])} for x in interp["result"]["conditions"]},
                        "verifier": {x["item_id"]: x["accepted"] for x in ver["result"]["checks"]},
                        "family_supported": ver["result"]["family_supported"]}
    try:
        verified = validate_interpretation(PACK_, srcs, proposal, checks)
        out["replay"] = {"proposal": proposal, "verified": verified}
        out["plan"] = plan_v2(D, claim_id, verified, proposal, srcs, PACK_)
    except ValueError as error:
        out["plan"] = handoff(str(error))
    # Ablations without extra calls: v2 without the verifier; v2 without presumptions.
    try:
        allok = {"family_supported": True, "issues": [], "checks": [{"item_id": i, "accepted": True, "reason": ""} for i in items]}
        out["plan_no_verifier"] = plan_v2(D, claim_id, validate_interpretation(PACK_, srcs, proposal, allok), proposal, srcs, PACK_)
    except ValueError as error:
        out["plan_no_verifier"] = handoff(str(error))
    try:
        verified = validate_interpretation(PACK_, srcs, proposal, checks)
        graph, _f, _o = compile_process(PACK_, claim_id, verified)
        graph = _apply_document_reviews(graph, verified, srcs)
        sv = supervaluate(graph)
        out["plan_no_presumption"] = {"family": verified["category"]["family"], "deferred": False,
                                      "requests": sorted(k for k, v in sv["states"].items() if v in REQUEST_STATES),
                                      "holds": sorted(k for k, v in sv["states"].items() if v == "held_behind_question")}
    except ValueError as error:
        out["plan_no_presumption"] = handoff(str(error))
    return out


def run_b1v2(D, claim_id, run, pack=None, memory=""):
    r = llm.call(system=system_v2(B1V2_TASK, pack, memory), user=case_block(D, claim_id), schema=s1.B1_SCHEMA, schema_name="evidence_plan",
                 run=run, tag=_tag("B1v2" + ("+mem" if memory else ""), claim_id))
    return {"plan": s1._plan_from_decisions(r["result"], "documents") if r["result"] else None, "error": r["error"]}


def run_b1(D, claim_id, run):
    r = llm.call(system=s1.system_prompt(s1.B1_TASK), user=case_block(D, claim_id), schema=s1.B1_SCHEMA,
                 schema_name="evidence_plan", run=run, tag=_tag("B1", claim_id))
    return {"plan": s1._plan_from_decisions(r["result"], "documents") if r["result"] else None, "error": r["error"]}


def run_cpv1(D, claim_id, run):
    """Study 1's CP with exact deferral as a variant (identical requests)."""
    from casepath_tenancy import casepath_plan, casepath_plan_exact
    srcs = D.sources(claim_id)
    interp = llm.call(system=s1.system_prompt(s1.CP_INTERPRET_TASK), user=case_block(D, claim_id), schema=s1.CP_INTERPRET_SCHEMA,
                      schema_name="casepath_interpret", run=run, tag=_tag("CPv1", claim_id, "interpret"))
    out = {"interpret_error": interp["error"], "verify_error": None, "plan": None}
    if not interp["result"]:
        return out
    proposal = {**interp["result"], "steps": [], "knowledge_candidates": []}
    try:
        items = list(proposal_items(proposal))
    except ValueError as error:
        out["plan"] = out["plan_exact"] = handoff(str(error))
        return out
    payload = json.dumps({"context": json.loads(case_block(D, claim_id).split("\n", 1)[1]), "proposal": interp["result"],
                          "item_ids": items}, ensure_ascii=False)
    ver = llm.call(system=s1.system_prompt(s1.CP_VERIFY_TASK), user="VERIFICATION INPUT:\n" + payload,
                   schema=s1.VERIFY_SCHEMA, schema_name="casepath_verify", run=run, tag=_tag("CPv1", claim_id, "verify"))
    out["verify_error"] = ver["error"]
    if ver["result"]:
        out["plan"] = casepath_plan(claim_id, proposal, ver["result"], srcs)
        out["plan_exact"] = casepath_plan_exact(claim_id, proposal, ver["result"], srcs)
    return out


DESIGNS = {"CPv2": run_cpv2, "B1v2": run_b1v2, "CPv1": run_cpv1, "B1": run_b1}
