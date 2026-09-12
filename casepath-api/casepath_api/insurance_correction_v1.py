from __future__ import annotations

from .claim_loop import CorrectionToolResult
from .claim_loop_contracts import (
    ClaimLoopState,
    CorrectionEffect,
    ToolArtifactReceipt,
)


class MouldNeutralAssessmentCorrectionAdapterV1:
    """Provider-free, case-local correction fixture for the generated claim.

    It can only downgrade the exact admitted neutral-assessment assertion to
    insufficient.  It cannot select another case, fact, evidence item, or
    normalized branch value.
    """

    adapter_id = "casepath.correction.mould-neutral-assessment/1.0.0"

    def execute(
        self,
        *,
        source_artifact: ToolArtifactReceipt,
        state: ClaimLoopState,
        timestamp: str,
    ) -> CorrectionToolResult:
        observation = source_artifact.observation
        if (
            source_artifact.session_id != state.session_id
            or source_artifact.loop_id != state.loop_id
            or source_artifact.artifact_source_version != state.record_version
            or observation.fact_id != "fact_cause"
            or observation.evidence_item_id != "technical_assessment"
            or observation.fact_state != "known"
            or observation.normalized_value != "building"
            or observation.evidence_status != "provided_sufficient"
            or len(observation.source_refs) != 1
        ):
            raise ValueError(
                "correction source is not the admitted neutral assessment"
            )
        effect = CorrectionEffect(
            fact_id=observation.fact_id,
            evidence_item_id=observation.evidence_item_id,
            value="Correction receipt: the assessment is not decision-sufficient.",
            fact_state="unknown",
            normalized_value=None,
            explanation=(
                "The case-local deterministic correction withdraws only the "
                "technical assessment's decision-bearing sufficiency."
            ),
            evidence_status="provided_insufficient",
        )
        return CorrectionToolResult(
            effect=effect,
            issuer_id=self.adapter_id,
            provenance_note=(
                "Generated public synthetic correction fixture; case-local, "
                f"provider-free, and issued at {timestamp}."
            ),
        )


class MouldNeutralAssessmentRollbackAdapterV1:
    """Restore the exact admitted assertion after one scoped withdrawal.

    This is a rollback authority, not a second source of truth.  It can only
    restore the observation already admitted by the local artifact registry,
    and only when the current loop contains exactly one matching correction.
    """

    adapter_id = "casepath.correction.mould-neutral-assessment-rollback/1.0.0"

    def execute(
        self,
        *,
        source_artifact: ToolArtifactReceipt,
        state: ClaimLoopState,
        timestamp: str,
    ) -> CorrectionToolResult:
        observation = source_artifact.observation
        if (
            source_artifact.session_id != state.session_id
            or source_artifact.loop_id != state.loop_id
            or source_artifact.artifact_source_version != state.record_version
            or observation.fact_id != "fact_cause"
            or observation.evidence_item_id != "technical_assessment"
            or observation.fact_state != "known"
            or observation.normalized_value != "building"
            or observation.evidence_status != "provided_sufficient"
            or len(observation.source_refs) != 1
            or len(state.corrections) != 1
            or state.corrections[0].effect.fact_id != observation.fact_id
            or state.corrections[0].effect.evidence_item_id
            != observation.evidence_item_id
            or state.corrections[0].effect.fact_state != "unknown"
            or state.corrections[0].effect.evidence_status
            != "provided_insufficient"
        ):
            raise ValueError(
                "rollback is not bound to one withdrawn neutral assessment"
            )
        effect = CorrectionEffect(
            fact_id=observation.fact_id,
            evidence_item_id=observation.evidence_item_id,
            value=observation.value,
            fact_state=observation.fact_state,
            normalized_value=observation.normalized_value,
            explanation=observation.explanation,
            evidence_status="provided_sufficient",
        )
        return CorrectionToolResult(
            effect=effect,
            issuer_id=self.adapter_id,
            provenance_note=(
                "Rollback of the single case-local correction, derived only from "
                f"the admitted source observation at {timestamp}."
            ),
        )


__all__ = [
    "MouldNeutralAssessmentCorrectionAdapterV1",
    "MouldNeutralAssessmentRollbackAdapterV1",
]
