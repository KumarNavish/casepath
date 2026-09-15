"""B6: the minimal deterministic artifact gate a competent engineer would add to a strong baseline.

This is a *comparator*, not part of the method. It exists to answer one objection experimentally: could the
whole result have been obtained by bolting one obvious ``if the artifact never arrived, it is not
received`` condition onto the strongest existing baseline?

It therefore keeps the baseline intact — its model call, its process decomposition, its verifier, its
request planner, its readiness mechanism — and post-processes only the decoded plan. It reads nothing the
baseline was not already given: the returned-document identities are in the baseline's own actor JSON. The
difference from the baseline is that the rule is enforced rather than stated in a prompt.

The gate is per document. It never asks whether some artifact exists somewhere in the run.
"""
from __future__ import annotations

from typing import Any, Mapping

CONTRACT = "casepath.artifact-gate-b6/1.0.0"
CREDITED = frozenset({"received", "insufficient"})
MAX_REQUESTS = 2


def returned_document_ids(actor: Mapping[str, Any]) -> set[str]:
    """Documents an artifact has actually been returned for, from the actor the baseline already sees."""
    out: set[str] = set()
    for source in actor.get("sources", ()):
        doc = source.get("document_id") or source.get("provided_document_id")
        if doc:
            out.add(doc)
    return out


def apply(actor: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return the plan with the artifact rule enforced, plus a receipt of every change made."""
    returned = returned_document_ids(actor)
    catalog = {row["id"] if "id" in row else row.get("document_id") for row in actor.get("document_catalog", ())}
    pending = {row.get("document_id") for row in plan.get("pending_deliveries", ()) or ()}

    downgraded: list[dict[str, str]] = []
    states: list[dict[str, Any]] = []
    for row in plan.get("document_states", ()) or ():
        doc, state = row.get("document_id"), row.get("state")
        if state in CREDITED and doc not in returned:
            new_state = "pending" if doc in pending else "missing"
            downgraded.append({"document_id": doc, "from": state, "to": new_state})
            row = {**row, "state": new_state}
        states.append(row)

    gated: dict[str, Any] = {**plan, "document_states": states}
    ready = bool(plan.get("ready"))
    withdrew_readiness = False
    if downgraded and ready:
        gated["ready"] = False
        ready = False
        withdrew_readiness = True

    # A withdrawal can leave next_action inconsistent with the plan's own contract (proceed with nothing
    # outstanding). Re-point it at the documents the gate just reopened: the smallest repair that keeps the
    # baseline's plan valid, and what an engineer adding this rule would write.
    action = dict(plan.get("next_action") or {"kind": "wait", "document_ids": []})
    repaired_action = False
    if withdrew_readiness and action.get("kind") in {"proceed", "clarify"}:
        wanted = [d["document_id"] for d in downgraded if d["document_id"] in catalog][:MAX_REQUESTS]
        if wanted:
            action = {"kind": "request", "document_ids": wanted}
            gated["requested_document_ids"] = wanted
        else:
            action = {"kind": "wait", "document_ids": []}
            gated["requested_document_ids"] = []
        gated["next_action"] = action
        repaired_action = True

    gated["artifact_gate"] = {
        "contract": CONTRACT,
        "downgraded": downgraded,
        "withdrew_readiness": withdrew_readiness,
        "repaired_next_action": repaired_action,
        "returned_document_ids": sorted(returned),
    }
    return gated
