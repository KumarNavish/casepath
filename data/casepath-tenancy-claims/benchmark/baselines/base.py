"""Provider-neutral prediction interface with hard, auditable budget accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import ValidationError

from contracts.schema import (
    BudgetSpec,
    CandidateArtifact,
    FailureCode,
    ObservableClaimPacket,
    ProviderCallReceipt,
    UsageReceipt,
)

from .conditions import CONDITIONS, ConditionDefinition, ConditionId
from .custom_factorial_v3 import GenerativeConditionIdV3
from .stage_schema import validate_draft
from .verifier import ContractFreeVerifier, VerificationReceipt


class BudgetExceeded(RuntimeError):
    """Raised before a response is admitted when it exceeds the frozen budget."""


@dataclass(frozen=True)
class StageRequest:
    condition_id: ConditionId | GenerativeConditionIdV3
    stage: str
    packet: dict[str, Any]
    prior_stage_outputs: tuple[dict[str, Any], ...]
    budget: BudgetSpec


@dataclass(frozen=True)
class ModelCallResult:
    payload: dict[str, Any]
    input_tokens: int
    output_tokens: int
    tool_calls: int = 0
    retrieved_bytes: int = 0
    latency_ms: int = 0
    cost_usd: float | None = None
    provider_call: ProviderCallReceipt | None = None


class ModelAdapter(Protocol):
    """The only provider-specific boundary used by the causal conditions."""

    def invoke(self, request: StageRequest) -> ModelCallResult: ...


@dataclass
class BudgetLedger:
    budget: BudgetSpec
    attempted_model_calls: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    retrieved_bytes: int = 0
    latency_ms: int = 0
    cost_usd: float | None = 0.0
    failures: list[str] = field(default_factory=list)
    provider_calls: list[ProviderCallReceipt] = field(default_factory=list)

    def note_attempt(self) -> None:
        self.attempted_model_calls += 1

    def admit(self, result: ModelCallResult) -> None:
        if result.provider_call is not None and (
            result.provider_call.input_tokens != result.input_tokens
            or result.provider_call.output_tokens != result.output_tokens
        ):
            raise ValueError("provider-call usage must match the admitted model result")
        proposed = {
            "model_calls": self.model_calls + 1,
            "tool_calls": self.tool_calls + result.tool_calls,
            "input_tokens": self.input_tokens + result.input_tokens,
            "output_tokens": self.output_tokens + result.output_tokens,
            "retrieved_bytes": self.retrieved_bytes + result.retrieved_bytes,
        }
        limits = {
            "model_calls": self.budget.max_model_calls,
            "tool_calls": self.budget.max_tool_calls,
            "input_tokens": self.budget.max_input_tokens,
            "output_tokens": self.budget.max_output_tokens,
            "retrieved_bytes": self.budget.max_retrieved_bytes,
        }
        exceeded = {
            name: (proposed[name], limit)
            for name, limit in limits.items()
            if proposed[name] > limit
        }
        if exceeded:
            detail = ", ".join(
                f"{name}={observed}>{limit}" for name, (observed, limit) in sorted(exceeded.items())
            )
            self.failures.append(f"budget exceeded: {detail}")
            raise BudgetExceeded(detail)
        self.model_calls = proposed["model_calls"]
        self.tool_calls = proposed["tool_calls"]
        self.input_tokens = proposed["input_tokens"]
        self.output_tokens = proposed["output_tokens"]
        self.retrieved_bytes = proposed["retrieved_bytes"]
        self.latency_ms += result.latency_ms
        if self.cost_usd is None or result.cost_usd is None:
            self.cost_usd = None
        else:
            self.cost_usd += result.cost_usd
        if result.provider_call is not None:
            self.provider_calls.append(result.provider_call)

    def receipt(self) -> UsageReceipt:
        return UsageReceipt(
            attempted_model_calls=self.attempted_model_calls,
            model_calls=self.model_calls,
            tool_calls=self.tool_calls,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            retrieved_bytes=self.retrieved_bytes,
            latency_ms=self.latency_ms,
            cost_usd=self.cost_usd,
            failures=tuple(self.failures),
            model_backed=(self.model_calls > 0 and len(self.provider_calls) == self.model_calls),
            provider_calls=tuple(self.provider_calls),
        )


@dataclass(frozen=True)
class PredictionResult:
    condition: ConditionDefinition
    candidate: CandidateArtifact
    usage: UsageReceipt
    stage_outputs: tuple[dict[str, Any], ...]
    verification: VerificationReceipt | None


class PredictionFailure(RuntimeError):
    """Safe, auditable condition failure with no provider prose or candidate data."""

    def __init__(
        self,
        *,
        condition: ConditionDefinition,
        stage: str,
        failure_code: FailureCode,
        usage: UsageReceipt,
    ) -> None:
        super().__init__(f"{condition.condition_id} failed at {stage}: {failure_code}")
        self.condition = condition
        self.stage = stage
        self.failure_code = failure_code
        self.usage = usage


def _failure_code(exc: Exception) -> FailureCode:
    if isinstance(exc, BudgetExceeded):
        return "budget_exceeded"
    if exc.__class__.__name__ == "ProviderResponseError":
        return "provider_response_error"
    if isinstance(exc, ValidationError):
        return "schema_validation_error"
    if isinstance(exc, ValueError):
        return "invalid_output"
    return "execution_error"


class CasePathSystem:
    """Generate a frozen condition or derive B8 without hidden evaluator access."""

    def __init__(
        self,
        condition_id: ConditionId,
        adapter: ModelAdapter | None,
        *,
        verifier: ContractFreeVerifier | None = None,
    ) -> None:
        if condition_id not in CONDITIONS:
            raise ValueError(f"unknown condition: {condition_id}")
        self.condition = CONDITIONS[condition_id]
        self.adapter = adapter
        self.verifier = verifier
        if self.condition.deterministic_verifier and adapter is not None:
            raise ValueError("B8 derives from B7 and cannot have a model adapter")
        if not self.condition.deterministic_verifier and adapter is None:
            raise ValueError("model-generating conditions require a model adapter")
        if self.condition.deterministic_verifier and verifier is None:
            raise ValueError("B8 requires a contract-free verifier")
        if not self.condition.deterministic_verifier and verifier is not None:
            raise ValueError("only B8 may use the deterministic verifier")

    def predict(
        self,
        packet: ObservableClaimPacket | dict[str, Any],
        budget: BudgetSpec,
    ) -> PredictionResult:
        if self.condition.deterministic_verifier:
            raise ValueError("B8 must be derived from the admitted B7 prediction")
        observable_packet = (
            packet
            if isinstance(packet, ObservableClaimPacket)
            else ObservableClaimPacket.model_validate(packet)
        )
        if budget.source_snapshot_id != observable_packet.source_snapshot_id:
            raise ValueError("budget and observable packet use different source snapshots")
        if budget.source_snapshot_sha256 != observable_packet.source_snapshot_sha256:
            raise ValueError("budget does not bind the observable source bytes")
        packet_payload = observable_packet.model_dump(mode="json")
        outputs: list[dict[str, Any]] = []
        ledger = BudgetLedger(budget)
        stage = "not_started"
        try:
            assert self.adapter is not None
            for stage in self.condition.stages:
                ledger.note_attempt()
                result = self.adapter.invoke(
                    StageRequest(
                        condition_id=self.condition.condition_id,
                        stage=stage,
                        packet=packet_payload,
                        prior_stage_outputs=tuple(outputs),
                        budget=budget,
                    )
                )
                ledger.admit(result)
                final_stage = stage in {
                    "direct_finalize",
                    "document_first_finalize",
                    "evidence_from_process",
                    "exide_finalize",
                }
                outputs.append(
                    result.payload if final_stage else validate_draft(stage, result.payload)
                )
            if not outputs:
                raise RuntimeError("condition produced no stage outputs")
            stage = "candidate_validation"
            candidate_payload = outputs[-1].get("candidate", outputs[-1])
            candidate = CandidateArtifact.model_validate(candidate_payload)
        except Exception as exc:
            code = _failure_code(exc)
            if code not in ledger.failures:
                ledger.failures.append(code)
            raise PredictionFailure(
                condition=self.condition,
                stage=stage,
                failure_code=code,
                usage=ledger.receipt(),
            ) from exc
        return PredictionResult(
            condition=self.condition,
            candidate=candidate,
            usage=ledger.receipt(),
            stage_outputs=tuple(outputs),
            verification=None,
        )

    def derive_from_b7(
        self,
        b7_prediction: PredictionResult,
        packet: ObservableClaimPacket,
    ) -> PredictionResult:
        """Apply B8 only to the exact candidate admitted for B7."""

        if not self.condition.deterministic_verifier:
            raise ValueError("only B8 can derive from B7")
        if b7_prediction.condition.condition_id != "B7":
            raise ValueError("B8 requires a B7 source prediction")
        if b7_prediction.candidate.case_id != packet.case_id:
            raise ValueError("B7 candidate and observable packet use different cases")
        assert self.verifier is not None
        try:
            candidate, verification = self.verifier.verify(
                b7_prediction.candidate,
                packet.scenario,
            )
        except Exception as exc:
            code = _failure_code(exc)
            failures = (*b7_prediction.usage.failures, code)
            raise PredictionFailure(
                condition=self.condition,
                stage="deterministic_verifier",
                failure_code=code,
                usage=b7_prediction.usage.model_copy(update={"failures": failures}),
            ) from exc
        return PredictionResult(
            condition=self.condition,
            candidate=candidate,
            usage=b7_prediction.usage,
            stage_outputs=b7_prediction.stage_outputs,
            verification=verification,
        )
