from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .data import CLAIMS
from .evidence_relations import (
    BASE_EVIDENCE_NODE_IDS,
    BASE_PROCESS_EDGE_PAIRS,
    BASE_PROCESS_NODE_IDS,
    EVIDENCE_ITEM_IDS_BY_CLAIM,
)
from .fact_relations import (
    BASE_EVIDENCE_STATUS_BY_CLAIM,
    EVIDENCE_ARTIFACT_IDS_BY_CLAIM,
    EVIDENCE_FACT_ID_BY_CLAIM,
    PROCESS_FACT_IDS_BY_CLAIM,
)
from .foundation.common import canonical_json_bytes, digest_value, is_sha256
from .law_registry import LAW_REGISTRY_VERSION, LAW_SOURCES
from .projections import (
    DECISION_OPTIONS,
    FAIL_CLOSED_NORMALIZED_VALUE_BY_DECISION_KEY,
    MOULD_PROCESS_RENDERING_PROFILE,
    MOULD_ROUTE_PROGRAM,
)


class PlaybookTemplateError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PlaybookTemplate:
    """Immutable declarative catalog bound to one pipeline/StateGraph cycle."""

    contract: str
    template_id: str
    template_version: str
    supported_claim_ids: tuple[str, ...]
    template_sha256: str
    _catalog_json: bytes

    @classmethod
    def build(
        cls,
        *,
        template_id: str,
        template_version: str,
        catalog: Mapping[str, Any],
    ) -> "PlaybookTemplate":
        supported = tuple(catalog.get("supported_claim_ids", ()))
        if not supported or len(supported) != len(set(supported)):
            raise PlaybookTemplateError("template claim roster must be unique")
        required = {
            "supported_claim_ids",
            "claim_sha256_by_id",
            "decision_options",
            "process_node_ids",
            "process_edge_pairs",
            "process_fact_ids_by_claim",
            "evidence_item_ids_by_claim",
            "evidence_node_ids",
            "evidence_fact_ids_by_claim",
            "evidence_artifact_ids_by_claim",
            "base_evidence_status_by_claim",
            "legal_registry_version",
            "legal_sources_sha256",
            "same_six_agent_stategraph",
            "fail_closed_normalized_values",
            "route_program",
            "process_rendering_profile",
            "evidence_projection_mode",
            "evidence_artifact_capabilities",
            "maximum_controlling_facts",
            "materializer_mode",
            "declarative_records",
        }
        if set(catalog) != required:
            raise PlaybookTemplateError("template catalog field set is not closed")
        claim_keyed = (
            "claim_sha256_by_id",
            "process_fact_ids_by_claim",
            "evidence_item_ids_by_claim",
            "evidence_fact_ids_by_claim",
            "evidence_artifact_ids_by_claim",
            "base_evidence_status_by_claim",
        )
        if any(set(catalog[key]) != set(supported) for key in claim_keyed):
            raise PlaybookTemplateError("template claim-keyed catalogs diverge")
        decision_options = catalog["decision_options"]
        fail_closed = catalog["fail_closed_normalized_values"]
        if (
            not isinstance(decision_options, Mapping)
            or set(fail_closed) != set(decision_options)
            or any(
                fail_closed[key] not in decision_options[key]
                for key in decision_options
            )
        ):
            raise PlaybookTemplateError(
                "template decision catalog lacks a fail-closed value"
            )
        route_program = catalog["route_program"]
        steps = route_program.get("steps") if isinstance(route_program, Mapping) else None
        if (
            not isinstance(steps, list)
            or not steps
            or {step.get("decision_key") for step in steps}
            != set(decision_options)
        ):
            raise PlaybookTemplateError("template route program is incomplete")
        evidence_ids = {
            item_id
            for claim_items in catalog["evidence_item_ids_by_claim"].values()
            for item_id in claim_items
        }
        capabilities = catalog["evidence_artifact_capabilities"]
        if set(capabilities) != evidence_ids or any(
            not isinstance(values, list) or not values
            for values in capabilities.values()
        ):
            raise PlaybookTemplateError(
                "template evidence capability roster is incomplete"
            )
        maximum_controlling_facts = catalog["maximum_controlling_facts"]
        if (
            type(maximum_controlling_facts) is not int
            or not 1 <= maximum_controlling_facts <= 16
            or catalog["evidence_projection_mode"]
            not in {"mould_v20", "current_path_only_v1"}
            or catalog["same_six_agent_stategraph"] is not True
        ):
            raise PlaybookTemplateError("template execution profile is invalid")
        if (
            not isinstance(catalog["legal_registry_version"], str)
            or not catalog["legal_registry_version"]
            or not is_sha256(catalog["legal_sources_sha256"])
        ):
            raise PlaybookTemplateError("template legal catalog is invalid")
        materializer_mode = catalog["materializer_mode"]
        declarative_records = catalog["declarative_records"]
        if materializer_mode == "legacy_mould_v20":
            if declarative_records != {}:
                raise PlaybookTemplateError(
                    "legacy materializer cannot carry declarative records"
                )
        elif materializer_mode == "declarative_cycle_v1":
            if not isinstance(declarative_records, Mapping) or set(
                declarative_records
            ) != set(supported):
                raise PlaybookTemplateError(
                    "declarative materializer record roster is incomplete"
                )
        else:
            raise PlaybookTemplateError("template materializer mode is invalid")
        material = {
            "contract": "casepath.playbook-template/1.0.0",
            "template_id": template_id,
            "template_version": template_version,
            "catalog": dict(catalog),
        }
        raw = canonical_json_bytes(material)
        return cls(
            contract=material["contract"],
            template_id=template_id,
            template_version=template_version,
            supported_claim_ids=supported,
            template_sha256=digest_value(material),
            _catalog_json=raw,
        )

    @property
    def catalog(self) -> dict[str, Any]:
        return json.loads(self._catalog_json)["catalog"]

    @property
    def receipt(self) -> dict[str, Any]:
        payload = {
            "contract": self.contract,
            "template_id": self.template_id,
            "template_version": self.template_version,
            "template_sha256": self.template_sha256,
            "supported_claim_ids": list(self.supported_claim_ids),
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    @property
    def persisted_record(self) -> dict[str, Any]:
        """Return the self-contained catalog needed for deterministic replay."""

        payload = {
            "contract": "casepath.playbook-template-record/1.0.0",
            "template": self.receipt,
            "catalog": self.catalog,
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    @classmethod
    def from_persisted_record(
        cls, record: Mapping[str, Any]
    ) -> "PlaybookTemplate":
        value = dict(record)
        if set(value) != {
            "contract",
            "template",
            "catalog",
            "receipt_sha256",
        } or value.get("contract") != "casepath.playbook-template-record/1.0.0":
            raise PlaybookTemplateError("persisted template field set is invalid")
        payload = {key: item for key, item in value.items() if key != "receipt_sha256"}
        if value.get("receipt_sha256") != digest_value(payload):
            raise PlaybookTemplateError("persisted template receipt is invalid")
        identity = value.get("template")
        catalog = value.get("catalog")
        if not isinstance(identity, Mapping) or not isinstance(catalog, Mapping):
            raise PlaybookTemplateError("persisted template payload is invalid")
        rebuilt = cls.build(
            template_id=str(identity.get("template_id")),
            template_version=str(identity.get("template_version")),
            catalog=catalog,
        )
        if rebuilt.receipt != dict(identity) or rebuilt.persisted_record != value:
            raise PlaybookTemplateError("persisted template identity diverges")
        return rebuilt

    def require_claim(self, claim_id: str) -> None:
        if claim_id not in self.supported_claim_ids:
            raise PlaybookTemplateError("claim is outside the playbook template")

    @property
    def decision_options(self) -> dict[str, dict[str, str]]:
        return self.catalog["decision_options"]

    @property
    def fail_closed_normalized_values(self) -> dict[str, str]:
        return self.catalog["fail_closed_normalized_values"]

    @property
    def route_program(self) -> dict[str, Any]:
        return self.catalog["route_program"]

    @property
    def process_rendering_profile(self) -> dict[str, Any]:
        return self.catalog["process_rendering_profile"]

    @property
    def evidence_projection_mode(self) -> str:
        return str(self.catalog["evidence_projection_mode"])

    @property
    def evidence_artifact_capabilities(self) -> dict[str, tuple[str, ...]]:
        return {
            key: tuple(value)
            for key, value in self.catalog[
                "evidence_artifact_capabilities"
            ].items()
        }

    @property
    def maximum_controlling_facts(self) -> int:
        return int(self.catalog["maximum_controlling_facts"])

    @property
    def materializer_mode(self) -> str:
        return str(self.catalog["materializer_mode"])

    def declarative_record(self, claim_id: str) -> dict[str, Any]:
        self.require_claim(claim_id)
        if self.materializer_mode != "declarative_cycle_v1":
            raise PlaybookTemplateError(
                "template does not expose a declarative record"
            )
        return self.catalog["declarative_records"][claim_id]


_MOULD_EVIDENCE_ARTIFACT_CAPABILITIES = {
    "claim_message": ["claim_message"],
    "source_integrity": ["submitted_source"],
    "lease": ["lease"],
    "policy_reference": ["policy_reference"],
    "customer_objective": ["claim_message", "customer_correspondence"],
    "management_position": ["management_correspondence"],
    "health_safety_statement": [
        "claim_message",
        "customer_correspondence",
        "medical",
    ],
    "defect_notice": ["defect_notice", "customer_correspondence"],
    "proof_of_delivery": ["delivery_proof"],
    "dated_photos": ["photo"],
    "recurrence_chronology": ["timeline"],
    "technical_assessment": ["technical_report", "inspection_report"],
    "moisture_measurements": ["measurement_report"],
    "building_envelope": ["building_report", "technical_report"],
    "repair_history": ["maintenance_record", "management_correspondence"],
    "use_evidence": ["use_log", "utility_record"],
    "remediation_plan": ["remediation_plan", "maintenance_record"],
    "financial_impact": ["invoice", "financial_record"],
    "settlement_proposal": ["settlement_record", "correspondence"],
    "conciliation_bundle": ["legal_filing"],
    "completion_record": ["completion_record", "maintenance_record"],
}


_MOULD_CATALOG = {
    "supported_claim_ids": sorted(CLAIMS),
    "claim_sha256_by_id": {
        claim_id: digest_value(CLAIMS[claim_id]) for claim_id in sorted(CLAIMS)
    },
    "decision_options": DECISION_OPTIONS,
    "process_node_ids": list(BASE_PROCESS_NODE_IDS),
    "process_edge_pairs": [list(value) for value in BASE_PROCESS_EDGE_PAIRS],
    "process_fact_ids_by_claim": PROCESS_FACT_IDS_BY_CLAIM,
    "evidence_item_ids_by_claim": {
        key: list(value) for key, value in EVIDENCE_ITEM_IDS_BY_CLAIM.items()
    },
    "evidence_node_ids": {
        key: list(value) for key, value in BASE_EVIDENCE_NODE_IDS.items()
    },
    "evidence_fact_ids_by_claim": EVIDENCE_FACT_ID_BY_CLAIM,
    "evidence_artifact_ids_by_claim": EVIDENCE_ARTIFACT_IDS_BY_CLAIM,
    "base_evidence_status_by_claim": BASE_EVIDENCE_STATUS_BY_CLAIM,
    "legal_registry_version": LAW_REGISTRY_VERSION,
    "legal_sources_sha256": digest_value(LAW_SOURCES),
    "same_six_agent_stategraph": True,
    "fail_closed_normalized_values": (
        FAIL_CLOSED_NORMALIZED_VALUE_BY_DECISION_KEY
    ),
    "route_program": MOULD_ROUTE_PROGRAM,
    "process_rendering_profile": MOULD_PROCESS_RENDERING_PROFILE,
    "evidence_projection_mode": "mould_v20",
    "evidence_artifact_capabilities": (
        _MOULD_EVIDENCE_ARTIFACT_CAPABILITIES
    ),
    "maximum_controlling_facts": 6,
    "materializer_mode": "legacy_mould_v20",
    "declarative_records": {},
}

MOULD_PLAYBOOK_TEMPLATE = PlaybookTemplate.build(
    template_id="casepath.mould-playbook-template",
    template_version="20.0.0",
    catalog=_MOULD_CATALOG,
)


__all__ = [
    "MOULD_PLAYBOOK_TEMPLATE",
    "PlaybookTemplate",
    "PlaybookTemplateError",
]
