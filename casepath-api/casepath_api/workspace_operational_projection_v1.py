from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from .claim_loop_contracts import ClaimLoopPhase, ClaimLoopState, ObligationStatus
from .foundation.common import digest_value


OPERATIONAL_PROJECTION_CONTRACT = "casepath.workspace-operational-projection/1.0.0"
EVIDENCE_CLASSES = (
    "received",
    "missing",
    "insufficient",
    "conditional",
    "irrelevant",
    "unknown",
)
_STATUS_CLASS = {
    "missing": "missing",
    "provided_insufficient": "insufficient",
    "conditional": "conditional",
    "not_applicable": "irrelevant",
    "present_unreviewed": "unknown",
    "conflicting": "unknown",
    "unknown": "unknown",
}
_KNOWN_RAW_STATUSES = frozenset((*_STATUS_CLASS, "provided_sufficient"))


class WorkspaceOperationalProjectionError(ValueError):
    pass


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise WorkspaceOperationalProjectionError(
            "operational projection timestamp is invalid"
        ) from exc
    if parsed.tzinfo is None:
        raise WorkspaceOperationalProjectionError(
            "operational projection timestamp lacks a timezone"
        )
    return parsed.astimezone(timezone.utc)


def _workspace_prefix(state: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "claim_id",
        "loop_id",
        "revision",
        "state_sha256",
        "last_event_sha256",
        "last_authoritative_update",
    }
    if not required.issubset(state):
        raise WorkspaceOperationalProjectionError("workspace prefix is incomplete")
    _timestamp(str(state["last_authoritative_update"]))
    return {
        "loop_id": state["loop_id"],
        "revision": state["revision"],
        "state_sha256": state["state_sha256"],
        "last_event_sha256": state["last_event_sha256"],
        "last_event_at": state["last_authoritative_update"],
    }


def _no_loop_projection(state: Mapping[str, Any]) -> dict[str, Any]:
    workspace_prefix = _workspace_prefix(state)
    failed = bool(state.get("failure_or_unknown_effect"))
    next_kind = "typed_failure" if failed else "start_processing"
    assessment = state.get("intake_assessment")
    current_node = (
        assessment.get("current_node")
        if isinstance(assessment, Mapping)
        and isinstance(assessment.get("current_node"), Mapping)
        else None
    )
    material = {
        "contract": OPERATIONAL_PROJECTION_CONTRACT,
        "claim_id": state["claim_id"],
        "workspace_prefix": workspace_prefix,
        "claim_loop_prefix": None,
        "current_process": (
            {
                "node_id": current_node.get("node_id"),
                "node_title": current_node.get("label"),
                "next_action_node_id": None,
                "selected_branch_id": None,
                "overlay_sha256": None,
            }
            if current_node is not None
            else None
        ),
        "controlling_decision": None,
        "evidence_items": [],
        "evidence_class_counts": {value: 0 for value in EVIDENCE_CLASSES},
        "workflow_state": state["workflow_state"],
        "readiness_state": state["readiness_state"],
        "principal_blocker": state["principal_blocker"],
        "pending_evidence_count": state["pending_evidence_count"],
        "next_state": {
            "kind": next_kind,
            "title": state["next_safe_action"],
            "action_id": None,
            "action_sha256": None,
            "terminal_mode": None,
        },
        "failure_or_unknown_effect": failed,
        "last_authoritative_update": state["last_authoritative_update"],
    }
    return {**material, "projection_sha256": digest_value(material)}


def _received_has_authority(
    *,
    fact: Mapping[str, Any],
    obligation: Any,
    provenance: set[tuple[str, str, str]],
) -> bool:
    return bool(
        fact.get("state") == "known"
        and obligation.status is ObligationStatus.SATISFIED
        and obligation.source_ref_ids
        and all(
            (obligation.fact_id, obligation.obligation_id, source_ref_id) in provenance
            for source_ref_id in obligation.source_ref_ids
        )
    )


def derive_workspace_operational_projection_v1(
    *,
    workspace_state: Mapping[str, Any],
    loop_state: ClaimLoopState | None,
    loop_events: Sequence[Any] = (),
    loop_journal_prefix: Mapping[str, Any] | None = None,
    expected_loop_id: str | None = None,
) -> dict[str, Any]:
    """Derive one UI/queue projection from validated append-only journals."""

    workspace_prefix = _workspace_prefix(workspace_state)
    if loop_state is None:
        if loop_events or loop_journal_prefix is not None:
            raise WorkspaceOperationalProjectionError(
                "loop events exist without a loop state"
            )
        return _no_loop_projection(workspace_state)
    state = ClaimLoopState.model_validate(loop_state.model_dump(mode="json"))
    if loop_journal_prefix is not None:
        if loop_events or set(loop_journal_prefix) != {
            "revision",
            "last_event_sha256",
            "last_event_at",
        }:
            raise WorkspaceOperationalProjectionError(
                "claim-loop compact prefix is invalid"
            )
        loop_event_count = loop_journal_prefix["revision"]
        loop_last_sha256 = loop_journal_prefix["last_event_sha256"]
        loop_last_at = loop_journal_prefix["last_event_at"]
    else:
        loop_event_count = len(loop_events)
        loop_last_sha256 = loop_events[-1].event_sha256 if loop_events else None
        loop_last_at = loop_events[-1].created_at if loop_events else None
    if (
        state.claim_id != workspace_state.get("claim_id")
        or expected_loop_id is None
        or state.loop_id != expected_loop_id
        or loop_event_count != state.revision
        or loop_event_count < 1
        or loop_last_sha256 != state.last_event_sha256
    ):
        raise WorkspaceOperationalProjectionError(
            "workspace and claim-loop prefixes do not join exactly"
        )
    binding = workspace_state.get("binding")
    assessment = workspace_state.get("intake_assessment")
    observable = state.accepted_artifacts.get("observable_package")
    workspace_binding = (
        observable.get("workspace_binding") if isinstance(observable, Mapping) else None
    )
    if (
        not isinstance(binding, Mapping)
        or not isinstance(assessment, Mapping)
        or not isinstance(workspace_binding, Mapping)
        or workspace_binding.get("binding_sha256") != binding.get("binding_sha256")
        or workspace_binding.get("intake_assessment_sha256")
        != assessment.get("assessment_sha256")
        or workspace_binding.get("static_template_sha256")
        != workspace_state.get("static_template_sha256")
        or state.accepted_artifacts.get("claim_id") != state.claim_id
    ):
        raise WorkspaceOperationalProjectionError(
            "claim-loop source authority differs from the workspace binding"
        )
    if not isinstance(loop_last_at, str):
        raise WorkspaceOperationalProjectionError(
            "claim-loop compact prefix lacks its timestamp"
        )
    _timestamp(loop_last_at)
    loop_prefix = {
        "loop_id": state.loop_id,
        "revision": state.revision,
        "phase": state.phase.value,
        "state_sha256": state.state_sha256,
        "last_event_sha256": state.last_event_sha256,
        "last_event_at": loop_last_at,
    }

    overlay = state.process.get("current_overlay")
    nodes = state.process.get("nodes")
    if not isinstance(overlay, Mapping) or not isinstance(nodes, list):
        raise WorkspaceOperationalProjectionError(
            "claim-loop process projection is invalid"
        )
    node_by_id: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        if (
            not isinstance(node, Mapping)
            or not isinstance(node.get("node_id"), str)
            or node["node_id"] in node_by_id
        ):
            raise WorkspaceOperationalProjectionError(
                "claim-loop process nodes are invalid"
            )
        node_by_id[node["node_id"]] = node
    current_node_id = overlay.get("current_node_id")
    current_node = node_by_id.get(current_node_id)
    if current_node is None:
        raise WorkspaceOperationalProjectionError(
            "current process node is outside the accepted process"
        )
    current_process = {
        "node_id": current_node_id,
        "node_title": current_node.get("title"),
        "next_action_node_id": overlay.get("next_action_node_id"),
        "selected_branch_id": overlay.get("selected_branch_id"),
        "overlay_sha256": digest_value(dict(overlay)),
    }

    items = state.checklist.get("items")
    if not isinstance(items, list):
        raise WorkspaceOperationalProjectionError("claim-loop checklist is invalid")
    fact_by_id: dict[str, Mapping[str, Any]] = {}
    for fact in state.facts:
        fact_id = fact.get("fact_id")
        if not isinstance(fact_id, str) or fact_id in fact_by_id:
            raise WorkspaceOperationalProjectionError(
                "claim-loop facts are duplicated or invalid"
            )
        fact_by_id[fact_id] = fact
    obligation_by_id = {value.obligation_id: value for value in state.obligations}
    if len(obligation_by_id) != len(state.obligations):
        raise WorkspaceOperationalProjectionError(
            "claim-loop obligations are duplicated"
        )
    provenance = {
        (value.fact_id, value.evidence_item_id, value.source_ref_id)
        for value in state.provenance_edges
    }
    evidence_items: list[dict[str, Any]] = []
    counts = {value: 0 for value in EVIDENCE_CLASSES}
    controlling: dict[str, Any] | None = None
    seen_item_ids: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise WorkspaceOperationalProjectionError(
                "claim-loop evidence item is invalid"
            )
        item_id = item.get("item_id")
        fact_id = item.get("fact_id")
        raw_status = item.get("status")
        if (
            not isinstance(item_id, str)
            or item_id in seen_item_ids
            or not isinstance(fact_id, str)
            or fact_id not in fact_by_id
            or item_id not in obligation_by_id
            or raw_status not in _KNOWN_RAW_STATUSES
        ):
            raise WorkspaceOperationalProjectionError(
                "claim-loop evidence joins are invalid"
            )
        seen_item_ids.add(item_id)
        fact = fact_by_id[fact_id]
        obligation = obligation_by_id[item_id]
        if obligation.fact_id != fact_id:
            raise WorkspaceOperationalProjectionError(
                "evidence obligation references another fact"
            )
        classification = (
            "received"
            if raw_status == "provided_sufficient"
            and _received_has_authority(
                fact=fact,
                obligation=obligation,
                provenance=provenance,
            )
            else "unknown"
            if raw_status == "provided_sufficient"
            else _STATUS_CLASS[raw_status]
        )
        counts[classification] += 1
        evidence = {
            "evidence_item_id": item_id,
            "title": item.get("title"),
            "fact_id": fact_id,
            "fact_state": fact.get("state"),
            "raw_status": raw_status,
            "evidence_class": classification,
            "obligation_status": obligation.status.value,
            "mandatory_now": obligation.mandatory_now,
            "current_path": bool(item.get("current_path")),
            "source_ref_ids": list(obligation.source_ref_ids),
            "provenance_edge_sha256s": sorted(
                digest_value(
                    {
                        "fact_id": value.fact_id,
                        "evidence_item_id": value.evidence_item_id,
                        "source_ref_id": value.source_ref_id,
                    }
                )
                for value in state.provenance_edges
                if value.evidence_item_id == item_id
            ),
        }
        evidence_items.append(evidence)
        if controlling is None and (
            obligation.mandatory_now
            or obligation.status is ObligationStatus.CONTRADICTED
        ):
            controlling = {
                "obligation_id": obligation.obligation_id,
                "fact_id": fact_id,
                "fact_state": fact.get("state"),
                "obligation_status": obligation.status.value,
                "evidence_item_id": item_id,
                "evidence_class": classification,
                "title": item.get("title"),
            }
    if set(obligation_by_id) != seen_item_ids or sum(counts.values()) != len(items):
        raise WorkspaceOperationalProjectionError(
            "claim-loop evidence classification is not exhaustive"
        )
    if (
        state.selected_action is not None
        and controlling is not None
        and (state.selected_action.evidence_item_id != controlling["evidence_item_id"])
    ):
        raise WorkspaceOperationalProjectionError(
            "selected action differs from the controlling obligation"
        )

    if state.phase is ClaimLoopPhase.DECISION_READY:
        if state.sufficiency.status.value != "decision_ready":
            raise WorkspaceOperationalProjectionError(
                "decision-ready phase lacks exact sufficiency"
            )
        workflow_state = "decision_ready"
        readiness_state = "decision_ready"
        blocker = "No current mandatory evidence obligation remains"
        next_state = {
            "kind": "decision_ready",
            "title": "Review certified decision-ready packet",
            "action_id": None,
            "action_sha256": None,
            "terminal_mode": state.terminal_mode,
        }
    elif state.phase is ClaimLoopPhase.ABSTAINED:
        if state.sufficiency.status.value != "abstain":
            raise WorkspaceOperationalProjectionError(
                "abstention phase lacks exact sufficiency"
            )
        workflow_state = "safe_abstention"
        readiness_state = "safe_abstention"
        blocker = state.abstain_reason or "Mandatory evidence remains unresolved"
        next_state = {
            "kind": "safe_abstention",
            "title": "Review safe abstention and unresolved evidence",
            "action_id": None,
            "action_sha256": None,
            "terminal_mode": state.terminal_mode,
        }
    elif state.phase is ClaimLoopPhase.DISPATCHING:
        workflow_state = "dispatching"
        readiness_state = "blocked"
        blocker = "One bounded evidence action is in flight"
        next_state = {
            "kind": "processing",
            "title": "Reconcile the in-flight evidence action",
            "action_id": (
                state.selected_action.action_id
                if state.selected_action is not None
                else None
            ),
            "action_sha256": (
                state.selected_action.action_sha256
                if state.selected_action is not None
                else None
            ),
            "terminal_mode": None,
        }
    elif state.selected_action is not None:
        workflow_state = "waiting_for_evidence"
        readiness_state = "blocked"
        blocker = (
            f"{controlling['title']} is {controlling['evidence_class']}"
            if controlling is not None
            else "The selected evidence action remains unresolved"
        )
        next_state = {
            "kind": "evidence_action",
            "title": state.selected_action.title,
            "action_id": state.selected_action.action_id,
            "action_sha256": state.selected_action.action_sha256,
            "terminal_mode": None,
        }
    else:
        workflow_state = "in_review"
        readiness_state = "blocked"
        blocker = (
            f"{controlling['title']} is {controlling['evidence_class']}"
            if controlling is not None
            else "The accepted journal is deriving its next bounded action"
        )
        next_state = {
            "kind": "processing",
            "title": "Derive the next bounded evidence action",
            "action_id": None,
            "action_sha256": None,
            "terminal_mode": None,
        }
    # An admitted, in-flight dispatch has a known operational state of its own.
    # It becomes an unknown effect only when the durable action history records
    # an unknown/failed outcome; otherwise healthy work would be falsely
    # prioritized and labelled as a safety failure.
    failure_or_unknown = any(
        value.outcome in {"failed", "unknown"} for value in state.action_history
    )
    last_update = max(
        (
            str(workspace_state["last_authoritative_update"]),
            loop_last_at,
        ),
        key=_timestamp,
    )
    material = {
        "contract": OPERATIONAL_PROJECTION_CONTRACT,
        "claim_id": state.claim_id,
        "workspace_prefix": workspace_prefix,
        "claim_loop_prefix": loop_prefix,
        "current_process": current_process,
        "controlling_decision": controlling,
        "evidence_items": evidence_items,
        "evidence_class_counts": counts,
        "workflow_state": workflow_state,
        "readiness_state": readiness_state,
        "principal_blocker": blocker,
        "pending_evidence_count": len(
            set(state.sufficiency.unresolved_mandatory_obligation_ids)
            | set(state.sufficiency.contradicted_obligation_ids)
        ),
        "next_state": next_state,
        "failure_or_unknown_effect": failure_or_unknown,
        "last_authoritative_update": last_update,
    }
    return {**material, "projection_sha256": digest_value(material)}


__all__ = [
    "EVIDENCE_CLASSES",
    "OPERATIONAL_PROJECTION_CONTRACT",
    "WorkspaceOperationalProjectionError",
    "derive_workspace_operational_projection_v1",
]
