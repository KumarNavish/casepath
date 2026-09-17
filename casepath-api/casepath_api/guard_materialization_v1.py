"""Deterministically materialize source-grounded textual conditions as first-class guards."""
from __future__ import annotations

import copy
from typing import Any, Mapping

CONTRACT = "casepath.guard-materialization/1.0.0"


def materialize(macro_graph: Mapping[str, Any], refinement_result: Mapping[str, Any]) -> dict[str, Any]:
    if not refinement_result.get("verification", {}).get("ok"):
        raise ValueError("evidence refinement must pass deterministic verification")
    out = copy.deepcopy(macro_graph)
    out["guards"] = []
    for node in out.get("nodes") or []:
        node.setdefault("guard_ids", [])
    guard_ids: set[str] = set()

    def add_guard(gid: str, statement: str, supported_by: list[str]) -> str:
        if gid in guard_ids:
            raise ValueError(f"duplicate guard id {gid}")
        guard_ids.add(gid)
        out["guards"].append({"guard_id": gid, "statement": statement,
                              "supported_by": list(supported_by), "support": "supported",
                              "exclusive_group": None})
        return gid

    for edge in out.get("transitions") or []:
        condition = (edge.get("condition") or "").strip()
        if condition:
            gid = add_guard(f"gm_edge_{edge['edge_id']}", condition, list(edge.get("supported_by") or []))
            edge["guard_id"] = gid
    compiled = []
    rules = list(refinement_result["refinement"].get("rules") or [])
    for i, rule in enumerate(rules, 1):
        nid = f"evidence_rule_v2_{i:03d}"
        supports = sorted(set((rule.get("supported_by") or []) + (rule.get("condition_supported_by") or [])))
        gids: list[str] = []
        condition = (rule.get("condition") or "").strip()
        if condition:
            gids.append(add_guard(f"gm_rule_{i:03d}", condition, list(rule.get("condition_supported_by") or [])))
        out.setdefault("nodes", []).append({"node_id": nid, "label": rule.get("requirement"),
            "kind": "step", "guard_ids": gids, "supported_by": supports, "support": "supported",
            "why": "Evidence-relevant source rule preserved by coverage-constrained refinement."})
        out.setdefault("transitions", []).append({"edge_id": f"gm_ev_{i:03d}",
            "source_node_id": rule["parent_node_id"], "target_node_id": nid,
            "guard_id": gids[0] if gids else None, "supported_by": list(rule.get("condition_supported_by") or rule.get("supported_by") or []),
            "support": "supported"})
        oid = f"gm_o{i:03d}"
        out.setdefault("obligations", []).append({"obligation_id": oid, "node_id": nid, "party": None,
            "statement": rule.get("requirement"), "guard_ids": gids,
            "supported_by": list(rule.get("supported_by") or []), "support": "supported",
            "requirement_kind": rule.get("requirement_kind")})
        facts = []
        for j, fact in enumerate(rule.get("facts") or [], 1):
            caps = []
            fact_id = f"{nid}.f{j:02d}"
            for k, cap in enumerate(fact.get("capabilities") or [], 1):
                caps.append({**cap, "capability_id": f"{fact_id}.c{k:02d}"})
            facts.append({**fact, "fact_id": fact_id, "node_id": nid,
                          "for_obligation_id": oid, "guard_ids": gids, "capabilities": caps})
        compiled.append({"node_id": nid, "facts": facts, "problems": []})

    out["guard_materialization"] = {"contract": CONTRACT, "compiled": compiled,
        "refinement_verification": refinement_result["verification"],
        "non_evidentiary": refinement_result["refinement"].get("non_evidentiary") or []}
    out["contract"] = CONTRACT
    out["grounding_problems"] = verify(out)
    return out


def compiled_rules(graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    return copy.deepcopy(graph.get("guard_materialization", {}).get("compiled") or [])


def verify(graph: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    guards = {g.get("guard_id") for g in graph.get("guards") or []}
    nodes = {n.get("node_id") for n in graph.get("nodes") or []}
    for edge in graph.get("transitions") or []:
        if (edge.get("condition") or "").strip() and not edge.get("guard_id"):
            problems.append(f"condition-bearing transition lacks guard: {edge.get('edge_id')}")
        if edge.get("guard_id") and edge.get("guard_id") not in guards:
            problems.append(f"transition cites unknown guard: {edge.get('edge_id')}")
        if edge.get("source_node_id") not in nodes or edge.get("target_node_id") not in nodes:
            problems.append(f"transition cites unknown node: {edge.get('edge_id')}")
    for node in graph.get("nodes") or []:
        for gid in node.get("guard_ids") or []:
            if gid not in guards:
                problems.append(f"node {node.get('node_id')} cites unknown guard {gid}")
    for obligation in graph.get("obligations") or []:
        for gid in obligation.get("guard_ids") or []:
            if gid not in guards:
                problems.append(f"obligation {obligation.get('obligation_id')} cites unknown guard {gid}")
    fact_ids: list[str] = []
    capability_ids: list[str] = []
    for item in graph.get("guard_materialization", {}).get("compiled") or []:
        for fact in item.get("facts") or []:
            fact_ids.append(fact.get("fact_id"))
            for gid in fact.get("guard_ids") or []:
                if gid not in guards:
                    problems.append(f"fact {fact.get('fact_id')} cites unknown guard {gid}")
            capability_ids.extend(c.get("capability_id") for c in fact.get("capabilities") or [])
    if len(fact_ids) != len(set(fact_ids)):
        problems.append("duplicate materialized fact ids")
    if len(capability_ids) != len(set(capability_ids)):
        problems.append("duplicate materialized capability ids")
    return problems
