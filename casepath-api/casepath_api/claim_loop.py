from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol
import unicodedata

from .claim_loop_contracts import (
    AcquisitionReceiptV1,
    AcceptedCycleArtifactsV1,
    ActionHistoryEntry,
    BoundActivity,
    CanonicalFactInterpretationV1,
    ClaimLoopPhase,
    ClaimLoopState,
    ClaimObservation,
    ClaimSourceRef,
    CorrectionArtifactReceipt,
    CorrectionEffect,
    CorrectionReuseReceipt,
    DecisionReadyPacket,
    EvidenceAction,
    NativeProposalRevisionV1,
    ObligationState,
    ObligationStatus,
    ProjectionLedgerEntry,
    ProvenanceEdge,
    ScopedCorrection,
    SixAgentCycleReceipt,
    SufficiencyState,
    SufficiencyStatus,
    ToolArtifactReceipt,
    ToolResultStatus,
    claim_loop_internal_event_key_v1,
    load_claim_loop_event_v1,
)
from .claim_loop_cycle import (
    ClaimLoopCycleError,
    build_accepted_role_artifacts_v1,
    derive_graph_activity_v1,
    validate_accepted_role_artifacts_v1,
    validate_cycle_receipt_graph_binding_v1,
)
from .evidence_relations import (
    MEMORY_EXTENSION_EDGE_PAIRS,
    MEMORY_EXTENSION_NODE_IDS,
    apply_evidence_relations,
)
from .fact_relations import validate_fact_relations
from .foundation.common import canonical_json_bytes, digest_text, digest_value, is_sha256
from .insurance_protocol_v1 import (
    ActionReceiptStatus,
    InsuranceProtocolRecordSetV1,
)
from .insurance_protocol_v2 import (
    InsuranceThinWaistRecordSetV2,
    build_thin_waist_replan_intent_v2,
)
from .playbook_template import (
    MOULD_PLAYBOOK_TEMPLATE,
    PlaybookTemplate,
    PlaybookTemplateError,
)
from .playbook_materializer import (
    PlaybookMaterializationError,
    validate_template_cycle_artifacts_v1,
    validate_template_legal_context_v1,
)
from .projections import (
    apply_evidence_projection,
    apply_process_projection,
    checklist_derived_sections,
    decision_projection,
)
from .record_projector import project_record_driven_facts_v1
from .validation import (
    ContractValidationError,
    validate_current_state,
    validate_evidence_model,
    validate_legal_context,
    validate_process_graph,
)


class ClaimLoopError(ValueError):
    pass


DEFAULT_EVIDENCE_TOOL_ID = "casepath.claim-evidence-adapter/1.0.0"


def _source_closure_digest_v1(files: Mapping[str, bytes]) -> str:
    return digest_value(
        {
            "contract": "casepath.executable-source-closure/1.0.0",
            "files": [
                {
                    "path": relative_path,
                    "file_sha256": sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                }
                for relative_path, raw in sorted(files.items())
            ],
        }
    )


def _artifact_interpreter_source_closure_sha256_v1() -> str:
    """Hash the exact local source closure trusted to interpret artifacts."""

    package_root = Path(__file__).resolve().parent
    relative_paths = (
        "claim_loop.py",
        "claim_loop_contracts.py",
        "foundation/common.py",
        "foundation/contracts.py",
        "playbook_template.py",
    )
    return _source_closure_digest_v1(
        {
            relative_path: (package_root / relative_path).read_bytes()
            for relative_path in relative_paths
        }
    )


def playbook_template_from_accepted_v1(
    accepted: Mapping[str, Any],
) -> PlaybookTemplate:
    identity = accepted.get("playbook_template")
    record = accepted.get("playbook_template_record")
    if not isinstance(identity, Mapping):
        raise ClaimLoopError("accepted playbook has no template identity")
    if record is None:
        if dict(identity) != MOULD_PLAYBOOK_TEMPLATE.receipt:
            raise ClaimLoopError("accepted playbook lacks its template catalog")
        return MOULD_PLAYBOOK_TEMPLATE
    if not isinstance(record, Mapping):
        raise ClaimLoopError("accepted playbook template record is invalid")
    try:
        template = PlaybookTemplate.from_persisted_record(record)
    except PlaybookTemplateError as exc:
        raise ClaimLoopError(str(exc)) from exc
    if template.receipt != dict(identity):
        raise ClaimLoopError("accepted playbook template identity diverges")
    return template


def _valid_custom_correction_source_binding_v1(
    value: Any,
    *,
    correction: ScopedCorrection,
    authority: CorrectionArtifactReceipt,
    source_artifact: ToolArtifactReceipt,
    correction_source_artifact: Any,
    correction_source_refs: Any,
) -> bool:
    if not isinstance(value, Mapping) or not isinstance(
        correction_source_artifact, Mapping
    ):
        return False
    if not isinstance(correction_source_refs, list) or not correction_source_refs:
        return False
    try:
        refs = tuple(
            ClaimSourceRef.model_validate(row) for row in correction_source_refs
        )
    except (TypeError, ValueError):
        return False
    ref = correction.source_ref
    if (
        refs[0] != ref
        or any(
            source.source_id != ref.source_id
            or source.source_sha256 != ref.source_sha256
            or source.locator_kind != "text_quote"
            for source in refs
        )
    ):
        return False
    for source in refs:
        page = next(
            (
                row
                for row in correction_source_artifact.get("extracted_pages", [])
                if isinstance(row, Mapping) and row.get("page") == source.page
            ),
            None,
        )
        text = page.get("text") if isinstance(page, Mapping) else None
        if (
            correction_source_artifact.get("artifact_id") != source.source_id
            or correction_source_artifact.get("sha256") != source.source_sha256
            or not isinstance(text, str)
            or digest_text(text) != source.source_sha256
            or source.text_start is None
            or source.text_end is None
            or source.text_end > len(text)
            or text[source.text_start : source.text_end]
            != source.sanitized_excerpt
            or source.span_sha256 != digest_text(source.sanitized_excerpt or "")
        ):
            return False
    expected = {
        "contract": "casepath.correction-source-binding/1.0.0",
        "authority_adapter_id": authority.authority_adapter_id,
        "target_artifact_receipt_sha256": source_artifact.receipt_sha256,
        "target_observation_sha256": (
            source_artifact.observation.observation_sha256
        ),
        "target_fact_id": source_artifact.observation.fact_id,
        "target_evidence_item_id": source_artifact.observation.evidence_item_id,
        "correction_id": correction.correction_id,
        "correction_source_ref_sha256": digest_value(
            correction.source_ref.model_dump(mode="json")
        ),
        "correction_source_refs_sha256": digest_value(
            [source.model_dump(mode="json") for source in refs]
        ),
        "correction_source_artifact_sha256": digest_value(
            dict(correction_source_artifact)
        ),
    }
    return set(value) == {*expected, "binding_sha256"} and value == {
        **expected,
        "binding_sha256": digest_value(expected),
    }


def _zero_activity(scope: Literal["incremental_loop"]) -> BoundActivity:
    return BoundActivity(
        scope=scope,
        graph_traversal_count=0,
        model_calls=0,
        provider_calls=0,
        activity_receipt_sha256s=(),
        execution_identity_sha256s=(),
        credential_access_status="none_due_to_zero_provider_calls",
        credential_access_receipt_sha256s=(),
        cost_status="exact",
        cost_usd=0.0,
    )


def bound_activity_from_cycle_receipt_v1(
    *,
    scope: Literal["source_acceptance", "incremental_loop"],
    receipt: SixAgentCycleReceipt,
) -> BoundActivity:
    """Project immutable activity only from the bound cycle receipt."""

    return BoundActivity(
        scope=scope,
        graph_traversal_count=1,
        model_calls=receipt.model_calls,
        provider_calls=receipt.provider_calls,
        activity_receipt_sha256s=(receipt.receipt_sha256,),
        execution_identity_sha256s=(receipt.graph_audit_sha256,),
        credential_access_status=receipt.credential_access_status,
        credential_access_receipt_sha256s=(
            receipt.credential_access_receipt_sha256s
        ),
        cost_status=receipt.cost_status,
        cost_usd=receipt.cost_usd,
    )


def _upstream_activity_from_graph_audit_v1(
    audit: Mapping[str, Any] | None,
) -> BoundActivity:
    if audit is None:
        return BoundActivity(
            scope="upstream_source_run",
            graph_traversal_count=0,
            model_calls=0,
            provider_calls=0,
            activity_receipt_sha256s=(),
            execution_identity_sha256s=(),
            credential_access_status="none_due_to_zero_provider_calls",
            credential_access_receipt_sha256s=(),
            cost_status="exact",
            cost_usd=0.0,
        )
    try:
        calls, cost_status, cost_usd = derive_graph_activity_v1(audit)
    except ClaimLoopCycleError as exc:
        raise ClaimLoopError(str(exc)) from exc
    audit_sha256 = digest_value(dict(audit))
    return BoundActivity(
        scope="upstream_source_run",
        graph_traversal_count=1,
        model_calls=calls,
        provider_calls=calls,
        activity_receipt_sha256s=(audit_sha256,),
        execution_identity_sha256s=(audit_sha256,),
        credential_access_status=(
            "not_measured"
            if calls > 0
            else "none_due_to_zero_provider_calls"
        ),
        credential_access_receipt_sha256s=(),
        cost_status=cost_status,
        cost_usd=cost_usd,
    )


def _validate_cycle_evidence_v1(
    *,
    receipt: SixAgentCycleReceipt,
    verification: Mapping[str, Any],
    graph_audit: Mapping[str, Any],
) -> None:
    try:
        validate_cycle_receipt_graph_binding_v1(
            receipt=receipt,
            graph_audit=graph_audit,
        )
    except ClaimLoopCycleError as exc:
        raise ClaimLoopError(str(exc)) from exc
    if receipt.verification_sha256 != digest_value(dict(verification)):
        raise ClaimLoopError(
            "cycle verification differs from its immutable receipt"
        )


def _incremental_activity(
    activity: BoundActivity,
    receipt: SixAgentCycleReceipt,
) -> BoundActivity:
    if activity.scope != "incremental_loop":
        raise ClaimLoopError("incremental activity scope is invalid")
    receipt_activity = bound_activity_from_cycle_receipt_v1(
        scope="incremental_loop",
        receipt=receipt,
    )
    credential_status = (
        "receipt_bound"
        if (
            activity.credential_access_status == "receipt_bound"
            or receipt_activity.credential_access_status == "receipt_bound"
        )
        else "not_measured"
        if (
            activity.credential_access_status == "not_measured"
            or receipt_activity.credential_access_status == "not_measured"
        )
        else "none_due_to_zero_provider_calls"
    )
    exact_cost = (
        activity.cost_status == "exact"
        and receipt_activity.cost_status == "exact"
    )
    return BoundActivity(
        scope="incremental_loop",
        graph_traversal_count=activity.graph_traversal_count + 1,
        model_calls=activity.model_calls + receipt.model_calls,
        provider_calls=activity.provider_calls + receipt.provider_calls,
        activity_receipt_sha256s=(
            *activity.activity_receipt_sha256s,
            receipt.receipt_sha256,
        ),
        execution_identity_sha256s=(
            *activity.execution_identity_sha256s,
            receipt.graph_audit_sha256,
        ),
        credential_access_status=credential_status,
        credential_access_receipt_sha256s=(
            *activity.credential_access_receipt_sha256s,
            *receipt.credential_access_receipt_sha256s,
        ),
        cost_status="exact" if exact_cost else "unknown",
        cost_usd=(
            round((activity.cost_usd or 0.0) + (receipt.cost_usd or 0.0), 8)
            if exact_cost
            else None
        ),
    )


def _total_activity(
    upstream: BoundActivity,
    source: BoundActivity,
    incremental: BoundActivity,
) -> BoundActivity:
    activities = (upstream, source, incremental)
    source_reuses_upstream = bool(
        upstream.graph_traversal_count == 1
        and source.graph_traversal_count == 1
        and upstream.execution_identity_sha256s
        == source.execution_identity_sha256s
    )
    if source_reuses_upstream and (
        upstream.model_calls != source.model_calls
        or upstream.provider_calls != source.provider_calls
        or upstream.cost_status != source.cost_status
        or upstream.cost_usd != source.cost_usd
    ):
        raise ClaimLoopError("aliased source activity metrics diverged")
    accounted = (
        (upstream, incremental)
        if source_reuses_upstream
        else activities
    )
    credential_status = (
        "receipt_bound"
        if any(
            value.credential_access_status == "receipt_bound"
            for value in accounted
        )
        else "not_measured"
        if any(
            value.credential_access_status == "not_measured"
            for value in accounted
        )
        else "none_due_to_zero_provider_calls"
    )
    exact_cost = all(value.cost_status == "exact" for value in accounted)
    execution_identities = tuple(
        dict.fromkeys(
            identity
            for value in activities
            for identity in value.execution_identity_sha256s
        )
    )
    return BoundActivity(
        scope="total_bound",
        graph_traversal_count=len(execution_identities),
        model_calls=sum(value.model_calls for value in accounted),
        provider_calls=sum(value.provider_calls for value in accounted),
        activity_receipt_sha256s=tuple(
            receipt
            for value in activities
            for receipt in value.activity_receipt_sha256s
        ),
        execution_identity_sha256s=execution_identities,
        credential_access_status=credential_status,
        credential_access_receipt_sha256s=tuple(
            receipt
            for value in activities
            for receipt in value.credential_access_receipt_sha256s
        ),
        cost_status="exact" if exact_cost else "unknown",
        cost_usd=(
            round(sum(value.cost_usd or 0.0 for value in accounted), 8)
            if exact_cost
            else None
        ),
    )


class EvidenceToolAdapter(Protocol):
    adapter_id: str
    implementation_id: str
    implementation_source_sha256: str
    implementation_sha256: str

    def execute(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        idempotency_key: str,
        timestamp: str,
    ) -> "ToolResult": ...


class EvidenceArtifactInterpreter(Protocol):
    """Server-owned authority that interprets one raw artifact within a catalog."""

    implementation_id: str
    implementation_source_sha256: str

    def interpret(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
    ) -> CanonicalFactInterpretationV1: ...


class CorrectionToolAdapter(Protocol):
    """Server-configured authority that proposes one typed correction effect."""

    adapter_id: str

    def execute(
        self,
        *,
        source_artifact: ToolArtifactReceipt,
        state: ClaimLoopState,
        timestamp: str,
    ) -> "CorrectionToolResult": ...


class CorrectionToolResult:
    def __init__(
        self,
        *,
        effect: "CorrectionEffect",
        issuer_kind: Literal[
            "deterministic_tool", "human_optional", "model_optional"
        ] = "deterministic_tool",
        issuer_id: str,
        provenance_note: str,
        model_calls: int = 0,
        provider_calls: int = 0,
        provider_credentials_read: bool = False,
        cost_usd: float = 0.0,
    ) -> None:
        if (
            model_calls != 0
            or provider_calls != 0
            or provider_credentials_read
            or cost_usd != 0.0
        ):
            raise ClaimLoopError(
                "the correction authority result must be provider-free"
            )
        self.effect = effect
        self.issuer_kind = issuer_kind
        self.issuer_id = issuer_id
        self.provenance_note = provenance_note
        self.model_calls = model_calls
        self.provider_calls = provider_calls
        self.provider_credentials_read = provider_credentials_read
        self.cost_usd = cost_usd


class ToolResult:
    def __init__(
        self,
        *,
        status: ToolResultStatus,
        sanitized_content: str | None = None,
        artifact_source_version: str | None = None,
        artifact_page_count: int | None = None,
        source_locator: str,
        reason: str | None = None,
    ) -> None:
        if status is ToolResultStatus.OBSERVED and not sanitized_content:
            raise ClaimLoopError("observed tool result requires sanitized content")
        if status is ToolResultStatus.OBSERVED and (
            not artifact_source_version
            or not isinstance(artifact_page_count, int)
            or isinstance(artifact_page_count, bool)
            or artifact_page_count != 1
        ):
            raise ClaimLoopError(
                "v1 observed tool result requires single-page artifact metadata"
            )
        if status is not ToolResultStatus.OBSERVED and sanitized_content is not None:
            raise ClaimLoopError("failed tool result cannot carry artifact content")
        if not isinstance(source_locator, str) or not source_locator:
            raise ClaimLoopError("tool result requires a server-owned source locator")
        if len(source_locator) > 2000:
            raise ClaimLoopError("tool result source locator is too long")
        if status is not ToolResultStatus.OBSERVED and (
            not isinstance(reason, str) or not reason or len(reason) > 300
        ):
            raise ClaimLoopError("non-observed tool result requires a bounded reason")
        if status is ToolResultStatus.OBSERVED and reason is not None:
            raise ClaimLoopError("observed tool result cannot carry a failure reason")
        self.status = status
        self.sanitized_content = sanitized_content
        self.artifact_source_version = artifact_source_version
        self.artifact_page_count = artifact_page_count
        self.source_locator = source_locator
        self.reason = reason


def adapter_implementation_sha256_v1(
    *,
    adapter_id: str,
    implementation_id: str,
    implementation_source_sha256: str,
) -> str:
    if len(implementation_source_sha256) != 64 or any(
        value not in "0123456789abcdef" for value in implementation_source_sha256
    ):
        raise ClaimLoopError(
            "adapter implementation source must be a lowercase SHA-256"
        )
    return digest_value(
        {
            "contract": "casepath.adapter-implementation-identity/1.1.0",
            "adapter_id": adapter_id,
            "implementation_id": implementation_id,
            "implementation_source_sha256": implementation_source_sha256,
        }
    )


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ClaimLoopError("timestamps require a timezone")
    return parsed


def _self_hashed_observation(payload: dict[str, Any]) -> ClaimObservation:
    return ClaimObservation.model_validate(
        {**payload, "observation_sha256": digest_value(payload)}
    )


def _source_ref_id(value: ClaimSourceRef) -> str:
    return f"source-ref.{digest_value(value.model_dump(mode='json'))}"


def _accepted_source_ref_id(value: Mapping[str, Any]) -> str:
    """Identify an immutable source reference from accepted pipeline state."""

    return f"source-ref.{digest_value(dict(value))}"


def source_span_authority_v1(value: ClaimSourceRef) -> dict[str, Any]:
    """Return cross-loop source authority without receipt-local identity."""

    return value.model_dump(mode="json", exclude={"source_id"})


_SYNTHETIC_MOULD_RAW_ARTIFACTS: dict[str, str] = {}


class _LegacyExactMouldArtifactInterpreterRemoved:
    """Model-free test interpreter; adapters supply bytes, never fact authority."""

    implementation_id = "deterministic_bounded_mould_interpreter_v1"

    @property
    def implementation_source_sha256(self) -> str:
        return _artifact_interpreter_source_closure_sha256_v1()

    _ASSERTIONS = {
        "recurrence_chronology": {
            "assertion_id": "mould.recurrence-chronology.confirmed/1",
            "normalized_value": None,
            "explanation": (
                "The server-owned bounded catalog resolves the conflicting "
                "first-observation date."
            ),
        },
        "technical_assessment": {
            "assertion_id": "mould.technical-assessment.building-cause/1",
            "normalized_value": "building",
            "explanation": (
                "The server-owned bounded catalog recognizes competent "
                "building-causation evidence."
            ),
        },
        "building_envelope": {
            "assertion_id": "mould.building-envelope.documented/1",
            "normalized_value": "building",
            "explanation": (
                "The server-owned bounded catalog recognizes the selected "
                "building-branch condition."
            ),
        },
    }

    def interpret(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
    ) -> CanonicalFactInterpretationV1:
        adapter_id = acquisition.adapter_id
        raw_artifact_sha256 = acquisition.receipt_sha256
        sanitized_content = acquisition.sanitized_content
        artifact_source_version = acquisition.record_version
        artifact_page_count = acquisition.artifact_page_count
        observed_at = acquisition.acquired_at
        if (
            acquisition.status is not ToolResultStatus.OBSERVED
            or sanitized_content is None
            or artifact_page_count is None
        ):
            raise ClaimLoopError("interpreter requires an observed acquisition")
        if artifact_page_count != 1 or artifact_source_version != state.record_version:
            raise ClaimLoopError("raw artifact metadata is outside the bounded catalog")
        prior_fact = next(
            (value for value in state.facts if value.get("fact_id") == action.fact_id),
            None,
        )
        if prior_fact is None:
            raise ClaimLoopError("selected action fact is absent from the accepted state")
        catalog = [
            {
                "evidence_item_id": evidence_item_id,
                "exact_content_sha256": digest_text(content),
                **self._ASSERTIONS[evidence_item_id],
            }
            for evidence_item_id, content in sorted(
                _SYNTHETIC_MOULD_RAW_ARTIFACTS.items()
            )
        ]
        assertion = self._ASSERTIONS.get(action.evidence_item_id)
        expected_content = _SYNTHETIC_MOULD_RAW_ARTIFACTS.get(
            action.evidence_item_id
        )
        selected = (
            assertion
            if assertion is not None and sanitized_content == expected_content
            else None
        )
        source_sha256 = digest_text(sanitized_content)
        source_ref = ClaimSourceRef.model_validate(
            {
                "source_id": f"tool-artifact.{raw_artifact_sha256}",
                "source_sha256": source_sha256,
                "source_version": artifact_source_version,
                "locator_kind": "text_quote",
                "page": 1,
                "sanitized_excerpt": sanitized_content,
                "text_start": 0,
                "text_end": len(sanitized_content),
                "field": None,
                "value": None,
                "span_sha256": source_sha256,
                "adapter_id": adapter_id,
            }
        )
        observation_payload = {
            "contract": "casepath.claim-observation/1.0.0",
            "observation_id": "observation."
            + digest_value(
                {
                    "raw_artifact_sha256": raw_artifact_sha256,
                    "action_sha256": action.action_sha256,
                }
            ),
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "value": sanitized_content,
            "fact_state": "known" if selected is not None else "unknown",
            "normalized_value": (
                selected["normalized_value"] if selected is not None else None
            ),
            "explanation": (
                selected["explanation"]
                if selected is not None
                else "The raw artifact does not match a bounded assertion."
            ),
            "evidence_status": (
                "provided_sufficient"
                if selected is not None
                else "provided_insufficient"
            ),
            "source_refs": [source_ref.model_dump(mode="json")],
            "observed_at": observed_at,
        }
        observation = _self_hashed_observation(observation_payload)
        payload = {
            "contract": "casepath.canonical-fact-interpretation/1.2.0",
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "raw_artifact_sha256": raw_artifact_sha256,
            "prior_fact_sha256": digest_value(prior_fact),
            "assertion_catalog_sha256": digest_value(catalog),
            "selected_assertion_id": (
                selected["assertion_id"] if selected is not None else None
            ),
            "observation": observation.model_dump(mode="json"),
            "implementation": "deterministic_bounded_mould_interpreter_v1",
            "implementation_source_sha256": self.implementation_source_sha256,
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
        }
        return CanonicalFactInterpretationV1.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )


class StructuredMouldArtifactInterpreterV2:
    """Interpret a closed typed assessment without exemplar-byte matching.

    The document reports a bounded finding and its free-text basis.  Only the
    server-owned playbook catalog determines whether that finding resolves the
    selected fact; the browser never supplies fact state or sufficiency.
    """

    implementation_id = "casepath.structured-mould-artifact-interpreter/2.0.0"
    schema = "casepath.synthetic-neutral-assessment/1.0.0"
    document_kind = "neutral_assessment"
    _DOCUMENT_KEYS = frozenset(
        {"schema", "document_kind", "evidence_item_id", "finding", "basis"}
    )

    @property
    def implementation_source_sha256(self) -> str:
        return _artifact_interpreter_source_closure_sha256_v1()

    @staticmethod
    def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ClaimLoopError("typed assessment contains a duplicate field")
            value[key] = item
        return value

    @classmethod
    def _parse_document(cls, content: str) -> dict[str, str]:
        if content != unicodedata.normalize("NFC", content):
            raise ClaimLoopError("typed assessment must use Unicode NFC")
        if len(content.encode("utf-8")) > 100_000:
            raise ClaimLoopError("typed assessment exceeds the byte limit")
        try:
            value = json.loads(
                content,
                object_pairs_hook=cls._duplicate_rejecting_object,
            )
        except (json.JSONDecodeError, RecursionError, UnicodeError) as exc:
            raise ClaimLoopError("typed assessment is not valid JSON") from exc
        if not isinstance(value, dict) or set(value) != cls._DOCUMENT_KEYS:
            raise ClaimLoopError("typed assessment fields are not closed")
        if any(not isinstance(item, str) for item in value.values()):
            raise ClaimLoopError("typed assessment fields must be strings")
        if value["schema"] != cls.schema:
            raise ClaimLoopError("typed assessment schema is unsupported")
        if value["document_kind"] != cls.document_kind:
            raise ClaimLoopError("typed assessment kind is unsupported")
        basis = value["basis"]
        if not basis.strip() or len(basis) > 4_000:
            raise ClaimLoopError("typed assessment basis is empty or oversized")
        if any(item != unicodedata.normalize("NFC", item) for item in value.values()):
            raise ClaimLoopError("typed assessment values must use Unicode NFC")
        return value

    @classmethod
    def input_contract(
        cls,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
    ) -> dict[str, Any]:
        template = playbook_template_from_accepted_v1(state.accepted_artifacts)
        fact = next(
            (value for value in state.facts if value.get("fact_id") == action.fact_id),
            None,
        )
        checklist_items = state.checklist.get("items")
        checklist_item = next(
            (
                value
                for value in checklist_items
                if isinstance(value, Mapping)
                and value.get("item_id") == action.evidence_item_id
            ),
            None,
        ) if isinstance(checklist_items, list) else None
        if (
            fact is None
            or checklist_item is None
            or checklist_item.get("fact_id") != action.fact_id
        ):
            raise ClaimLoopError(
                "typed assessment action is outside the accepted fact/checklist authority"
            )
        decision_key = fact.get("decision_key")
        if decision_key is None:
            # Some current-path obligations establish the existence/quality of
            # a fact without selecting a categorical process branch (for
            # example, a complete recurrence chronology). Keep that outcome
            # closed and typed without inventing a normalized branch value.
            options = {
                "established": "The source establishes the requested fact.",
                "unresolved": "The source leaves the requested fact unresolved.",
            }
            unresolved = "unresolved"
        else:
            options = template.decision_options.get(decision_key)
            unresolved = template.fail_closed_normalized_values.get(decision_key)
            if not isinstance(options, dict) or unresolved not in options:
                raise ClaimLoopError("typed assessment decision catalog is invalid")
        payload = {
            "contract": "casepath.typed-evidence-input/1.0.0",
            "schema": cls.schema,
            "document_kind": cls.document_kind,
            "evidence_item_id": action.evidence_item_id,
            "fact_id": action.fact_id,
            "decision_key": decision_key,
            "finding_values": list(options),
            "unresolved_finding": unresolved,
            "basis_max_characters": 4_000,
            "content_max_utf8_bytes": 100_000,
            "template_sha256": template.template_sha256,
            "implementation_id": cls.implementation_id,
            "implementation_source_sha256": cls().implementation_source_sha256,
        }
        return {**payload, "input_contract_sha256": digest_value(payload)}

    @classmethod
    def validate_content(
        cls,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        content: str,
    ) -> dict[str, str]:
        """Validate user bytes before a registry effect can be journaled."""

        document = cls._parse_document(content)
        contract = cls.input_contract(action=action, state=state)
        if document["evidence_item_id"] != action.evidence_item_id:
            raise ClaimLoopError("typed assessment targets another evidence item")
        if document["finding"] not in contract["finding_values"]:
            raise ClaimLoopError("typed assessment finding is outside the catalog")
        return document

    def interpret(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
    ) -> CanonicalFactInterpretationV1:
        content = acquisition.sanitized_content
        if (
            acquisition.status is not ToolResultStatus.OBSERVED
            or content is None
            or acquisition.artifact_page_count != 1
            or acquisition.record_version != state.record_version
            or acquisition.action_id != action.action_id
        ):
            raise ClaimLoopError("typed assessment acquisition boundary is invalid")
        prior_fact = next(
            (value for value in state.facts if value.get("fact_id") == action.fact_id),
            None,
        )
        if prior_fact is None:
            raise ClaimLoopError("typed assessment fact is absent")
        input_contract = self.input_contract(action=action, state=state)
        document = self.validate_content(
            action=action,
            state=state,
            content=content,
        )
        resolved = document["finding"] != input_contract["unresolved_finding"]
        source_sha256 = digest_text(content)
        source_ref = ClaimSourceRef.model_validate(
            {
                "source_id": f"tool-artifact.{acquisition.receipt_sha256}",
                "source_sha256": source_sha256,
                "source_version": acquisition.record_version,
                "locator_kind": "text_quote",
                "page": 1,
                "sanitized_excerpt": content,
                "text_start": 0,
                "text_end": len(content),
                "field": None,
                "value": None,
                "span_sha256": source_sha256,
                "adapter_id": acquisition.adapter_id,
            }
        )
        decision_key = input_contract["decision_key"]
        if decision_key is None:
            explanation = (
                "The admitted typed assessment establishes the requested fact."
                if resolved
                else "The admitted typed assessment leaves the requested fact unresolved."
            )
        else:
            explanation = (
                f"The admitted typed assessment reports a bounded {decision_key} finding."
                if resolved
                else f"The admitted typed assessment leaves {decision_key} unresolved."
            )
        observation_payload = {
            "contract": "casepath.claim-observation/1.0.0",
            "observation_id": "observation."
            + digest_value(
                {
                    "acquisition_receipt_sha256": acquisition.receipt_sha256,
                    "action_sha256": action.action_sha256,
                }
            ),
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "value": content,
            "fact_state": "known" if resolved else "unknown",
            "normalized_value": (
                document["finding"]
                if resolved and input_contract["decision_key"] is not None
                else None
            ),
            "explanation": explanation,
            "evidence_status": (
                "provided_sufficient" if resolved else "provided_insufficient"
            ),
            "source_refs": [source_ref.model_dump(mode="json")],
            "observed_at": acquisition.acquired_at,
        }
        observation = _self_hashed_observation(observation_payload)
        catalog = {
            "input_contract": input_contract,
            "document_schema": sorted(self._DOCUMENT_KEYS),
            "template_sha256": input_contract["template_sha256"],
        }
        payload = {
            "contract": "casepath.canonical-fact-interpretation/1.2.0",
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "raw_artifact_sha256": acquisition.receipt_sha256,
            "prior_fact_sha256": digest_value(prior_fact),
            "assertion_catalog_sha256": digest_value(catalog),
            "selected_assertion_id": (
                f"typed-assessment.{action.evidence_item_id}.{document['finding']}/2"
                if resolved
                else None
            ),
            "observation": observation.model_dump(mode="json"),
            "implementation": self.implementation_id,
            "implementation_source_sha256": self.implementation_source_sha256,
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
        }
        return CanonicalFactInterpretationV1.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )


# Keep the established import name while moving production and tests onto the
# successor schema.  No accepted literal document is embedded in source.
DeterministicMouldArtifactInterpreter = StructuredMouldArtifactInterpreterV2


class DeterministicTemplateArtifactInterpreter:
    """Interpret exact tool bytes through a server-owned template assertion set."""

    def __init__(
        self,
        *,
        template: PlaybookTemplate,
        assertions: Mapping[str, Mapping[str, Any]],
    ) -> None:
        normalized: dict[str, dict[str, Any]] = {}
        fact_by_item: dict[str, dict[str, Any]] = {}
        for claim_id in template.supported_claim_ids:
            record = template.declarative_record(claim_id)
            facts = {value["fact_id"]: value for value in record["facts"]}
            for item in record["checklist"]["items"]:
                item_id = item["item_id"]
                fact = facts.get(item["fact_id"])
                if fact is None or (
                    item_id in fact_by_item and fact_by_item[item_id] != fact
                ):
                    raise ClaimLoopError(
                        "template assertion fact mapping is ambiguous"
                    )
                fact_by_item[item_id] = fact
        if not assertions or not set(assertions) <= set(fact_by_item):
            raise ClaimLoopError("template assertion roster is invalid")
        for item_id, assertion in assertions.items():
            value = dict(assertion)
            if set(value) != {
                "assertion_id",
                "exact_content",
                "normalized_value",
                "explanation",
            } or any(
                not isinstance(value[field], str) or not value[field]
                for field in ("assertion_id", "exact_content", "explanation")
            ):
                raise ClaimLoopError("template assertion is invalid")
            fact = fact_by_item[item_id]
            normalized_value = value["normalized_value"]
            decision_key = fact.get("decision_key")
            if (
                fact.get("controls_process") is True
                and normalized_value
                not in template.decision_options.get(decision_key, {})
            ):
                raise ClaimLoopError(
                    "template assertion is outside the decision catalog"
                )
            normalized[item_id] = value
        self.template = template
        self.assertions = normalized
        self.implementation_id = (
            "casepath.deterministic-template-artifact-interpreter."
            + digest_value(
                {
                    "template_sha256": template.template_sha256,
                    "assertions": normalized,
                }
            )
        )

    @property
    def implementation_source_sha256(self) -> str:
        return _artifact_interpreter_source_closure_sha256_v1()

    def interpret(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
    ) -> CanonicalFactInterpretationV1:
        if (
            acquisition.status is not ToolResultStatus.OBSERVED
            or acquisition.sanitized_content is None
            or acquisition.artifact_page_count != 1
            or acquisition.record_version != state.record_version
            or acquisition.action_id != action.action_id
            or playbook_template_from_accepted_v1(
                state.accepted_artifacts
            ).template_sha256
            != self.template.template_sha256
        ):
            raise ClaimLoopError(
                "template interpreter acquisition boundary is invalid"
            )
        prior_fact = next(
            (value for value in state.facts if value.get("fact_id") == action.fact_id),
            None,
        )
        if prior_fact is None:
            raise ClaimLoopError("template interpreter fact is absent")
        assertion = self.assertions.get(action.evidence_item_id)
        selected = (
            assertion
            if assertion is not None
            and acquisition.sanitized_content == assertion["exact_content"]
            else None
        )
        source_sha256 = digest_text(acquisition.sanitized_content)
        source_ref = ClaimSourceRef.model_validate(
            {
                "source_id": f"tool-artifact.{acquisition.receipt_sha256}",
                "source_sha256": source_sha256,
                "source_version": acquisition.record_version,
                "locator_kind": "text_quote",
                "page": 1,
                "sanitized_excerpt": acquisition.sanitized_content,
                "text_start": 0,
                "text_end": len(acquisition.sanitized_content),
                "field": None,
                "value": None,
                "span_sha256": source_sha256,
                "adapter_id": acquisition.adapter_id,
            }
        )
        observation_payload = {
            "contract": "casepath.claim-observation/1.0.0",
            "observation_id": "observation."
            + digest_value(
                {
                    "acquisition_receipt_sha256": acquisition.receipt_sha256,
                    "action_sha256": action.action_sha256,
                }
            ),
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "value": acquisition.sanitized_content,
            "fact_state": "known" if selected is not None else "unknown",
            "normalized_value": (
                selected["normalized_value"] if selected is not None else None
            ),
            "explanation": (
                selected["explanation"]
                if selected is not None
                else "The artifact does not match a bounded template assertion."
            ),
            "evidence_status": (
                "provided_sufficient"
                if selected is not None
                else "provided_insufficient"
            ),
            "source_refs": [source_ref.model_dump(mode="json")],
            "observed_at": acquisition.acquired_at,
        }
        observation = _self_hashed_observation(observation_payload)
        catalog = [
            {
                "evidence_item_id": item_id,
                "assertion_id": value["assertion_id"],
                "exact_content_sha256": digest_text(value["exact_content"]),
                "normalized_value": value["normalized_value"],
            }
            for item_id, value in sorted(self.assertions.items())
        ]
        payload = {
            "contract": "casepath.canonical-fact-interpretation/1.2.0",
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "fact_id": action.fact_id,
            "evidence_item_id": action.evidence_item_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "raw_artifact_sha256": acquisition.receipt_sha256,
            "prior_fact_sha256": digest_value(prior_fact),
            "assertion_catalog_sha256": digest_value(catalog),
            "selected_assertion_id": (
                selected["assertion_id"] if selected is not None else None
            ),
            "observation": observation.model_dump(mode="json"),
            "implementation": self.implementation_id,
            "implementation_source_sha256": self.implementation_source_sha256,
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
        }
        return CanonicalFactInterpretationV1.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )


def _accepted_artifacts(result: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "claim_id",
        "facts",
        "legal_research",
        "process",
        "checklist",
        "verification",
        "playbook_template",
    }
    if not required <= set(result):
        raise ClaimLoopError("accepted result is incomplete")
    facts = result.get("facts")
    process = result.get("process")
    checklist = result.get("checklist")
    verification = result.get("verification")
    legal = result.get("legal_research")
    audit = result.get("audit")
    playbook_template = result.get("playbook_template")
    if (
        not isinstance(facts, list)
        or not isinstance(process, Mapping)
        or not isinstance(checklist, Mapping)
        or not isinstance(verification, Mapping)
        or not isinstance(legal, Mapping)
        or verification.get("valid") is not True
        or verification.get("computed") is not True
        or verification.get("rejected_proposals") != []
        or verification.get("accepted_artifacts")
        != [
            "canonical_claim_state",
            "legal_context",
            "process_graph",
            "evidence_model",
            "precedents",
        ]
        or not isinstance(verification.get("whole_playbook_hash"), str)
        or not isinstance(audit, Mapping)
        or audit.get("accepted") is not True
        or audit.get("verification_computed") is not True
        or not isinstance(playbook_template, Mapping)
        or digest_value(
            {
                key: playbook_template[key]
                for key in (
                    "contract",
                    "template_id",
                    "template_version",
                    "template_sha256",
                    "supported_claim_ids",
                )
            }
        )
        != playbook_template.get("receipt_sha256")
        or result["claim_id"] not in playbook_template.get("supported_claim_ids", [])
    ):
        raise ClaimLoopError("accepted playbook boundary is not valid")
    overlay = process.get("current_overlay")
    if not isinstance(overlay, Mapping):
        raise ClaimLoopError("accepted process has no current overlay")
    next_action = result.get("next_action")
    if not isinstance(next_action, Mapping) or (
        next_action.get("process_node_id") != overlay.get("next_action_node_id")
    ):
        raise ClaimLoopError("accepted next action is not bound to the process overlay")
    accepted = {
        "claim_id": result["claim_id"],
        "facts": deepcopy(facts),
        "legal_research": deepcopy(dict(legal)),
        "process": deepcopy(dict(process)),
        "checklist": deepcopy(dict(checklist)),
        "verification": deepcopy(dict(verification)),
        "next_action": deepcopy(dict(next_action)),
        "agent_orchestration": deepcopy(result.get("agent_orchestration", {})),
        "playbook_template": deepcopy(dict(playbook_template)),
    }
    template_record = result.get("playbook_template_record")
    if template_record is not None:
        if not isinstance(template_record, Mapping):
            raise ClaimLoopError("accepted playbook template record is invalid")
        accepted["playbook_template_record"] = deepcopy(dict(template_record))
    observable_package = result.get("observable_package")
    if observable_package is not None:
        if (
            not isinstance(observable_package, Mapping)
            or audit.get("observable_input_hash")
            != digest_value(dict(observable_package))
        ):
            raise ClaimLoopError("accepted observable package is not bound")
        accepted["observable_package"] = deepcopy(dict(observable_package))
    playbook_template_from_accepted_v1(accepted)
    return accepted


def _deterministic_gate_receipt(
    *,
    claim_id: str,
    facts: tuple[dict[str, Any], ...],
    process: dict[str, Any],
    checklist: dict[str, Any],
    legal: Mapping[str, Any],
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
) -> dict[str, Any]:
    """Re-run the existing deterministic process/evidence safety gates.

    The accepted v20 run remains the sole six-agent semantic boundary.  Each
    outer-loop update reuses the same release graph/evidence validators before
    it may become decision-ready; no model agent or substitute gate is added.
    """

    if template.template_sha256 != MOULD_PLAYBOOK_TEMPLATE.template_sha256:
        try:
            check_names = list(
                validate_template_cycle_artifacts_v1(
                    template=template,
                    claim_id=claim_id,
                    facts=facts,
                    process=process,
                    checklist=checklist,
                )
            )
            check_names.extend(
                validate_template_legal_context_v1(
                    template=template,
                    legal=legal,
                )
            )
        except (PlaybookMaterializationError, KeyError, TypeError, ValueError) as exc:
            raise ClaimLoopError(
                "projected playbook failed deterministic template gates"
            ) from exc
        payload = {
            "contract": "casepath.claim-loop-deterministic-gate-receipt/1.0.0",
            "claim_id": claim_id,
            "playbook_template_sha256": template.template_sha256,
            "facts_sha256": digest_value(list(facts)),
            "process_sha256": digest_value(process),
            "checklist_sha256": digest_value(checklist),
            "legal_sha256": digest_value(dict(legal)),
            "check_names": check_names,
            "release_gates_recomputed": True,
            "deterministic_authority": True,
            "valid": True,
            "computed": True,
            "rejected_proposals": [],
            "whole_playbook_hash": digest_value(
                {"process": process, "checklist": checklist}
            ),
            "model_calls": 0,
            "provider_calls": 0,
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    facts_by_id = {value["fact_id"]: value for value in facts}
    process_node_ids = {value.get("node_id") for value in process.get("nodes", [])}
    has_memory_extension = bool(process_node_ids & set(MEMORY_EXTENSION_NODE_IDS))
    allowed_extension_nodes = (
        set(MEMORY_EXTENSION_NODE_IDS) if has_memory_extension else None
    )
    allowed_extension_edges = (
        set(MEMORY_EXTENSION_EDGE_PAIRS) if has_memory_extension else None
    )
    artifact_ids = {
        source_ref["artifact_id"]
        for fact in facts
        for source_ref in fact.get("source_refs", [])
        if isinstance(source_ref, Mapping)
        and isinstance(source_ref.get("artifact_id"), str)
    }
    artifact_ids_by_fact = {
        fact["fact_id"]: {
            source_ref["artifact_id"]
            for source_ref in fact.get("source_refs", [])
            if isinstance(source_ref, Mapping)
            and isinstance(source_ref.get("artifact_id"), str)
        }
        for fact in facts
    }
    allowed_artifact_extensions_by_item = {
        item["item_id"]: set(artifact_ids_by_fact.get(item["fact_id"], set()))
        for item in checklist.get("items", [])
        if isinstance(item, Mapping)
        and isinstance(item.get("item_id"), str)
        and isinstance(item.get("fact_id"), str)
    }
    try:
        legal_ids, legal_checks = validate_legal_context(dict(legal))
        process_checks = validate_process_graph(
            process,
            fact_ids=set(facts_by_id),
            legal_source_ids=legal_ids,
            evidence_item_ids={value["item_id"] for value in checklist["items"]},
            facts_by_id=facts_by_id,
            allowed_extension_node_ids=allowed_extension_nodes,
            allowed_extension_edge_pairs=allowed_extension_edges,
        )
        evidence_checks = validate_evidence_model(
            checklist,
            process=process,
            facts_by_id=facts_by_id,
            legal_source_ids=legal_ids,
            allowed_artifact_ids=artifact_ids,
            allowed_extension_node_ids=allowed_extension_nodes,
        )
        validate_fact_relations(
            claim_id=claim_id,
            facts=list(facts),
            process=process,
            checklist=checklist,
            include_memory_extension=has_memory_extension,
            allowed_artifact_extensions_by_item=(
                allowed_artifact_extensions_by_item
            ),
        )
        current_checks = validate_current_state(
            {"facts": list(facts)}, process, checklist
        )
    except (ContractValidationError, KeyError, TypeError, ValueError) as exc:
        raise ClaimLoopError("projected playbook failed deterministic gates") from exc
    payload = {
        "contract": "casepath.claim-loop-deterministic-gate-receipt/1.0.0",
        "claim_id": claim_id,
        "facts_sha256": digest_value(list(facts)),
        "process_sha256": digest_value(process),
        "checklist_sha256": digest_value(checklist),
        "legal_sha256": digest_value(dict(legal)),
        "check_names": [
            value["name"]
            for value in (
                *legal_checks,
                *process_checks,
                *evidence_checks,
                *current_checks,
            )
        ]
        + ["Exact fact relationships"],
        "release_gates_recomputed": True,
        "deterministic_authority": True,
        "valid": True,
        "computed": True,
        "rejected_proposals": [],
        "whole_playbook_hash": digest_value(
            {"process": process, "checklist": checklist}
        ),
        "model_calls": 0,
        "provider_calls": 0,
    }
    return {**payload, "receipt_sha256": digest_value(payload)}


def build_claim_loop_gate_receipt_v1(
    *,
    claim_id: str,
    facts: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
    legal: Mapping[str, Any],
    template: PlaybookTemplate = MOULD_PLAYBOOK_TEMPLATE,
) -> dict[str, Any]:
    """Run the production release validators over exact cycle artifacts."""

    return _deterministic_gate_receipt(
        claim_id=claim_id,
        facts=tuple(deepcopy(value) for value in facts),
        process=deepcopy(dict(process)),
        checklist=deepcopy(dict(checklist)),
        legal=deepcopy(dict(legal)),
        template=template,
    )


def project_claim_loop_artifacts_v1(
    *,
    accepted: Mapping[str, Any],
    observations: tuple[ClaimObservation, ...],
    corrections: tuple[ScopedCorrection, ...],
    projection_ledger: tuple[ProjectionLedgerEntry, ...],
) -> dict[str, Any]:
    """Return the exact deterministic inputs a fresh StateGraph cycle must bind."""

    (
        facts,
        fact_catalog_sha256,
        process,
        checklist,
        obligations,
        uncertainty,
        blocking_uncertainty,
        provenance,
        sufficiency,
        gate_receipt,
    ) = _project_artifacts(
        accepted=accepted,
        observations=observations,
        corrections=corrections,
        projection_ledger=projection_ledger,
    )
    return {
        "facts": facts,
        "fact_catalog_sha256": fact_catalog_sha256,
        "process": process,
        "checklist": checklist,
        "obligations": obligations,
        "uncertainty_fact_ids": uncertainty,
        "blocking_uncertainty_fact_ids": blocking_uncertainty,
        "provenance_edges": provenance,
        "sufficiency": sufficiency,
        "deterministic_gate_receipt": gate_receipt,
    }


def accepted_artifacts_from_run(result: Mapping[str, Any]) -> dict[str, Any]:
    """Public constructor used by the API after the existing acceptance gate."""

    return _accepted_artifacts(result)


def _correction_observation(correction: ScopedCorrection) -> dict[str, Any]:
    effect = correction.effect
    payload = {
        # A correction is a distinct server-admitted authority record.  It may
        # withdraw a previously decision-bearing assertion; an ordinary
        # insufficient observation remains unable to erase accepted truth.
        "contract": "casepath.correction-observation/1.0.0",
        "observation_id": f"correction-observation.{correction.correction_sha256}",
        "fact_id": effect.fact_id,
        "evidence_item_id": effect.evidence_item_id,
        "value": effect.value,
        "fact_state": effect.fact_state,
        "normalized_value": effect.normalized_value,
        "explanation": effect.explanation,
        "evidence_status": effect.evidence_status,
        "source_refs": [correction.source_ref.model_dump(mode="json")],
        "observed_at": correction.effective_at,
    }
    return {**payload, "observation_sha256": digest_value(payload)}


def _projection_records(
    observations: tuple[ClaimObservation, ...],
    corrections: tuple[ScopedCorrection, ...],
    projection_ledger: tuple[ProjectionLedgerEntry, ...],
) -> list[dict[str, Any]]:
    observation_by_hash = {
        value.observation_sha256: value.model_dump(mode="json")
        for value in observations
    }
    correction_by_hash = {
        value.correction_sha256: _correction_observation(value)
        for value in corrections
    }
    if (
        len(observation_by_hash) != len(observations)
        or len(correction_by_hash) != len(corrections)
        or len(projection_ledger) != len(observations) + len(corrections)
    ):
        raise ClaimLoopError("record projection ledger is not one-to-one")
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for entry in projection_ledger:
        key = (entry.kind, entry.record_sha256)
        if key in seen:
            raise ClaimLoopError("record projection ledger contains a duplicate")
        seen.add(key)
        if entry.kind == "observation":
            record = observation_by_hash.get(entry.record_sha256)
        else:
            record = correction_by_hash.get(entry.record_sha256)
        if record is None:
            raise ClaimLoopError("record projection ledger references an unknown record")
        records.append(record)
    if seen != {
        *(("observation", value) for value in observation_by_hash),
        *(("correction", value) for value in correction_by_hash),
    }:
        raise ClaimLoopError("record projection ledger omits a record")
    return records


def _project_artifacts(
    *,
    accepted: Mapping[str, Any],
    observations: tuple[ClaimObservation, ...],
    corrections: tuple[ScopedCorrection, ...],
    projection_ledger: tuple[ProjectionLedgerEntry, ...],
    accepted_cycle_artifacts: Mapping[str, Any] | None = None,
) -> tuple[
    tuple[dict[str, Any], ...],
    str,
    dict[str, Any],
    dict[str, Any],
    tuple[ObligationState, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[ProvenanceEdge, ...],
    SufficiencyState,
    dict[str, Any],
]:
    records = _projection_records(observations, corrections, projection_ledger)
    template = playbook_template_from_accepted_v1(accepted)
    projection = project_record_driven_facts_v1(
        seed_facts=accepted["facts"],
        observation_records=records,
        decision_options=template.decision_options,
        fail_closed_values=template.fail_closed_normalized_values,
    )
    facts = tuple(deepcopy(value) for value in projection.facts)
    process = deepcopy(accepted["process"])
    route = decision_projection(list(facts), route_program=template.route_program)
    process["selected_path"] = deepcopy(route["selected_path"])
    process["current_node"] = route["current_node"]
    process["current_overlay"] = apply_process_projection(
        process["nodes"],
        process["edges"],
        route,
        process["main_spine"],
        rendering_profile=template.process_rendering_profile,
    )
    checklist = deepcopy(accepted["checklist"])
    items = checklist.get("items")
    if not isinstance(items, list):
        raise ClaimLoopError("accepted checklist has no items")
    apply_evidence_relations(process, items)
    apply_evidence_projection(
        items,
        process,
        projection_mode=template.evidence_projection_mode,
    )
    evidence_updates: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {}
    for record in records:
        source_refs = tuple(
            ClaimSourceRef.model_validate(value) for value in record["source_refs"]
        )
        evidence_updates[record["evidence_item_id"]] = (
            record["evidence_status"],
            tuple(_source_ref_id(value) for value in source_refs),
            tuple(dict.fromkeys(value.source_id for value in source_refs)),
        )
    item_ids = {item.get("item_id") for item in items}
    if not set(evidence_updates) <= item_ids:
        raise ClaimLoopError("observation references unknown evidence")
    for item in items:
        update = evidence_updates.get(item["item_id"])
        if update is not None:
            status, source_ref_ids, artifact_ids = update
            item["status"] = "missing" if status == "unavailable" else status
            item["loop_source_ref_ids"] = list(source_ref_ids)
            item["artifact_ids"] = list(artifact_ids)
    apply_evidence_relations(process, items)
    checklist.update(checklist_derived_sections(items))

    if accepted_cycle_artifacts is not None:
        cycle = deepcopy(
            accepted_cycle_artifacts.model_dump(mode="json")
            if isinstance(accepted_cycle_artifacts, AcceptedCycleArtifactsV1)
            else dict(accepted_cycle_artifacts)
        )
        expected_keys = {
            "contract",
            "facts",
            "process",
            "checklist",
            "final_claim_brief",
            "verification",
            "role_artifacts",
            "receipt_sha256",
        }
        payload = {key: value for key, value in cycle.items() if key != "receipt_sha256"}
        if (
            set(cycle) != expected_keys
            or cycle.get("contract")
            != "casepath.accepted-cycle-artifacts/1.0.0"
            or cycle.get("receipt_sha256") != digest_value(payload)
            or cycle.get("facts") != list(facts)
            or not isinstance(cycle.get("process"), dict)
            or not isinstance(cycle.get("checklist"), dict)
            or not isinstance(cycle.get("final_claim_brief"), dict)
            or not isinstance(cycle.get("verification"), dict)
        ):
            raise ClaimLoopError("accepted cycle artifacts are invalid")
        process = cycle["process"]
        checklist = cycle["checklist"]
        items = checklist.get("items")
        if not isinstance(items, list):
            raise ClaimLoopError("accepted cycle checklist has no items")

    fact_by_id = {value["fact_id"]: value for value in facts}
    accepted_fact_by_id = {
        value["fact_id"]: value for value in accepted["facts"]
    }
    accepted_source_refs_by_item: dict[
        str, tuple[tuple[str, Mapping[str, Any]], ...]
    ] = {}
    for item in items:
        accepted_fact = accepted_fact_by_id.get(item.get("fact_id"), {})
        raw_refs = accepted_fact.get("source_refs", [])
        if not isinstance(raw_refs, list):
            raise ClaimLoopError("accepted fact source provenance is invalid")
        accepted_source_refs_by_item[item["item_id"]] = tuple(
            (_accepted_source_ref_id(ref), ref)
            for ref in raw_refs
            if isinstance(ref, Mapping)
        )
    obligations: list[ObligationState] = []
    for item in items:
        fact = fact_by_id.get(item.get("fact_id"), {})
        status = item.get("status")
        if fact.get("state") == "conflicting":
            obligation_status = ObligationStatus.CONTRADICTED
        elif status == "provided_sufficient" and fact.get("state") == "known":
            obligation_status = ObligationStatus.SATISFIED
        elif status == "conditional":
            obligation_status = ObligationStatus.CONDITIONAL
        elif not item.get("current_path") or status == "not_applicable":
            obligation_status = ObligationStatus.BLOCKED
        else:
            obligation_status = ObligationStatus.ACTIVE
        seed_source_ref_ids = tuple(
            value[0] for value in accepted_source_refs_by_item[item["item_id"]]
        )
        loop_source_ref_ids = tuple(item.get("loop_source_ref_ids", ()))
        obligation_source_ref_ids = tuple(
            dict.fromkeys((*seed_source_ref_ids, *loop_source_ref_ids))
        )
        obligations.append(
            ObligationState(
                obligation_id=item["item_id"],
                process_node_ids=tuple(item.get("node_ids", [item["node_id"]])),
                fact_id=item["fact_id"],
                status=obligation_status,
                evidence_status=status,
                mandatory_now=(
                    bool(item.get("current_path"))
                    and item.get("required_level") == "mandatory"
                    and obligation_status
                    in {ObligationStatus.ACTIVE, ObligationStatus.CONTRADICTED}
                ),
                source_ref_ids=obligation_source_ref_ids,
            )
        )
    uncertainty = tuple(
        value["fact_id"]
        for value in facts
        if value.get("state") in {"unknown", "conflicting"}
    )
    current_required_fact_ids = {
        value.fact_id
        for value in obligations
        if value.mandatory_now
        or (
            value.status is ObligationStatus.CONTRADICTED
            and any(
                item.get("item_id") == value.obligation_id
                and bool(item.get("current_path"))
                for item in items
            )
        )
    }
    controlling_fact_ids = {
        value["fact_id"] for value in facts if value.get("controls_process") is True
    }
    blocking_uncertainty = tuple(
        fact_id
        for fact_id in uncertainty
        if fact_id in current_required_fact_ids or fact_id in controlling_fact_ids
    )
    observations_by_hash = {
        value.observation_sha256: value for value in observations
    }
    corrections_by_hash = {
        value.correction_sha256: value for value in corrections
    }
    provenance: list[ProvenanceEdge] = []
    for item in items:
        accepted_fact = accepted_fact_by_id.get(item.get("fact_id"), {})
        accepted_fact_sha256 = digest_value(accepted_fact)
        for source_ref_id, source_ref in accepted_source_refs_by_item[
            item["item_id"]
        ]:
            provenance.append(
                ProvenanceEdge(
                    observation_sha256=digest_value(
                        {
                            "contract": (
                                "casepath.accepted-fact-provenance/1.0.0"
                            ),
                            "accepted_fact_sha256": accepted_fact_sha256,
                            "evidence_item_id": item["item_id"],
                            "source_ref": dict(source_ref),
                        }
                    ),
                    source_ref_id=source_ref_id,
                    fact_id=item["fact_id"],
                    evidence_item_id=item["item_id"],
                )
            )
    for entry in projection_ledger:
        if entry.kind == "observation":
            observation = observations_by_hash[entry.record_sha256]
            provenance.extend(
                ProvenanceEdge(
                    observation_sha256=observation.observation_sha256,
                    source_ref_id=_source_ref_id(source_ref),
                    fact_id=observation.fact_id,
                    evidence_item_id=observation.evidence_item_id,
                )
                for source_ref in observation.source_refs
            )
        else:
            correction = corrections_by_hash[entry.record_sha256]
            provenance.append(
                ProvenanceEdge(
                    observation_sha256=correction.correction_sha256,
                    source_ref_id=_source_ref_id(correction.source_ref),
                    fact_id=correction.effect.fact_id,
                    evidence_item_id=correction.effect.evidence_item_id,
                )
            )
    provenance_edges = tuple(provenance)
    unresolved = tuple(
        value.obligation_id for value in obligations if value.mandatory_now
    )
    contradicted = tuple(
        value.obligation_id
        for value in obligations
        if value.status is ObligationStatus.CONTRADICTED
    )
    provenance_keys = {
        (value.fact_id, value.evidence_item_id, value.source_ref_id)
        for value in provenance_edges
    }
    provenance_complete = all(
        value.source_ref_ids
        and all(
            (value.fact_id, value.obligation_id, source_ref_id)
            in provenance_keys
            for source_ref_id in value.source_ref_ids
        )
        for value in obligations
        if value.status is ObligationStatus.SATISFIED
    )
    sufficiency = SufficiencyState(
        status=(
            SufficiencyStatus.DECISION_READY
            if (
                not unresolved
                and not contradicted
                and not blocking_uncertainty
                and provenance_complete
            )
            else SufficiencyStatus.INSUFFICIENT
        ),
        unresolved_mandatory_obligation_ids=unresolved,
        contradicted_obligation_ids=contradicted,
        provenance_complete=provenance_complete,
    )
    gate_receipt = _deterministic_gate_receipt(
        claim_id=accepted["claim_id"],
        facts=facts,
        process=process,
        checklist=checklist,
        legal=accepted["legal_research"],
        template=template,
    )
    return (
        facts,
        projection.receipt["catalog_sha256"],
        process,
        checklist,
        tuple(obligations),
        uncertainty,
        blocking_uncertainty,
        provenance_edges,
        sufficiency,
        gate_receipt,
    )


def _failed_evidence_items(history: tuple[ActionHistoryEntry, ...]) -> set[str]:
    return {
        value.action.evidence_item_id
        for value in history
        if value.outcome in {"unavailable", "failed", "unknown"}
    }


def _derive_action(
    *,
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
    obligations: tuple[ObligationState, ...],
    history: tuple[ActionHistoryEntry, ...],
    retired_evidence_item_ids: frozenset[str] = frozenset(),
) -> EvidenceAction | None:
    overlay = process.get("current_overlay")
    if not isinstance(overlay, Mapping):
        raise ClaimLoopError("projected process has no overlay")
    next_node = overlay.get("next_action_node_id")
    if not isinstance(next_node, str) or not next_node:
        raise ClaimLoopError("projected process has no bounded next action")
    obligations_by_id = {value.obligation_id: value for value in obligations}
    failed = _failed_evidence_items(history)
    mandatory_candidates = []
    conditional_candidates = []
    for index, item in enumerate(checklist.get("items", [])):
        max_observed_attempts = item.get("max_observed_attempts")
        if max_observed_attempts is not None:
            if (
                isinstance(max_observed_attempts, bool)
                or not isinstance(max_observed_attempts, int)
                or not 1 <= max_observed_attempts <= 16
            ):
                raise ClaimLoopError(
                    "checklist observed-attempt bound must be an integer from 1 to 16"
                )
            observed_attempts = sum(
                1
                for value in history
                if value.action.evidence_item_id == item.get("item_id")
                and value.outcome == "observed"
            )
            if observed_attempts >= max_observed_attempts:
                continue
        obligation = obligations_by_id.get(item.get("item_id"))
        if (
            obligation is None
            or obligation.obligation_id in failed
            or obligation.obligation_id in retired_evidence_item_ids
        ):
            continue
        node_ids = tuple(item.get("node_ids", [item.get("node_id")]))
        if obligation.mandatory_now:
            # Current controlling obligations take precedence even when the
            # playbook's next acquisition node is downstream of the fact that
            # blocks entry to it (for example, recurrence chronology).
            mandatory_candidates.append((index, item, obligation))
        elif (
            obligation.status is ObligationStatus.CONDITIONAL
            and next_node in node_ids
        ):
            conditional_candidates.append((index, item, obligation))
    candidates = mandatory_candidates or conditional_candidates
    if not candidates:
        return None
    _, item, obligation = min(candidates, key=lambda value: value[0])
    if obligation.status is ObligationStatus.CONTRADICTED:
        action_kind = "clarify"
    elif item.get("status") == "provided_insufficient":
        action_kind = "validate"
    else:
        action_kind = "acquire"
    payload = {
        "contract": "casepath.evidence-action/1.0.0",
        "action_kind": action_kind,
        "process_node_id": next_node,
        "evidence_item_id": item["item_id"],
        "fact_id": item["fact_id"],
        "title": item["title"],
        "bounded_tool_id": item.get("bounded_tool_id") or DEFAULT_EVIDENCE_TOOL_ID,
    }
    action_sha256 = digest_value(payload)
    return EvidenceAction.model_validate(
        {
            **payload,
            "action_id": f"action.{action_sha256}",
            "action_sha256": action_sha256,
        }
    )


def derive_evidence_action_v1(state: ClaimLoopState) -> EvidenceAction | None:
    """Derive the one bounded action from an immutable accepted loop state."""

    if state.selected_action is not None or state.phase in {
        ClaimLoopPhase.DECISION_READY,
        ClaimLoopPhase.ABSTAINED,
    }:
        return state.selected_action
    return _derive_action(
        process=state.process,
        checklist=state.checklist,
        obligations=state.obligations,
        history=state.action_history,
        retired_evidence_item_ids=_retired_native_evidence_items(
            state.native_proposal_revisions
        ),
    )


def _retired_native_evidence_items(
    revisions: tuple[NativeProposalRevisionV1, ...],
) -> frozenset[str]:
    if not revisions:
        return frozenset()
    return frozenset(
        value.prior_evidence_item_id
        for value in revisions[-1].action_dispositions
        if value.disposition == "retired"
    )


def _accepted_cycle_artifacts_from_state(
    state: ClaimLoopState,
) -> AcceptedCycleArtifactsV1:
    return AcceptedCycleArtifactsV1.model_validate(
        state.accepted_cycle_artifacts.model_dump(mode="json")
    )


def _state(
    *,
    session_id: str,
    loop_id: str,
    claim_id: str,
    source_run_id: str,
    record_version: str,
    revision: int,
    accepted: dict[str, Any],
    observations: tuple[ClaimObservation, ...],
    projection_ledger: tuple[ProjectionLedgerEntry, ...],
    selected_action: EvidenceAction | None,
    action_history: tuple[ActionHistoryEntry, ...],
    corrections: tuple[ScopedCorrection, ...],
    reuse_receipts: tuple[CorrectionReuseReceipt, ...],
    native_proposal_revisions: tuple[NativeProposalRevisionV1, ...],
    six_agent_verification: dict[str, Any],
    six_agent_graph_audit: dict[str, Any],
    six_agent_cycle_receipt: SixAgentCycleReceipt,
    upstream_source_run_activity: BoundActivity,
    source_acceptance_activity: BoundActivity,
    incremental_loop_activity: BoundActivity,
    active_dispatch_sha256: str | None,
    active_dispatch_owner: str | None,
    active_dispatch_expires_at: str | None,
    last_event_sha256: str,
    force_select: bool,
    accepted_cycle_artifacts: AcceptedCycleArtifactsV1 | Mapping[str, Any] | None = None,
) -> ClaimLoopState:
    (
        facts,
        fact_catalog_sha256,
        process,
        checklist,
        obligations,
        uncertainty,
        blocking_uncertainty,
        provenance,
        sufficiency,
        deterministic_gate_receipt,
    ) = _project_artifacts(
        accepted=accepted,
        observations=observations,
        corrections=corrections,
        projection_ledger=projection_ledger,
        accepted_cycle_artifacts=accepted_cycle_artifacts,
    )
    if accepted_cycle_artifacts is None:
        final_claim_brief = six_agent_graph_audit.get("final_claim_brief")
        if not isinstance(final_claim_brief, Mapping):
            raise ClaimLoopError("cycle graph audit has no accepted final brief")
        cycle_payload = {
            "contract": "casepath.accepted-cycle-artifacts/1.0.0",
            "facts": list(facts),
            "process": process,
            "checklist": checklist,
            "final_claim_brief": dict(final_claim_brief),
            "verification": six_agent_verification,
            "role_artifacts": build_accepted_role_artifacts_v1(
                facts=facts,
                graph_audit=six_agent_graph_audit,
            ).model_dump(mode="json"),
        }
        accepted_cycle = AcceptedCycleArtifactsV1.model_validate(
            {**cycle_payload, "receipt_sha256": digest_value(cycle_payload)}
        )
    else:
        accepted_cycle = AcceptedCycleArtifactsV1.model_validate(
            accepted_cycle_artifacts.model_dump(mode="json")
            if isinstance(accepted_cycle_artifacts, AcceptedCycleArtifactsV1)
            else dict(accepted_cycle_artifacts)
        )
    try:
        validate_accepted_role_artifacts_v1(
            accepted_cycle_artifacts=accepted_cycle,
            graph_audit=six_agent_graph_audit,
        )
    except ClaimLoopCycleError as exc:
        raise ClaimLoopError(str(exc)) from exc
    if (
        six_agent_cycle_receipt.source_run_id != source_run_id
        or six_agent_cycle_receipt.loop_id != loop_id
        or six_agent_cycle_receipt.playbook_template_sha256
        != accepted["playbook_template"]["template_sha256"]
        or six_agent_cycle_receipt.facts_sha256 != digest_value(list(facts))
        or six_agent_cycle_receipt.process_sha256 != digest_value(process)
        or six_agent_cycle_receipt.checklist_sha256 != digest_value(checklist)
        or six_agent_cycle_receipt.accepted_cycle_artifacts_sha256
        != accepted_cycle.receipt_sha256
        or six_agent_cycle_receipt.final_claim_brief_sha256
        != digest_value(accepted_cycle.final_claim_brief)
        or six_agent_cycle_receipt.verification_sha256
        != digest_value(six_agent_verification)
        or six_agent_verification.get("valid") is not True
        or six_agent_verification.get("computed") is not True
        or six_agent_verification.get("facts_sha256") != digest_value(list(facts))
        or six_agent_verification.get("process_sha256") != digest_value(process)
        or six_agent_verification.get("checklist_sha256") != digest_value(checklist)
        or six_agent_verification.get("whole_playbook_hash")
        != digest_value({"process": process, "checklist": checklist})
        or (
            six_agent_cycle_receipt.transport_mode != "accepted_source_run"
            and six_agent_verification != deterministic_gate_receipt
        )
    ):
        raise ClaimLoopError("six-agent cycle receipt does not bind projected state")
    audit_gates = {
        value.get("agent_id"): value
        for value in six_agent_graph_audit.get("deterministic_gates", [])
        if isinstance(value, Mapping)
    }
    audit_agents = {
        value.get("agent_id"): value
        for value in six_agent_graph_audit.get("agents", [])
        if isinstance(value, Mapping)
    }
    if (
        audit_agents.get("canonical_facts", {}).get("output_artifact_hash")
        != digest_value(list(facts))
        or audit_gates.get("deterministic_process_gate", {}).get(
            "output_artifact_hash"
        )
        != digest_value(process)
        or audit_gates.get("deterministic_evidence_gate", {}).get(
            "output_artifact_hash"
        )
        != digest_value(checklist)
        or audit_gates.get("whole_playbook_gate", {}).get(
            "verification_report_hash"
        )
        != digest_value(six_agent_verification)
        or audit_gates.get("whole_playbook_gate", {}).get(
            "verification_whole_playbook_hash"
        )
        != six_agent_verification.get("whole_playbook_hash")
        or audit_gates.get("whole_playbook_gate", {}).get(
            "final_brief_artifact_hash"
        )
        != digest_value(accepted_cycle.final_claim_brief)
        or audit_gates.get("whole_playbook_gate", {}).get(
            "output_artifact_hash"
        )
        != digest_value(
            {
                "process": process,
                "checklist": checklist,
                "final_brief": accepted_cycle.final_claim_brief,
            }
        )
    ):
        raise ClaimLoopError("six-agent graph audit does not bind projected state")
    terminal_mode: str | None = None
    abstain_reason: str | None = None
    phase = ClaimLoopPhase.REPLANNING if revision > 1 else ClaimLoopPhase.COMPILED
    if sufficiency.status is SufficiencyStatus.DECISION_READY:
        selected_action = None
        terminal_mode = "finalize"
        phase = ClaimLoopPhase.DECISION_READY
    elif force_select:
        selected_action = _derive_action(
            process=process,
            checklist=checklist,
            obligations=obligations,
            history=action_history,
            retired_evidence_item_ids=_retired_native_evidence_items(
                native_proposal_revisions
            ),
        )
        if selected_action is None:
            terminal_mode = "abstain"
            abstain_reason = "mandatory evidence is unresolved and no bounded action remains"
            phase = ClaimLoopPhase.ABSTAINED
            sufficiency = SufficiencyState(
                status=SufficiencyStatus.ABSTAIN,
                unresolved_mandatory_obligation_ids=(
                    sufficiency.unresolved_mandatory_obligation_ids
                ),
                contradicted_obligation_ids=sufficiency.contradicted_obligation_ids,
                provenance_complete=sufficiency.provenance_complete,
            )
        else:
            phase = ClaimLoopPhase.AWAITING_OBSERVATION
    elif active_dispatch_sha256 is not None and selected_action is not None:
        phase = ClaimLoopPhase.DISPATCHING
    elif selected_action is not None:
        phase = ClaimLoopPhase.AWAITING_OBSERVATION
    payload = {
        "contract": "casepath.claim-loop-state/1.0.0",
        "session_id": session_id,
        "loop_id": loop_id,
        "claim_id": claim_id,
        "source_run_id": source_run_id,
        "record_version": record_version,
        "revision": revision,
        "phase": phase.value,
        "accepted_artifacts_sha256": digest_value(accepted),
        "accepted_artifacts": deepcopy(accepted),
        "observations": [value.model_dump(mode="json") for value in observations],
        "projection_ledger": [
            value.model_dump(mode="json") for value in projection_ledger
        ],
        "facts": list(facts),
        "fact_catalog_sha256": fact_catalog_sha256,
        "process": process,
        "checklist": checklist,
        "accepted_cycle_artifacts_sha256": accepted_cycle.receipt_sha256,
        "accepted_cycle_artifacts": accepted_cycle.model_dump(mode="json"),
        "deterministic_gate_receipt": deterministic_gate_receipt,
        "six_agent_verification": deepcopy(six_agent_verification),
        "six_agent_graph_audit": deepcopy(six_agent_graph_audit),
        "six_agent_cycle_receipt": six_agent_cycle_receipt.model_dump(mode="json"),
        "upstream_source_run_activity": upstream_source_run_activity.model_dump(
            mode="json"
        ),
        "source_acceptance_activity": source_acceptance_activity.model_dump(
            mode="json"
        ),
        "incremental_loop_activity": incremental_loop_activity.model_dump(
            mode="json"
        ),
        "total_bound_activity": _total_activity(
            upstream_source_run_activity,
            source_acceptance_activity,
            incremental_loop_activity,
        ).model_dump(mode="json"),
        "obligations": [value.model_dump(mode="json") for value in obligations],
        "uncertainty_fact_ids": list(uncertainty),
        "blocking_uncertainty_fact_ids": list(blocking_uncertainty),
        "selected_action": (
            selected_action.model_dump(mode="json") if selected_action else None
        ),
        "action_history": [value.model_dump(mode="json") for value in action_history],
        "sufficiency": sufficiency.model_dump(mode="json"),
        "provenance_edges": [value.model_dump(mode="json") for value in provenance],
        "corrections": [value.model_dump(mode="json") for value in corrections],
        "correction_reuse_receipts": [
            value.model_dump(mode="json") for value in reuse_receipts
        ],
        "active_dispatch_sha256": active_dispatch_sha256,
        "active_dispatch_owner": active_dispatch_owner,
        "active_dispatch_expires_at": active_dispatch_expires_at,
        "terminal_mode": terminal_mode,
        "abstain_reason": abstain_reason,
        "last_event_sha256": last_event_sha256,
    }
    if native_proposal_revisions:
        payload["native_proposal_revisions"] = [
            value.model_dump(mode="json") for value in native_proposal_revisions
        ]
    return ClaimLoopState.model_validate(
        {**payload, "state_sha256": digest_value(payload)}
    )


def reduce_claim_loop_event(
    state: ClaimLoopState | None,
    *,
    event_type: str,
    command: Mapping[str, Any],
    sequence: int,
    event_sha256: str,
    timestamp: str,
) -> ClaimLoopState:
    """Pure deterministic reducer. Persistence supplies sequence and event hash."""

    if state is None:
        if event_type != "LOOP_CREATED" or sequence != 1:
            raise ClaimLoopError("the first loop event must create the loop")
        accepted = _accepted_artifacts(command["accepted_result"])
        cycle_receipt = SixAgentCycleReceipt.model_validate(
            command["six_agent_cycle_receipt"]
        )
        six_agent_verification = deepcopy(command["six_agent_verification"])
        six_agent_graph_audit = deepcopy(command["six_agent_graph_audit"])
        source_acceptance_activity = BoundActivity.model_validate(
            command["source_acceptance_activity"]
        )
        upstream_source_run_activity = BoundActivity.model_validate(
            command["upstream_source_run_activity"]
        )
        if upstream_source_run_activity.scope != "upstream_source_run":
            raise ClaimLoopError("upstream source activity scope is invalid")
        upstream_source_graph_audit = command.get("upstream_source_graph_audit")
        if upstream_source_graph_audit is not None and not isinstance(
            upstream_source_graph_audit, Mapping
        ):
            raise ClaimLoopError("upstream source graph audit is invalid")
        expected_upstream_activity = _upstream_activity_from_graph_audit_v1(
            upstream_source_graph_audit
        )
        if upstream_source_run_activity != expected_upstream_activity:
            raise ClaimLoopError(
                "upstream source activity does not match its graph audit"
            )
        _validate_cycle_evidence_v1(
            receipt=cycle_receipt,
            verification=six_agent_verification,
            graph_audit=six_agent_graph_audit,
        )
        expected_source_activity = bound_activity_from_cycle_receipt_v1(
            scope="source_acceptance",
            receipt=cycle_receipt,
        )
        if source_acceptance_activity != expected_source_activity:
            raise ClaimLoopError(
                "source activity does not match its six-agent receipt"
            )
        incremental_loop_activity = _zero_activity("incremental_loop")
        if (
            cycle_receipt.cycle_kind != "source_acceptance"
            or cycle_receipt.prior_state_sha256 is not None
            or cycle_receipt.trigger_sha256
            != digest_value(command["accepted_result"])
        ):
            raise ClaimLoopError("source cycle receipt boundary is invalid")
        return _state(
            session_id=command["session_id"],
            loop_id=command["loop_id"],
            claim_id=command["claim_id"],
            source_run_id=command["source_run_id"],
            record_version=command["record_version"],
            revision=1,
            accepted=accepted,
            observations=(),
            projection_ledger=(),
            selected_action=None,
            action_history=(),
            corrections=(),
            reuse_receipts=(),
            native_proposal_revisions=(),
            six_agent_verification=six_agent_verification,
            six_agent_graph_audit=six_agent_graph_audit,
            six_agent_cycle_receipt=cycle_receipt,
            upstream_source_run_activity=upstream_source_run_activity,
            source_acceptance_activity=source_acceptance_activity,
            incremental_loop_activity=incremental_loop_activity,
            active_dispatch_sha256=None,
            active_dispatch_owner=None,
            active_dispatch_expires_at=None,
            last_event_sha256=event_sha256,
            force_select=False,
            accepted_cycle_artifacts=command.get("accepted_cycle_artifacts"),
        )
    if sequence != state.revision + 1:
        raise ClaimLoopError("event sequence does not extend loop state")
    accepted = deepcopy(state.accepted_artifacts)
    observations = state.observations
    projection_ledger = state.projection_ledger
    history = state.action_history
    corrections = state.corrections
    reuse_receipts = state.correction_reuse_receipts
    native_proposal_revisions = state.native_proposal_revisions
    active_dispatch_sha256 = state.active_dispatch_sha256
    active_dispatch_owner = state.active_dispatch_owner
    active_dispatch_expires_at = state.active_dispatch_expires_at
    selected_action = state.selected_action
    six_agent_verification = deepcopy(state.six_agent_verification)
    six_agent_graph_audit = deepcopy(state.six_agent_graph_audit)
    six_agent_cycle_receipt = state.six_agent_cycle_receipt
    upstream_source_run_activity = state.upstream_source_run_activity
    source_acceptance_activity = state.source_acceptance_activity
    incremental_loop_activity = state.incremental_loop_activity
    accepted_cycle_artifacts = _accepted_cycle_artifacts_from_state(state)
    force_select = False
    if event_type == "NATIVE_PROPOSAL_REVISION_RECORDED":
        proposal_revision = NativeProposalRevisionV1.model_validate(
            command.get("proposal_revision")
        )
        request_identity = command.get("request_identity")
        if (
            set(command) != {
                "proposal_revision",
                "request_identity",
                "client_idempotency_key",
                "client_request_sha256",
            }
            or not isinstance(command.get("client_idempotency_key"), str)
            or not is_sha256(command.get("client_request_sha256"))
            or not isinstance(request_identity, Mapping)
            or set(request_identity) != {
                "contract",
                "claim_id",
                "loop_id",
                "prior_cycle_id",
                "cycle_id",
                "source_prefix_sha256",
                "proposal_sha256",
                "revision_packet_sha256",
            }
            or request_identity.get("contract")
            != "casepath.native-proposal-revision-request/1.0.0"
            or request_identity.get("claim_id") != proposal_revision.claim_id
            or request_identity.get("loop_id") != proposal_revision.loop_id
            or request_identity.get("prior_cycle_id")
            != proposal_revision.prior_cycle_id
            or request_identity.get("cycle_id") != proposal_revision.cycle_id
            or request_identity.get("source_prefix_sha256")
            != proposal_revision.source_prefix_sha256
            or request_identity.get("proposal_sha256")
            != proposal_revision.proposal_sha256
            or not is_sha256(request_identity.get("revision_packet_sha256"))
            or proposal_revision.claim_id != state.claim_id
            or proposal_revision.loop_id != state.loop_id
            or proposal_revision.parent_revision != state.revision
            or proposal_revision.parent_state_sha256 != state.state_sha256
            or any(
                value.cycle_id == proposal_revision.cycle_id
                for value in native_proposal_revisions
            )
        ):
            raise ClaimLoopError("native proposal revision lineage is invalid")
        package = state.accepted_artifacts.get("observable_package")
        native_receipt = (
            package.get("native_proposal_receipt")
            if isinstance(package, Mapping)
            else None
        )
        prior_cycle_id = (
            native_proposal_revisions[-1].cycle_id
            if native_proposal_revisions
            else native_receipt.get("cycle_id")
            if isinstance(native_receipt, Mapping)
            else None
        )
        if proposal_revision.prior_cycle_id != prior_cycle_id:
            raise ClaimLoopError("native proposal revision skips its prior cycle")
        native_proposal_revisions = (
            *native_proposal_revisions,
            proposal_revision,
        )
        retired_items = _retired_native_evidence_items(
            native_proposal_revisions
        )
        if (
            selected_action is not None
            and selected_action.evidence_item_id in retired_items
        ):
            if active_dispatch_sha256 is not None:
                raise ClaimLoopError("an active dispatch cannot be retired by proposal")
            selected_action = None
            force_select = True
    elif event_type == "ACTION_SELECTED":
        if state.phase in {ClaimLoopPhase.DECISION_READY, ClaimLoopPhase.ABSTAINED}:
            raise ClaimLoopError("terminal claim loop cannot select another action")
        if selected_action is not None:
            raise ClaimLoopError("claim loop already has an outstanding action")
        force_select = True
    elif event_type == "ACTION_DISPATCH_STARTED":
        protocol_value = command.get("insurance_protocol_v1")
        protocol_records = (
            InsuranceProtocolRecordSetV1.model_validate_json(
                canonical_json_bytes(protocol_value)
            )
            if protocol_value is not None
            else None
        )
        if protocol_records is not None:
            if (
                selected_action is not None
                or protocol_records.action_receipt is not None
                or protocol_records.proposal.session_id != state.session_id
                or protocol_records.proposal.loop_id != state.loop_id
                or protocol_records.proposal.claim_id != state.claim_id
                or protocol_records.proposal.record_version != state.record_version
                or protocol_records.proposal.source_revision != state.revision
                or protocol_records.proposal.source_state_sha256
                != state.state_sha256
                or command.get("protocol_record_set_sha256")
                != protocol_records.record_set_sha256
            ):
                raise ClaimLoopError("protocol intent admission boundary is invalid")
            selected_action = protocol_records.decision.compatibility_action
        if selected_action is None:
            raise ClaimLoopError("dispatch requires a selected action")
        if active_dispatch_sha256 is not None:
            raise ClaimLoopError("an action dispatch is already active")
        if command.get("action_id") != selected_action.action_id:
            raise ClaimLoopError("dispatch is not bound to the selected action")
        if command.get("action_sha256") != selected_action.action_sha256:
            raise ClaimLoopError("dispatch action hash changed")
        adapter_id = command.get("adapter_id")
        if not isinstance(adapter_id, str) or not adapter_id:
            raise ClaimLoopError("dispatch requires a bounded adapter identity")
        if adapter_id != selected_action.bounded_tool_id:
            raise ClaimLoopError("dispatch adapter lacks the selected action capability")
        lease_owner = command.get("lease_owner")
        lease_expires_at = command.get("lease_expires_at")
        client_idempotency_key = command.get("client_idempotency_key")
        client_request_type = command.get("client_request_type", "advance")
        advance_request_sha256 = command.get(
            "client_request_sha256", command.get("advance_request_sha256")
        )
        client_result_idempotency_key = command.get(
            "client_result_idempotency_key"
        )
        client_dispatch_idempotency_key = command.get(
            "client_dispatch_idempotency_key"
        )
        dispatch_generation = command.get("dispatch_generation")
        if (
            not isinstance(lease_owner, str)
            or not lease_owner
            or not isinstance(lease_expires_at, str)
            or _timestamp(lease_expires_at) <= _timestamp(timestamp)
            or not isinstance(client_idempotency_key, str)
            or not client_idempotency_key
            or not isinstance(advance_request_sha256, str)
            or client_result_idempotency_key
            != claim_loop_internal_event_key_v1(
                session_id=state.session_id,
                loop_id=state.loop_id,
                client_idempotency_key=client_idempotency_key,
                request_type=client_request_type,
                request_sha256=advance_request_sha256,
                event_kind="result",
            )
            or client_dispatch_idempotency_key
            != claim_loop_internal_event_key_v1(
                session_id=state.session_id,
                loop_id=state.loop_id,
                client_idempotency_key=client_idempotency_key,
                request_type=client_request_type,
                request_sha256=advance_request_sha256,
                event_kind="dispatch",
            )
            or not isinstance(dispatch_generation, int)
            or isinstance(dispatch_generation, bool)
            or dispatch_generation < 1
        ):
            raise ClaimLoopError("dispatch lease identity or expiry is invalid")
        if protocol_records is not None and (
            lease_expires_at != protocol_records.decision.effective_until
        ):
            raise ClaimLoopError("protocol intent expiry differs from dispatch lease")
        # Bind the lease to this exact journal event, not only to action/adapter
        # semantics; a later legitimate attempt at the same action is distinct.
        active_dispatch_sha256 = event_sha256
        active_dispatch_owner = lease_owner
        active_dispatch_expires_at = lease_expires_at
    elif event_type in {
        "PROTOCOL_EXECUTION_STARTED",
        "PROTOCOL_ACTION_RECEIPT_RECORDED",
        "PROTOCOL_SOURCE_OBSERVATION_RECORDED",
        "PROTOCOL_ASSERTION_NORMALIZED",
        "PROTOCOL_INTERPRETATION_RECORDED",
    }:
        protocol_records = InsuranceProtocolRecordSetV1.model_validate_json(
            canonical_json_bytes(command.get("insurance_protocol_v1"))
        )
        if (
            selected_action is None
            or active_dispatch_sha256 is None
            or command.get("dispatch_sha256") != active_dispatch_sha256
            or command.get("intent_sha256")
            != protocol_records.intent.intent_sha256
            or command.get("protocol_record_set_sha256")
            != protocol_records.record_set_sha256
            or protocol_records.proposal.session_id != state.session_id
            or protocol_records.proposal.loop_id != state.loop_id
            or protocol_records.proposal.claim_id != state.claim_id
            or protocol_records.proposal.record_version != state.record_version
            or protocol_records.decision.compatibility_action.action_sha256
            != selected_action.action_sha256
        ):
            raise ClaimLoopError("protocol transition is not bound to active intent")
        receipt = protocol_records.action_receipt
        if event_type == "PROTOCOL_EXECUTION_STARTED":
            if receipt is not None:
                raise ClaimLoopError("execution start cannot claim an action outcome")
        elif event_type == "PROTOCOL_ACTION_RECEIPT_RECORDED":
            if (
                receipt is None
                or protocol_records.source_observation is not None
            ):
                raise ClaimLoopError("action receipt transition has invalid scope")
        elif event_type == "PROTOCOL_SOURCE_OBSERVATION_RECORDED":
            if (
                receipt is None
                or receipt.status is not ActionReceiptStatus.COMMITTED
                or protocol_records.source_observation is None
                or protocol_records.normalized_assertion is not None
            ):
                raise ClaimLoopError("source observation transition is invalid")
        elif event_type == "PROTOCOL_ASSERTION_NORMALIZED":
            if (
                protocol_records.normalized_assertion is None
                or protocol_records.interpretation is not None
            ):
                raise ClaimLoopError("normalized assertion transition is invalid")
        elif protocol_records.interpretation is None:
            raise ClaimLoopError("interpretation transition is incomplete")
    elif event_type == "OBSERVATION_INGESTED":
        observation = ClaimObservation.model_validate(command["observation"])
        artifact = ToolArtifactReceipt.model_validate(
            command.get("tool_artifact_receipt")
        )
        authority_binding = command.get("evidence_authority_binding")
        if (
            selected_action is not None
            and selected_action.bounded_tool_id
            == "loopback-source-byte-acquisition-v1"
        ):
            expected_binding_keys = {
                "contract",
                "proposal_sha256",
                "admission_receipt_sha256",
                "interpretation_receipt_sha256",
                "acquisition_receipt_sha256",
                "registration_receipt_sha256",
                "authority_id",
                "authority_source_sha256",
                "binding_sha256",
            }
            if (
                not isinstance(authority_binding, Mapping)
                or set(authority_binding) != expected_binding_keys
                or authority_binding.get("contract")
                != "casepath.workspace-evidence-authority-binding/1.0.0"
                or authority_binding.get("authority_id")
                != "casepath.independent-evidence-authority/1.0.0"
                or authority_binding.get("interpretation_receipt_sha256")
                != artifact.interpretation.receipt_sha256
                or authority_binding.get("acquisition_receipt_sha256")
                != artifact.acquisition_receipt_sha256
                or not all(
                    is_sha256(authority_binding.get(key))
                    for key in (
                        "proposal_sha256",
                        "admission_receipt_sha256",
                        "registration_receipt_sha256",
                        "authority_source_sha256",
                        "binding_sha256",
                    )
                )
                or authority_binding.get("binding_sha256")
                != digest_value(
                    {
                        key: value
                        for key, value in authority_binding.items()
                        if key != "binding_sha256"
                    }
                )
            ):
                raise ClaimLoopError(
                    "workspace observation lacks its exact authority chain"
                )
        if selected_action is None or command.get("action_id") != selected_action.action_id:
            raise ClaimLoopError("observation is not bound to the selected action")
        if observation.evidence_item_id != selected_action.evidence_item_id:
            raise ClaimLoopError("observation changes an unselected obligation")
        if observation.fact_id != selected_action.fact_id:
            raise ClaimLoopError("observation changes an unselected fact")
        if (
            active_dispatch_sha256 is None
            or command.get("dispatch_sha256") != active_dispatch_sha256
            or command.get("artifact_receipt_sha256") != artifact.receipt_sha256
            or artifact.session_id != state.session_id
            or artifact.loop_id != state.loop_id
            or artifact.action_id != selected_action.action_id
            or artifact.action_sha256 != selected_action.action_sha256
            or artifact.adapter_id != selected_action.bounded_tool_id
            or artifact.acquisition_receipt.adapter_id
            != selected_action.bounded_tool_id
            or artifact.dispatch_sha256 != active_dispatch_sha256
            or artifact.observation != observation
        ):
            raise ClaimLoopError("observation is not bound to an active tool receipt")
        protocol_value = command.get("insurance_protocol_v1")
        if protocol_value is not None:
            protocol_records = InsuranceProtocolRecordSetV1.model_validate_json(
                canonical_json_bytes(protocol_value)
            )
            if (
                protocol_records.interpretation is None
                or protocol_records.normalized_assertion is None
                or protocol_records.normalized_assertion.claim_observation
                != observation
                or protocol_records.normalized_assertion.canonical_interpretation
                != artifact.interpretation
                or command.get("protocol_record_set_sha256")
                != protocol_records.record_set_sha256
                or protocol_records.decision.compatibility_action.action_sha256
                != selected_action.action_sha256
            ):
                raise ClaimLoopError("observation protocol authority is incomplete")
            thin_waist = InsuranceThinWaistRecordSetV2.model_validate_json(
                canonical_json_bytes(command.get("insurance_thin_waist_v2"))
            )
            expected_thin_waist = build_thin_waist_replan_intent_v2(
                session_id=state.session_id,
                loop_id=state.loop_id,
                claim_id=state.claim_id,
                record_version=state.record_version,
                source_state_sha256=state.state_sha256,
                source_revision=state.revision,
                records=protocol_records,
                timestamp=timestamp,
            )
            if thin_waist != expected_thin_waist:
                raise ClaimLoopError(
                    "observation lacks its interpretation-bound replan intent"
                )
        observations = (*observations, observation)
        projection_ledger = (
            *projection_ledger,
            ProjectionLedgerEntry(
                kind="observation",
                record_sha256=observation.observation_sha256,
                artifact_receipt_sha256=command["artifact_receipt_sha256"],
                recorded_at=timestamp,
            ),
        )
        six_agent_cycle_receipt = SixAgentCycleReceipt.model_validate(
            command.get("six_agent_cycle_receipt")
        )
        accepted_cycle_artifacts = deepcopy(
            command.get("accepted_cycle_artifacts")
        )
        six_agent_verification = deepcopy(command.get("six_agent_verification"))
        six_agent_graph_audit = deepcopy(command.get("six_agent_graph_audit"))
        if not isinstance(six_agent_verification, Mapping) or not isinstance(
            six_agent_graph_audit, Mapping
        ):
            raise ClaimLoopError("observation cycle evidence is invalid")
        _validate_cycle_evidence_v1(
            receipt=six_agent_cycle_receipt,
            verification=six_agent_verification,
            graph_audit=six_agent_graph_audit,
        )
        if (
            six_agent_cycle_receipt.cycle_kind != "observation"
            or six_agent_cycle_receipt.prior_state_sha256 != state.state_sha256
            or six_agent_cycle_receipt.trigger_sha256
            != observation.observation_sha256
        ):
            raise ClaimLoopError("observation cycle receipt boundary is invalid")
        incremental_loop_activity = _incremental_activity(
            incremental_loop_activity,
            six_agent_cycle_receipt,
        )
        history = (
            *history,
            ActionHistoryEntry(
                action=selected_action,
                outcome="observed",
                observation_sha256=observation.observation_sha256,
                recorded_at=timestamp,
            ),
        )
        selected_action = None
        active_dispatch_sha256 = None
        active_dispatch_owner = None
        active_dispatch_expires_at = None
        force_select = True
    elif event_type == "EVIDENCE_PROPOSAL_REJECTED":
        expected_command_keys = {
            "action_id",
            "action_sha256",
            "dispatch_sha256",
            "acquisition_receipt_sha256",
            "acquisition_receipt",
            "authority_rejection_receipt_sha256",
            "authority_rejection_receipt",
            "advance_request_sha256",
        }
        rejection = command.get("authority_rejection_receipt")
        acquisition = AcquisitionReceiptV1.model_validate(
            command.get("acquisition_receipt")
        )
        expected_rejection_keys = {
            "contract",
            "session_id",
            "loop_id",
            "claim_id",
            "record_version",
            "parent_revision",
            "parent_state_sha256",
            "action_id",
            "action_sha256",
            "dispatch_sha256",
            "acquisition_receipt_sha256",
            "acquisition_intent_id",
            "source_acquisition_receipt_sha256",
            "source_entry_sha256",
            "content_sha256",
            "proposal_sha256",
            "authority_id",
            "authority_source_sha256",
            "reason",
            "rejected_at",
            "authoritative_semantic_effect",
            "receipt_sha256",
        }
        nullable_hashes = (
            (
                rejection.get("source_acquisition_receipt_sha256"),
                rejection.get("source_entry_sha256"),
                rejection.get("content_sha256"),
                rejection.get("proposal_sha256"),
            )
            if isinstance(rejection, Mapping)
            else ()
        )
        if (
            set(command) != expected_command_keys
            or not isinstance(rejection, Mapping)
            or set(rejection) != expected_rejection_keys
            or rejection.get("contract")
            != "casepath.workspace-authority-rejection/1.0.0"
            or rejection.get("receipt_sha256")
            != digest_value(
                {
                    key: value
                    for key, value in rejection.items()
                    if key != "receipt_sha256"
                }
            )
            or command.get("authority_rejection_receipt_sha256")
            != rejection.get("receipt_sha256")
            or any(
                value is not None and not is_sha256(value)
                for value in nullable_hashes
            )
            or not isinstance(rejection.get("reason"), str)
            or not rejection.get("reason")
            or len(rejection.get("reason")) > 300
            or rejection.get("authority_id")
            != "casepath.independent-evidence-authority/1.0.0"
            or not is_sha256(rejection.get("authority_source_sha256"))
            or rejection.get("authoritative_semantic_effect") is not False
            or selected_action is None
            or active_dispatch_sha256 is None
            or acquisition.status is not ToolResultStatus.OBSERVED
            or command.get("action_id") != selected_action.action_id
            or command.get("action_sha256") != selected_action.action_sha256
            or command.get("dispatch_sha256") != active_dispatch_sha256
            or command.get("acquisition_receipt_sha256")
            != acquisition.receipt_sha256
            or acquisition.session_id != state.session_id
            or acquisition.loop_id != state.loop_id
            or acquisition.record_version != state.record_version
            or acquisition.action_id != selected_action.action_id
            or acquisition.action_sha256 != selected_action.action_sha256
            or acquisition.dispatch_sha256 != active_dispatch_sha256
            or rejection.get("session_id") != state.session_id
            or rejection.get("loop_id") != state.loop_id
            or rejection.get("claim_id") != state.claim_id
            or rejection.get("record_version") != state.record_version
            or rejection.get("parent_revision") != state.revision
            or rejection.get("parent_state_sha256") != state.state_sha256
            or rejection.get("action_id") != selected_action.action_id
            or rejection.get("action_sha256") != selected_action.action_sha256
            or rejection.get("dispatch_sha256") != active_dispatch_sha256
            or rejection.get("acquisition_receipt_sha256")
            != acquisition.receipt_sha256
            or rejection.get("rejected_at") != acquisition.acquired_at
            or (
                rejection.get("content_sha256") is not None
                and rejection.get("content_sha256")
                != acquisition.sanitized_content_sha256
            )
        ):
            raise ClaimLoopError(
                "evidence rejection is not bound to the active acquired proposal"
            )
        # This closes one operational dispatch without admitting a fact.  The
        # action, projections, queue, history, and sufficiency remain exact.
        active_dispatch_sha256 = None
        active_dispatch_owner = None
        active_dispatch_expires_at = None
    elif event_type == "PROTOCOL_REPLAN_RECEIPT_RECORDED":
        thin_waist = InsuranceThinWaistRecordSetV2.model_validate_json(
            canonical_json_bytes(command.get("insurance_thin_waist_v2"))
        )
        receipt = thin_waist.action_receipt
        if (
            receipt is None
            or command.get("thin_waist_record_set_sha256")
            != thin_waist.record_set_sha256
            or command.get("committed_replan_event_sha256")
            != state.last_event_sha256
            or receipt.committed_event_sha256 != state.last_event_sha256
            or receipt.resulting_state_sha256 != state.state_sha256
            or receipt.resulting_revision != state.revision
        ):
            raise ClaimLoopError(
                "replan receipt is not bound to the committed observation event"
            )
    elif event_type == "TOOL_UNAVAILABLE":
        acquisition = AcquisitionReceiptV1.model_validate(
            command.get("acquisition_receipt")
        )
        if selected_action is None or command.get("action_id") != selected_action.action_id:
            raise ClaimLoopError("tool failure is not bound to the selected action")
        outcome = command.get("outcome")
        if outcome not in {"unavailable", "failed"}:
            raise ClaimLoopError("tool failure outcome is invalid")
        if (
            active_dispatch_sha256 is None
            or command.get("dispatch_sha256") != active_dispatch_sha256
            or command.get("acquisition_receipt_sha256")
            != acquisition.receipt_sha256
            or acquisition.session_id != state.session_id
            or acquisition.loop_id != state.loop_id
            or acquisition.record_version != state.record_version
            or acquisition.action_id != selected_action.action_id
            or acquisition.action_sha256 != selected_action.action_sha256
            or acquisition.dispatch_sha256 != active_dispatch_sha256
            or acquisition.adapter_id != selected_action.bounded_tool_id
            or acquisition.status.value != outcome
        ):
            raise ClaimLoopError("tool failure is not bound to active dispatch")
        history = (
            *history,
            ActionHistoryEntry(
                action=selected_action,
                outcome=outcome,
                observation_sha256=None,
                recorded_at=timestamp,
            ),
        )
        selected_action = None
        active_dispatch_sha256 = None
        active_dispatch_owner = None
        active_dispatch_expires_at = None
        force_select = True
    elif event_type == "DISPATCH_UNKNOWN":
        if (
            selected_action is None
            or active_dispatch_sha256 is None
            or command.get("action_id") != selected_action.action_id
            or command.get("dispatch_sha256") != active_dispatch_sha256
        ):
            raise ClaimLoopError("unknown dispatch is not bound to active state")
        protocol_value = command.get("insurance_protocol_v1")
        if protocol_value is not None:
            protocol_records = InsuranceProtocolRecordSetV1.model_validate_json(
                canonical_json_bytes(protocol_value)
            )
            if (
                protocol_records.action_receipt is None
                or protocol_records.action_receipt.status
                is not ActionReceiptStatus.UNKNOWN
                or protocol_records.intent.intent_sha256
                != command.get("intent_sha256")
                or protocol_records.record_set_sha256
                != command.get("protocol_record_set_sha256")
            ):
                raise ClaimLoopError("protocol unknown receipt is invalid")
            # Protocol unknown retains the exact action, intent and dispatch.
            # Reconciliation may observe the existing effect but must not retry it.
        else:
            history = (
                *history,
                ActionHistoryEntry(
                    action=selected_action,
                    outcome="unknown",
                    observation_sha256=None,
                    recorded_at=timestamp,
                ),
            )
            selected_action = None
            active_dispatch_sha256 = None
            active_dispatch_owner = None
            active_dispatch_expires_at = None
            force_select = True
    elif event_type == "PROTOCOL_INTENT_CANCELLED":
        protocol_records = InsuranceProtocolRecordSetV1.model_validate_json(
            canonical_json_bytes(command.get("insurance_protocol_v1"))
        )
        if (
            selected_action is None
            or active_dispatch_sha256 is None
            or command.get("dispatch_sha256") != active_dispatch_sha256
            or protocol_records.action_receipt is None
            or protocol_records.action_receipt.status
            is not ActionReceiptStatus.CANCELLED
            or protocol_records.intent.intent_sha256
            != command.get("intent_sha256")
        ):
            raise ClaimLoopError("protocol cancellation is not bound to active intent")
        selected_action = None
        active_dispatch_sha256 = None
        active_dispatch_owner = None
        active_dispatch_expires_at = None
        force_select = True
    elif event_type in {"CORRECTION_APPLIED", "CORRECTION_REUSED"}:
        if active_dispatch_sha256 is not None:
            raise ClaimLoopError("cannot correct state during an active dispatch")
        correction = ScopedCorrection.model_validate(command["correction"])
        authority = CorrectionArtifactReceipt.model_validate(
            command.get("correction_artifact_receipt")
        )
        source_artifact = ToolArtifactReceipt.model_validate(
            command.get("source_tool_artifact_receipt")
        )
        reuse = (
            CorrectionReuseReceipt.model_validate(command["reuse_receipt"])
            if event_type == "CORRECTION_REUSED"
            else None
        )
        target_matching_artifact = (
            ToolArtifactReceipt.model_validate(
                command.get("target_matching_tool_artifact_receipt")
            )
            if reuse is not None
            else None
        )
        source_application_event = (
            load_claim_loop_event_v1(command.get("source_application_event"))
            if reuse is not None
            else None
        )
        if correction.correction_id in {
            value.correction_id for value in corrections
        }:
            raise ClaimLoopError("correction was already applied")
        if state.claim_id not in correction.scope.claim_ids:
            raise ClaimLoopError("correction is unrelated to this claim")
        if correction.record_version != state.record_version:
            raise ClaimLoopError("correction source version is stale")
        effective = _timestamp(correction.effective_at)
        current = _timestamp(timestamp)
        if effective > current:
            raise ClaimLoopError("correction is not yet effective")
        if correction.expires_at is not None and current >= _timestamp(
            correction.expires_at
        ):
            raise ClaimLoopError("correction has expired")
        fact_ids = {value["fact_id"] for value in state.facts}
        evidence_fact_ids = {
            value["item_id"]: value["fact_id"]
            for value in state.checklist.get("items", [])
        }
        if (
            correction.effect.fact_id not in fact_ids
            or evidence_fact_ids.get(correction.effect.evidence_item_id)
            != correction.effect.fact_id
        ):
            raise ClaimLoopError("correction target is outside the accepted playbook")
        target_fact = next(
            value
            for value in state.facts
            if value.get("fact_id") == correction.effect.fact_id
        )
        target_evidence = next(
            value
            for value in state.checklist.get("items", [])
            if value.get("item_id") == correction.effect.evidence_item_id
        )
        unrelated_before = [
            value
            for value in state.facts
            if value.get("fact_id") != correction.effect.fact_id
        ]
        expected_before_semantics = {
            "fact_state": target_fact.get("state"),
            "normalized_value": target_fact.get("normalized_value"),
            "value": target_fact.get("value"),
            "explanation": target_fact.get("explanation"),
            "evidence_status": target_evidence.get("status"),
        }
        if (
            command.get("before_semantics") != expected_before_semantics
            or authority.receipt_sha256
            != correction.correction_artifact_receipt_sha256
            or authority.record_version != correction.record_version
            or authority.target_claim_id != state.claim_id
            or authority.scope != correction.scope
            or authority.proposed_effect != correction.effect
            or authority.source_artifact_receipt_sha256
            != correction.source_artifact_receipt_sha256
            or authority.source_ref != correction.source_ref
            or authority.issued_at != correction.effective_at
            or authority.expires_at != correction.expires_at
            or source_artifact.receipt_sha256
            != correction.source_artifact_receipt_sha256
            or source_artifact.session_id != authority.session_id
            or source_artifact.loop_id != authority.loop_id
            or source_artifact.action_id != authority.target_action_id
            or source_artifact.artifact_source_version
            != authority.record_version
            or source_artifact.observation.observation_sha256
            != authority.source_observation_sha256
            or (
                authority.source_ref not in source_artifact.observation.source_refs
                and not _valid_custom_correction_source_binding_v1(
                    command.get("correction_source_binding"),
                    correction=correction,
                    authority=authority,
                    source_artifact=source_artifact,
                    correction_source_artifact=command.get(
                        "correction_source_artifact"
                    ),
                    correction_source_refs=command.get("correction_source_refs"),
                )
            )
            or (
                correction.effect.fact_state != "known"
                and correction.effect.normalized_value is not None
            )
        ):
            raise ClaimLoopError("correction authority binding is invalid")
        if event_type == "CORRECTION_APPLIED":
            if (
                authority.session_id != state.session_id
                or authority.loop_id != state.loop_id
                or authority.parent_state_sha256 != state.state_sha256
                or digest_value(target_fact) != authority.before_fact_sha256
                or digest_value(target_evidence)
                != authority.before_evidence_sha256
                or digest_value(unrelated_before)
                != authority.unrelated_facts_before_sha256
            ):
                raise ClaimLoopError("local correction parent binding is invalid")
            expected_after_fact_sha256 = authority.expected_after_fact_sha256
            expected_after_evidence_sha256 = (
                authority.expected_after_evidence_sha256
            )
            expected_unrelated_after_sha256 = (
                authority.unrelated_facts_after_sha256
            )
        else:
            assert reuse is not None
            assert target_matching_artifact is not None
            assert source_application_event is not None
            if (
                reuse.correction_sha256 != correction.correction_sha256
                or reuse.correction_artifact_receipt_sha256
                != authority.receipt_sha256
                or reuse.source_artifact_receipt_sha256
                != source_artifact.receipt_sha256
                or reuse.target_matching_artifact_receipt_sha256
                != target_matching_artifact.receipt_sha256
                or reuse.source_application_event_sha256
                != source_application_event.event_sha256
                or reuse.source_application_state_sha256
                != source_application_event.resulting_state_sha256
                or source_application_event.session_id
                != reuse.source_session_id
                or source_application_event.loop_id != reuse.source_loop_id
                or source_application_event.event_type
                != "CORRECTION_APPLIED"
                or source_application_event.command.get("correction", {}).get(
                    "correction_id"
                )
                != correction.correction_id
                or reuse.source_session_id != authority.session_id
                or reuse.source_loop_id != authority.loop_id
                or reuse.target_session_id != state.session_id
                or reuse.target_loop_id != state.loop_id
                or reuse.target_claim_id != state.claim_id
                or reuse.record_version != state.record_version
                or reuse.target_parent_state_sha256 != state.state_sha256
                or reuse.target_before_fact_sha256 != digest_value(target_fact)
                or reuse.target_before_evidence_sha256
                != digest_value(target_evidence)
                or reuse.target_unrelated_facts_before_sha256
                != digest_value(unrelated_before)
                or reuse.applied_fact_ids != (correction.effect.fact_id,)
                or reuse.applied_evidence_item_ids
                != (correction.effect.evidence_item_id,)
                or reuse.source_loop_id == state.loop_id
                or command.get("source_session_id") != state.session_id
                or target_matching_artifact.session_id != state.session_id
                or target_matching_artifact.loop_id != state.loop_id
                or target_matching_artifact.artifact_source_version
                != state.record_version
                or target_matching_artifact.observation.fact_id
                != correction.effect.fact_id
                or target_matching_artifact.observation.evidence_item_id
                != correction.effect.evidence_item_id
                or not any(
                    source_span_authority_v1(value)
                    == source_span_authority_v1(correction.source_ref)
                    for value in target_matching_artifact.observation.source_refs
                )
                or not any(
                    entry.artifact_receipt_sha256
                    == target_matching_artifact.receipt_sha256
                    for entry in state.projection_ledger
                )
            ):
                raise ClaimLoopError("correction reuse receipt binding is invalid")
            expected_after_fact_sha256 = (
                reuse.target_expected_after_fact_sha256
            )
            expected_after_evidence_sha256 = (
                reuse.target_expected_after_evidence_sha256
            )
            expected_unrelated_after_sha256 = (
                reuse.target_unrelated_facts_after_sha256
            )
        corrections = (*corrections, correction)
        projection_ledger = (
            *projection_ledger,
            ProjectionLedgerEntry(
                kind="correction",
                record_sha256=correction.correction_sha256,
                artifact_receipt_sha256=(
                    correction.source_artifact_receipt_sha256
                ),
                # Projection chronology is an immutable correction property;
                # event created_at remains the admission clock used for expiry.
                recorded_at=correction.effective_at,
            ),
        )
        projected_correction = project_claim_loop_artifacts_v1(
            accepted=accepted,
            observations=observations,
            corrections=corrections,
            projection_ledger=projection_ledger,
        )
        target_after_fact = next(
            value
            for value in projected_correction["facts"]
            if value.get("fact_id") == correction.effect.fact_id
        )
        target_after_evidence = next(
            value
            for value in projected_correction["checklist"].get("items", [])
            if value.get("item_id") == correction.effect.evidence_item_id
        )
        unrelated_after = [
            value
            for value in projected_correction["facts"]
            if value.get("fact_id") != correction.effect.fact_id
        ]
        expected_after_semantics = {
            "fact_state": target_after_fact.get("state"),
            "normalized_value": target_after_fact.get("normalized_value"),
            "value": target_after_fact.get("value"),
            "explanation": target_after_fact.get("explanation"),
            "evidence_status": target_after_evidence.get("status"),
        }
        if (
            command.get("after_semantics") != expected_after_semantics
            or digest_value(target_after_fact) != expected_after_fact_sha256
            or digest_value(target_after_evidence)
            != expected_after_evidence_sha256
            or digest_value(unrelated_after)
            != expected_unrelated_after_sha256
            or digest_value(unrelated_before) != digest_value(unrelated_after)
            or (
                digest_value(target_fact) == digest_value(target_after_fact)
                and digest_value(target_evidence)
                == digest_value(target_after_evidence)
            )
        ):
            raise ClaimLoopError(
                "correction transition/locality proof is invalid or a no-op"
            )
        six_agent_cycle_receipt = SixAgentCycleReceipt.model_validate(
            command.get("six_agent_cycle_receipt")
        )
        accepted_cycle_artifacts = deepcopy(
            command.get("accepted_cycle_artifacts")
        )
        six_agent_verification = deepcopy(command.get("six_agent_verification"))
        six_agent_graph_audit = deepcopy(command.get("six_agent_graph_audit"))
        if not isinstance(six_agent_verification, Mapping) or not isinstance(
            six_agent_graph_audit, Mapping
        ):
            raise ClaimLoopError("correction cycle evidence is invalid")
        _validate_cycle_evidence_v1(
            receipt=six_agent_cycle_receipt,
            verification=six_agent_verification,
            graph_audit=six_agent_graph_audit,
        )
        if (
            six_agent_cycle_receipt.cycle_kind != "correction"
            or six_agent_cycle_receipt.prior_state_sha256 != state.state_sha256
            or six_agent_cycle_receipt.trigger_sha256
            != correction.correction_sha256
        ):
            raise ClaimLoopError("correction cycle receipt boundary is invalid")
        incremental_loop_activity = _incremental_activity(
            incremental_loop_activity,
            six_agent_cycle_receipt,
        )
        if reuse is not None:
            reuse_receipts = (
                *reuse_receipts,
                reuse,
            )
        selected_action = None
        force_select = True
    else:
        raise ClaimLoopError("unsupported claim loop event")
    next_state = _state(
        session_id=state.session_id,
        loop_id=state.loop_id,
        claim_id=state.claim_id,
        source_run_id=state.source_run_id,
        record_version=state.record_version,
        revision=sequence,
        accepted=accepted,
        observations=observations,
        projection_ledger=projection_ledger,
        selected_action=selected_action,
        action_history=history,
        corrections=corrections,
        reuse_receipts=reuse_receipts,
        native_proposal_revisions=native_proposal_revisions,
        six_agent_verification=six_agent_verification,
        six_agent_graph_audit=six_agent_graph_audit,
        six_agent_cycle_receipt=six_agent_cycle_receipt,
        upstream_source_run_activity=upstream_source_run_activity,
        source_acceptance_activity=source_acceptance_activity,
        incremental_loop_activity=incremental_loop_activity,
        active_dispatch_sha256=active_dispatch_sha256,
        active_dispatch_owner=active_dispatch_owner,
        active_dispatch_expires_at=active_dispatch_expires_at,
        last_event_sha256=event_sha256,
        force_select=force_select,
        accepted_cycle_artifacts=accepted_cycle_artifacts,
    )
    if event_type == "ACTION_SELECTED" and "advance_request_sha256" in command:
        action = next_state.selected_action
        if (
            command.get("selected_from_revision") != state.revision
            or command.get("selected_result_revision") != sequence
            or command.get("selected_action_id")
            != (action.action_id if action is not None else None)
            or command.get("selected_action_sha256")
            != (action.action_sha256 if action is not None else None)
        ):
            raise ClaimLoopError("advance selection lineage binding is invalid")
    return next_state


def decision_ready_packet(state: ClaimLoopState) -> DecisionReadyPacket:
    payload = {
        "contract": "casepath.decision-ready-packet/1.0.0",
        "loop_id": state.loop_id,
        "claim_id": state.claim_id,
        "phase": state.phase.value,
        "terminal_mode": state.terminal_mode,
        "current_overlay": deepcopy(state.process["current_overlay"]),
        "selected_action": (
            state.selected_action.model_dump(mode="json")
            if state.selected_action
            else None
        ),
        "obligations": [value.model_dump(mode="json") for value in state.obligations],
        "sufficiency": state.sufficiency.model_dump(mode="json"),
        "provenance_edges": [
            value.model_dump(mode="json") for value in state.provenance_edges
        ],
        "deterministic_gate_receipt_sha256": state.deterministic_gate_receipt[
            "receipt_sha256"
        ],
        "six_agent_cycle_receipt_sha256": (
            state.six_agent_cycle_receipt.receipt_sha256
        ),
        "accepted_cycle_artifacts_sha256": (
            state.accepted_cycle_artifacts.receipt_sha256
        ),
        "accepted_cycle_artifacts": state.accepted_cycle_artifacts.model_dump(
            mode="json"
        ),
        "source_state_sha256": state.state_sha256,
    }
    return DecisionReadyPacket.model_validate(
        {**payload, "packet_sha256": digest_value(payload)}
    )


class SyntheticMouldEvidenceAdapter:
    """Deterministic development fixture; never performs I/O or provider calls."""

    adapter_id = DEFAULT_EVIDENCE_TOOL_ID
    implementation_id = "casepath.synthetic-mould-evidence-adapter/1.0.0"
    implementation_source_sha256 = _artifact_interpreter_source_closure_sha256_v1()
    implementation_sha256 = adapter_implementation_sha256_v1(
        adapter_id=adapter_id,
        implementation_id=implementation_id,
        implementation_source_sha256=implementation_source_sha256,
    )

    def execute(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        idempotency_key: str,
        timestamp: str,
    ) -> ToolResult:
        del idempotency_key, timestamp
        template = playbook_template_from_accepted_v1(state.accepted_artifacts)
        fact = next(
            (value for value in state.facts if value.get("fact_id") == action.fact_id),
            None,
        )
        decision_key = fact.get("decision_key") if fact is not None else None
        if decision_key is None:
            options = {"established": "", "unresolved": ""}
            unresolved = "unresolved"
        else:
            options = template.decision_options.get(decision_key, {})
            unresolved = template.fail_closed_normalized_values.get(decision_key)
        finding = next((value for value in options if value != unresolved), None)
        if finding is None:
            return ToolResult(
                status=ToolResultStatus.UNAVAILABLE,
                source_locator=f"synthetic-mould:{action.evidence_item_id}",
                reason="the deterministic fixture has no result for this action",
            )
        value = canonical_json_bytes(
            {
                "schema": StructuredMouldArtifactInterpreterV2.schema,
                "document_kind": StructuredMouldArtifactInterpreterV2.document_kind,
                "evidence_item_id": action.evidence_item_id,
                "finding": finding,
                "basis": (
                    "Deterministic generated fixture for the selected evidence action."
                ),
            }
        ).decode("utf-8")
        return ToolResult(
            status=ToolResultStatus.OBSERVED,
            sanitized_content=value,
            artifact_source_version=state.record_version,
            artifact_page_count=1,
            source_locator=f"synthetic-mould:{action.evidence_item_id}",
        )


class UnavailableEvidenceAdapter:
    adapter_id = DEFAULT_EVIDENCE_TOOL_ID
    implementation_id = "casepath.unavailable-evidence-adapter/1.0.0"
    implementation_source_sha256 = _artifact_interpreter_source_closure_sha256_v1()
    implementation_sha256 = adapter_implementation_sha256_v1(
        adapter_id=adapter_id,
        implementation_id=implementation_id,
        implementation_source_sha256=implementation_source_sha256,
    )

    def execute(
        self,
        *,
        action: EvidenceAction,
        state: ClaimLoopState,
        idempotency_key: str,
        timestamp: str,
    ) -> ToolResult:
        return ToolResult(
            status=ToolResultStatus.UNAVAILABLE,
            source_locator=f"unavailable:{action.evidence_item_id}",
            reason="evidence source is unavailable",
        )


__all__ = [
    "ClaimLoopError",
    "adapter_implementation_sha256_v1",
    "EvidenceToolAdapter",
    "EvidenceArtifactInterpreter",
    "DeterministicMouldArtifactInterpreter",
    "StructuredMouldArtifactInterpreterV2",
    "DeterministicTemplateArtifactInterpreter",
    "SyntheticMouldEvidenceAdapter",
    "ToolResult",
    "UnavailableEvidenceAdapter",
    "accepted_artifacts_from_run",
    "bound_activity_from_cycle_receipt_v1",
    "build_claim_loop_gate_receipt_v1",
    "decision_ready_packet",
    "derive_evidence_action_v1",
    "project_claim_loop_artifacts_v1",
    "playbook_template_from_accepted_v1",
    "source_span_authority_v1",
    "reduce_claim_loop_event",
]
