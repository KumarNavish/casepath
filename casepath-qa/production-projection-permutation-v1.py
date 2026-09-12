#!/usr/bin/env python3
"""Sealed, read-only identity-permutation probe for the production projector.

The probe rebuilds an unseen, claim-shaped copy of both authoritative journals
entirely in memory. It supports the complete four-event Gate-2 seam plus the two
explicitly authorized Gate-1 carryover prefixes. New event topologies must gain
an explicit identity transformer and declared scope before they can be claimed
as permutation evidence.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
import platform
import re
import sys
from types import ModuleType
from typing import Any, Mapping, Sequence


# Install before importing any production package. The child is also launched
# with PYTHONDONTWRITEBYTECODE=1, but this hook is the fail-closed boundary.
_WRITE_OPEN_FLAGS = 0
for _flag_name in ("O_WRONLY", "O_RDWR", "O_APPEND", "O_CREAT", "O_TRUNC", "O_EXCL"):
    _WRITE_OPEN_FLAGS |= int(getattr(os, _flag_name, 0))

_DENIED_AUDIT_EVENTS = frozenset(
    {
        "sqlite3.connect", "sqlite3.connect/handle", "subprocess.Popen",
        "os.system", "os.fork", "os.forkpty", "os.posix_spawn",
        "os.posix_spawnp", "pty.spawn", "socket.__new__", "socket.bind",
        "socket.connect", "socket.connect_ex", "socket.getaddrinfo",
        "socket.gethostbyaddr", "socket.gethostbyname", "socket.gethostbyname_ex",
        "socket.sendto", "os.remove", "os.unlink", "os.rename", "os.replace",
        "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.truncate",
        "os.fchmod", "os.fchown", "os.lchown", "os.mknod", "os.mkfifo",
        "os.utime", "os.link", "os.symlink", "os.setxattr", "os.removexattr",
        "shutil.copyfile", "shutil.copymode", "shutil.copystat",
        "shutil.copytree", "shutil.move", "shutil.rmtree", "shutil.chown",
    }
)
_DENIED_AUDIT_PREFIXES = ("os.exec",)
_DENIED_ATTEMPTS = 0
_DENIED_EVENT_COUNTS: dict[str, int] = {}


def _audit(event: str, args: tuple[Any, ...]) -> None:
    global _DENIED_ATTEMPTS
    denied = event in _DENIED_AUDIT_EVENTS or event.startswith(_DENIED_AUDIT_PREFIXES)
    if event == "open":
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        denied = (
            isinstance(mode, str)
            and any(marker in mode for marker in ("w", "a", "x", "+"))
        ) or (isinstance(flags, int) and bool(flags & _WRITE_OPEN_FLAGS))
    if denied:
        _DENIED_ATTEMPTS += 1
        _DENIED_EVENT_COUNTS[event] = _DENIED_EVENT_COUNTS.get(event, 0) + 1
        raise RuntimeError(f"projection permutation probe denied audit event {event}")


sys.addaudithook(_audit)
_AUDIT_INSTALLED_BEFORE_PRODUCTION_IMPORTS = True


# Production imports intentionally occur below the audit boundary.
from casepath_api.claim_loop import (  # noqa: E402
    StructuredMouldArtifactInterpreterV2,
    accepted_artifacts_from_run,
    bound_activity_from_cycle_receipt_v1,
    build_claim_loop_gate_receipt_v1,
    project_claim_loop_artifacts_v1,
    reduce_claim_loop_event,
)
from casepath_api.claim_loop_contracts import (  # noqa: E402
    AcquisitionReceiptV1,
    BoundActivity,
    ClaimLoopState,
    ProjectionLedgerEntry,
    ToolArtifactReceipt,
    claim_loop_internal_event_key_v1,
    load_claim_loop_event_v1,
)
from casepath_api.claim_loop_cycle import (  # noqa: E402
    build_six_agent_cycle_receipt_v1,
    derive_graph_activity_v1,
)
from casepath_api.foundation.common import digest_text, digest_value  # noqa: E402
from casepath_api.multi_agent import (  # noqa: E402
    DeterministicStructuredAgent,
    NemotronMultiAgentOrchestrator,
)
from casepath_api.pipeline_v15 import (  # noqa: E402
    ClaimPipeline,
    DETERMINISTIC_PROFILE,
    ORCHESTRATOR,
    RELEASE,
)
from casepath_api.playbook_materializer import (  # noqa: E402
    build_template_cycle_verification_v1,
    materialize_template_cycle_v1,
)
from casepath_api.playbook_template import PlaybookTemplate  # noqa: E402
from casepath_api.workspace_claim_loop_v1 import (  # noqa: E402
    WorkspaceStructuredEvidenceInterpreterV1,
)
from casepath_api.workspace_evidence_authority_v1 import (  # noqa: E402
    _EvidenceSemantics as FixedSourceSpanEvidenceSemantics,
    _module_sha256 as fixed_source_span_module_sha256,
)
from casepath_api.workspace_evidence_independent_authority_v1 import (  # noqa: E402
    IndependentWorkspaceEvidenceAuthorityV1,
    _finding as independent_fixed_source_finding,
    _module_sha256 as independent_authority_module_sha256,
)
from casepath_api.workspace_operational_projection_v1 import (  # noqa: E402
    derive_workspace_operational_projection_v1,
)


_CLAIM_RE = re.compile(r"clm_[0-9a-f]{16}\Z")
_SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
_PREFIXED_DIGEST_RE = re.compile(
    r"(?:action|claim-loop-worker|cycle-canonical|declarative-source|loop|"
    r"observation|record|run_source|source-ref|tool-artifact)\.[0-9a-f]{32,64}\Z"
)
_OPAQUE_ID_RE = re.compile(r"[a-z][a-z0-9_.-]*[._][0-9a-f]{16,64}\Z")
_INPUT_KEYS = frozenset(
    {
        "claim_id", "alias_claim_id", "alias_nonce_sha256", "permutation_scope",
        "forbidden_identity_values", "workspace_state", "workspace_events",
        "loop_events", "loop_journal_prefix", "expected_original_projection",
        "independent_replay_receipt",
    }
)
_CHILD_ENV_REQUIRED = frozenset(
    {
        "HOME", "LANG", "LC_ALL", "PATH", "PYTHONHASHSEED",
        "PYTHONNOUSERSITE", "PYTHONSAFEPATH", "PYTHONDONTWRITEBYTECODE", "TZ",
    }
)
_CHILD_ENV_PLATFORM_OPTIONAL = frozenset({"__CF_USER_TEXT_ENCODING"})
_WORKSPACE_EVENT_KEYS = frozenset(
    {
        "contract", "session_id", "loop_id", "sequence",
        "previous_event_sha256", "event_type", "idempotency_key",
        "command_sha256", "command", "created_at", "event_sha256",
        "resulting_state_sha256",
    }
)
_ADMITTED_LOOP_EVENT_TYPES = (
    "LOOP_CREATED", "ACTION_SELECTED", "ACTION_DISPATCH_STARTED",
    "OBSERVATION_INGESTED",
)
_SELECTED_LOOP_EVENT_TYPES = ("LOOP_CREATED", "ACTION_SELECTED")
_WORKSPACE_EVENT_TYPES = (
    "WORKSPACE_CLAIM_IMPORTED", "WORKSPACE_PROCESSING_STARTED",
)
_PROJECTION_KEYS = frozenset(
    {
        "contract", "claim_id", "workspace_prefix", "claim_loop_prefix",
        "current_process", "controlling_decision", "evidence_items",
        "evidence_class_counts", "workflow_state", "readiness_state",
        "principal_blocker", "pending_evidence_count", "next_state",
        "failure_or_unknown_effect", "last_authoritative_update",
        "projection_sha256",
    }
)
_EXTERNAL_IDENTITY_CATEGORIES = {
    "session_id": "execution_namespace", "created_at": "journal_time",
    "last_authoritative_update": "journal_time", "received_at": "source_time",
    "registered_at": "source_time", "acquired_at": "source_time",
    "lease_expires_at": "lease_time", "message_id": "source_asset",
    "artifact_id": "source_or_semantic_asset", "parent_artifact_id": "source_asset",
    "fact_id": "playbook_semantics", "evidence_item_id": "playbook_semantics",
    "obligation_id": "playbook_semantics", "node_id": "playbook_semantics",
    "action_id": "playbook_semantics", "action_sha256": "playbook_semantics",
    "adapter_id": "runtime_implementation", "implementation": "runtime_implementation",
    "implementation_id": "runtime_implementation",
    "implementation_source_sha256": "runtime_implementation",
    "adapter_implementation_id": "runtime_implementation",
    "adapter_implementation_source_sha256": "runtime_implementation",
    "adapter_implementation_sha256": "runtime_implementation",
    "static_template_sha256": "public_corpus_snapshot",
    "source_registry_sha256": "public_corpus_snapshot",
    "source_registry_file_sha256": "public_corpus_snapshot",
    "claim_file_sha256": "source_asset", "source_sha256": "source_asset",
    "artifact_sha256": "source_asset", "raw_bytes_sha256": "source_asset",
    "sanitized_content_sha256": "source_asset", "span_sha256": "source_asset",
    "raw_artifact_sha256": "dependent_receipt",
    "client_idempotency_key": "caller_request",
    "advance_request_sha256": "caller_request",
    "client_request_sha256": "caller_request",
}
_EXTERNAL_CATEGORY_REASONS = {
    "caller_request": "caller-owned idempotency/request identity is outside claim renaming",
    "dependent_receipt": "receipt binds unchanged source bytes rather than claim identity",
    "execution_namespace": "the sealed replay preserves the production session namespace",
    "journal_time": "the copied journal preserves authoritative event time",
    "lease_time": "the copied dispatch preserves the authoritative lease interval",
    "playbook_semantics": "public playbook fact, obligation, node, or action semantics are claim-independent",
    "public_corpus_snapshot": "immutable public-corpus snapshot identity is not fabricated for the unseen alias",
    "runtime_implementation": "adapter/runtime implementation identity is installed code authority",
    "semantic_or_source_identity": "byte-identical production replay proves this opaque identity is claim-independent in the compared structure",
    "source_asset": "admitted source bytes and their content identities are intentionally unchanged",
    "source_or_semantic_asset": "artifact identity belongs to unchanged admitted bytes or public semantics",
    "source_time": "the copied source preserves its authoritative acquisition time",
}


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _self_hash(value: Mapping[str, Any], field: str) -> str:
    return digest_value({key: item for key, item in value.items() if key != field})


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks a timezone")
    return parsed


def _replace_claim(value: Any, claim_id: str, alias: str) -> Any:
    if isinstance(value, str):
        return value.replace(claim_id, alias)
    if isinstance(value, list):
        return [_replace_claim(item, claim_id, alias) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_claim(item, claim_id, alias) for item in value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, item in value.items():
            key = raw_key.replace(claim_id, alias) if isinstance(raw_key, str) else raw_key
            if key in result:
                raise ValueError("claim rename collides in a mapping")
            result[key] = _replace_claim(item, claim_id, alias)
        return result
    return value


def _occurrence_paths(value: Any, token: str, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, str):
        if token in value:
            paths.append(path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(_occurrence_paths(item, token, f"{path}/{index}"))
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and token in key:
                paths.append(f"{path}/@key:{key}")
            paths.extend(_occurrence_paths(item, token, f"{path}/{key}"))
    return paths


def _require_absent_identity(value: Any, identity: str, label: str) -> None:
    paths = _occurrence_paths(value, identity)
    if paths:
        raise ValueError(
            f"{label} retains identity {identity} at {len(paths)} structural paths"
        )


def _alias_for(claim_id: str, nonce_sha256: str) -> str:
    return "clm_" + digest_value(
        {
            "contract": "casepath.projection-permutation-alias/1.0.0",
            "claim_id": claim_id,
            "alias_nonce_sha256": nonce_sha256,
        }
    )[:16]


def _validate_identity_inputs(value: Mapping[str, Any]) -> tuple[str, str, list[str]]:
    if set(value) != _INPUT_KEYS:
        raise ValueError("projection permutation input field set is not closed")
    claim_id = value.get("claim_id")
    alias = value.get("alias_claim_id")
    nonce = value.get("alias_nonce_sha256")
    forbidden = value.get("forbidden_identity_values")
    permutation_scope = value.get("permutation_scope")
    if (
        not isinstance(claim_id, str) or _CLAIM_RE.fullmatch(claim_id) is None
        or not isinstance(alias, str) or _CLAIM_RE.fullmatch(alias) is None
        or not isinstance(nonce, str) or _SHA_RE.fullmatch(nonce) is None
        or alias != _alias_for(claim_id, nonce) or claim_id == alias
        or not isinstance(forbidden, list) or not forbidden
        or any(not isinstance(item, str) or _CLAIM_RE.fullmatch(item) is None for item in forbidden)
        or len(forbidden) != len(set(forbidden)) or claim_id not in forbidden
        or alias in forbidden
        or permutation_scope not in {
            "complete_four_event_gate2_seam",
            "gate1_pre_rejection_selected_prefix_plus_zero_effect_rejection_proof",
            "gate1_first_admitted_seam_prefix_plus_full_terminal_replay",
        }
    ):
        raise ValueError("claim permutation identity or forbidden roster is invalid")
    corpus_count = (
        value.get("workspace_events", [{}])[0].get("command", {})
        .get("corpus_identity", {}).get("claim_count")
        if isinstance(value.get("workspace_events"), list) and value.get("workspace_events")
        else None
    )
    if corpus_count != len(forbidden):
        raise ValueError("forbidden identity roster does not cover the public corpus")
    return claim_id, alias, forbidden


def _workspace_event_material(event: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in event.items()
            if key not in {"event_sha256", "resulting_state_sha256"}}


def _workspace_state(material: Mapping[str, Any]) -> dict[str, Any]:
    copied = _copy(material)
    return {**copied, "state_sha256": digest_value(copied)}


def _reduce_workspace_independent(
    current: Mapping[str, Any] | None,
    event: Mapping[str, Any],
    claim_id: str,
) -> dict[str, Any]:
    command = event["command"]
    sequence = event["sequence"]
    event_type = event["event_type"]
    if current is None:
        if event_type != "WORKSPACE_CLAIM_IMPORTED" or sequence != 1:
            raise ValueError("workspace journal does not begin with import")
        if set(command) != {"binding", "corpus_identity", "request_expected_revision"}:
            raise ValueError("workspace import command field set differs")
        binding = command.get("binding")
        if (
            not isinstance(binding, Mapping) or binding.get("claim_id") != claim_id
            or binding.get("binding_sha256") != _self_hash(binding, "binding_sha256")
            or command.get("request_expected_revision") != 0
            or binding.get("static_template_sha256")
            != command.get("corpus_identity", {}).get("static_template_sha256")
        ):
            raise ValueError("workspace import binding is invalid")
        return _workspace_state(
            {
                "contract": "casepath.claim-workspace-state/1.0.0",
                "claim_id": claim_id, "loop_id": f"workspace.{claim_id}",
                "binding": binding,
                "static_template_sha256": binding["static_template_sha256"],
                "intake_assessment": None, "owner": None,
                "workflow_state": "received", "readiness_state": "not_assessed",
                "claim_type": "unclassified_intake", "deadline_at": None,
                "principal_blocker": "Deterministic assessment has not started",
                "pending_evidence_count": None,
                "next_safe_action": "Start deterministic assessment",
                "failure_or_unknown_effect": False, "revision": 1,
                "last_event_sha256": event["event_sha256"],
                "last_authoritative_update": event["created_at"],
            }
        )
    if sequence != current.get("revision", 0) + 1:
        raise ValueError("workspace event sequence is discontinuous")
    if command.get("request_expected_revision") != current["revision"]:
        raise ValueError("workspace command is not parent-revision bound")
    material = {key: item for key, item in current.items() if key != "state_sha256"}
    material.update(
        {"revision": sequence, "last_event_sha256": event["event_sha256"],
         "last_authoritative_update": event["created_at"]}
    )
    if event_type == "WORKSPACE_OWNER_ASSIGNED":
        if set(command) != {"owner", "request_expected_revision"}:
            raise ValueError("workspace owner command differs")
        material["owner"] = command["owner"].strip()
    elif event_type == "WORKSPACE_PROCESSING_STARTED":
        if set(command) != {"expected_binding_sha256", "intake_assessment",
                            "request_expected_revision"} or command.get(
            "expected_binding_sha256"
        ) != current["binding"]["binding_sha256"]:
            raise ValueError("workspace processing command is stale")
        assessment = command.get("intake_assessment")
        if (
            not isinstance(assessment, Mapping) or assessment.get("claim_id") != claim_id
            or assessment.get("binding_sha256") != current["binding"]["binding_sha256"]
            or assessment.get("assessment_sha256") != _self_hash(assessment, "assessment_sha256")
        ):
            raise ValueError("workspace assessment is not self- and claim-bound")
        node = assessment.get("current_node")
        if not isinstance(node, Mapping) or not isinstance(node.get("label"), str):
            raise ValueError("workspace current assessment node is invalid")
        material.update(
            {"workflow_state": "in_review", "readiness_state": "blocked",
             "claim_type": assessment["claim_type"], "intake_assessment": assessment,
             "principal_blocker": f"{node['label']} is not yet established from admitted evidence",
             "next_safe_action": node["label"]}
        )
    elif event_type == "WORKSPACE_UNKNOWN_RECONCILED":
        if set(command) != {"prior_state_sha256", "request_expected_revision"}:
            raise ValueError("workspace reconciliation command differs")
        if command.get("prior_state_sha256") != current["state_sha256"]:
            raise ValueError("workspace reconciliation is not parent-state bound")
        material.update(
            {"failure_or_unknown_effect": False, "workflow_state": "waiting",
             "principal_blocker": "Unknown effect reconciled; review required",
             "next_safe_action": "Resume deterministic assessment"}
        )
    else:
        raise ValueError(f"unsupported workspace event type {event_type}")
    return _workspace_state(material)


def _replay_workspace(events: Sequence[Mapping[str, Any]], claim_id: str) -> dict[str, Any]:
    if not events:
        raise ValueError("workspace raw event roster is absent")
    state: dict[str, Any] | None = None
    previous: str | None = None
    for expected_sequence, event in enumerate(events, start=1):
        if (
            not isinstance(event, Mapping) or set(event) != _WORKSPACE_EVENT_KEYS
            or event.get("contract") != "casepath.claim-workspace-journal-event/1.0.0"
            or event.get("session_id") != "casepath-workspace-local"
            or event.get("loop_id") != f"workspace.{claim_id}"
            or event.get("sequence") != expected_sequence
            or event.get("previous_event_sha256") != previous
            or event.get("command_sha256") != digest_value(event.get("command"))
            or event.get("event_sha256") != digest_value(_workspace_event_material(event))
        ):
            raise ValueError("workspace raw event envelope is invalid")
        _timestamp(event["created_at"])
        state = _reduce_workspace_independent(state, event, claim_id)
        if state["state_sha256"] != event.get("resulting_state_sha256"):
            raise ValueError("workspace independent replay differs from event state")
        previous = event["event_sha256"]
    assert state is not None
    return state


def _append_workspace_event(
    state: Mapping[str, Any] | None, original: Mapping[str, Any], *,
    claim_id: str, idempotency_key: str, command: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    material = {
        "contract": "casepath.claim-workspace-journal-event/1.0.0",
        "session_id": "casepath-workspace-local", "loop_id": f"workspace.{claim_id}",
        "sequence": original["sequence"],
        "previous_event_sha256": None if state is None else state["last_event_sha256"],
        "event_type": original["event_type"], "idempotency_key": idempotency_key,
        "command_sha256": digest_value(command), "command": _copy(command),
        "created_at": original["created_at"],
    }
    event_sha256 = digest_value(material)
    provisional = {**material, "event_sha256": event_sha256,
                   "resulting_state_sha256": "0" * 64}
    next_state = _reduce_workspace_independent(state, provisional, claim_id)
    event = {**material, "event_sha256": event_sha256,
             "resulting_state_sha256": next_state["state_sha256"]}
    return next_state, event


def _permuted_workspace(
    events: Sequence[Mapping[str, Any]], *, claim_id: str, alias: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if tuple(event.get("event_type") for event in events) != _WORKSPACE_EVENT_TYPES:
        raise ValueError("Gate-2 workspace event topology changed")
    binding = _replace_claim(events[0]["command"]["binding"], claim_id, alias)
    binding["binding_sha256"] = _self_hash(binding, "binding_sha256")
    assessment = _replace_claim(events[1]["command"]["intake_assessment"], claim_id, alias)
    assessment["claim_id"] = alias
    assessment["binding_sha256"] = binding["binding_sha256"]
    assessment["assessment_sha256"] = _self_hash(assessment, "assessment_sha256")
    commands = (
        {"binding": binding,
         # Immutable public-corpus snapshot authority is external, not fabricated.
         "corpus_identity": _copy(events[0]["command"]["corpus_identity"]),
         "request_expected_revision": 0},
        {"expected_binding_sha256": binding["binding_sha256"],
         "intake_assessment": assessment, "request_expected_revision": 1},
    )
    keys = (f"seed.{binding['binding_sha256']}",
            _replace_claim(events[1]["idempotency_key"], claim_id, alias))
    state: dict[str, Any] | None = None
    transformed: list[dict[str, Any]] = []
    for original, key, command in zip(events, keys, commands, strict=True):
        state, event = _append_workspace_event(
            state, original, claim_id=alias, idempotency_key=key, command=command
        )
        transformed.append(event)
    assert state is not None
    return state, transformed


def _replay_loop(events: Sequence[Mapping[str, Any]], claim_id: str) -> ClaimLoopState:
    if not events:
        raise ValueError("raw ClaimLoop event roster is absent")
    state: ClaimLoopState | None = None
    previous: str | None = None
    for expected_sequence, event_value in enumerate(events, start=1):
        event = load_claim_loop_event_v1(dict(event_value))
        if (
            event.sequence != expected_sequence
            or event.previous_event_sha256 != previous
            or event.loop_id != events[0]["loop_id"]
            or event.session_id != events[0]["session_id"]
        ):
            raise ValueError("ClaimLoop raw event prefix is discontinuous")
        state = reduce_claim_loop_event(
            state,
            event_type=event.event_type,
            command=event.command,
            sequence=event.sequence,
            event_sha256=event.event_sha256,
            timestamp=event.created_at,
        )
        if state.state_sha256 != event.resulting_state_sha256:
            raise ValueError("production ClaimLoop replay differs from event state")
        previous = event.event_sha256
    assert state is not None
    if state.claim_id != claim_id:
        raise ValueError("ClaimLoop replay belongs to another claim")
    return state


def _pipeline_for(template: PlaybookTemplate) -> ClaimPipeline:
    graph = NemotronMultiAgentOrchestrator(
        None,
        agent_runner=DeterministicStructuredAgent(),
        playbook_template=template,
    )
    return ClaimPipeline(
        None,
        model_mode="deterministic_reference",
        agent_orchestrator=graph,
        playbook_template=template,
        pace_seconds=0,
    )


def _run_cycle(
    *,
    template: PlaybookTemplate,
    source_run_id: str,
    orchestration_id: str,
    observable_package: Mapping[str, Any],
    facts: Sequence[Mapping[str, Any]],
    process: Mapping[str, Any],
    checklist: Mapping[str, Any],
    verification: Mapping[str, Any],
    claim_id: str,
    legal: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if legal is None:
        def builder(
            values: list[dict[str, Any]],
            accepted_process: dict[str, Any],
            accepted_checklist: dict[str, Any],
        ) -> dict[str, Any]:
            return build_template_cycle_verification_v1(
                template=template,
                facts=values,
                process=accepted_process,
                checklist=accepted_checklist,
            )
    else:
        def builder(
            values: list[dict[str, Any]],
            accepted_process: dict[str, Any],
            accepted_checklist: dict[str, Any],
        ) -> dict[str, Any]:
            return build_claim_loop_gate_receipt_v1(
                claim_id=claim_id,
                facts=values,
                process=accepted_process,
                checklist=accepted_checklist,
                legal=legal,
                template=template,
            )
    return _pipeline_for(template).analyze_cycle(
        source_run_id=source_run_id,
        orchestration_id=orchestration_id,
        observable_package=_copy(observable_package),
        facts=_copy(list(facts)),
        process=_copy(process),
        checklist=_copy(checklist),
        verification=_copy(verification),
        transport_mode="deterministic_test_double",
        cycle_verification_builder=builder,
    )


def _permuted_template(
    record_value: Mapping[str, Any], claim_id: str, alias: str
) -> PlaybookTemplate:
    original = PlaybookTemplate.from_persisted_record(record_value)
    if original.supported_claim_ids != (claim_id,):
        raise ValueError("Gate-2 template is not claim-local")
    catalog = _replace_claim(original.catalog, claim_id, alias)
    record = catalog["declarative_records"][alias]
    catalog["claim_sha256_by_id"][alias] = digest_value(record)
    rebuilt = PlaybookTemplate.build(
        template_id=original.template_id.replace(claim_id, alias),
        template_version=original.template_version,
        catalog=catalog,
    )
    if rebuilt.supported_claim_ids != (alias,):
        raise ValueError("permuted template is not alias-local")
    return rebuilt


def _permuted_observable_package(
    package_value: Mapping[str, Any],
    *,
    claim_id: str,
    alias: str,
    binding_sha256: str,
    assessment_sha256: str,
) -> dict[str, Any]:
    content_roster = {
        "customer_message": package_value.get("customer_message"),
        "artifact_content": [
            {"extracted_pages": item.get("extracted_pages"),
             "parsed_email": item.get("parsed_email")}
            for item in package_value.get("artifacts", [])
            if isinstance(item, Mapping)
        ],
    }
    if _occurrence_paths(content_roster, claim_id):
        raise ValueError("immutable source content embeds the claim identity")
    package = _replace_claim(package_value, claim_id, alias)
    if package.get("claim_id") != alias:
        raise ValueError("observable package lacks a claim identity")
    workspace_binding = package.get("workspace_binding")
    if not isinstance(workspace_binding, dict):
        raise ValueError("observable package lacks its workspace binding")
    workspace_binding["binding_sha256"] = binding_sha256
    workspace_binding["intake_assessment_sha256"] = assessment_sha256
    admission = package.get("workspace_evidence_admission")
    if isinstance(admission, dict):
        entries = admission.get("source_entries")
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and "source_entry_sha256" in entry:
                    entry["source_entry_sha256"] = _self_hash(entry, "source_entry_sha256")
        admission["policy_sha256"] = _self_hash(admission, "policy_sha256")
    return package


def _new_source_result(
    *,
    old_result: Mapping[str, Any],
    session_id: str,
    claim_id: str,
    alias: str,
    alias_workspace_state: Mapping[str, Any],
) -> tuple[str, PlaybookTemplate, dict[str, Any], dict[str, Any]]:
    template_record = old_result.get("playbook_template_record")
    if not isinstance(template_record, Mapping):
        raise ValueError("accepted source lacks a persisted template")
    template = _permuted_template(template_record, claim_id, alias)
    package = _permuted_observable_package(
        old_result["observable_package"],
        claim_id=claim_id,
        alias=alias,
        binding_sha256=alias_workspace_state["binding"]["binding_sha256"],
        assessment_sha256=alias_workspace_state["intake_assessment"]["assessment_sha256"],
    )
    legal = _replace_claim(old_result["legal_research"], claim_id, alias)
    source_request = {
        "contract": "casepath.declarative-source-request/1.0.0",
        "session_id": session_id,
        "claim_id": alias,
        "template_sha256": template.template_sha256,
        "observable_package_sha256": digest_value(package),
        "legal_research_sha256": digest_value(legal),
    }
    source_run_id = "run_source_" + digest_value(source_request)[:32]
    materialized = materialize_template_cycle_v1(
        template=template,
        claim_id=alias,
        observable_package=package,
    )
    orchestration_id = "declarative-source." + digest_value(
        {"run_id": source_run_id, "template_sha256": template.template_sha256,
         "observable_package_sha256": digest_value(package)}
    )
    cycle = _run_cycle(
        template=template,
        source_run_id=source_run_id,
        orchestration_id=orchestration_id,
        observable_package=package,
        facts=materialized.facts,
        process=materialized.process,
        checklist=materialized.checklist,
        verification=materialized.verification,
        claim_id=alias,
        legal=None,
    )
    accepted = cycle["accepted_cycle_artifacts"]
    process = _copy(accepted["process"])
    checklist = _copy(accepted["checklist"])
    nodes = {item["node_id"]: item for item in process["nodes"]}
    next_node_id = process["current_overlay"]["next_action_node_id"]
    next_node = nodes[next_node_id]
    result = {
        "claim_id": alias,
        "facts": _copy(accepted["facts"]),
        "legal_research": legal,
        "process": process,
        "checklist": checklist,
        "verification": _copy(cycle["verification"]),
        "agent_orchestration": _copy(cycle["orchestration_audit"]),
        "next_action": {
            "title": next_node["title"], "detail": next_node["why"],
            "requires_expert_approval": False, "process_node_id": next_node_id,
            "agent_brief_contribution": _copy(accepted["final_claim_brief"]),
        },
        "playbook_template": template.receipt,
        "playbook_template_record": template.persisted_record,
        "observable_package": package,
        "audit": {
            "input_hash": digest_value(package),
            "observable_input_hash": digest_value(package),
            "canonical_state_hash": digest_value(accepted["facts"]),
            "profile": DETERMINISTIC_PROFILE,
            "orchestrator": ORCHESTRATOR,
            "schema": "casepath.declarative-playbook-source/1.0.0",
            "accepted": True,
            "verification_computed": True,
            "authority_mode": "deterministic_reference",
        },
    }
    accepted_artifacts_from_run(result)
    return source_run_id, template, package, result


def _source_acceptance_cycle(
    *,
    source_run_id: str,
    loop_id: str,
    claim_id: str,
    template: PlaybookTemplate,
    accepted_result: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Any]:
    accepted = accepted_artifacts_from_run(accepted_result)
    projected = project_claim_loop_artifacts_v1(
        accepted=accepted, observations=(), corrections=(), projection_ledger=()
    )
    package = _copy(accepted["observable_package"])
    orchestration_id = "claim-loop-source." + digest_value(
        {"source_run_id": source_run_id, "loop_id": loop_id,
         "accepted_result_sha256": digest_value(accepted_result),
         "observable_package_sha256": digest_value(package)}
    )
    cycle = _run_cycle(
        template=template, source_run_id=source_run_id,
        orchestration_id=orchestration_id, observable_package=package,
        facts=projected["facts"], process=projected["process"],
        checklist=projected["checklist"],
        verification=projected["deterministic_gate_receipt"],
        claim_id=claim_id, legal=accepted["legal_research"],
    )
    audit = cycle["orchestration_audit"]
    verification = cycle["verification"]
    artifacts = cycle["accepted_cycle_artifacts"]
    receipt = build_six_agent_cycle_receipt_v1(
        source_run_id=source_run_id, loop_id=loop_id,
        cycle_kind="source_acceptance", prior_state_sha256=None,
        trigger_sha256=digest_value(accepted_result),
        orchestration_id=orchestration_id,
        playbook_template_sha256=template.template_sha256,
        observable_package=package, facts=artifacts["facts"],
        process=artifacts["process"], checklist=artifacts["checklist"],
        verification=verification, graph_audit=audit,
        accepted_cycle_artifacts=artifacts,
        transport_mode="deterministic_test_double", model_calls=0,
        provider_calls=0,
        credential_access_status="none_due_to_zero_provider_calls",
        credential_access_receipt_sha256s=(), cost_status="exact", cost_usd=0.0,
    )
    return verification, audit, artifacts, receipt


def _upstream_activity(audit: Mapping[str, Any]) -> BoundActivity:
    calls, cost_status, cost_usd = derive_graph_activity_v1(audit)
    if calls != 0 or cost_status != "exact" or cost_usd != 0.0:
        raise ValueError("permuted upstream graph is not provider-free")
    audit_sha256 = digest_value(audit)
    return BoundActivity(
        scope="upstream_source_run", graph_traversal_count=1,
        model_calls=0, provider_calls=0,
        activity_receipt_sha256s=(audit_sha256,),
        execution_identity_sha256s=(audit_sha256,),
        credential_access_status="none_due_to_zero_provider_calls",
        credential_access_receipt_sha256s=(), cost_status="exact", cost_usd=0.0,
    )


def _append_loop_event(
    state: ClaimLoopState | None, original: Mapping[str, Any], *,
    loop_id: str, idempotency_key: str, command: Mapping[str, Any],
) -> tuple[ClaimLoopState, dict[str, Any]]:
    material = {
        "contract": original["contract"], "session_id": original["session_id"],
        "loop_id": loop_id, "sequence": original["sequence"],
        "previous_event_sha256": None if state is None else state.last_event_sha256,
        "event_type": original["event_type"], "idempotency_key": idempotency_key,
        "command_sha256": digest_value(command), "command": _copy(command),
        "created_at": original["created_at"],
    }
    event_sha256 = digest_value(material)
    next_state = reduce_claim_loop_event(
        state, event_type=original["event_type"], command=command,
        sequence=original["sequence"], event_sha256=event_sha256,
        timestamp=original["created_at"],
    )
    event = {**material, "event_sha256": event_sha256,
             "resulting_state_sha256": next_state.state_sha256}
    load_claim_loop_event_v1(event)
    return next_state, event


def _new_acquisition(
    old_value: Mapping[str, Any],
    state: ClaimLoopState,
    *,
    source_locator: str | None = None,
) -> AcquisitionReceiptV1:
    old = AcquisitionReceiptV1.model_validate(old_value)
    if state.selected_action is None or state.active_dispatch_sha256 is None:
        raise ValueError("alias observation lacks an active dispatch")
    material = old.model_dump(mode="json", exclude={"receipt_sha256"})
    material.update(
        {"loop_id": state.loop_id, "record_version": state.record_version,
         "action_id": state.selected_action.action_id,
         "action_sha256": state.selected_action.action_sha256,
         "dispatch_sha256": state.active_dispatch_sha256}
    )
    if source_locator is not None:
        material["source_locator"] = source_locator
    request = {
        "contract": (
            "casepath.source-registration-request/1.0.0"
            if material["contract"]
            == "casepath.source-registration-compatibility-receipt/1.0.0"
            else "casepath.acquisition-request/1.1.0"
        ),
        "session_id": material["session_id"], "loop_id": material["loop_id"],
        "record_version": material["record_version"],
        "action_id": material["action_id"], "action_sha256": material["action_sha256"],
        "dispatch_sha256": material["dispatch_sha256"],
        "dispatch_generation": material["dispatch_generation"],
        "adapter_id": material["adapter_id"],
        "adapter_implementation_id": material["adapter_implementation_id"],
        "adapter_implementation_source_sha256": material[
            "adapter_implementation_source_sha256"
        ],
        "adapter_implementation_sha256": material["adapter_implementation_sha256"],
        "source_locator": material["source_locator"],
    }
    material["acquisition_request_sha256"] = digest_value(request)
    return AcquisitionReceiptV1.model_validate(
        {**material, "receipt_sha256": digest_value(material)}
    )


def _authority_alias_digest(
    *,
    identity_kind: str,
    original_identity: str,
    state: ClaimLoopState,
    authority_parent_state: ClaimLoopState,
    dependencies: Sequence[str] = (),
) -> str:
    if state.selected_action is None:
        raise ValueError("authority permutation lacks its selected action")
    return digest_value(
        {
            "contract": "casepath.projection-permutation-authority-rebind/1.0.0",
            "identity_kind": identity_kind,
            "original_identity": original_identity,
            "alias_claim_id": state.claim_id,
            "alias_loop_id": state.loop_id,
            "alias_record_version": state.record_version,
            "authority_parent_revision": authority_parent_state.revision,
            "authority_parent_state_sha256": authority_parent_state.state_sha256,
            "action_sha256": state.selected_action.action_sha256,
            "dependent_identities": list(dependencies),
        }
    )


def _permuted_fixed_source_locator(
    source_locator: str,
    *,
    state: ClaimLoopState,
    authority_parent_state: ClaimLoopState,
) -> tuple[str, dict[str, Any]]:
    parts = source_locator.split(":")
    if (
        len(parts) != 4
        or parts[0] != "loopback-source-span"
        or re.fullmatch(r"intent\.[0-9a-f]{64}", parts[1]) is None
        or re.fullmatch(r"acquisition\.[0-9a-f]{64}", parts[2]) is None
        or _SHA_RE.fullmatch(parts[3]) is None
    ):
        raise ValueError("fixed source acquisition locator is invalid")
    alias_intent_id = "intent." + _authority_alias_digest(
        identity_kind="acquisition_intent_id",
        original_identity=parts[1],
        state=state,
        authority_parent_state=authority_parent_state,
    )
    alias_source_acquisition_id = "acquisition." + _authority_alias_digest(
        identity_kind="source_acquisition_receipt_id",
        original_identity=parts[2],
        state=state,
        authority_parent_state=authority_parent_state,
        dependencies=(alias_intent_id, parts[3]),
    )
    alias_locator = ":".join(
        (parts[0], alias_intent_id, alias_source_acquisition_id, parts[3])
    )
    material = {
        "contract": "casepath.fixed-source-locator-permutation/1.0.0",
        "original_source_locator": source_locator,
        "permuted_source_locator": alias_locator,
        "source_entry_sha256": parts[3],
        "intent_id_mapping": {"before": parts[1], "after": alias_intent_id},
        "source_acquisition_id_mapping": {
            "before": parts[2], "after": alias_source_acquisition_id,
        },
        "authority_parent_revision": authority_parent_state.revision,
        "authority_parent_state_sha256": authority_parent_state.state_sha256,
    }
    return alias_locator, {**material, "receipt_sha256": digest_value(material)}


def _derive_fixed_source_interpretation(
    *,
    state: ClaimLoopState,
    acquisition: AcquisitionReceiptV1,
    installed_source_sha256: str,
) -> tuple[Any, dict[str, Any], str | None]:
    if state.selected_action is None:
        raise ValueError("fixed source interpretation lacks its selected action")
    parts = acquisition.source_locator.split(":")
    if (
        len(parts) != 4
        or parts[0] != "loopback-source-span"
        or re.fullmatch(r"intent\.[0-9a-f]{64}", parts[1]) is None
        or re.fullmatch(r"acquisition\.[0-9a-f]{64}", parts[2]) is None
        or _SHA_RE.fullmatch(parts[3]) is None
    ):
        raise ValueError("fixed source interpretation locator is invalid")
    package = state.accepted_artifacts.get("observable_package")
    admission = (
        package.get("workspace_evidence_admission")
        if isinstance(package, Mapping)
        else None
    )
    entries = admission.get("source_entries") if isinstance(admission, Mapping) else None
    matches = [
        dict(entry)
        for entry in entries or []
        if isinstance(entry, Mapping) and entry.get("source_entry_sha256") == parts[3]
    ]
    if len(matches) != 1:
        raise ValueError("fixed source locator is absent from its admission")
    entry = matches[0]
    text = acquisition.sanitized_content
    raw = text.encode("utf-8") if isinstance(text, str) else b""
    if (
        not isinstance(text, str)
        or not text
        or entry.get("exact_text") != text
        or entry.get("span_sha256") != digest_text(text)
        or entry.get("source_entry_sha256") != _self_hash(
            entry, "source_entry_sha256"
        )
        or not isinstance(entry.get("byte_start"), int)
        or not isinstance(entry.get("byte_end"), int)
        or entry["byte_end"] - entry["byte_start"] != len(raw)
        or acquisition.raw_byte_count != len(raw)
        or acquisition.raw_bytes_sha256 != digest_text(text)
        or acquisition.sanitized_content_sha256 != digest_text(text)
    ):
        raise ValueError("fixed source interpretation differs from admitted bytes")

    action = state.selected_action
    catalog, unresolved, resolved, grant = FixedSourceSpanEvidenceSemantics._catalog(
        action=action, state=state
    )
    finding = FixedSourceSpanEvidenceSemantics._proposal_finding(
        action, text, unresolved, resolved, grant
    )
    production_semantics = object.__new__(FixedSourceSpanEvidenceSemantics)
    production_semantics.implementation_source_sha256 = installed_source_sha256
    production = production_semantics._interpretation(
        action=action,
        state=state,
        acquisition=acquisition,
        receipt=None,
        entry=entry,
        text=text,
        finding=finding,
        catalog=catalog,
        unresolved=unresolved,
    )

    independent_catalog = IndependentWorkspaceEvidenceAuthorityV1._catalog(
        state=state, action=action
    )
    if independent_catalog != (catalog, unresolved, resolved, grant):
        raise ValueError("fixed source production and independent catalogs differ")
    independent_finding = independent_fixed_source_finding(
        action=action,
        text=text,
        unresolved=unresolved,
        resolved=resolved,
        grant=grant,
    )
    independent_semantics = object.__new__(IndependentWorkspaceEvidenceAuthorityV1)
    independent_semantics.interpreter_source_sha256 = installed_source_sha256
    independent = independent_semantics._interpretation(
        state=state,
        action=action,
        acquisition=acquisition,
        receipt=None,
        entry=entry,
        text=text,
        finding=independent_finding,
        unresolved=unresolved,
        catalog=catalog,
    )
    if (
        finding != independent_finding
        or production.model_dump(mode="json")
        != independent.model_dump(mode="json")
    ):
        raise ValueError("fixed source production and independent replay differ")
    return production, entry, finding


def _fixed_source_interpretation(
    *,
    old: ToolArtifactReceipt,
    original_state: ClaimLoopState,
    state: ClaimLoopState,
    acquisition: AcquisitionReceiptV1,
    locator_receipt: Mapping[str, Any],
) -> tuple[Any, dict[str, Any]]:
    installed_source_sha256 = fixed_source_span_module_sha256()
    if old.interpretation.implementation_source_sha256 != installed_source_sha256:
        raise ValueError("fixed source interpretation source identity changed")
    original, original_entry, original_finding = _derive_fixed_source_interpretation(
        state=original_state,
        acquisition=old.acquisition_receipt,
        installed_source_sha256=installed_source_sha256,
    )
    if original.model_dump(mode="json") != old.interpretation.model_dump(mode="json"):
        raise ValueError("original fixed source interpretation is not reproducible")
    production, entry, finding = _derive_fixed_source_interpretation(
        state=state,
        acquisition=acquisition,
        installed_source_sha256=installed_source_sha256,
    )
    old_sources = old.observation.source_refs
    old_source = old_sources[0] if len(old_sources) == 1 else None
    if (
        old_source is None
        or old.acquisition_receipt.sanitized_content != acquisition.sanitized_content
        or old.observation.value != acquisition.sanitized_content
        or original_entry != entry
        or original_finding != finding
        or old_source.source_id != entry.get("artifact_id")
        or old_source.source_sha256 != entry.get("artifact_sha256")
        or old_source.source_version != entry.get("source_version")
        or old_source.text_start != entry.get("text_start")
        or old_source.text_end != entry.get("text_end")
        or old_source.span_sha256 != entry.get("span_sha256")
    ):
        raise ValueError("fixed source alias changed immutable source semantics")
    material = {
        "contract": "casepath.fixed-source-interpretation-permutation/1.0.0",
        "implementation": FixedSourceSpanEvidenceSemantics.implementation_id,
        "implementation_source_sha256": installed_source_sha256,
        "source_entry_sha256": entry["source_entry_sha256"],
        "source_span_sha256": entry["span_sha256"],
        "original_acquisition_receipt_sha256": old.acquisition_receipt_sha256,
        "original_interpretation_receipt_sha256": old.interpretation.receipt_sha256,
        "alias_acquisition_receipt_sha256": acquisition.receipt_sha256,
        "alias_interpretation_receipt_sha256": production.receipt_sha256,
        "original_production_independent_exact_equal": True,
        "production_independent_exact_equal": True,
        "locator_permutation_receipt_sha256": locator_receipt["receipt_sha256"],
    }
    return production, {**material, "receipt_sha256": digest_value(material)}


def _new_tool_artifact(
    old_value: Mapping[str, Any],
    state: ClaimLoopState,
    *,
    original_state: ClaimLoopState,
    authority_parent_state: ClaimLoopState,
) -> tuple[ToolArtifactReceipt, dict[str, Any] | None]:
    old = ToolArtifactReceipt.model_validate(old_value)
    implementation = old.interpretation.implementation
    locator_receipt: dict[str, Any] | None = None
    source_locator: str | None = None
    if implementation == FixedSourceSpanEvidenceSemantics.implementation_id:
        source_locator, locator_receipt = _permuted_fixed_source_locator(
            old.acquisition_receipt.source_locator,
            state=state,
            authority_parent_state=authority_parent_state,
        )
    acquisition = _new_acquisition(
        old.acquisition_receipt.model_dump(mode="json"),
        state,
        source_locator=source_locator,
    )
    if implementation == StructuredMouldArtifactInterpreterV2.implementation_id:
        interpreter: Any = StructuredMouldArtifactInterpreterV2()
        interpretation = interpreter.interpret(
            action=state.selected_action, state=state, acquisition=acquisition
        )
    elif implementation == WorkspaceStructuredEvidenceInterpreterV1.implementation_id:
        interpreter = WorkspaceStructuredEvidenceInterpreterV1()
        interpretation = interpreter.interpret(
            action=state.selected_action, state=state, acquisition=acquisition
        )
    elif implementation == FixedSourceSpanEvidenceSemantics.implementation_id:
        assert locator_receipt is not None
        interpretation, fixed_receipt = _fixed_source_interpretation(
            old=old,
            original_state=original_state,
            state=state,
            acquisition=acquisition,
            locator_receipt=locator_receipt,
        )
    else:
        raise ValueError(f"unsupported evidence interpreter {implementation}")
    assert state.selected_action is not None
    material = {
        "contract": "casepath.tool-artifact-receipt/1.1.0",
        "session_id": state.session_id, "loop_id": state.loop_id,
        "action_id": state.selected_action.action_id,
        "action_sha256": state.selected_action.action_sha256,
        "dispatch_sha256": state.active_dispatch_sha256,
        "adapter_id": acquisition.adapter_id,
        "acquisition_receipt_sha256": acquisition.receipt_sha256,
        "acquisition_receipt": acquisition.model_dump(mode="json"),
        "artifact_source_version": acquisition.record_version,
        "artifact_page_count": acquisition.artifact_page_count,
        "sanitized_content": acquisition.sanitized_content,
        "raw_artifact_sha256": acquisition.receipt_sha256,
        "interpretation": interpretation.model_dump(mode="json"),
        "observation": interpretation.observation.model_dump(mode="json"),
        "registered_at": acquisition.acquired_at, "model_calls": 0,
        "provider_calls": 0, "provider_credentials_read": False, "cost_usd": 0.0,
    }
    artifact = ToolArtifactReceipt.model_validate(
        {**material, "receipt_sha256": digest_value(material)}
    )
    if implementation != FixedSourceSpanEvidenceSemantics.implementation_id:
        return artifact, None
    fixed_material = {
        "contract": "casepath.fixed-source-artifact-permutation/1.0.0",
        "locator_permutation": locator_receipt,
        "interpretation_permutation": fixed_receipt,
        "original_artifact_receipt_sha256": old.receipt_sha256,
        "alias_artifact_receipt_sha256": artifact.receipt_sha256,
    }
    return artifact, {**fixed_material, "receipt_sha256": digest_value(fixed_material)}


def _permuted_authority_binding(
    old_value: Mapping[str, Any],
    *,
    old_artifact: ToolArtifactReceipt,
    artifact: ToolArtifactReceipt,
    state: ClaimLoopState,
    authority_parent_state: ClaimLoopState,
    fixed_artifact_receipt: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    old = _copy(old_value)
    expected_keys = {
        "contract", "proposal_sha256", "admission_receipt_sha256",
        "interpretation_receipt_sha256", "acquisition_receipt_sha256",
        "registration_receipt_sha256", "authority_id",
        "authority_source_sha256", "binding_sha256",
    }
    if (
        set(old) != expected_keys
        or old.get("contract")
        != "casepath.workspace-evidence-authority-binding/1.0.0"
        or old.get("interpretation_receipt_sha256")
        != old_artifact.interpretation.receipt_sha256
        or old.get("acquisition_receipt_sha256")
        != old_artifact.acquisition_receipt_sha256
        or old.get("authority_id")
        != "casepath.independent-evidence-authority/1.0.0"
        or old.get("authority_source_sha256")
        != independent_authority_module_sha256()
        or old.get("binding_sha256") != _self_hash(old, "binding_sha256")
        or any(
            _SHA_RE.fullmatch(str(old.get(key))) is None
            for key in (
                "proposal_sha256", "admission_receipt_sha256",
                "registration_receipt_sha256", "authority_source_sha256",
            )
        )
    ):
        raise ValueError("original workspace authority binding is invalid")
    if old_artifact.interpretation.implementation != FixedSourceSpanEvidenceSemantics.implementation_id:
        old["interpretation_receipt_sha256"] = artifact.interpretation.receipt_sha256
        old["acquisition_receipt_sha256"] = artifact.acquisition_receipt_sha256
        old["binding_sha256"] = _self_hash(old, "binding_sha256")
        return old, None
    if fixed_artifact_receipt is None:
        raise ValueError("fixed source artifact lacks its permutation receipt")

    registration_sha256 = _authority_alias_digest(
        identity_kind="registration_receipt_sha256",
        original_identity=old["registration_receipt_sha256"],
        state=state,
        authority_parent_state=authority_parent_state,
        dependencies=(
            artifact.acquisition_receipt.source_locator,
            artifact.acquisition_receipt_sha256,
        ),
    )
    proposal_sha256 = _authority_alias_digest(
        identity_kind="proposal_sha256",
        original_identity=old["proposal_sha256"],
        state=state,
        authority_parent_state=authority_parent_state,
        dependencies=(
            registration_sha256,
            artifact.acquisition_receipt_sha256,
            artifact.interpretation.receipt_sha256,
        ),
    )
    admission_sha256 = _authority_alias_digest(
        identity_kind="admission_receipt_sha256",
        original_identity=old["admission_receipt_sha256"],
        state=state,
        authority_parent_state=authority_parent_state,
        dependencies=(
            proposal_sha256,
            registration_sha256,
            artifact.acquisition_receipt_sha256,
            artifact.interpretation.receipt_sha256,
        ),
    )
    authority = {
        **old,
        "proposal_sha256": proposal_sha256,
        "admission_receipt_sha256": admission_sha256,
        "interpretation_receipt_sha256": artifact.interpretation.receipt_sha256,
        "acquisition_receipt_sha256": artifact.acquisition_receipt_sha256,
        "registration_receipt_sha256": registration_sha256,
    }
    authority["binding_sha256"] = _self_hash(authority, "binding_sha256")
    mapping = [
        {"kind": key, "before": old[key], "after": authority[key]}
        for key in (
            "proposal_sha256", "admission_receipt_sha256",
            "interpretation_receipt_sha256", "acquisition_receipt_sha256",
            "registration_receipt_sha256", "binding_sha256",
        )
    ]
    material = {
        "contract": "casepath.fixed-source-authority-binding-permutation/1.0.0",
        "scope": "event_visible_synthetic_identity_closure",
        "authority_primitive_chain_reconstructed": False,
        "original_authority_primitive_chain_validated_here": False,
        "persisted_alias_sidecar_chain_claimed": False,
        "event_visible_binding_self_hash_validated": True,
        "boundary": (
            "the fixed ten-field input contains the receipted UTF-8 span but omits the "
            "authority-v3 primitive objects and their unrecoverable preimage fields; "
            "this no-write probe closes every identity exposed by the immutable claim-loop "
            "event but does not claim production authority sidecars exist for the alias"
        ),
        "authority_id": authority["authority_id"],
        "authority_source_sha256": authority["authority_source_sha256"],
        "authority_parent_revision": authority_parent_state.revision,
        "authority_parent_state_sha256": authority_parent_state.state_sha256,
        "artifact_permutation_receipt_sha256": fixed_artifact_receipt[
            "receipt_sha256"
        ],
        "identity_mapping": mapping,
        "identity_mapping_sha256": digest_value(mapping),
        "binding_self_hash_valid": (
            authority["binding_sha256"] == _self_hash(authority, "binding_sha256")
        ),
    }
    return authority, {**material, "receipt_sha256": digest_value(material)}


def _cycle_package(
    accepted: Mapping[str, Any], receipts: Sequence[ToolArtifactReceipt]
) -> dict[str, Any]:
    package = _copy(accepted["observable_package"])
    appended: dict[str, dict[str, Any]] = {}
    for artifact in receipts:
        source = artifact.observation.source_refs[0]
        existing = [
            item for item in package.get("artifacts", [])
            if isinstance(item, Mapping) and item.get("artifact_id") == source.source_id
        ]
        if existing:
            if len(existing) != 1:
                raise ValueError("cycle source identity is ambiguous")
            page = next(
                (item for item in existing[0].get("extracted_pages", [])
                 if isinstance(item, Mapping) and item.get("page") == source.page),
                None,
            )
            text = page.get("text") if isinstance(page, Mapping) else None
            if (
                existing[0].get("sha256") != source.source_sha256
                or not isinstance(text, str) or source.text_start is None
                or source.text_end is None
                or text[source.text_start:source.text_end] != source.sanitized_excerpt
                or source.span_sha256 != digest_text(source.sanitized_excerpt or "")
            ):
                raise ValueError("cycle source differs from admitted bytes")
            continue
        item = {
            "artifact_id": source.source_id,
            "filename": f"{artifact.observation.evidence_item_id}.pdf",
            "media_type": "application/pdf", "received_at": artifact.registered_at,
            "page_count": 1, "sha256": source.source_sha256,
            "extracted_pages": [{"page": 1, "text": artifact.sanitized_content}],
        }
        prior = appended.get(source.source_id)
        if prior is not None and {
            key: value for key, value in prior.items() if key != "received_at"
        } != {key: value for key, value in item.items() if key != "received_at"}:
            raise ValueError("cycle artifact identity changed")
        appended.setdefault(source.source_id, item)
    package["artifacts"] = [*package["artifacts"],
                            *(appended[key] for key in sorted(appended))]
    return package


def _observation_cycle(
    *,
    state: ClaimLoopState,
    artifact: ToolArtifactReceipt,
    template: PlaybookTemplate,
    prior_receipts: Sequence[ToolArtifactReceipt],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Any]:
    observations = (*state.observations, artifact.observation)
    ledger = (
        *state.projection_ledger,
        ProjectionLedgerEntry(
            kind="observation",
            record_sha256=artifact.observation.observation_sha256,
            artifact_receipt_sha256=artifact.receipt_sha256,
            recorded_at=artifact.registered_at,
        ),
    )
    projected = project_claim_loop_artifacts_v1(
        accepted=state.accepted_artifacts, observations=observations,
        corrections=state.corrections, projection_ledger=ledger,
    )
    package = _cycle_package(state.accepted_artifacts, (*prior_receipts, artifact))
    orchestration_id = "claim-loop-cycle." + digest_value(
        {"source_run_id": state.source_run_id, "loop_id": state.loop_id,
         "prior_state_sha256": state.state_sha256, "cycle_kind": "observation",
         "trigger_sha256": artifact.observation.observation_sha256,
         "facts_sha256": digest_value(list(projected["facts"])),
         "observable_package_sha256": digest_value(package)}
    )
    cycle = _run_cycle(
        template=template, source_run_id=state.source_run_id,
        orchestration_id=orchestration_id, observable_package=package,
        facts=projected["facts"], process=projected["process"],
        checklist=projected["checklist"],
        verification=projected["deterministic_gate_receipt"],
        claim_id=state.claim_id, legal=state.accepted_artifacts["legal_research"],
    )
    audit = cycle["orchestration_audit"]
    verification = cycle["verification"]
    artifacts = cycle["accepted_cycle_artifacts"]
    calls, cost_status, cost_usd = derive_graph_activity_v1(audit)
    if calls != 0 or cost_status != "exact" or cost_usd != 0.0:
        raise ValueError("permuted observation graph is not provider-free")
    receipt = build_six_agent_cycle_receipt_v1(
        source_run_id=state.source_run_id, loop_id=state.loop_id,
        cycle_kind="observation", prior_state_sha256=state.state_sha256,
        trigger_sha256=artifact.observation.observation_sha256,
        orchestration_id=orchestration_id,
        playbook_template_sha256=template.template_sha256,
        observable_package=package, facts=artifacts["facts"],
        process=artifacts["process"], checklist=artifacts["checklist"],
        verification=verification, graph_audit=audit,
        accepted_cycle_artifacts=artifacts,
        transport_mode="deterministic_test_double", model_calls=0,
        provider_calls=0,
        credential_access_status="none_due_to_zero_provider_calls",
        credential_access_receipt_sha256s=(), cost_status="exact", cost_usd=0.0,
    )
    return verification, audit, artifacts, receipt


def _permuted_loop(
    events: Sequence[Mapping[str, Any]], *, claim_id: str, alias: str,
    alias_workspace_state: Mapping[str, Any],
) -> tuple[ClaimLoopState, list[dict[str, Any]], dict[str, Any] | None]:
    event_types = tuple(event.get("event_type") for event in events)
    if event_types not in {_ADMITTED_LOOP_EVENT_TYPES, _SELECTED_LOOP_EVENT_TYPES}:
        raise ValueError("Gate-2 ClaimLoop event topology changed")
    if any(event.get("contract") != "casepath.claim-loop-event/1.0.0" for event in events):
        raise ValueError("Gate-2 ClaimLoop uses an unsupported protocol envelope")
    original_active_state = _replay_loop(events[:3], claim_id)
    created = events[0]
    old_command = created["command"]
    session_id = created["session_id"]
    old_result = old_command["accepted_result"]
    old_assessment = old_result["observable_package"]["workspace_binding"][
        "intake_assessment_sha256"
    ]
    old_create_key = f"workspace-loop.{old_assessment}"
    old_source_request = {
        "contract": "casepath.declarative-source-request/1.0.0",
        "session_id": session_id, "claim_id": claim_id,
        "template_sha256": old_result["playbook_template"]["template_sha256"],
        "observable_package_sha256": digest_value(old_result["observable_package"]),
        "legal_research_sha256": digest_value(old_result["legal_research"]),
    }
    expected_old_record = "record." + digest_value(
        {"contract": "casepath.server-owned-record-version/1.0.0",
         "source_run_id": old_command["source_run_id"], "claim_id": claim_id,
         "result_sha256": digest_value(old_result), "pipeline_release": RELEASE,
         "result_schema": old_result["audit"]["schema"]}
    )
    if (
        created["idempotency_key"] != old_create_key
        or old_command["source_run_id"] != "run_source_" + digest_value(old_source_request)[:32]
        or old_command["create_request_sha256"]
        != digest_value({"source_run_id": old_command["source_run_id"]})
        or old_command["record_version"] != expected_old_record
        or old_command["six_agent_cycle_receipt"].get("transport_mode")
        != "deterministic_test_double"
    ):
        raise ValueError("original source/create identity is not reproducible")
    source_run_id, template, _package, result = _new_source_result(
        old_result=old_result, session_id=session_id, claim_id=claim_id,
        alias=alias, alias_workspace_state=alias_workspace_state,
    )
    create_key = f"workspace-loop.{alias_workspace_state['intake_assessment']['assessment_sha256']}"
    loop_id = "loop." + digest_value(
        {"contract": "casepath.claim-loop-create-resource/1.0.0",
         "session_id": session_id, "idempotency_key": create_key}
    )
    record_version = "record." + digest_value(
        {"contract": "casepath.server-owned-record-version/1.0.0",
         "source_run_id": source_run_id, "claim_id": alias,
         "result_sha256": digest_value(result), "pipeline_release": RELEASE,
         "result_schema": result["audit"]["schema"]}
    )
    verification, graph_audit, artifacts, cycle_receipt = _source_acceptance_cycle(
        source_run_id=source_run_id, loop_id=loop_id, claim_id=alias,
        template=template, accepted_result=result,
    )
    upstream_audit = result["agent_orchestration"]
    upstream_activity = _upstream_activity(upstream_audit)
    source_activity = bound_activity_from_cycle_receipt_v1(
        scope="source_acceptance", receipt=cycle_receipt
    )
    create_command = {
        "session_id": session_id, "loop_id": loop_id, "claim_id": alias,
        "source_run_id": source_run_id,
        "create_request_sha256": digest_value({"source_run_id": source_run_id}),
        "record_version": record_version, "accepted_result": result,
        "six_agent_verification": verification,
        "six_agent_graph_audit": graph_audit,
        "six_agent_cycle_receipt": cycle_receipt.model_dump(mode="json"),
        "accepted_cycle_artifacts": artifacts,
        "upstream_source_run_activity": upstream_activity.model_dump(mode="json"),
        "upstream_source_graph_audit": upstream_audit,
        "source_acceptance_activity": source_activity.model_dump(mode="json"),
    }
    state: ClaimLoopState | None = None
    transformed: list[dict[str, Any]] = []
    state, event = _append_loop_event(
        state, created, loop_id=loop_id, idempotency_key=create_key,
        command=create_command,
    )
    transformed.append(event)

    selected = events[1]
    expected_old_select = "workspace-select.initial." + old_assessment[:24]
    if selected["idempotency_key"] != expected_old_select or selected["command"] != {}:
        raise ValueError("Gate-2 initial selection identity differs")
    select_key = "workspace-select.initial." + alias_workspace_state[
        "intake_assessment"
    ]["assessment_sha256"][:24]
    state, event = _append_loop_event(
        state, selected, loop_id=loop_id, idempotency_key=select_key, command={}
    )
    transformed.append(event)
    authority_parent_state = state

    if event_types == _SELECTED_LOOP_EVENT_TYPES:
        return state, transformed, None

    dispatched = events[2]
    dispatch_command = _copy(dispatched["command"])
    if state.selected_action is None:
        raise ValueError("permuted selection produced no action")
    if (
        dispatch_command.get("action_id") != state.selected_action.action_id
        or dispatch_command.get("action_sha256") != state.selected_action.action_sha256
    ):
        raise ValueError("claim rename changed the bounded action semantics")
    parent_key = dispatch_command["client_idempotency_key"]
    request_type = dispatch_command.get("client_request_type", "advance")
    request_sha256 = dispatch_command.get(
        "client_request_sha256", dispatch_command.get("advance_request_sha256")
    )
    dispatch_key = claim_loop_internal_event_key_v1(
        session_id=session_id, loop_id=loop_id,
        client_idempotency_key=parent_key, request_type=request_type,
        request_sha256=request_sha256, event_kind="dispatch",
    )
    result_key = claim_loop_internal_event_key_v1(
        session_id=session_id, loop_id=loop_id,
        client_idempotency_key=parent_key, request_type=request_type,
        request_sha256=request_sha256, event_kind="result",
    )
    dispatch_command["client_dispatch_idempotency_key"] = dispatch_key
    dispatch_command["client_result_idempotency_key"] = result_key
    dispatch_command["lease_owner"] = "claim-loop-worker." + digest_value(
        {"session_id": session_id, "loop_id": loop_id,
         "idempotency_key": parent_key,
         "action_sha256": state.selected_action.action_sha256,
         "adapter_id": dispatch_command["adapter_id"]}
    )
    state, event = _append_loop_event(
        state, dispatched, loop_id=loop_id, idempotency_key=dispatch_key,
        command=dispatch_command,
    )
    transformed.append(event)

    observed = events[3]
    old_observation_command = observed["command"]
    old_artifact = ToolArtifactReceipt.model_validate(
        old_observation_command["tool_artifact_receipt"]
    )
    artifact, fixed_artifact_receipt = _new_tool_artifact(
        old_observation_command["tool_artifact_receipt"],
        state,
        original_state=original_active_state,
        authority_parent_state=authority_parent_state,
    )
    cycle_verification, cycle_audit, cycle_artifacts, observation_receipt = _observation_cycle(
        state=state, artifact=artifact, template=template, prior_receipts=(),
    )
    observation_command = {
        "action_id": artifact.action_id, "dispatch_sha256": artifact.dispatch_sha256,
        "artifact_receipt_sha256": artifact.receipt_sha256,
        "tool_artifact_receipt": artifact.model_dump(mode="json"),
        "observation": artifact.observation.model_dump(mode="json"),
        "six_agent_verification": cycle_verification,
        "six_agent_graph_audit": cycle_audit,
        "six_agent_cycle_receipt": observation_receipt.model_dump(mode="json"),
        "accepted_cycle_artifacts": cycle_artifacts,
    }
    authority_permutation_receipt: dict[str, Any] | None = None
    if "evidence_authority_binding" in old_observation_command:
        authority, authority_permutation_receipt = _permuted_authority_binding(
            old_observation_command["evidence_authority_binding"],
            old_artifact=old_artifact,
            artifact=artifact,
            state=state,
            authority_parent_state=authority_parent_state,
            fixed_artifact_receipt=fixed_artifact_receipt,
        )
        observation_command["evidence_authority_binding"] = authority
    if "advance_request_sha256" in old_observation_command:
        observation_command["advance_request_sha256"] = old_observation_command[
            "advance_request_sha256"
        ]
    if set(observation_command) != set(old_observation_command):
        raise ValueError("Gate-2 observation command topology changed")
    state, event = _append_loop_event(
        state, observed, loop_id=loop_id, idempotency_key=result_key,
        command=observation_command,
    )
    transformed.append(event)
    return state, transformed, authority_permutation_receipt


def _prefix(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    tail = events[-1]
    return {
        "revision": tail["sequence"],
        "last_event_sha256": tail["event_sha256"],
        "last_event_at": tail["created_at"],
    }


def _projection(
    workspace_state: Mapping[str, Any],
    state: ClaimLoopState,
    events: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    loaded = [load_claim_loop_event_v1(dict(event)) for event in events]
    detailed = derive_workspace_operational_projection_v1(
        workspace_state=workspace_state,
        loop_state=state,
        loop_events=loaded,
        expected_loop_id=state.loop_id,
    )
    compact = derive_workspace_operational_projection_v1(
        workspace_state=workspace_state,
        loop_state=state,
        loop_journal_prefix=_prefix(events),
        expected_loop_id=state.loop_id,
    )
    if detailed != compact:
        raise ValueError("production detail and compact projection calls differ")
    if (
        set(detailed) != _PROJECTION_KEYS
        or detailed["projection_sha256"] != _self_hash(detailed, "projection_sha256")
    ):
        raise ValueError("production projection is not complete and self-hashed")
    return detailed, compact


def _identity_leaf(path: str, old: str, new: str) -> bool:
    key = path.rsplit("/", 1)[-1].lower()
    return old != new and (
        _SHA_RE.fullmatch(old) is not None
        or _PREFIXED_DIGEST_RE.fullmatch(old) is not None
        or (
            _OPAQUE_ID_RE.fullmatch(old) is not None
            and _OPAQUE_ID_RE.fullmatch(new) is not None
        )
        or any(marker in key for marker in (
            "id", "sha", "hash", "receipt", "version", "path", "key", "owner",
            "locator",
        ))
    )


def _identity_roster(path: str, before: Sequence[Any], after: Sequence[Any]) -> bool:
    """Recognize canonical set-valued identity rosters whose sort can change."""

    key = path.rsplit("/", 1)[-1].lower()
    return (
        key.endswith("_ids") or key.endswith("_sha256s")
    ) and all(isinstance(item, str) for item in (*before, *after))


def _compare_identity_roster(
    before: Sequence[str],
    after: Sequence[str],
    *,
    claim_id: str,
    alias: str,
    path: str,
    pairs: dict[str, str],
    inverse: dict[str, str],
    changed_paths: list[str],
    preserved: dict[tuple[str, str], dict[str, Any]],
) -> None:
    """Compare a canonical identity set without inventing positional renames."""

    if len(before) != len(set(before)) or len(after) != len(set(after)):
        raise ValueError(f"identity roster contains duplicates at {path}")
    old_indexes = {value: index for index, value in enumerate(before)}
    new_indexes = {value: index for index, value in enumerate(after)}
    unmatched_old = set(before)
    unmatched_new = set(after)
    matches: list[tuple[str, str]] = []

    # First honor dependencies established outside the roster.
    for old in before:
        new = pairs.get(old)
        if new in unmatched_new:
            matches.append((old, new))
            unmatched_old.remove(old)
            unmatched_new.remove(new)
    for new in after:
        old = inverse.get(new)
        if old in unmatched_old:
            matches.append((old, new))
            unmatched_old.remove(old)
            unmatched_new.remove(new)

    # Production canonicalizes these rosters by the opaque value.  Rehashing
    # can cross a preserved source identity in that order, so retain exact
    # common members before pairing the remaining derived identities.
    for item in sorted(unmatched_old & unmatched_new):
        matches.append((item, item))
        unmatched_old.remove(item)
        unmatched_new.remove(item)

    if len(unmatched_old) != len(unmatched_new):
        raise ValueError(f"identity roster is not a closed rename at {path}")
    matches.extend(zip(sorted(unmatched_old), sorted(unmatched_new), strict=True))
    for old, new in matches:
        _compare_closed(
            old,
            new,
            claim_id=claim_id,
            alias=alias,
            path=f"{path}/{old_indexes[old]}->{new_indexes[new]}",
            pairs=pairs,
            inverse=inverse,
            changed_paths=changed_paths,
            preserved=preserved,
        )


def _compare_closed(
    before: Any,
    after: Any,
    *,
    claim_id: str,
    alias: str,
    path: str = "$",
    pairs: dict[str, str],
    inverse: dict[str, str],
    changed_paths: list[str],
    preserved: dict[tuple[str, str], dict[str, Any]],
) -> None:
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        expected_keys = {
            key.replace(claim_id, alias) if isinstance(key, str) else key: key
            for key in before
        }
        if set(after) != set(expected_keys):
            raise ValueError(f"closed rename changed mapping topology at {path}")
        for new_key, old_key in expected_keys.items():
            if new_key != old_key:
                old_text, new_text = str(old_key), str(new_key)
                prior = pairs.setdefault(old_text, new_text)
                reverse = inverse.setdefault(new_text, old_text)
                if prior != new_text or reverse != old_text:
                    raise ValueError("claim-key permutation is not bijective")
                changed_paths.append(f"{path}/@key:{old_text}")
            _compare_closed(
                before[old_key], after[new_key], claim_id=claim_id, alias=alias,
                path=f"{path}/{old_key}", pairs=pairs, inverse=inverse,
                changed_paths=changed_paths, preserved=preserved,
            )
        return
    if isinstance(before, (list, tuple)) and isinstance(after, (list, tuple)):
        if len(before) != len(after):
            raise ValueError(f"closed rename changed sequence topology at {path}")
        if _identity_roster(path, before, after):
            _compare_identity_roster(
                before,
                after,
                claim_id=claim_id,
                alias=alias,
                path=path,
                pairs=pairs,
                inverse=inverse,
                changed_paths=changed_paths,
                preserved=preserved,
            )
            return
        for index, (old_item, new_item) in enumerate(zip(before, after, strict=True)):
            _compare_closed(
                old_item, new_item, claim_id=claim_id, alias=alias,
                path=f"{path}/{index}", pairs=pairs, inverse=inverse,
                changed_paths=changed_paths, preserved=preserved,
            )
        return
    if before == after:
        if isinstance(before, str):
            key = path.rsplit("/", 1)[-1]
            category = _EXTERNAL_IDENTITY_CATEGORIES.get(key)
            if category is None and (_SHA_RE.fullmatch(before) or key.endswith("_id")):
                category = "semantic_or_source_identity"
            if category is not None:
                record = preserved.setdefault(
                    (category, before),
                    {"category": category, "value": before, "paths": []},
                )
                record["paths"].append(path)
        return
    if type(before) is not type(after) or not isinstance(before, str):
        raise ValueError(f"closed rename changed non-identity semantics at {path}")
    if before.replace(claim_id, alias) != after and not _identity_leaf(
        path, before, after
    ):
        raise ValueError(
            f"closed rename changed an unclassified semantic value at {path}: "
            f"{before!r} -> {after!r}"
        )
    prior = pairs.setdefault(before, after)
    reverse = inverse.setdefault(after, before)
    if prior != after or reverse != before:
        raise ValueError(
            f"identity dependency mapping is not bijective at {path}: "
            f"{before!r}->{after!r}, prior={prior!r}, reverse={reverse!r}"
        )
    changed_paths.append(path)


def _inverse_map(value: Any, inverse: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return inverse.get(value, value)
    if isinstance(value, list):
        return [_inverse_map(item, inverse) for item in value]
    if isinstance(value, Mapping):
        return {
            inverse.get(key, key) if isinstance(key, str) else key: _inverse_map(item, inverse)
            for key, item in value.items()
        }
    return value


def _normalize_inverse_rosters(reference: Any, mapped: Any, path: str = "$") -> Any:
    """Restore canonical identity-roster order after inverse mapping."""

    if isinstance(reference, Mapping) and isinstance(mapped, Mapping):
        if set(reference) != set(mapped):
            return mapped
        return {
            key: _normalize_inverse_rosters(
                reference[key], mapped[key], f"{path}/{key}"
            )
            for key in reference
        }
    if isinstance(reference, (list, tuple)) and isinstance(mapped, (list, tuple)):
        if (
            _identity_roster(path, reference, mapped)
            and len(reference) == len(mapped)
            and sorted(reference) == sorted(mapped)
        ):
            return _copy(list(reference))
        if len(reference) != len(mapped):
            return mapped
        return [
            _normalize_inverse_rosters(old, new, f"{path}/{index}")
            for index, (old, new) in enumerate(zip(reference, mapped, strict=True))
        ]
    return mapped


def _inverse_map_complete(
    value: Any, reference: Any, inverse: Mapping[str, str]
) -> Any:
    return _normalize_inverse_rosters(reference, _inverse_map(value, inverse))


def _external_roster(
    preserved: Mapping[tuple[str, str], Mapping[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for record in sorted(
        preserved.values(), key=lambda item: (item["category"], item["value"])
    ):
        paths = sorted(set(record["paths"]))
        category = record["category"]
        if category not in _EXTERNAL_CATEGORY_REASONS:
            raise ValueError(f"unclassified external identity category {category}")
        result.append(
            {"category": category,
             "reason": _EXTERNAL_CATEGORY_REASONS[category],
             "value": record["value"],
             "path_count": len(paths), "paths_sha256": digest_value(paths)}
        )
    return result


def _runtime_source_closure(forbidden: Sequence[str]) -> dict[str, Any]:
    files: dict[str, dict[str, Any]] = {}
    identity_hits: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        if not name.startswith("casepath_api") or not isinstance(module, ModuleType):
            continue
        raw_path = getattr(module, "__file__", None)
        if not isinstance(raw_path, str):
            continue
        path = Path(raw_path).resolve()
        if not path.is_file():
            continue
        raw = path.read_bytes()
        entry = {"module": name, "path": str(path), "size_bytes": len(raw),
                 "sha256": sha256(raw).hexdigest()}
        files[str(path)] = entry
        for identity in forbidden:
            if identity.encode("utf-8") in raw:
                identity_hits.append(
                    {"module": name, "path": str(path), "identity": identity}
                )
    roster = sorted(files.values(), key=lambda item: item["path"])
    if identity_hits:
        raise ValueError("loaded production source closure embeds a corpus claim identity")
    return {
        "definition": "all loaded casepath_api module files used by the sealed child",
        "module_file_count": len(roster),
        "module_roster_sha256": digest_value(roster),
        "forbidden_identity_count": len(forbidden),
        "forbidden_identity_roster_sha256": digest_value(sorted(forbidden)),
        "literal_hit_count": 0, "modules": roster,
    }


def _child_runtime_receipt(
    module_closure: Mapping[str, Any],
) -> dict[str, Any]:
    environment_names = set(os.environ)
    missing = sorted(_CHILD_ENV_REQUIRED - environment_names)
    unexpected = sorted(
        environment_names - _CHILD_ENV_REQUIRED - _CHILD_ENV_PLATFORM_OPTIONAL
    )
    if missing or unexpected:
        raise ValueError(
            "permutation child environment is not closed: "
            f"missing={missing!r}, unexpected={unexpected!r}"
        )
    expected_values = {
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1", "PYTHONSAFEPATH": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "TZ": "UTC",
    }
    if any(os.environ.get(key) != expected for key, expected in expected_values.items()):
        raise ValueError("permutation child environment value differs from the sealed policy")
    flags = {
        "isolated": int(sys.flags.isolated),
        "safe_path": bool(sys.flags.safe_path),
        "dont_write_bytecode": int(sys.flags.dont_write_bytecode),
        "no_user_site": int(sys.flags.no_user_site),
        "ignore_environment": int(sys.flags.ignore_environment),
    }
    if flags != {
        "isolated": 1, "safe_path": True, "dont_write_bytecode": 1,
        "no_user_site": 1, "ignore_environment": 1,
    }:
        raise ValueError("permutation child lacks the required -I/-P/-B isolation effects")
    environment = {
        key: os.environ[key]
        for key in sorted(environment_names)
    }
    ordered_path = list(sys.path)
    executable = Path(sys.executable).absolute()
    real_executable = executable.resolve(strict=True)
    material = {
        "contract": "casepath.production-permutation-child-runtime/1.0.0",
        "sys_executable": str(executable),
        "sys_executable_realpath": str(real_executable),
        "python_version": platform.python_version(),
        "python_version_info": list(sys.version_info),
        "python_build": list(platform.python_build()),
        "python_compiler": platform.python_compiler(),
        "python_implementation": platform.python_implementation(),
        "implementation_cache_tag": sys.implementation.cache_tag,
        "cwd": str(Path.cwd().resolve()),
        "sys_flags": flags,
        "ordered_sys_path": ordered_path,
        "ordered_sys_path_sha256": digest_value(ordered_path),
        "allowlisted_environment": environment,
        "allowlisted_environment_sha256": digest_value(environment),
        "required_environment_names": sorted(_CHILD_ENV_REQUIRED),
        "optional_platform_environment_names": sorted(
            _CHILD_ENV_PLATFORM_OPTIONAL
        ),
        "loaded_casepath_api_module_file_count": module_closure[
            "module_file_count"
        ],
        "loaded_casepath_api_module_roster_sha256": module_closure[
            "module_roster_sha256"
        ],
    }
    return {**material, "receipt_sha256": digest_value(material)}


def _expected_negative_rejection(
    *, name: str, expected_fragment: str, operation: Any
) -> dict[str, Any]:
    try:
        operation()
    except ValueError as exc:
        message = str(exc)
        if expected_fragment not in message:
            raise ValueError(
                f"negative control {name} failed for an unexpected reason: {message}"
            ) from exc
        return {
            "name": name,
            "rejected": True,
            "exception_type": type(exc).__name__,
            "reason": message,
            "reason_sha256": digest_value(message),
        }
    raise ValueError(f"negative control {name} was incorrectly accepted")


def _negative_controls(
    *,
    original_input: Mapping[str, Any],
    permuted_input: Mapping[str, Any],
    claim_id: str,
    alias: str,
) -> dict[str, Any]:
    incomplete = _copy(permuted_input)
    incomplete["workspace_state"]["claim_id"] = claim_id
    incomplete_rejection = _expected_negative_rejection(
        name="incomplete_primary_identity_rename",
        expected_fragment="retains identity",
        operation=lambda: _require_absent_identity(
            incomplete, claim_id, "negative incomplete permutation"
        ),
    )
    incomplete_rejection.update(
        {
            "mutation_path": "$/workspace_state/claim_id",
            "mutated_candidate_sha256": digest_value(incomplete),
            "original_identity_occurrence_count": len(
                _occurrence_paths(incomplete, claim_id)
            ),
        }
    )

    declarative_records = original_input["loop_events"][0]["command"][
        "accepted_result"
    ]["playbook_template_record"]["catalog"]["declarative_records"]
    if not isinstance(declarative_records, Mapping) or claim_id not in declarative_records:
        raise ValueError("negative collision control lacks the production claim-key map")
    collision_seed = _copy(declarative_records)
    collision_seed[alias] = {
        "negative_control": "preexisting alias key must make the rename collide"
    }
    collision_rejection = _expected_negative_rejection(
        name="colliding_claim_key_rename",
        expected_fragment="collides in a mapping",
        operation=lambda: _replace_claim(collision_seed, claim_id, alias),
    )
    collision_rejection.update(
        {
            "mutation_path": (
                "$/loop_events/0/command/accepted_result/playbook_template_record/"
                "catalog/declarative_records/@key:alias_claim_id"
            ),
            "mutated_candidate_sha256": digest_value(collision_seed),
            "colliding_target_key": alias,
        }
    )
    controls = [incomplete_rejection, collision_rejection]
    material = {
        "contract": "casepath.identity-permutation-negative-controls/1.0.0",
        "control_count": len(controls),
        "all_rejected_before_acceptance": all(
            item["rejected"] for item in controls
        ),
        "controls": controls,
    }
    if not material["all_rejected_before_acceptance"]:
        raise ValueError("identity permutation negative control was accepted")
    return {**material, "receipt_sha256": digest_value(material)}


def _validate_independent_receipt(
    receipt: Any,
    *,
    claim_id: str,
    workspace_state: Mapping[str, Any],
    workspace_events: Sequence[Mapping[str, Any]],
    loop_state: ClaimLoopState,
    loop_events: Sequence[Mapping[str, Any]],
    original_projection: Mapping[str, Any],
) -> dict[str, Any]:
    expected_keys = {
        "contract", "claim_id", "workspace_state_sha256",
        "workspace_event_roster_sha256", "claim_loop_state_sha256",
        "claim_loop_event_roster_sha256", "expected_projection_sha256",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != expected_keys:
        raise ValueError("independent replay receipt field set differs")
    expected = {
        "contract": "casepath.gate2-independent-permutation-binding/1.0.0",
        "claim_id": claim_id,
        "workspace_state_sha256": workspace_state["state_sha256"],
        "workspace_event_roster_sha256": digest_value(list(workspace_events)),
        "claim_loop_state_sha256": loop_state.state_sha256,
        "claim_loop_event_roster_sha256": digest_value(list(loop_events)),
        "expected_projection_sha256": original_projection["projection_sha256"],
    }
    if dict(receipt) != expected:
        raise ValueError("production replay differs from QA-independent replay binding")
    return expected


def _process(value: dict[str, Any]) -> dict[str, Any]:
    claim_id, alias, forbidden = _validate_identity_inputs(value)
    workspace_events = value["workspace_events"]
    loop_events = value["loop_events"]
    if not isinstance(workspace_events, list) or not isinstance(loop_events, list):
        raise ValueError("raw event rosters must be arrays")
    event_types = tuple(event.get("event_type") for event in loop_events)
    scope = value["permutation_scope"]
    if (
        scope == "gate1_pre_rejection_selected_prefix_plus_zero_effect_rejection_proof"
        and event_types != _SELECTED_LOOP_EVENT_TYPES
    ) or (
        scope in {
            "complete_four_event_gate2_seam",
            "gate1_first_admitted_seam_prefix_plus_full_terminal_replay",
        }
        and event_types != _ADMITTED_LOOP_EVENT_TYPES
    ):
        raise ValueError("permutation scope does not match its closed event topology")
    original_workspace = _replay_workspace(workspace_events, claim_id)
    if original_workspace != value["workspace_state"]:
        raise ValueError("input workspace state differs from independent raw replay")
    original_state = _replay_loop(loop_events, claim_id)
    supplied_prefix = value["loop_journal_prefix"]
    if not isinstance(supplied_prefix, Mapping) or dict(supplied_prefix) != _prefix(loop_events):
        raise ValueError("input ClaimLoop compact prefix differs from raw events")
    original_projection, original_compact = _projection(
        original_workspace, original_state, loop_events
    )
    if original_projection != value["expected_original_projection"]:
        raise ValueError("production original projection differs from live expected projection")
    independent = _validate_independent_receipt(
        value["independent_replay_receipt"], claim_id=claim_id,
        workspace_state=original_workspace, workspace_events=workspace_events,
        loop_state=original_state, loop_events=loop_events,
        original_projection=original_projection,
    )
    original_input = {
        "workspace_events": workspace_events, "workspace_state": original_workspace,
        "loop_events": loop_events,
        "loop_state": original_state.model_dump(mode="json"),
    }
    _require_absent_identity(original_input, alias, "original authority")

    alias_workspace, alias_workspace_events = _permuted_workspace(
        workspace_events, claim_id=claim_id, alias=alias
    )
    alias_state, alias_loop_events, authority_permutation_receipt = _permuted_loop(
        loop_events, claim_id=claim_id, alias=alias,
        alias_workspace_state=alias_workspace,
    )
    if _replay_workspace(alias_workspace_events, alias) != alias_workspace:
        raise ValueError("permuted workspace independent replay differs")
    if _replay_loop(alias_loop_events, alias) != alias_state:
        raise ValueError("permuted ClaimLoop production replay differs")
    permuted_projection, permuted_compact = _projection(
        alias_workspace, alias_state, alias_loop_events
    )
    permuted_input = {
        "workspace_events": alias_workspace_events, "workspace_state": alias_workspace,
        "loop_events": alias_loop_events,
        "loop_state": alias_state.model_dump(mode="json"),
    }
    _require_absent_identity(permuted_input, claim_id, "permuted authority")

    pairs: dict[str, str] = {}
    inverse: dict[str, str] = {}
    changed_paths: list[str] = []
    preserved: dict[tuple[str, str], dict[str, Any]] = {}
    _compare_closed(
        original_input, permuted_input, claim_id=claim_id, alias=alias,
        pairs=pairs, inverse=inverse, changed_paths=changed_paths,
        preserved=preserved,
    )
    if pairs.get(claim_id) != alias:
        raise ValueError("closed mapping does not contain the primary identity rename")
    projection_pairs = dict(pairs)
    projection_inverse = dict(inverse)
    _compare_closed(
        original_projection,
        permuted_projection,
        claim_id=claim_id,
        alias=alias,
        path="$/production_projection",
        pairs=projection_pairs,
        inverse=projection_inverse,
        changed_paths=changed_paths,
        preserved=preserved,
    )
    inverse_projection = _inverse_map_complete(
        permuted_projection, original_projection, projection_inverse
    )
    if inverse_projection != original_projection:
        raise ValueError("inverse-mapped complete production projection differs")
    negative_controls = _negative_controls(
        original_input=original_input,
        permuted_input=permuted_input,
        claim_id=claim_id,
        alias=alias,
    )

    changed_paths = sorted(set(changed_paths))
    external_roster = _external_roster(preserved)
    external_values = {item["value"] for item in external_roster}
    mapping_rows = [
        {"before": before_value, "after": after_value}
        for before_value, after_value in sorted(projection_pairs.items())
    ]
    if external_values & set(projection_pairs):
        raise ValueError(
            "an identity is classified as both renamed and intentionally external"
        )
    runtime_closure = _runtime_source_closure(forbidden)
    child_runtime = _child_runtime_receipt(runtime_closure)
    module_path = Path(
        inspect.getmodule(derive_workspace_operational_projection_v1).__file__
    ).resolve()
    normalized_sha256 = digest_value(inverse_projection)
    audit_policy = {
        "hook_installed_before_production_imports": _AUDIT_INSTALLED_BEFORE_PRODUCTION_IMPORTS,
        "write_open_flag_mask": _WRITE_OPEN_FLAGS,
        "denied_exact_events": sorted(_DENIED_AUDIT_EVENTS),
        "denied_prefixes": list(_DENIED_AUDIT_PREFIXES),
        "denied_attempt_count": _DENIED_ATTEMPTS,
        "denied_event_counts": dict(sorted(_DENIED_EVENT_COUNTS.items())),
        "sqlite_denied": True, "filesystem_mutation_denied": True,
        "subprocess_denied": True, "network_denied": True,
    }
    before = {
        "workspace_event_roster_sha256": digest_value(workspace_events),
        "workspace_state_sha256": original_workspace["state_sha256"],
        "loop_event_roster_sha256": digest_value(loop_events),
        "loop_state_sha256": original_state.state_sha256,
        "projection": original_projection,
        "projection_input_sha256": digest_value(original_input),
    }
    after = {
        "workspace_event_roster_sha256": digest_value(alias_workspace_events),
        "workspace_state_sha256": alias_workspace["state_sha256"],
        "loop_event_roster_sha256": digest_value(alias_loop_events),
        "loop_state_sha256": alias_state.state_sha256,
        "projection": permuted_projection,
        "inverse_mapped_projection": inverse_projection,
        "projection_input_sha256": digest_value(permuted_input),
    }
    identity_receipt = {
        "contract": "casepath.closed-identity-permutation/1.0.0",
        "primary_mapping": {"before": claim_id, "after": alias},
        "alias_derivation": {
            "contract": "casepath.projection-permutation-alias/1.0.0",
            "alias_nonce_sha256": value["alias_nonce_sha256"],
            "derived_alias_claim_id": alias,
        },
        "changed_identity_value_count": len(projection_pairs),
        "changed_identity_mapping_sha256": digest_value(mapping_rows),
        "changed_identity_path_count": len(changed_paths),
        "changed_identity_paths_sha256": digest_value(changed_paths),
        "original_claim_occurrence_count_before": len(
            _occurrence_paths(original_input, claim_id)
        ),
        "original_claim_occurrence_count_after": 0,
        "alias_occurrence_count_before": 0,
        "alias_occurrence_count_after": len(_occurrence_paths(permuted_input, alias)),
        "bijective": len(projection_pairs) == len(projection_inverse),
        "bijection_domain": "unique scalar identity values plus claim-bearing mapping keys",
        "mapping_rows": mapping_rows,
        "full_structure_inverse_equal": _inverse_map_complete(
            permuted_input, original_input, inverse
        ) == original_input,
        "full_projection_inverse_equal": inverse_projection == original_projection,
        "changed_paths": changed_paths,
    }
    if not identity_receipt["full_structure_inverse_equal"]:
        raise ValueError("inverse mapping does not reconstruct the complete input authority")
    material = {
        "contract": "casepath.production-projection-permutation-result/1.0.0",
        "claim_id": claim_id, "alias_claim_id": alias,
        "permutation_scope": value["permutation_scope"],
        "qualified_callable": (
            "casepath_api.workspace_operational_projection_v1."
            "derive_workspace_operational_projection_v1"
        ),
        "callable_signature": str(inspect.signature(
            derive_workspace_operational_projection_v1
        )),
        "module_path": str(module_path),
        "module_sha256": sha256(module_path.read_bytes()).hexdigest(),
        "raw_event_roster_sha256": digest_value(loop_events),
        "replayed_state_sha256": original_state.state_sha256,
        "original_input_sha256": digest_value(original_input),
        "permuted_input_sha256": digest_value(permuted_input),
        "original_projection_sha256": original_projection["projection_sha256"],
        "permuted_projection_sha256": permuted_projection["projection_sha256"],
        "original_semantic_sha256": normalized_sha256,
        "permuted_semantic_sha256": normalized_sha256,
        "identity_neutral_semantics_equal": True,
        "before": before, "after": after,
        "identity_permutation": identity_receipt,
        "external_nonrenamable_identities": {
            "definition": (
                "unchanged source bytes, public-corpus snapshot identities, runtime "
                "implementations, caller request identities, time, and playbook semantics"
            ),
            "classification_policy": [
                {"category": category, "reason": reason}
                for category, reason in sorted(_EXTERNAL_CATEGORY_REASONS.items())
            ],
            "every_identity_classified": True,
            "disjoint_from_changed_identity_domain": True,
            "identity_count": len(external_roster),
            "identity_roster_sha256": digest_value(external_roster),
            "identities": external_roster,
        },
        "independent_replay_binding": independent,
        "original_detail_compact_exact_equal": original_projection == original_compact,
        "permuted_detail_compact_exact_equal": permuted_projection == permuted_compact,
        "expected_original_projection_exact_equal": True,
        "negative_controls": negative_controls,
        "fixed_source_authority_permutation": authority_permutation_receipt,
        "child_runtime": child_runtime,
        "runtime_source_closure": runtime_closure,
        "audit_policy": audit_policy,
        "input_receipt_sha256": digest_value(value),
    }
    return {**material, "receipt_sha256": digest_value(material)}


def main() -> None:
    for line_number, line in enumerate(sys.stdin, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("projection permutation input is not an object")
            result = _process(value)
        except Exception as exc:  # pragma: no cover - sealed evidence path
            raise RuntimeError(
                f"projection permutation input line {line_number} failed: {exc}"
            ) from exc
        sys.stdout.write(
            json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
