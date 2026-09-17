"""Two-tier evidence planning over a source-induced process graph.

Unresolved branch -> acquire evidence that resolves the branch.
Active branch     -> acquire evidence/documents satisfying active requirements.
Inactive branch   -> acquire neither.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import case_interpreter_v1 as ci
from . import evidence_refinement_v1 as er
from . import obligation_compiler_v1 as oc
from . import state_refinement_v1 as sr

CONTRACT = "casepath.two-tier-evidence-planner/1.0.0"


def _resolver_capabilities(graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    out = []
    for edge in graph.get("transitions") or []:
        condition = edge.get("condition")
        if not condition:
            continue
        out.append({
            "capability_id": f"resolver.{edge['edge_id']}",
            "edge_id": edge["edge_id"],
            "source_node_id": edge.get("source_node_id"),
            "target_node_id": edge.get("target_node_id"),
            "must_show": f"whether the following process condition holds in this case: {condition}",
            "condition": condition,
            "from_propositions": list(edge.get("supported_by") or []),
        })
    return out
def _map_all(capabilities: Sequence[Mapping[str, Any]], catalogue: Sequence[str], call) -> list[dict[str, Any]]:
    reqs: list[dict[str, Any]] = []
    for i in range(0, len(capabilities), 12):
        mapped = oc.map_documents(capabilities[i:i + 12], catalogue, call)
        if mapped.get("problems"):
            raise ValueError(f"document mapping problems: {mapped['problems']}")
        reqs.extend(mapped["requirements"])
    return reqs


def prepare(refined_graph: Mapping[str, Any], catalogue: Sequence[str], call) -> dict[str, Any]:
    compiled = er.compiled_rules(refined_graph) + sr.compiled_rules(refined_graph)
    requirement_caps = [
        cap
        for block in compiled
        for fact in block.get("facts") or []
        for cap in fact.get("capabilities") or []
    ]
    resolvers = _resolver_capabilities(refined_graph)
    all_caps = requirement_caps + resolvers
    requirements = _map_all(all_caps, catalogue, call)
    return {
        "contract": CONTRACT,
        "compiled": compiled,
        "resolvers": resolvers,
        "requirements": requirements,
        "catalogue": list(catalogue),
    }


def _routes(requirements: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {r["capability_id"]: list(r.get("routes") or []) for r in requirements}
def plan_case(*, graph: Mapping[str, Any], propositions: Mapping[str, Mapping[str, Any]],
              case: Mapping[str, str], prepared: Mapping[str, Any], held: Sequence[str], call) -> dict[str, Any]:
    decided = ci.decide(graph, case, call)
    state = ci.activate(graph, decided["verdicts"])
    chains = oc.build_chains(
        graph, state, prepared["compiled"], prepared["requirements"], propositions
    )
    held_set = set(held)
    active_requirement_chains = [
        {**ch, "purpose": "satisfy_active_requirement"}
        for ch in chains["chains"]
        if ch.get("activation") == "active"
    ]

    by_route = _routes(prepared["requirements"])
    resolver_chains = []
    for cap in prepared["resolvers"]:
        verdict = decided["verdicts"].get(cap["edge_id"], {}).get("verdict", "unresolved")
        parent_state = state.get(cap.get("source_node_id"), "unresolved")
        if verdict != "unresolved" or parent_state == "inactive":
            continue
        for route in by_route.get(cap["capability_id"], []):
            resolver_chains.append({
                "document_types": list(route.get("document_types") or []),
                "route_id": route.get("route_id"),
                "capability_id": cap["capability_id"],
                "must_show": cap["must_show"],
                "fact_id": f"resolver.{cap['edge_id']}",
                "fact": cap["condition"],
                "only_if": None,
                "node_id": cap.get("source_node_id"),
                "target_node_id": cap.get("target_node_id"),
                "activation": parent_state,
                "authorities": list(cap.get("from_propositions") or []),
                "propositions": list(cap.get("from_propositions") or []),
                "fault": None,
                "purpose": "resolve_process_state",
            })
    all_chains = active_requirement_chains + resolver_chains
    grouped: dict[str, dict[str, Any]] = {}
    for ch in all_chains:
        docs = [d for d in ch.get("document_types") or [] if d not in held_set]
        if not docs:
            continue
        key = "+".join(sorted(ch.get("document_types") or []))
        item = grouped.setdefault(key, {
            "document_types": list(ch.get("document_types") or []),
            "still_missing": docs,
            "justified_by": [],
            "purposes": set(),
        })
        item["purposes"].add(ch["purpose"])
        item["justified_by"].append({
            "purpose": ch["purpose"],
            "node_id": ch.get("node_id"),
            "target_node_id": ch.get("target_node_id"),
            "fact": ch.get("fact"),
            "must_show": ch.get("must_show"),
            "authorities": ch.get("authorities") or [],
        })
    requests = []
    for item in grouped.values():
        item["purposes"] = sorted(item["purposes"])
        requests.append(item)

    resolver_requests = [r for r in requests if "resolve_process_state" in r["purposes"]]
    active_requests = [r for r in requests if "satisfy_active_requirement" in r["purposes"]]
    next_action = None
    if resolver_requests:
        ranked = sorted(
            resolver_requests,
            key=lambda r: (-len(r["justified_by"]), len(r["still_missing"]), r["still_missing"]),
        )
        next_action = {
            "type": "resolve_process_state",
            "request": ranked[0],
            "why": "This evidence resolves an open process condition before branch-specific obligations are requested.",
        }
    elif active_requests:
        ranked = sorted(active_requests, key=lambda r: (-len(r["justified_by"]), len(r["still_missing"]), r["still_missing"]))
        next_action = {
            "type": "satisfy_active_requirement",
            "request": ranked[0],
            "why": "This evidence satisfies an obligation on the active process path.",
        }
    return {
        "contract": CONTRACT,
        "requests": requests,
        "documents": sorted({d for r in requests for d in r["still_missing"]}),
        "next_action": next_action,
        "activation": state,
        "predicate_verdicts": decided["verdicts"],
        "resolver_chains": resolver_chains,
        "active_requirement_chains": active_requirement_chains,
        "evidence_gaps": chains["evidence_gaps"],
        "counts": {
            "requests": len(requests),
            "resolver_requests": len(resolver_requests),
            "active_requirement_requests": len(active_requests),
            "resolver_chains": len(resolver_chains),
            "active_requirement_chains": len(active_requirement_chains),
            "evidence_gaps": len(chains["evidence_gaps"]),
        },
    }
