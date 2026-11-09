"""CasePath (latest agent) on tenancy claims, using the product's own code.

Pipeline: typed interpretation -> independent verification -> deterministic
admission (`validate_interpretation`) -> process compilation (`compile_process`)
-> causal evaluation (`causal_process_v1.evaluate`). Only the request-relevant
parts are run: step assessments and knowledge candidates are omitted.
"""
from __future__ import annotations

import sys
from copy import deepcopy

from tenancy_data import REPO, templates

sys.path.insert(0, str(REPO / "casepath-api"))
from casepath_api.autonomous_policy_v1 import (  # noqa: E402
    compile_process, proposal_items, validate_interpretation)
from casepath_api.causal_process_v1 import evaluate, seal_graph, _document_definition_sha256  # noqa: E402

FAMILIES = [t["domain"] for t in templates()["templates"]]


def _apply_document_reviews(graph: dict, verified: dict, sources: list[dict]) -> dict:
    """As AutonomousController._documents: verified items become document reviews."""
    rejected = {row["item_id"] for row in verified["item_rejections"]}
    by_id = {s["artifact_id"]: s for s in sources}
    for document in verified["documents"]:
        if f"document:{document['document_type']}:{document['artifact_id']}" in rejected:
            continue
        view = evaluate(graph)
        route = next(d for d in view["documents"] if d["document_type"] == document["document_type"])
        source = by_id[document["artifact_id"]]
        supplied_review = (document.get("independently_verified") is True
                           and source["role"] == "supporting_document")
        if route["activation"] != "true" and not supplied_review:
            continue
        graph = deepcopy(graph)
        definition = next(d for d in graph["document_catalog"] if d["document_type"] == document["document_type"])
        review = {"artifact_id": source["artifact_id"], "file_name": source["file_name"],
                  "media_type": source["media_type"], "sha256": source["sha256"],
                  "source_quote": document["citations"][0]["quote"] if document["citations"] else "",
                  "review": document["assessment"], "reviewed_by": "independent_machine_verification",
                  "note": document["summary"], "citations": document["citations"],
                  "document_definition_sha256": _document_definition_sha256(definition)}
        definition["held_files"] = [d for d in definition["held_files"]
                                    if d["artifact_id"] != source["artifact_id"]] + [review]
        graph["revision"] += 1
        graph = seal_graph(graph)
    return graph


def plan_from_verified(claim_id: str, verified: dict, sources: list[dict]) -> dict:
    graph, _facts, _obligations = compile_process(templates(), claim_id, verified)
    graph = _apply_document_reviews(graph, verified, sources)
    view = evaluate(graph)
    docs = {d["document_type"]: d["route_state"] for d in view["documents"]}
    return {"family": verified["category"]["family"], "document_states": docs,
            "requests": sorted(k for k, v in docs.items() if v in {"needed_now", "needed_later"}),
            "holds": sorted(k for k, v in docs.items() if v == "held_behind_question"),
            "established": sorted(k for k, v in docs.items() if v == "established"),
            "unresolved_flags": sorted(c["flag"] for c in verified["conditions"] if c["verdict"] == "unresolved"),
            "deferred": False}


def casepath_plan(claim_id: str, proposal: dict, verifier: dict | None, sources: list[dict]) -> dict:
    """Run admission and the causal engine. verifier=None accepts every item (ablation)."""
    proposal = {**deepcopy(proposal), "steps": proposal.get("steps", []),
                "knowledge_candidates": proposal.get("knowledge_candidates", [])}
    if verifier is None:
        verifier = {"family_supported": True, "issues": [],
                    "checks": [{"item_id": i, "accepted": True, "reason": ""} for i in proposal_items(proposal)]}
    try:
        verified = validate_interpretation(templates(), sources, proposal, verifier)
    except ValueError as error:
        return {"family": None, "document_states": {}, "requests": [], "holds": [], "established": [],
                "unresolved_flags": [], "deferred": True, "deferral_reason": str(error)}
    return plan_from_verified(claim_id, verified, sources)


# ---------------------------------------------------------------------------
# Exact deferral (supervaluation) on top of the unchanged product engine.
# Strong Kleene logic is sound but incomplete: where alternative branches
# reconverge, (U and T) or (T and U) evaluates to U although the step is
# reached under every answer. Supervaluation evaluates the engine under every
# completion of the open flags and requests a document only if every completion
# requires it; it holds a document only if the answer actually matters.
from itertools import product as _product  # noqa: E402

REQUEST_STATES = {"needed_now", "needed_later"}


def supervaluate(graph: dict, max_open: int = 12) -> dict:
    flags = graph["conditions"]
    open_flags = sorted(f for f, v in flags.items() if v.get("verdict") == "unresolved")
    if len(open_flags) > max_open:
        view = evaluate(graph)
        return {"mode": "kleene_fallback", "states": {d["document_type"]: d["route_state"] for d in view["documents"]},
                "questions": open_flags}
    completions = []
    for bits in _product(("true", "false"), repeat=len(open_flags)):
        override = dict(zip(open_flags, bits))
        view = evaluate(graph, conditions=override) if override else evaluate(graph)
        completions.append((override, {d["document_type"]: d["route_state"] for d in view["documents"]}))
    base = {d["document_type"]: d["route_state"] for d in evaluate(graph)["documents"]}
    states, relevant = {}, set()
    for doc in base:
        req = [s[doc] in REQUEST_STATES for _, s in completions]
        if all(req):
            states[doc] = "needed_now" if all(s[doc] == "needed_now" for _, s in completions) else "needed_later"
        elif not any(req):
            states[doc] = base[doc] if base[doc] not in REQUEST_STATES | {"held_behind_question"} else completions[0][1][doc]
        else:
            states[doc] = "held_behind_question"
            for flag in open_flags:  # a question matters if flipping it alone changes this document
                for override, s in completions:
                    if override[flag] == "true":
                        twin = {**override, flag: "false"}
                        t = next(st for ov, st in completions if ov == twin)
                        if (s[doc] in REQUEST_STATES) != (t[doc] in REQUEST_STATES):
                            relevant.add(flag)
                            break
    return {"mode": "supervaluation", "states": states, "questions": sorted(relevant)}


def plan_from_verified_exact(claim_id: str, verified: dict, sources: list[dict]) -> dict:
    graph, _f, _o = compile_process(templates(), claim_id, verified)
    graph = _apply_document_reviews(graph, verified, sources)
    sv = supervaluate(graph)
    docs = sv["states"]
    return {"family": verified["category"]["family"], "document_states": docs, "mode": sv["mode"],
            "requests": sorted(k for k, v in docs.items() if v in REQUEST_STATES),
            "holds": sorted(k for k, v in docs.items() if v == "held_behind_question"),
            "established": sorted(k for k, v in docs.items() if v == "established"),
            "questions": sv["questions"], "deferred": False}


def casepath_plan_exact(claim_id: str, proposal: dict, verifier: dict | None, sources: list[dict]) -> dict:
    proposal = {**deepcopy(proposal), "steps": proposal.get("steps", []),
                "knowledge_candidates": proposal.get("knowledge_candidates", [])}
    if verifier is None:
        verifier = {"family_supported": True, "issues": [],
                    "checks": [{"item_id": i, "accepted": True, "reason": ""} for i in proposal_items(proposal)]}
    try:
        verified = validate_interpretation(templates(), sources, proposal, verifier)
    except ValueError as error:
        return {"family": None, "document_states": {}, "requests": [], "holds": [], "established": [],
                "questions": [], "deferred": True, "deferral_reason": str(error)}
    return plan_from_verified_exact(claim_id, verified, sources)
