"""Strict contracts for proposition-specific CasePath traceability."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from manifests.digests import digest_json

from .schema import SourceLocator, StrictModel


class AuthoritySnapshotV3(StrictModel):
    snapshot_id: str = Field(min_length=1)
    jurisdiction: Literal["CH"]
    language: Literal["de"]
    source_url: str = Field(min_length=1)
    effective_date: date
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)


class AuthorityPassageV3(StrictModel):
    authority_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    article: str = Field(min_length=1)
    xml_eid: str = Field(pattern=r"^art_[a-z0-9_]+(?:/para(?:_[0-9]+)?)?$")
    exact_text: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_text_hash(self) -> AuthorityPassageV3:
        if self.text_sha256 != hashlib.sha256(self.exact_text.encode("utf-8")).hexdigest():
            raise ValueError("authority passage text hash is stale")
        return self


class AuthorityPassageBundleV3(StrictModel):
    contract: Literal["casepath.swiss-authority-passages/3.1.0"]
    extraction_identity: Literal["fedlex-akn3-visible-text-whitespace-normalization/1.0.0"]
    legal_status: Literal["official_german_federal_law_snapshot_research_mapping_not_legal_advice"]
    snapshots: tuple[AuthoritySnapshotV3, ...] = Field(min_length=1)
    passages: tuple[AuthorityPassageV3, ...] = Field(min_length=1)
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_bundle(self) -> AuthorityPassageBundleV3:
        snapshot_ids = [item.snapshot_id for item in self.snapshots]
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("authority snapshot IDs repeat")
        passage_ids = [item.authority_id for item in self.passages]
        if len(passage_ids) != len(set(passage_ids)):
            raise ValueError("authority passage IDs repeat")
        unknown = {item.snapshot_id for item in self.passages}.difference(snapshot_ids)
        if unknown:
            raise ValueError(f"authority passages reference unknown snapshots: {sorted(unknown)}")
        payload = self.model_dump(mode="json", exclude={"bundle_sha256"})
        if self.bundle_sha256 != digest_json(payload):
            raise ValueError("authority passage bundle hash is stale")
        return self


TraceSourceKindV3 = Literal[
    "case_invariant_rule",
    "swiss_authority_passage",
    "observable_message_span",
    "observable_attachment_inventory",
]


class TraceRegistryEntryV3(StrictModel):
    source_kind: TraceSourceKindV3
    display_value: str | tuple[dict[str, object], ...]
    locator: SourceLocator
    line_number: int | None = Field(default=None, ge=1)
    authority_id: str | None = None
    parent_artifact_id: str | None = None
    parent_artifact_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    representation_identity: str | None = None
    support_scope: Literal["normative", "case_specific", "availability"]


class ProvenanceChainExpectationV3(StrictModel):
    chain_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    fact_id: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    inherited_locators: tuple[SourceLocator, ...] = Field(min_length=1)


class TraceabilityContractV3(StrictModel):
    contract: Literal["casepath.traceability-contract/3.1.0"]
    case_id: str = Field(min_length=1)
    authority_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chain_expectations: tuple[ProvenanceChainExpectationV3, ...]
    contract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_hash(self) -> TraceabilityContractV3:
        if self.contract_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"contract_sha256"})
        ):
            raise ValueError("traceability contract hash is stale")
        chain_ids = [item.chain_id for item in self.chain_expectations]
        if len(chain_ids) != len(set(chain_ids)):
            raise ValueError("traceability chain IDs repeat")
        return self
