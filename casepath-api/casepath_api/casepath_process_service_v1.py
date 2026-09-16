"""The product surface for the paper's method: one call per claim, returning the full justification trace.

This is deliberately thin. It composes the same four modules the experiments use — induction, case
interpretation, obligation compilation, evidence admission — and adds nothing of its own, so that "the
product runs the paper method" is true by construction rather than by inspection. If this file grew its own
logic, the claim would stop being checkable.

What it exposes to the interface is the answer to the question a handler actually asks of a request:

    Why is this required?        the node that is active or unresolved
    Why does that node matter?   the authority passage and the exact quoted span
    What fact does it need?      the fact obligation
    Why this document?           the evidence capability it establishes, and the alternatives
    Why now?                     nothing sufficient is present yet
    When does it stop?           the predicate whose resolution would withdraw it
"""
from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from . import case_interpreter_v1 as ci
from . import obligation_compiler_v1 as oc

CONTRACT = "casepath.process-service/1.0.0"


def _authority_index(passages: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {p["authority_id"]: p for p in passages}


def explain_requests(*, graph: Mapping[str, Any], propositions: Mapping[str, Mapping[str, Any]],
                     passages: Sequence[Mapping[str, Any]], compiled: Sequence[Mapping[str, Any]],
                     requirements: Sequence[Mapping[str, Any]], case: Mapping[str, str],
                     already_held: Sequence[str], call: Callable[[str, str], str]) -> dict[str, Any]:
    """Everything the interface needs for one claim, with each request fully traced."""
    authorities = _authority_index(passages)
    decided = ci.decide(graph, case, call)
    state = ci.activate(graph, decided["verdicts"])
    chains = oc.build_chains(graph, state, compiled, requirements, propositions)
    cl = oc.checklist(chains, already_held=already_held)

    # which predicate, if resolved, would close each node — this is what makes a request retractable
    closers: dict[str, list[dict[str, Any]]] = {}
    for t in graph.get("transitions") or []:
        if t.get("condition") and t.get("target_node_id"):
            closers.setdefault(t["target_node_id"], []).append(
                {"predicate_id": t["edge_id"], "condition": t["condition"],
                 "current_verdict": decided["verdicts"].get(t["edge_id"], {}).get("verdict", "unresolved")})

    explained = []
    for req in cl["requests"]:
        traces = []
        for j in req["justified_by"]:
            cites = []
            for aid in j.get("authorities") or []:
                a = authorities.get(aid)
                if a:
                    cites.append({"authority_id": aid, "citation": a.get("article"),
                                  "exact_text": a.get("exact_text"), "source_url": a.get("source_url")})
            traces.append({
                "process_node": j["node_id"],
                "node_label": next((n.get("label") for n in graph["nodes"] if n["node_id"] == j["node_id"]), None),
                "activation": state.get(j["node_id"]),
                "required_fact": j["fact"],
                "evidence_capability": j["must_show"],
                "authorities": cites,
                "would_be_withdrawn_if": closers.get(j["node_id"], []),
            })
        explained.append({"document_types": req["document_types"], "still_missing": req["still_missing"],
                          "justifications": traces})

    return {"contract": CONTRACT,
            "requests": explained,
            "activation": state,
            "predicate_verdicts": {k: {"verdict": v["verdict"], "quote": v.get("quote"),
                                       "what_would_settle_it": v.get("what_would_settle_it")}
                                   for k, v in decided["verdicts"].items()},
            "evidence_gaps": chains["evidence_gaps"],
            "faults": {k: v for k, v in chains["counts"].items() if k != "chains"},
            "unresolved_predicates": [p["predicate_id"] for p in
                                      [{"predicate_id": k} for k, v in decided["verdicts"].items()
                                       if v["verdict"] == "unresolved"]]}


def diff_requests(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    """What changed, and why — the audit event the interface shows when a branch resolves."""
    def docs(state):
        return {d for r in state["requests"] for d in r["document_types"]}
    b, a = docs(before), docs(after)
    flipped = [{"predicate_id": k,
                "from": before["predicate_verdicts"].get(k, {}).get("verdict"),
                "to": v.get("verdict")}
               for k, v in after["predicate_verdicts"].items()
               if before["predicate_verdicts"].get(k, {}).get("verdict") != v.get("verdict")]
    closed = [n for n, s in after["activation"].items()
              if s == "inactive" and before["activation"].get(n) != "inactive"]
    return {"withdrawn": sorted(b - a), "added": sorted(a - b),
            "predicates_that_flipped": flipped, "nodes_that_closed": closed,
            "explanation": [f"{d} was withdrawn because every process node that required it is now inactive"
                            for d in sorted(b - a)]}
