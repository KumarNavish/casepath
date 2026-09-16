"""Score a system against a source-based reference contract.

Three families, and the third is the one that separates a genuinely process-derived checklist from a model
that happens to emit a plausible static list.

  A. process identification — did the system reconstruct the decisions the sources specify? Scored
     semantically against the contract's required decisions, not against one drawing of a graph. A system
     that splits or merges nodes while preserving the decision is not penalised.
  B. process-derived checklist — are the documents the right ones, and is each one justified by a chain
     back to an active obligation?
  C. dynamic causal consistency — when a branch resolves, does the checklist change the way the contract
     says it must? A static predictor can score well on A and B and cannot score well on C.

Nothing here reads a system's own induced graph as ground truth.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

CONTRACT = "casepath.process-evaluation/1.0.0"


def _prf(hit: int, predicted: int, gold: int) -> dict[str, float]:
    p = hit / predicted if predicted else 0.0
    r = hit / gold if gold else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4),
            "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0,
            "hit": hit, "predicted": predicted, "gold": gold}


def process_identification(reference: Mapping[str, Any], predicted_graph: Mapping[str, Any],
                           decision_match: Mapping[str, str]) -> dict[str, Any]:
    """`decision_match` maps reference decision_id -> predicted node_id, or None where unmatched.

    The mapping is produced by a semantic matcher outside this module, so that graph shape is not scored.
    """
    gold_decisions = [d["decision_id"] for d in reference.get("decisions") or []]
    matched = {k: v for k, v in decision_match.items() if v}
    nodes = {n["node_id"] for n in predicted_graph.get("nodes") or []}
    extra = nodes - set(matched.values())

    gold_preds = {p["predicate_id"] for p in reference.get("predicates") or []}
    pred_conds = [t for t in predicted_graph.get("transitions") or [] if t.get("condition")]

    critical_missing = [d for d in gold_decisions if not decision_match.get(d)]
    grounded = sum(1 for n in predicted_graph.get("nodes") or [] if n.get("supported_by"))
    return {
        "decisions": _prf(len(matched), len(nodes), len(gold_decisions)),
        "critical_decision_omissions": critical_missing,
        "extra_nodes": sorted(extra),
        "branch_predicates": {"gold": len(gold_preds), "predicted_conditional_edges": len(pred_conds)},
        "source_grounding_rate": round(grounded / len(nodes), 4) if nodes else 0.0,
        "terminal_coverage": _prf(
            len({n["node_id"] for n in predicted_graph.get("nodes") or [] if n.get("kind") == "terminal"}
                & set(matched.values())),
            sum(1 for n in predicted_graph.get("nodes") or [] if n.get("kind") == "terminal"),
            len(reference.get("terminals") or [])),
    }


def checklist_quality(reference: Mapping[str, Any], requested: Sequence[str],
                      chains: Sequence[Mapping[str, Any]], critical: Sequence[str] = ()) -> dict[str, Any]:
    """Family B. `chains` are the system's justification chains, one per justified document route."""
    gold_docs = {d["document_type"] for d in reference.get("documents") or []}
    req = set(requested)
    crit = set(critical) or gold_docs
    justified = {d for ch in chains if ch.get("fault") is None for d in ch.get("document_types", [])}

    orphans = sorted(req - justified)
    unnecessary = sorted(req - gold_docs)
    with_chain = [ch for ch in chains if ch.get("fault") is None]
    faults = {f: sum(1 for ch in chains if ch.get("fault") == f)
              for f in ("wrong_branch_request", "premature_request")}
    alt_routes = {}
    for ch in with_chain:
        alt_routes.setdefault(ch.get("capability_id"), set()).add(ch.get("route_id"))
    multi = sum(1 for v in alt_routes.values() if len(v) > 1)
    return {
        "critical_document_recall": round(len(req & crit) / len(crit), 4) if crit else 0.0,
        "unnecessary_document_rate": round(len(unnecessary) / len(req), 4) if req else 0.0,
        "valid_chain_precision": round(len(req & justified) / len(req), 4) if req else 0.0,
        "orphan_documents": orphans,
        "orphan_rate": round(len(orphans) / len(req), 4) if req else 0.0,
        "wrong_branch_requests": faults["wrong_branch_request"],
        "premature_requests": faults["premature_request"],
        "alternative_route_coverage": round(multi / len(alt_routes), 4) if alt_routes else 0.0,
        "documents_requested": sorted(req),
    }


def causal_consistency(before: Mapping[str, Any], after: Mapping[str, Any],
                       expected_withdrawn: Sequence[str], expected_added: Sequence[str] = ()) -> dict[str, Any]:
    """Family C. One branch intervention, with the contract saying what must change.

    `before`/`after` each carry `requested` (the checklist) and `chains` (its justifications).
    `expected_withdrawn` comes from the reference contract: documents whose every justification is closed
    by the intervention.
    """
    req_b, req_a = set(before["requested"]), set(after["requested"])
    exp_w, exp_a = set(expected_withdrawn), set(expected_added)

    actually_withdrawn = req_b - req_a
    actually_added = req_a - req_b

    # a document that lost every active justification in the system's own chains
    def live(state):
        return {d for ch in state["chains"] if ch.get("fault") is None for d in ch.get("document_types", [])}
    lost_all = live(before) - live(after)

    correct_w = actually_withdrawn & exp_w
    correct_a = actually_added & exp_a
    changes_expected = len(exp_w) + len(exp_a)
    changes_correct = len(correct_w) + len(correct_a)
    return {
        "checklist_responsiveness": round(changes_correct / changes_expected, 4) if changes_expected else None,
        "justification_withdrawal_precision":
            round(len(actually_withdrawn & lost_all) / len(actually_withdrawn), 4) if actually_withdrawn else None,
        "justification_withdrawal_recall":
            round(len(actually_withdrawn & lost_all) / len(lost_all), 4) if lost_all else None,
        "spurious_persistence": sorted(lost_all - actually_withdrawn),
        "spurious_addition": sorted(actually_added - exp_a),
        "expected_withdrawn": sorted(exp_w), "actually_withdrawn": sorted(actually_withdrawn),
        "expected_added": sorted(exp_a), "actually_added": sorted(actually_added),
    }


def aggregate_causal(runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pool interventions. A system that never changes its checklist scores zero responsiveness."""
    def mean(key):
        vals = [r[key] for r in runs if r.get(key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None
    return {"interventions": len(runs),
            "checklist_responsiveness": mean("checklist_responsiveness"),
            "justification_withdrawal_precision": mean("justification_withdrawal_precision"),
            "justification_withdrawal_recall": mean("justification_withdrawal_recall"),
            "total_spurious_persistence": sum(len(r["spurious_persistence"]) for r in runs),
            "total_spurious_addition": sum(len(r["spurious_addition"]) for r in runs),
            "never_changed": sum(1 for r in runs if not r["actually_withdrawn"] and not r["actually_added"])}
