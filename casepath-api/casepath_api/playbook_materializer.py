from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .evidence_relations import apply_evidence_relations
from .foundation.common import digest_value
from .playbook_template import PlaybookTemplate, PlaybookTemplateError
from .projections import (
    apply_evidence_projection,
    apply_process_projection,
    checklist_derived_sections,
    decision_projection,
)
from .record_projector import project_record_driven_facts_v1


class PlaybookMaterializationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MaterializedCycleInputs:
    observable_package: dict[str, Any]
    facts: tuple[dict[str, Any], ...]
    process: dict[str, Any]
    checklist: dict[str, Any]
    verification: dict[str, Any]
    receipt: dict[str, Any]


def validate_template_cycle_artifacts_v1(
    *,
    template: PlaybookTemplate,
    claim_id: str,
    facts: Sequence[Mapping[str, Any]],
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
) -> tuple[str, ...]:
    """Validate one non-legacy cycle against the closed template catalog."""

    template.require_claim(claim_id)
    fact_values = [dict(value) for value in facts]
    fact_ids = [value.get("fact_id") for value in fact_values]
    if len(fact_ids) != len(set(fact_ids)) or any(
        not isinstance(value, str) or not value for value in fact_ids
    ):
        raise PlaybookMaterializationError("template fact roster is invalid")
    controlling = [
        value for value in fact_values if value.get("controls_process") is True
    ]
    if [value.get("fact_id") for value in controlling] != template.catalog[
        "process_fact_ids_by_claim"
    ][claim_id]:
        raise PlaybookMaterializationError(
            "template controlling-fact roster diverges"
        )
    if not controlling or len(controlling) > template.maximum_controlling_facts:
        raise PlaybookMaterializationError(
            "template controlling-fact budget is invalid"
        )
    for fact in controlling:
        decision_key = fact.get("decision_key")
        normalized = fact.get("normalized_value")
        if (
            decision_key not in template.decision_options
            or normalized not in template.decision_options[decision_key]
            or fact.get("decision_value")
            != template.decision_options[decision_key][normalized]
        ):
            raise PlaybookMaterializationError(
                "template fact is outside the decision catalog"
            )
    process_value = deepcopy(dict(process))
    if process_value.get("claim_id", claim_id) != claim_id:
        raise PlaybookMaterializationError("template process claim diverges")
    nodes = process_value.get("nodes")
    edges = process_value.get("edges")
    main_spine = process_value.get("main_spine")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not isinstance(
        main_spine, list
    ):
        raise PlaybookMaterializationError("template process topology is invalid")
    if [value.get("node_id") for value in nodes] != template.catalog[
        "process_node_ids"
    ] or [
        [value.get("source"), value.get("target")] for value in edges
    ] != template.catalog["process_edge_pairs"]:
        raise PlaybookMaterializationError("template process topology diverges")
    route = decision_projection(
        [
            {
                "controls_process": True,
                "decision_key": value["decision_key"],
                "decision_value": value["decision_value"],
            }
            for value in controlling
        ],
        route_program=template.route_program,
    )
    expected_overlay = apply_process_projection(
        nodes,
        edges,
        route,
        main_spine,
        rendering_profile=template.process_rendering_profile,
    )
    if (
        process_value.get("selected_path") != route["selected_path"]
        or process_value.get("current_node") != route["current_node"]
        or process_value.get("current_overlay") != expected_overlay
    ):
        raise PlaybookMaterializationError("template route projection diverges")
    items = checklist.get("items")
    if not isinstance(items, list):
        raise PlaybookMaterializationError("template checklist is invalid")
    expected_item_ids = template.catalog["evidence_item_ids_by_claim"][claim_id]
    if [value.get("item_id") for value in items] != expected_item_ids:
        raise PlaybookMaterializationError("template evidence roster diverges")
    expected_fact_ids = template.catalog["evidence_fact_ids_by_claim"][claim_id]
    expected_nodes = template.catalog["evidence_node_ids"]
    source_artifact_ids_by_fact = {
        fact["fact_id"]: {
            ref["artifact_id"]
            for ref in fact.get("source_refs", [])
            if isinstance(ref, Mapping)
            and isinstance(ref.get("artifact_id"), str)
        }
        for fact in fact_values
    }
    for item in items:
        item_id = item["item_id"]
        artifact_ids = item.get("artifact_ids")
        if (
            item.get("fact_id") != expected_fact_ids[item_id]
            or list(item.get("node_ids", [item.get("node_id")]))
            != list(expected_nodes[item_id])
            or not isinstance(artifact_ids, list)
            or (
                not artifact_ids
                and item.get("status")
                not in {"conditional", "missing", "not_required"}
            )
            or len(artifact_ids) != len(set(artifact_ids))
            or any(not isinstance(value, str) or not value for value in artifact_ids)
            or not set(artifact_ids)
            <= source_artifact_ids_by_fact.get(item["fact_id"], set())
        ):
            raise PlaybookMaterializationError(
                "template evidence relationship diverges"
            )
    projected_items = deepcopy(items)
    apply_evidence_relations(process_value, projected_items)
    apply_evidence_projection(
        projected_items,
        process_value,
        projection_mode=template.evidence_projection_mode,
    )
    apply_evidence_relations(process_value, projected_items)
    for actual, expected in zip(items, projected_items, strict=True):
        for field in ("current_path", "node_ids"):
            if actual.get(field) != expected.get(field):
                raise PlaybookMaterializationError(
                    "template evidence projection diverges"
                )
    return (
        "Closed template fact catalog",
        "Closed template process topology",
        "Deterministic template route projection",
        "Closed template evidence relationships",
    )


def validate_template_legal_context_v1(
    *, template: PlaybookTemplate, legal: Mapping[str, Any]
) -> tuple[str, ...]:
    """Bind a declarative playbook to its exact public legal-source catalog."""

    value = dict(legal)
    if set(value) != {"contract", "registry_version", "sources"}:
        raise PlaybookMaterializationError(
            "template legal-context field set is not closed"
        )
    if (
        not isinstance(value["contract"], str)
        or not value["contract"]
        or value["registry_version"]
        != template.catalog["legal_registry_version"]
        or not isinstance(value["sources"], list)
        or digest_value(value["sources"])
        != template.catalog["legal_sources_sha256"]
    ):
        raise PlaybookMaterializationError(
            "template legal context diverges from its catalog"
        )
    return (
        "Closed template legal-context schema",
        "Exact template legal registry and source digest",
    )


def build_template_cycle_verification_v1(
    *,
    template: PlaybookTemplate,
    facts: Sequence[Mapping[str, Any]],
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
) -> dict[str, Any]:
    process_value = dict(process)
    claim_id = process_value.get("claim_id")
    if not isinstance(claim_id, str):
        if len(template.supported_claim_ids) != 1:
            raise PlaybookMaterializationError(
                "template cycle claim identity is ambiguous"
            )
        claim_id = template.supported_claim_ids[0]
    checks = validate_template_cycle_artifacts_v1(
        template=template,
        claim_id=claim_id,
        facts=facts,
        process=process,
        checklist=checklist,
    )
    payload = {
        "contract": "casepath.template-cycle-verification/1.0.0",
        "computed": True,
        "valid": True,
        "playbook_template_sha256": template.template_sha256,
        "facts_sha256": digest_value(list(facts)),
        "process_sha256": digest_value(dict(process)),
        "checklist_sha256": digest_value(dict(checklist)),
        "whole_playbook_hash": digest_value(
            {"process": dict(process), "checklist": dict(checklist)}
        ),
        "check_names": list(checks),
        "release_gates_recomputed": True,
        "deterministic_authority": True,
        "rejected_proposals": [],
        "accepted_artifacts": [
            "canonical_claim_state",
            "legal_context",
            "process_graph",
            "evidence_model",
            "precedents",
        ],
        "model_calls": 0,
        "provider_calls": 0,
    }
    return {**payload, "receipt_sha256": digest_value(payload)}


def materialize_template_cycle_v1(
    *,
    template: PlaybookTemplate,
    claim_id: str,
    observable_package: Mapping[str, Any],
    observation_records: Sequence[Mapping[str, Any]] = (),
) -> MaterializedCycleInputs:
    """Materialize one bounded record for the existing six-role StateGraph."""

    try:
        record = template.declarative_record(claim_id)
    except PlaybookTemplateError as exc:
        raise PlaybookMaterializationError(str(exc)) from exc
    if set(record) != {"facts", "process", "checklist"}:
        raise PlaybookMaterializationError(
            "declarative record field set is not closed"
        )
    facts_value = record["facts"]
    process_value = record["process"]
    checklist_value = record["checklist"]
    if (
        not isinstance(facts_value, list)
        or not isinstance(process_value, Mapping)
        or not isinstance(checklist_value, Mapping)
    ):
        raise PlaybookMaterializationError("declarative record types are invalid")
    projection = project_record_driven_facts_v1(
        seed_facts=facts_value,
        observation_records=observation_records,
        decision_options=template.decision_options,
        fail_closed_values=template.fail_closed_normalized_values,
    )
    facts = [deepcopy(value) for value in projection.facts]
    controlling = [value for value in facts if value.get("controls_process") is True]
    if not controlling or len(controlling) > template.maximum_controlling_facts:
        raise PlaybookMaterializationError(
            "record controlling-fact count exceeds the template budget"
        )
    process = deepcopy(dict(process_value))
    if set(process) < {"nodes", "edges", "main_spine"}:
        raise PlaybookMaterializationError("process specification is incomplete")
    node_ids = [value.get("node_id") for value in process["nodes"]]
    edge_pairs = [
        [value.get("source"), value.get("target")] for value in process["edges"]
    ]
    if (
        node_ids != template.catalog["process_node_ids"]
        or edge_pairs != template.catalog["process_edge_pairs"]
    ):
        raise PlaybookMaterializationError(
            "process topology differs from the template"
        )
    route = decision_projection(
        [
            {
                "controls_process": True,
                "decision_key": value["decision_key"],
                "decision_value": value["decision_value"],
            }
            for value in controlling
        ],
        route_program=template.route_program,
    )
    process["nodes"] = deepcopy(process["nodes"])
    process["edges"] = deepcopy(process["edges"])
    process["current_node"] = route["current_node"]
    process["selected_path"] = list(route["selected_path"])
    process["current_overlay"] = apply_process_projection(
        process["nodes"],
        process["edges"],
        route,
        list(process["main_spine"]),
        rendering_profile=template.process_rendering_profile,
    )
    checklist = deepcopy(dict(checklist_value))
    items = checklist.get("items")
    if not isinstance(items, list):
        raise PlaybookMaterializationError("checklist items are invalid")
    expected_items = template.catalog["evidence_item_ids_by_claim"][claim_id]
    if [value.get("item_id") for value in items] != expected_items:
        raise PlaybookMaterializationError(
            "checklist item order differs from the template"
        )
    apply_evidence_relations(process, items)
    apply_evidence_projection(
        items,
        process,
        projection_mode=template.evidence_projection_mode,
    )
    apply_evidence_relations(process, items)
    checklist.update(checklist_derived_sections(items))
    verification = build_template_cycle_verification_v1(
        template=template,
        facts=facts,
        process=process,
        checklist=checklist,
    )
    package = deepcopy(dict(observable_package))
    receipt_payload = {
        "contract": "casepath.template-cycle-materialization/1.0.0",
        "template_sha256": template.template_sha256,
        "claim_id": claim_id,
        "observable_package_sha256": digest_value(package),
        "projector_receipt_sha256": projection.receipt["receipt_sha256"],
        "facts_sha256": digest_value(facts),
        "process_sha256": digest_value(process),
        "checklist_sha256": digest_value(checklist),
        "verification_sha256": verification["receipt_sha256"],
    }
    return MaterializedCycleInputs(
        observable_package=package,
        facts=tuple(facts),
        process=process,
        checklist=checklist,
        verification=verification,
        receipt={
            **receipt_payload,
            "receipt_sha256": digest_value(receipt_payload),
        },
    )


__all__ = [
    "MaterializedCycleInputs",
    "PlaybookMaterializationError",
    "build_template_cycle_verification_v1",
    "materialize_template_cycle_v1",
    "validate_template_cycle_artifacts_v1",
    "validate_template_legal_context_v1",
]
