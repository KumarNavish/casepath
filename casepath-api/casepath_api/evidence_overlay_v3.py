"""Source-grounded evidence overlay for process-first document planning.

A macro process graph explains where a requirement belongs. It does not silently gate
that requirement through unrelated upstream unknowns. Each evidence rule retains its
own source-grounded applicability guard and process-node anchor.
"""
from __future__ import annotations

import copy
from typing import Any, Callable, Mapping, Sequence

from . import case_interpreter_v3 as ci
from . import obligation_compiler_v2 as oc

CONTRACT = "casepath.evidence-overlay/3.0.0"


def materialize(refinement_result: Mapping[str, Any]) -> dict[str, Any]:
    if not refinement_result.get("verification", {}).get("ok"):
        raise ValueError("evidence refinement must pass deterministic verification")
    guards: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    compiled: list[dict[str, Any]] = []
    for index, rule in enumerate(refinement_result["refinement"].get("rules") or [], 1):
        rule_id = f"overlay_rule_{index:03d}"
        guard_id = None
        condition = (rule.get("condition") or "").strip()
        if condition:
            guard_id = f"overlay_guard_{index:03d}"
            guards.append({
                "guard_id": guard_id,
                "statement": condition,
                "supported_by": list(rule.get("condition_supported_by") or []),
                "support": "supported",
                "exclusive_group": None,
            })
        facts = []
        for fact_index, fact in enumerate(rule.get("facts") or [], 1):
            fact_id = f"{rule_id}.f{fact_index:02d}"
            capabilities = []
            for cap_index, cap in enumerate(fact.get("capabilities") or [], 1):
                capabilities.append({
                    **cap,
                    "capability_id": f"{fact_id}.c{cap_index:02d}",
                })
            facts.append({
                **fact,
                "fact_id": fact_id,
                "node_id": rule.get("parent_node_id"),
                "guard_id": guard_id,
                "capabilities": capabilities,
            })
        materialized = {
            "rule_id": rule_id,
            "parent_node_id": rule.get("parent_node_id"),
            "requirement_kind": rule.get("requirement_kind"),
            "requirement": rule.get("requirement"),
            "guard_id": guard_id,
            "condition": condition or None,
            "supported_by": list(rule.get("supported_by") or []),
            "condition_supported_by": list(rule.get("condition_supported_by") or []),
            "facts": facts,
        }
        rules.append(materialized)
        compiled.append({"node_id": rule_id, "facts": facts, "problems": []})

    return {
        "contract": CONTRACT,
        "guards": guards,
        "rules": rules,
        "compiled": compiled,
        "non_evidentiary": copy.deepcopy(refinement_result["refinement"].get("non_evidentiary") or []),
        "verification": copy.deepcopy(refinement_result["verification"]),
    }
def _resolver_capability(rule: Mapping[str, Any]) -> dict[str, Any] | None:
    if not rule.get("guard_id"):
        return None
    return {
        "capability_id": f"resolver.{rule['rule_id']}",
        "rule_id": rule["rule_id"],
        "guard_id": rule["guard_id"],
        "must_show": f"whether this source-defined applicability condition holds: {rule['condition']}",
        "from_propositions": list(rule.get("condition_supported_by") or []),
    }


def prepare(overlay: Mapping[str, Any], catalogue: Sequence[str], call: Callable[[str, str], str]) -> dict[str, Any]:
    requirement_caps = [
        cap
        for block in overlay.get("compiled") or []
        for fact in block.get("facts") or []
        for cap in fact.get("capabilities") or []
    ]
    resolvers = [x for x in (_resolver_capability(r) for r in overlay.get("rules") or []) if x]
    capabilities = requirement_caps + resolvers
    requirements: list[dict[str, Any]] = []
    problems: list[str] = []
    for start in range(0, len(capabilities), 12):
        mapped = oc.map_documents(capabilities[start:start + 12], catalogue, call)
        requirements.extend(mapped.get("requirements") or [])
        problems.extend(mapped.get("problems") or [])
    known = {c["capability_id"] for c in capabilities}
    returned = {r.get("capability_id") for r in requirements if r.get("capability_id")}
    if known != returned:
        problems.append({
            "missing_capabilities": sorted(known - returned),
            "unknown_capabilities": sorted(returned - known),
        })
    return {
        "contract": CONTRACT,
        "overlay": copy.deepcopy(overlay),
        "catalogue": list(catalogue),
        "resolvers": resolvers,
        "requirements": requirements,
        "problems": problems,
    }


def _guard_state(guard_id: str | None, verdicts: Mapping[str, Mapping[str, Any]]) -> str:
    if guard_id is None:
        return "active"
    verdict = verdicts.get(guard_id, {}).get("verdict", "unresolved")
    return {"true": "active", "false": "inactive", "unresolved": "unresolved"}[verdict]


def _routes(prepared: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {r["capability_id"]: list(r.get("routes") or []) for r in prepared.get("requirements") or []}
def plan_case(*, case: Mapping[str, str], prepared: Mapping[str, Any], held: Sequence[str],
              call: Callable[[str, str], str] | None = None, decide_fn=None,
              decided: Mapping[str, Any] | None = None,
              confirmed_guard_ids: Sequence[str] = ()) -> dict[str, Any]:
    """Plan only from the active path; unresolved branches become next-action questions.

    A narrative can activate a positive branch without being treated as documentary proof.
    Callers may pass guard ids already confirmed by admitted evidence; otherwise a true
    guarded rule may request a mapped confirmation route. Unresolved guards never add
    branch-specific documents to the checklist.
    """
    if prepared.get("problems"):
        raise ValueError(f"overlay preparation problems: {prepared['problems']}")
    overlay = prepared["overlay"]
    if decided is None:
        if call is None:
            raise ValueError("call is required when no precomputed guard decision is supplied")
        decide_fn = decide_fn or ci.decide
        decided = decide_fn({"guards": overlay.get("guards") or []}, case, call)
    verdicts = decided["verdicts"]
    route_index = _routes(prepared)
    held_set = set(held)
    confirmed = set(confirmed_guard_ids)
    active_chains: list[dict[str, Any]] = []
    confirmation_chains: list[dict[str, Any]] = []
    state_questions: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for rule, block in zip(overlay.get("rules") or [], overlay.get("compiled") or []):
        guard_id = rule.get("guard_id")
        verdict = verdicts.get(guard_id, {}).get("verdict", "unresolved") if guard_id else "true"
        if verdict == "unresolved":
            capability_id = f"resolver.{rule['rule_id']}" if guard_id else None
            state_questions.append({
                "rule_id": rule["rule_id"], "guard_id": guard_id,
                "process_node": rule.get("parent_node_id"), "condition": rule.get("condition"),
                "what_would_settle_it": verdicts.get(guard_id, {}).get("what_would_settle_it"),
                "mapped_document_routes": list(route_index.get(capability_id, [])) if capability_id else [],
                "authorities": list(rule.get("condition_supported_by") or []),
            })
            continue
        if verdict == "false":
            continue

        if guard_id and guard_id not in confirmed:
            capability_id = f"resolver.{rule['rule_id']}"
            routes = route_index.get(capability_id, [])
            for route in routes:
                confirmation_chains.append({
                    "document_types": list(route.get("document_types") or []),
                    "route_id": route.get("route_id"), "capability_id": capability_id,
                    "must_show": f"documentary confirmation that {rule.get('condition')}",
                    "fact": rule.get("condition"), "node_id": rule.get("parent_node_id"),
                    "rule_id": rule["rule_id"], "guard_id": guard_id,
                    "authorities": list(rule.get("condition_supported_by") or []),
                    "purpose": "confirm_active_process_state",
                })

        for fact in block.get("facts") or []:
            for capability in fact.get("capabilities") or []:
                routes = route_index.get(capability["capability_id"], [])
                if not routes:
                    gaps.append({"fault": "evidence_gap", "rule_id": rule["rule_id"],
                                 "node_id": rule.get("parent_node_id"), "fact_id": fact["fact_id"],
                                 "capability_id": capability["capability_id"],
                                 "must_show": capability.get("must_show")})
                for route in routes:
                    active_chains.append({
                        "document_types": list(route.get("document_types") or []),
                        "route_id": route.get("route_id"), "capability_id": capability["capability_id"],
                        "must_show": capability.get("must_show"), "fact_id": fact["fact_id"],
                        "fact": fact.get("statement"), "node_id": rule.get("parent_node_id"),
                        "rule_id": rule["rule_id"], "guard_id": guard_id,
                        "authorities": list(rule.get("supported_by") or []),
                        "purpose": "satisfy_active_requirement",
                    })

    grouped: dict[str, dict[str, Any]] = {}
    for chain in active_chains + confirmation_chains:
        docs = [d for d in chain["document_types"] if d not in held_set]
        if not docs:
            continue
        key = "+".join(sorted(chain["document_types"]))
        request = grouped.setdefault(key, {"document_types": list(chain["document_types"]),
                                           "still_missing": docs, "purposes": set(),
                                           "justified_by": []})
        request["purposes"].add(chain["purpose"])
        request["justified_by"].append({
            "purpose": chain["purpose"], "process_node": chain.get("node_id"),
            "rule_id": chain.get("rule_id"), "guard_id": chain.get("guard_id"),
            "fact": chain.get("fact"), "must_show": chain.get("must_show"),
            "authorities": chain.get("authorities") or [],
        })
    requests = []
    for request in grouped.values():
        request["purposes"] = sorted(request["purposes"])
        requests.append(request)
    requests.sort(key=lambda x: (x["still_missing"], x["document_types"]))

    next_action = None
    if state_questions:
        ranked = sorted(state_questions,
                        key=lambda q: (-bool(q["mapped_document_routes"]), q.get("guard_id") or ""))
        q = ranked[0]
        next_action = {"type": "resolve_process_state", "guard_id": q["guard_id"],
                       "process_node": q["process_node"], "condition": q["condition"],
                       "what_would_settle_it": q["what_would_settle_it"],
                       "why": "Resolve a source-defined branch before requesting its branch-specific documents."}
    elif requests:
        ranked = sorted(requests, key=lambda r: (-len(r["justified_by"]), len(r["still_missing"]), r["still_missing"]))
        next_action = {"type": "satisfy_active_requirement", "request": ranked[0],
                       "why": "Satisfy a source-grounded requirement active on the current process path."}

    return {"contract": CONTRACT, "requests": requests,
            "documents": sorted({d for r in requests for d in r["still_missing"]}),
            "next_action": next_action, "guard_verdicts": verdicts,
            "ungrounded": decided.get("ungrounded") or [],
            "active_requirement_chains": active_chains,
            "confirmation_chains": confirmation_chains,
            "resolver_chains": [], "state_questions": state_questions,
            "evidence_gaps": gaps,
            "counts": {"requests": len(requests), "active_requirement_chains": len(active_chains),
                       "confirmation_chains": len(confirmation_chains),
                       "state_questions": len(state_questions), "evidence_gaps": len(gaps)}}

