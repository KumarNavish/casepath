from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import re
from time import monotonic, sleep
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence

from .claim_loop import (
    ClaimLoopError,
    CorrectionToolAdapter,
    CorrectionToolResult,
    EvidenceArtifactInterpreter,
    EvidenceToolAdapter,
    ToolResultStatus,
    ToolResult,
    adapter_implementation_sha256_v1,
    accepted_artifacts_from_run,
    bound_activity_from_cycle_receipt_v1,
    build_claim_loop_gate_receipt_v1,
    decision_ready_packet,
    derive_evidence_action_v1,
    project_claim_loop_artifacts_v1,
    playbook_template_from_accepted_v1,
    source_span_authority_v1,
)
from .claim_loop_cycle import (
    ClaimLoopCycleError,
    build_accepted_cycle_artifacts_v1,
    build_six_agent_cycle_receipt_v1,
    derive_graph_activity_v1,
)
from .claim_loop_contracts import (
    AcquisitionReceiptV1,
    BoundActivity,
    ClaimLoopCommandReceipt,
    ClaimLoopPhase,
    ClaimLoopState,
    ClaimObservation,
    ClaimSourceRef,
    NativeProposalRevisionV1,
    CorrectionArtifactReceipt,
    CorrectionReuseReceipt,
    CorrectionScope,
    ProjectionLedgerEntry,
    ScopedCorrection,
    SixAgentCycleReceipt,
    ToolArtifactReceipt,
    claim_loop_internal_event_key_v1,
)
from .claim_loop_store import ClaimLoopStore, ClaimLoopStoreError
from .foundation.common import canonical_json_bytes, digest_text, digest_value, is_sha256
from .insurance_protocol_runtime import (
    InsuranceProtocolAuthorityError,
    build_registration_authority_v1,
    build_registration_compatibility_action_v1,
    build_verified_neutral_assessment_proposal_v1,
    current_decision_scope_v1,
)
from .ecab_replay_adapter import ECABFactualHistorySpanV1
from .insurance_protocol_v1 import (
    ActionReceiptStatus,
    ActionReceiptV1,
    InsuranceProtocolRecordSetV1,
    InterpretationV1,
    NormalizedAssertionV1,
    SourceObservationV1,
    hash_record_set_v1,
)
from .insurance_protocol_v2 import (
    CorrectionDeltaProjectionV1,
    InsuranceThinWaistRecordSetV2,
    InterpretationActionReceiptV2,
    VersionedCaseStateV2,
    build_thin_waist_replan_intent_v2,
    hash_thin_waist_record_set_v2,
)
from .insurance_correction_v1 import (
    MouldNeutralAssessmentCorrectionAdapterV1,
    MouldNeutralAssessmentRollbackAdapterV1,
)
from .local_artifact_registry import (
    LocalArtifactRegistryAdapterV1,
    LocalArtifactRegistryError,
    LocalRegistryMaterialV1,
)
from .data import CLAIMS, DEMO_CLAIM, observable_claim_package
from .playbook_template import MOULD_PLAYBOOK_TEMPLATE
from .storage import SYSTEM_OWNED_SESSION_IDS, Storage


class ClaimLoopServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        conflict_envelope: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.conflict_envelope = (
            deepcopy(dict(conflict_envelope)) if conflict_envelope is not None else None
        )


class EvidenceAuthorityRejectionError(ClaimLoopServiceError):
    def __init__(self, message: str, *, rejection_receipt: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.rejection_receipt = deepcopy(dict(rejection_receipt))


_PUBLIC_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


def _artifact_scoped_semantic_value(value: Any, artifact: ToolArtifactReceipt) -> Any:
    """Normalize only receipt-local IDs for cross-loop correction reuse."""

    source = artifact.observation.source_refs[0]
    source_ref_id = f"source-ref.{digest_value(source.model_dump(mode='json'))}"
    if isinstance(value, str):
        if value == source.source_id:
            return "@matching-artifact"
        if value == source_ref_id:
            return "@matching-source-ref"
        return value
    if isinstance(value, list):
        return [_artifact_scoped_semantic_value(item, artifact) for item in value]
    if isinstance(value, dict):
        return {
            key: _artifact_scoped_semantic_value(item, artifact)
            for key, item in value.items()
        }
    return value


class ClaimCyclePipeline(Protocol):
    def analyze_cycle(
        self,
        *,
        source_run_id: str,
        orchestration_id: str,
        observable_package: dict[str, Any],
        facts: list[dict[str, Any]],
        process: dict[str, Any],
        checklist: dict[str, Any],
        verification: dict[str, Any],
        transport_mode: Literal["deterministic_test_double"],
        cycle_verification_builder: Callable[
            [list[dict[str, Any]], dict[str, Any], dict[str, Any]],
            dict[str, Any],
        ],
        progress_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _protocol_records_with(
    records: InsuranceProtocolRecordSetV1, **updates: Any
) -> InsuranceProtocolRecordSetV1:
    payload = records.model_dump(mode="json", exclude={"record_set_sha256"})
    payload.update(updates)
    return hash_record_set_v1(payload)


class ClaimLoopService:
    """Durable deterministic controller around accepted CasePath playbooks."""

    DISPATCH_LEASE_SECONDS = 300
    CLIENT_REQUEST_TTL_SECONDS = 900
    IDENTICAL_REQUEST_WAIT_SECONDS = 30.0

    @staticmethod
    def _internal_event_key(
        *,
        session_id: str,
        loop_id: str,
        client_idempotency_key: str,
        request_sha256: str,
        event_kind: str,
        request_type: str = "advance",
    ) -> str:
        return claim_loop_internal_event_key_v1(
            session_id=session_id,
            loop_id=loop_id,
            client_idempotency_key=client_idempotency_key,
            request_type=request_type,
            request_sha256=request_sha256,
            event_kind=event_kind,
        )

    def __init__(
        self,
        storage: Storage,
        *,
        adapters: Mapping[str, EvidenceToolAdapter] | None = None,
        artifact_interpreter: EvidenceArtifactInterpreter | None = None,
        correction_adapters: Mapping[str, CorrectionToolAdapter] | None = None,
        cycle_pipeline: ClaimCyclePipeline | None = None,
        source_pipeline: Any | None = None,
        protocol_adapter: LocalArtifactRegistryAdapterV1 | None = None,
        protocol_fault_hook: Callable[[str], None] | None = None,
        authorized_owned_sessions: Sequence[str] = (),
        reconciliation_scope: Literal["unowned", "authorized_only"] = "unowned",
        cycle_transport_mode: Literal[
            "openrouter", "deterministic_test_double"
        ] = "deterministic_test_double",
        clock: Callable[[], str] = _now,
    ) -> None:
        self.storage = storage
        unknown_authorizations = set(authorized_owned_sessions) - set(
            storage.protected_session_ids
        )
        if unknown_authorizations:
            raise ClaimLoopServiceError(
                "claim-loop authority names an unregistered protected session"
            )
        self._authorized_owned_sessions = frozenset(authorized_owned_sessions)
        if (reconciliation_scope == "authorized_only") != bool(
            self._authorized_owned_sessions
        ):
            raise ClaimLoopServiceError(
                "claim-loop reconciliation scope must match owned-session authority"
            )
        self._reconciliation_scope = reconciliation_scope
        self.adapters = dict(adapters or {})
        adapter_identities: dict[str, tuple[str, str, str]] = {}
        for adapter_id, adapter in self.adapters.items():
            implementation_id = getattr(adapter, "implementation_id", None)
            implementation_source_sha256 = getattr(
                adapter, "implementation_source_sha256", None
            )
            implementation_sha256 = getattr(adapter, "implementation_sha256", None)
            expected_sha256 = (
                adapter_implementation_sha256_v1(
                    adapter_id=adapter_id,
                    implementation_id=implementation_id,
                    implementation_source_sha256=(implementation_source_sha256),
                )
                if isinstance(implementation_id, str)
                and implementation_id
                and isinstance(implementation_source_sha256, str)
                else None
            )
            if (
                adapter.adapter_id != adapter_id
                or not isinstance(implementation_id, str)
                or not implementation_id
                or implementation_sha256 != expected_sha256
            ):
                raise ClaimLoopServiceError(
                    "configured evidence adapter implementation is not frozen"
                )
            adapter_identities[adapter_id] = (
                implementation_id,
                implementation_source_sha256,
                implementation_sha256,
            )
        self.protocol_adapter = protocol_adapter
        if protocol_adapter is not None:
            protocol_identity = (
                protocol_adapter.implementation_id,
                protocol_adapter.implementation_source_sha256,
                protocol_adapter.implementation_sha256,
            )
            if protocol_adapter.adapter_id in adapter_identities and (
                adapter_identities[protocol_adapter.adapter_id] != protocol_identity
            ):
                raise ClaimLoopServiceError(
                    "protocol adapter identity conflicts with evidence adapter"
                )
            adapter_identities[protocol_adapter.adapter_id] = protocol_identity
        self.correction_adapters = dict(correction_adapters or {})
        for correction_adapter_id, correction_adapter in (
            self.correction_adapters.items()
        ):
            if correction_adapter.adapter_id != correction_adapter_id:
                raise ClaimLoopServiceError(
                    "configured correction adapter object identity differs from its key"
                )
        self.store = ClaimLoopStore(
            storage.path,
            artifact_interpreter=artifact_interpreter,
            adapter_identities=adapter_identities,
            correction_adapters=self.correction_adapters,
            protocol_registry=protocol_adapter,
        )
        self.artifact_interpreter = artifact_interpreter
        self.cycle_pipeline = cycle_pipeline
        self.source_pipeline = source_pipeline
        self._protocol_fault_hook = protocol_fault_hook
        if cycle_transport_mode != "deterministic_test_double":
            raise ClaimLoopServiceError(
                "the zero-cost claim-loop candidate rejects provider-backed cycles"
            )
        self.cycle_transport_mode = cycle_transport_mode
        self._clock = clock

    def _assert_session_authority(self, session_id: str) -> None:
        if (
            session_id in SYSTEM_OWNED_SESSION_IDS
            or session_id in self.storage.protected_session_ids
        ) and session_id not in self._authorized_owned_sessions:
            raise ClaimLoopServiceError(
                "system-owned claim-loop session requires its dedicated authority"
            )

    @staticmethod
    def _graph_activity(
        audit: Mapping[str, Any],
    ) -> tuple[int, Literal["exact", "unknown"], float | None]:
        try:
            return derive_graph_activity_v1(audit)
        except ClaimLoopCycleError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    @classmethod
    def _upstream_source_run_activity(
        cls,
        run: Mapping[str, Any],
    ) -> tuple[BoundActivity, dict[str, Any] | None]:
        audit = run.get("agent_orchestration")
        if not isinstance(audit, Mapping):
            result = run.get("result")
            audit = (
                result.get("agent_orchestration")
                if isinstance(result, Mapping)
                else None
            )
        if not isinstance(audit, Mapping) or audit.get("executed") is False:
            return (
                BoundActivity(
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
                ),
                None,
            )
        calls, cost_status, cost_usd = cls._graph_activity(audit)
        audit_value = deepcopy(dict(audit))
        audit_sha256 = digest_value(audit_value)
        return (
            BoundActivity(
                scope="upstream_source_run",
                graph_traversal_count=1,
                model_calls=calls,
                provider_calls=calls,
                activity_receipt_sha256s=(audit_sha256,),
                execution_identity_sha256s=(audit_sha256,),
                credential_access_status=(
                    "not_measured" if calls > 0 else "none_due_to_zero_provider_calls"
                ),
                credential_access_receipt_sha256s=(),
                cost_status=cost_status,
                cost_usd=cost_usd,
            ),
            audit_value,
        )

    def _cycle_observable_package(
        self,
        *,
        accepted: Mapping[str, Any],
        projection_ledger: tuple[ProjectionLedgerEntry, ...],
        corrections: tuple[ScopedCorrection, ...] = (),
    ) -> dict[str, Any]:
        package_value = accepted.get("observable_package")
        if isinstance(package_value, Mapping):
            package = deepcopy(dict(package_value))
        else:
            claim = CLAIMS.get(str(accepted.get("claim_id")))
            if claim is None:
                raise ClaimLoopServiceError(
                    "claim is outside the bound playbook template"
                )
            package = observable_claim_package(claim)
        appended: dict[str, dict[str, Any]] = {}
        for entry in projection_ledger:
            artifact = self.store.tool_artifact(entry.artifact_receipt_sha256)
            if artifact is None:
                raise ClaimLoopServiceError(
                    "projection ledger artifact receipt was not found"
                )
            for source in artifact.observation.source_refs:
                existing_source_artifacts = [
                    value
                    for value in package.get("artifacts", [])
                    if isinstance(value, Mapping)
                    and value.get("artifact_id") == source.source_id
                ]
                if existing_source_artifacts:
                    if len(existing_source_artifacts) != 1:
                        raise ClaimLoopServiceError(
                            "cycle source artifact identity is ambiguous"
                        )
                    existing_source = existing_source_artifacts[0]
                    page = next(
                        (
                            value
                            for value in existing_source.get("extracted_pages", [])
                            if isinstance(value, Mapping)
                            and value.get("page") == source.page
                        ),
                        None,
                    )
                    text = page.get("text") if isinstance(page, Mapping) else None
                    if (
                        existing_source.get("sha256") != source.source_sha256
                        or not isinstance(text, str)
                        or source.text_start is None
                        or source.text_end is None
                        or source.text_end > len(text)
                        or text[source.text_start : source.text_end]
                        != source.sanitized_excerpt
                        or source.span_sha256
                        != digest_text(source.sanitized_excerpt or "")
                    ):
                        raise ClaimLoopServiceError(
                            "cycle source artifact differs from admitted observable bytes"
                        )
                    continue
                source_renderer = getattr(
                    self.artifact_interpreter,
                    "observable_artifact_for_source_ref",
                    None,
                )
                if source_renderer is not None:
                    try:
                        item = source_renderer(source=source, artifact=artifact)
                    except (ClaimLoopError, TypeError, ValueError) as exc:
                        raise ClaimLoopServiceError(
                            "cycle source artifact could not be reconstructed"
                        ) from exc
                else:
                    item = {
                        "artifact_id": source.source_id,
                        "filename": f"{artifact.observation.evidence_item_id}.pdf",
                        "media_type": "application/pdf",
                        "received_at": artifact.registered_at,
                        "page_count": 1,
                        "sha256": source.source_sha256,
                        "extracted_pages": [
                            {"page": 1, "text": artifact.sanitized_content}
                        ],
                    }
                if (
                    not isinstance(item, Mapping)
                    or item.get("artifact_id") != source.source_id
                    or item.get("sha256") != source.source_sha256
                ):
                    raise ClaimLoopServiceError(
                        "cycle source artifact reconstruction is invalid"
                    )
                item = deepcopy(dict(item))
                existing = appended.get(source.source_id)
                if existing is not None:
                    existing_semantic = {
                        key: value
                        for key, value in existing.items()
                        if key != "received_at"
                    }
                    item_semantic = {
                        key: value for key, value in item.items() if key != "received_at"
                    }
                    if existing_semantic != item_semantic:
                        raise ClaimLoopServiceError("cycle artifact identity changed")
                    continue
                appended[source.source_id] = item
        for correction in corrections:
            source = correction.source_ref
            if any(
                isinstance(value, Mapping)
                and value.get("artifact_id") == source.source_id
                for value in [*package.get("artifacts", []), *appended.values()]
            ):
                continue
            authority = self.store.correction_artifact(
                correction.correction_artifact_receipt_sha256
            )
            adapter = (
                self.correction_adapters.get(authority.authority_adapter_id)
                if authority is not None
                else None
            )
            renderer = getattr(
                adapter, "observable_artifact_for_correction_source", None
            )
            item = None
            stored_correction = self.store.correction(correction.correction_id)
            if stored_correction is not None:
                _, source_session_id, source_loop_id = stored_correction
                event_matches = [
                    event.command.get("correction_source_artifact")
                    for event in self.store.events(
                        session_id=source_session_id, loop_id=source_loop_id
                    )
                    if event.event_type in {"CORRECTION_APPLIED", "CORRECTION_REUSED"}
                    and event.command.get("correction", {}).get("correction_id")
                    == correction.correction_id
                    and isinstance(
                        event.command.get("correction_source_artifact"), Mapping
                    )
                ]
                if len(event_matches) > 1:
                    raise ClaimLoopServiceError(
                        "correction source artifact journal identity is ambiguous"
                    )
                if event_matches:
                    item = event_matches[0]
            if item is None:
                if not callable(renderer):
                    raise ClaimLoopServiceError(
                        "correction source artifact cannot be reconstructed"
                    )
                try:
                    item = renderer(source=source, correction=correction)
                except (ClaimLoopError, TypeError, ValueError) as exc:
                    raise ClaimLoopServiceError(
                        "correction source artifact could not be reconstructed"
                    ) from exc
            if (
                not isinstance(item, Mapping)
                or item.get("artifact_id") != source.source_id
                or item.get("sha256") != source.source_sha256
            ):
                raise ClaimLoopServiceError(
                    "correction source artifact reconstruction is invalid"
                )
            source_page = next(
                (
                    row
                    for row in item.get("extracted_pages", [])
                    if isinstance(row, Mapping) and row.get("page") == source.page
                ),
                None,
            )
            source_text = (
                source_page.get("text") if isinstance(source_page, Mapping) else None
            )
            if (
                not isinstance(source_text, str)
                or source.text_start is None
                or source.text_end is None
                or source.text_end > len(source_text)
                or source_text[source.text_start : source.text_end]
                != source.sanitized_excerpt
                or source.span_sha256
                != digest_text(source.sanitized_excerpt or "")
            ):
                raise ClaimLoopServiceError(
                    "correction source artifact span is invalid"
                )
            appended[source.source_id] = deepcopy(dict(item))
        package["artifacts"] = [
            *package["artifacts"],
            *(appended[key] for key in sorted(appended)),
        ]
        return package

    def _fresh_cycle_receipt(
        self,
        *,
        state: ClaimLoopState,
        cycle_kind: Literal["observation", "correction"],
        trigger_sha256: str,
        observations: tuple[ClaimObservation, ...],
        corrections: tuple[ScopedCorrection, ...],
        projection_ledger: tuple[ProjectionLedgerEntry, ...],
    ) -> tuple[
        SixAgentCycleReceipt,
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
    ]:
        if self.cycle_pipeline is None:
            raise ClaimLoopServiceError(
                "fresh six-agent cycle execution is not configured"
            )
        projected = project_claim_loop_artifacts_v1(
            accepted=state.accepted_artifacts,
            observations=observations,
            corrections=corrections,
            projection_ledger=projection_ledger,
        )
        template = playbook_template_from_accepted_v1(state.accepted_artifacts)
        cycle_pipeline = self._pipeline_for_template(template)
        configured_template = getattr(cycle_pipeline, "playbook_template", None)
        if (
            configured_template is None
            or configured_template.template_sha256 != template.template_sha256
        ):
            raise ClaimLoopServiceError(
                "cycle pipeline does not bind the loop playbook template"
            )
        package = self._cycle_observable_package(
            accepted=state.accepted_artifacts,
            projection_ledger=projection_ledger,
            corrections=corrections,
        )
        orchestration_id = "claim-loop-cycle." + digest_value(
            {
                "source_run_id": state.source_run_id,
                "loop_id": state.loop_id,
                "prior_state_sha256": state.state_sha256,
                "cycle_kind": cycle_kind,
                "trigger_sha256": trigger_sha256,
                "facts_sha256": digest_value(list(projected["facts"])),
                "observable_package_sha256": digest_value(package),
            }
        )
        cycle_result = cycle_pipeline.analyze_cycle(
            source_run_id=state.source_run_id,
            orchestration_id=orchestration_id,
            observable_package=package,
            facts=list(projected["facts"]),
            process=projected["process"],
            checklist=projected["checklist"],
            verification=projected["deterministic_gate_receipt"],
            transport_mode=self.cycle_transport_mode,
            cycle_verification_builder=lambda facts, process, checklist: (
                build_claim_loop_gate_receipt_v1(
                    claim_id=state.claim_id,
                    facts=facts,
                    process=process,
                    checklist=checklist,
                    legal=state.accepted_artifacts["legal_research"],
                    template=template,
                )
            ),
        )
        audit = cycle_result.get("orchestration_audit")
        fresh_verification = cycle_result.get("verification")
        accepted_cycle_artifacts = cycle_result.get("accepted_cycle_artifacts")
        if (
            not isinstance(audit, Mapping)
            or not isinstance(fresh_verification, Mapping)
            or not isinstance(accepted_cycle_artifacts, Mapping)
        ):
            raise ClaimLoopServiceError("fresh graph cycle result is incomplete")
        fresh_verification = deepcopy(dict(fresh_verification))
        accepted_cycle_artifacts = deepcopy(dict(accepted_cycle_artifacts))
        if (
            accepted_cycle_artifacts.get("facts") != list(projected["facts"])
            or accepted_cycle_artifacts.get("verification") != fresh_verification
            or not isinstance(accepted_cycle_artifacts.get("process"), Mapping)
            or not isinstance(accepted_cycle_artifacts.get("checklist"), Mapping)
            or not isinstance(
                accepted_cycle_artifacts.get("final_claim_brief"), Mapping
            )
        ):
            raise ClaimLoopServiceError(
                "fresh graph accepted artifacts are not bound to the cycle"
            )
        calls, cost_status, cost_usd = self._graph_activity(audit)
        if self.cycle_transport_mode == "deterministic_test_double" and (
            calls != 0 or cost_status != "exact" or cost_usd != 0.0
        ):
            raise ClaimLoopServiceError("provider-free cycle reported activity")
        try:
            receipt = build_six_agent_cycle_receipt_v1(
                source_run_id=state.source_run_id,
                loop_id=state.loop_id,
                cycle_kind=cycle_kind,
                prior_state_sha256=state.state_sha256,
                trigger_sha256=trigger_sha256,
                orchestration_id=orchestration_id,
                playbook_template_sha256=state.accepted_artifacts["playbook_template"][
                    "template_sha256"
                ],
                observable_package=package,
                facts=accepted_cycle_artifacts["facts"],
                process=accepted_cycle_artifacts["process"],
                checklist=accepted_cycle_artifacts["checklist"],
                verification=fresh_verification,
                graph_audit=audit,
                accepted_cycle_artifacts=accepted_cycle_artifacts,
                transport_mode=self.cycle_transport_mode,
                model_calls=calls,
                provider_calls=calls,
                credential_access_status=(
                    "not_measured" if calls > 0 else "none_due_to_zero_provider_calls"
                ),
                credential_access_receipt_sha256s=(),
                cost_status=cost_status,
                cost_usd=cost_usd,
            )
        except ClaimLoopCycleError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return (
            receipt,
            fresh_verification,
            deepcopy(dict(audit)),
            accepted_cycle_artifacts,
        )

    def _pipeline_for_template(self, template: Any) -> Any:
        """Resolve an exact deterministic pipeline without template fallback."""

        pipeline = self.cycle_pipeline
        if pipeline is None:
            raise ClaimLoopServiceError(
                "fresh six-agent cycle execution is not configured"
            )
        configured = getattr(pipeline, "playbook_template", None)
        if (
            configured is not None
            and configured.template_sha256 == template.template_sha256
        ):
            return pipeline
        resolver = getattr(pipeline, "for_template", None)
        if not callable(resolver):
            raise ClaimLoopServiceError(
                "cycle pipeline cannot resolve the accepted playbook template"
            )
        resolved = resolver(template)
        resolved_template = getattr(resolved, "playbook_template", None)
        if (
            resolved_template is None
            or resolved_template.template_sha256 != template.template_sha256
        ):
            raise ClaimLoopServiceError(
                "cycle pipeline resolver returned another playbook template"
            )
        return resolved

    def _source_cycle_material(
        self,
        *,
        run: Mapping[str, Any],
        loop_id: str,
        claim_id: str,
    ) -> tuple[
        dict[str, Any],
        SixAgentCycleReceipt,
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
    ]:
        result = run.get("result")
        template = run.get("playbook_template")
        if not isinstance(result, Mapping) or not isinstance(template, Mapping):
            raise ClaimLoopServiceError(
                "accepted run has no persisted playbook-template identity"
            )
        accepted_result = deepcopy(dict(result))
        accepted_result["playbook_template"] = deepcopy(dict(template))
        template_record = run.get("playbook_template_record")
        if (
            template_record is None
            and dict(template) == MOULD_PLAYBOOK_TEMPLATE.receipt
        ):
            template_record = MOULD_PLAYBOOK_TEMPLATE.persisted_record
        if not isinstance(template_record, Mapping):
            raise ClaimLoopServiceError(
                "accepted run has no persisted playbook-template catalog"
            )
        accepted_result["playbook_template_record"] = deepcopy(dict(template_record))
        package_value = run.get("observable_package")
        if package_value is None:
            package_value = result.get("observable_package")
        if isinstance(package_value, Mapping):
            package = deepcopy(dict(package_value))
        else:
            claim = CLAIMS.get(claim_id)
            if claim is None:
                raise ClaimLoopServiceError(
                    "accepted run has no persisted observable package"
                )
            package = observable_claim_package(claim)
        accepted_result["observable_package"] = deepcopy(package)
        try:
            accepted = accepted_artifacts_from_run(accepted_result)
        except (KeyError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "accepted source run failed the playbook boundary"
            ) from exc
        package = self._cycle_observable_package(
            accepted=accepted,
            projection_ledger=(),
        )
        result_audit = result.get("audit")
        if not isinstance(result_audit, Mapping) or result_audit.get(
            "observable_input_hash"
        ) != digest_value(package):
            raise ClaimLoopServiceError(
                "accepted source run does not bind its observable package"
            )
        audit = run.get("agent_orchestration")
        if not isinstance(audit, Mapping):
            audit = result.get("agent_orchestration")
        has_executed_source_graph = (
            isinstance(audit, Mapping)
            and audit.get("executed") is not False
            and isinstance(audit.get("orchestration_id"), str)
            and isinstance(audit.get("agents"), list)
            and isinstance(audit.get("deterministic_gates"), list)
        )
        if has_executed_source_graph and self.cycle_pipeline is None:
            verification = result.get("verification")
            orchestration_id = audit.get("orchestration_id")
            if not isinstance(verification, Mapping) or not isinstance(
                orchestration_id, str
            ):
                has_executed_source_graph = False
            else:
                verification = deepcopy(dict(verification))
                audit = deepcopy(dict(audit))
                calls, cost_status, cost_usd = self._graph_activity(audit)
                try:
                    final_claim_brief = audit.get("final_claim_brief")
                    if not isinstance(final_claim_brief, Mapping):
                        raise ClaimLoopCycleError(
                            "source graph audit has no accepted final brief"
                        )
                    accepted_cycle_artifacts = build_accepted_cycle_artifacts_v1(
                        facts=accepted_result["facts"],
                        process=accepted_result["process"],
                        checklist=accepted_result["checklist"],
                        final_claim_brief=final_claim_brief,
                        verification=verification,
                        graph_audit=audit,
                    )
                    receipt = build_six_agent_cycle_receipt_v1(
                        source_run_id=str(run["run_id"]),
                        loop_id=loop_id,
                        cycle_kind="source_acceptance",
                        prior_state_sha256=None,
                        trigger_sha256=digest_value(accepted_result),
                        orchestration_id=orchestration_id,
                        playbook_template_sha256=str(template["template_sha256"]),
                        observable_package=package,
                        facts=accepted_result["facts"],
                        process=accepted_result["process"],
                        checklist=accepted_result["checklist"],
                        verification=verification,
                        graph_audit=audit,
                        accepted_cycle_artifacts=accepted_cycle_artifacts,
                        transport_mode="accepted_source_run",
                        model_calls=calls,
                        provider_calls=calls,
                        credential_access_status=(
                            "not_measured"
                            if calls > 0
                            else "none_due_to_zero_provider_calls"
                        ),
                        credential_access_receipt_sha256s=(),
                        cost_status=cost_status,
                        cost_usd=cost_usd,
                    )
                except (ClaimLoopCycleError, KeyError, TypeError, ValueError):
                    # Governed memory may have changed the final accepted
                    # process/checklist after the original model graph.  Such a
                    # stale audit remains provenance but cannot authorize the
                    # loop; fall through to a fresh provider-free traversal.
                    has_executed_source_graph = False
                else:
                    return (
                        accepted_result,
                        receipt,
                        verification,
                        audit,
                        accepted_cycle_artifacts.model_dump(mode="json"),
                    )

        # Reference-mode v20 results intentionally do not invoke the model
        # graph, and case-specific memory may change accepted artifacts after
        # an earlier model graph.  Prospectively traverse the exact same
        # compiled six-role StateGraph over the final accepted artifacts with
        # the credential-free runner whenever the original audit cannot prove
        # exact final-artifact equality.
        if self.cycle_pipeline is None:
            raise ClaimLoopServiceError(
                "source acceptance requires an exact source graph or the "
                "provider-free StateGraph"
            )
        projected = project_claim_loop_artifacts_v1(
            accepted=accepted,
            observations=(),
            corrections=(),
            projection_ledger=(),
        )
        accepted_template = playbook_template_from_accepted_v1(accepted)
        source_cycle_pipeline = self._pipeline_for_template(accepted_template)
        configured_template = getattr(source_cycle_pipeline, "playbook_template", None)
        if (
            configured_template is None
            or configured_template.template_sha256 != accepted_template.template_sha256
        ):
            raise ClaimLoopServiceError(
                "source cycle pipeline does not bind the playbook template"
            )
        orchestration_id = "claim-loop-source." + digest_value(
            {
                "source_run_id": str(run["run_id"]),
                "loop_id": loop_id,
                "accepted_result_sha256": digest_value(accepted_result),
                "observable_package_sha256": digest_value(package),
            }
        )
        cycle_result = source_cycle_pipeline.analyze_cycle(
            source_run_id=str(run["run_id"]),
            orchestration_id=orchestration_id,
            observable_package=package,
            facts=list(projected["facts"]),
            process=projected["process"],
            checklist=projected["checklist"],
            verification=projected["deterministic_gate_receipt"],
            transport_mode="deterministic_test_double",
            cycle_verification_builder=lambda facts, process, checklist: (
                build_claim_loop_gate_receipt_v1(
                    claim_id=str(accepted["claim_id"]),
                    facts=facts,
                    process=process,
                    checklist=checklist,
                    legal=accepted["legal_research"],
                    template=accepted_template,
                )
            ),
        )
        audit_value = cycle_result.get("orchestration_audit")
        verification_value = cycle_result.get("verification")
        accepted_cycle_value = cycle_result.get("accepted_cycle_artifacts")
        if (
            not isinstance(audit_value, Mapping)
            or not isinstance(verification_value, Mapping)
            or not isinstance(accepted_cycle_value, Mapping)
        ):
            raise ClaimLoopServiceError(
                "provider-free source graph returned incomplete evidence"
            )
        audit = deepcopy(dict(audit_value))
        verification = deepcopy(dict(verification_value))
        accepted_cycle_artifacts = deepcopy(dict(accepted_cycle_value))
        calls, cost_status, cost_usd = self._graph_activity(audit)
        if calls != 0 or cost_status != "exact" or cost_usd != 0.0:
            raise ClaimLoopServiceError(
                "provider-free source acceptance reported external activity"
            )
        try:
            receipt = build_six_agent_cycle_receipt_v1(
                source_run_id=str(run["run_id"]),
                loop_id=loop_id,
                cycle_kind="source_acceptance",
                prior_state_sha256=None,
                trigger_sha256=digest_value(accepted_result),
                orchestration_id=orchestration_id,
                playbook_template_sha256=str(template["template_sha256"]),
                observable_package=package,
                facts=accepted_cycle_artifacts["facts"],
                process=accepted_cycle_artifacts["process"],
                checklist=accepted_cycle_artifacts["checklist"],
                verification=verification,
                graph_audit=audit,
                accepted_cycle_artifacts=accepted_cycle_artifacts,
                transport_mode="deterministic_test_double",
                model_calls=0,
                provider_calls=0,
                credential_access_status="none_due_to_zero_provider_calls",
                credential_access_receipt_sha256s=(),
                cost_status="exact",
                cost_usd=0.0,
            )
        except (ClaimLoopCycleError, KeyError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "accepted source six-agent receipt is invalid"
            ) from exc
        return (
            accepted_result,
            receipt,
            verification,
            deepcopy(dict(audit)),
            accepted_cycle_artifacts,
        )

    def _validate_tool_artifact(
        self,
        *,
        action: Any,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        adapter_id: str,
        observation: ClaimObservation,
        sanitized_content: str,
        artifact_source_version: str,
        artifact_page_count: int,
    ) -> None:
        if (
            observation.fact_id != action.fact_id
            or observation.evidence_item_id != action.evidence_item_id
            or observation.evidence_status == "unavailable"
        ):
            raise ClaimLoopServiceError(
                "tool artifact is not bound to the selected obligation"
            )
        if not observation.source_refs:
            raise ClaimLoopServiceError(
                "tool artifact requires server-verifiable source provenance"
            )
        if any(
            source.adapter_id != adapter_id or source.locator_kind != "text_quote"
            for source in observation.source_refs
        ):
            raise ClaimLoopServiceError("tool source capability is not authorized")
        custom_source_validator = getattr(
            self.artifact_interpreter,
            "validate_interpreted_source_binding",
            None,
        )
        if custom_source_validator is not None:
            try:
                custom_source_validator(
                    action=action,
                    state=state,
                    acquisition=acquisition,
                    observation=observation,
                )
            except (ClaimLoopError, TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "tool observation source binding is invalid"
                ) from exc
            return
        if len(observation.source_refs) != 1:
            raise ClaimLoopServiceError(
                "the default tool artifact path requires exactly one source span"
            )
        source = observation.source_refs[0]
        if (
            source.source_version != artifact_source_version
            or artifact_page_count != 1
            or source.page != 1
        ):
            raise ClaimLoopServiceError("tool source page or version is not canonical")
        if (
            source.source_sha256 != digest_text(sanitized_content)
            or source.text_start is None
            or source.text_end is None
            or source.text_end > len(sanitized_content)
        ):
            raise ClaimLoopServiceError("tool artifact content hash or span is invalid")
        span = sanitized_content[source.text_start : source.text_end]
        if (
            span != source.sanitized_excerpt
            or source.span_sha256 != digest_text(span)
            or observation.value != span
        ):
            raise ClaimLoopServiceError(
                "tool observation value is not supported by its exact source span"
            )

    def _register_acquisition_result(
        self,
        *,
        state: ClaimLoopState,
        adapter: EvidenceToolAdapter,
        result: Any,
        timestamp: str,
        source_registration: bool = False,
    ) -> AcquisitionReceiptV1:
        action = state.selected_action
        if action is None or state.active_dispatch_sha256 is None:
            raise ClaimLoopServiceError("tool result has no active dispatch")
        if adapter.adapter_id != action.bounded_tool_id:
            raise ClaimLoopServiceError(
                "tool acquisition adapter lacks the selected action capability"
            )
        implementation_id = getattr(adapter, "implementation_id", None)
        implementation_source_sha256 = getattr(
            adapter, "implementation_source_sha256", None
        )
        implementation_sha256 = getattr(adapter, "implementation_sha256", None)
        if (
            not isinstance(implementation_id, str)
            or not implementation_id
            or not isinstance(implementation_source_sha256, str)
            or implementation_sha256
            != adapter_implementation_sha256_v1(
                adapter_id=adapter.adapter_id,
                implementation_id=implementation_id,
                implementation_source_sha256=implementation_source_sha256,
            )
        ):
            raise ClaimLoopServiceError(
                "tool acquisition adapter implementation is not frozen"
            )
        events = self.store.events(session_id=state.session_id, loop_id=state.loop_id)
        dispatch_event = next(
            (
                event
                for event in events
                if event.event_sha256 == state.active_dispatch_sha256
                and event.event_type == "ACTION_DISPATCH_STARTED"
            ),
            None,
        )
        if dispatch_event is None:
            raise ClaimLoopServiceError(
                "tool acquisition lacks its durable dispatch start"
            )
        dispatch_generation = dispatch_event.command.get("dispatch_generation")
        if (
            not isinstance(dispatch_generation, int)
            or isinstance(dispatch_generation, bool)
            or dispatch_generation < 1
        ):
            raise ClaimLoopServiceError("tool acquisition generation is invalid")
        artifact_source_version = result.artifact_source_version
        if (
            result.status is ToolResultStatus.OBSERVED
            and artifact_source_version != state.record_version
        ):
            raise ClaimLoopServiceError(
                "tool acquisition source version is stale for the active record"
            )
        record_version = (
            artifact_source_version
            if result.status is ToolResultStatus.OBSERVED
            else state.record_version
        )
        request_identity = {
            "contract": (
                "casepath.source-registration-request/1.0.0"
                if source_registration
                else "casepath.acquisition-request/1.1.0"
            ),
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "record_version": record_version,
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "dispatch_sha256": state.active_dispatch_sha256,
            "dispatch_generation": dispatch_generation,
            "adapter_id": adapter.adapter_id,
            "adapter_implementation_id": implementation_id,
            "adapter_implementation_source_sha256": (implementation_source_sha256),
            "adapter_implementation_sha256": implementation_sha256,
            "source_locator": result.source_locator,
        }
        observed = result.status is ToolResultStatus.OBSERVED
        content = result.sanitized_content if observed else None
        raw = content.encode("utf-8") if content is not None else None
        payload = {
            "contract": (
                "casepath.source-registration-compatibility-receipt/1.0.0"
                if source_registration
                else "casepath.acquisition-receipt/1.1.0"
            ),
            "status": result.status.value,
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "record_version": record_version,
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "dispatch_sha256": state.active_dispatch_sha256,
            "dispatch_generation": dispatch_generation,
            "adapter_id": adapter.adapter_id,
            "adapter_implementation_id": implementation_id,
            "adapter_implementation_source_sha256": (implementation_source_sha256),
            "adapter_implementation_sha256": implementation_sha256,
            "source_locator": result.source_locator,
            "acquisition_request_sha256": digest_value(request_identity),
            "acquired_at": timestamp,
            "content_kind": "canonical_utf8_text_v1" if observed else None,
            "mime_type": "text/plain; charset=utf-8" if observed else None,
            "raw_byte_count": len(raw) if raw is not None else None,
            "raw_bytes_sha256": digest_text(content) if content is not None else None,
            "sanitizer_implementation": "identity_utf8_v1" if observed else None,
            "sanitized_content": content,
            "sanitized_content_sha256": (
                digest_text(content) if content is not None else None
            ),
            "artifact_page_count": result.artifact_page_count if observed else None,
            "reason_code": result.reason if not observed else None,
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
        }
        try:
            receipt = AcquisitionReceiptV1.model_validate(
                {**payload, "receipt_sha256": digest_value(payload)}
            )
            self.store.register_acquisition(receipt, raw_payload=raw)
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "raw acquisition registration failed closed"
            ) from exc
        return receipt

    def _register_tool_result(
        self,
        *,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
    ) -> ToolArtifactReceipt:
        action = state.selected_action
        if action is None or state.active_dispatch_sha256 is None:
            raise ClaimLoopServiceError("tool result has no active dispatch")
        if (
            acquisition.status is not ToolResultStatus.OBSERVED
            or acquisition.sanitized_content is None
            or acquisition.artifact_page_count is None
            or acquisition.action_id != action.action_id
            or acquisition.action_sha256 != action.action_sha256
            or acquisition.dispatch_sha256 != state.active_dispatch_sha256
            or acquisition.record_version != state.record_version
        ):
            raise ClaimLoopServiceError(
                "tool artifact is not bound to an observed acquisition"
            )
        if self.artifact_interpreter is None:
            raise ClaimLoopServiceError(
                "observed artifacts require a server-owned interpreter"
            )
        try:
            interpretation = self.artifact_interpreter.interpret(
                action=action,
                state=state,
                acquisition=acquisition,
            )
        except (ClaimLoopError, ValueError, TypeError) as exc:
            rejection_recorder = getattr(
                self.artifact_interpreter,
                "record_interpretation_rejection",
                None,
            )
            if rejection_recorder is not None:
                try:
                    rejection = rejection_recorder(
                        action=action,
                        state=state,
                        acquisition=acquisition,
                        reason=str(exc),
                    )
                except (ClaimLoopError, TypeError, ValueError) as rejection_exc:
                    raise ClaimLoopServiceError(
                        "raw artifact rejection audit failed closed"
                    ) from rejection_exc
                raise EvidenceAuthorityRejectionError(
                    "raw artifact interpretation was rejected",
                    rejection_receipt=rejection,
                ) from exc
            raise ClaimLoopServiceError(
                "raw artifact interpretation failed closed"
            ) from exc
        authority_validator = getattr(
            self.artifact_interpreter,
            "validate_interpretation_authority",
            None,
        )
        if authority_validator is not None:
            try:
                authority_validator(
                    action=action,
                    state=state,
                    acquisition=acquisition,
                    interpretation=interpretation,
                )
            except (ClaimLoopError, TypeError, ValueError) as exc:
                rejection_reader = getattr(
                    self.artifact_interpreter,
                    "authority_rejection_for_acquisition",
                    None,
                )
                if rejection_reader is not None:
                    try:
                        rejection = rejection_reader(acquisition.receipt_sha256)
                    except (ClaimLoopError, TypeError, ValueError) as rejection_exc:
                        raise ClaimLoopServiceError(
                            "authority rejection receipt failed closed"
                        ) from rejection_exc
                    raise EvidenceAuthorityRejectionError(
                        "raw artifact proposal was rejected by independent authority",
                        rejection_receipt=rejection,
                    ) from exc
                raise ClaimLoopServiceError(
                    "raw artifact proposal was rejected by independent authority"
                ) from exc
        observation = interpretation.observation
        self._validate_tool_artifact(
            action=action,
            state=state,
            acquisition=acquisition,
            adapter_id=acquisition.adapter_id,
            observation=observation,
            sanitized_content=acquisition.sanitized_content,
            artifact_source_version=acquisition.record_version,
            artifact_page_count=acquisition.artifact_page_count,
        )
        payload = {
            "contract": "casepath.tool-artifact-receipt/1.1.0",
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "dispatch_sha256": state.active_dispatch_sha256,
            "adapter_id": acquisition.adapter_id,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "acquisition_receipt": acquisition.model_dump(mode="json"),
            "artifact_source_version": acquisition.record_version,
            "artifact_page_count": acquisition.artifact_page_count,
            "sanitized_content": acquisition.sanitized_content,
            "raw_artifact_sha256": acquisition.receipt_sha256,
            "interpretation": interpretation.model_dump(mode="json"),
            "observation": observation.model_dump(mode="json"),
            "registered_at": acquisition.acquired_at,
            "model_calls": 0,
            "provider_calls": 0,
            "provider_credentials_read": False,
            "cost_usd": 0.0,
        }
        receipt = ToolArtifactReceipt.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )
        try:
            self.store.register_tool_artifact(receipt)
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return receipt

    def _observation_command(
        self,
        *,
        state: ClaimLoopState,
        artifact: ToolArtifactReceipt,
        advance_request_sha256: str | None = None,
    ) -> dict[str, Any]:
        observation = artifact.observation
        observations = (*state.observations, observation)
        projection_ledger = (
            *state.projection_ledger,
            ProjectionLedgerEntry(
                kind="observation",
                record_sha256=observation.observation_sha256,
                artifact_receipt_sha256=artifact.receipt_sha256,
                # The immutable artifact receipt, not a caller/recovery clock,
                # defines projection chronology.  Concurrent recovery therefore
                # constructs byte-identical commands.
                recorded_at=artifact.registered_at,
            ),
        )
        (
            cycle_receipt,
            cycle_verification,
            graph_audit,
            accepted_cycle_artifacts,
        ) = self._fresh_cycle_receipt(
            state=state,
            cycle_kind="observation",
            trigger_sha256=observation.observation_sha256,
            observations=observations,
            corrections=state.corrections,
            projection_ledger=projection_ledger,
        )
        command = {
            "action_id": artifact.action_id,
            "dispatch_sha256": artifact.dispatch_sha256,
            "artifact_receipt_sha256": artifact.receipt_sha256,
            "tool_artifact_receipt": artifact.model_dump(mode="json"),
            "observation": observation.model_dump(mode="json"),
            "six_agent_verification": cycle_verification,
            "six_agent_graph_audit": graph_audit,
            "six_agent_cycle_receipt": cycle_receipt.model_dump(mode="json"),
            "accepted_cycle_artifacts": accepted_cycle_artifacts,
        }
        authority_binding_reader = getattr(
            self.artifact_interpreter,
            "authority_binding_for_interpretation",
            None,
        )
        if authority_binding_reader is not None:
            try:
                command["evidence_authority_binding"] = authority_binding_reader(
                    artifact.interpretation
                )
            except (ClaimLoopError, TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "observation authority binding failed closed"
                ) from exc
        if advance_request_sha256 is not None:
            command["advance_request_sha256"] = advance_request_sha256
        return command

    def _evidence_rejection_command(
        self,
        *,
        state: ClaimLoopState,
        acquisition: AcquisitionReceiptV1,
        rejection_receipt: Mapping[str, Any],
        advance_request_sha256: str,
    ) -> dict[str, Any]:
        action = state.selected_action
        rejection_reader = getattr(
            self.artifact_interpreter,
            "authority_rejection_for_acquisition",
            None,
        )
        if action is None or state.active_dispatch_sha256 is None:
            raise ClaimLoopServiceError(
                "authority rejection has no active evidence dispatch"
            )
        if rejection_reader is None:
            raise ClaimLoopServiceError(
                "authority rejection has no durable receipt reader"
            )
        try:
            persisted = rejection_reader(acquisition.receipt_sha256)
        except (ClaimLoopError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "authority rejection receipt is unavailable"
            ) from exc
        if persisted != dict(rejection_receipt):
            raise ClaimLoopServiceError(
                "authority rejection differs from its durable receipt"
            )
        return {
            "action_id": action.action_id,
            "action_sha256": action.action_sha256,
            "dispatch_sha256": state.active_dispatch_sha256,
            "acquisition_receipt_sha256": acquisition.receipt_sha256,
            "acquisition_receipt": acquisition.model_dump(mode="json"),
            "authority_rejection_receipt_sha256": persisted.get("receipt_sha256"),
            "authority_rejection_receipt": persisted,
            "advance_request_sha256": advance_request_sha256,
        }

    def _correction_command(
        self,
        *,
        state: ClaimLoopState,
        correction: ScopedCorrection,
        admitted_at: str,
        source_session_id: str | None = None,
        reuse_receipt: CorrectionReuseReceipt | None = None,
    ) -> dict[str, Any]:
        correction_artifact = self.store.correction_artifact(
            correction.correction_artifact_receipt_sha256
        )
        source_artifact = self.store.tool_artifact(
            correction.source_artifact_receipt_sha256
        )
        if correction_artifact is None or source_artifact is None:
            raise ClaimLoopServiceError(
                "correction authority artifacts are unavailable"
            )
        authority_adapter = self.correction_adapters.get(
            correction_artifact.authority_adapter_id
        )
        if (
            authority_adapter is None
            or authority_adapter.adapter_id
            != correction_artifact.authority_adapter_id
            or correction_artifact.issuer_id
            != correction_artifact.authority_adapter_id
        ):
            raise ClaimLoopServiceError(
                "correction authority adapter is not configured exactly"
            )
        if reuse_receipt is None:
            try:
                authority_result = authority_adapter.execute(
                    source_artifact=source_artifact,
                    state=state,
                    timestamp=correction_artifact.issued_at,
                )
            except (ClaimLoopError, TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "correction authority cannot reproduce its proposal"
                ) from exc
            if (
                not isinstance(authority_result, CorrectionToolResult)
                or authority_result.effect != correction_artifact.proposed_effect
                or authority_result.issuer_id != correction_artifact.issuer_id
                or authority_result.issuer_kind != correction_artifact.issuer_kind
                or authority_result.provenance_note
                != correction_artifact.provenance_note
                or authority_result.model_calls != correction_artifact.model_calls
                or authority_result.provider_calls
                != correction_artifact.provider_calls
                or authority_result.provider_credentials_read
                != correction_artifact.provider_credentials_read
                or authority_result.cost_usd != correction_artifact.cost_usd
            ):
                raise ClaimLoopServiceError(
                    "correction authority proposal differs from its configured adapter"
                )
        try:
            admitted = datetime.fromisoformat(admitted_at.replace("Z", "+00:00"))
            effective = datetime.fromisoformat(
                correction.effective_at.replace("Z", "+00:00")
            )
            expires = (
                datetime.fromisoformat(correction.expires_at.replace("Z", "+00:00"))
                if correction.expires_at is not None
                else None
            )
        except (AttributeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "correction admission timestamps are invalid"
            ) from exc
        if (
            state.active_dispatch_sha256 is not None
            or correction.record_version != state.record_version
            or correction.scope.claim_ids != (state.claim_id,)
            or effective > admitted
            or (expires is not None and admitted >= expires)
        ):
            raise ClaimLoopServiceError(
                "correction is stale, expired, or outside the current scope"
            )
        if reuse_receipt is None:
            if (
                source_session_id is not None
                or correction_artifact.session_id != state.session_id
                or correction_artifact.loop_id != state.loop_id
                or correction_artifact.parent_state_sha256 != state.state_sha256
            ):
                raise ClaimLoopServiceError("local correction parent identity is stale")
        elif (
            source_session_id != state.session_id
            or reuse_receipt.target_session_id != state.session_id
            or reuse_receipt.target_loop_id != state.loop_id
            or reuse_receipt.target_parent_state_sha256 != state.state_sha256
            or reuse_receipt.correction_artifact_receipt_sha256
            != correction_artifact.receipt_sha256
        ):
            raise ClaimLoopServiceError("correction reuse parent identity is stale")
        corrections = (*state.corrections, correction)
        projection_ledger = (
            *state.projection_ledger,
            ProjectionLedgerEntry(
                kind="correction",
                record_sha256=correction.correction_sha256,
                artifact_receipt_sha256=(correction.source_artifact_receipt_sha256),
                recorded_at=correction.effective_at,
            ),
        )
        (
            cycle_receipt,
            cycle_verification,
            graph_audit,
            accepted_cycle_artifacts,
        ) = self._fresh_cycle_receipt(
            state=state,
            cycle_kind="correction",
            trigger_sha256=correction.correction_sha256,
            observations=state.observations,
            corrections=corrections,
            projection_ledger=projection_ledger,
        )
        target_fact = next(
            (
                value
                for value in state.facts
                if value.get("fact_id") == correction.effect.fact_id
            ),
            None,
        )
        target_evidence = next(
            (
                value
                for value in state.checklist.get("items", [])
                if value.get("item_id") == correction.effect.evidence_item_id
            ),
            None,
        )
        if not isinstance(target_fact, Mapping) or not isinstance(
            target_evidence, Mapping
        ):
            raise ClaimLoopServiceError(
                "correction semantic target is absent from the parent state"
            )
        before_semantics = {
            "fact_state": target_fact.get("state"),
            "normalized_value": target_fact.get("normalized_value"),
            "value": target_fact.get("value"),
            "explanation": target_fact.get("explanation"),
            "evidence_status": target_evidence.get("status"),
        }
        after_fact = next(
            (
                value
                for value in accepted_cycle_artifacts["facts"]
                if value.get("fact_id") == correction.effect.fact_id
            ),
            None,
        )
        after_evidence = next(
            (
                value
                for value in accepted_cycle_artifacts["checklist"].get("items", [])
                if value.get("item_id") == correction.effect.evidence_item_id
            ),
            None,
        )
        if not isinstance(after_fact, Mapping) or not isinstance(
            after_evidence, Mapping
        ):
            raise ClaimLoopServiceError(
                "correction semantic target is absent from the projected state"
            )
        after_semantics = {
            "fact_state": after_fact.get("state"),
            "normalized_value": after_fact.get("normalized_value"),
            "value": after_fact.get("value"),
            "explanation": after_fact.get("explanation"),
            "evidence_status": after_evidence.get("status"),
        }
        command: dict[str, Any] = {
            "correction": correction.model_dump(mode="json"),
            "correction_artifact_receipt": correction_artifact.model_dump(mode="json"),
            "source_tool_artifact_receipt": source_artifact.model_dump(mode="json"),
            "before_semantics": before_semantics,
            "after_semantics": after_semantics,
            "six_agent_verification": cycle_verification,
            "six_agent_graph_audit": graph_audit,
            "six_agent_cycle_receipt": cycle_receipt.model_dump(mode="json"),
            "accepted_cycle_artifacts": accepted_cycle_artifacts,
        }
        correction_source_binding = getattr(
            authority_adapter, "correction_source_binding", None
        )
        if callable(correction_source_binding):
            try:
                source_artifact_reader = getattr(
                    authority_adapter, "correction_source_artifact", None
                )
                if not callable(source_artifact_reader):
                    raise ClaimLoopError(
                        "correction source artifact reader is unavailable"
                    )
                command["correction_source_artifact"] = source_artifact_reader(
                    source_artifact=source_artifact,
                    state=state,
                    correction=correction,
                )
                source_refs_reader = getattr(
                    authority_adapter, "correction_source_refs", None
                )
                if not callable(source_refs_reader):
                    raise ClaimLoopError(
                        "correction source reference reader is unavailable"
                    )
                command["correction_source_refs"] = source_refs_reader(
                    source_artifact=source_artifact,
                    state=state,
                    correction=correction,
                )
                command["correction_source_binding"] = correction_source_binding(
                    source_artifact=source_artifact,
                    state=state,
                    correction=correction,
                )
            except (ClaimLoopError, TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "correction source binding receipt is invalid"
                ) from exc
        if source_session_id is not None:
            command["source_session_id"] = source_session_id
        if reuse_receipt is not None:
            target_matching_artifact = self.store.tool_artifact(
                reuse_receipt.target_matching_artifact_receipt_sha256
            )
            if target_matching_artifact is None:
                raise ClaimLoopServiceError(
                    "correction reuse matching artifact is unavailable"
                )
            source_application_event = next(
                (
                    event
                    for event in self.store.events(
                        session_id=reuse_receipt.source_session_id,
                        loop_id=reuse_receipt.source_loop_id,
                    )
                    if event.event_sha256
                    == reuse_receipt.source_application_event_sha256
                ),
                None,
            )
            if source_application_event is None:
                raise ClaimLoopServiceError(
                    "correction source application event is unavailable"
                )
            command["reuse_receipt"] = reuse_receipt.model_dump(mode="json")
            command["target_matching_tool_artifact_receipt"] = (
                target_matching_artifact.model_dump(mode="json")
            )
            command["source_application_event"] = source_application_event.model_dump(
                mode="json"
            )
        return command

    @staticmethod
    def _response(
        state: ClaimLoopState,
        receipt: ClaimLoopCommandReceipt | None,
    ) -> dict[str, Any]:
        if receipt is not None and (
            receipt.loop_id != state.loop_id
            or receipt.revision != state.revision
            or receipt.state_sha256 != state.state_sha256
            or receipt.event_sha256 != state.last_event_sha256
        ):
            raise ClaimLoopServiceError(
                "command receipt does not bind the returned canonical state"
            )
        upstream_activity = state.upstream_source_run_activity.model_dump(mode="json")
        source_activity = state.source_acceptance_activity.model_dump(mode="json")
        incremental_activity = state.incremental_loop_activity.model_dump(mode="json")
        total_activity = state.total_bound_activity.model_dump(mode="json")
        credential_status = total_activity["credential_access_status"]
        return {
            "contract": "casepath.claim-loop-response/1.0.0",
            "loop_id": state.loop_id,
            "revision": state.revision,
            "phase": state.phase.value,
            "state_sha256": state.state_sha256,
            "selected_action": (
                state.selected_action.model_dump(mode="json")
                if state.selected_action
                else None
            ),
            "terminal_mode": state.terminal_mode,
            "sufficiency": state.sufficiency.model_dump(mode="json"),
            "command_receipt": (
                receipt.model_dump(mode="json") if receipt is not None else None
            ),
            "upstream_source_run_activity": upstream_activity,
            "source_acceptance_activity": source_activity,
            "incremental_loop_activity": incremental_activity,
            "total_bound_activity": total_activity,
            "model_calls": total_activity["model_calls"],
            "provider_calls": total_activity["provider_calls"],
            "provider_credentials_read": (
                False
                if credential_status == "none_due_to_zero_provider_calls"
                else True
                if credential_status == "receipt_bound"
                else None
            ),
            "credential_access_status": credential_status,
            "cost_status": total_activity["cost_status"],
            "cost_usd": total_activity["cost_usd"],
        }

    def _response_with_protocol_prefix(
        self,
        *,
        state: ClaimLoopState,
        receipt: ClaimLoopCommandReceipt | None,
        additions: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build top-level and protocol projections from one immutable prefix.

        The journal may lawfully advance while a response is being serialized.
        Both public layers must nevertheless describe the same append-only
        prefix; projecting the current tail in a second read can splice a later
        correction into an older command receipt.
        """

        events = self.store.events(session_id=state.session_id, loop_id=state.loop_id)
        if state.revision < 1 or len(events) < state.revision:
            raise ClaimLoopServiceError("protocol response journal prefix is absent")
        prefix_events = events[: state.revision]
        prefix_state = self.store.state_at_revision(
            session_id=state.session_id,
            loop_id=state.loop_id,
            revision=state.revision,
        )
        if prefix_state.model_dump(mode="json") != state.model_dump(mode="json"):
            raise ClaimLoopServiceError(
                "protocol response state is not its journal prefix"
            )
        prefix_entries = self._protocol_entries(prefix_events)
        self._validate_protocol_registry_receipt(prefix_entries)
        protocol = self._protocol_projection(
            state=prefix_state,
            events=prefix_events,
        ).model_dump(mode="json")
        if (
            protocol["base_revision"] != prefix_state.revision
            or protocol["base_state_sha256"] != prefix_state.state_sha256
            or protocol["last_event_sha256"] != prefix_state.last_event_sha256
        ):
            raise ClaimLoopServiceError(
                "protocol projection does not bind the response journal prefix"
            )
        response = self._response(prefix_state, receipt)
        if additions is not None:
            response.update(dict(additions))
        response["protocol_state"] = protocol
        return response

    def _bind_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._assert_session_authority(session_id)
        if _PUBLIC_IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise ClaimLoopServiceError(
                "idempotency key must be a public opaque identifier"
            )
        try:
            request_sha256 = self.store.bind_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type=request_type,
                request=request,
                timestamp=self._clock(),
            )
            binding = self.store.client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type=request_type,
                request_sha256=request_sha256,
            )
            if binding.get("failure") is not None:
                raise ClaimLoopServiceError(
                    binding["failure"]["detail"],
                    conflict_envelope=binding["failure"],
                )
            return {**binding, "request_sha256": request_sha256}
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    def _supersede_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
        detail: str,
    ) -> None:
        try:
            failure = self.store.supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type=request_type,
                request_sha256=request_sha256,
                detail=detail,
                completed_at=self._clock(),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        raise ClaimLoopServiceError(failure["detail"], conflict_envelope=failure)

    def _complete_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
        response: Mapping[str, Any],
    ) -> dict[str, Any]:
        response_value = deepcopy(dict(response))
        if response_value.get("command_receipt") is None:
            try:
                binding = self.store.client_request(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type=request_type,
                    request_sha256=request_sha256,
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            reserved_state = binding.get("reserved_state")
            if not isinstance(reserved_state, ClaimLoopState):
                raise ClaimLoopServiceError(
                    "no-event response lacks its atomic reservation snapshot"
                )
            request_value = binding.get("request")
            if not isinstance(request_value, Mapping) or not (
                self._reserved_request_is_noop(
                    request_type=request_type,
                    request=request_value,
                    state=reserved_state,
                )
            ):
                raise ClaimLoopServiceError(
                    "reserved request required a domain transition"
                )
            response_value = self._response(reserved_state, None)
        try:
            return self.store.complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type=request_type,
                request_sha256=request_sha256,
                response=response_value,
                completed_at=self._clock(),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    def _reserved_request_is_noop(
        self,
        *,
        request_type: str,
        request: Mapping[str, Any],
        state: ClaimLoopState,
    ) -> bool:
        """Prove a response-only command against its reserved journal prefix."""

        terminal = state.phase in {
            ClaimLoopPhase.DECISION_READY,
            ClaimLoopPhase.ABSTAINED,
        }
        if request_type == "select_action":
            return terminal or state.selected_action is not None
        if request_type != "advance":
            return False
        if terminal or state.active_dispatch_sha256 is not None:
            return True
        if state.selected_action is None:
            return False
        requested_adapter = request.get("requested_adapter_id")
        if requested_adapter is not None:
            return False
        return state.selected_action.bounded_tool_id not in self.adapters

    def _await_completed_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
    ) -> dict[str, Any]:
        self._assert_session_authority(session_id)
        deadline = monotonic() + self.IDENTICAL_REQUEST_WAIT_SECONDS
        while monotonic() < deadline:
            try:
                binding = self.store.client_request(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type=request_type,
                    request_sha256=request_sha256,
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            if binding["response"] is not None:
                return deepcopy(binding["response"])
            sleep(0.01)
        failure = {
            "contract": "casepath.claim-loop-conflict/1.0.0",
            "code": "request_in_progress",
            "reason": (
                "identical client request remains in progress; retry the same key"
            ),
            "idempotency_key": idempotency_key,
            "request_type": request_type,
            "request_sha256": request_sha256,
        }
        raise ClaimLoopServiceError(
            failure["reason"], conflict_envelope=failure
        )

    def _reconciliation_lineage_response(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        self._assert_session_authority(session_id)
        event_key = idempotency_key
        if request_type == "advance":
            event_key = self._internal_event_key(
                session_id=session_id,
                loop_id=loop_id,
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                event_kind="result",
            )
        elif request_type == "insurance_register":
            for kind, expected_type in (
                ("replan-receipt", "PROTOCOL_REPLAN_RECEIPT_RECORDED"),
                ("intent-cancelled", "PROTOCOL_INTENT_CANCELLED"),
            ):
                terminal_key = self._internal_event_key(
                    session_id=session_id,
                    loop_id=loop_id,
                    client_idempotency_key=idempotency_key,
                    request_sha256=request_sha256,
                    request_type=request_type,
                    event_kind=kind,
                )
                terminal = self.store.event_prefix_result(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=terminal_key,
                )
                if terminal is None:
                    continue
                event, state, receipt = terminal
                if (
                    event.event_type != expected_type
                    or event.command.get("origin_client_idempotency_key")
                    != idempotency_key
                    or event.command.get("origin_client_request_sha256")
                    != request_sha256
                    or event.command.get("origin_client_request_type") != request_type
                ):
                    raise ClaimLoopServiceError(
                        "abandoned insurance lineage changed its origin"
                    )
                events = self.store.events(session_id=session_id, loop_id=loop_id)
                prefix = events[: state.revision]
                self._validate_protocol_registry_receipt(self._protocol_entries(prefix))
                return {
                    **self._response(state, receipt),
                    "protocol_state": self._protocol_projection(
                        state=state, events=prefix
                    ).model_dump(mode="json"),
                }
            return None
        result = self.store.event_prefix_result(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=event_key,
        )
        if result is None:
            if request_type != "advance":
                return None
            select_key = self._internal_event_key(
                session_id=session_id,
                loop_id=loop_id,
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                event_kind="select",
            )
            selected = self.store.event_prefix_result(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=select_key,
            )
            if selected is None:
                return None
            event, state, receipt = selected
            if (
                event.event_type != "ACTION_SELECTED"
                or event.command.get("advance_request_sha256") != request_sha256
                or state.phase
                not in {ClaimLoopPhase.DECISION_READY, ClaimLoopPhase.ABSTAINED}
            ):
                return None
            return self._response(state, receipt)
        event, state, receipt = result
        valid = False
        if request_type == "create":
            valid = (
                event.event_type == "LOOP_CREATED"
                and event.command.get("source_run_id") == request.get("source_run_id")
                and event.command.get("create_request_sha256") == request_sha256
            )
        elif request_type == "select_action":
            valid = event.event_type == "ACTION_SELECTED"
        elif request_type == "ingest_observation":
            valid = (
                event.event_type == "OBSERVATION_INGESTED"
                and event.command.get("action_id") == request.get("action_id")
                and event.command.get("artifact_receipt_sha256")
                == request.get("artifact_receipt_sha256")
                and event.command.get("advance_request_sha256") is None
            )
        elif request_type == "tool_unavailable":
            valid = (
                event.event_type == "TOOL_UNAVAILABLE"
                and event.command.get("action_id") == request.get("action_id")
                and event.command.get("outcome") == request.get("outcome")
                and event.command.get("dispatch_sha256")
                == request.get("dispatch_sha256")
                and event.command.get("advance_request_sha256") is None
            )
        elif request_type == "apply_correction":
            valid = event.event_type == "CORRECTION_APPLIED" and event.command.get(
                "correction", {}
            ).get("correction_id") == request.get("correction_id")
        elif request_type == "reuse_correction":
            valid = event.event_type == "CORRECTION_REUSED" and event.command.get(
                "correction", {}
            ).get("correction_id") == request.get("correction_id")
        elif request_type == "advance":
            valid = (
                event.event_type
                in {
                    "OBSERVATION_INGESTED",
                    "EVIDENCE_PROPOSAL_REJECTED",
                    "TOOL_UNAVAILABLE",
                    "DISPATCH_UNKNOWN",
                }
                and event.command.get("advance_request_sha256") == request_sha256
            )
        if not valid:
            raise ClaimLoopServiceError(
                "abandoned request lineage differs from its reserved route/body"
            )
        return self._response(state, receipt)

    def reconcile_abandoned_requests(
        self,
        *,
        now: str,
        limit: int = 128,
        recover_protocol_effects: bool = True,
    ) -> dict[str, Any]:
        """Resolve only durable results, provable no-ops, or expired reservations."""

        try:
            observed_at = datetime.fromisoformat(now.replace("Z", "+00:00"))
            rows = self.store.reserved_client_requests(limit=limit)
        except (ClaimLoopStoreError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if observed_at.tzinfo is None:
            raise ClaimLoopServiceError("reconciliation time must be timezone-aware")
        outcomes: list[dict[str, str]] = []
        counts = {
            "completed_lineage": 0,
            "completed_noop": 0,
            "superseded": 0,
            "abandoned": 0,
            "active_reserved": 0,
            "active_partial_lineage": 0,
        }
        domain_events_appended = 0
        tool_calls = 0
        for row in rows:
            owned_row = row["session_id"] in self.storage.protected_session_ids
            row_in_scope = (
                row["session_id"] in self._authorized_owned_sessions
                if self._reconciliation_scope == "authorized_only"
                else not owned_row
            )
            if not row_in_scope:
                # A generic startup reconciler cannot even inspect, expire, or
                # complete another controller's reserved command lineage; an
                # owned reconciler cannot interfere with generic tenants.
                continue
            try:
                binding = self.store.client_request(
                    session_id=row["session_id"],
                    loop_id=row["loop_id"],
                    idempotency_key=row["idempotency_key"],
                    request_type=row["request_type"],
                    request_sha256=row["request_sha256"],
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            if binding["status"] != "RESERVED":
                continue
            request = binding.get("request")
            if not isinstance(request, Mapping):
                raise ClaimLoopServiceError("reserved request body is invalid")
            response = self._reconciliation_lineage_response(
                session_id=row["session_id"],
                loop_id=row["loop_id"],
                idempotency_key=row["idempotency_key"],
                request_type=row["request_type"],
                request_sha256=row["request_sha256"],
                request=request,
            )
            if (
                response is None
                and row["request_type"] == "insurance_register"
                and recover_protocol_effects
            ):
                before_state, before_events = self.store.snapshot(
                    session_id=row["session_id"],
                    loop_id=row["loop_id"],
                )
                protocol_entries = self._protocol_entries(before_events)
                if protocol_entries:
                    origin_records = protocol_entries[0][1]
                    try:
                        registry_receipt = self._require_protocol_adapter().status(
                            intent=origin_records.intent
                        )
                    except (
                        LocalArtifactRegistryError,
                        TypeError,
                        ValueError,
                    ) as exc:
                        raise ClaimLoopServiceError(str(exc)) from exc
                    # Startup recovery may project a durable adapter outcome into
                    # the journal, but it never originates an unjournaled effect.
                    # A live None status remains owned by the existing executor.
                    if registry_receipt is not None:
                        response = self._resume_protocol_registration(
                            state=before_state,
                            records=origin_records,
                            client_idempotency_key=row["idempotency_key"],
                            request_sha256=row["request_sha256"],
                            allow_execute=False,
                            allow_reconcile=True,
                        )
                        after_state, _ = self.store.snapshot(
                            session_id=row["session_id"],
                            loop_id=row["loop_id"],
                        )
                        domain_events_appended += max(
                            0, after_state.revision - before_state.revision
                        )
                        binding_after_recovery = self.store.client_request(
                            session_id=row["session_id"],
                            loop_id=row["loop_id"],
                            idempotency_key=row["idempotency_key"],
                            request_type=row["request_type"],
                            request_sha256=row["request_sha256"],
                        )
                        terminal_response = binding_after_recovery.get("response")
                        if terminal_response is not None:
                            response = terminal_response
                        else:
                            protocol_status = response.get("protocol_state", {}).get(
                                "protocol_status"
                            )
                            if protocol_status not in {"cancelled", "replanned"}:
                                response = None
            if response is not None:
                try:
                    self.store.complete_client_request(
                        session_id=row["session_id"],
                        loop_id=row["loop_id"],
                        idempotency_key=row["idempotency_key"],
                        request_type=row["request_type"],
                        request_sha256=row["request_sha256"],
                        response=response,
                        completed_at=now,
                    )
                except ClaimLoopStoreError as exc:
                    raise ClaimLoopServiceError(str(exc)) from exc
                outcome = "completed_lineage"
            else:
                reserved_state = binding.get("reserved_state")
                if isinstance(reserved_state, ClaimLoopState) and (
                    self._reserved_request_is_noop(
                        request_type=row["request_type"],
                        request=request,
                        state=reserved_state,
                    )
                ):
                    try:
                        self.store.complete_client_request(
                            session_id=row["session_id"],
                            loop_id=row["loop_id"],
                            idempotency_key=row["idempotency_key"],
                            request_type=row["request_type"],
                            request_sha256=row["request_sha256"],
                            response=self._response(reserved_state, None),
                            completed_at=now,
                        )
                    except ClaimLoopStoreError as exc:
                        raise ClaimLoopServiceError(str(exc)) from exc
                    outcome = "completed_noop"
                else:
                    created_at = datetime.fromisoformat(
                        str(row["created_at"]).replace("Z", "+00:00")
                    )
                    if created_at.tzinfo is None:
                        raise ClaimLoopServiceError(
                            "reserved request creation time is invalid"
                        )
                    expired = observed_at >= created_at + timedelta(
                        seconds=self.CLIENT_REQUEST_TTL_SECONDS
                    )
                    if not expired:
                        outcome = "active_reserved"
                    else:
                        try:
                            if reserved_state is None:
                                self.store.abandon_client_request(
                                    session_id=row["session_id"],
                                    loop_id=row["loop_id"],
                                    idempotency_key=row["idempotency_key"],
                                    request_type=row["request_type"],
                                    request_sha256=row["request_sha256"],
                                    detail=("request expired before any domain event"),
                                    completed_at=now,
                                )
                                outcome = "abandoned"
                            else:
                                self.store.supersede_client_request(
                                    session_id=row["session_id"],
                                    loop_id=row["loop_id"],
                                    idempotency_key=row["idempotency_key"],
                                    request_type=row["request_type"],
                                    request_sha256=row["request_sha256"],
                                    detail=(
                                        "request expired without a durable result lineage"
                                    ),
                                    completed_at=now,
                                )
                                outcome = "superseded"
                        except ClaimLoopStoreError as exc:
                            if "recoverable event lineage" not in str(exc):
                                raise ClaimLoopServiceError(str(exc)) from exc
                            outcome = "active_partial_lineage"
            counts[outcome] += 1
            outcomes.append(
                {
                    "request_sha256": row["request_sha256"],
                    "outcome": outcome,
                }
            )
        payload = {
            "contract": "casepath.claim-loop-reconciliation/1.0.0",
            "observed_at": now,
            "ttl_seconds": self.CLIENT_REQUEST_TTL_SECONDS,
            "scanned_count": len(rows),
            **counts,
            "requests": outcomes,
            "domain_events_appended": domain_events_appended,
            "tool_calls": tool_calls,
            "model_calls": 0,
            "provider_calls": 0,
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    def create(
        self,
        *,
        session_id: str,
        source_run_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if _PUBLIC_IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise ClaimLoopServiceError(
                "idempotency key must be a public opaque identifier"
            )
        # The create resource identity belongs to the session/client key, not to
        # caller-supplied body fields.  Reusing the key with another source run
        # must conflict instead of minting a second loop.
        loop_id = f"loop.{digest_value({'contract': 'casepath.claim-loop-create-resource/1.0.0', 'session_id': session_id, 'idempotency_key': idempotency_key})}"
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="create",
            request={"source_run_id": source_run_id},
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        create_request_sha256 = binding["request_sha256"]

        def finish(response: Mapping[str, Any]) -> dict[str, Any]:
            return self._complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="create",
                request_sha256=create_request_sha256,
                response=response,
            )

        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if (
                existing.event_type != "LOOP_CREATED"
                or existing.command.get("create_request_sha256")
                != create_request_sha256
                or existing.command.get("source_run_id") != source_run_id
            ):
                raise ClaimLoopServiceError(
                    "create idempotency key was reused with different input"
                )
            try:
                state, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type="LOOP_CREATED",
                    idempotency_key=idempotency_key,
                    command=existing.command,
                    timestamp=existing.created_at,
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            return finish(self._response(state, receipt))

        run = self.storage.get_run(source_run_id, session_id=session_id)
        if run is None:
            raise ClaimLoopServiceError("accepted source run was not found")
        if run.get("status") != "complete" or not isinstance(run.get("result"), dict):
            raise ClaimLoopServiceError("source run has no accepted playbook")
        claim_id = run.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ClaimLoopServiceError("source run claim identity is invalid")
        result_sha256 = digest_value(run["result"])
        record_material = {
            "contract": "casepath.server-owned-record-version/1.0.0",
            "source_run_id": source_run_id,
            "claim_id": claim_id,
            "result_sha256": result_sha256,
            "pipeline_release": run.get("release"),
            "result_schema": run["result"].get("audit", {}).get("schema"),
        }
        record_version = f"record.{digest_value(record_material)}"
        (
            accepted_result,
            cycle_receipt,
            cycle_verification,
            graph_audit,
            accepted_cycle_artifacts,
        ) = self._source_cycle_material(
            run=run,
            loop_id=loop_id,
            claim_id=claim_id,
        )
        source_acceptance_activity = bound_activity_from_cycle_receipt_v1(
            scope="source_acceptance",
            receipt=cycle_receipt,
        )
        (
            upstream_source_run_activity,
            upstream_source_graph_audit,
        ) = self._upstream_source_run_activity(run)
        command = {
            "session_id": session_id,
            "loop_id": loop_id,
            "claim_id": claim_id,
            "source_run_id": source_run_id,
            "create_request_sha256": create_request_sha256,
            "record_version": record_version,
            "accepted_result": accepted_result,
            "six_agent_verification": cycle_verification,
            "six_agent_graph_audit": graph_audit,
            "six_agent_cycle_receipt": cycle_receipt.model_dump(mode="json"),
            "accepted_cycle_artifacts": accepted_cycle_artifacts,
            "upstream_source_run_activity": (
                upstream_source_run_activity.model_dump(mode="json")
            ),
            "upstream_source_graph_audit": upstream_source_graph_audit,
            "source_acceptance_activity": (
                source_acceptance_activity.model_dump(mode="json")
            ),
        }
        try:
            state, receipt, replayed = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type="LOOP_CREATED",
                idempotency_key=idempotency_key,
                command=command,
                timestamp=self._clock(),
                expected_revision=0,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return finish(self._response(state, receipt))

    def bootstrap_generated_mould(
        self,
        *,
        session_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Create the provider-free generated Mould source and its loop.

        This is the sole product bootstrap for the Iteration-31 slice.  It uses
        the explicit deterministic source pipeline and replays an existing
        loop/create response before creating any new source run.
        """

        self._assert_session_authority(session_id)
        if self.source_pipeline is None:
            raise ClaimLoopServiceError(
                "provider-free generated source pipeline is unavailable"
            )
        if _PUBLIC_IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise ClaimLoopServiceError(
                "idempotency key must be a public opaque identifier"
            )
        loop_id = f"loop.{digest_value({'contract': 'casepath.claim-loop-create-resource/1.0.0', 'session_id': session_id, 'idempotency_key': idempotency_key})}"
        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            source_run_id = existing.command.get("source_run_id")
            if not isinstance(source_run_id, str):
                raise ClaimLoopServiceError(
                    "generated bootstrap event lacks its source run"
                )
            return self.create(
                session_id=session_id,
                source_run_id=source_run_id,
                idempotency_key=idempotency_key,
            )
        try:
            source_run_id = self.source_pipeline.create(
                DEMO_CLAIM["claim_id"],
                session_id=session_id,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "provider-free generated source run could not start"
            ) from exc
        deadline = monotonic() + 30.0
        while monotonic() < deadline:
            run = self.storage.get_run(source_run_id, session_id=session_id)
            if run is not None and run.get("status") in {"complete", "failed"}:
                if run.get("status") != "complete":
                    raise ClaimLoopServiceError(
                        "provider-free generated source run failed"
                    )
                break
            sleep(0.01)
        else:
            raise ClaimLoopServiceError(
                "provider-free generated source run did not finish in time"
            )
        try:
            return self.create(
                session_id=session_id,
                source_run_id=source_run_id,
                idempotency_key=idempotency_key,
            )
        except ClaimLoopServiceError:
            # A concurrent identical bootstrap may have won after both source
            # runs began.  Replay only that exact journaled winner.
            winner = self.store.idempotent_event(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
            )
            winner_source = (
                winner.command.get("source_run_id") if winner is not None else None
            )
            if not isinstance(winner_source, str):
                raise
            return self.create(
                session_id=session_id,
                source_run_id=winner_source,
                idempotency_key=idempotency_key,
            )

    def _raw_state(self, *, session_id: str, loop_id: str) -> ClaimLoopState:
        self._assert_session_authority(session_id)
        try:
            return self.store.recover(
                session_id=session_id, loop_id=loop_id, timestamp=self._clock()
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    def _state_with_recovery_receipt(
        self, *, session_id: str, loop_id: str
    ) -> tuple[ClaimLoopState, ClaimLoopCommandReceipt | None]:
        self._assert_session_authority(session_id)
        try:
            current, events = self.store.snapshot(
                session_id=session_id, loop_id=loop_id
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if current.active_dispatch_sha256 is None:
            event = events[-1]
            request_sha256 = event.command.get("advance_request_sha256")
            if isinstance(request_sha256, str):
                dispatch_event = next(
                    (
                        candidate
                        for candidate in events
                        if candidate.event_type == "ACTION_DISPATCH_STARTED"
                        and candidate.command.get("advance_request_sha256")
                        == request_sha256
                        and candidate.command.get("client_result_idempotency_key")
                        == event.idempotency_key
                    ),
                    None,
                )
                if dispatch_event is None:
                    return current, None
                client_key = dispatch_event.command.get("client_idempotency_key")
                if not isinstance(client_key, str) or not client_key:
                    raise ClaimLoopServiceError(
                        "advance result lacks its originating client key"
                    )
                dispatch_key = self._internal_event_key(
                    session_id=session_id,
                    loop_id=loop_id,
                    client_idempotency_key=client_key,
                    request_sha256=request_sha256,
                    event_kind="dispatch",
                )
                result_key = self._internal_event_key(
                    session_id=session_id,
                    loop_id=loop_id,
                    client_idempotency_key=client_key,
                    request_sha256=request_sha256,
                    event_kind="result",
                )
                if (
                    event.idempotency_key != result_key
                    or dispatch_event.idempotency_key != dispatch_key
                    or dispatch_event.command.get("client_result_idempotency_key")
                    != result_key
                    or dispatch_event.command.get("client_dispatch_idempotency_key")
                    != dispatch_key
                    or dispatch_event.command.get("advance_request_sha256")
                    != request_sha256
                ):
                    raise ClaimLoopServiceError(
                        "advance result is not bound to its dispatch request"
                    )
                try:
                    result_state, result_receipt, _ = self.store.append(
                        session_id=session_id,
                        loop_id=loop_id,
                        event_type=event.event_type,
                        idempotency_key=event.idempotency_key,
                        command=event.command,
                        timestamp=event.created_at,
                    )
                except ClaimLoopStoreError as exc:
                    raise ClaimLoopServiceError(str(exc)) from exc
                response = self._response(result_state, result_receipt)
                self._complete_client_request(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=client_key,
                    request_type="advance",
                    request_sha256=request_sha256,
                    response=response,
                )
                return result_state, result_receipt
            return current, None
        acquisition = self.store.acquisition_for_dispatch(
            session_id=session_id,
            loop_id=loop_id,
            dispatch_sha256=current.active_dispatch_sha256,
        )
        artifact = self.store.tool_artifact_for_dispatch(
            session_id=session_id,
            loop_id=loop_id,
            dispatch_sha256=current.active_dispatch_sha256,
        )
        dispatch_event = next(
            (
                event
                for event in events
                if event.event_sha256 == current.active_dispatch_sha256
                and event.event_type == "ACTION_DISPATCH_STARTED"
            ),
            None,
        )
        if dispatch_event is None:
            raise ClaimLoopServiceError(
                "active dispatch is not bound to its durable start event"
            )
        if dispatch_event.command.get("insurance_protocol_v1") is not None:
            # Insurance effects have their own intent/receipt state machine.
            # A read may expose that replay-derived state, but must never apply
            # the legacy expiry path or synthesize a generic outcome.
            return current, None
        advance_request_sha256 = dispatch_event.command.get("advance_request_sha256")
        client_idempotency_key = dispatch_event.command.get("client_idempotency_key")
        client_result_idempotency_key = dispatch_event.command.get(
            "client_result_idempotency_key"
        )
        if (
            not isinstance(advance_request_sha256, str)
            or not isinstance(client_idempotency_key, str)
            or not client_idempotency_key
            or client_result_idempotency_key
            != self._internal_event_key(
                session_id=session_id,
                loop_id=loop_id,
                client_idempotency_key=client_idempotency_key,
                request_sha256=advance_request_sha256,
                event_kind="result",
            )
            or dispatch_event.command.get("client_dispatch_idempotency_key")
            != self._internal_event_key(
                session_id=session_id,
                loop_id=loop_id,
                client_idempotency_key=client_idempotency_key,
                request_sha256=advance_request_sha256,
                event_kind="dispatch",
            )
        ):
            raise ClaimLoopServiceError(
                "active dispatch lacks its originating client-result binding"
            )
        event_type: str | None = None
        command: dict[str, Any] | None = None
        observed_now = self._clock()
        event_timestamp: str | None = None
        if (
            artifact is None
            and acquisition is not None
            and acquisition.status is ToolResultStatus.OBSERVED
        ):
            try:
                artifact = self._register_tool_result(
                    state=current, acquisition=acquisition
                )
            except EvidenceAuthorityRejectionError as exc:
                event_type = "EVIDENCE_PROPOSAL_REJECTED"
                event_timestamp = str(exc.rejection_receipt.get("rejected_at"))
                command = self._evidence_rejection_command(
                    state=current,
                    acquisition=acquisition,
                    rejection_receipt=exc.rejection_receipt,
                    advance_request_sha256=advance_request_sha256,
                )
        if event_type is None and artifact is not None:
            event_type = "OBSERVATION_INGESTED"
            event_timestamp = artifact.registered_at
            command = self._observation_command(
                state=current,
                artifact=artifact,
                advance_request_sha256=advance_request_sha256,
            )
        elif event_type is None and acquisition is not None:
            event_type = "TOOL_UNAVAILABLE"
            event_timestamp = acquisition.acquired_at
            command = {
                "action_id": acquisition.action_id,
                "outcome": acquisition.status.value,
                "dispatch_sha256": acquisition.dispatch_sha256,
                "acquisition_receipt_sha256": acquisition.receipt_sha256,
                "acquisition_receipt": acquisition.model_dump(mode="json"),
                "advance_request_sha256": advance_request_sha256,
            }
        elif event_type is None:
            expiry = datetime.fromisoformat(
                current.active_dispatch_expires_at.replace("Z", "+00:00")
            )
            now = datetime.fromisoformat(observed_now.replace("Z", "+00:00"))
            if now >= expiry:
                event_type = "DISPATCH_UNKNOWN"
                event_timestamp = current.active_dispatch_expires_at
                command = {
                    "action_id": current.selected_action.action_id,
                    "dispatch_sha256": current.active_dispatch_sha256,
                    "advance_request_sha256": advance_request_sha256,
                }
        if event_type is None or command is None or event_timestamp is None:
            return current, None
        recovery_key = client_result_idempotency_key
        try:
            recovered, receipt, _ = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type=event_type,
                idempotency_key=recovery_key,
                command=command,
                timestamp=event_timestamp,
                expected_revision=current.revision,
            )
        except ClaimLoopStoreError as exc:
            if str(exc) in {
                "durable tool artifact supersedes dispatch expiry",
                "durable acquisition supersedes dispatch expiry",
            }:
                return self._state_with_recovery_receipt(
                    session_id=session_id, loop_id=loop_id
                )
            # A concurrent reader may have won the identical recovery CAS.
            # Replaying our canonical command proves equivalence; a different
            # event type/body remains a hard idempotency conflict.
            if (
                self.store.idempotent_event(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=recovery_key,
                )
                is None
            ):
                raise ClaimLoopServiceError(str(exc)) from exc
            try:
                recovered, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type=event_type,
                    idempotency_key=recovery_key,
                    command=command,
                    timestamp=event_timestamp,
                )
            except ClaimLoopStoreError as replay_exc:
                raise ClaimLoopServiceError(str(replay_exc)) from replay_exc
        response = self._response(recovered, receipt)
        self._complete_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=client_idempotency_key,
            request_type="advance",
            request_sha256=advance_request_sha256,
            response=response,
        )
        return recovered, receipt

    def state(self, *, session_id: str, loop_id: str) -> ClaimLoopState:
        return self._state_with_recovery_receipt(
            session_id=session_id, loop_id=loop_id
        )[0]

    def state_response(self, *, session_id: str, loop_id: str) -> dict[str, Any]:
        state, receipt = self._state_with_recovery_receipt(
            session_id=session_id, loop_id=loop_id
        )
        return {
            **state.model_dump(mode="json"),
            "command_receipt": (
                receipt.model_dump(mode="json") if receipt is not None else None
            ),
        }

    def record_native_proposal_revision(
        self,
        *,
        session_id: str,
        loop_id: str,
        proposal_revision: Mapping[str, Any],
        request_identity: Mapping[str, Any],
        idempotency_key: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        """Append one source-bound proposal snapshot without admitting facts."""

        try:
            revision = NativeProposalRevisionV1.model_validate(proposal_revision)
        except (TypeError, ValueError) as exc:
            raise ClaimLoopServiceError("native proposal revision is invalid") from exc
        request = dict(request_identity)
        if (
            set(request) != {
                "contract",
                "claim_id",
                "loop_id",
                "prior_cycle_id",
                "cycle_id",
                "source_prefix_sha256",
                "proposal_sha256",
                "revision_packet_sha256",
            }
            or request.get("contract")
            != "casepath.native-proposal-revision-request/1.0.0"
            or request.get("claim_id") != revision.claim_id
            or request.get("loop_id") != revision.loop_id
            or request.get("prior_cycle_id") != revision.prior_cycle_id
            or request.get("cycle_id") != revision.cycle_id
            or request.get("source_prefix_sha256")
            != revision.source_prefix_sha256
            or request.get("proposal_sha256") != revision.proposal_sha256
            or not is_sha256(request.get("revision_packet_sha256"))
        ):
            raise ClaimLoopServiceError("native proposal revision request identity is invalid")
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="record_native_proposal_revision",
            request=request,
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        request_sha256 = binding["request_sha256"]
        event_key = self._internal_event_key(
            session_id=session_id,
            loop_id=loop_id,
            client_idempotency_key=idempotency_key,
            request_type="record_native_proposal_revision",
            request_sha256=request_sha256,
            event_kind="result",
        )

        def finish(response: Mapping[str, Any]) -> dict[str, Any]:
            return self._complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="record_native_proposal_revision",
                request_sha256=request_sha256,
                response=response,
            )

        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=event_key,
        )
        if existing is not None:
            if (
                existing.event_type != "NATIVE_PROPOSAL_REVISION_RECORDED"
                or existing.command.get("request_identity") != request
                or existing.command.get("client_idempotency_key")
                != idempotency_key
                or existing.command.get("client_request_sha256")
                != request_sha256
            ):
                raise ClaimLoopServiceError(
                    "native revision idempotency key was reused with different input"
                )
            try:
                state, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type=existing.event_type,
                    idempotency_key=event_key,
                    command=existing.command,
                    timestamp=existing.created_at,
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            return finish(self._response(state, receipt))

        current = self.state(session_id=session_id, loop_id=loop_id)
        if (
            current.revision != expected_revision
            or revision.parent_revision != expected_revision
            or revision.parent_state_sha256 != current.state_sha256
            or revision.claim_id != current.claim_id
            or revision.loop_id != current.loop_id
        ):
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="record_native_proposal_revision",
                request_sha256=request_sha256,
                detail="native proposal revision prefix changed before append",
            )
        try:
            state, receipt, _ = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type="NATIVE_PROPOSAL_REVISION_RECORDED",
                idempotency_key=event_key,
                command={
                    "proposal_revision": revision.model_dump(mode="json"),
                    "request_identity": request,
                    "client_idempotency_key": idempotency_key,
                    "client_request_sha256": request_sha256,
                },
                # recorded_at is the source/replay disclosure clock.  The
                # journal admission clock must follow the live client-request
                # reservation so historical saved outputs remain admissible.
                timestamp=self._clock(),
                expected_revision=expected_revision,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return finish(self._response(state, receipt))

    def replay_completed_native_proposal_revision_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_identity: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Replay a completed revision before mutable parent state is rebuilt."""

        try:
            existing = self.store.lookup_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="record_native_proposal_revision",
                request=dict(request_identity),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if existing is None:
            return None
        if existing.get("failure") is not None:
            raise ClaimLoopServiceError(str(existing["failure"]["detail"]))
        response = existing.get("response")
        return deepcopy(response) if isinstance(response, Mapping) else None

    def select_action(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        self._raw_state(session_id=session_id, loop_id=loop_id)
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="select_action",
            request={"expected_revision": expected_revision},
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        request_sha256 = binding["request_sha256"]
        reserved_state = binding.get("reserved_state")
        if not isinstance(reserved_state, ClaimLoopState):
            raise ClaimLoopServiceError(
                "select request lacks its reserved journal prefix"
            )

        def finish(response: Mapping[str, Any]) -> dict[str, Any]:
            return self._complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="select_action",
                request_sha256=request_sha256,
                response=response,
            )

        current = self.state(session_id=session_id, loop_id=loop_id)
        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            try:
                state, receipt, replayed = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type="ACTION_SELECTED",
                    idempotency_key=idempotency_key,
                    command={},
                    timestamp=self._clock(),
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            return finish(self._response(state, receipt))
        if current.revision != reserved_state.revision:
            if self._reserved_request_is_noop(
                request_type="select_action",
                request=binding["request"],
                state=reserved_state,
            ):
                return finish(self._response(reserved_state, None))
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="select_action",
                request_sha256=request_sha256,
                detail="select reservation prefix changed before its transition",
            )
        if (
            expected_revision is not None
            and expected_revision != reserved_state.revision
        ):
            raise ClaimLoopServiceError("claim loop revision changed")
        if current.selected_action is not None or current.phase in {
            ClaimLoopPhase.DECISION_READY,
            ClaimLoopPhase.ABSTAINED,
        }:
            return finish(self._response(current, None))
        try:
            state, receipt, replayed = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type="ACTION_SELECTED",
                idempotency_key=idempotency_key,
                command={},
                timestamp=self._clock(),
                expected_revision=(
                    current.revision if expected_revision is None else expected_revision
                ),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return finish(self._response(state, receipt))

    def ingest_registered_observation(
        self,
        *,
        session_id: str,
        loop_id: str,
        action_id: str,
        artifact_receipt_sha256: str,
        idempotency_key: str,
        expected_revision: int | None = None,
        _advance_request_sha256: str | None = None,
    ) -> dict[str, Any]:
        current = self._raw_state(session_id=session_id, loop_id=loop_id)
        if _advance_request_sha256 is None:
            binding = self._bind_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="ingest_observation",
                request={
                    "action_id": action_id,
                    "artifact_receipt_sha256": artifact_receipt_sha256,
                    "expected_revision": expected_revision,
                },
            )
            if binding["response"] is not None:
                return deepcopy(binding["response"])
            request_sha256 = binding["request_sha256"]

            def finish(response: Mapping[str, Any]) -> dict[str, Any]:
                return self._complete_client_request(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type="ingest_observation",
                    request_sha256=request_sha256,
                    response=response,
                )
        else:

            def finish(response: Mapping[str, Any]) -> dict[str, Any]:
                return deepcopy(dict(response))

        # This command, rather than a read-side recovery, owns the ingestion.
        # If a concurrent GET already reconciled it, return that exact state
        # below instead of attempting a second observation event.
        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if (
                existing.event_type != "OBSERVATION_INGESTED"
                or existing.command.get("action_id") != action_id
                or existing.command.get("artifact_receipt_sha256")
                != artifact_receipt_sha256
                or existing.command.get("advance_request_sha256")
                != _advance_request_sha256
            ):
                raise ClaimLoopServiceError(
                    "idempotency key was reused with different observation input"
                )
            try:
                state, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type=existing.event_type,
                    idempotency_key=idempotency_key,
                    command=existing.command,
                    timestamp=self._clock(),
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            return finish(self._response(state, receipt))
        artifact = self.store.tool_artifact(artifact_receipt_sha256)
        if artifact is None:
            raise ClaimLoopServiceError("server-owned tool artifact was not found")
        if current.active_dispatch_sha256 is None:
            already_ingested = any(
                event.event_type == "OBSERVATION_INGESTED"
                and event.command.get("artifact_receipt_sha256")
                == artifact_receipt_sha256
                for event in self.store.events(session_id=session_id, loop_id=loop_id)
            )
            if already_ingested:
                recovery_event = next(
                    event
                    for event in self.store.events(
                        session_id=session_id, loop_id=loop_id
                    )
                    if event.event_type == "OBSERVATION_INGESTED"
                    and event.command.get("artifact_receipt_sha256")
                    == artifact_receipt_sha256
                )
                state, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type=recovery_event.event_type,
                    idempotency_key=recovery_event.idempotency_key,
                    command=recovery_event.command,
                    timestamp=self._clock(),
                )
                return finish(self._response(state, receipt))
        if (
            artifact.session_id != session_id
            or artifact.loop_id != loop_id
            or artifact.action_id != action_id
            or current.selected_action is None
            or artifact.action_sha256 != current.selected_action.action_sha256
            or artifact.dispatch_sha256 != current.active_dispatch_sha256
        ):
            raise ClaimLoopServiceError("tool artifact does not bind active dispatch")
        event_timestamp = artifact.registered_at
        command = self._observation_command(
            state=current,
            artifact=artifact,
            advance_request_sha256=_advance_request_sha256,
        )
        try:
            state, receipt, replayed = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type="OBSERVATION_INGESTED",
                idempotency_key=idempotency_key,
                command=command,
                timestamp=event_timestamp,
                expected_revision=(
                    current.revision if expected_revision is None else expected_revision
                ),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return finish(self._response(state, receipt))

    def tool_unavailable(
        self,
        *,
        session_id: str,
        loop_id: str,
        action_id: str,
        outcome: str,
        idempotency_key: str,
        dispatch_sha256: str | None = None,
        acquisition_receipt_sha256: str,
        _advance_request_sha256: str | None = None,
        _event_timestamp: str | None = None,
    ) -> dict[str, Any]:
        self._raw_state(session_id=session_id, loop_id=loop_id)
        binding: dict[str, Any] | None = None
        if _advance_request_sha256 is None:
            binding = self._bind_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="tool_unavailable",
                request={
                    "action_id": action_id,
                    "outcome": outcome,
                    "dispatch_sha256": dispatch_sha256,
                    "acquisition_receipt_sha256": acquisition_receipt_sha256,
                    "advance_request_sha256": None,
                },
            )
            if binding["response"] is not None:
                return deepcopy(binding["response"])
            request_sha256 = binding["request_sha256"]
        else:
            request_sha256 = _advance_request_sha256
        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if (
                existing.event_type != "TOOL_UNAVAILABLE"
                or existing.command.get("action_id") != action_id
                or existing.command.get("outcome") != outcome
                or existing.command.get("dispatch_sha256") != dispatch_sha256
                or existing.command.get("acquisition_receipt_sha256")
                != acquisition_receipt_sha256
                or existing.command.get("advance_request_sha256")
                != _advance_request_sha256
            ):
                raise ClaimLoopServiceError(
                    "idempotency key was reused with different unavailable input"
                )
            try:
                state, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type=existing.event_type,
                    idempotency_key=idempotency_key,
                    command=existing.command,
                    timestamp=existing.created_at,
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            response = self._response(state, receipt)
            if _advance_request_sha256 is not None:
                return response
            return self._complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="tool_unavailable",
                request_sha256=request_sha256,
                response=response,
            )
        current = self.state(session_id=session_id, loop_id=loop_id)
        acquisition = self.store.acquisition(acquisition_receipt_sha256)
        if acquisition is None:
            raise ClaimLoopServiceError(
                "server-owned acquisition receipt was not found"
            )
        if binding is not None:
            reserved_state = binding.get("reserved_state")
            if not isinstance(reserved_state, ClaimLoopState):
                raise ClaimLoopServiceError(
                    "tool-unavailable request lacks its reserved journal prefix"
                )
            if current.revision != reserved_state.revision:
                self._supersede_client_request(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type="tool_unavailable",
                    request_sha256=request_sha256,
                    detail=(
                        "tool-unavailable reservation prefix changed before "
                        "its transition"
                    ),
                )
            current = reserved_state
        try:
            state, receipt, replayed = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type="TOOL_UNAVAILABLE",
                idempotency_key=idempotency_key,
                command={
                    "action_id": action_id,
                    "outcome": outcome,
                    "dispatch_sha256": dispatch_sha256,
                    "acquisition_receipt_sha256": acquisition.receipt_sha256,
                    "acquisition_receipt": acquisition.model_dump(mode="json"),
                    "advance_request_sha256": _advance_request_sha256,
                },
                timestamp=_event_timestamp or self._clock(),
                expected_revision=current.revision,
            )
        except ClaimLoopStoreError as exc:
            if binding is not None:
                raced = self.store.idempotent_event(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                )
                if raced is not None:
                    return self.tool_unavailable(
                        session_id=session_id,
                        loop_id=loop_id,
                        action_id=action_id,
                        outcome=outcome,
                        idempotency_key=idempotency_key,
                        dispatch_sha256=dispatch_sha256,
                        acquisition_receipt_sha256=acquisition_receipt_sha256,
                    )
                latest = self.state(session_id=session_id, loop_id=loop_id)
                if latest.revision != current.revision:
                    self._supersede_client_request(
                        session_id=session_id,
                        loop_id=loop_id,
                        idempotency_key=idempotency_key,
                        request_type="tool_unavailable",
                        request_sha256=request_sha256,
                        detail=(
                            "tool-unavailable reservation prefix changed "
                            "during its transition"
                        ),
                    )
            raise ClaimLoopServiceError(str(exc)) from exc
        response = self._response(state, receipt)
        if _advance_request_sha256 is not None:
            return response
        return self._complete_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="tool_unavailable",
            request_sha256=request_sha256,
            response=response,
        )

    def advance(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        adapter_id: str | None = None,
        expected_revision: int | None = None,
        request_context_sha256: str | None = None,
    ) -> dict[str, Any]:
        # This is the bounded worker/maintenance boundary.  It never invokes a
        # tool, model, or reducer transition; it only binds already durable
        # outcomes or terminalizes expired pre-event reservations.
        self.reconcile_abandoned_requests(
            now=self._clock(),
            recover_protocol_effects=False,
        )
        # Validate existence before reserving a caller key, then bind that key
        # globally across all loop command routes before read-side recovery can
        # advance the journal.
        self._raw_state(session_id=session_id, loop_id=loop_id)
        request: dict[str, Any] = {
            "expected_revision": expected_revision,
            "requested_adapter_id": adapter_id,
        }
        if request_context_sha256 is not None:
            if not is_sha256(request_context_sha256):
                raise ClaimLoopServiceError("advance request context is invalid")
            request["request_context_sha256"] = request_context_sha256
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="advance",
            request=request,
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        advance_request_sha256 = binding["request_sha256"]
        reserved_state = binding.get("reserved_state")
        if not isinstance(reserved_state, ClaimLoopState):
            raise ClaimLoopServiceError(
                "advance request lacks its reserved journal prefix"
            )

        def finish(response: Mapping[str, Any]) -> dict[str, Any]:
            return self._complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
                response=response,
            )

        current, recovery_receipt = self._state_with_recovery_receipt(
            session_id=session_id, loop_id=loop_id
        )
        try:
            recovered_binding = self.store.client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if recovered_binding["response"] is not None:
            return deepcopy(recovered_binding["response"])
        result_key = self._internal_event_key(
            session_id=session_id,
            loop_id=loop_id,
            client_idempotency_key=idempotency_key,
            request_sha256=advance_request_sha256,
            event_kind="result",
        )
        existing_result = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=result_key,
        )
        if existing_result is not None:
            if (
                existing_result.command.get("advance_request_sha256")
                != advance_request_sha256
            ):
                raise ClaimLoopServiceError(
                    "idempotency key was reused with different advance input"
                )
            try:
                state, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type=existing_result.event_type,
                    idempotency_key=result_key,
                    command=existing_result.command,
                    timestamp=self._clock(),
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            return finish(self._response(state, receipt))
        dispatch_key = self._internal_event_key(
            session_id=session_id,
            loop_id=loop_id,
            client_idempotency_key=idempotency_key,
            request_sha256=advance_request_sha256,
            event_kind="dispatch",
        )
        existing_dispatch = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=dispatch_key,
        )
        if existing_dispatch is not None:
            if (
                existing_dispatch.event_type != "ACTION_DISPATCH_STARTED"
                or existing_dispatch.command.get("advance_request_sha256")
                != advance_request_sha256
            ):
                raise ClaimLoopServiceError(
                    "idempotency key was reused with different advance input"
                )
            # The persisted start proves this request crossed the external
            # boundary.  Recovery may have consumed its result/expiry; never
            # gate this exact replay on the now-advanced revision or redispatch.
            return self._await_completed_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
            )
        select_key = self._internal_event_key(
            session_id=session_id,
            loop_id=loop_id,
            client_idempotency_key=idempotency_key,
            request_sha256=advance_request_sha256,
            event_kind="select",
        )
        existing_select = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=select_key,
        )
        if existing_select is not None and (
            existing_select.event_type != "ACTION_SELECTED"
            or existing_select.command.get("advance_request_sha256")
            != advance_request_sha256
        ):
            raise ClaimLoopServiceError("advance selection identity changed")
        select_receipt: ClaimLoopCommandReceipt | None = None
        selected_prefix: ClaimLoopState | None = None
        if existing_select is not None:
            try:
                selected_prefix, select_receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type="ACTION_SELECTED",
                    idempotency_key=select_key,
                    command=existing_select.command,
                    timestamp=existing_select.created_at,
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            bound_action = selected_prefix.selected_action
            current_action = current.selected_action
            if (
                bound_action is None
                or current_action is None
                or bound_action.action_id != current_action.action_id
                or bound_action.action_sha256 != current_action.action_sha256
                or current.active_dispatch_sha256 is not None
            ):
                # The request's selected action was consumed or claimed by a
                # different lineage.  Complete this request at its exact
                # selection prefix; never apply it to a newer action.
                return finish(self._response(selected_prefix, select_receipt))
        elif current.revision != reserved_state.revision:
            if self._reserved_request_is_noop(
                request_type="advance",
                request=binding["request"],
                state=reserved_state,
            ):
                return finish(self._response(reserved_state, None))
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
                detail="advance reservation prefix changed before its transition",
            )
        if (
            existing_select is None
            and expected_revision is not None
            and expected_revision != reserved_state.revision
        ):
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
                detail="claim loop revision changed before advance admission",
            )
        if current.selected_action is None and current.phase not in {
            ClaimLoopPhase.DECISION_READY,
            ClaimLoopPhase.ABSTAINED,
        }:
            try:
                predicted_action = derive_evidence_action_v1(current)
                current, select_receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type="ACTION_SELECTED",
                    idempotency_key=select_key,
                    command={
                        "advance_request_sha256": advance_request_sha256,
                        "client_idempotency_key": idempotency_key,
                        "client_select_idempotency_key": select_key,
                        "selected_from_revision": current.revision,
                        "selected_result_revision": current.revision + 1,
                        "selected_action_id": (
                            predicted_action.action_id
                            if predicted_action is not None
                            else None
                        ),
                        "selected_action_sha256": (
                            predicted_action.action_sha256
                            if predicted_action is not None
                            else None
                        ),
                    },
                    timestamp=self._clock(),
                    expected_revision=(
                        current.revision
                        if expected_revision is None
                        else expected_revision
                    ),
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            selected = self._response(current, select_receipt)
            if selected["terminal_mode"] is not None:
                return finish(selected)
        if adapter_id is None or current.selected_action is None:
            if current.selected_action is None:
                return finish(self._response(current, select_receipt))
            candidate_id = current.selected_action.bounded_tool_id
            if candidate_id not in self.adapters:
                return finish(self._response(current, select_receipt))
            adapter_id = candidate_id
        adapter = self.adapters.get(adapter_id)
        if adapter is None:
            raise ClaimLoopServiceError("requested evidence adapter is unavailable")
        if adapter.adapter_id != adapter_id:
            raise ClaimLoopServiceError(
                "configured adapter object identity differs from its capability key"
            )
        if current.selected_action.bounded_tool_id != adapter_id:
            raise ClaimLoopServiceError(
                "requested adapter lacks the selected action capability"
            )
        if current.active_dispatch_sha256 is not None:
            # A different command key cannot bypass the persisted job lease.
            return finish(self._response(current, recovery_receipt))

        proposed_dispatch_started_at = self._clock()
        proposed_dispatch_expiry = (
            datetime.fromisoformat(proposed_dispatch_started_at.replace("Z", "+00:00"))
            + timedelta(seconds=self.DISPATCH_LEASE_SECONDS)
        ).isoformat()
        try:
            (
                dispatch_started_at,
                dispatch_expiry,
                dispatch_generation,
            ) = self.store.bind_client_dispatch(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
                dispatch_idempotency_key=dispatch_key,
                started_at=proposed_dispatch_started_at,
                expires_at=proposed_dispatch_expiry,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        lease_owner = "claim-loop-worker." + digest_value(
            {
                "session_id": session_id,
                "loop_id": loop_id,
                "idempotency_key": idempotency_key,
                "action_sha256": current.selected_action.action_sha256,
                "adapter_id": adapter_id,
            }
        )
        dispatch_command = {
            "action_id": current.selected_action.action_id,
            "action_sha256": current.selected_action.action_sha256,
            "adapter_id": adapter_id,
            "lease_owner": lease_owner,
            "lease_expires_at": dispatch_expiry,
            "advance_request_sha256": advance_request_sha256,
            "client_idempotency_key": idempotency_key,
            "client_result_idempotency_key": result_key,
            "client_dispatch_idempotency_key": dispatch_key,
            "dispatch_generation": dispatch_generation,
        }
        try:
            dispatch_state, _, dispatch_replayed = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type="ACTION_DISPATCH_STARTED",
                idempotency_key=dispatch_key,
                command=dispatch_command,
                timestamp=dispatch_started_at,
                expected_revision=current.revision,
                client_dispatch_guard={
                    "client_idempotency_key": idempotency_key,
                    "request_sha256": advance_request_sha256,
                    "dispatch_started_at": dispatch_started_at,
                    "dispatch_expires_at": dispatch_expiry,
                    "dispatch_generation": dispatch_generation,
                },
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if dispatch_replayed:
            # Another worker won the admission CAS.  It may still be outside the
            # journal at the tool boundary, so this worker must not execute.
            self._state_with_recovery_receipt(session_id=session_id, loop_id=loop_id)
            return self._await_completed_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
            )
        execute_started_at = self._clock()
        if datetime.fromisoformat(execute_started_at.replace("Z", "+00:00")) >= (
            datetime.fromisoformat(dispatch_expiry.replace("Z", "+00:00"))
        ):
            self._state_with_recovery_receipt(session_id=session_id, loop_id=loop_id)
            return self._await_completed_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
            )
        result = adapter.execute(
            action=dispatch_state.selected_action,
            state=dispatch_state,
            idempotency_key=dispatch_state.active_dispatch_sha256,
            timestamp=execute_started_at,
        )
        completed_at = self._clock()
        if datetime.fromisoformat(completed_at.replace("Z", "+00:00")) >= (
            datetime.fromisoformat(dispatch_expiry.replace("Z", "+00:00"))
        ):
            self._state_with_recovery_receipt(session_id=session_id, loop_id=loop_id)
            return self._await_completed_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="advance",
                request_sha256=advance_request_sha256,
            )
        acquisition = self._register_acquisition_result(
            state=dispatch_state,
            adapter=adapter,
            result=result,
            timestamp=completed_at,
        )
        if result.status is ToolResultStatus.OBSERVED:
            if (
                result.sanitized_content is None
                or result.artifact_source_version is None
                or result.artifact_page_count is None
            ):  # pragma: no cover - ToolResult invariant
                raise ClaimLoopServiceError("adapter returned no raw artifact")
            try:
                artifact = self._register_tool_result(
                    state=dispatch_state,
                    acquisition=acquisition,
                )
            except EvidenceAuthorityRejectionError as exc:
                command = self._evidence_rejection_command(
                    state=dispatch_state,
                    acquisition=acquisition,
                    rejection_receipt=exc.rejection_receipt,
                    advance_request_sha256=advance_request_sha256,
                )
                try:
                    rejected_state, rejected_receipt, _ = self.store.append(
                        session_id=session_id,
                        loop_id=loop_id,
                        event_type="EVIDENCE_PROPOSAL_REJECTED",
                        idempotency_key=result_key,
                        command=command,
                        timestamp=str(exc.rejection_receipt.get("rejected_at")),
                        expected_revision=dispatch_state.revision,
                    )
                except ClaimLoopStoreError as store_exc:
                    raise ClaimLoopServiceError(str(store_exc)) from store_exc
                return finish(self._response(rejected_state, rejected_receipt))
            response = self.ingest_registered_observation(
                session_id=session_id,
                loop_id=loop_id,
                action_id=dispatch_state.selected_action.action_id,
                artifact_receipt_sha256=artifact.receipt_sha256,
                idempotency_key=result_key,
                expected_revision=dispatch_state.revision,
                _advance_request_sha256=advance_request_sha256,
            )
            return finish(response)
        response = self.tool_unavailable(
            session_id=session_id,
            loop_id=loop_id,
            action_id=dispatch_state.selected_action.action_id,
            outcome=result.status.value,
            idempotency_key=result_key,
            dispatch_sha256=dispatch_state.active_dispatch_sha256,
            acquisition_receipt_sha256=acquisition.receipt_sha256,
            _advance_request_sha256=advance_request_sha256,
            _event_timestamp=completed_at,
        )
        return finish(response)

    def apply_correction(
        self,
        *,
        session_id: str,
        loop_id: str,
        correction_id: str,
        idempotency_key: str,
        client_request_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._raw_state(session_id=session_id, loop_id=loop_id)
        request_context = (
            deepcopy(dict(client_request_context))
            if isinstance(client_request_context, Mapping)
            else None
        )
        if client_request_context is not None and (
            request_context is None or not request_context
        ):
            raise ClaimLoopServiceError(
                "correction client request context is invalid"
            )
        request: dict[str, Any] = {"correction_id": correction_id}
        if request_context is not None:
            request["client_request_context"] = request_context
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="apply_correction",
            request=request,
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        request_sha256 = binding["request_sha256"]
        reserved_state = binding.get("reserved_state")
        if not isinstance(reserved_state, ClaimLoopState):
            raise ClaimLoopServiceError(
                "correction request lacks its reserved journal prefix"
            )
        if reserved_state.active_dispatch_sha256 is not None:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="apply_correction",
                request_sha256=request_sha256,
                detail="correction is forbidden while a dispatch lease is active",
            )

        def finish(response: Mapping[str, Any]) -> dict[str, Any]:
            return self._complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="apply_correction",
                request_sha256=request_sha256,
                response=response,
            )

        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if (
                existing.event_type != "CORRECTION_APPLIED"
                or existing.command.get("correction", {}).get("correction_id")
                != correction_id
                or existing.command.get("client_request_context")
                != request_context
            ):
                raise ClaimLoopServiceError(
                    "idempotency key was reused with different correction input"
                )
            try:
                state, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type=existing.event_type,
                    idempotency_key=idempotency_key,
                    command=existing.command,
                    timestamp=self._clock(),
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            return finish(self._response(state, receipt))
        stored = self.store.correction(correction_id)
        if stored is None:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="apply_correction",
                request_sha256=request_sha256,
                detail="server-owned correction receipt was not found",
            )
        correction, source_session_id, source_loop_id = stored
        if source_session_id != session_id or source_loop_id != loop_id:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="apply_correction",
                request_sha256=request_sha256,
                detail="correction belongs to another loop; use the reuse boundary",
            )
        current = self.state(session_id=session_id, loop_id=loop_id)
        if current.revision != reserved_state.revision:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="apply_correction",
                request_sha256=request_sha256,
                detail="correction reservation prefix changed before its transition",
            )
        current = reserved_state
        timestamp = self._clock()
        try:
            command = self._correction_command(
                state=current,
                correction=correction,
                admitted_at=timestamp,
            )
            if request_context is not None:
                command["client_request_context"] = request_context
        except ClaimLoopServiceError as exc:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="apply_correction",
                request_sha256=request_sha256,
                detail=str(exc),
            )
        try:
            state, receipt, replayed = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type="CORRECTION_APPLIED",
                idempotency_key=idempotency_key,
                command=command,
                timestamp=timestamp,
                expected_revision=current.revision,
            )
        except ClaimLoopStoreError as exc:
            raced = self.store.idempotent_event(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
            )
            if raced is not None:
                return self.apply_correction(
                    session_id=session_id,
                    loop_id=loop_id,
                    correction_id=correction_id,
                    idempotency_key=idempotency_key,
                )
            latest = self.state(session_id=session_id, loop_id=loop_id)
            if latest.revision != current.revision:
                self._supersede_client_request(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type="apply_correction",
                    request_sha256=request_sha256,
                    detail=(
                        "correction reservation prefix changed during its transition"
                    ),
                )
            raise ClaimLoopServiceError(str(exc)) from exc
        return finish(self._response(state, receipt))

    def replay_completed_correction_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_identity: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Replay one completed correction before consulting the current state.

        Native callers can derive ``request_identity`` from immutable source-cycle
        input.  The first application stores that identity inside both the durable
        client request and its correction event.  A retry therefore returns the
        original journal-prefix response even after the correction changed the
        loop's current parent, while a changed need or source packet conflicts.
        """

        self._assert_session_authority(session_id)
        if _PUBLIC_IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise ClaimLoopServiceError(
                "idempotency key must be a public opaque identifier"
            )
        if not isinstance(request_identity, Mapping) or not request_identity:
            raise ClaimLoopServiceError(
                "correction replay request identity is invalid"
            )
        identity = deepcopy(dict(request_identity))
        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is None:
            return None
        context = existing.command.get("client_request_context")
        if (
            existing.event_type != "CORRECTION_APPLIED"
            or not isinstance(context, Mapping)
            or context.get("request_identity") != identity
        ):
            raise ClaimLoopServiceError(
                "idempotency key was reused with different correction input"
            )
        correction_id = existing.command.get("correction", {}).get("correction_id")
        if not isinstance(correction_id, str) or not correction_id:
            raise ClaimLoopServiceError(
                "completed correction request lacks its durable correction"
            )
        response = self.apply_correction(
            session_id=session_id,
            loop_id=loop_id,
            correction_id=correction_id,
            idempotency_key=idempotency_key,
            client_request_context=context,
        )
        return {
            "correction_id": correction_id,
            "client_request_context": deepcopy(dict(context)),
            "response": response,
        }

    def register_correction(
        self,
        *,
        session_id: str,
        loop_id: str,
        source_artifact_receipt_sha256: str,
        correction_adapter_id: str,
        expires_at: str | None = None,
        issued_at: str | None = None,
        expected_parent_state_sha256: str | None = None,
        expected_effect: Mapping[str, Any] | None = None,
    ) -> ScopedCorrection:
        """Admit a material correction from exact server-owned evidence.

        This authority boundary is intentionally absent from the public router.
        It invokes a server-configured authority adapter; callers cannot supply
        fact state, evidence status, normalized value, or correction prose.
        """

        state = self.state(session_id=session_id, loop_id=loop_id)
        if (
            expected_parent_state_sha256 is not None
            and state.state_sha256 != expected_parent_state_sha256
        ):
            raise ClaimLoopServiceError(
                "correction parent state changed before authority admission"
            )
        artifact = self.store.tool_artifact(source_artifact_receipt_sha256)
        if (
            artifact is None
            or artifact.session_id != session_id
            or artifact.loop_id != loop_id
            or not any(
                entry.artifact_receipt_sha256 == source_artifact_receipt_sha256
                for entry in state.projection_ledger
            )
        ):
            raise ClaimLoopServiceError(
                "correction is not bound to a server-owned source artifact"
            )
        observation = artifact.observation
        adapter = self.correction_adapters.get(correction_adapter_id)
        if adapter is None:
            raise ClaimLoopServiceError(
                "requested correction authority adapter is unavailable"
            )
        if adapter.adapter_id != correction_adapter_id:
            raise ClaimLoopServiceError(
                "configured correction adapter object identity differs from its key"
            )
        timestamp = issued_at or self._clock()
        correction_source_reader = getattr(adapter, "source_ref_for_correction", None)
        if callable(correction_source_reader):
            try:
                source_ref = correction_source_reader(
                    source_artifact=artifact,
                    state=state,
                    timestamp=timestamp,
                )
            except (ClaimLoopError, TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "correction source reference is invalid"
                ) from exc
            if not isinstance(source_ref, ClaimSourceRef):
                raise ClaimLoopServiceError(
                    "correction authority returned no exact source reference"
                )
        else:
            if len(observation.source_refs) != 1:
                raise ClaimLoopServiceError(
                    "the default correction path requires one exact admitted locator"
                )
            source_ref = observation.source_refs[0]
        try:
            result = adapter.execute(
                source_artifact=artifact,
                state=state,
                timestamp=timestamp,
            )
        except (ClaimLoopError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if not isinstance(result, CorrectionToolResult):
            raise ClaimLoopServiceError(
                "correction authority returned an invalid result"
            )
        if result.issuer_id != correction_adapter_id:
            raise ClaimLoopServiceError(
                "correction result issuer differs from configured authority"
            )
        effect = result.effect
        if expected_effect is not None and effect.model_dump(mode="json") != dict(
            expected_effect
        ):
            raise ClaimLoopServiceError(
                "correction authority effect differs from selected semantic preview"
            )
        if (
            effect.fact_id != observation.fact_id
            or effect.evidence_item_id != observation.evidence_item_id
            or source_ref.locator_kind != "text_quote"
            or (effect.fact_state != "known" and effect.normalized_value is not None)
        ):
            raise ClaimLoopServiceError(
                "correction proposal is not supported by the exact source span"
            )
        fact = next(
            (value for value in state.facts if value.get("fact_id") == effect.fact_id),
            None,
        )
        evidence = next(
            (
                value
                for value in state.checklist.get("items", [])
                if value.get("item_id") == effect.evidence_item_id
            ),
            None,
        )
        if (
            fact is None
            or evidence is None
            or evidence.get("fact_id") != effect.fact_id
        ):
            raise ClaimLoopServiceError(
                "correction target is outside the accepted playbook"
            )
        if effect.fact_state == "known" and fact.get("controls_process") is True:
            decision_key = fact.get("decision_key")
            decision_options = playbook_template_from_accepted_v1(
                state.accepted_artifacts
            ).decision_options
            if effect.normalized_value not in decision_options.get(decision_key, {}):
                raise ClaimLoopServiceError(
                    "correction value is outside the bounded fact catalog"
                )
        scope = CorrectionScope(
            claim_ids=(state.claim_id,),
            fact_ids=(effect.fact_id,),
            evidence_item_ids=(effect.evidence_item_id,),
        )

        def build_correction(artifact_sha256: str) -> ScopedCorrection:
            payload = {
                "contract": "casepath.scoped-correction/1.0.0",
                "correction_artifact_receipt_sha256": artifact_sha256,
                "source_artifact_receipt_sha256": artifact.receipt_sha256,
                "source_ref": source_ref.model_dump(mode="json"),
                "record_version": state.record_version,
                "scope": scope.model_dump(mode="json"),
                "effect": effect.model_dump(mode="json"),
                "effective_at": timestamp,
                "expires_at": expires_at,
                "expiry_semantics": "admission_deadline_persistent_effect",
            }
            correction_sha256 = digest_value(payload)
            return ScopedCorrection.model_validate(
                {
                    **payload,
                    "correction_id": f"correction.{correction_sha256}",
                    "correction_sha256": correction_sha256,
                }
            )

        provisional = build_correction("0" * 64)
        provisional_ledger = (
            *state.projection_ledger,
            ProjectionLedgerEntry(
                kind="correction",
                record_sha256=provisional.correction_sha256,
                artifact_receipt_sha256=artifact.receipt_sha256,
                recorded_at=timestamp,
            ),
        )
        try:
            projected = project_claim_loop_artifacts_v1(
                accepted=state.accepted_artifacts,
                observations=state.observations,
                corrections=(*state.corrections, provisional),
                projection_ledger=provisional_ledger,
            )
        except (TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "correction proposal cannot produce a valid playbook state"
            ) from exc
        after_fact = next(
            value
            for value in projected["facts"]
            if value.get("fact_id") == effect.fact_id
        )
        after_evidence = next(
            value
            for value in projected["checklist"].get("items", [])
            if value.get("item_id") == effect.evidence_item_id
        )
        unrelated_before = [
            value for value in state.facts if value.get("fact_id") != effect.fact_id
        ]
        unrelated_after = [
            value
            for value in projected["facts"]
            if value.get("fact_id") != effect.fact_id
        ]
        if digest_value(unrelated_before) != digest_value(unrelated_after):
            raise ClaimLoopServiceError(
                "correction would spill outside its singleton projection scope"
            )
        authority_content = canonical_json_bytes(effect.model_dump(mode="json")).decode(
            "utf-8"
        )
        authority_content_sha256 = digest_text(authority_content)
        authority_source_ref = ClaimSourceRef.model_validate(
            {
                "contract": "casepath.claim-source-reference/1.0.0",
                "source_id": (
                    "correction-authority."
                    + digest_value(
                        {
                            "adapter_id": correction_adapter_id,
                            "parent_state_sha256": state.state_sha256,
                            "effect": effect.model_dump(mode="json"),
                        }
                    )
                ),
                "source_sha256": authority_content_sha256,
                "source_version": state.record_version,
                "locator_kind": "text_quote",
                "page": 1,
                "sanitized_excerpt": authority_content,
                "text_start": 0,
                "text_end": len(authority_content),
                "field": None,
                "value": None,
                "span_sha256": authority_content_sha256,
                "adapter_id": correction_adapter_id,
            }
        )
        receipt_payload = {
            "contract": "casepath.correction-artifact-receipt/1.0.0",
            "session_id": session_id,
            "loop_id": loop_id,
            "parent_state_sha256": state.state_sha256,
            "record_version": state.record_version,
            "target_claim_id": state.claim_id,
            "target_action_id": artifact.action_id,
            "source_artifact_receipt_sha256": artifact.receipt_sha256,
            "source_observation_sha256": observation.observation_sha256,
            "source_ref": source_ref.model_dump(mode="json"),
            "authority_adapter_id": correction_adapter_id,
            "authority_content": authority_content,
            "authority_content_sha256": authority_content_sha256,
            "authority_source_ref": authority_source_ref.model_dump(mode="json"),
            "scope": scope.model_dump(mode="json"),
            "proposed_effect": effect.model_dump(mode="json"),
            "before_fact_sha256": digest_value(fact),
            "before_evidence_sha256": digest_value(evidence),
            "expected_after_fact_sha256": digest_value(after_fact),
            "expected_after_evidence_sha256": digest_value(after_evidence),
            "unrelated_facts_before_sha256": digest_value(unrelated_before),
            "unrelated_facts_after_sha256": digest_value(unrelated_after),
            "rollback_fact_sha256": digest_value(fact),
            "rollback_evidence_sha256": digest_value(evidence),
            "issuer_kind": result.issuer_kind,
            "issuer_id": result.issuer_id,
            "provenance_note": result.provenance_note,
            "issued_at": timestamp,
            "expires_at": expires_at,
            "model_calls": result.model_calls,
            "provider_calls": result.provider_calls,
            "provider_credentials_read": result.provider_credentials_read,
            "cost_usd": result.cost_usd,
        }
        receipt = CorrectionArtifactReceipt.model_validate(
            {
                **receipt_payload,
                "receipt_sha256": digest_value(receipt_payload),
            }
        )
        correction = build_correction(receipt.receipt_sha256)
        final_ledger = (
            *state.projection_ledger,
            ProjectionLedgerEntry(
                kind="correction",
                record_sha256=correction.correction_sha256,
                artifact_receipt_sha256=artifact.receipt_sha256,
                recorded_at=timestamp,
            ),
        )
        final_projection = project_claim_loop_artifacts_v1(
            accepted=state.accepted_artifacts,
            observations=state.observations,
            corrections=(*state.corrections, correction),
            projection_ledger=final_ledger,
        )
        if (
            digest_value(
                next(
                    value
                    for value in final_projection["facts"]
                    if value.get("fact_id") == effect.fact_id
                )
            )
            != receipt.expected_after_fact_sha256
            or digest_value(
                next(
                    value
                    for value in final_projection["checklist"].get("items", [])
                    if value.get("item_id") == effect.evidence_item_id
                )
            )
            != receipt.expected_after_evidence_sha256
            or digest_value(
                [
                    value
                    for value in final_projection["facts"]
                    if value.get("fact_id") != effect.fact_id
                ]
            )
            != receipt.unrelated_facts_after_sha256
        ):
            raise ClaimLoopServiceError(
                "correction before/after commitment is not reproducible"
            )
        try:
            self.store.register_correction(
                correction_artifact=receipt,
                correction=correction,
                source_session_id=session_id,
                source_loop_id=loop_id,
                timestamp=timestamp,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return correction

    def reuse_correction(
        self,
        *,
        session_id: str,
        loop_id: str,
        correction_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._raw_state(session_id=session_id, loop_id=loop_id)
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="reuse_correction",
            request={"correction_id": correction_id},
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        request_sha256 = binding["request_sha256"]
        reserved_state = binding.get("reserved_state")
        if not isinstance(reserved_state, ClaimLoopState):
            raise ClaimLoopServiceError(
                "correction-reuse request lacks its reserved journal prefix"
            )
        if reserved_state.active_dispatch_sha256 is not None:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="reuse_correction",
                request_sha256=request_sha256,
                detail=(
                    "correction reuse is forbidden while a dispatch lease is active"
                ),
            )

        def finish(response: Mapping[str, Any]) -> dict[str, Any]:
            return self._complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="reuse_correction",
                request_sha256=request_sha256,
                response=response,
            )

        existing = self.store.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if (
                existing.event_type != "CORRECTION_REUSED"
                or existing.command.get("correction", {}).get("correction_id")
                != correction_id
            ):
                raise ClaimLoopServiceError(
                    "idempotency key was reused with different reuse input"
                )
            try:
                state, receipt, _ = self.store.append(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type=existing.event_type,
                    idempotency_key=idempotency_key,
                    command=existing.command,
                    timestamp=self._clock(),
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            return finish(self._response(state, receipt))
        current = self.state(session_id=session_id, loop_id=loop_id)
        if current.revision != reserved_state.revision:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="reuse_correction",
                request_sha256=request_sha256,
                detail=(
                    "correction-reuse reservation prefix changed before its transition"
                ),
            )
        current = reserved_state
        stored = self.store.correction(correction_id)
        if stored is None:
            raise ClaimLoopServiceError("correction was not found")
        correction, source_session_id, source_loop_id = stored
        if source_session_id != session_id:
            raise ClaimLoopServiceError(
                "correction reuse cannot cross a session boundary"
            )
        source_state, source_events = self.store.snapshot(
            session_id=source_session_id, loop_id=source_loop_id
        )
        source_application_events = [
            event
            for event in source_events
            if event.event_type == "CORRECTION_APPLIED"
            and event.command.get("correction", {}).get("correction_id")
            == correction.correction_id
        ]
        if len(source_application_events) != 1 or correction.correction_id not in {
            value.correction_id for value in source_state.corrections
        }:
            raise ClaimLoopServiceError(
                "correction was not durably applied in its source loop"
            )
        source_scope_records: list[tuple[str, str]] = []
        source_observation_by_hash = {
            value.observation_sha256: value for value in source_state.observations
        }
        source_correction_by_hash = {
            value.correction_sha256: value for value in source_state.corrections
        }
        for entry in source_state.projection_ledger:
            if entry.kind == "observation":
                observation = source_observation_by_hash[entry.record_sha256]
                if (
                    observation.fact_id == correction.effect.fact_id
                    and observation.evidence_item_id
                    == correction.effect.evidence_item_id
                ):
                    source_scope_records.append((entry.kind, entry.record_sha256))
            else:
                scoped = source_correction_by_hash[entry.record_sha256]
                if (
                    scoped.effect.fact_id == correction.effect.fact_id
                    and scoped.effect.evidence_item_id
                    == correction.effect.evidence_item_id
                ):
                    source_scope_records.append((entry.kind, entry.record_sha256))
        if not source_scope_records or source_scope_records[-1] != (
            "correction",
            correction.correction_sha256,
        ):
            raise ClaimLoopServiceError("correction was superseded in its source scope")
        source_application_event = source_application_events[0]
        source_before_state = self.store.state_at_revision(
            session_id=source_session_id,
            loop_id=source_loop_id,
            revision=source_application_event.sequence - 1,
        )
        origin_authority = self.store.correction_artifact(
            correction.correction_artifact_receipt_sha256
        )
        origin_artifact = self.store.tool_artifact(
            correction.source_artifact_receipt_sha256
        )
        if origin_authority is None or origin_artifact is None:
            raise ClaimLoopServiceError("correction authority receipt was not found")
        if source_loop_id == loop_id:
            raise ClaimLoopServiceError(
                "correction reuse requires a distinct loop in the same session"
            )
        if (
            correction.record_version != current.record_version
            or correction.scope.claim_ids != (current.claim_id,)
            or current.active_dispatch_sha256 is not None
        ):
            raise ClaimLoopServiceError(
                "correction reuse target does not match the frozen source boundary"
            )
        matching_target_artifact: ToolArtifactReceipt | None = None
        for entry in current.projection_ledger:
            target_artifact = self.store.tool_artifact(entry.artifact_receipt_sha256)
            if (
                target_artifact is not None
                and target_artifact.session_id == session_id
                and target_artifact.loop_id == loop_id
                and target_artifact.observation.fact_id == correction.effect.fact_id
                and target_artifact.observation.evidence_item_id
                == correction.effect.evidence_item_id
                and any(
                    source_span_authority_v1(value)
                    == source_span_authority_v1(correction.source_ref)
                    for value in target_artifact.observation.source_refs
                )
            ):
                matching_target_artifact = target_artifact
                break
        if matching_target_artifact is None:
            raise ClaimLoopServiceError(
                "correction reuse target lacks the exact matching source span"
            )
        target_fact = next(
            (
                value
                for value in current.facts
                if value.get("fact_id") == correction.effect.fact_id
            ),
            None,
        )
        target_evidence = next(
            (
                value
                for value in current.checklist.get("items", [])
                if value.get("item_id") == correction.effect.evidence_item_id
            ),
            None,
        )
        if (
            target_fact is None
            or target_evidence is None
            or target_evidence.get("fact_id") != correction.effect.fact_id
        ):
            raise ClaimLoopServiceError(
                "correction reuse target is outside the accepted playbook"
            )
        source_before_fact = next(
            (
                value
                for value in source_before_state.facts
                if value.get("fact_id") == correction.effect.fact_id
            ),
            None,
        )
        source_before_evidence = next(
            (
                value
                for value in source_before_state.checklist.get("items", [])
                if value.get("item_id") == correction.effect.evidence_item_id
            ),
            None,
        )
        if (
            source_before_fact is None
            or source_before_evidence is None
            or digest_value(
                _artifact_scoped_semantic_value(target_fact, matching_target_artifact)
            )
            != digest_value(
                _artifact_scoped_semantic_value(source_before_fact, origin_artifact)
            )
            or digest_value(
                _artifact_scoped_semantic_value(
                    target_evidence, matching_target_artifact
                )
            )
            != digest_value(
                _artifact_scoped_semantic_value(source_before_evidence, origin_artifact)
            )
        ):
            raise ClaimLoopServiceError(
                "correction reuse target has diverged from the proven before state"
            )
        target_ledger = (
            *current.projection_ledger,
            ProjectionLedgerEntry(
                kind="correction",
                record_sha256=correction.correction_sha256,
                artifact_receipt_sha256=(correction.source_artifact_receipt_sha256),
                recorded_at=correction.effective_at,
            ),
        )
        try:
            target_projection = project_claim_loop_artifacts_v1(
                accepted=current.accepted_artifacts,
                observations=current.observations,
                corrections=(*current.corrections, correction),
                projection_ledger=target_ledger,
            )
        except (TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "correction reuse cannot produce a valid target state"
            ) from exc
        target_after_fact = next(
            value
            for value in target_projection["facts"]
            if value.get("fact_id") == correction.effect.fact_id
        )
        target_after_evidence = next(
            value
            for value in target_projection["checklist"].get("items", [])
            if value.get("item_id") == correction.effect.evidence_item_id
        )
        target_unrelated_before = [
            value
            for value in current.facts
            if value.get("fact_id") != correction.effect.fact_id
        ]
        target_unrelated_after = [
            value
            for value in target_projection["facts"]
            if value.get("fact_id") != correction.effect.fact_id
        ]
        if digest_value(target_unrelated_before) != digest_value(
            target_unrelated_after
        ):
            raise ClaimLoopServiceError(
                "correction reuse would spill into an unrelated fact"
            )
        receipt_payload = {
            "contract": "casepath.correction-reuse-receipt/1.0.0",
            "correction_sha256": correction.correction_sha256,
            "correction_artifact_receipt_sha256": (
                correction.correction_artifact_receipt_sha256
            ),
            "source_artifact_receipt_sha256": (
                correction.source_artifact_receipt_sha256
            ),
            "target_matching_artifact_receipt_sha256": (
                matching_target_artifact.receipt_sha256
            ),
            "source_application_event_sha256": (source_application_event.event_sha256),
            "source_application_state_sha256": (
                source_application_event.resulting_state_sha256
            ),
            "source_session_id": source_session_id,
            "source_loop_id": source_loop_id,
            "target_session_id": session_id,
            "target_loop_id": loop_id,
            "target_claim_id": current.claim_id,
            "record_version": current.record_version,
            "target_parent_state_sha256": current.state_sha256,
            "target_before_fact_sha256": digest_value(target_fact),
            "target_before_evidence_sha256": digest_value(target_evidence),
            "target_expected_after_fact_sha256": digest_value(target_after_fact),
            "target_expected_after_evidence_sha256": digest_value(
                target_after_evidence
            ),
            "target_unrelated_facts_before_sha256": digest_value(
                target_unrelated_before
            ),
            "target_unrelated_facts_after_sha256": digest_value(target_unrelated_after),
            "applied_fact_ids": [correction.effect.fact_id],
            "applied_evidence_item_ids": [correction.effect.evidence_item_id],
        }
        reuse_receipt = CorrectionReuseReceipt.model_validate(
            {**receipt_payload, "receipt_sha256": digest_value(receipt_payload)}
        )
        timestamp = self._clock()
        command = self._correction_command(
            state=current,
            correction=correction,
            admitted_at=timestamp,
            source_session_id=source_session_id,
            reuse_receipt=reuse_receipt,
        )
        try:
            state, command_receipt, replayed = self.store.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type="CORRECTION_REUSED",
                idempotency_key=idempotency_key,
                command=command,
                timestamp=timestamp,
                expected_revision=current.revision,
            )
        except ClaimLoopStoreError as exc:
            raced = self.store.idempotent_event(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
            )
            if raced is not None:
                return self.reuse_correction(
                    session_id=session_id,
                    loop_id=loop_id,
                    correction_id=correction_id,
                    idempotency_key=idempotency_key,
                )
            latest = self.state(session_id=session_id, loop_id=loop_id)
            if latest.revision != current.revision:
                self._supersede_client_request(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type="reuse_correction",
                    request_sha256=request_sha256,
                    detail=(
                        "correction-reuse reservation prefix changed during its "
                        "transition"
                    ),
                )
            raise ClaimLoopServiceError(str(exc)) from exc
        return finish(self._response(state, command_receipt))

    def _require_protocol_adapter(self) -> LocalArtifactRegistryAdapterV1:
        if self.protocol_adapter is None:
            raise ClaimLoopServiceError("local artifact registration is not configured")
        return self.protocol_adapter

    def _protocol_fault(self, phase: str) -> None:
        if self._protocol_fault_hook is not None:
            self._protocol_fault_hook(phase)

    @staticmethod
    def _protocol_entries(
        events: tuple[Any, ...],
    ) -> tuple[tuple[Any, InsuranceProtocolRecordSetV1], ...]:
        entries: list[tuple[Any, InsuranceProtocolRecordSetV1]] = []
        for event in events:
            value = event.command.get("insurance_protocol_v1")
            if value is None:
                continue
            try:
                records = InsuranceProtocolRecordSetV1.model_validate_json(
                    canonical_json_bytes(value)
                )
            except (TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "journaled insurance protocol record set is invalid"
                ) from exc
            if (
                event.command.get("protocol_record_set_sha256")
                != records.record_set_sha256
            ):
                raise ClaimLoopServiceError("journaled protocol identity diverged")
            entries.append((event, records))
        return tuple(entries)

    def _validate_protocol_registry_receipt(
        self,
        entries: tuple[tuple[Any, InsuranceProtocolRecordSetV1], ...],
    ) -> None:
        if not entries:
            return
        receipt = entries[-1][1].action_receipt
        if receipt is None:
            return
        adapter = self._require_protocol_adapter()
        try:
            persisted = adapter.status(intent=entries[-1][1].intent)
        except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if persisted != receipt:
            raise ClaimLoopServiceError(
                "journaled protocol receipt differs from registry authority"
            )

    def _protocol_projection(
        self,
        *,
        state: ClaimLoopState,
        events: tuple[Any, ...],
    ) -> VersionedCaseStateV2:
        entries = self._protocol_entries(events)
        latest_records = entries[-1][1] if entries else None
        latest_type = entries[-1][0].event_type if entries else None
        thin_entries: list[tuple[Any, InsuranceThinWaistRecordSetV2]] = []
        for event in events:
            value = event.command.get("insurance_thin_waist_v2")
            if value is None:
                continue
            try:
                thin = InsuranceThinWaistRecordSetV2.model_validate_json(
                    canonical_json_bytes(value)
                )
            except (TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "journaled thin-waist record set is invalid"
                ) from exc
            if (
                event.command.get("thin_waist_record_set_sha256")
                != thin.record_set_sha256
            ):
                raise ClaimLoopServiceError("journaled thin-waist identity diverged")
            thin_entries.append((event, thin))
        latest_thin = thin_entries[-1][1] if thin_entries else None
        status_by_type = {
            "ACTION_DISPATCH_STARTED": "intent_journaled",
            "PROTOCOL_EXECUTION_STARTED": "execution_started",
            "DISPATCH_UNKNOWN": "dispatch_unknown",
            "PROTOCOL_INTENT_CANCELLED": "cancelled",
            "PROTOCOL_ACTION_RECEIPT_RECORDED": "receipt_recorded",
            "PROTOCOL_SOURCE_OBSERVATION_RECORDED": "source_observed",
            "PROTOCOL_ASSERTION_NORMALIZED": "assertion_normalized",
            "PROTOCOL_INTERPRETATION_RECORDED": "interpreted",
            "OBSERVATION_INGESTED": "replan_receipt_pending",
        }
        protocol_status = (
            status_by_type[latest_type] if latest_type is not None else "not_started"
        )
        if latest_thin is not None:
            protocol_status = (
                "replanned"
                if latest_thin.action_receipt is not None
                else "replan_receipt_pending"
            )
        pending = (
            latest_thin.action_intent.intent_sha256
            if protocol_status == "replan_receipt_pending" and latest_thin is not None
            else (
                latest_records.intent.intent_sha256
                if latest_records is not None
                and protocol_status not in {"cancelled", "replanned"}
                else None
            )
        )
        packet_sha256 = None
        if state.phase in {ClaimLoopPhase.DECISION_READY, ClaimLoopPhase.ABSTAINED}:
            packet_sha256 = decision_ready_packet(state).packet_sha256
        latest_correction = None
        for correction_event in reversed(events):
            if correction_event.event_type not in {
                "CORRECTION_APPLIED",
                "CORRECTION_REUSED",
            }:
                continue
            try:
                correction = ScopedCorrection.model_validate(
                    correction_event.command["correction"]
                )
                artifact = CorrectionArtifactReceipt.model_validate(
                    correction_event.command["correction_artifact_receipt"]
                )
                reuse_value = correction_event.command.get("reuse_receipt")
                reuse = (
                    CorrectionReuseReceipt.model_validate(reuse_value)
                    if reuse_value is not None
                    else None
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "journaled correction projection is invalid"
                ) from exc
            delta_payload = {
                "contract": "casepath.correction-delta-projection/1.0.0",
                "event_type": correction_event.event_type,
                "event_sha256": correction_event.event_sha256,
                "correction_id": correction.correction_id,
                "correction_sha256": correction.correction_sha256,
                "correction_artifact_receipt_sha256": artifact.receipt_sha256,
                "fact_id": correction.effect.fact_id,
                "evidence_item_id": correction.effect.evidence_item_id,
                "before_fact_sha256": (
                    reuse.target_before_fact_sha256
                    if reuse is not None
                    else artifact.before_fact_sha256
                ),
                "after_fact_sha256": (
                    reuse.target_expected_after_fact_sha256
                    if reuse is not None
                    else artifact.expected_after_fact_sha256
                ),
                "before_evidence_sha256": (
                    reuse.target_before_evidence_sha256
                    if reuse is not None
                    else artifact.before_evidence_sha256
                ),
                "after_evidence_sha256": (
                    reuse.target_expected_after_evidence_sha256
                    if reuse is not None
                    else artifact.expected_after_evidence_sha256
                ),
                "unrelated_facts_before_sha256": (
                    reuse.target_unrelated_facts_before_sha256
                    if reuse is not None
                    else artifact.unrelated_facts_before_sha256
                ),
                "unrelated_facts_after_sha256": (
                    reuse.target_unrelated_facts_after_sha256
                    if reuse is not None
                    else artifact.unrelated_facts_after_sha256
                ),
            }
            latest_correction = CorrectionDeltaProjectionV1.model_validate_json(
                canonical_json_bytes(
                    {**delta_payload, "delta_sha256": digest_value(delta_payload)}
                )
            )
            break
        payload = {
            "contract": "casepath.versioned-case-state/2.0.0",
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "claim_id": state.claim_id,
            "record_version": state.record_version,
            "base_revision": state.revision,
            "base_state_sha256": state.state_sha256,
            "last_event_sha256": state.last_event_sha256,
            "protocol_status": protocol_status,
            "protocol_event_sha256s": [
                event.event_sha256
                for event in events
                if event.command.get("insurance_protocol_v1") is not None
                or event.command.get("insurance_thin_waist_v2") is not None
            ],
            "record_set": (
                latest_records.model_dump(mode="json")
                if latest_records is not None
                else None
            ),
            "thin_waist_record_set": (
                latest_thin.model_dump(mode="json") if latest_thin is not None else None
            ),
            "pending_intent_sha256": pending,
            "next_action": (
                state.selected_action.model_dump(mode="json")
                if state.selected_action is not None
                else None
            ),
            "terminal_mode": state.terminal_mode,
            "decision_ready_packet_sha256": packet_sha256,
            "correction_count": len(state.corrections),
            "latest_correction": (
                latest_correction.model_dump(mode="json")
                if latest_correction is not None
                else None
            ),
        }
        return VersionedCaseStateV2.model_validate_json(
            canonical_json_bytes(
                {**payload, "projection_sha256": digest_value(payload)}
            )
        )

    def protocol_state(self, *, session_id: str, loop_id: str) -> dict[str, Any]:
        self._assert_session_authority(session_id)
        try:
            state, events = self.store.snapshot(session_id=session_id, loop_id=loop_id)
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        self._validate_protocol_registry_receipt(self._protocol_entries(events))
        return self._protocol_projection(state=state, events=events).model_dump(
            mode="json"
        )

    def protocol_proposal(self, *, session_id: str, loop_id: str) -> dict[str, Any]:
        self._assert_session_authority(session_id)
        try:
            state, events = self.store.snapshot(session_id=session_id, loop_id=loop_id)
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if self._protocol_entries(events):
            raise ClaimLoopServiceError(
                "an insurance registration lineage already exists"
            )
        try:
            proposal = build_verified_neutral_assessment_proposal_v1(
                state=state,
                journal_events=events,
            )
        except (InsuranceProtocolAuthorityError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        registration_action = build_registration_compatibility_action_v1(
            state=state,
            adapter=self._require_protocol_adapter(),
        )
        describe_input = getattr(self.artifact_interpreter, "input_contract", None)
        if not callable(describe_input):
            raise ClaimLoopServiceError(
                "configured artifact interpreter exposes no typed input contract"
            )
        try:
            evidence_input_contract = describe_input(
                action=registration_action,
                state=state,
            )
        except (ClaimLoopError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return {
            "contract": "casepath.insurance-proposal-response/1.0.0",
            "loop_id": loop_id,
            "revision": state.revision,
            "state_sha256": state.state_sha256,
            "proposal": proposal.model_dump(mode="json"),
            "proposal_sha256": proposal.proposal_sha256,
            "pace_scope": current_decision_scope_v1(
                state=state,
                journal_events=events,
            ),
            "registration_action": registration_action.model_dump(mode="json"),
            "evidence_input_contract": evidence_input_contract,
        }

    def _protocol_correction_candidate(
        self,
        *,
        state: ClaimLoopState,
        events: tuple[Any, ...],
        timestamp: str | None = None,
    ) -> dict[str, Any] | None:
        """Derive the only lawful correction choice from journal authority.

        The browser may choose this candidate, but cannot author a fact, scope,
        effect, or adapter.  A second candidate is exposed only after the first
        correction and restores the exact admitted observation as a rollback.
        """

        if state.active_dispatch_sha256 is not None:
            return None
        projection = self._protocol_projection(state=state, events=events)
        thin = projection.thin_waist_record_set
        if projection.protocol_status != "replanned" or thin is None:
            return None
        candidates: list[ToolArtifactReceipt] = []
        for entry in state.projection_ledger:
            if entry.kind != "observation":
                continue
            artifact = self.store.tool_artifact(entry.artifact_receipt_sha256)
            if artifact is None:
                raise ClaimLoopServiceError(
                    "protocol observation artifact is unavailable"
                )
            observation = artifact.observation
            if (
                observation.fact_id == "fact_cause"
                and observation.evidence_item_id == "technical_assessment"
                and observation.fact_state == "known"
                and observation.normalized_value == "building"
                and observation.evidence_status == "provided_sufficient"
            ):
                candidates.append(artifact)
        if len(candidates) != 1:
            return None
        if len(state.corrections) == 0:
            delta_id = "withdraw_decision_sufficiency_v1"
            delta_label = "Withdraw this assessment's decision-bearing sufficiency"
            adapter_id = MouldNeutralAssessmentCorrectionAdapterV1.adapter_id
            operation = "apply_scoped_correction"
        elif len(state.corrections) == 1:
            delta_id = "restore_admitted_assertion_v1"
            delta_label = "Roll back to the exact admitted assessment assertion"
            adapter_id = MouldNeutralAssessmentRollbackAdapterV1.adapter_id
            operation = "rollback_scoped_correction"
        else:
            return None
        adapter = self.correction_adapters.get(adapter_id)
        if adapter is None or adapter.adapter_id != adapter_id:
            raise ClaimLoopServiceError(
                "required correction authority adapter is unavailable"
            )
        try:
            result = adapter.execute(
                source_artifact=candidates[0],
                state=state,
                timestamp=timestamp or state.last_event_sha256,
            )
        except (ClaimLoopError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if (
            not isinstance(result, CorrectionToolResult)
            or result.issuer_id != adapter_id
        ):
            raise ClaimLoopServiceError(
                "correction candidate issuer differs from configured authority"
            )
        fact = next(
            value
            for value in state.facts
            if value.get("fact_id") == result.effect.fact_id
        )
        evidence = next(
            value
            for value in state.checklist.get("items", [])
            if value.get("item_id") == result.effect.evidence_item_id
        )
        payload = {
            "contract": "casepath.correction-choice/1.0.0",
            "operation": operation,
            "loop_id": state.loop_id,
            "revision": state.revision,
            "state_sha256": state.state_sha256,
            "source_artifact_receipt_sha256": candidates[0].receipt_sha256,
            "source_observation_sha256": (candidates[0].observation.observation_sha256),
            "target_assertion_sha256": thin.normalized_assertion.assertion_sha256,
            "target_interpretation_sha256": (thin.interpretation.interpretation_sha256),
            "target_fact_id": result.effect.fact_id,
            "target_evidence_item_id": result.effect.evidence_item_id,
            "current_semantics": {
                "fact_state": fact.get("state"),
                "normalized_value": fact.get("normalized_value"),
                "value": fact.get("value"),
                "evidence_status": evidence.get("status"),
            },
            "semantic_delta_id": delta_id,
            "semantic_delta_label": delta_label,
            "proposed_semantics": {
                "fact_state": result.effect.fact_state,
                "normalized_value": result.effect.normalized_value,
                "value": result.effect.value,
                "evidence_status": result.effect.evidence_status,
                "explanation": result.effect.explanation,
            },
            "authority_adapter_id": adapter_id,
        }
        return {**payload, "candidate_sha256": digest_value(payload)}

    def protocol_correction_options(
        self, *, session_id: str, loop_id: str
    ) -> dict[str, Any]:
        self._assert_session_authority(session_id)
        try:
            state, events = self.store.snapshot(session_id=session_id, loop_id=loop_id)
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        candidate = self._protocol_correction_candidate(state=state, events=events)
        payload = {
            "contract": "casepath.correction-options/1.0.0",
            "loop_id": loop_id,
            "revision": state.revision,
            "state_sha256": state.state_sha256,
            "candidates": [candidate] if candidate is not None else [],
        }
        return {**payload, "options_sha256": digest_value(payload)}

    def prepare_protocol_correction(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        correction_adapter_id: str | None = None,
        candidate_sha256: str | None = None,
        target_assertion_sha256: str | None = None,
        target_interpretation_sha256: str | None = None,
        semantic_delta_id: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create one server-derived, case-local correction authority.

        Public callers select one server-enumerated candidate.  They still
        supply no fact value, scope, evidence authority, or free-form truth.
        The selected candidate binds the admitted assertion, interpretation,
        typed delta and configured adapter; the server rederives all of it.
        """

        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="insurance_prepare_correction",
            request={
                "candidate_sha256": candidate_sha256,
                "target_assertion_sha256": target_assertion_sha256,
                "target_interpretation_sha256": target_interpretation_sha256,
                "semantic_delta_id": semantic_delta_id,
                "correction_adapter_id": correction_adapter_id,
                "expected_revision": expected_revision,
            },
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        reserved = binding.get("reserved_state")
        if not isinstance(reserved, ClaimLoopState):
            raise ClaimLoopServiceError("correction preparation lacks a journal prefix")
        try:
            all_events = self.store.events(session_id=session_id, loop_id=loop_id)
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        prefix_events = all_events[: reserved.revision]
        if (
            len(prefix_events) != reserved.revision
            or not prefix_events
            or prefix_events[-1].event_sha256 != reserved.last_event_sha256
        ):
            raise ClaimLoopServiceError(
                "correction reservation journal prefix is unavailable"
            )
        selected = self._protocol_correction_candidate(
            state=reserved,
            events=prefix_events,
            timestamp=binding["created_at"],
        )
        if selected is None:
            raise ClaimLoopServiceError("no scoped correction candidate is available")
        # Direct service callers from the legacy invariant suite may omit the
        # public selection fields. The HTTP boundary requires all of them.
        candidate_sha256 = candidate_sha256 or selected["candidate_sha256"]
        target_assertion_sha256 = (
            target_assertion_sha256 or selected["target_assertion_sha256"]
        )
        target_interpretation_sha256 = (
            target_interpretation_sha256 or selected["target_interpretation_sha256"]
        )
        semantic_delta_id = semantic_delta_id or selected["semantic_delta_id"]
        correction_adapter_id = (
            correction_adapter_id or selected["authority_adapter_id"]
        )
        if (
            candidate_sha256 != selected["candidate_sha256"]
            or target_assertion_sha256 != selected["target_assertion_sha256"]
            or target_interpretation_sha256 != selected["target_interpretation_sha256"]
            or semantic_delta_id != selected["semantic_delta_id"]
            or correction_adapter_id != selected["authority_adapter_id"]
            or (
                expected_revision is not None
                and expected_revision != selected["revision"]
            )
        ):
            raise ClaimLoopServiceError(
                "correction selection differs from server-owned authority"
            )
        current = self.state(session_id=session_id, loop_id=loop_id)
        if current.state_sha256 != reserved.state_sha256:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_prepare_correction",
                request_sha256=binding["request_sha256"],
                detail="correction preparation prefix changed",
            )
        if reserved.active_dispatch_sha256 is not None:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_prepare_correction",
                request_sha256=binding["request_sha256"],
                detail="correction preparation is forbidden during dispatch",
            )
        candidates: list[ToolArtifactReceipt] = []
        for entry in reserved.projection_ledger:
            if entry.kind != "observation":
                continue
            artifact = self.store.tool_artifact(entry.artifact_receipt_sha256)
            if artifact is None:
                raise ClaimLoopServiceError(
                    "protocol observation artifact is unavailable"
                )
            observation = artifact.observation
            if (
                observation.fact_id == "fact_cause"
                and observation.evidence_item_id == "technical_assessment"
                and observation.fact_state == "known"
                and observation.normalized_value == "building"
                and observation.evidence_status == "provided_sufficient"
            ):
                candidates.append(artifact)
        if len(candidates) != 1:
            raise ClaimLoopServiceError(
                "exactly one admitted neutral assessment is required"
            )
        self._protocol_fault("BEFORE_CORRECTION_AUTHORITY_ADMISSION")
        try:
            correction = self.register_correction(
                session_id=session_id,
                loop_id=loop_id,
                source_artifact_receipt_sha256=candidates[0].receipt_sha256,
                correction_adapter_id=correction_adapter_id,
                issued_at=binding["created_at"],
                expected_parent_state_sha256=reserved.state_sha256,
                expected_effect={
                    "fact_id": selected["target_fact_id"],
                    "evidence_item_id": selected["target_evidence_item_id"],
                    **selected["proposed_semantics"],
                },
            )
        except ClaimLoopServiceError:
            latest = self.state(session_id=session_id, loop_id=loop_id)
            if latest.state_sha256 != reserved.state_sha256:
                self._supersede_client_request(
                    session_id=session_id,
                    loop_id=loop_id,
                    idempotency_key=idempotency_key,
                    request_type="insurance_prepare_correction",
                    request_sha256=binding["request_sha256"],
                    detail=("correction authority prefix changed before admission"),
                )
            raise
        if correction.effect.model_dump(mode="json") != {
            "fact_id": selected["target_fact_id"],
            "evidence_item_id": selected["target_evidence_item_id"],
            **selected["proposed_semantics"],
        }:
            raise ClaimLoopServiceError(
                "persisted correction effect differs from selected semantic preview"
            )
        response = {
            **self._response(reserved, None),
            "contract": "casepath.insurance-correction-proposal-response/1.0.0",
            "correction_id": correction.correction_id,
            "correction_sha256": correction.correction_sha256,
            "source_artifact_receipt_sha256": (
                correction.source_artifact_receipt_sha256
            ),
            "scope": correction.scope.model_dump(mode="json"),
            "effect": correction.effect.model_dump(mode="json"),
            "selection": selected,
        }
        artifact = self.store.correction_artifact(
            correction.correction_artifact_receipt_sha256
        )
        if artifact is None:
            raise ClaimLoopServiceError(
                "correction preview authority was not persisted"
            )
        response["preview"] = {
            "correction_artifact_receipt_sha256": artifact.receipt_sha256,
            "parent_state_sha256": artifact.parent_state_sha256,
            "target_claim_id": artifact.target_claim_id,
            "target_action_id": artifact.target_action_id,
            "before_fact_sha256": artifact.before_fact_sha256,
            "expected_after_fact_sha256": artifact.expected_after_fact_sha256,
            "before_evidence_sha256": artifact.before_evidence_sha256,
            "expected_after_evidence_sha256": (artifact.expected_after_evidence_sha256),
            "unrelated_facts_before_sha256": (artifact.unrelated_facts_before_sha256),
            "unrelated_facts_after_sha256": artifact.unrelated_facts_after_sha256,
            "rollback_fact_sha256": artifact.rollback_fact_sha256,
            "rollback_evidence_sha256": artifact.rollback_evidence_sha256,
            "before_semantics": selected["current_semantics"],
            "expected_after_semantics": selected["proposed_semantics"],
            "operation": selected["operation"],
        }
        try:
            return self.store.complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_prepare_correction",
                request_sha256=binding["request_sha256"],
                response=response,
                completed_at=self._clock(),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    def stage_protocol_material(
        self,
        *,
        session_id: str,
        loop_id: str,
        filename: str,
        media_type: str,
        content: str,
        idempotency_key: str,
        claimed_content_sha256: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        adapter = self._require_protocol_adapter()
        if getattr(adapter, "requires_typed_factual_history_stage", False):
            raise ClaimLoopServiceError("ECAB_TYPED_FACTUAL_HISTORY_STAGE_REQUIRED")
        state = self._raw_state(session_id=session_id, loop_id=loop_id)
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="insurance_stage",
            request={
                "filename": filename,
                "media_type": media_type,
                "content": content,
                "claimed_content_sha256": claimed_content_sha256,
                "expected_revision": expected_revision,
            },
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        reserved = binding.get("reserved_state")
        if not isinstance(reserved, ClaimLoopState):
            raise ClaimLoopServiceError("stage request lacks a journal prefix")
        if state.revision != reserved.revision or (
            expected_revision is not None and expected_revision != reserved.revision
        ):
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_stage",
                request_sha256=binding["request_sha256"],
                detail="stage reservation prefix changed before quarantine",
            )
        validate_content = getattr(self.artifact_interpreter, "validate_content", None)
        if not callable(validate_content):
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_stage",
                request_sha256=binding["request_sha256"],
                detail=(
                    "configured artifact interpreter exposes no admission validator"
                ),
            )
        try:
            validate_content(
                action=build_registration_compatibility_action_v1(
                    state=reserved,
                    adapter=adapter,
                ),
                state=reserved,
                content=content,
            )
        except (ClaimLoopError, TypeError, ValueError) as exc:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_stage",
                request_sha256=binding["request_sha256"],
                detail=f"typed evidence admission rejected: {exc}",
            )
        material = LocalRegistryMaterialV1(
            filename=filename,
            media_type=media_type,
            content=content,
            claimed_content_sha256=(claimed_content_sha256 or digest_text(content)),
        )
        try:
            staged = adapter.stage(
                session_id=session_id,
                loop_id=loop_id,
                claim_id=reserved.claim_id,
                record_version=reserved.record_version,
                material=material,
                staged_at=binding["created_at"],
            )
        except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_stage",
                request_sha256=binding["request_sha256"],
                detail=f"artifact quarantine rejected: {exc}",
            )
        response = {
            **self._response(reserved, None),
            "contract": "casepath.insurance-stage-response/1.0.0",
            "staged_artifact": staged.model_dump(mode="json"),
            "staged_artifact_receipt_sha256": staged.receipt_sha256,
        }
        try:
            return self.store.complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_stage",
                request_sha256=binding["request_sha256"],
                response=response,
                completed_at=self._clock(),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    def stage_protocol_factual_history(
        self,
        *,
        session_id: str,
        loop_id: str,
        span: ECABFactualHistorySpanV1,
        idempotency_key: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Stage one outcome-free span against the server-derived action."""

        adapter = self._require_protocol_adapter()
        stage_typed = getattr(adapter, "stage_factual_history", None)
        if not getattr(
            adapter, "requires_typed_factual_history_stage", False
        ) or not callable(stage_typed):
            raise ClaimLoopServiceError("FACTUAL_HISTORY_ADAPTER_REQUIRED")
        span = ECABFactualHistorySpanV1.model_validate(span.model_dump(mode="json"))
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="insurance_stage_factual_history",
            request={
                "span": span.model_dump(mode="json"),
                "expected_revision": expected_revision,
            },
        )
        if binding["response"] is not None:
            return deepcopy(binding["response"])
        reserved = binding.get("reserved_state")
        if not isinstance(reserved, ClaimLoopState):
            raise ClaimLoopServiceError("factual-history stage lacks a journal prefix")
        current = self._raw_state(session_id=session_id, loop_id=loop_id)
        if current.revision != reserved.revision or (
            expected_revision is not None and expected_revision != reserved.revision
        ):
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_stage_factual_history",
                request_sha256=binding["request_sha256"],
                detail="factual-history stage prefix changed before quarantine",
            )
        action = build_registration_compatibility_action_v1(
            state=reserved,
            adapter=adapter,
        )
        try:
            mapped_stage = stage_typed(
                session_id=session_id,
                loop_id=loop_id,
                claim_id=reserved.claim_id,
                record_version=reserved.record_version,
                action=action,
                span=span,
                staged_at=binding["created_at"],
            )
        except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_stage_factual_history",
                request_sha256=binding["request_sha256"],
                detail=f"factual-history quarantine rejected: {exc}",
            )
        response = {
            **self._response(reserved, None),
            "contract": "casepath.insurance-factual-history-stage-response/1.0.0",
            "registration_action": action.model_dump(mode="json"),
            "mapped_stage_receipt": mapped_stage.model_dump(mode="json"),
            "mapped_stage_receipt_sha256": mapped_stage.receipt_sha256,
            "staged_artifact": mapped_stage.staged_artifact.model_dump(mode="json"),
            "staged_artifact_receipt_sha256": (
                mapped_stage.staged_artifact.receipt_sha256
            ),
        }
        try:
            return self.store.complete_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_stage_factual_history",
                request_sha256=binding["request_sha256"],
                response=response,
                completed_at=self._clock(),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    @staticmethod
    def _protocol_staging_binding(
        adapter: LocalArtifactRegistryAdapterV1,
        staged_artifact_receipt_sha256: str,
    ) -> dict[str, Any] | None:
        reader = getattr(adapter, "staging_binding", None)
        if not callable(reader):
            return None
        binding = reader(staged_artifact_receipt_sha256)
        return binding.model_dump(mode="json")

    def _append_protocol_event(
        self,
        *,
        state: ClaimLoopState,
        records: InsuranceProtocolRecordSetV1,
        event_type: str,
        event_kind: str,
        client_idempotency_key: str,
        request_sha256: str,
        timestamp: str,
    ) -> tuple[ClaimLoopState, ClaimLoopCommandReceipt | None, bool]:
        session_id = state.session_id
        loop_id = state.loop_id
        if state.last_event_sha256 is None:
            raise ClaimLoopServiceError(
                "protocol transition lacks its journaled intent"
            )
        command = {
            "dispatch_sha256": state.active_dispatch_sha256,
            "intent_sha256": records.intent.intent_sha256,
            "protocol_record_set_sha256": records.record_set_sha256,
            "insurance_protocol_v1": records.model_dump(mode="json"),
            "origin_client_idempotency_key": client_idempotency_key,
            "origin_client_request_sha256": request_sha256,
            "origin_client_request_type": "insurance_register",
            "prior_protocol_event_sha256": state.last_event_sha256,
        }
        staging_binding = self._protocol_staging_binding(
            self._require_protocol_adapter(),
            records.staged_artifact.receipt_sha256,
        )
        if staging_binding is not None:
            command["adapter_staging_binding"] = staging_binding
        if event_type == "DISPATCH_UNKNOWN":
            if state.selected_action is None:
                raise ClaimLoopServiceError(
                    "unknown protocol dispatch lacks its active action"
                )
            command["action_id"] = state.selected_action.action_id
        try:
            return self.store.append_or_return_protocol_winner(
                session_id=session_id,
                loop_id=loop_id,
                event_type=event_type,
                event_kind=event_kind,
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                command=command,
                timestamp=timestamp,
                expected_revision=state.revision,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    @staticmethod
    def _source_observation(
        *,
        state: ClaimLoopState,
        records: InsuranceProtocolRecordSetV1,
        receipt: ActionReceiptV1,
        content: str,
    ) -> SourceObservationV1:
        if receipt.artifact_uri is None or receipt.committed_at is None:
            raise ClaimLoopServiceError("committed action receipt is incomplete")
        payload = {
            "contract": "casepath.source-observation/1.0.0",
            "session_id": state.session_id,
            "loop_id": state.loop_id,
            "claim_id": state.claim_id,
            "record_version": state.record_version,
            "action_receipt_sha256": receipt.receipt_sha256,
            "artifact_uri": receipt.artifact_uri,
            "content_sha256": digest_text(content),
            "source_version": state.record_version,
            "page": 1,
            "text_start": 0,
            "text_end": len(content),
            "exact_text_sha256": digest_text(content),
            "observed_at": receipt.committed_at,
            "authority": "local_artifact_registry_receipt",
        }
        return SourceObservationV1.model_validate(
            {**payload, "observation_sha256": digest_value(payload)}
        )

    @staticmethod
    def _normalized_assertion(
        *,
        source: SourceObservationV1,
        artifact: ToolArtifactReceipt,
    ) -> NormalizedAssertionV1:
        canonical = artifact.interpretation
        observation = artifact.observation
        payload = {
            "contract": "casepath.normalized-assertion/1.0.0",
            "source_observation_sha256": source.observation_sha256,
            "fact_id": observation.fact_id,
            "evidence_item_id": observation.evidence_item_id,
            "fact_state": observation.fact_state,
            "normalized_value": observation.normalized_value,
            "extraction_method": canonical.implementation,
            "extraction_method_source_sha256": (canonical.implementation_source_sha256),
            "claim_observation_sha256": observation.observation_sha256,
            "claim_observation": observation.model_dump(mode="json"),
            "canonical_interpretation": canonical.model_dump(mode="json"),
        }
        return NormalizedAssertionV1.model_validate(
            {**payload, "assertion_sha256": digest_value(payload)}
        )

    @staticmethod
    def _interpretation_record(
        *,
        state: ClaimLoopState,
        assertion: NormalizedAssertionV1,
    ) -> InterpretationV1:
        canonical = assertion.canonical_interpretation
        observation = assertion.claim_observation
        if (
            observation.fact_state == "known"
            and observation.evidence_status == "provided_sufficient"
        ):
            status = "supported"
        elif observation.fact_state == "conflicting":
            status = "disputed"
        else:
            status = "insufficient"
        template = state.accepted_artifacts.get("playbook_template")
        if not isinstance(template, Mapping) or not isinstance(
            template.get("template_sha256"), str
        ):
            raise ClaimLoopServiceError("playbook template identity is absent")
        payload = {
            "contract": "casepath.interpretation/1.0.0",
            "assertion_sha256": assertion.assertion_sha256,
            "canonical_interpretation_receipt_sha256": canonical.receipt_sha256,
            "prior_fact_sha256": canonical.prior_fact_sha256,
            "assertion_catalog_sha256": canonical.assertion_catalog_sha256,
            "selected_assertion_id": canonical.selected_assertion_id,
            "playbook_template_sha256": template["template_sha256"],
            "policy_version": "casepath.claim-loop-interpretation-policy/1.0.0",
            "status": status,
        }
        return InterpretationV1.model_validate(
            {**payload, "interpretation_sha256": digest_value(payload)}
        )

    @staticmethod
    def _thin_waist_replan_intent_v2(
        *,
        state: ClaimLoopState,
        records: InsuranceProtocolRecordSetV1,
        timestamp: str,
    ) -> InsuranceThinWaistRecordSetV2:
        try:
            return build_thin_waist_replan_intent_v2(
                session_id=state.session_id,
                loop_id=state.loop_id,
                claim_id=state.claim_id,
                record_version=state.record_version,
                source_state_sha256=state.state_sha256,
                source_revision=state.revision,
                records=records,
                timestamp=timestamp,
            )
        except ValueError as exc:
            raise ClaimLoopServiceError(
                "canonical replan intent requires the complete epistemic prefix"
            ) from exc

    @staticmethod
    def _thin_waist_replan_receipt_v2(
        *,
        lineage: InsuranceThinWaistRecordSetV2,
        receipt: ClaimLoopCommandReceipt,
        committed_at: str,
    ) -> InsuranceThinWaistRecordSetV2:
        receipt_payload = {
            "contract": "casepath.interpretation-action-receipt/2.0.0",
            "intent_sha256": lineage.action_intent.intent_sha256,
            "status": "committed",
            "committed_event_sha256": receipt.event_sha256,
            "resulting_state_sha256": receipt.state_sha256,
            "resulting_revision": receipt.revision,
            "committed_at": committed_at,
        }
        action_receipt = InterpretationActionReceiptV2.model_validate(
            {
                **receipt_payload,
                "receipt_sha256": digest_value(receipt_payload),
            }
        )
        payload = lineage.model_dump(mode="json", exclude={"record_set_sha256"})
        payload["action_receipt"] = action_receipt.model_dump(mode="json")
        return hash_thin_waist_record_set_v2(payload)

    def _ensure_thin_waist_replan_receipt_v2(
        self,
        *,
        session_id: str,
        loop_id: str,
        client_idempotency_key: str,
        request_sha256: str,
    ) -> tuple[ClaimLoopState, ClaimLoopCommandReceipt]:
        for _ in range(16):
            canonical, events = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
            observation_event = next(
                (
                    event
                    for event in reversed(events)
                    if event.event_type == "OBSERVATION_INGESTED"
                    and event.command.get("insurance_thin_waist_v2") is not None
                ),
                None,
            )
            if observation_event is None:
                raise ClaimLoopServiceError(
                    "committed protocol replan lacks its thin-waist intent"
                )
            try:
                lineage = InsuranceThinWaistRecordSetV2.model_validate_json(
                    canonical_json_bytes(
                        observation_event.command["insurance_thin_waist_v2"]
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "journaled thin-waist replan intent is invalid"
                ) from exc
            result_receipt_payload = {
                "contract": "casepath.claim-loop-command-receipt/1.0.0",
                "loop_id": loop_id,
                "idempotency_key": observation_event.idempotency_key,
                "event_sha256": observation_event.event_sha256,
                "state_sha256": observation_event.resulting_state_sha256,
                "revision": observation_event.sequence,
            }
            result_receipt = ClaimLoopCommandReceipt.model_validate(
                {
                    **result_receipt_payload,
                    "receipt_sha256": digest_value(result_receipt_payload),
                }
            )
            completed = self._thin_waist_replan_receipt_v2(
                lineage=lineage,
                receipt=result_receipt,
                committed_at=observation_event.created_at,
            )
            command = {
                "thin_waist_record_set_sha256": completed.record_set_sha256,
                "insurance_thin_waist_v2": completed.model_dump(mode="json"),
                "committed_replan_event_sha256": observation_event.event_sha256,
                "origin_client_idempotency_key": client_idempotency_key,
                "origin_client_request_sha256": request_sha256,
                "origin_client_request_type": "insurance_register",
            }
            try:
                elected, command_receipt, _ = (
                    self.store.append_or_return_protocol_winner(
                        session_id=session_id,
                        loop_id=loop_id,
                        event_type="PROTOCOL_REPLAN_RECEIPT_RECORDED",
                        event_kind="replan-receipt",
                        client_idempotency_key=client_idempotency_key,
                        request_sha256=request_sha256,
                        command=command,
                        timestamp=observation_event.created_at,
                        expected_revision=canonical.revision,
                    )
                )
            except ClaimLoopStoreError as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            if command_receipt is not None:
                return elected, command_receipt
        raise ClaimLoopServiceError("thin-waist receipt election did not stabilize")

    def _resume_protocol_registration(
        self,
        *,
        state: ClaimLoopState,
        records: InsuranceProtocolRecordSetV1,
        client_idempotency_key: str,
        request_sha256: str,
        allow_execute: bool,
        allow_reconcile: bool = False,
    ) -> dict[str, Any]:
        adapter = self._require_protocol_adapter()
        session_id = state.session_id
        loop_id = state.loop_id
        requested_intent_sha256 = records.intent.intent_sha256
        state, events = self.store.snapshot(
            session_id=session_id,
            loop_id=loop_id,
        )
        entries = self._protocol_entries(events)
        if not entries:
            raise ClaimLoopServiceError("insurance intent journal is absent")
        if entries[0][1].intent.intent_sha256 != requested_intent_sha256:
            raise ClaimLoopServiceError(
                "insurance registration resumed a different journaled intent"
            )
        latest_event, records = entries[-1]
        if latest_event.event_type in {
            "OBSERVATION_INGESTED",
            "PROTOCOL_INTENT_CANCELLED",
        }:
            if latest_event.event_type == "OBSERVATION_INGESTED":
                replay_state, command_receipt = (
                    self._ensure_thin_waist_replan_receipt_v2(
                        session_id=session_id,
                        loop_id=loop_id,
                        client_idempotency_key=client_idempotency_key,
                        request_sha256=request_sha256,
                    )
                )
                self._protocol_fault("AFTER_REPLAN")
            else:
                replay_state, command_receipt, _ = self._append_protocol_event(
                    state=state,
                    records=records,
                    event_type="PROTOCOL_INTENT_CANCELLED",
                    event_kind="intent-cancelled",
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    timestamp=latest_event.created_at,
                )
                if command_receipt is None:
                    return self._resume_protocol_registration(
                        state=replay_state,
                        records=entries[0][1],
                        client_idempotency_key=client_idempotency_key,
                        request_sha256=request_sha256,
                        allow_execute=False,
                        allow_reconcile=allow_reconcile,
                    )
            response = self._response_with_protocol_prefix(
                state=replay_state,
                receipt=command_receipt,
            )
            return self._complete_protocol_request(
                state=replay_state,
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                response=response,
            )
        event_types = {event.event_type for event, _ in entries}
        execution_already_started = "PROTOCOL_EXECUTION_STARTED" in event_types
        if not execution_already_started:
            if not allow_execute:
                raise ClaimLoopServiceError(
                    "intent was journaled but execution was not started"
                )
            try:
                current_time = datetime.fromisoformat(
                    self._clock().replace("Z", "+00:00")
                )
                expiry = datetime.fromisoformat(
                    records.intent.expires_at.replace("Z", "+00:00")
                )
            except (AttributeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "protocol execution lease is invalid"
                ) from exc
            if current_time >= expiry:
                try:
                    expired_receipt = adapter.status(intent=records.intent)
                    if expired_receipt is None:
                        expired_receipt = adapter.cancel(
                            intent=records.intent,
                            cancelled_at=current_time.isoformat(),
                        )
                except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
                    try:
                        persisted = adapter.status(intent=records.intent)
                    except (
                        LocalArtifactRegistryError,
                        TypeError,
                        ValueError,
                    ) as status_exc:
                        raise ClaimLoopServiceError(str(status_exc)) from status_exc
                    refreshed, refreshed_events = self.store.snapshot(
                        session_id=session_id,
                        loop_id=loop_id,
                    )
                    refreshed_entries = self._protocol_entries(refreshed_events)
                    if persisted is not None or (
                        refreshed_entries
                        and refreshed_entries[-1][0].event_sha256
                        != latest_event.event_sha256
                    ):
                        return self._resume_protocol_registration(
                            state=refreshed,
                            records=entries[0][1],
                            client_idempotency_key=client_idempotency_key,
                            request_sha256=request_sha256,
                            allow_execute=False,
                            allow_reconcile=True,
                        )
                    raise ClaimLoopServiceError(str(exc)) from exc
                refreshed, refreshed_events = self.store.snapshot(
                    session_id=session_id,
                    loop_id=loop_id,
                )
                refreshed_entries = self._protocol_entries(refreshed_events)
                if (
                    not refreshed_entries
                    or refreshed_entries[-1][0].event_sha256
                    != latest_event.event_sha256
                ):
                    return self._resume_protocol_registration(
                        state=refreshed,
                        records=entries[0][1],
                        client_idempotency_key=client_idempotency_key,
                        request_sha256=request_sha256,
                        allow_execute=False,
                        allow_reconcile=allow_reconcile,
                    )
                state = refreshed
                records = refreshed_entries[-1][1]
                if expired_receipt.status is not ActionReceiptStatus.CANCELLED:
                    return self._resume_protocol_registration(
                        state=state,
                        records=entries[0][1],
                        client_idempotency_key=client_idempotency_key,
                        request_sha256=request_sha256,
                        allow_execute=False,
                        allow_reconcile=True,
                    )
                cancelled_records = _protocol_records_with(
                    records,
                    action_receipt=expired_receipt.model_dump(mode="json"),
                )
                state, receipt, _ = self._append_protocol_event(
                    state=state,
                    records=cancelled_records,
                    event_type="PROTOCOL_INTENT_CANCELLED",
                    event_kind="intent-cancelled",
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    timestamp=expired_receipt.committed_at or current_time.isoformat(),
                )
                if receipt is None:
                    return self._resume_protocol_registration(
                        state=state,
                        records=entries[0][1],
                        client_idempotency_key=client_idempotency_key,
                        request_sha256=request_sha256,
                        allow_execute=False,
                        allow_reconcile=allow_reconcile,
                    )
                response = self._response_with_protocol_prefix(
                    state=state,
                    receipt=receipt,
                )
                return self._complete_protocol_request(
                    state=state,
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    response=response,
                )
            self._protocol_fault("BEFORE_EXECUTION_START")
            state, execution_receipt, replayed = self._append_protocol_event(
                state=state,
                records=records,
                event_type="PROTOCOL_EXECUTION_STARTED",
                event_kind="execution-started",
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                timestamp=records.intent.created_at,
            )
            if execution_receipt is None or replayed:
                return self._resume_protocol_registration(
                    state=state,
                    records=entries[0][1],
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=allow_reconcile,
                )
            self._protocol_fault("AFTER_EXECUTION_START")
            state, events = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
            entries = self._protocol_entries(events)
            latest_event, records = entries[-1]
        else:
            # The durable start marker is the execute-once boundary.  A retry
            # may inspect/cancel/reconcile the same intent but may not invoke
            # the side-effecting execute method again.
            allow_execute = False
        try:
            action_receipt = adapter.status(intent=records.intent)
        except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        refreshed_state, refreshed_events = self.store.snapshot(
            session_id=session_id,
            loop_id=loop_id,
        )
        refreshed_entries = self._protocol_entries(refreshed_events)
        if (
            not refreshed_entries
            or refreshed_entries[-1][0].event_sha256 != latest_event.event_sha256
        ):
            return self._resume_protocol_registration(
                state=refreshed_state,
                records=entries[0][1],
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=allow_reconcile,
            )
        state = refreshed_state
        events = refreshed_events
        entries = refreshed_entries
        latest_event, records = entries[-1]
        if (
            latest_event.event_type == "PROTOCOL_EXECUTION_STARTED"
            and not allow_execute
            and action_receipt is None
        ):
            try:
                current = datetime.fromisoformat(self._clock().replace("Z", "+00:00"))
                expires = datetime.fromisoformat(
                    records.intent.expires_at.replace("Z", "+00:00")
                )
            except (AttributeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "protocol execution lease is invalid"
                ) from exc
            if current < expires:
                # Another same-key caller owns the already-journaled execute
                # boundary.  Give it one bounded chance to publish the immutable
                # response before treating a durable COMMIT_CLAIMED receipt as
                # a crashed-owner uncertainty.  A truly absent adapter outcome
                # remains live and must never be cancelled by a duplicate.
                try:
                    return self._await_completed_client_request(
                        session_id=state.session_id,
                        loop_id=state.loop_id,
                        idempotency_key=client_idempotency_key,
                        request_type="insurance_register",
                        request_sha256=request_sha256,
                    )
                except ClaimLoopServiceError as wait_exc:
                    if "identical client request remains in progress" not in str(
                        wait_exc
                    ):
                        raise
                    raise
        if action_receipt is None and allow_execute:
            try:
                action_receipt = adapter.execute(
                    intent=records.intent,
                    staged=records.staged_artifact,
                    executed_at=self._clock(),
                )
                self._protocol_fault("AFTER_ADAPTER_RETURN")
            except Exception as exc:
                try:
                    action_receipt = adapter.status(intent=records.intent)
                except (
                    LocalArtifactRegistryError,
                    TypeError,
                    ValueError,
                ) as status_exc:
                    raise ClaimLoopServiceError(str(status_exc)) from status_exc
                if action_receipt is None:
                    raise ClaimLoopServiceError(
                        "protocol execution failed before a durable effect"
                    ) from exc
            if action_receipt is not None:
                # Adapter execution is an external boundary.  Its durable
                # receipt, not this caller's pre-execution snapshot, is now the
                # authority.  Re-enter from the journal before any append.
                return self._resume_protocol_registration(
                    state=state,
                    records=entries[0][1],
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=allow_reconcile,
                )
        if action_receipt is None:
            # Execution-start with no durable effect is a known precommit state;
            # cancellation wins the same per-effect CAS and prevents blind retry.
            try:
                action_receipt = adapter.cancel(
                    intent=records.intent, cancelled_at=self._clock()
                )
            except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
                try:
                    persisted = adapter.status(intent=records.intent)
                except (
                    LocalArtifactRegistryError,
                    TypeError,
                    ValueError,
                ) as status_exc:
                    raise ClaimLoopServiceError(str(status_exc)) from status_exc
                refreshed, _ = self.store.snapshot(
                    session_id=session_id,
                    loop_id=loop_id,
                )
                if persisted is not None:
                    return self._resume_protocol_registration(
                        state=refreshed,
                        records=entries[0][1],
                        client_idempotency_key=client_idempotency_key,
                        request_sha256=request_sha256,
                        allow_execute=False,
                        allow_reconcile=True,
                    )
                raise ClaimLoopServiceError(str(exc)) from exc
            refreshed, refreshed_events = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
            refreshed_entries = self._protocol_entries(refreshed_events)
            if (
                not refreshed_entries
                or refreshed_entries[-1][0].event_sha256 != latest_event.event_sha256
            ):
                return self._resume_protocol_registration(
                    state=refreshed,
                    records=entries[0][1],
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=allow_reconcile,
                )
            state = refreshed
            records = refreshed_entries[-1][1]
        if action_receipt.status is ActionReceiptStatus.UNKNOWN:
            unknown_records = _protocol_records_with(
                records,
                action_receipt=action_receipt.model_dump(mode="json"),
            )
            state, unknown_command_receipt, _ = self._append_protocol_event(
                state=state,
                records=unknown_records,
                event_type="DISPATCH_UNKNOWN",
                event_kind="dispatch-unknown",
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                timestamp=self._clock(),
            )
            if unknown_command_receipt is None or (
                unknown_command_receipt.revision != state.revision
                or unknown_command_receipt.state_sha256 != state.state_sha256
                or unknown_command_receipt.event_sha256 != state.last_event_sha256
            ):
                return self._resume_protocol_registration(
                    state=state,
                    records=entries[0][1],
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=allow_reconcile,
                )
            records = unknown_records
            response_state, response_events = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
            if (
                response_state.revision != state.revision
                or response_state.state_sha256 != state.state_sha256
                or response_state.last_event_sha256 != state.last_event_sha256
            ):
                return self._resume_protocol_registration(
                    state=response_state,
                    records=entries[0][1],
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=allow_reconcile,
                )
            self._validate_protocol_registry_receipt(
                self._protocol_entries(response_events)
            )
            protocol_projection = self._protocol_projection(
                state=response_state,
                events=response_events,
            ).model_dump(mode="json")
            unknown_response = {
                **self._response(response_state, unknown_command_receipt),
                "protocol_state": protocol_projection,
            }
            confirmed_state, _ = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
            if (
                confirmed_state.revision != response_state.revision
                or confirmed_state.state_sha256 != response_state.state_sha256
                or confirmed_state.last_event_sha256 != response_state.last_event_sha256
            ):
                return self._resume_protocol_registration(
                    state=confirmed_state,
                    records=entries[0][1],
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=allow_reconcile,
                )
            if not allow_reconcile:
                return unknown_response
            try:
                action_receipt = adapter.reconcile(
                    intent=records.intent,
                    staged=records.staged_artifact,
                )
            except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
                raise ClaimLoopServiceError(str(exc)) from exc
            if (
                action_receipt is None
                or action_receipt.status is ActionReceiptStatus.UNKNOWN
            ):
                refreshed, refreshed_events = self.store.snapshot(
                    session_id=session_id,
                    loop_id=loop_id,
                )
                refreshed_entries = self._protocol_entries(refreshed_events)
                if (
                    not refreshed_entries
                    or refreshed_entries[-1][0].event_sha256
                    != unknown_command_receipt.event_sha256
                ):
                    return self._resume_protocol_registration(
                        state=refreshed,
                        records=entries[0][1],
                        client_idempotency_key=client_idempotency_key,
                        request_sha256=request_sha256,
                        allow_execute=False,
                        allow_reconcile=allow_reconcile,
                    )
                return unknown_response
            return self._resume_protocol_registration(
                state=state,
                records=entries[0][1],
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=allow_reconcile,
            )
        if action_receipt.status is ActionReceiptStatus.CANCELLED:
            cancelled_records = _protocol_records_with(
                records,
                action_receipt=action_receipt.model_dump(mode="json"),
            )
            state, receipt, _ = self._append_protocol_event(
                state=state,
                records=cancelled_records,
                event_type="PROTOCOL_INTENT_CANCELLED",
                event_kind="intent-cancelled",
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                timestamp=action_receipt.committed_at or self._clock(),
            )
            if receipt is None:
                return self._resume_protocol_registration(
                    state=state,
                    records=entries[0][1],
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=allow_reconcile,
                )
            response = self._response_with_protocol_prefix(
                state=state,
                receipt=receipt,
            )
            return self._complete_protocol_request(
                state=state,
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                response=response,
            )
        if action_receipt.status is not ActionReceiptStatus.COMMITTED:
            raise ClaimLoopServiceError("protocol action did not commit safely")
        committed_records = _protocol_records_with(
            records,
            action_receipt=action_receipt.model_dump(mode="json"),
        )
        if records.action_receipt is None or (
            records.action_receipt.status is ActionReceiptStatus.UNKNOWN
        ):
            state, action_event_receipt, action_event_replayed = (
                self._append_protocol_event(
                    state=state,
                    records=committed_records,
                    event_type="PROTOCOL_ACTION_RECEIPT_RECORDED",
                    event_kind="action-receipt",
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    timestamp=action_receipt.committed_at or records.intent.created_at,
                )
            )
            if action_event_receipt is not None and not action_event_replayed:
                self._protocol_fault("AFTER_ACTION_RECEIPT")
            return self._resume_protocol_registration(
                state=state,
                records=entries[0][1],
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=allow_reconcile,
            )
        artifact = self.store.tool_artifact_for_dispatch(
            session_id=session_id,
            loop_id=loop_id,
            dispatch_sha256=state.active_dispatch_sha256 or "",
        )
        if artifact is None:
            if latest_event.event_type != "PROTOCOL_ACTION_RECEIPT_RECORDED":
                raise ClaimLoopServiceError(
                    "protocol epistemic stage lacks its registered artifact"
                )
            content = adapter.content(records.staged_artifact)
            # Content retrieval is an external boundary.  If another caller
            # advanced the journal, restart without registering from this
            # caller's older state.
            refreshed, refreshed_events = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
            refreshed_entries = self._protocol_entries(refreshed_events)
            if (
                not refreshed_entries
                or refreshed_entries[-1][0].event_sha256 != latest_event.event_sha256
            ):
                return self._resume_protocol_registration(
                    state=refreshed,
                    records=entries[0][1],
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=allow_reconcile,
                )
            state = refreshed
            tool_result = ToolResult(
                status=ToolResultStatus.OBSERVED,
                sanitized_content=content,
                artifact_source_version=state.record_version,
                artifact_page_count=1,
                source_locator=action_receipt.artifact_uri or "",
            )
            acquisition = self._register_acquisition_result(
                state=state,
                adapter=adapter,
                result=tool_result,
                timestamp=action_receipt.committed_at or records.intent.created_at,
                source_registration=True,
            )
            artifact = self._register_tool_result(state=state, acquisition=acquisition)
        content = artifact.sanitized_content
        if records.source_observation is None:
            source = self._source_observation(
                state=state,
                records=committed_records,
                receipt=action_receipt,
                content=content,
            )
            source_records = _protocol_records_with(
                committed_records,
                source_observation=source.model_dump(mode="json"),
            )
            self._protocol_fault("BEFORE_SOURCE_OBSERVATION")
            state, source_event_receipt, source_event_replayed = (
                self._append_protocol_event(
                    state=state,
                    records=source_records,
                    event_type="PROTOCOL_SOURCE_OBSERVATION_RECORDED",
                    event_kind="source-observation",
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    timestamp=source.observed_at,
                )
            )
            if source_event_receipt is not None and not source_event_replayed:
                self._protocol_fault("AFTER_SOURCE_OBSERVATION")
            return self._resume_protocol_registration(
                state=state,
                records=entries[0][1],
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=allow_reconcile,
            )
        source = records.source_observation
        if records.normalized_assertion is None:
            assertion = self._normalized_assertion(
                source=source,
                artifact=artifact,
            )
            assertion_records = _protocol_records_with(
                records,
                normalized_assertion=assertion.model_dump(mode="json"),
            )
            self._protocol_fault("BEFORE_NORMALIZED_ASSERTION")
            state, assertion_event_receipt, assertion_event_replayed = (
                self._append_protocol_event(
                    state=state,
                    records=assertion_records,
                    event_type="PROTOCOL_ASSERTION_NORMALIZED",
                    event_kind="normalized-assertion",
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    timestamp=source.observed_at,
                )
            )
            if assertion_event_receipt is not None and not assertion_event_replayed:
                self._protocol_fault("AFTER_NORMALIZED_ASSERTION")
            return self._resume_protocol_registration(
                state=state,
                records=entries[0][1],
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=allow_reconcile,
            )
        assertion = records.normalized_assertion
        if records.interpretation is None:
            interpretation = self._interpretation_record(
                state=state, assertion=assertion
            )
            completed_records = _protocol_records_with(
                records,
                interpretation=interpretation.model_dump(mode="json"),
            )
            self._protocol_fault("BEFORE_INTERPRETATION")
            state, interpretation_event_receipt, interpretation_event_replayed = (
                self._append_protocol_event(
                    state=state,
                    records=completed_records,
                    event_type="PROTOCOL_INTERPRETATION_RECORDED",
                    event_kind="interpretation",
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    timestamp=source.observed_at,
                )
            )
            if (
                interpretation_event_receipt is not None
                and not interpretation_event_replayed
            ):
                self._protocol_fault("AFTER_INTERPRETATION")
            return self._resume_protocol_registration(
                state=state,
                records=entries[0][1],
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=allow_reconcile,
            )
        completed_records = records
        thin_waist_lineage = self._thin_waist_replan_intent_v2(
            state=state,
            records=completed_records,
            timestamp=source.observed_at,
        )
        command = self._observation_command(
            state=state,
            artifact=artifact,
        )
        command.update(
            {
                "client_request_type": "insurance_register",
                "client_request_sha256": request_sha256,
                "client_idempotency_key": client_idempotency_key,
                "protocol_record_set_sha256": completed_records.record_set_sha256,
                "insurance_protocol_v1": completed_records.model_dump(mode="json"),
                "thin_waist_record_set_sha256": (thin_waist_lineage.record_set_sha256),
                "insurance_thin_waist_v2": thin_waist_lineage.model_dump(mode="json"),
                "prior_protocol_event_sha256": latest_event.event_sha256,
            }
        )
        staging_binding = self._protocol_staging_binding(
            adapter,
            completed_records.staged_artifact.receipt_sha256,
        )
        if staging_binding is not None:
            command["adapter_staging_binding"] = staging_binding
        try:
            state, receipt, observation_replayed = (
                self.store.append_or_return_protocol_winner(
                    session_id=session_id,
                    loop_id=loop_id,
                    event_type="OBSERVATION_INGESTED",
                    event_kind="result",
                    client_idempotency_key=client_idempotency_key,
                    request_sha256=request_sha256,
                    command=command,
                    timestamp=source.observed_at,
                    expected_revision=state.revision,
                )
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if receipt is None:
            return self._resume_protocol_registration(
                state=state,
                records=entries[0][1],
                client_idempotency_key=client_idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=allow_reconcile,
            )
        if not observation_replayed:
            self._protocol_fault("AFTER_REPLAN_COMMIT_BEFORE_RECEIPT")
        return self._resume_protocol_registration(
            state=state,
            records=entries[0][1],
            client_idempotency_key=client_idempotency_key,
            request_sha256=request_sha256,
            allow_execute=False,
            allow_reconcile=allow_reconcile,
        )

    def _complete_protocol_request(
        self,
        *,
        state: ClaimLoopState,
        client_idempotency_key: str,
        request_sha256: str,
        response: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            return self.store.complete_client_request(
                session_id=state.session_id,
                loop_id=state.loop_id,
                idempotency_key=client_idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
                response=response,
                completed_at=self._clock(),
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc

    def register_protocol_material(
        self,
        *,
        session_id: str,
        loop_id: str,
        proposal_sha256: str,
        staged_artifact_receipt_sha256: str,
        idempotency_key: str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        adapter = self._require_protocol_adapter()
        try:
            staging_binding = self._protocol_staging_binding(
                adapter,
                staged_artifact_receipt_sha256,
            )
        except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        self._raw_state(session_id=session_id, loop_id=loop_id)
        binding = self._bind_client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type="insurance_register",
            request={
                "proposal_sha256": proposal_sha256,
                "staged_artifact_receipt_sha256": (staged_artifact_receipt_sha256),
                "adapter_staging_binding_sha256": (
                    staging_binding.get("receipt_sha256")
                    if staging_binding is not None
                    else None
                ),
                "expected_revision": expected_revision,
            },
        )
        if binding["response"] is not None:
            events = self.store.events(session_id=session_id, loop_id=loop_id)
            self._validate_protocol_registry_receipt(self._protocol_entries(events))
            return deepcopy(binding["response"])
        reserved = binding.get("reserved_state")
        if not isinstance(reserved, ClaimLoopState):
            raise ClaimLoopServiceError("registration request lacks a journal prefix")
        request_sha256 = binding["request_sha256"]
        current, events = self.store.snapshot(
            session_id=session_id,
            loop_id=loop_id,
        )
        dispatch_key = self._internal_event_key(
            session_id=session_id,
            loop_id=loop_id,
            client_idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            request_type="insurance_register",
            event_kind="dispatch",
        )
        dispatch_event = self.store.idempotent_event(
            session_id=session_id, loop_id=loop_id, idempotency_key=dispatch_key
        )
        if dispatch_event is not None:
            state, current_events = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
            current_entries = self._protocol_entries(current_events)
            origin = next(
                records
                for event, records in current_entries
                if event.event_sha256 == dispatch_event.event_sha256
            )
            return self._resume_protocol_registration(
                state=state,
                records=origin,
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                allow_execute=True,
            )
        if current.revision != reserved.revision or (
            expected_revision is not None and expected_revision != reserved.revision
        ):
            raced_dispatch = self.store.idempotent_event(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=dispatch_key,
            )
            if raced_dispatch is not None:
                raced_state = self.state(session_id=session_id, loop_id=loop_id)
                raced_entries = self._protocol_entries(
                    self.store.events(session_id=session_id, loop_id=loop_id)
                )
                raced_origin = next(
                    raced_records
                    for raced_event, raced_records in raced_entries
                    if raced_event.event_sha256 == raced_dispatch.event_sha256
                )
                return self._resume_protocol_registration(
                    state=raced_state,
                    records=raced_origin,
                    client_idempotency_key=idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=True,
                )
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
                detail="registration reservation prefix changed before intent",
            )
        prefix_events = events[: reserved.revision]
        proposal = build_verified_neutral_assessment_proposal_v1(
            state=reserved,
            journal_events=prefix_events,
        )
        if proposal.proposal_sha256 != proposal_sha256:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
                detail="proof-carrying proposal is stale or substituted",
            )
        try:
            staged = adapter.staged(staged_artifact_receipt_sha256)
        except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
                detail=f"staged artifact authority rejected: {exc}",
            )
        decided_at = binding["created_at"]
        effective_until = (
            datetime.fromisoformat(decided_at.replace("Z", "+00:00"))
            + timedelta(seconds=self.DISPATCH_LEASE_SECONDS)
        ).isoformat()
        try:
            records = build_registration_authority_v1(
                state=reserved,
                proposal=proposal,
                staged=staged,
                adapter=adapter,
                decided_at=decided_at,
                effective_until=effective_until,
                source_journal_events=prefix_events,
            )
        except (InsuranceProtocolAuthorityError, LocalArtifactRegistryError) as exc:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
                detail=f"registration authority rejected: {exc}",
            )
        validate_content = getattr(self.artifact_interpreter, "validate_content", None)
        if not callable(validate_content):
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
                detail=(
                    "configured artifact interpreter exposes no admission validator"
                ),
            )
        try:
            validate_content(
                action=records.decision.compatibility_action,
                state=reserved,
                content=adapter.content(staged),
            )
        except (
            ClaimLoopError,
            LocalArtifactRegistryError,
            TypeError,
            ValueError,
        ) as exc:
            self._supersede_client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
                detail=f"typed evidence registration rejected: {exc}",
            )
        if staging_binding is not None:
            mapped_event = staging_binding.get("mapped_event")
            if not isinstance(mapped_event, Mapping) or (
                mapped_event.get("action_id")
                != records.decision.compatibility_action.action_id
                or mapped_event.get("action_sha256")
                != records.decision.compatibility_action.action_sha256
            ):
                raise ClaimLoopServiceError(
                    "factual-history stage is bound to another action"
                )
        result_key = self._internal_event_key(
            session_id=session_id,
            loop_id=loop_id,
            client_idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            request_type="insurance_register",
            event_kind="result",
        )
        try:
            started_at, expires_at, generation = self.store.bind_client_dispatch(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
                dispatch_idempotency_key=dispatch_key,
                started_at=decided_at,
                expires_at=effective_until,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        lease_owner = "insurance-register." + digest_value(
            {
                "session_id": session_id,
                "loop_id": loop_id,
                "intent_sha256": records.intent.intent_sha256,
            }
        )
        command = {
            "action_id": records.decision.compatibility_action.action_id,
            "action_sha256": records.decision.compatibility_action.action_sha256,
            "adapter_id": adapter.adapter_id,
            "lease_owner": lease_owner,
            "lease_expires_at": expires_at,
            "client_request_type": "insurance_register",
            "client_request_sha256": request_sha256,
            "client_idempotency_key": idempotency_key,
            "client_result_idempotency_key": result_key,
            "client_dispatch_idempotency_key": dispatch_key,
            "dispatch_generation": generation,
            "protocol_record_set_sha256": records.record_set_sha256,
            "insurance_protocol_v1": records.model_dump(mode="json"),
        }
        if staging_binding is not None:
            command["adapter_staging_binding"] = staging_binding
        try:
            state, dispatch_receipt, _ = self.store.append_or_return_protocol_winner(
                session_id=session_id,
                loop_id=loop_id,
                event_type="ACTION_DISPATCH_STARTED",
                event_kind="dispatch",
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                command=command,
                timestamp=started_at,
                expected_revision=reserved.revision,
                client_dispatch_guard={
                    "client_idempotency_key": idempotency_key,
                    "request_type": "insurance_register",
                    "request_sha256": request_sha256,
                    "dispatch_started_at": started_at,
                    "dispatch_expires_at": expires_at,
                    "dispatch_generation": generation,
                },
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if dispatch_receipt is None:
            raise ClaimLoopServiceError(
                "registration prefix changed before intent election"
            )
        self._protocol_fault("AFTER_INTENT_JOURNAL")
        return self._resume_protocol_registration(
            state=state,
            records=records,
            client_idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            # The execution-start journal event, not dispatch replay, elects
            # the one caller permitted to invoke the adapter.
            allow_execute=True,
        )

    def reconcile_protocol_intent(
        self,
        *,
        session_id: str,
        loop_id: str,
        intent_sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self._assert_session_authority(session_id)
        state, events = self.store.snapshot(session_id=session_id, loop_id=loop_id)
        entries = self._protocol_entries(events)
        if not entries:
            raise ClaimLoopServiceError("insurance intent does not exist")
        origin_event, records = entries[0]
        if records.intent.intent_sha256 != intent_sha256:
            raise ClaimLoopServiceError("insurance intent identity changed")
        parent_key = origin_event.command.get("client_idempotency_key")
        request_sha256 = origin_event.command.get("client_request_sha256")
        if idempotency_key != parent_key or not isinstance(request_sha256, str):
            raise ClaimLoopServiceError(
                "reconciliation requires the original idempotency key"
            )
        return self._resume_protocol_registration(
            state=state,
            records=records,
            client_idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            allow_execute=False,
            allow_reconcile=True,
        )

    def cancel_protocol_intent(
        self,
        *,
        session_id: str,
        loop_id: str,
        intent_sha256: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Cancel the original intent only while the effect CAS is unclaimed."""

        self._assert_session_authority(session_id)
        adapter = self._require_protocol_adapter()
        state, events = self.store.snapshot(session_id=session_id, loop_id=loop_id)
        entries = self._protocol_entries(events)
        if not entries:
            raise ClaimLoopServiceError("insurance intent does not exist")
        origin_event, origin_records = entries[0]
        if origin_records.intent.intent_sha256 != intent_sha256:
            raise ClaimLoopServiceError("insurance intent identity changed")
        parent_key = origin_event.command.get("client_idempotency_key")
        request_sha256 = origin_event.command.get("client_request_sha256")
        if idempotency_key != parent_key or not isinstance(request_sha256, str):
            raise ClaimLoopServiceError(
                "cancellation requires the original idempotency key"
            )
        try:
            parent_request = self.store.client_request(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                request_type="insurance_register",
                request_sha256=request_sha256,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        if parent_request.get("response") is not None:
            return deepcopy(parent_request["response"])
        latest_event, _ = entries[-1]
        try:
            existing_receipt = adapter.status(intent=origin_records.intent)
        except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        refreshed, refreshed_events = self.store.snapshot(
            session_id=session_id,
            loop_id=loop_id,
        )
        refreshed_entries = self._protocol_entries(refreshed_events)
        if (
            not refreshed_entries
            or refreshed_entries[-1][0].event_sha256 != latest_event.event_sha256
        ):
            return self.cancel_protocol_intent(
                session_id=session_id,
                loop_id=loop_id,
                intent_sha256=intent_sha256,
                idempotency_key=idempotency_key,
            )
        state = refreshed
        events = refreshed_events
        entries = refreshed_entries
        latest_event, _ = entries[-1]
        if latest_event.event_type == "OBSERVATION_INGESTED" or (
            existing_receipt is not None
            and existing_receipt.status is ActionReceiptStatus.COMMITTED
        ):
            if latest_event.event_type != "OBSERVATION_INGESTED":
                return self._resume_protocol_registration(
                    state=state,
                    records=origin_records,
                    client_idempotency_key=idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=True,
                )
            return {
                **self._response(state, None),
                "cancellation_outcome": "commit_preserved",
                "protocol_state": self._protocol_projection(
                    state=state, events=events
                ).model_dump(mode="json"),
            }
        if latest_event.event_type == "PROTOCOL_INTENT_CANCELLED":
            response = {
                **self._response(state, None),
                "cancellation_outcome": "cancelled",
                "protocol_state": self._protocol_projection(
                    state=state, events=events
                ).model_dump(mode="json"),
            }
            return self._complete_protocol_request(
                state=state,
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                response=response,
            )
        if existing_receipt is not None:
            if existing_receipt.status is ActionReceiptStatus.UNKNOWN:
                return self._resume_protocol_registration(
                    state=state,
                    records=origin_records,
                    client_idempotency_key=idempotency_key,
                    request_sha256=request_sha256,
                    allow_execute=False,
                    allow_reconcile=True,
                )
            raise ClaimLoopServiceError("insurance intent cannot be cancelled")
        if latest_event.event_type == "PROTOCOL_EXECUTION_STARTED":
            try:
                current = datetime.fromisoformat(self._clock().replace("Z", "+00:00"))
                expires = datetime.fromisoformat(
                    origin_records.intent.expires_at.replace("Z", "+00:00")
                )
            except (AttributeError, ValueError) as exc:
                raise ClaimLoopServiceError(
                    "insurance intent expiry is invalid"
                ) from exc
            if current < expires:
                raise ClaimLoopServiceError(
                    "insurance intent execution is still in progress"
                )
        cancelled_at = self._clock()
        try:
            receipt = adapter.cancel(
                intent=origin_records.intent,
                cancelled_at=cancelled_at,
            )
        except (LocalArtifactRegistryError, TypeError, ValueError) as exc:
            try:
                persisted = adapter.status(intent=origin_records.intent)
            except (LocalArtifactRegistryError, TypeError, ValueError) as status_exc:
                raise ClaimLoopServiceError(str(status_exc)) from status_exc
            if persisted is None:
                raise ClaimLoopServiceError(str(exc)) from exc
            refreshed, _ = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
            return self._resume_protocol_registration(
                state=refreshed,
                records=origin_records,
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=True,
            )
        refreshed, refreshed_events = self.store.snapshot(
            session_id=session_id,
            loop_id=loop_id,
        )
        refreshed_entries = self._protocol_entries(refreshed_events)
        if (
            not refreshed_entries
            or refreshed_entries[-1][0].event_sha256 != latest_event.event_sha256
        ):
            return self._resume_protocol_registration(
                state=refreshed,
                records=origin_records,
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=True,
            )
        state = refreshed
        if receipt.status is not ActionReceiptStatus.CANCELLED:
            return self._resume_protocol_registration(
                state=state,
                records=origin_records,
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=True,
            )
        cancelled_records = _protocol_records_with(
            origin_records,
            action_receipt=receipt.model_dump(mode="json"),
        )
        state, command_receipt, _ = self._append_protocol_event(
            state=state,
            records=cancelled_records,
            event_type="PROTOCOL_INTENT_CANCELLED",
            event_kind="intent-cancelled",
            client_idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            timestamp=cancelled_at,
        )
        if command_receipt is None:
            return self._resume_protocol_registration(
                state=state,
                records=origin_records,
                client_idempotency_key=idempotency_key,
                request_sha256=request_sha256,
                allow_execute=False,
                allow_reconcile=True,
            )
        response = self._response_with_protocol_prefix(
            state=state,
            receipt=command_receipt,
            additions={"cancellation_outcome": "cancelled"},
        )
        return self._complete_protocol_request(
            state=state,
            client_idempotency_key=idempotency_key,
            request_sha256=request_sha256,
            response=response,
        )

    @staticmethod
    def packet_from_state(state: ClaimLoopState) -> dict[str, Any]:
        try:
            return decision_ready_packet(state).model_dump(mode="json")
        except (TypeError, ValueError) as exc:
            raise ClaimLoopServiceError(
                "claim loop has not reached a terminal decision packet"
            ) from exc

    @staticmethod
    def audit_from_snapshot(
        *,
        state: ClaimLoopState,
        events: Sequence[Any],
    ) -> dict[str, Any]:
        if (
            not events
            or len(events) != state.revision
            or events[-1].event_sha256 != state.last_event_sha256
            or events[-1].resulting_state_sha256 != state.state_sha256
        ):
            raise ClaimLoopServiceError(
                "claim loop audit inputs are not one journal prefix"
            )
        upstream_activity = state.upstream_source_run_activity.model_dump(mode="json")
        source_activity = state.source_acceptance_activity.model_dump(mode="json")
        incremental_activity = state.incremental_loop_activity.model_dump(mode="json")
        total_activity = state.total_bound_activity.model_dump(mode="json")
        credential_status = total_activity["credential_access_status"]
        payload = {
            "contract": "casepath.claim-loop-audit/1.0.0",
            "loop_id": state.loop_id,
            "state_sha256": state.state_sha256,
            "event_sha256s": [value.event_sha256 for value in events],
            "event_count": len(events),
            "last_event_sha256": state.last_event_sha256,
            "upstream_source_run_activity": upstream_activity,
            "source_acceptance_activity": source_activity,
            "incremental_loop_activity": incremental_activity,
            "total_bound_activity": total_activity,
            "model_calls": total_activity["model_calls"],
            "provider_calls": total_activity["provider_calls"],
            "provider_credentials_read": (
                False
                if credential_status == "none_due_to_zero_provider_calls"
                else True
                if credential_status == "receipt_bound"
                else None
            ),
            "credential_access_status": credential_status,
            "cost_status": total_activity["cost_status"],
            "cost_usd": total_activity["cost_usd"],
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    def packet(self, *, session_id: str, loop_id: str) -> dict[str, Any]:
        state = self.state(session_id=session_id, loop_id=loop_id)
        return self.packet_from_state(state)

    def audit(self, *, session_id: str, loop_id: str) -> dict[str, Any]:
        # First reconcile any already-durable external outcome, then bind the
        # public audit to one atomic state/event snapshot.
        self.state(session_id=session_id, loop_id=loop_id)
        try:
            state, events = self.store.snapshot(
                session_id=session_id,
                loop_id=loop_id,
            )
        except ClaimLoopStoreError as exc:
            raise ClaimLoopServiceError(str(exc)) from exc
        return self.audit_from_snapshot(state=state, events=events)


__all__ = ["ClaimLoopService", "ClaimLoopServiceError"]
