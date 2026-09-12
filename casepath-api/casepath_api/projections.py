from __future__ import annotations

from typing import Any


DECISION_OPTIONS = {
    "scope": {
        "supported_in_scope": "in_scope",
        "supported_out_of_scope": "out_of_scope",
        "unverified": "scope_unverified",
    },
    "dispute": {
        "present": "dispute_present",
        "absent": "no_dispute",
        "unverified": "dispute_unverified",
    },
    "urgency": {
        "urgent": "urgent",
        "not_urgent": "not_urgent",
        "unverified": "urgency_unverified",
    },
    "notification": {
        "notified": "notified",
        "not_notified": "not_notified",
        "unverified": "notification_unverified",
    },
    "recurrence": {
        "supported": "recurrence_supported",
        "not_supported": "recurrence_not_supported",
        "unverified": "recurrence_unverified",
    },
    "causation": {
        "building": "cause_building",
        "tenant_use": "cause_tenant_use",
        "mixed": "cause_mixed",
        "unresolved": "cause_unresolved",
    },
}
PROCESS_DECISION_KEYS = (
    "scope",
    "dispute",
    "urgency",
    "notification",
    "recurrence",
    "causation",
)

FAIL_CLOSED_NORMALIZED_VALUE_BY_DECISION_KEY = {
    "scope": "unverified",
    "dispute": "unverified",
    "urgency": "unverified",
    "notification": "unverified",
    "recurrence": "unverified",
    "causation": "unresolved",
}

MOULD_ROUTE_PROGRAM = {
    "start_path": ["intake"],
    "steps": [
        {
            "node_id": "scope",
            "decision_key": "scope",
            "transitions": {
                "in_scope": {"kind": "continue"},
                "out_of_scope": {
                    "kind": "stop",
                    "target_node_id": "out_of_scope",
                    "selected_branch_id": "out-of-scope",
                    "append_target": True,
                },
                "scope_unverified": {
                    "kind": "stop",
                    "target_node_id": "scope",
                    "selected_branch_id": "scope-unverified",
                    "append_target": False,
                },
            },
        },
        {
            "node_id": "dispute",
            "decision_key": "dispute",
            "transitions": {
                "dispute_present": {"kind": "continue"},
                "no_dispute": {
                    "kind": "stop",
                    "target_node_id": "no_dispute",
                    "selected_branch_id": "no-dispute",
                    "append_target": True,
                },
                "dispute_unverified": {
                    "kind": "stop",
                    "target_node_id": "dispute",
                    "selected_branch_id": "dispute-unverified",
                    "append_target": False,
                },
            },
        },
        {
            "node_id": "urgency",
            "decision_key": "urgency",
            "transitions": {
                "not_urgent": {"kind": "continue"},
                "urgent": {
                    "kind": "stop",
                    "target_node_id": "urgent_escalation",
                    "selected_branch_id": "urgent",
                    "append_target": True,
                },
                "urgency_unverified": {
                    "kind": "stop",
                    "target_node_id": "urgency",
                    "selected_branch_id": "urgency-unverified",
                    "append_target": False,
                },
            },
        },
        {
            "node_id": "notification",
            "decision_key": "notification",
            "transitions": {
                "notified": {"kind": "continue"},
                "not_notified": {
                    "kind": "stop",
                    "target_node_id": "formal_notice",
                    "selected_branch_id": "notice-gap",
                    "append_target": True,
                },
                "notification_unverified": {
                    "kind": "stop",
                    "target_node_id": "formal_notice",
                    "selected_branch_id": "notice-gap",
                    "append_target": True,
                },
            },
        },
        {
            "node_id": "defect",
            "decision_key": "recurrence",
            "transitions": {
                "recurrence_supported": {"kind": "continue"},
                "recurrence_not_supported": {
                    "kind": "stop",
                    "target_node_id": "defect",
                    "selected_branch_id": "recurrence-gap",
                    "append_target": False,
                },
                "recurrence_unverified": {
                    "kind": "stop",
                    "target_node_id": "defect",
                    "selected_branch_id": "recurrence-gap",
                    "append_target": False,
                },
            },
        },
        {
            "node_id": "causation",
            "decision_key": "causation",
            "transitions": {
                "cause_building": {
                    "kind": "stop",
                    "target_node_id": "building_defect",
                    "selected_branch_id": "building-defect",
                    "append_target": True,
                },
                "cause_tenant_use": {
                    "kind": "stop",
                    "target_node_id": "tenant_use",
                    "selected_branch_id": "tenant-use",
                    "append_target": True,
                },
                "cause_mixed": {
                    "kind": "stop",
                    "target_node_id": "mixed_cause",
                    "selected_branch_id": "mixed-cause",
                    "append_target": True,
                },
                "cause_unresolved": {
                    "kind": "stop",
                    "target_node_id": "evidence_gap",
                    "selected_branch_id": "insufficient",
                    "append_target": True,
                },
            },
        },
    ],
}

MOULD_PROCESS_RENDERING_PROFILE = {
    "answer_by_node": {
        "scope": {
            "in_scope": "In scope",
            "out_of_scope": "Outside scope",
            "scope_unverified": "Unverified",
        },
        "dispute": {
            "dispute_present": "Dispute established",
            "no_dispute": "No dispute established",
            "dispute_unverified": "Unverified",
        },
        "urgency": {
            "urgent": "Urgent",
            "not_urgent": "No acute concern reported",
            "urgency_unverified": "Unverified",
        },
        "notification": {
            "notified": "Notification established",
            "not_notified": "Not notified",
            "notification_unverified": "Unverified",
        },
        "defect": {
            "recurrence_supported": "Recurrence supported",
            "recurrence_not_supported": "Recurrence not supported",
            "recurrence_unverified": "Unverified",
        },
        "causation": {
            "cause_building": "Building-related cause supported",
            "cause_tenant_use": "Use-related cause supported",
            "cause_mixed": "Mixed cause supported",
            "cause_unresolved": "Unresolved",
        },
    },
    "blocked_node_ids": ["responsibility", "remedy"],
    "loop_edge_pairs": [["evidence_gap", "causation"]],
    "future_edge_sources": ["remedy", "escalation"],
}


def decision_projection(
    facts: list[dict[str, Any]],
    *,
    route_program: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project the active process route from typed fact decisions only."""

    program = route_program or MOULD_ROUTE_PROGRAM
    steps = program.get("steps")
    start_path = program.get("start_path")
    if not isinstance(steps, list) or not steps or not isinstance(start_path, list):
        raise ValueError("Process route program is invalid")
    decision_keys = tuple(step.get("decision_key") for step in steps)
    if any(not isinstance(key, str) or not key for key in decision_keys) or len(
        set(decision_keys)
    ) != len(decision_keys):
        raise ValueError("Process route decision keys are invalid")
    grouped: dict[str, list[str]] = {key: [] for key in decision_keys}
    for value in facts:
        key = value.get("decision_key")
        if key in grouped and value.get("controls_process") is True:
            grouped[key].append(value.get("decision_value"))
    invalid = [key for key, values in grouped.items() if len(values) != 1]
    if invalid:
        raise ValueError(
            f"Process projection requires exactly one controlling fact for {invalid}"
        )
    decisions = {key: values[0] for key, values in grouped.items()}

    route = list(start_path)
    step_index_by_node = {
        step.get("node_id"): index for index, step in enumerate(steps)
    }
    if len(step_index_by_node) != len(steps):
        raise ValueError("Process route step nodes are invalid")
    index = 0
    while index < len(steps):
        step = steps[index]
        node_id = step.get("node_id")
        decision_key = step["decision_key"]
        transitions = step.get("transitions")
        if not isinstance(node_id, str) or not isinstance(transitions, dict):
            raise ValueError("Process route step is invalid")
        if not route or route[-1] != node_id:
            route.append(node_id)
        transition = transitions.get(decisions[decision_key])
        if not isinstance(transition, dict):
            raise ValueError(
                f"Unsupported {decision_key} decision {decisions[decision_key]!r}"
            )
        if transition.get("kind") == "continue":
            index += 1
            continue
        if transition.get("kind") == "jump":
            target = transition.get("target_node_id")
            target_index = step_index_by_node.get(target)
            if (
                not isinstance(target, str)
                or target_index is None
                or target_index <= index
            ):
                raise ValueError("Process route jump is not forward and closed")
            index = target_index
            continue
        if transition.get("kind") != "stop":
            raise ValueError("Process route transition kind is invalid")
        target = transition.get("target_node_id")
        branch_id = transition.get("selected_branch_id")
        if not isinstance(target, str) or not isinstance(branch_id, str):
            raise ValueError("Process stop transition is incomplete")
        selected_path = [*route]
        if transition.get("append_target") is True and target != node_id:
            selected_path.append(target)
        return _projection(
            decisions, selected_path, node_id, target, branch_id
        )
    raise ValueError("Process route program has no terminal transition")


def _projection(
    decisions: dict[str, str],
    selected_path: list[str],
    current_node: str,
    next_action_node: str,
    selected_branch_id: str,
) -> dict[str, Any]:
    return {
        "decisions": decisions,
        "selected_path": selected_path,
        "current_node": current_node,
        "next_action_node": next_action_node,
        "selected_branch_id": selected_branch_id,
    }


def apply_process_projection(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    projection: dict[str, Any],
    main_spine: list[str],
    *,
    rendering_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply one fail-closed decision projection to the fixed graph template."""

    current = projection["current_node"]
    next_action = projection["next_action_node"]
    selected_path = projection["selected_path"]
    selected_pairs = set(zip(selected_path, selected_path[1:]))
    completed = selected_path[: selected_path.index(current)]
    spine_position = (
        main_spine.index(current) if current in main_spine else len(main_spine)
    )
    profile = rendering_profile or MOULD_PROCESS_RENDERING_PROFILE
    blocked_candidates = set(profile.get("blocked_node_ids", []))
    blocked = [
        node_id
        for node_id in main_spine[spine_position + 1 :]
        if node_id in blocked_candidates
    ]

    branch_targets: set[str] = set()
    answer_by_node: dict[str, str] = {}
    for node_id, answers in profile.get("answer_by_node", {}).items():
        decision_value = next(
            (
                value
                for value in projection["decisions"].values()
                if value in answers
            ),
            None,
        )
        if decision_value is not None:
            answer_by_node[node_id] = answers[decision_value]
    loop_edges = {
        tuple(value) for value in profile.get("loop_edge_pairs", [])
    }
    future_sources = set(profile.get("future_edge_sources", []))
    for node in nodes:
        branch_targets.update(
            branch["target"] for branch in node.get("branches", [])
        )
        if node["node_id"] in completed:
            node["state"] = "complete"
        elif node["node_id"] == current:
            node["state"] = "current"
        elif node["node_id"] == next_action:
            node["state"] = "next"
        elif node["node_id"] in blocked:
            node["state"] = "blocked"
        elif node["main_spine"]:
            node["state"] = "future"
        else:
            node["state"] = "inactive"
        if node["node_id"] in answer_by_node:
            node["answer"] = answer_by_node[node["node_id"]]
        elif node["main_spine"] and node["state"] in {"blocked", "future"}:
            node["answer"] = "Not reached"
        for branch in node.get("branches", []):
            branch["state"] = (
                "selected"
                if branch["branch_id"] == projection["selected_branch_id"]
                else "possible"
            )

    for value in edges:
        pair = (value["source"], value["target"])
        if pair in selected_pairs:
            value["state"] = "selected"
        elif pair in loop_edges:
            value["state"] = "loop"
        elif value["source"] in future_sources:
            value["state"] = "future"
        else:
            value["state"] = "possible"

    inactive_targets = sorted(branch_targets - {next_action, current})
    return {
        "completed_node_ids": completed,
        "current_node_id": current,
        "selected_branch_id": projection["selected_branch_id"],
        "blocked_node_ids": blocked,
        "inactive_branch_ids": inactive_targets,
        "next_action_node_id": next_action,
        "decisions": projection["decisions"],
    }


def apply_evidence_projection(
    items: list[dict[str, Any]],
    process: dict[str, Any],
    *,
    projection_mode: str = "mould_v20",
) -> None:
    """Project checklist relevance and statuses from the same typed decisions."""

    decisions = process["current_overlay"]["decisions"]
    by_id = {item["item_id"]: item for item in items}

    if projection_mode not in {"mould_v20", "current_path_only_v1"}:
        raise ValueError("Unsupported evidence projection mode")
    if projection_mode == "mould_v20" and decisions["urgency"] == "urgency_unverified":
        by_id["health_safety_statement"]["status"] = "missing"
        by_id["health_safety_statement"]["artifact_ids"] = []
        by_id["health_safety_statement"]["why"] = (
            "Current health, safety and deadline information is absent and must "
            "be established before ordinary handling continues."
        )

    if projection_mode == "mould_v20" and decisions["notification"] == "not_notified":
        for item_id in ("defect_notice", "proof_of_delivery"):
            by_id[item_id]["status"] = "missing"
            by_id[item_id]["artifact_ids"] = []
    elif projection_mode == "mould_v20" and decisions["notification"] == "notification_unverified":
        by_id["defect_notice"]["status"] = (
            "provided_insufficient"
            if by_id["defect_notice"]["artifact_ids"]
            else "missing"
        )
        by_id["proof_of_delivery"]["status"] = "missing"
        by_id["proof_of_delivery"]["artifact_ids"] = []

    if projection_mode == "mould_v20" and decisions["recurrence"] in {
        "recurrence_unverified",
        "recurrence_not_supported",
    }:
        by_id["dated_photos"]["status"] = (
            "provided_insufficient"
            if by_id["dated_photos"]["artifact_ids"]
            else "missing"
        )
        by_id["recurrence_chronology"]["status"] = "missing"

    cause = decisions.get("causation")

    def require_current_evidence(item_id: str) -> None:
        item = by_id[item_id]
        item["required_level"] = "mandatory"
        if not item.get("artifact_ids"):
            item["status"] = "missing"
        elif item.get("status") not in {
            "provided_sufficient",
            "provided_insufficient",
        }:
            # A record-driven artifact can make the requirement concrete, but
            # only the accepted projector/evidence gate may claim sufficiency.
            item["status"] = "provided_insufficient"

    if projection_mode == "mould_v20" and cause == "cause_building":
        require_current_evidence("building_envelope")
        by_id["use_evidence"]["status"] = "not_applicable"
    elif projection_mode == "mould_v20" and cause == "cause_tenant_use":
        by_id["building_envelope"]["status"] = "not_applicable"
        require_current_evidence("use_evidence")
    elif projection_mode == "mould_v20" and cause == "cause_mixed":
        for item_id in ("building_envelope", "use_evidence"):
            require_current_evidence(item_id)

    active_nodes = set(process["selected_path"]) | {
        process["current_overlay"]["next_action_node_id"]
    }
    for value in items:
        owner_node_ids = value.get("node_ids")
        if not isinstance(owner_node_ids, list) or not owner_node_ids:
            owner_node_ids = [value["node_id"]]
        value["current_path"] = bool(active_nodes.intersection(owner_node_ids))
        if (
            projection_mode == "current_path_only_v1"
            and value["current_path"]
            and value["status"] == "conditional"
        ):
            value["required_level"] = "mandatory"
            value["status"] = (
                "provided_insufficient"
                if value.get("artifact_ids")
                else "missing"
            )
            value["applies_when"] = "always"
        if not value["current_path"] and value["status"] == "missing":
            value["status"] = "conditional"
            value["required_level"] = "conditional"
            value["applies_when"] = (
                "One of the linked process nodes is reached: "
                + ", ".join(owner_node_ids)
            )
    if projection_mode == "mould_v20" and decisions["urgency"] == "urgency_unverified":
        by_id["health_safety_statement"]["status"] = "missing"
        by_id["health_safety_statement"]["artifact_ids"] = []
        by_id["health_safety_statement"]["required_level"] = "mandatory"


def checklist_derived_sections(
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the exact public checklist projections from authoritative items."""

    present: list[dict[str, Any]] = []
    required: list[dict[str, Any]] = []
    for evidence in items:
        if evidence["status"].startswith("provided"):
            present.append(
                {
                    "item_id": evidence["item_id"],
                    "title": evidence["title"],
                    "status": (
                        "available"
                        if evidence["status"] == "provided_sufficient"
                        else "insufficient"
                    ),
                    "node_id": evidence["node_id"],
                    "fact": evidence["fact_id"],
                    "why": evidence["why"],
                    "artifact_id": (
                        evidence["artifact_ids"][0]
                        if evidence["artifact_ids"]
                        else None
                    ),
                }
            )
        elif (
            evidence["status"] in {"missing", "conditional"}
            and evidence["current_path"]
        ):
            required.append(
                {
                    "item_id": evidence["item_id"],
                    "title": evidence["title"],
                    "status": (
                        "still_needed"
                        if evidence["status"] == "missing"
                        else "conditional"
                    ),
                    "node_id": evidence["node_id"],
                    "fact": evidence["fact_id"],
                    "why": evidence["why"],
                    "mandatory": (
                        "now"
                        if evidence["status"] == "missing"
                        else evidence["applies_when"]
                    ),
                    "already_supplied": False,
                }
            )
    summary = {
        "provided_sufficient": sum(
            item["status"] == "provided_sufficient" for item in items
        ),
        "provided_insufficient": sum(
            item["status"] == "provided_insufficient" for item in items
        ),
        "missing": sum(item["status"] == "missing" for item in items),
        "conditional": sum(item["status"] == "conditional" for item in items),
        "not_applicable": sum(
            item["status"] == "not_applicable" for item in items
        ),
        "process_nodes_covered": len(
            {
                node_id
                for item in items
                for node_id in item.get("node_ids", [item["node_id"]])
            }
        ),
    }
    return {"present": present, "required": required, "summary": summary}


__all__ = [
    "DECISION_OPTIONS",
    "FAIL_CLOSED_NORMALIZED_VALUE_BY_DECISION_KEY",
    "MOULD_PROCESS_RENDERING_PROFILE",
    "MOULD_ROUTE_PROGRAM",
    "PROCESS_DECISION_KEYS",
    "apply_evidence_projection",
    "apply_process_projection",
    "checklist_derived_sections",
    "decision_projection",
]
