from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, Protocol

from .common import digest_value
from .contracts import (
    CanonicalCaseInput,
    ModelArtifact,
    ModelBoundaryReceipt,
    ModelBoundaryResult,
)


class ModelBoundaryError(RuntimeError):
    pass


ExecutionKind = Literal["deterministic_reference", "offline_fake", "failing_test"]


class ProviderNeutralModel(Protocol):
    """Core model boundary with no provider, SDK, route, or credential dependency."""

    adapter_id: str
    execution_kind: ExecutionKind

    def invoke(self, request: CanonicalCaseInput) -> ModelArtifact: ...


class DeterministicReferenceAdapter:
    adapter_id = "casepath.deterministic-reference-adapter/1.0.0"
    execution_kind: ExecutionKind = "deterministic_reference"

    def __init__(self, artifacts: Mapping[str, ModelArtifact]) -> None:
        self._artifacts = dict(artifacts)

    def invoke(self, request: CanonicalCaseInput) -> ModelArtifact:
        artifact = self._artifacts.get(request.case_id)
        if artifact is None:
            raise ModelBoundaryError(
                f"no deterministic reference for {request.case_id}"
            )
        return artifact


class OfflineFakeAdapter:
    adapter_id = "casepath.offline-fake-adapter/1.0.0"
    execution_kind: ExecutionKind = "offline_fake"

    def __init__(self, artifacts: Mapping[str, ModelArtifact]) -> None:
        self._artifacts = dict(artifacts)

    def invoke(self, request: CanonicalCaseInput) -> ModelArtifact:
        artifact = self._artifacts.get(request.case_id)
        if artifact is None:
            raise ModelBoundaryError(
                f"offline fake has no fixture for {request.case_id}"
            )
        return artifact


class FailingTestAdapter:
    adapter_id = "casepath.failing-test-adapter/1.0.0"
    execution_kind: ExecutionKind = "failing_test"

    def invoke(self, request: CanonicalCaseInput) -> ModelArtifact:
        raise ModelBoundaryError(f"intentional failing-test adapter: {request.case_id}")


def execute_model_boundary(
    adapter: ProviderNeutralModel, request: CanonicalCaseInput
) -> ModelBoundaryResult:
    if adapter.execution_kind not in {"deterministic_reference", "offline_fake"}:
        raise ModelBoundaryError(
            f"adapter execution kind is not admissible for a successful run: {adapter.execution_kind}"
        )
    artifact = adapter.invoke(request)
    if artifact.case_id != request.case_id:
        raise ModelBoundaryError("adapter changed case identity")
    request_sha256 = digest_value(request.model_dump(mode="json"))
    output_sha256 = digest_value(artifact.model_dump(mode="json"))
    payload = {
        "contract": "casepath.model-boundary-receipt/1.0.0",
        "case_id": request.case_id,
        "adapter_id": adapter.adapter_id,
        "execution_kind": adapter.execution_kind,
        "request_sha256": request_sha256,
        "output_sha256": output_sha256,
        "adapter_invocations": 1,
        "model_calls": 0,
        "provider_calls": 0,
        "provider_credentials_read": False,
        "cost_usd": 0.0,
    }
    receipt = ModelBoundaryReceipt.model_validate(
        {**payload, "receipt_sha256": digest_value(payload)}
    )
    return ModelBoundaryResult(artifact=artifact, receipt=receipt)
