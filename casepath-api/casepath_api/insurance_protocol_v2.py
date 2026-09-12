from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .foundation.common import canonical_json_bytes, digest_value, is_sha256
from .claim_loop_contracts import EvidenceAction
from .foundation.contracts import FoundationModel
from .insurance_protocol_v1 import (
    InsuranceProtocolRecordSetV1,
    SourceObservationV1,
)


def _sha256(value: str) -> str:
    if not is_sha256(value):
        raise ValueError("value must be a lowercase SHA-256 digest")
    return value


def _self_hash(model: FoundationModel, field: str) -> None:
    if digest_value(model.model_dump(mode="json", exclude={field})) != getattr(
        model, field
    ):
        raise ValueError(f"{field} self-hash mismatch")


class InterpretationDecisionProposalV2(FoundationModel):
    """Non-authoritative proposal to apply one admitted interpretation."""

    contract: Literal["casepath.interpretation-decision-proposal/2.0.0"] = (
        "casepath.interpretation-decision-proposal/2.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    source_observation_sha256: str
    normalized_assertion_sha256: str
    interpretation_sha256: str
    source_state_sha256: str
    source_revision: int = Field(ge=1)
    proposed_transition: Literal["APPLY_INTERPRETATION_AND_REPLAN"]
    proposed_at: str
    authoritative: Literal[False] = False
    proposal_sha256: str

    @field_validator(
        "source_observation_sha256",
        "normalized_assertion_sha256",
        "interpretation_sha256",
        "source_state_sha256",
        "proposal_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _sha256(value)

    @model_validator(mode="after")
    def validate_proposal(self) -> InterpretationDecisionProposalV2:
        _self_hash(self, "proposal_sha256")
        return self


class NormalizedAssertionV2(FoundationModel):
    """Observation-derived assertion without policy interpretation content."""

    contract: Literal["casepath.normalized-assertion/2.0.0"] = (
        "casepath.normalized-assertion/2.0.0"
    )
    source_observation_sha256: str
    fact_id: str
    evidence_item_id: str
    fact_state: Literal["known", "unknown", "conflicting"]
    normalized_value: str | None
    extraction_method: str
    extraction_method_source_sha256: str
    claim_observation_sha256: str
    source_ref_sha256s: tuple[str, ...] = Field(min_length=1)
    assertion_sha256: str

    @field_validator(
        "source_observation_sha256",
        "extraction_method_source_sha256",
        "claim_observation_sha256",
        "assertion_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _sha256(value)

    @field_validator("source_ref_sha256s")
    @classmethod
    def validate_source_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("assertion source references must be unique")
        return tuple(_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_assertion(self) -> NormalizedAssertionV2:
        _self_hash(self, "assertion_sha256")
        return self


class InterpretationV2(FoundationModel):
    contract: Literal["casepath.interpretation/2.0.0"] = "casepath.interpretation/2.0.0"
    assertion_sha256: str
    canonical_interpretation_receipt_sha256: str
    prior_fact_sha256: str
    assertion_catalog_sha256: str
    selected_assertion_id: str | None
    playbook_template_sha256: str
    policy_version: str
    status: Literal["supported", "insufficient", "disputed"]
    interpretation_sha256: str

    @field_validator(
        "assertion_sha256",
        "canonical_interpretation_receipt_sha256",
        "prior_fact_sha256",
        "assertion_catalog_sha256",
        "playbook_template_sha256",
        "interpretation_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _sha256(value)

    @model_validator(mode="after")
    def validate_interpretation(self) -> InterpretationV2:
        _self_hash(self, "interpretation_sha256")
        return self


class InterpretationDecisionRecordV2(FoundationModel):
    contract: Literal["casepath.interpretation-decision-record/2.0.0"] = (
        "casepath.interpretation-decision-record/2.0.0"
    )
    proposal_sha256: str
    interpretation_sha256: str
    authority: Literal["deterministic_claim_loop_authority_v1"]
    authority_policy_version: Literal["casepath.interpretation-replan-authority/2.0.0"]
    disposition: Literal["AUTHORIZE_JOURNALED_REPLAN"]
    decided_at: str
    decision_sha256: str

    @field_validator("proposal_sha256", "interpretation_sha256", "decision_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _sha256(value)

    @model_validator(mode="after")
    def validate_record(self) -> InterpretationDecisionRecordV2:
        _self_hash(self, "decision_sha256")
        return self


class InterpretationActionIntentV2(FoundationModel):
    contract: Literal["casepath.interpretation-action-intent/2.0.0"] = (
        "casepath.interpretation-action-intent/2.0.0"
    )
    proposal_sha256: str
    decision_sha256: str
    interpretation_sha256: str
    expected_parent_state_sha256: str
    expected_parent_revision: int = Field(ge=1)
    transition_id: Literal[
        "casepath.internal-transition.apply-interpretation-and-replan/2.0.0"
    ]
    created_at: str
    intent_sha256: str

    @field_validator(
        "proposal_sha256",
        "decision_sha256",
        "interpretation_sha256",
        "expected_parent_state_sha256",
        "intent_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _sha256(value)

    @model_validator(mode="after")
    def validate_intent(self) -> InterpretationActionIntentV2:
        _self_hash(self, "intent_sha256")
        return self


class InterpretationActionReceiptV2(FoundationModel):
    contract: Literal["casepath.interpretation-action-receipt/2.0.0"] = (
        "casepath.interpretation-action-receipt/2.0.0"
    )
    intent_sha256: str
    status: Literal["committed"] = "committed"
    committed_event_sha256: str
    resulting_state_sha256: str
    resulting_revision: int = Field(ge=1)
    committed_at: str
    receipt_sha256: str

    @field_validator(
        "intent_sha256",
        "committed_event_sha256",
        "resulting_state_sha256",
        "receipt_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _sha256(value)

    @model_validator(mode="after")
    def validate_receipt(self) -> InterpretationActionReceiptV2:
        _self_hash(self, "receipt_sha256")
        return self


class InsuranceThinWaistRecordSetV2(FoundationModel):
    """Canonical post-source chain in its required semantic order."""

    contract: Literal["casepath.insurance-thin-waist-record-set/2.0.0"] = (
        "casepath.insurance-thin-waist-record-set/2.0.0"
    )
    source_observation: SourceObservationV1
    normalized_assertion: NormalizedAssertionV2
    interpretation: InterpretationV2
    decision_proposal: InterpretationDecisionProposalV2
    decision_record: InterpretationDecisionRecordV2
    action_intent: InterpretationActionIntentV2
    action_receipt: InterpretationActionReceiptV2 | None = None
    source_registration_record_set_sha256: str
    record_set_sha256: str

    @field_validator("source_registration_record_set_sha256", "record_set_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _sha256(value)

    @model_validator(mode="after")
    def validate_chain(self) -> InsuranceThinWaistRecordSetV2:
        if (
            self.decision_proposal.session_id != self.source_observation.session_id
            or self.decision_proposal.loop_id != self.source_observation.loop_id
            or self.decision_proposal.claim_id != self.source_observation.claim_id
            or self.decision_proposal.record_version
            != self.source_observation.record_version
            or self.normalized_assertion.source_observation_sha256
            != self.source_observation.observation_sha256
            or self.interpretation.assertion_sha256
            != self.normalized_assertion.assertion_sha256
            or self.decision_proposal.source_observation_sha256
            != self.source_observation.observation_sha256
            or self.decision_proposal.normalized_assertion_sha256
            != self.normalized_assertion.assertion_sha256
            or self.decision_proposal.interpretation_sha256
            != self.interpretation.interpretation_sha256
            or self.decision_record.proposal_sha256
            != self.decision_proposal.proposal_sha256
            or self.decision_record.interpretation_sha256
            != self.interpretation.interpretation_sha256
            or self.action_intent.proposal_sha256
            != self.decision_proposal.proposal_sha256
            or self.action_intent.decision_sha256
            != self.decision_record.decision_sha256
            or self.action_intent.interpretation_sha256
            != self.interpretation.interpretation_sha256
            or self.action_intent.expected_parent_state_sha256
            != self.decision_proposal.source_state_sha256
            or self.action_intent.expected_parent_revision
            != self.decision_proposal.source_revision
            or self.decision_record.decided_at != self.decision_proposal.proposed_at
            or self.action_intent.created_at != self.decision_proposal.proposed_at
        ):
            raise ValueError(
                "source, assertion, interpretation and decision lineage diverged"
            )
        if self.action_receipt is not None and (
            self.action_receipt.intent_sha256 != self.action_intent.intent_sha256
            or self.action_receipt.resulting_revision
            != self.action_intent.expected_parent_revision + 1
            or self.action_receipt.committed_at != self.decision_proposal.proposed_at
        ):
            raise ValueError("replan action receipt does not bind its intent")
        _self_hash(self, "record_set_sha256")
        return self


class CorrectionDeltaProjectionV1(FoundationModel):
    """Replay-derived, case-local correction receipt exposed to the product."""

    contract: Literal["casepath.correction-delta-projection/1.0.0"] = (
        "casepath.correction-delta-projection/1.0.0"
    )
    event_type: Literal["CORRECTION_APPLIED", "CORRECTION_REUSED"]
    event_sha256: str
    correction_id: str
    correction_sha256: str
    correction_artifact_receipt_sha256: str
    fact_id: str
    evidence_item_id: str
    before_fact_sha256: str
    after_fact_sha256: str
    before_evidence_sha256: str
    after_evidence_sha256: str
    unrelated_facts_before_sha256: str
    unrelated_facts_after_sha256: str
    delta_sha256: str

    @field_validator(
        "event_sha256",
        "correction_sha256",
        "correction_artifact_receipt_sha256",
        "before_fact_sha256",
        "after_fact_sha256",
        "before_evidence_sha256",
        "after_evidence_sha256",
        "unrelated_facts_before_sha256",
        "unrelated_facts_after_sha256",
        "delta_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _sha256(value)

    @model_validator(mode="after")
    def validate_delta(self) -> CorrectionDeltaProjectionV1:
        if self.before_fact_sha256 == self.after_fact_sha256:
            raise ValueError("correction projection does not change its target fact")
        if (
            self.unrelated_facts_before_sha256
            != self.unrelated_facts_after_sha256
        ):
            raise ValueError("correction projection spills outside its fact scope")
        _self_hash(self, "delta_sha256")
        return self


class VersionedCaseStateV2(FoundationModel):
    """Replay-derived projection exposing both registration and replan authority."""

    contract: Literal["casepath.versioned-case-state/2.0.0"] = (
        "casepath.versioned-case-state/2.0.0"
    )
    session_id: str
    loop_id: str
    claim_id: str
    record_version: str
    base_revision: int = Field(ge=1)
    base_state_sha256: str
    last_event_sha256: str
    protocol_status: Literal[
        "not_started",
        "intent_journaled",
        "execution_started",
        "dispatch_unknown",
        "cancelled",
        "receipt_recorded",
        "source_observed",
        "assertion_normalized",
        "interpreted",
        "replan_receipt_pending",
        "replanned",
    ]
    protocol_event_sha256s: tuple[str, ...]
    record_set: InsuranceProtocolRecordSetV1 | None = None
    thin_waist_record_set: InsuranceThinWaistRecordSetV2 | None = None
    pending_intent_sha256: str | None = None
    next_action: EvidenceAction | None = None
    terminal_mode: Literal["finalize", "abstain"] | None = None
    decision_ready_packet_sha256: str | None = None
    correction_count: int = Field(default=0, ge=0)
    latest_correction: CorrectionDeltaProjectionV1 | None = None
    projection_sha256: str

    @field_validator(
        "base_state_sha256",
        "last_event_sha256",
        "pending_intent_sha256",
        "decision_ready_packet_sha256",
        "projection_sha256",
    )
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is not None:
            return _sha256(value)
        return value

    @field_validator("protocol_event_sha256s")
    @classmethod
    def validate_event_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("protocol event identities must be unique")
        return tuple(_sha256(item) for item in value)

    @model_validator(mode="after")
    def validate_projection(self) -> VersionedCaseStateV2:
        if self.protocol_status == "not_started":
            if (
                self.record_set is not None
                or self.thin_waist_record_set is not None
                or self.protocol_event_sha256s
            ):
                raise ValueError("not-started projection cannot claim protocol records")
        elif self.record_set is None or not self.protocol_event_sha256s:
            raise ValueError("active protocol projection requires replay evidence")
        if self.thin_waist_record_set is not None and (
            self.record_set is None
            or self.thin_waist_record_set.source_registration_record_set_sha256
            != self.record_set.record_set_sha256
        ):
            raise ValueError("thin-waist projection changed registration authority")
        if self.protocol_status == "replan_receipt_pending":
            if (
                self.thin_waist_record_set is None
                or self.thin_waist_record_set.action_receipt is not None
                or self.pending_intent_sha256
                != self.thin_waist_record_set.action_intent.intent_sha256
            ):
                raise ValueError("pending replan projection is incomplete")
        elif self.protocol_status == "replanned":
            if (
                self.thin_waist_record_set is None
                or self.thin_waist_record_set.action_receipt is None
                or self.pending_intent_sha256 is not None
            ):
                raise ValueError("completed replan projection is incomplete")
        elif self.pending_intent_sha256 is not None and (
            self.record_set is None
            or self.pending_intent_sha256 != self.record_set.intent.intent_sha256
        ):
            raise ValueError("pending registration intent differs from replay")
        if self.protocol_status == "cancelled" and (
            self.pending_intent_sha256 is not None
        ):
            raise ValueError("cancelled projection cannot claim a pending intent")
        if (self.correction_count == 0) != (self.latest_correction is None):
            raise ValueError("correction count and replay-derived delta diverged")
        _self_hash(self, "projection_sha256")
        return self


def build_thin_waist_replan_intent_v2(
    *,
    session_id: str,
    loop_id: str,
    claim_id: str,
    record_version: str,
    source_state_sha256: str,
    source_revision: int,
    records: InsuranceProtocolRecordSetV1,
    timestamp: str,
) -> InsuranceThinWaistRecordSetV2:
    """Deterministically derive the successor chain from admitted V1 authority."""

    source = records.source_observation
    assertion = records.normalized_assertion
    legacy_interpretation = records.interpretation
    if source is None or assertion is None or legacy_interpretation is None:
        raise ValueError(
            "canonical replan intent requires the complete epistemic prefix"
        )
    normalized_payload = {
        "contract": "casepath.normalized-assertion/2.0.0",
        "source_observation_sha256": source.observation_sha256,
        "fact_id": assertion.fact_id,
        "evidence_item_id": assertion.evidence_item_id,
        "fact_state": assertion.fact_state,
        "normalized_value": assertion.normalized_value,
        "extraction_method": assertion.extraction_method,
        "extraction_method_source_sha256": (assertion.extraction_method_source_sha256),
        "claim_observation_sha256": assertion.claim_observation_sha256,
        "source_ref_sha256s": [
            digest_value(value.model_dump(mode="json"))
            for value in assertion.claim_observation.source_refs
        ],
    }
    normalized = NormalizedAssertionV2.model_validate(
        {
            **normalized_payload,
            "assertion_sha256": digest_value(normalized_payload),
        }
    )
    interpretation_payload = {
        "contract": "casepath.interpretation/2.0.0",
        "assertion_sha256": normalized.assertion_sha256,
        "canonical_interpretation_receipt_sha256": (
            legacy_interpretation.canonical_interpretation_receipt_sha256
        ),
        "prior_fact_sha256": legacy_interpretation.prior_fact_sha256,
        "assertion_catalog_sha256": (legacy_interpretation.assertion_catalog_sha256),
        "selected_assertion_id": legacy_interpretation.selected_assertion_id,
        "playbook_template_sha256": (legacy_interpretation.playbook_template_sha256),
        "policy_version": legacy_interpretation.policy_version,
        "status": legacy_interpretation.status,
    }
    interpretation = InterpretationV2.model_validate(
        {
            **interpretation_payload,
            "interpretation_sha256": digest_value(interpretation_payload),
        }
    )
    proposal_payload = {
        "contract": "casepath.interpretation-decision-proposal/2.0.0",
        "session_id": session_id,
        "loop_id": loop_id,
        "claim_id": claim_id,
        "record_version": record_version,
        "source_observation_sha256": source.observation_sha256,
        "normalized_assertion_sha256": normalized.assertion_sha256,
        "interpretation_sha256": interpretation.interpretation_sha256,
        "source_state_sha256": source_state_sha256,
        "source_revision": source_revision,
        "proposed_transition": "APPLY_INTERPRETATION_AND_REPLAN",
        "proposed_at": timestamp,
        "authoritative": False,
    }
    proposal = InterpretationDecisionProposalV2.model_validate(
        {
            **proposal_payload,
            "proposal_sha256": digest_value(proposal_payload),
        }
    )
    decision_payload = {
        "contract": "casepath.interpretation-decision-record/2.0.0",
        "proposal_sha256": proposal.proposal_sha256,
        "interpretation_sha256": interpretation.interpretation_sha256,
        "authority": "deterministic_claim_loop_authority_v1",
        "authority_policy_version": ("casepath.interpretation-replan-authority/2.0.0"),
        "disposition": "AUTHORIZE_JOURNALED_REPLAN",
        "decided_at": timestamp,
    }
    decision = InterpretationDecisionRecordV2.model_validate(
        {
            **decision_payload,
            "decision_sha256": digest_value(decision_payload),
        }
    )
    intent_payload = {
        "contract": "casepath.interpretation-action-intent/2.0.0",
        "proposal_sha256": proposal.proposal_sha256,
        "decision_sha256": decision.decision_sha256,
        "interpretation_sha256": interpretation.interpretation_sha256,
        "expected_parent_state_sha256": source_state_sha256,
        "expected_parent_revision": source_revision,
        "transition_id": (
            "casepath.internal-transition.apply-interpretation-and-replan/2.0.0"
        ),
        "created_at": timestamp,
    }
    intent = InterpretationActionIntentV2.model_validate(
        {**intent_payload, "intent_sha256": digest_value(intent_payload)}
    )
    return hash_thin_waist_record_set_v2(
        {
            "contract": "casepath.insurance-thin-waist-record-set/2.0.0",
            "source_observation": source.model_dump(mode="json"),
            "normalized_assertion": normalized.model_dump(mode="json"),
            "interpretation": interpretation.model_dump(mode="json"),
            "decision_proposal": proposal.model_dump(mode="json"),
            "decision_record": decision.model_dump(mode="json"),
            "action_intent": intent.model_dump(mode="json"),
            "action_receipt": None,
            "source_registration_record_set_sha256": records.record_set_sha256,
        }
    )


def hash_thin_waist_record_set_v2(
    payload: dict[str, Any],
) -> InsuranceThinWaistRecordSetV2:
    return InsuranceThinWaistRecordSetV2.model_validate_json(
        canonical_json_bytes({**payload, "record_set_sha256": digest_value(payload)})
    )


__all__ = [
    "CorrectionDeltaProjectionV1",
    "InsuranceThinWaistRecordSetV2",
    "InterpretationActionIntentV2",
    "InterpretationActionReceiptV2",
    "InterpretationDecisionProposalV2",
    "InterpretationDecisionRecordV2",
    "InterpretationV2",
    "NormalizedAssertionV2",
    "VersionedCaseStateV2",
    "build_thin_waist_replan_intent_v2",
    "hash_thin_waist_record_set_v2",
]
