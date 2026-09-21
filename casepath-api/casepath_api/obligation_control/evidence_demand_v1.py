"""Requests from active obligations and alternative evidence routes.

Route selection minimizes (number of requested documents, review items, lexical
route key) PER CAPABILITY. It is not a global minimum-document optimizer.
Adequacy is an explicit upstream assessment, never inferred from possession.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .obligation_control_v1 import (Graph, Invalid, Truth, all3, any3, fields, identifier,
                                    ids, support, truth)

CONTRACT = "casepath.evidence-demand/1.0.0"
STATES = {"missing", "provided_sufficient", "provided_insufficient", "unknown", "conditional", "irrelevant"}


@dataclass(frozen=True)
class Route:
    route_id: str
    document_ids: tuple[str, ...]
    source_refs: tuple[str, ...]


@dataclass(frozen=True)
class Capability:
    capability_id: str
    fact_id: str
    fact_statement: str
    must_show: str
    routes: tuple[Route, ...]
    source_refs: tuple[str, ...]


def capabilities(obj: Any, registry: set[str]) -> tuple[Capability, ...]:
    if not isinstance(obj, list) or len(obj) > 256:
        raise Invalid("capabilities must be a bounded list")
    out = []
    for row in obj:
        fields(row, {"capability_id", "fact_id", "fact_statement", "must_show", "routes", "source_refs"})
        if any(not isinstance(row[k], str) or not row[k].strip() for k in ("must_show", "fact_statement")):
            raise Invalid("capability must state what evidence shows")
        if not isinstance(row["routes"], list) or len(row["routes"]) > 32:
            raise Invalid("routes must be a bounded list")
        routes = []
        for r in row["routes"]:
            fields(r, {"route_id", "document_ids", "source_refs"})
            routes.append(Route(identifier(r["route_id"]), ids(r["document_ids"], nonempty=True), support(r["source_refs"], registry)))
        if len({r.route_id for r in routes}) != len(routes):
            raise Invalid("duplicate routes within a capability")
        out.append(Capability(identifier(row["capability_id"]), identifier(row["fact_id"]), row["fact_statement"],
                              row["must_show"], tuple(sorted(routes, key=lambda r: r.route_id)), support(row["source_refs"], registry)))
    if len({c.capability_id for c in out}) != len(out):
        raise Invalid("duplicate capability ids")
    return tuple(sorted(out, key=lambda c: c.capability_id))


def evidence_state(obj: Any, caps: tuple[Capability, ...], case_source_refs: set[str]) -> dict:
    fields(obj, {"documents", "slot_assessments", "joint_assessments"})
    known_docs = {d for c in caps for r in c.routes for d in r.document_ids}
    if not isinstance(obj["documents"], dict) or set(obj["documents"]) - known_docs:
        raise Invalid("unknown document identity in evidence state")
    documents = {}
    for doc, value in obj["documents"].items():
        fields(value, {"presence", "native_state", "source_refs"})
        if value["presence"] not in {"missing", "present", "unknown"} or value["native_state"] not in STATES:
            raise Invalid("invalid document presence/state")
        state, presence = value["native_state"], value["presence"]
        if (state == "missing" and presence != "missing") or (state.startswith("provided_") and presence != "present"):
            raise Invalid("contradictory document presence and native state")
        refs = value["source_refs"]
        if not isinstance(refs, list) or any(not isinstance(x, str) or x not in case_source_refs for x in refs):
            raise Invalid("document assessment has unknown observation source")
        if presence != "unknown" and not refs:
            raise Invalid("positive/negative presence requires an observation reference")
        documents[doc] = {**value, "source_refs": sorted(set(refs))}
    routes = {(c.capability_id, r.route_id): r for c in caps for r in c.routes}
    slots, joints = {}, {}
    for name, dest, is_joint in (("slot_assessments", slots, False), ("joint_assessments", joints, True)):
        if not isinstance(obj[name], list) or len(obj[name]) > 8192:
            raise Invalid("assessment list exceeds bound")
        for row in obj[name]:
            fields(row, {"capability_id", "route_id", "adequate", "source_refs"} | (set() if is_joint else {"document_id"}))
            pair = (row["capability_id"], row["route_id"])
            if pair not in routes:
                raise Invalid("unknown assessment route")
            route = routes[pair]
            if is_joint:
                key = pair
            else:
                if row["document_id"] not in route.document_ids:
                    raise Invalid("document outside assessed route")
                key = (*pair, row["document_id"])
            if key in dest:
                raise Invalid("duplicate evidence assessment")
            value = truth(row["adequate"])
            refs = row["source_refs"]
            if not isinstance(refs, list) or any(not isinstance(x, str) or x not in case_source_refs for x in refs):
                raise Invalid("unknown adequacy observation reference")
            if value != Truth.UNKNOWN and not refs:
                raise Invalid("decided adequacy requires an observation reference")
            if value == Truth.TRUE:
                tested = route.document_ids if is_joint else (row["document_id"],)
                if any(documents.get(d, {}).get("presence") != "present" for d in tested):
                    raise Invalid("adequate evidence cannot be missing or unobserved")
            dest[key] = value
    return {"documents": documents, "slots": slots, "joints": joints}


def route_status(cap: Capability, route: Route, evidence: dict) -> dict:
    request, review, vals = [], [], []
    for doc in route.document_ids:
        presence = evidence["documents"].get(doc, {}).get("presence", "unknown")
        adequacy = evidence["slots"].get((cap.capability_id, route.route_id, doc), Truth.UNKNOWN)
        if presence == "missing":
            vals.append(Truth.FALSE); request.append(doc)
        elif presence == "unknown":
            vals.append(Truth.UNKNOWN); review.append({"document_id": doc, "reason": "presence_unresolved"})
        elif adequacy == Truth.FALSE:
            vals.append(Truth.FALSE); request.append(doc)
        elif adequacy == Truth.UNKNOWN:
            vals.append(Truth.UNKNOWN); review.append({"document_id": doc, "reason": "adequacy_unresolved"})
        else:
            vals.append(Truth.TRUE)
    joint = evidence["joints"].get((cap.capability_id, route.route_id), Truth.TRUE if len(route.document_ids) == 1 else Truth.UNKNOWN)
    if not request and not review and joint != Truth.TRUE:
        review.append({"document_id": None, "reason": "joint_adequacy_unresolved" if joint == Truth.UNKNOWN else "joint_adequacy_failed"})
    satisfied = all3(tuple(vals) + (joint,))
    return {"route_id": route.route_id, "document_ids": list(route.document_ids),
            "satisfaction": satisfied.value, "request": sorted(request), "review": review,
            "source_refs": list(route.source_refs)}


def plan(graph: Graph, caps: tuple[Capability, ...], observations: dict, evidence: dict, *, execution_mode: str = "graph") -> dict:
    by_cap = {c.capability_id: c for c in caps}
    if any(not set(o.capability_ids) <= set(by_cap) for o in graph.obligations):
        raise Invalid("obligation references unknown capability")
    if execution_mode not in {"graph", "compiled"}:
        raise Invalid("unknown control execution mode")
    control = graph.evaluate(observations) if execution_mode == "graph" else graph.evaluate_compiled(observations)
    cap_status = {}
    for c in caps:
        alternatives = [route_status(c, r, evidence) for r in c.routes]
        satisfied = any3(tuple(Truth(r["satisfaction"]) for r in alternatives))
        selected = None
        if alternatives:
            selected = min(alternatives, key=lambda r: (r["satisfaction"] != Truth.TRUE.value,
                len(r["request"]), len(r["review"]), tuple(r["request"]), r["route_id"]))
        cap_status[c.capability_id] = {"satisfaction": satisfied.value, "selected": selected, "alternatives": alternatives}
    requests: dict[str, list[dict]] = {}
    conditional: set[str] = set()
    reviews, questions, gaps = [], [], []
    obligation_completion = {}
    for o in graph.obligations:
        state = control["obligations"][o.obligation_id]
        active, acquisition = Truth(state["applicability"]), Truth(state["acquisition"])
        completion = all3(tuple(Truth(cap_status[c]["satisfaction"]) for c in o.capability_ids))
        obligation_completion[o.obligation_id] = completion
        if active == Truth.FALSE:
            continue
        if active == Truth.UNKNOWN:
            questions.append({"kind": "resolve_applicability", "obligation_id": o.obligation_id, "scope_id": o.scope_id})
        for cid in o.capability_ids:
            c, value = by_cap[cid], cap_status[cid]
            if value["satisfaction"] == Truth.TRUE.value:
                continue
            selected = value["selected"]
            if selected is None:
                gaps.append({"obligation_id": o.obligation_id, "capability_id": cid, "applicability": active.value, "reason": "no_document_route"})
                continue
            if active == Truth.UNKNOWN or acquisition != Truth.TRUE:
                conditional.update(selected["request"])
                if active == Truth.TRUE:
                    questions.append({"kind": "acquisition_not_permitted" if acquisition == Truth.FALSE else "resolve_acquisition", "obligation_id": o.obligation_id, "capability_id": cid})
                continue
            for item in selected["review"]:
                reviews.append({"obligation_id": o.obligation_id, "capability_id": cid, "route_id": selected["route_id"], **item})
            for doc in selected["request"]:
                chain = {"scope_id": o.scope_id, "obligation_id": o.obligation_id,
                         "fact_id": c.fact_id, "capability_id": cid, "route_id": selected["route_id"],
                         "document_id": doc, "must_show": c.must_show,
                         "source_refs": sorted(set(o.source_refs) | set(c.source_refs) | set(selected["source_refs"]))}
                requests.setdefault(doc, []).append(chain)
    values = graph.values(observations)
    actions = {}
    for a in graph.actions:
        required = []
        for oid in a.obligation_ids:
            applicability = Truth(control["obligations"][oid]["applicability"])
            required.append(Truth.TRUE if applicability == Truth.FALSE else Truth.UNKNOWN if applicability == Truth.UNKNOWN else obligation_completion[oid])
        actions[a.action_id] = all3((Truth(control["scopes"][a.scope_id]["state"]), a.prerequisites.evaluate(values), *required)).value
    # Every request is conditional on actual controller eligibility, not native gold.
    out_requests = [{"document_id": d, "justifications": requests[d]} for d in sorted(requests)]
    next_action = None
    if questions:
        next_action = questions[0]
    elif reviews:
        next_action = {"kind": "review_evidence", **reviews[0]}
    elif out_requests:
        next_action = {"kind": "request_document", "document_id": out_requests[0]["document_id"]}
    elif any(g["applicability"] == Truth.TRUE.value for g in gaps):
        next_action = {"kind": "review_evidence_gap", **next(g for g in gaps if g["applicability"] == Truth.TRUE.value)}
    else:
        ready = sorted(a for a, state in actions.items() if state == Truth.TRUE.value)
        if ready:
            next_action = {"kind": "action_ready", "action_id": ready[0]}
    return {"contract": CONTRACT, "control": control, "capabilities": cap_status,
            "requests": out_requests, "documents_now": sorted(requests),
            "documents_conditional": sorted(conditional - set(requests)), "reviews": reviews,
            "questions": questions, "evidence_gaps": gaps, "action_readiness": actions,
            "next_action": next_action,
            "semantics": "per_capability_route_selection; possession_does_not_establish_adequacy"}
