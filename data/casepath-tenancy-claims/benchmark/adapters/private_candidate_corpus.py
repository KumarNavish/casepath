"""Strict adapter for the sealed 150-case private synthetic corpus.

The adapter does not import the generator. It authenticates the frozen bytes,
replays every declared digest, and exposes separately named observable and
evaluator values to the autonomous compiler.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import Field, model_validator

from contracts.autonomous import Language, Subtype
from contracts.schema import StrictModel
from manifests.digests import canonical_json_bytes, digest_json

CORPUS_CONTRACT = "casepath.private-candidate-corpus/2.0.0"
ROW_CONTRACT = "casepath.private-candidate-row/2.0.0"
REFERENCE_CONTRACT = "casepath.private-candidate-reference-answer/1.0.0"
GENERATION_RECEIPT_CONTRACT = "casepath.private-candidate-generation-receipt/1.0.0"
COMPLETE_PACKAGE_CONTRACT = "casepath.complete-benchmark-package/1.0.0"
FILE_SET_CONTRACT = "casepath.frozen-complete-benchmark-package-file-set/1.0.0"

_SHA256 = r"^[0-9a-f]{64}$"
_ROW_ID = r"^dpr_[0-9a-f]{24}$"
_ROW_RECEIPT_PATH = "candidate-row-receipt.json"
_OBSERVABLE_PATH = "complete-package/inference/observable-claim.json"
_CANONICAL_PATH = "restricted/canonical-claim.json"
_REFERENCE_PATH = "restricted/reference-answer.json"
_GENERATION_PATH = "restricted/generation-receipt.json"
_PACKAGE_MANIFEST_PATH = "complete-package/complete-package-manifest.json"
_PACKAGE_FILE_SET_PATH = "complete-package/file-set.json"


class CorpusIntegrityError(ValueError):
    """Raised when any source identity or cross-file invariant fails closed."""


class CorpusEntry(StrictModel):
    ordinal: int = Field(ge=1, le=50)
    row_id: str = Field(pattern=_ROW_ID)
    row_sha256: str = Field(pattern=_SHA256)
    subtype: Subtype
    language: Language
    phase: Literal["pilot", "scale"]
    claim_id: str
    relative_path: str = Field(pattern=r"^rows/dpr_[0-9a-f]{24}$")
    row_receipt_sha256: str = Field(pattern=_SHA256)
    complete_package_manifest_sha256: str = Field(pattern=_SHA256)
    complete_package_file_set_sha256: str = Field(pattern=_SHA256)
    canonical_claim_sha256: str = Field(pattern=_SHA256)
    reference_answer_sha256: str = Field(pattern=_SHA256)


class CorpusManifest(StrictModel):
    contract: Literal["casepath.private-candidate-corpus/2.0.0"]
    scope: Literal["full"]
    plan_contract: str
    plan_sha256: str = Field(pattern=_SHA256)
    ledger_contract: str
    ledger_sha256: str = Field(pattern=_SHA256)
    visual_asset_ledger_contract: str
    visual_asset_ledger_sha256: str = Field(pattern=_SHA256)
    visual_ledger_design_time_image_generation_calls: int = Field(ge=0)
    semantic_source_kind: Literal["codex_curated_content_ledger"]
    runtime_model_calls: Literal[0]
    generation_environment: dict[str, Any]
    row_count: Literal[150]
    subtype_counts: dict[Subtype, int]
    language_counts: dict[Language, int]
    publication_eligible: Literal[False]
    distribution_allowed: Literal[False]
    independent_review_status: Literal["not_performed"]
    entries: tuple[CorpusEntry, ...] = Field(min_length=150, max_length=150)
    corpus_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_semantics(self) -> CorpusManifest:
        if self.corpus_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"corpus_sha256"})
        ):
            raise ValueError("corpus manifest semantic hash differs")
        order = [(entry.subtype, entry.ordinal) for entry in self.entries]
        if order != sorted(order):
            raise ValueError("corpus entries are not in canonical subtype/ordinal order")
        if len({entry.row_id for entry in self.entries}) != 150:
            raise ValueError("corpus row IDs are not unique")
        if len({entry.claim_id for entry in self.entries}) != 150:
            raise ValueError("corpus claim IDs are not unique")
        if Counter(entry.subtype for entry in self.entries) != Counter(self.subtype_counts):
            raise ValueError("corpus subtype counts differ")
        if Counter(entry.language for entry in self.entries) != Counter(self.language_counts):
            raise ValueError("corpus language counts differ")
        if set(self.subtype_counts.values()) != {50} or set(self.language_counts.values()) != {75}:
            raise ValueError("corpus is not the expected balanced 150-case source")
        return self


class DeclaredFile(StrictModel):
    relative_path: str
    zone: Literal["complete_package", "restricted"]
    size_bytes: int = Field(ge=1)
    sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_path(self) -> DeclaredFile:
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != self.relative_path:
            raise ValueError("declared file path is unsafe")
        zone = (
            "complete_package"
            if path.parts and path.parts[0] == "complete-package"
            else "restricted"
            if path.parts and path.parts[0] == "restricted"
            else None
        )
        if zone != self.zone:
            raise ValueError("declared file zone differs from its path")
        return self


class RowReceipt(StrictModel):
    contract: Literal["casepath.private-candidate-row/2.0.0"]
    ordinal: int = Field(ge=1, le=50)
    row_id: str = Field(pattern=_ROW_ID)
    row_sha256: str = Field(pattern=_SHA256)
    plan_sha256: str = Field(pattern=_SHA256)
    ledger_sha256: str = Field(pattern=_SHA256)
    visual_asset_ledger_sha256: str = Field(pattern=_SHA256)
    curated_visual_asset_id: str | None
    design_time_image_generation_call_count: Literal[0, 1]
    subtype: Subtype
    language: Language
    phase: Literal["pilot", "scale"]
    claim_id: str
    logical_artifact_count: Literal[11]
    provider_call_count: Literal[0]
    complete_package_manifest_sha256: str = Field(pattern=_SHA256)
    complete_package_file_set_sha256: str = Field(pattern=_SHA256)
    canonical_claim_sha256: str = Field(pattern=_SHA256)
    reference_answer_sha256: str = Field(pattern=_SHA256)
    files: tuple[DeclaredFile, ...] = Field(min_length=14, max_length=14)
    row_receipt_sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def validate_receipt(self) -> RowReceipt:
        paths = [item.relative_path for item in self.files]
        if paths != sorted(paths) or len(set(paths)) != 14:
            raise ValueError("row receipt file paths are not unique and sorted")
        if self.row_receipt_sha256 != digest_json(
            self.model_dump(mode="json", exclude={"row_receipt_sha256"})
        ):
            raise ValueError("row receipt semantic hash differs")
        return self


@dataclass(frozen=True)
class VerifiedCorpusRow:
    entry: CorpusEntry
    receipt: RowReceipt
    observable_claim: dict[str, Any]
    process_graph: dict[str, Any]
    current_process_state: dict[str, Any]
    document_checklist: dict[str, Any]
    intentionally_missing_documents: tuple[str, ...]
    expected_next_action: dict[str, Any]
    hidden_subcategory: str
    reference_answer: dict[str, Any]
    canonical_claim: dict[str, Any]
    source_file_sha256: dict[str, str]


@dataclass(frozen=True)
class VerifiedCorpus:
    root: Path
    manifest: CorpusManifest
    manifest_file_sha256: str
    production_plan_file_sha256: str
    rows: tuple[VerifiedCorpusRow, ...]


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CorpusIntegrityError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise CorpusIntegrityError(f"non-finite JSON constant: {value}")


def _read_json(path: Path) -> tuple[Any, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusIntegrityError(f"cannot read required source file: {path}") from exc
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusIntegrityError(f"invalid JSON source file: {path}") from exc
    return value, raw


def _read_canonical_json(path: Path) -> tuple[Any, bytes]:
    value, raw = _read_json(path)
    if raw != canonical_json_bytes(value):
        raise CorpusIntegrityError(f"JSON source is not canonical bytes: {path}")
    return value, raw


def _safe_file(root: Path, relative_path: str) -> Path:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != relative_path:
        raise CorpusIntegrityError(f"unsafe source path: {relative_path}")
    path = root.joinpath(*relative.parts)
    if path.is_symlink() or not path.is_file():
        raise CorpusIntegrityError(f"source path is not a regular file: {relative_path}")
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise CorpusIntegrityError(f"source path escapes corpus root: {relative_path}") from exc
    return path


def _verify_self_hash(value: dict[str, Any], field: str, label: str) -> None:
    expected = value.get(field)
    payload = dict(value)
    payload.pop(field, None)
    if not isinstance(expected, str) or expected != digest_json(payload):
        raise CorpusIntegrityError(f"{label} semantic hash differs")


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise CorpusIntegrityError(f"invalid JSON pointer: {pointer}")
    current = value
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise CorpusIntegrityError(f"JSON pointer does not resolve: {pointer}")
    return current


def _verify_embedded_file(artifact: dict[str, Any], label: str) -> None:
    required = {"artifact_id", "content_base64", "file_name", "media_type", "sha256", "size_bytes"}
    if set(artifact) != required:
        raise CorpusIntegrityError(f"{label} has an unexpected embedded-file schema")
    try:
        decoded = base64.b64decode(artifact["content_base64"], validate=True)
    except (binascii.Error, ValueError, TypeError) as exc:
        raise CorpusIntegrityError(f"{label} has invalid base64 bytes") from exc
    if len(decoded) != artifact["size_bytes"]:
        raise CorpusIntegrityError(f"{label} embedded size differs")
    if hashlib.sha256(decoded).hexdigest() != artifact["sha256"]:
        raise CorpusIntegrityError(f"{label} embedded digest differs")


def _verify_observable_claim(observable: dict[str, Any], entry: CorpusEntry) -> None:
    if set(observable) != {"attachments", "contract", "customer_message", "submission"}:
        raise CorpusIntegrityError(f"observable claim schema differs: {entry.claim_id}")
    contract = observable["contract"]
    if contract != {
        "complete_downstream_input": True,
        "contains_post_intake_information": False,
        "name": "casepath_observable_claim",
        "rule": "Pass this object—and only this object—to downstream inference.",
        "version": "intake-only/1.2.0",
    }:
        raise CorpusIntegrityError(f"observable boundary contract differs: {entry.claim_id}")
    submission = observable["submission"]
    if submission.get("claim_id") != entry.claim_id or submission.get("language") != entry.language:
        raise CorpusIntegrityError(f"observable identity differs: {entry.claim_id}")
    message = observable["customer_message"]
    _verify_embedded_file(message["raw_file"], f"{entry.claim_id} customer message")
    attachments = observable["attachments"]
    if not isinstance(attachments, list):
        raise CorpusIntegrityError(f"observable attachments are not a list: {entry.claim_id}")
    for index, attachment in enumerate(attachments):
        _verify_embedded_file(attachment, f"{entry.claim_id} attachment {index}")
    attachment_ids = [attachment["artifact_id"] for attachment in attachments]
    if len(set(attachment_ids)) != len(attachment_ids):
        raise CorpusIntegrityError(f"observable attachment IDs repeat: {entry.claim_id}")
    if message.get("attachment_ids") != attachment_ids:
        raise CorpusIntegrityError(f"observable attachment bindings differ: {entry.claim_id}")


def _verify_complete_package(row_root: Path, receipt: RowReceipt) -> None:
    manifest_value, _ = _read_canonical_json(row_root / _PACKAGE_MANIFEST_PATH)
    file_set_value, _ = _read_canonical_json(row_root / _PACKAGE_FILE_SET_PATH)
    if manifest_value.get("contract") != COMPLETE_PACKAGE_CONTRACT:
        raise CorpusIntegrityError("complete-package contract differs")
    if file_set_value.get("contract") != FILE_SET_CONTRACT:
        raise CorpusIntegrityError("complete-package file-set contract differs")
    _verify_self_hash(manifest_value, "manifest_sha256", "complete-package manifest")
    _verify_self_hash(file_set_value, "file_set_sha256", "complete-package file set")
    if manifest_value["manifest_sha256"] != receipt.complete_package_manifest_sha256:
        raise CorpusIntegrityError("row and complete-package manifest hashes differ")
    if file_set_value["file_set_sha256"] != receipt.complete_package_file_set_sha256:
        raise CorpusIntegrityError("row and complete-package file-set hashes differ")
    if file_set_value.get("complete_package_manifest_sha256") != manifest_value["manifest_sha256"]:
        raise CorpusIntegrityError("file set is bound to another package manifest")

    package_root = row_root / "complete-package"
    file_rows = file_set_value.get("files")
    if not isinstance(file_rows, list):
        raise CorpusIntegrityError("complete-package file list is missing")
    listed_paths: set[str] = set()
    for file_row in file_rows:
        relative_path = file_row.get("relative_path")
        if not isinstance(relative_path, str) or relative_path in listed_paths:
            raise CorpusIntegrityError("complete-package file paths repeat or are invalid")
        listed_paths.add(relative_path)
        path = _safe_file(package_root, relative_path)
        raw = path.read_bytes()
        if len(raw) != file_row.get("size_bytes"):
            raise CorpusIntegrityError(f"complete-package file size differs: {relative_path}")
        if hashlib.sha256(raw).hexdigest() != file_row.get("sha256"):
            raise CorpusIntegrityError(f"complete-package file hash differs: {relative_path}")
    actual_paths = {
        relative_path
        for path in package_root.rglob("*")
        if path.is_file()
        and (relative_path := path.relative_to(package_root).as_posix()) != "file-set.json"
    }
    if listed_paths != actual_paths:
        raise CorpusIntegrityError("complete-package file set is incomplete or has extra files")

    artifacts = manifest_value.get("artifacts")
    if not isinstance(artifacts, list):
        raise CorpusIntegrityError("complete-package artifacts are missing")
    artifact_paths: set[str] = set()
    for artifact in artifacts:
        relative_path = artifact.get("relative_path")
        if not isinstance(relative_path, str):
            raise CorpusIntegrityError("complete-package artifact path is invalid")
        artifact_paths.add(relative_path)
        path = _safe_file(package_root, relative_path)
        scope = artifact.get("digest_scope")
        if scope == "exact_file_bytes":
            payload = path.read_bytes()
        elif scope == "canonical_json_value":
            json_value, _ = _read_canonical_json(path)
            pointer = artifact.get("json_pointer")
            selected = json_value if pointer is None else _json_pointer(json_value, pointer)
            payload = canonical_json_bytes(selected)
        else:
            raise CorpusIntegrityError(f"unsupported artifact digest scope: {scope}")
        if len(payload) != artifact.get("size_bytes"):
            raise CorpusIntegrityError(f"logical artifact size differs: {artifact.get('artifact')}")
        if hashlib.sha256(payload).hexdigest() != artifact.get("sha256"):
            raise CorpusIntegrityError(f"logical artifact hash differs: {artifact.get('artifact')}")
    if artifact_paths != listed_paths - {"complete-package-manifest.json"}:
        raise CorpusIntegrityError("logical artifacts do not cover the frozen package files")


def _verify_row_files(row_root: Path, receipt: RowReceipt) -> dict[str, str]:
    declared = {item.relative_path: item for item in receipt.files}
    actual = {
        relative_path
        for path in row_root.rglob("*")
        if path.is_file()
        and (relative_path := path.relative_to(row_root).as_posix()) != _ROW_RECEIPT_PATH
    }
    if actual != set(declared):
        raise CorpusIntegrityError("row receipt file inventory is incomplete or has extra files")
    hashes: dict[str, str] = {}
    for relative_path, item in declared.items():
        path = _safe_file(row_root, relative_path)
        raw = path.read_bytes()
        observed = hashlib.sha256(raw).hexdigest()
        if len(raw) != item.size_bytes or observed != item.sha256:
            raise CorpusIntegrityError(f"row file digest differs: {relative_path}")
        hashes[relative_path] = observed
        if path.suffix == ".json":
            _read_canonical_json(path)
    return hashes


def _scenario_flags(canonical_claim: dict[str, Any]) -> set[str]:
    case_spec = canonical_claim["hidden_ground_truth"]["case_specification"]
    active_flags = set(case_spec["active_flags"])
    true_flags = {
        fact["fact_key"].removeprefix("flag_")
        for fact in case_spec["true_facts"]
        if fact["fact_key"].startswith("flag_") and fact["value"] is True
    }
    if active_flags != true_flags:
        raise CorpusIntegrityError("canonical active flags and true flag facts differ")
    return active_flags


def _verify_cross_file_semantics(
    *,
    entry: CorpusEntry,
    receipt: RowReceipt,
    observable: dict[str, Any],
    graph: dict[str, Any],
    state: dict[str, Any],
    checklist: dict[str, Any],
    intentionally_missing: list[str],
    next_action: dict[str, Any],
    hidden_subcategory: str,
    reference: dict[str, Any],
    canonical: dict[str, Any],
) -> None:
    claim_ids = {
        receipt.claim_id,
        observable["submission"].get("claim_id"),
        reference.get("claim_id"),
        canonical.get("metadata", {}).get("claim_id"),
    }
    if claim_ids != {entry.claim_id}:
        raise CorpusIntegrityError(f"cross-file claim identities differ: {entry.claim_id}")
    graph_ids = {
        graph.get("process_graph_id"),
        state.get("process_graph_id"),
        checklist.get("process_graph_id"),
        reference.get("process_graph_id"),
    }
    if len(graph_ids) != 1:
        raise CorpusIntegrityError(f"cross-file process graph identities differ: {entry.claim_id}")
    case_spec = canonical["hidden_ground_truth"]["case_specification"]
    if {
        case_spec.get("claim_category"),
        reference.get("expected_claim_category"),
        entry.subtype,
    } != {entry.subtype}:
        raise CorpusIntegrityError(f"cross-file subtype identities differ: {entry.claim_id}")
    if {
        case_spec.get("scenario_archetype_id"),
        graph.get("scenario_template_id"),
        reference.get("expected_tenant_law_subcategory"),
        hidden_subcategory,
    } != {hidden_subcategory}:
        raise CorpusIntegrityError(f"cross-file scenario identities differ: {entry.claim_id}")
    if reference.get("expected_next_action") != next_action:
        raise CorpusIntegrityError(f"expected next actions differ: {entry.claim_id}")

    nodes = {node["node_id"]: node for node in graph["nodes"]}
    edges = {edge["edge_id"]: edge for edge in graph["edges"]}
    actual_path = graph["actual_path"]
    actual_nodes = [step["node_id"] for step in actual_path]
    actual_edges = [step["edge_id_from_previous"] for step in actual_path[1:]]
    if actual_nodes != reference.get("expected_process_path_node_ids"):
        raise CorpusIntegrityError(f"reference and graph paths differ: {entry.claim_id}")
    if actual_nodes != case_spec.get("selected_path_node_ids"):
        raise CorpusIntegrityError(f"canonical and graph paths differ: {entry.claim_id}")
    if actual_edges != case_spec.get("selected_path_edge_ids"):
        raise CorpusIntegrityError(f"canonical and graph path edges differ: {entry.claim_id}")
    if actual_nodes[0] != graph.get("start_node_id"):
        raise CorpusIntegrityError(f"actual path does not start at graph start: {entry.claim_id}")
    if actual_nodes[-1] != graph.get("reached_terminal_node_id"):
        raise CorpusIntegrityError(
            f"actual path does not reach declared terminal: {entry.claim_id}"
        )
    if not set(graph.get("terminal_node_ids", ())).issubset(nodes):
        raise CorpusIntegrityError(f"graph terminals are unknown: {entry.claim_id}")
    for previous, current, edge_id in zip(
        actual_nodes[:-1], actual_nodes[1:], actual_edges, strict=True
    ):
        edge = edges.get(edge_id)
        if edge is None or (edge["source_node_id"], edge["target_node_id"]) != (
            previous,
            current,
        ):
            raise CorpusIntegrityError(f"actual path edge is inconsistent: {entry.claim_id}")

    active_flags = _scenario_flags(canonical)
    branch_selections: dict[str, bool] = {}
    for branch in graph["branch_decisions"]:
        matches: list[bool] = []
        for clause in branch["all_of"]:
            if clause.get("operator") != "equals" or type(clause.get("expected_value")) is not bool:
                raise CorpusIntegrityError("branch uses an unsupported non-Boolean comparison")
            observed = clause["fact_key"] in active_flags
            matched = observed is clause["expected_value"]
            if clause.get("observed_value") is not observed or clause.get("matched") is not matched:
                raise CorpusIntegrityError(f"branch clause evaluation differs: {entry.claim_id}")
            matches.append(matched)
        selected = all(matches)
        if branch.get("selected") is not selected:
            raise CorpusIntegrityError(f"branch selection differs: {entry.claim_id}")
        branch_selections[branch["edge_id"]] = selected
    if branch_selections != case_spec.get("branch_conditions"):
        raise CorpusIntegrityError(f"canonical branch map differs: {entry.claim_id}")
    if {edge_id for edge_id, selected in branch_selections.items() if selected} != (
        set(actual_edges) & set(branch_selections)
    ):
        raise CorpusIntegrityError(
            f"selected branch edges and actual path differ: {entry.claim_id}"
        )

    items = checklist["items"]
    item_types = [item["document_type"] for item in items]
    if len(item_types) != len(set(item_types)):
        raise CorpusIntegrityError(f"checklist document types repeat: {entry.claim_id}")
    for requirement_class, top_level_key in (
        ("mandatory", "mandatory_document_types"),
        ("conditional", "conditional_document_types"),
        ("optional", "optional_document_types"),
    ):
        if set(checklist[top_level_key]) != {
            item["document_type"]
            for item in items
            if item["requirement_class"] == requirement_class
        }:
            raise CorpusIntegrityError(f"checklist {top_level_key} differs: {entry.claim_id}")
    missing = {
        item["document_type"]
        for item in items
        if item["status"] in {"requested_missing", "missing_unrequested"}
    }
    if missing != set(checklist["missing_document_types"]):
        raise CorpusIntegrityError(f"checklist missing-document set differs: {entry.claim_id}")
    if missing != set(intentionally_missing):
        raise CorpusIntegrityError(f"intentionally-missing file differs: {entry.claim_id}")
    unnecessary = {
        item["document_type"]
        for item in items
        if item["requirement_class"] == "optional" and item["condition_triggered"]
    }
    if unnecessary != set(checklist["unnecessary_request_document_types"]):
        raise CorpusIntegrityError(f"unnecessary request set differs: {entry.claim_id}")

    active_required = {
        item["document_type"]
        for item in items
        if item["condition_triggered"] and item["requirement_class"] in {"mandatory", "conditional"}
    }
    reference_partition = (
        set(reference["satisfied_document_types"])
        | set(reference["physically_absent_document_types"])
        | set(reference["present_but_insufficient_document_types"])
    )
    if active_required != set(reference["required_document_types"]):
        raise CorpusIntegrityError(f"reference required documents differ: {entry.claim_id}")
    if active_required != reference_partition:
        raise CorpusIntegrityError(
            f"reference document states do not partition requirements: {entry.claim_id}"
        )
    if any(
        left & right
        for index, left in enumerate(
            (
                set(reference["satisfied_document_types"]),
                set(reference["physically_absent_document_types"]),
                set(reference["present_but_insufficient_document_types"]),
            )
        )
        for right in (
            set(reference["satisfied_document_types"]),
            set(reference["physically_absent_document_types"]),
            set(reference["present_but_insufficient_document_types"]),
        )[index + 1 :]
    ):
        raise CorpusIntegrityError(f"reference document states overlap: {entry.claim_id}")

    observable_ids = {
        observable["customer_message"]["message_id"],
        *(attachment["artifact_id"] for attachment in observable["attachments"]),
    }
    if not set(state["source_artifact_ids"]).issubset(observable_ids):
        raise CorpusIntegrityError(
            f"current state cites a non-observable intake artifact: {entry.claim_id}"
        )


def _entry_receipt_bindings(
    entry: CorpusEntry, receipt: RowReceipt, manifest: CorpusManifest
) -> None:
    pairs = (
        (entry.ordinal, receipt.ordinal),
        (entry.row_id, receipt.row_id),
        (entry.row_sha256, receipt.row_sha256),
        (entry.subtype, receipt.subtype),
        (entry.language, receipt.language),
        (entry.phase, receipt.phase),
        (entry.claim_id, receipt.claim_id),
        (entry.row_receipt_sha256, receipt.row_receipt_sha256),
        (entry.complete_package_manifest_sha256, receipt.complete_package_manifest_sha256),
        (entry.complete_package_file_set_sha256, receipt.complete_package_file_set_sha256),
        (entry.canonical_claim_sha256, receipt.canonical_claim_sha256),
        (entry.reference_answer_sha256, receipt.reference_answer_sha256),
        (manifest.plan_sha256, receipt.plan_sha256),
        (manifest.ledger_sha256, receipt.ledger_sha256),
        (manifest.visual_asset_ledger_sha256, receipt.visual_asset_ledger_sha256),
    )
    if any(left != right for left, right in pairs):
        raise CorpusIntegrityError(f"manifest and row receipt bindings differ: {entry.row_id}")


def _verify_production_plan(
    path: Path,
    manifest: CorpusManifest,
    entries: tuple[CorpusEntry, ...],
    expected_file_sha256: str | None,
) -> str:
    if path.is_symlink() or not path.is_file():
        raise CorpusIntegrityError(f"production plan is not a regular file: {path}")
    # The production plan is a human-readable, pretty-printed source file.
    # Its exact raw bytes are pinned by ``expected_file_sha256`` below, while
    # its semantic identity and every row self-hash are recomputed canonically.
    value, raw = _read_json(path)
    file_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_file_sha256 is not None and file_sha256 != expected_file_sha256:
        raise CorpusIntegrityError("production plan file hash differs from the seal")
    if value.get("contract") != manifest.plan_contract:
        raise CorpusIntegrityError("production plan contract differs from the corpus manifest")
    _verify_self_hash(value, "plan_sha256", "production plan")
    if value["plan_sha256"] != manifest.plan_sha256:
        raise CorpusIntegrityError("production plan semantic hash differs from the corpus manifest")
    rows = value.get("rows")
    if not isinstance(rows, list) or len(rows) != 150:
        raise CorpusIntegrityError("production plan does not contain exactly 150 rows")
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise CorpusIntegrityError("production plan row is not an object")
        _verify_self_hash(row, "row_sha256", f"production row {row.get('row_id')}")
        row_id = row.get("row_id")
        if not isinstance(row_id, str) or row_id in rows_by_id:
            raise CorpusIntegrityError("production plan row IDs repeat or are invalid")
        rows_by_id[row_id] = row
    if set(rows_by_id) != {entry.row_id for entry in entries}:
        raise CorpusIntegrityError("production plan and corpus row IDs differ")
    for entry in entries:
        row = rows_by_id[entry.row_id]
        bindings = (
            (row.get("row_sha256"), entry.row_sha256),
            (row.get("ordinal"), entry.ordinal),
            (row.get("subtype"), entry.subtype),
            (row.get("phase"), entry.phase),
            (row.get("controls", {}).get("language"), entry.language),
        )
        if any(left != right for left, right in bindings):
            raise CorpusIntegrityError(f"production row binding differs: {entry.row_id}")
    return file_sha256


def _load_verified_row(
    root: Path, manifest: CorpusManifest, entry: CorpusEntry
) -> VerifiedCorpusRow:
    row_root = root / entry.relative_path
    if row_root.is_symlink() or not row_root.is_dir():
        raise CorpusIntegrityError(f"row is not a regular directory: {entry.row_id}")
    receipt_value, _ = _read_canonical_json(row_root / _ROW_RECEIPT_PATH)
    receipt = RowReceipt.model_validate(receipt_value)
    _entry_receipt_bindings(entry, receipt, manifest)
    file_hashes = _verify_row_files(row_root, receipt)
    _verify_complete_package(row_root, receipt)

    values: dict[str, Any] = {}
    for name, relative_path in {
        "observable": _OBSERVABLE_PATH,
        "graph": "complete-package/evaluator/full-reference-process-graph.json",
        "state": "complete-package/evaluator/current-process-state.json",
        "checklist": "complete-package/evaluator/required-document-checklist.json",
        "missing": "complete-package/evaluator/intentionally-missing-documents.json",
        "next_action": "complete-package/evaluator/expected-next-action.json",
        "subcategory": "complete-package/evaluator/hidden-tenant-law-subcategory.json",
        "reference": _REFERENCE_PATH,
        "canonical": _CANONICAL_PATH,
        "generation": _GENERATION_PATH,
    }.items():
        values[name], _ = _read_canonical_json(row_root / relative_path)

    _verify_observable_claim(values["observable"], entry)
    _verify_self_hash(values["reference"], "reference_answer_sha256", "reference answer")
    _verify_self_hash(values["generation"], "receipt_sha256", "generation receipt")
    if values["reference"].get("contract") != REFERENCE_CONTRACT:
        raise CorpusIntegrityError(f"reference-answer contract differs: {entry.claim_id}")
    if values["generation"].get("contract") != GENERATION_RECEIPT_CONTRACT:
        raise CorpusIntegrityError(f"generation-receipt contract differs: {entry.claim_id}")
    if values["generation"].get("runtime_model_calls") != 0:
        raise CorpusIntegrityError(f"source row used runtime model calls: {entry.claim_id}")
    if values["generation"].get("row_sha256") != entry.row_sha256:
        raise CorpusIntegrityError(f"generation receipt row hash differs: {entry.claim_id}")
    if values["generation"].get("claim_id") != entry.claim_id:
        raise CorpusIntegrityError(f"generation receipt claim differs: {entry.claim_id}")
    if file_hashes[_CANONICAL_PATH] != entry.canonical_claim_sha256:
        raise CorpusIntegrityError(f"canonical claim file hash differs: {entry.claim_id}")
    if values["reference"]["reference_answer_sha256"] != entry.reference_answer_sha256:
        raise CorpusIntegrityError(f"reference answer semantic hash differs: {entry.claim_id}")

    _verify_cross_file_semantics(
        entry=entry,
        receipt=receipt,
        observable=values["observable"],
        graph=values["graph"],
        state=values["state"],
        checklist=values["checklist"],
        intentionally_missing=values["missing"],
        next_action=values["next_action"],
        hidden_subcategory=values["subcategory"],
        reference=values["reference"],
        canonical=values["canonical"],
    )
    return VerifiedCorpusRow(
        entry=entry,
        receipt=receipt,
        observable_claim=values["observable"],
        process_graph=values["graph"],
        current_process_state=values["state"],
        document_checklist=values["checklist"],
        intentionally_missing_documents=tuple(values["missing"]),
        expected_next_action=values["next_action"],
        hidden_subcategory=values["subcategory"],
        reference_answer=values["reference"],
        canonical_claim=values["canonical"],
        source_file_sha256=file_hashes,
    )


def load_verified_corpus(
    root: Path,
    *,
    expected_contract: str,
    expected_corpus_sha256: str,
    expected_manifest_file_sha256: str,
    production_plan_path: Path | None = None,
    expected_plan_file_sha256: str | None = None,
) -> VerifiedCorpus:
    """Authenticate the exact corpus and all 150 row/package/file identities."""

    root = root.resolve()
    if not root.is_dir():
        raise CorpusIntegrityError(f"corpus root is unavailable: {root}")
    manifest_path = _safe_file(root, "corpus-manifest.json")
    manifest_value, manifest_raw = _read_canonical_json(manifest_path)
    manifest_file_sha256 = hashlib.sha256(manifest_raw).hexdigest()
    if manifest_file_sha256 != expected_manifest_file_sha256:
        raise CorpusIntegrityError("corpus manifest file hash differs from the seal")
    manifest = CorpusManifest.model_validate(manifest_value)
    if manifest.contract != expected_contract or manifest.contract != CORPUS_CONTRACT:
        raise CorpusIntegrityError("corpus contract differs from the seal")
    if manifest.corpus_sha256 != expected_corpus_sha256:
        raise CorpusIntegrityError("corpus semantic hash differs from the seal")
    plan_path = production_plan_path or (root.parents[2] / "config/curated-production-plan.v5.json")
    production_plan_file_sha256 = _verify_production_plan(
        plan_path,
        manifest,
        manifest.entries,
        expected_plan_file_sha256,
    )
    rows = tuple(_load_verified_row(root, manifest, entry) for entry in manifest.entries)
    return VerifiedCorpus(
        root=root,
        manifest=manifest,
        manifest_file_sha256=manifest_file_sha256,
        production_plan_file_sha256=production_plan_file_sha256,
        rows=rows,
    )
