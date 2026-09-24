#!/usr/bin/env python3
"""Validate and reconcile the append-only local runtime boot lineage.

This controller is deliberately stdlib-only.  It runs from the already sealed
source capsule before a product child starts, validates every historical boot
against that boot's own sealed capsule, and only then advances the mutable
current-receipt pointer to the unique append-only tip.
"""

from __future__ import annotations

import base64
import csv
from email import policy
from email.parser import BytesParser
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from pathlib import PurePosixPath
import posixpath
import re
import sqlite3
import stat
import subprocess
import sys
import types
import uuid


SHA256 = re.compile(r"[0-9a-f]{64}")
SHA1 = re.compile(r"[0-9a-f]{40}")
BOOT_NAME = re.compile(r"boot-[A-Za-z0-9TZ-]+\.json")
STAGING_NAME = re.compile(
    r"\.(boot-[A-Za-z0-9TZ-]+)\.[0-9]+\.[0-9a-f]{8}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.tmp"
)
POINTER_TEMP_NAME = re.compile(
    r"\.runtime-boot-receipt\.(?:reconcile-)?[0-9]+[.-]"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{12}\.tmp"
)
BOOT_KEYS = {
    "contract",
    "boot_id",
    "ready_at_utc",
    "prior_boot_receipt_file_sha256",
    "url",
    "topology",
    "launcher",
    "process",
    "environment",
    "source",
    "runtime",
    "static",
    "attestation",
    "receipt_sha256",
}
BOOT_KEYS_V22 = BOOT_KEYS | {"runtime_closure"}
RUNTIME_CLOSURE_SECTIONS = {
    "capsule",
    "distribution_integrity",
    "isolated_probe",
    "launch_context",
    "python_runtime",
    "site_packages",
}
RUNTIME_CLAIM_BOUNDARY = (
    "exact_active_capsule_python_entry_real_executable_isolated_path_environment_"
    "and_complete_site_packages;cpython_stdlib_tree_and_original_wheel_archives_"
    "not_captured"
)
ISOLATED_PROBE_PROGRAM = r'''
import importlib.util,json,os,platform,site,sys
names=("fastapi","pydantic","uvicorn")
origins={}
for name in names:
    spec=importlib.util.find_spec(name)
    origins[name]=None if spec is None else spec.origin
value={
    "argv":sys.argv,
    "base_exec_prefix":sys.base_exec_prefix,
    "base_prefix":sys.base_prefix,
    "enable_user_site":site.ENABLE_USER_SITE,
    "environment":dict(os.environ),
    "exec_prefix":sys.exec_prefix,
    "executable":sys.executable,
    "flags":{
        "dont_write_bytecode":bool(sys.flags.dont_write_bytecode),
        "ignore_environment":bool(sys.flags.ignore_environment),
        "isolated":bool(sys.flags.isolated),
        "no_site":bool(sys.flags.no_site),
        "no_user_site":bool(sys.flags.no_user_site),
        "safe_path":bool(sys.flags.safe_path),
    },
    "implementation":sys.implementation.name,
    "cache_tag":sys.implementation.cache_tag,
    "module_origins":origins,
    "path":sys.path,
    "prefix":sys.prefix,
    "python_build":list(platform.python_build()),
    "python_compiler":platform.python_compiler(),
    "python_version":platform.python_version(),
    "version_info":[
        sys.version_info.major,sys.version_info.minor,sys.version_info.micro,
        sys.version_info.releaselevel,sys.version_info.serial,
    ],
}
print(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(",",":")))
'''.strip()
EVENT_KEYS = {
    "contract",
    "session_id",
    "loop_id",
    "sequence",
    "previous_event_sha256",
    "event_type",
    "idempotency_key",
    "command_sha256",
    "command",
    "created_at",
    "event_sha256",
    "resulting_state_sha256",
}
EVENT_TYPES = {
    "casepath.claim-loop-event/1.0.0": {
        "LOOP_CREATED",
        "ACTION_SELECTED",
        "OBSERVATION_INGESTED",
        "EVIDENCE_PROPOSAL_REJECTED",
        "TOOL_UNAVAILABLE",
        "ACTION_DISPATCH_STARTED",
        "DISPATCH_UNKNOWN",
        "CORRECTION_APPLIED",
        "CORRECTION_REUSED",
        "NATIVE_PROPOSAL_REVISION_RECORDED",
    },
    "casepath.claim-loop-protocol-event/1.0.0": {
        "ACTION_DISPATCH_STARTED",
        "PROTOCOL_EXECUTION_STARTED",
        "PROTOCOL_ACTION_RECEIPT_RECORDED",
        "PROTOCOL_SOURCE_OBSERVATION_RECORDED",
        "PROTOCOL_ASSERTION_NORMALIZED",
        "PROTOCOL_INTERPRETATION_RECORDED",
        "PROTOCOL_INTENT_CANCELLED",
        "DISPATCH_UNKNOWN",
        "OBSERVATION_INGESTED",
    },
    "casepath.claim-loop-protocol-event/2.0.0": {
        "PROTOCOL_REPLAN_RECEIPT_RECORDED"
    },
    "casepath.claim-workspace-journal-event/1.0.0": {
        "WORKSPACE_CLAIM_IMPORTED",
        "WORKSPACE_OWNER_ASSIGNED",
        "WORKSPACE_PROCESSING_STARTED",
        "WORKSPACE_UNKNOWN_RECONCILED",
        "WORKSPACE_HANDLER_OBSERVATION_RECORDED",
        "WORKSPACE_HANDLER_OBSERVATION_WITHDRAWN",
        "WORKSPACE_DRAFT_RECORDED",
        "WORKSPACE_REVIEWED_MEMORY_KEPT",
        "WORKSPACE_REVIEWED_MEMORY_APPLIED",
        "WORKSPACE_REVIEWED_MEMORY_RETIRED",
    },
}
LEGACY_ATTESTATION_KEYS = {
    "health_response_sha256",
    "ready_response_sha256",
    "model_ledger_response_sha256",
    "root_html_sha256",
    "workspace_seed_receipt_file_sha256",
    "workspace_seed_receipt_base64",
    "workspace_seed_receipt_sha256",
    "workspace_seed_event_roster_sha256",
    "workspace_response_sha256",
    "workspace_response_base64",
    "workspace_projection_sha256",
    "workspace_state_roster_sha256",
    "workspace_total_count",
    "workspace_authority",
    "workspace_corpus_identity_sha256",
    "credential_configured",
    "model_ledger_records",
    "model_ledger_network_calls",
    "source_reverified_after_ready",
}
DURABLE_ATTESTATION_KEYS = LEGACY_ATTESTATION_KEYS | {
    "durable_event_count",
    "durable_event_roster",
    "durable_event_roster_sha256",
    "durable_registry_file_count",
    "durable_registry_inventory",
    "durable_registry_inventory_sha256",
}


class HistoryError(RuntimeError):
    """A boot-history authority failed closed validation."""


_CAPSULE_CACHE: dict[tuple[str, str, str, str], tuple[Path, str, bytes]] = {}
_RUNTIME_CLOSURE_CACHE: set[str] = set()


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def png_dimensions(raw: bytes, label: str) -> list[int]:
    if (
        len(raw) < 24
        or raw[:8] != b"\x89PNG\r\n\x1a\n"
        or raw[12:16] != b"IHDR"
    ):
        raise HistoryError(f"{label} is not a canonical PNG source asset")
    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    if width < 1 or height < 1:
        raise HistoryError(f"{label} has invalid PNG dimensions")
    return [width, height]


def require_keys(value: object, keys: set[str], label: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise HistoryError(f"{label} schema is not closed")
    return value


def require_sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise HistoryError(f"{label} is not a SHA-256 identity")
    return value


def read_regular(path: Path, label: str) -> tuple[bytes, os.stat_result]:
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise HistoryError(f"{label} is not a regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return b"".join(chunks), metadata
            chunks.append(chunk)
    except OSError as exc:
        raise HistoryError(f"{label} is not a readable regular file") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def stat_regular(path: Path, label: str) -> os.stat_result:
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise HistoryError(f"{label} is not a regular file")
        return metadata
    except OSError as exc:
        raise HistoryError(f"{label} is not a regular file") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def tree_has_posix_acl(root: Path) -> bool:
    if sys.platform.startswith("linux"):
        for candidate in (root, *root.rglob("*")):
            try:
                attributes = os.listxattr(candidate, follow_symlinks=False)
            except OSError as exc:
                raise HistoryError(
                    "capsule ACL authority could not be inspected"
                ) from exc
            if any(
                attribute in {"system.posix_acl_access", "system.posix_acl_default"}
                for attribute in attributes
            ):
                return True
        return False
    if sys.platform != "darwin":
        return False
    try:
        listing = "\n".join(
            (
                subprocess.check_output(
                    ["/bin/ls", "-lde", "--", str(root)],
                    text=True,
                    stderr=subprocess.STDOUT,
                ),
                subprocess.check_output(
                    ["/bin/ls", "-lAeR", "--", str(root)],
                    text=True,
                    stderr=subprocess.STDOUT,
                ),
            )
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HistoryError("capsule ACL authority could not be inspected") from exc
    return bool(
        re.search(r"^[bcdlps-][rwxStTs-]{9}\+", listing, re.MULTILINE)
        or re.search(r"^\s*\d+:\s", listing, re.MULTILINE)
    )


def parse_json(raw: bytes, label: str) -> dict[str, object]:
    def closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, member in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = member
        return value

    try:
        value = json.loads(raw, object_pairs_hook=closed_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HistoryError(f"{label} is not canonical JSON") from exc
    if not isinstance(value, dict):
        raise HistoryError(f"{label} is not an object")
    return value


def valid_relative(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not Path(value).is_absolute()
        and Path(value).as_posix() == value
        and all(part not in {"", ".", ".."} for part in Path(value).parts)
    )


def add_expected(
    expected: dict[str, dict[str, object]],
    relative: str,
    identity: dict[str, object],
    label: str,
) -> None:
    prior = expected.get(relative)
    if prior is not None and prior != identity:
        raise HistoryError(f"capsule authorities conflict for {relative}: {label}")
    expected[relative] = identity


def expected_parent_directories(paths: list[str]) -> list[str]:
    directories: set[str] = set()
    for relative in paths:
        parts = Path(relative).parts
        for index in range(1, len(parts)):
            directories.add(Path(*parts[:index]).as_posix())
    return sorted(directories)


def validate_capsule(
    receipt: dict[str, object], runtime: Path
) -> tuple[Path, str, bytes]:
    source = require_keys(
        receipt.get("source"),
        {
            "repository",
            "git_branch",
            "git_head",
            "execution_root",
            "source_capsule_receipt_file_sha256",
            "source_manifest_path",
            "source_manifest_before_child_sha256",
            "source_manifest_file_sha256",
            "source_manifest_after_ready_sha256",
            "artifact_manifest_file_sha256",
        },
        "boot source",
    )
    manifest_sha = require_sha256(
        source["source_manifest_file_sha256"], "boot source manifest"
    )
    cache_key = (
        str(runtime),
        manifest_sha,
        digest(canonical(source)),
        digest(canonical(receipt.get("static"))),
    )
    capsule_root = runtime / "source-capsules" / manifest_sha
    if (
        source["execution_root"] != str(capsule_root)
        or source["source_manifest_path"] != "casepath/source-manifest.json"
        or capsule_root.is_symlink()
        or not capsule_root.is_dir()
        or stat.S_IMODE(capsule_root.stat().st_mode) != 0o500
    ):
        raise HistoryError("boot source capsule path is invalid")
    if cache_key in _CAPSULE_CACHE:
        return _CAPSULE_CACHE[cache_key]
    if tree_has_posix_acl(capsule_root):
        raise HistoryError("boot source capsule contains an ACL-bearing entry")
    manifest_raw, _ = read_regular(
        capsule_root / "casepath/source-manifest.json", "capsule source manifest"
    )
    if digest(manifest_raw) != manifest_sha:
        raise HistoryError("capsule source manifest bytes drifted")
    manifest = parse_json(manifest_raw, "capsule source manifest")
    manifest_contract = manifest.get("contract")
    manifest = require_keys(
        manifest,
        ({
            "artifact_manifest",
            "contract",
            "file_count",
            "files",
            "gate_count",
            "gates",
            "inventory_policy",
            "release_id",
        } if manifest_contract == "casepath.source-manifest/2.1.0" else {
            "artifact_manifest",
            "contract",
            "file_count",
            "files",
            "gate_count",
            "gates",
            "inventory_policy",
            "release_id",
            "source_commit",
        }),
        "capsule source manifest",
    )
    source_commit = (
        require_keys(
            manifest["source_commit"], {"source", "value"}, "capsule source commit"
        )
        if manifest_contract == "casepath.source-manifest/2.0.0"
        else None
    )
    rows = manifest["files"]
    if (
        manifest_contract
        not in {"casepath.source-manifest/2.0.0", "casepath.source-manifest/2.1.0"}
        or not isinstance(manifest["release_id"], str)
        or not manifest["release_id"]
        or not isinstance(source["git_head"], str)
        or SHA1.fullmatch(source["git_head"]) is None
        or (
            source_commit is not None
            and (
                source_commit["source"] != "CASEPATH_SOURCE_COMMIT"
                or source_commit["value"] != source["git_head"]
            )
        )
        or not isinstance(rows, list)
        or manifest["file_count"] != len(rows)
    ):
        raise HistoryError("capsule source manifest identity is invalid")
    expected: dict[str, dict[str, object]] = {}
    source_paths: list[str] = []
    for raw_row in rows:
        row = require_keys(
            raw_row,
            {"executable", "path", "sha256", "size_bytes"},
            "capsule source row",
        )
        if (
            not valid_relative(row["path"])
            or type(row["executable"]) is not bool
            or not isinstance(row["sha256"], str)
            or SHA256.fullmatch(row["sha256"]) is None
            or type(row["size_bytes"]) is not int
            or row["size_bytes"] < 0
        ):
            raise HistoryError("capsule source row is invalid")
        relative = str(row["path"])
        source_paths.append(relative)
        add_expected(expected, relative, dict(row), "source manifest")
    if source_paths != sorted(source_paths) or len(set(source_paths)) != len(
        source_paths
    ):
        raise HistoryError("capsule source roster is not canonical")
    source_rows_by_path = {row["path"]: row for row in rows}
    source_roots = ["casepath", "casepath-api", "casepath-qa", "docs", "examples"]
    extra_files = [
        ".gitattributes",
        ".gitignore",
        "AGENTS.md",
        "bin/casepath",
        "CONTRIBUTING.md",
        "LICENSE",
        "README.md",
        "THIRD_PARTY_NOTICES.md",
        "CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md",
    ]
    expected_gates = [
        {"path": row["path"], "sha256": row["sha256"]}
        for row in rows
        if row["path"].startswith("casepath-qa/")
        and Path(row["path"]).suffix in {".mjs", ".py"}
        and Path(row["path"]).name.startswith(
            ("browser-", "check-", "reset-", "patch_")
        )
    ]
    if (
        manifest["inventory_policy"]
        != {
            "includes_nonignored_pending_files": True,
            "roots": [*source_roots, *extra_files],
            "self_output_excluded": "casepath/source-manifest.json",
        }
        or manifest["gates"] != expected_gates
        or manifest["gate_count"] != len(expected_gates)
    ):
        raise HistoryError("capsule source inventory/gate authority is invalid")
    add_expected(
        expected,
        "casepath/source-manifest.json",
        {
            "executable": False,
            "path": "casepath/source-manifest.json",
            "sha256": manifest_sha,
            "size_bytes": len(manifest_raw),
        },
        "source manifest",
    )
    artifact_path = "casepath-api/artifacts/artifact-manifest.json"
    artifact_raw, _ = read_regular(
        capsule_root / artifact_path, "capsule artifact manifest"
    )
    artifact_sha = digest(artifact_raw)
    binding = manifest["artifact_manifest"]
    artifact_manifest = require_keys(
        parse_json(artifact_raw, "capsule artifact manifest"),
        {
            "contract",
            "file_count",
            "files",
            "leakage_policy",
            "release_id",
            "source_assets",
            "source_date_epoch",
        },
        "capsule artifact manifest",
    )
    artifact_rows = artifact_manifest.get("files")
    model_visible_rows = [
        {"path": row["path"], "sha256": row["sha256"]}
        for row in artifact_rows
        if isinstance(row, dict) and row.get("model_visible") is True
    ] if isinstance(artifact_rows, list) else []
    expected_leakage_policy = {
        "markers": [
            "benchmark",
            "casepath",
            "demo",
            "dummy",
            "example_domain",
            "expected_action",
            "fictional",
            "generated",
            "ground_truth",
            "hidden_label",
            "reference_answer",
            "sample",
            "scenario_template",
        ],
        "model_visible_files_scanned": len(model_visible_rows),
        "status": "passed",
        "surfaces": [
            "raw bytes",
            "PDF extracted text and metadata",
            "email headers and body",
            "image metadata",
        ],
    }
    if (
        not isinstance(binding, dict)
        or set(binding) != {"model_visible_files", "path", "sha256"}
        or binding.get("path") != artifact_path
        or binding.get("sha256") != artifact_sha
        or binding.get("model_visible_files") != model_visible_rows
        or artifact_manifest["contract"] != "casepath.artifact-manifest/1.0.0"
        or artifact_manifest["release_id"] != manifest["release_id"]
        or artifact_manifest["source_date_epoch"] != 1786406400
        or artifact_manifest["leakage_policy"] != expected_leakage_policy
        or not isinstance(artifact_manifest["source_assets"], list)
        or not isinstance(artifact_rows, list)
        or artifact_manifest.get("file_count") != len(artifact_rows)
        or source["artifact_manifest_file_sha256"] != artifact_sha
    ):
        raise HistoryError("capsule artifact manifest authority is invalid")
    add_expected(
        expected,
        artifact_path,
        {
            "executable": False,
            "path": artifact_path,
            "sha256": artifact_sha,
            "size_bytes": len(artifact_raw),
        },
        "artifact manifest",
    )
    artifact_paths: list[str] = []
    for row in artifact_rows:
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "leakage_scan",
                "media_type",
                "model_visible",
                "path",
                "sha256",
                "size_bytes",
            }
            or not valid_relative(row.get("path"))
            or not isinstance(row.get("sha256"), str)
            or SHA256.fullmatch(row["sha256"]) is None
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] < 0
            or type(row["model_visible"]) is not bool
            or row["leakage_scan"]
            != ("passed" if row["model_visible"] else "not_model_visible")
            or row["media_type"]
            != (mimetypes.guess_type(row["path"])[0] or "application/octet-stream")
        ):
            raise HistoryError("capsule artifact row is invalid")
        artifact_paths.append(row["path"])
        relative = f"casepath-api/artifacts/{row['path']}"
        add_expected(
            expected,
            relative,
            {
                "executable": False,
                "path": relative,
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
            },
            "artifact manifest",
        )
    if artifact_paths != sorted(artifact_paths) or len(set(artifact_paths)) != len(
        artifact_paths
    ):
        raise HistoryError("capsule artifact roster is not canonical")
    source_asset_paths: list[str] = []
    for asset in artifact_manifest["source_assets"]:
        asset = require_keys(
            asset, {"dimensions", "path", "sha256"}, "artifact source asset"
        )
        dimensions = asset["dimensions"]
        if (
            not valid_relative(asset["path"])
            or not isinstance(asset["sha256"], str)
            or SHA256.fullmatch(asset["sha256"]) is None
            or not isinstance(dimensions, list)
            or len(dimensions) != 2
            or any(type(value) is not int or value < 1 for value in dimensions)
        ):
            raise HistoryError("artifact source asset is invalid")
        source_asset_paths.append(asset["path"])
        authority = source_rows_by_path.get(asset["path"])
        if not isinstance(authority, dict) or authority.get("sha256") != asset["sha256"]:
            raise HistoryError("artifact source asset lacks sealed source authority")
        asset_raw, _ = read_regular(
            capsule_root / asset["path"], "artifact source asset"
        )
        if digest(asset_raw) != asset["sha256"] or png_dimensions(
            asset_raw, "artifact source asset"
        ) != dimensions:
            raise HistoryError("artifact source asset bytes or dimensions differ")
    if source_asset_paths != sorted(source_asset_paths) or len(
        set(source_asset_paths)
    ) != len(source_asset_paths):
        raise HistoryError("artifact source-asset roster is not canonical")
    static = require_keys(
        receipt.get("static"),
        {
            "inventory",
            "inventory_sha256",
            "inventory_before_child_sha256",
            "inventory_after_ready_sha256",
            "deployment_file_sha256",
        },
        "boot static authority",
    )
    static_inventory = static["inventory"]
    if not isinstance(static_inventory, list) or not static_inventory:
        raise HistoryError("boot static inventory is empty")
    static_rows: list[dict[str, object]] = []
    static_paths: list[str] = []
    for raw_row in static_inventory:
        row = require_keys(
            raw_row, {"path", "sha256", "bytes"}, "boot static row"
        )
        if (
            not valid_relative(row["path"])
            or not isinstance(row["sha256"], str)
            or SHA256.fullmatch(row["sha256"]) is None
            or type(row["bytes"]) is not int
            or row["bytes"] < 0
        ):
            raise HistoryError("boot static row is invalid")
        relative = f"casepath-public/{row['path']}"
        read_regular(capsule_root / relative, "capsule static file")
        authored_row = source_rows_by_path.get(f"casepath/{row['path']}")
        expected_executable = (
            False if row["path"] == "deployment.json" else None
        )
        if row["path"] != "deployment.json" and isinstance(authored_row, dict):
            expected_executable = authored_row.get("executable")
            if (
                authored_row.get("sha256") != row["sha256"]
                or authored_row.get("size_bytes") != row["bytes"]
            ):
                raise HistoryError(
                    f"boot static row differs from authored source: {row['path']}"
                )
        if type(expected_executable) is not bool:
            raise HistoryError(
                f"boot static row lacks authored authority: {row['path']}"
            )
        identity = {
            "executable": expected_executable,
            "path": relative,
            "sha256": row["sha256"],
            "size_bytes": row["bytes"],
        }
        add_expected(expected, relative, identity, "boot static inventory")
        static_rows.append(
            {
                "path": row["path"],
                "sha256": row["sha256"],
                "size_bytes": row["bytes"],
                "executable": identity["executable"],
            }
        )
        static_paths.append(row["path"])
    if static_paths != sorted(static_paths) or len(set(static_paths)) != len(
        static_paths
    ):
        raise HistoryError("boot static roster is not canonical")
    if (
        static["inventory_sha256"] != digest(canonical(static_inventory))
        or static["inventory_before_child_sha256"] != static["inventory_sha256"]
        or static["inventory_after_ready_sha256"] != static["inventory_sha256"]
        or static["deployment_file_sha256"]
        != next(
            (row["sha256"] for row in static_inventory if row["path"] == "deployment.json"),
            None,
        )
    ):
        raise HistoryError("boot static identity is invalid")
    release_raw, _ = read_regular(
        capsule_root / "casepath/release.json", "capsule release identity"
    )
    deployment_raw, _ = read_regular(
        capsule_root / "casepath-public/deployment.json",
        "capsule deployment identity",
    )
    release = parse_json(release_raw, "capsule release identity")
    deployment = parse_json(deployment_raw, "capsule deployment identity")
    frontend = release.get("components", {}).get("frontend", {})
    if (
        release.get("release_id") != manifest["release_id"]
        or deployment.get("contract")
        != "casepath.deployment-identity/1.0.0"
        or deployment.get("alignment_eligible") is not True
        or deployment.get("source_commit") != source["git_head"]
        or deployment.get("release_id") != manifest["release_id"]
        or deployment.get("component_version") != frontend.get("version")
        or deployment.get("component_contract") != frontend.get("contract")
    ):
        raise HistoryError("capsule release/deployment identity is invalid")
    capsule_receipt_raw, _ = read_regular(
        capsule_root / "CAPSULE_RECEIPT.json", "capsule receipt"
    )
    capsule_receipt = require_keys(
        parse_json(capsule_receipt_raw, "capsule receipt"),
        {
            "contract",
            "source_manifest_file_sha256",
            "source_roster_sha256",
            "source_file_count",
            "artifact_manifest_file_sha256",
            "artifact_file_count",
            "static_inventory_sha256",
            "static_file_count",
            "receipt_sha256",
        },
        "capsule receipt",
    )
    capsule_semantic = dict(capsule_receipt)
    capsule_receipt_sha = capsule_semantic.pop("receipt_sha256")
    if (
        source["source_capsule_receipt_file_sha256"]
        != digest(capsule_receipt_raw)
        or capsule_receipt["contract"] != "casepath.sealed-source-capsule/1.0.0"
        or capsule_receipt_sha != digest(canonical(capsule_semantic))
        or capsule_receipt["source_manifest_file_sha256"] != manifest_sha
        or capsule_receipt["source_roster_sha256"] != digest(canonical(rows))
        or capsule_receipt["source_file_count"] != len(rows)
        or capsule_receipt["artifact_manifest_file_sha256"] != artifact_sha
        or capsule_receipt["artifact_file_count"] != len(artifact_rows)
        or capsule_receipt["static_inventory_sha256"] != digest(canonical(static_rows))
        or capsule_receipt["static_file_count"] != len(static_rows)
    ):
        raise HistoryError("capsule receipt is invalid")
    add_expected(
        expected,
        "CAPSULE_RECEIPT.json",
        {
            "executable": False,
            "path": "CAPSULE_RECEIPT.json",
            "sha256": digest(capsule_receipt_raw),
            "size_bytes": len(capsule_receipt_raw),
        },
        "capsule receipt",
    )
    actual_files: list[str] = []
    actual_directories: list[str] = []
    for candidate in sorted(capsule_root.rglob("*")):
        metadata = candidate.lstat()
        relative = candidate.relative_to(capsule_root).as_posix()
        if candidate.is_symlink() or (
            not stat.S_ISREG(metadata.st_mode)
            and not stat.S_ISDIR(metadata.st_mode)
        ):
            raise HistoryError(f"capsule contains an invalid entry: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            if stat.S_IMODE(metadata.st_mode) != 0o500:
                raise HistoryError(
                    f"capsule directory mode is noncanonical: {relative}"
                )
            actual_directories.append(relative)
        else:
            if metadata.st_nlink != 1:
                raise HistoryError(
                    f"capsule contains an externally linked file: {relative}"
                )
            actual_files.append(relative)
    # pathlib orders by path components, whereas the sealed rosters are ordered
    # by canonical POSIX strings.  Prefix siblings such as ``casepath`` and
    # ``casepath-api`` therefore need an explicit canonical sort after walking.
    actual_files.sort()
    actual_directories.sort()
    if actual_files != sorted(expected) or actual_directories != expected_parent_directories(
        sorted(expected)
    ):
        raise HistoryError("capsule file or directory roster is not exact")
    for relative, identity in expected.items():
        raw, metadata = read_regular(capsule_root / relative, "capsule file")
        expected_mode = 0o555 if identity["executable"] else 0o444
        observed = {
            "executable": bool(metadata.st_mode & stat.S_IXUSR),
            "path": relative,
            "sha256": digest(raw),
            "size_bytes": len(raw),
        }
        if observed != identity or stat.S_IMODE(metadata.st_mode) != expected_mode:
            raise HistoryError(f"capsule file differs from authority: {relative}")
    result = (capsule_root, digest(canonical(rows)), manifest_raw)
    _CAPSULE_CACHE[cache_key] = result
    return result


def expected_environment(
    runtime: Path, data_root: Path, capsule: Path, source_commit: str
) -> dict[str, str]:
    return {
        "CASEPATH_ARTIFACT_REGISTRY_PATH": str(data_root / "artifact-registry"),
        "CASEPATH_DB_PATH": str(data_root / "casepath.db"),
        "CASEPATH_LOCAL_RUNTIME_RECEIPT": str(
            runtime / "runtime-boot-receipt.json"
        ),
        "CASEPATH_LOCAL_STATIC_ROOT": str(capsule / "casepath-public"),
        "CASEPATH_MODEL_MODE": "deterministic_reference",
        "CASEPATH_SOURCE_COMMIT": source_commit,
        "HOME": str(runtime / "home"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": ":".join(
            (
                str(runtime / "venv/bin"),
                "/usr/local/bin",
                "/usr/bin",
                "/bin",
                "/usr/sbin",
                "/sbin",
            )
        ),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPYCACHEPREFIX": str(runtime / "pycache"),
        "PYTHONSAFEPATH": "1",
        "SOURCE_DATE_EPOCH": "1786406400",
        "TMPDIR": str(runtime / "tmp"),
        "TZ": "UTC",
        "LANGCHAIN_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
        "LANGSMITH_TRACING": "false",
    }


def validate_durable_attestation(attestation: dict[str, object]) -> None:
    events = attestation.get("durable_event_roster")
    registry = attestation.get("durable_registry_inventory")
    if (
        not isinstance(events, list)
        or attestation.get("durable_event_count") != len(events)
        or attestation.get("durable_event_roster_sha256") != digest(canonical(events))
        or not isinstance(registry, list)
        or attestation.get("durable_registry_file_count") != len(registry)
        or attestation.get("durable_registry_inventory_sha256")
        != digest(canonical(registry))
    ):
        raise HistoryError("durable boot attestation is invalid")
    event_keys: list[tuple[str, str, int]] = []
    for row in events:
        row = require_keys(
            row,
            {
                "session_id",
                "loop_id",
                "sequence",
                "event_sha256",
                "event_json_sha256",
            },
            "durable event row",
        )
        if (
            not isinstance(row["session_id"], str)
            or not isinstance(row["loop_id"], str)
            or type(row["sequence"]) is not int
            or row["sequence"] < 1
            or not isinstance(row["event_sha256"], str)
            or SHA256.fullmatch(row["event_sha256"]) is None
            or not isinstance(row["event_json_sha256"], str)
            or SHA256.fullmatch(row["event_json_sha256"]) is None
        ):
            raise HistoryError("durable event row is invalid")
        event_keys.append((row["session_id"], row["loop_id"], row["sequence"]))
    if event_keys != sorted(event_keys) or len(set(event_keys)) != len(event_keys):
        raise HistoryError("durable event roster is not canonical")
    registry_paths: list[str] = []
    for row in registry:
        row = require_keys(
            row, {"path", "sha256", "size_bytes"}, "durable registry row"
        )
        if (
            not valid_relative(row["path"])
            or not isinstance(row["sha256"], str)
            or SHA256.fullmatch(row["sha256"]) is None
            or type(row["size_bytes"]) is not int
            or row["size_bytes"] < 0
        ):
            raise HistoryError("durable registry row is invalid")
        registry_paths.append(row["path"])
    if registry_paths != sorted(registry_paths) or len(set(registry_paths)) != len(
        registry_paths
    ):
        raise HistoryError("durable registry roster is not canonical")


def validate_embedded_workspace(
    receipt: dict[str, object], source_roster_sha: str
) -> None:
    source = receipt["source"]
    attestation = receipt["attestation"]
    try:
        seed_raw = base64.b64decode(
            attestation["workspace_seed_receipt_base64"], validate=True
        )
        workspace_raw = base64.b64decode(
            attestation["workspace_response_base64"], validate=True
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HistoryError("embedded workspace bytes are invalid") from exc
    if (
        base64.b64encode(seed_raw).decode("ascii")
        != attestation["workspace_seed_receipt_base64"]
        or base64.b64encode(workspace_raw).decode("ascii")
        != attestation["workspace_response_base64"]
    ):
        raise HistoryError("embedded workspace Base64 is not canonical")
    seed = require_keys(
        parse_json(seed_raw, "embedded seed receipt"),
        {"contract", "seed_receipt", "source_authority", "receipt_sha256"},
        "embedded seed receipt",
    )
    authority = require_keys(
        seed["source_authority"],
        {
            "contract",
            "source_manifest_file_sha256",
            "source_manifest_roster_sha256",
        },
        "embedded seed source authority",
    )
    inner = require_keys(
        seed["seed_receipt"],
        {
            "contract",
            "corpus_identity",
            "claim_count",
            "new_import_count",
            "replayed_import_count",
            "event_roster_sha256",
            "timestamp",
            "model_calls",
            "provider_calls",
            "credential_reads",
            "cost_usd",
            "receipt_sha256",
        },
        "embedded seed result",
    )
    seed_semantic = dict(seed)
    seed_sha = seed_semantic.pop("receipt_sha256")
    inner_semantic = dict(inner)
    inner_sha = inner_semantic.pop("receipt_sha256")
    corpus_identity = inner.get("corpus_identity")
    expected_claim_count = (
        corpus_identity.get("claim_count")
        if isinstance(corpus_identity, dict)
        else None
    )
    workspace = parse_json(workspace_raw, "embedded workspace")
    workspace_semantic = dict(workspace)
    projection_sha = workspace_semantic.pop("projection_sha256", None)
    if (
        seed["contract"] != "casepath.sealed-workspace-seed/1.0.0"
        or seed_sha != digest(canonical(seed_semantic))
        or authority["contract"]
        != "casepath.sealed-seed-source-authority/1.0.0"
        or authority["source_manifest_file_sha256"]
        != source["source_manifest_file_sha256"]
        or authority["source_manifest_roster_sha256"] != source_roster_sha
        or inner["contract"] != "casepath.claim-workspace-seed/1.0.0"
        or inner_sha != digest(canonical(inner_semantic))
        or type(expected_claim_count) is not int
        or expected_claim_count <= 0
        or inner["claim_count"] != expected_claim_count
        or inner["new_import_count"] + inner["replayed_import_count"]
        != expected_claim_count
        or any(
            inner[field] != 0
            for field in (
                "model_calls",
                "provider_calls",
                "credential_reads",
                "cost_usd",
            )
        )
        or digest(seed_raw) != attestation["workspace_seed_receipt_file_sha256"]
        or seed_sha != attestation["workspace_seed_receipt_sha256"]
        or inner["event_roster_sha256"]
        != attestation["workspace_seed_event_roster_sha256"]
        or digest(workspace_raw) != attestation["workspace_response_sha256"]
        or workspace.get("contract")
        not in {
            "casepath.claim-queue-projection/1.0.0",
            "casepath.claim-queue-projection/2.0.0",
        }
        or projection_sha != digest(canonical(workspace_semantic))
        or projection_sha != attestation["workspace_projection_sha256"]
        or workspace.get("state_roster_sha256")
        != attestation["workspace_state_roster_sha256"]
        or workspace.get("total_count") != expected_claim_count
        or workspace.get("total_count") != attestation["workspace_total_count"]
        or workspace.get("authority") != "claim_loop_events"
        or workspace.get("authority") != attestation["workspace_authority"]
        or digest(canonical(workspace.get("corpus_identity")))
        != attestation["workspace_corpus_identity_sha256"]
        or workspace.get("corpus_identity") != inner.get("corpus_identity")
    ):
        raise HistoryError("embedded workspace attestation is invalid")


def validate_closure_hash(
    value: object, keys: set[str], label: str
) -> dict[str, object]:
    closed = require_keys(value, keys | {"closure_sha256"}, label)
    semantic = dict(closed)
    stated = semantic.pop("closure_sha256")
    if require_sha256(stated, f"{label} closure") != digest(canonical(semantic)):
        raise HistoryError(f"{label} self-hash is invalid")
    return closed


def validate_closure_entry(
    row_value: object, candidate: Path, display_path: str, label: str
) -> None:
    if not isinstance(row_value, dict):
        raise HistoryError(f"{label} entry is not an object")
    kind = row_value.get("kind")
    common = {"gid", "kind", "mode", "path", "uid"}
    if kind == "directory":
        row = require_keys(row_value, common, label)
    elif kind == "file":
        row = require_keys(row_value, common | {"sha256", "size_bytes"}, label)
    elif kind == "symlink":
        row = require_keys(
            row_value,
            common | {"target", "target_sha256", "target_size_bytes"},
            label,
        )
    else:
        raise HistoryError(f"{label} entry kind is invalid")
    metadata = candidate.lstat()
    if (
        row["path"] != display_path
        or row["mode"] != stat.S_IMODE(metadata.st_mode)
        or row["uid"] != metadata.st_uid
        or row["gid"] != metadata.st_gid
    ):
        raise HistoryError(f"{label} metadata differs from disk")
    if kind == "directory":
        if not stat.S_ISDIR(metadata.st_mode):
            raise HistoryError(f"{label} is not a directory")
        return
    if kind == "file":
        raw, observed = read_regular(candidate, label)
        if (
            not stat.S_ISREG(observed.st_mode)
            or row["size_bytes"] != len(raw)
            or require_sha256(row["sha256"], f"{label} hash") != digest(raw)
        ):
            raise HistoryError(f"{label} file identity differs from disk")
        return
    if not stat.S_ISLNK(metadata.st_mode):
        raise HistoryError(f"{label} is not a symlink")
    target = os.readlink(candidate)
    target_raw = os.fsencode(target)
    if (
        row["target"] != target
        or row["target_size_bytes"] != len(target_raw)
        or row["target_sha256"] != digest(target_raw)
    ):
        raise HistoryError(f"{label} symlink identity differs from disk")


def validate_tree_closure(
    value: object,
    expected_root: Path,
    label: str,
    *,
    reject_symlinks: bool = False,
) -> dict[str, object]:
    section = validate_closure_hash(
        value,
        {"root", "entry_count", "roster", "roster_sha256"},
        label,
    )
    root = expected_root.resolve()
    if (
        section["root"] != str(root)
        or expected_root.is_symlink()
        or not expected_root.is_dir()
        or root != expected_root
    ):
        raise HistoryError(f"{label} root is invalid")
    roster = section["roster"]
    if (
        not isinstance(roster, list)
        or section["entry_count"] != len(roster)
        or section["roster_sha256"] != digest(canonical(roster))
    ):
        raise HistoryError(f"{label} roster authority is invalid")
    actual = [root, *sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())]
    expected_paths = [".", *[item.relative_to(root).as_posix() for item in actual[1:]]]
    stated_paths = [row.get("path") if isinstance(row, dict) else None for row in roster]
    if stated_paths != expected_paths or len(set(expected_paths)) != len(expected_paths):
        raise HistoryError(f"{label} path roster is not exact")
    for row, candidate, relative in zip(roster, actual, expected_paths, strict=True):
        validate_closure_entry(row, candidate, relative, f"{label} {relative}")
        if reject_symlinks and row["kind"] == "symlink":
            raise HistoryError(f"{label} contains a symlink")
    return section


def normalize_distribution(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def validate_distribution_closure(
    value: object,
    site_section: dict[str, object],
    runtime: Path,
    capsule: Path,
) -> dict[str, object]:
    stored = validate_closure_hash(
        value,
        {
            "contract",
            "site_packages",
            "locked_pins",
            "dist_info_instance_count",
            "dist_info_instances",
            "dist_info_instances_sha256",
            "record_owned_path_count",
            "record_ownership",
            "record_ownership_sha256",
            "allowed_unowned_bytecode_count",
            "allowed_unowned_bytecode_sha256",
            "bootstrap_unowned_paths",
            "bootstrap_unowned_paths_sha256",
            "virtualenv_pth",
            "installed_distributions",
            "installed_distributions_sha256",
            "provenance_boundary",
        },
        "runtime distribution closure",
    )
    venv = runtime / "venv"
    site_packages = venv / "lib/python3.13/site-packages"
    if (
        stored["contract"] != "casepath.python-distribution-record-closure/1.0.0"
        or stored["site_packages"] != str(site_packages)
        or stored["provenance_boundary"]
        != (
            "installed_bytes_and_dist_info_RECORD_sha256_only;"
            "original_wheel_archive_hashes_not_captured"
        )
    ):
        raise HistoryError("runtime distribution closure boundary is invalid")
    requirements_raw, _ = read_regular(
        capsule / "casepath-api/requirements.lock", "capsule requirements lock"
    )
    locked_pins: dict[str, str] = {}
    for raw_line in requirements_raw.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("==") != 1:
            raise HistoryError("capsule requirements lock has an unpinned row")
        name, version = line.split("==", 1)
        normalized = normalize_distribution(name)
        if not normalized or not version or normalized in locked_pins:
            raise HistoryError("capsule requirements lock duplicates a package")
        locked_pins[normalized] = version

    site_prefix = site_packages.relative_to(venv).as_posix()
    site_file_rows = {
        posixpath.join(site_prefix, row["path"]): row
        for row in site_section["roster"]
        if row["kind"] == "file"
    }
    captured_dist_info = sorted(
        row["path"]
        for row in site_section["roster"]
        if row["kind"] == "directory" and row["path"].endswith(".dist-info")
    )
    direct_dist_info = sorted(site_packages.glob("*.dist-info"))
    if captured_dist_info != [candidate.name for candidate in direct_dist_info]:
        raise HistoryError("runtime contains a noncanonical dist-info instance")
    ownership: dict[str, str] = {}
    normalized_instances: set[str] = set()
    instances: list[dict[str, object]] = []
    for dist_info in direct_dist_info:
        metadata_raw, _ = read_regular(dist_info / "METADATA", "dist-info METADATA")
        record_raw, _ = read_regular(dist_info / "RECORD", "dist-info RECORD")
        message = BytesParser(policy=policy.default).parsebytes(metadata_raw)
        name = message.get("Name")
        version = message.get("Version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise HistoryError("dist-info metadata lacks name or version")
        normalized_name = normalize_distribution(name)
        if normalized_name in normalized_instances:
            raise HistoryError("runtime duplicates a normalized distribution")
        normalized_instances.add(normalized_name)
        if locked_pins.get(normalized_name) != version:
            raise HistoryError("runtime distribution differs from requirements lock")
        record_relative = (
            site_packages / dist_info.name / "RECORD"
        ).relative_to(venv).as_posix()
        record_paths: set[str] = set()
        record_rows: list[dict[str, object]] = []
        try:
            decoded = record_raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HistoryError("dist-info RECORD is not UTF-8") from exc
        for csv_row in csv.reader(decoded.splitlines()):
            if len(csv_row) != 3:
                raise HistoryError("dist-info RECORD row is malformed")
            relative, hash_field, size_field = csv_row
            if not relative or "\\" in relative or PurePosixPath(relative).is_absolute():
                raise HistoryError("dist-info RECORD path is invalid")
            normalized_path = posixpath.normpath(
                posixpath.join(site_prefix, relative)
            )
            if normalized_path == ".." or normalized_path.startswith("../"):
                raise HistoryError("dist-info RECORD path escapes venv")
            if normalized_path in record_paths or normalized_path in ownership:
                raise HistoryError("dist-info RECORD ownership is duplicated")
            record_paths.add(normalized_path)
            captured = site_file_rows.get(normalized_path)
            if captured is None:
                target_raw, _ = read_regular(
                    venv / normalized_path, "dist-info RECORD target"
                )
                target_sha = digest(target_raw)
                target_size = len(target_raw)
            else:
                target_sha = captured["sha256"]
                target_size = captured["size_bytes"]
            if normalized_path == record_relative:
                if hash_field or size_field:
                    raise HistoryError("dist-info RECORD self-row is not canonical")
            else:
                expected_hash = base64.urlsafe_b64encode(
                    bytes.fromhex(target_sha)
                ).rstrip(b"=").decode("ascii")
                if (
                    hash_field != f"sha256={expected_hash}"
                    or not size_field.isdecimal()
                    or int(size_field) != target_size
                ):
                    raise HistoryError("dist-info RECORD target differs from authority")
            ownership[normalized_path] = dist_info.name
            record_rows.append(
                {"hash": hash_field, "path": normalized_path, "size": size_field}
            )
        record_rows.sort(key=lambda row: row["path"])
        instances.append(
            {
                "dist_info": dist_info.name,
                "metadata_sha256": digest(metadata_raw),
                "name": name,
                "normalized_name": normalized_name,
                "record_entry_count": len(record_rows),
                "record_roster_sha256": digest(canonical(record_rows)),
                "record_sha256": digest(record_raw),
                "version": version,
            }
        )
    instances.sort(
        key=lambda row: (row["normalized_name"], row["version"], row["dist_info"])
    )
    if len(instances) != len(locked_pins) or [
        row["normalized_name"] for row in instances
    ] != sorted(locked_pins):
        raise HistoryError("runtime dist-info instances are not exact")

    bootstrap_unowned = sorted(
        {
            f"{site_prefix}/_virtualenv.pth",
            f"{site_prefix}/_virtualenv.py",
        }
    )
    unowned = sorted(set(site_file_rows) - set(ownership))
    unowned_bytecode = sorted(
        relative
        for relative in unowned
        if "/__pycache__/" in f"/{relative}" and relative.endswith(".pyc")
    )
    for relative in unowned_bytecode:
        pure = PurePosixPath(relative)
        cache_index = pure.parts.index("__pycache__")
        match = re.fullmatch(
            r"(.+)\.cpython-313(?:(?:\.opt-[12])|(?:-pytest-[0-9]+\.[0-9]+\.[0-9]+))?\.pyc",
            pure.name,
        )
        if match is None:
            raise HistoryError("runtime contains noncanonical unowned bytecode")
        source = PurePosixPath(
            *pure.parts[:cache_index], f"{match.group(1)}.py"
        ).as_posix()
        if source not in ownership and source != f"{site_prefix}/_virtualenv.py":
            raise HistoryError("runtime bytecode lacks source authority")
    if set(unowned) != set(bootstrap_unowned) | set(unowned_bytecode):
        raise HistoryError("runtime contains an unowned importable file")
    pth = site_packages / "_virtualenv.pth"
    pth_raw, pth_metadata = read_regular(pth, "_virtualenv.pth")
    if pth_raw != b"import _virtualenv":
        raise HistoryError("runtime _virtualenv.pth is not exact")
    injection_paths = []
    for row in site_section["roster"]:
        relative = str(row["path"])
        lowered = relative.lower()
        basename = PurePosixPath(lowered).name
        parts = PurePosixPath(lowered).parts
        if (
            lowered.endswith(".egg-link")
            or any(part.endswith(".egg") for part in parts)
            or ".egg-info/" in lowered
            or lowered.endswith(".egg-info")
            or basename.startswith("__editable__")
            or basename in {"direct_url.json", "easy-install.pth"}
            or (lowered.endswith(".pth") and relative != "_virtualenv.pth")
            or any(part in {".git", ".hg", ".svn"} for part in parts)
            or any(
                part in {"sitecustomize", "usercustomize"}
                or part.startswith("sitecustomize.")
                or part.startswith("usercustomize.")
                for part in parts
            )
            or "casepath-eval" in lowered
            or "casepath_eval" in lowered
        ):
            injection_paths.append(relative)
    if injection_paths:
        raise HistoryError("runtime contains an injection or editable artifact")
    ownership_rows = [
        {"dist_info": owner, "path": relative}
        for relative, owner in sorted(ownership.items())
    ]
    distributions = sorted(
        [f"{row['name']}=={row['version']}" for row in instances],
        key=lambda item: (item.casefold(), item),
    )
    material = {
        "contract": "casepath.python-distribution-record-closure/1.0.0",
        "site_packages": str(site_packages),
        "locked_pins": [
            {"name": name, "version": version}
            for name, version in sorted(locked_pins.items())
        ],
        "dist_info_instance_count": len(instances),
        "dist_info_instances": instances,
        "dist_info_instances_sha256": digest(canonical(instances)),
        "record_owned_path_count": len(ownership_rows),
        "record_ownership": ownership_rows,
        "record_ownership_sha256": digest(canonical(ownership_rows)),
        "allowed_unowned_bytecode_count": len(unowned_bytecode),
        "allowed_unowned_bytecode_sha256": digest(canonical(unowned_bytecode)),
        "bootstrap_unowned_paths": bootstrap_unowned,
        "bootstrap_unowned_paths_sha256": digest(canonical(bootstrap_unowned)),
        "virtualenv_pth": {
            "path": f"{site_prefix}/_virtualenv.pth",
            "mode": stat.S_IMODE(pth_metadata.st_mode),
            "uid": pth_metadata.st_uid,
            "gid": pth_metadata.st_gid,
            "sha256": digest(pth_raw),
            "size_bytes": len(pth_raw),
            "exact_utf8": "import _virtualenv",
        },
        "installed_distributions": distributions,
        "installed_distributions_sha256": digest(canonical(distributions)),
        "provenance_boundary": (
            "installed_bytes_and_dist_info_RECORD_sha256_only;"
            "original_wheel_archive_hashes_not_captured"
        ),
    }
    expected = {**material, "closure_sha256": digest(canonical(material))}
    if stored != expected:
        raise HistoryError("runtime distribution closure differs from disk")
    return stored


def validate_runtime_closure(
    receipt: dict[str, object], runtime: Path, data_root: Path, repository: Path, capsule: Path
) -> str:
    wrapper = require_keys(
        receipt["runtime_closure"],
        {
            "contract",
            "baseline",
            "baseline_closure_sha256",
            "phases",
            "phase_closure_equality",
        },
        "boot runtime closure",
    )
    baseline = validate_closure_hash(
        wrapper["baseline"],
        {"contract", "claim_boundary", "sections", "subordinate_closure_sha256"},
        "runtime closure baseline",
    )
    sections = require_keys(
        baseline["sections"], RUNTIME_CLOSURE_SECTIONS, "runtime closure sections"
    )
    subordinate = require_keys(
        baseline["subordinate_closure_sha256"],
        RUNTIME_CLOSURE_SECTIONS,
        "runtime subordinate hashes",
    )
    if (
        wrapper["contract"] != "casepath.boot-runtime-closure/1.0.0"
        or wrapper["phase_closure_equality"] is not True
        or baseline["contract"] != "casepath.executable-runtime-closure/1.1.0"
        or baseline["claim_boundary"] != RUNTIME_CLAIM_BOUNDARY
        or wrapper["baseline_closure_sha256"] != baseline["closure_sha256"]
    ):
        raise HistoryError("boot runtime closure boundary is invalid")
    for name in sorted(RUNTIME_CLOSURE_SECTIONS):
        section = sections[name]
        if not isinstance(section, dict):
            raise HistoryError("runtime subordinate closure is not an object")
        semantic = dict(section)
        stated = semantic.pop("closure_sha256", None)
        if (
            require_sha256(stated, f"runtime {name} closure")
            != digest(canonical(semantic))
            or subordinate[name] != stated
        ):
            raise HistoryError(f"runtime subordinate closure is invalid: {name}")
    phases = wrapper["phases"]
    if not isinstance(phases, list) or len(phases) != 3:
        raise HistoryError("boot runtime closure phase roster is invalid")
    for index, phase_name in enumerate(("after_sync", "before_child", "after_ready")):
        phase = require_keys(
            phases[index],
            {"phase", "closure_sha256", "subordinate_closure_sha256"},
            "runtime closure phase",
        )
        if (
            phase["phase"] != phase_name
            or phase["closure_sha256"] != baseline["closure_sha256"]
            or phase["subordinate_closure_sha256"] != subordinate
        ):
            raise HistoryError("runtime closure changed across startup phases")

    process = receipt["process"]
    environment = receipt["environment"]
    runtime_receipt = receipt["runtime"]
    launch = require_keys(
        sections["launch_context"],
        {"contract", "service", "permutation_subprocess", "closure_sha256"},
        "runtime launch context",
    )
    service = require_keys(
        launch["service"],
        {"argv", "cwd", "app_dir", "environment", "environment_sha256"},
        "runtime service launch",
    )
    permutation = require_keys(
        launch["permutation_subprocess"],
        {"argv", "cwd", "environment", "environment_sha256", "helper"},
        "runtime permutation launch",
    )
    python_runtime = sections["python_runtime"]
    expected_permutation_environment = {
        "HOME": str(runtime / "home"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": ":".join(
            (str(runtime / "venv/bin"), "/usr/bin", "/bin", "/usr/sbin", "/sbin")
        ),
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "TZ": "UTC",
    }
    permutation_helper = capsule / "casepath-qa/production-projection-permutation-v1.py"
    expected_permutation_argv = [
        runtime_receipt["python_path"],
        "-B",
        "-I",
        "-P",
        "-c",
        (
            'import runpy,sys; sys.path.insert(0,sys.argv.pop(1)); '
            'runpy.run_path(sys.argv.pop(1),run_name="__main__")'
        ),
        str(capsule / "casepath-api"),
        str(permutation_helper),
    ]
    if (
        launch.get("contract") != "casepath.closed-launch-context/1.0.0"
        or service.get("argv") != process["argv"]
        or service.get("cwd") != str(repository)
        or service.get("app_dir") != str(capsule / "casepath-api")
        or service.get("environment") != environment["values"]
        or service.get("environment_sha256") != digest(canonical(environment["values"]))
        or permutation.get("argv") != expected_permutation_argv
        or permutation.get("cwd") != str(repository)
        or permutation.get("environment") != expected_permutation_environment
        or permutation.get("environment_sha256")
        != digest(canonical(expected_permutation_environment))
    ):
        raise HistoryError("runtime launch context differs from boot authority")
    validate_closure_entry(
        permutation.get("helper"),
        permutation_helper,
        str(permutation_helper),
        "runtime permutation helper",
    )
    if not isinstance(python_runtime, dict):
        raise HistoryError("runtime Python identity is invalid")
    python_runtime = require_keys(
        python_runtime,
        {
            "contract",
            "stated_path",
            "symlink_chain",
            "symlink_chain_sha256",
            "real_path",
            "real_file",
            "base_prefix",
            "pyvenv_config",
            "interpreter_argv_flags",
            "implementation",
            "cache_tag",
            "python_version",
            "version_info",
            "python_build",
            "python_compiler",
            "closure_sha256",
        },
        "runtime Python identity",
    )
    if (
        python_runtime["contract"] != "casepath.python-runtime-identity/1.0.0"
        or python_runtime["stated_path"] != runtime_receipt["python_path"]
        or python_runtime["real_path"] != runtime_receipt["python_real_path"]
        or python_runtime["python_version"] != runtime_receipt["python_version"]
        or python_runtime["interpreter_argv_flags"] != ["-I", "-B", "-P"]
        or python_runtime["implementation"] != "cpython"
        or python_runtime["cache_tag"] != "cpython-313"
        or python_runtime["version_info"] != [3, 13, 9, "final", 0]
        or not isinstance(python_runtime["python_build"], list)
        or len(python_runtime["python_build"]) != 2
        or not isinstance(python_runtime["python_compiler"], str)
        or not python_runtime["python_compiler"]
    ):
        raise HistoryError("runtime Python identity differs from boot authority")

    closure_sha = baseline["closure_sha256"]
    if closure_sha in _RUNTIME_CLOSURE_CACHE:
        return closure_sha
    capsule_section = validate_tree_closure(
        sections["capsule"], capsule, "runtime capsule closure"
    )
    site_packages = runtime / "venv/lib/python3.13/site-packages"
    site_section = validate_tree_closure(
        sections["site_packages"],
        site_packages,
        "runtime site-packages closure",
        reject_symlinks=True,
    )
    if capsule_section["root"] != str(capsule):
        raise HistoryError("runtime capsule closure root differs from authority")
    validate_distribution_closure(
        sections["distribution_integrity"], site_section, runtime, capsule
    )
    stated_path = Path(python_runtime["stated_path"])
    chain = python_runtime["symlink_chain"]
    if (
        not isinstance(chain, list)
        or not chain
        or python_runtime["symlink_chain_sha256"] != digest(canonical(chain))
    ):
        raise HistoryError("runtime Python symlink chain is invalid")
    chain_path = stated_path
    visited: set[str] = set()
    for row in chain:
        key = str(chain_path)
        if key in visited:
            raise HistoryError("runtime Python symlink chain contains a cycle")
        visited.add(key)
        validate_closure_entry(row, chain_path, key, "runtime Python symlink")
        if row["kind"] != "symlink":
            raise HistoryError("runtime Python symlink chain contains a non-link")
        target = os.readlink(chain_path)
        chain_path = Path(
            os.path.normpath(
                target if os.path.isabs(target) else os.path.join(chain_path.parent, target)
            )
        )
    real_path = Path(python_runtime["real_path"])
    if chain_path.resolve() != real_path or stated_path.resolve() != real_path:
        raise HistoryError("runtime Python symlink chain target is invalid")
    validate_closure_entry(
        python_runtime["real_file"], real_path, str(real_path), "runtime Python executable"
    )
    if python_runtime["real_file"].get("sha256") != runtime_receipt["python_file_sha256"]:
        raise HistoryError("runtime Python executable hash differs from boot authority")
    validate_closure_entry(
        python_runtime["pyvenv_config"],
        runtime / "venv/pyvenv.cfg",
        str(runtime / "venv/pyvenv.cfg"),
        "runtime pyvenv config",
    )
    base_prefix = Path(python_runtime["base_prefix"]).resolve()
    try:
        real_path.relative_to(base_prefix)
    except ValueError as exc:
        raise HistoryError("runtime Python executable escaped its base prefix") from exc

    isolated = validate_closure_hash(
        sections["isolated_probe"],
        {"contract", "command", "cwd", "expected_environment", "observation", "stdout_sha256"},
        "runtime isolated probe",
    )
    expected_probe_environment = {
        "HOME": str(runtime / "home"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": ":".join(
            (str(runtime / "venv/bin"), "/usr/bin", "/bin", "/usr/sbin", "/sbin")
        ),
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(runtime / "pycache"),
        "TZ": "UTC",
    }
    expected_probe_command = [
        str(stated_path), "-I", "-B", "-P", "-c", ISOLATED_PROBE_PROGRAM
    ]
    if (
        isolated["contract"] != "casepath.isolated-python-path-environment-probe/1.0.0"
        or isolated["command"] != expected_probe_command
        or isolated["cwd"] != str(capsule)
        or isolated["expected_environment"] != expected_probe_environment
    ):
        raise HistoryError("runtime isolated probe authority is invalid")
    completed = subprocess.run(
        expected_probe_command,
        cwd=capsule,
        env=expected_probe_environment,
        check=False,
        capture_output=True,
        timeout=60,
    )
    if completed.returncode != 0 or completed.stderr:
        raise HistoryError("runtime isolated probe execution failed")
    observation = parse_json(completed.stdout, "runtime isolated probe output")
    if (
        isolated["observation"] != observation
        or isolated["stdout_sha256"] != digest(completed.stdout)
        or observation.get("path")
        != [
            str(base_prefix / "lib/python313.zip"),
            str(base_prefix / "lib/python3.13"),
            str(base_prefix / "lib/python3.13/lib-dynload"),
            str(site_packages),
        ]
        or observation.get("flags")
        != {
            "dont_write_bytecode": True,
            "ignore_environment": True,
            "isolated": True,
            "no_site": False,
            "no_user_site": True,
            "safe_path": True,
        }
    ):
        raise HistoryError("runtime isolated probe differs from authority")
    _RUNTIME_CLOSURE_CACHE.add(closure_sha)
    return closure_sha


def validate_receipt(
    path: Path, runtime: Path, data_root: Path, repository: Path
) -> tuple[bytes, dict[str, object], str]:
    raw, metadata = read_regular(path, "boot history receipt")
    parsed_receipt = parse_json(raw, "boot history receipt")
    receipt_contract = parsed_receipt.get("contract")
    receipt = require_keys(
        parsed_receipt,
        BOOT_KEYS_V22
        if receipt_contract == "casepath.local-runtime-boot/2.2.0"
        else BOOT_KEYS,
        "boot",
    )
    semantic = dict(receipt)
    receipt_sha = semantic.pop("receipt_sha256")
    prior = receipt["prior_boot_receipt_file_sha256"]
    if (
        receipt["contract"]
        not in {
            "casepath.local-runtime-boot/2.0.0",
            "casepath.local-runtime-boot/2.1.0",
            "casepath.local-runtime-boot/2.2.0",
        }
        or receipt["boot_id"] != path.stem
        or receipt_sha != digest(canonical(semantic))
        or (
            prior is not None
            and (not isinstance(prior, str) or SHA256.fullmatch(prior) is None)
        )
        or (
            receipt["contract"]
            in {
                "casepath.local-runtime-boot/2.1.0",
                "casepath.local-runtime-boot/2.2.0",
            }
            and (
                stat.S_IMODE(metadata.st_mode) != 0o444
                or metadata.st_nlink != 1
            )
        )
    ):
        raise HistoryError(f"boot history receipt is invalid: {path.name}")
    capsule, source_roster_sha, _ = validate_capsule(receipt, runtime)
    launcher = require_keys(
        receipt["launcher"], {"path", "sha256", "bytes"}, "boot launcher"
    )
    process = require_keys(
        receipt["process"],
        {"pid", "listener_owner_pid", "cwd", "argv", "workers"},
        "boot process",
    )
    environment = require_keys(
        receipt["environment"],
        {"values", "provider_credential_names_present"},
        "boot environment",
    )
    runtime_receipt = require_keys(
        receipt["runtime"],
        {
            "python_path",
            "python_real_path",
            "python_file_sha256",
            "python_version",
            "requirements_lock_sha256",
            "installed_distributions",
            "installed_distributions_sha256",
            "data_root",
            "data_root_provenance_file_sha256",
            "database_path",
            "artifact_registry_path",
        },
        "boot runtime",
    )
    source = receipt["source"]
    launcher_raw, _ = read_regular(capsule / "bin/casepath", "capsule launcher")
    requirements_raw, _ = read_regular(
        capsule / "casepath-api/requirements.lock", "capsule requirements lock"
    )
    python_path = Path(runtime_receipt["python_path"])
    expected_argv = [
        str(python_path),
        "-I",
        *(["-B"] if receipt["contract"] == "casepath.local-runtime-boot/2.2.0" else []),
        "-P",
        "-m",
        "uvicorn",
        "casepath_api.app:app",
        "--app-dir",
        str(capsule / "casepath-api"),
        "--host",
        "127.0.0.1",
        "--port",
        "4173",
        "--no-access-log",
    ]
    expected_env = expected_environment(runtime, data_root, capsule, source["git_head"])
    provenance_raw, _ = read_regular(
        data_root / "DATA_ROOT_PROVENANCE.json", "durable data provenance"
    )
    distributions = runtime_receipt["installed_distributions"]

    def normalize_name(value: str) -> str:
        return re.sub(r"[-_.]+", "-", value).lower()

    locked_pins: dict[str, str] = {}
    for line in requirements_raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("==") != 1:
            raise HistoryError("capsule requirements lock has an unpinned row")
        name, version = line.split("==", 1)
        normalized = normalize_name(name)
        if normalized in locked_pins:
            raise HistoryError("capsule requirements lock duplicates a package")
        locked_pins[normalized] = version
    installed_pins: dict[str, str] = {}
    if isinstance(distributions, list):
        for value in distributions:
            if not isinstance(value, str) or value.count("==") != 1:
                raise HistoryError("boot distribution roster has an unpinned row")
            name, version = value.split("==", 1)
            normalized = normalize_name(name)
            if normalized in installed_pins:
                raise HistoryError("boot distribution roster duplicates a package")
            installed_pins[normalized] = version
    if (
        receipt["url"] != "http://127.0.0.1:4173/"
        or receipt["topology"]
        != "single_fastapi_same_origin_static_api_and_in_process_worker"
        or launcher["path"] != "bin/casepath"
        or launcher["sha256"] != digest(launcher_raw)
        or launcher["bytes"] != len(launcher_raw)
        or type(process["pid"]) is not int
        or process["pid"] < 1
        or process["listener_owner_pid"] != process["pid"]
        or process["cwd"] != str(repository)
        or process["argv"] != expected_argv
        or process["workers"] != 1
        or environment["values"] != expected_env
        or environment["provider_credential_names_present"] != []
        or source["repository"] != str(repository)
        or not isinstance(source["git_branch"], str)
        or not source["git_branch"]
        or source["source_manifest_before_child_sha256"]
        != source["source_manifest_file_sha256"]
        or source["source_manifest_after_ready_sha256"]
        != source["source_manifest_file_sha256"]
        or runtime_receipt["python_path"] != str(runtime / "venv/bin/python")
        or not isinstance(runtime_receipt["python_real_path"], str)
        or not Path(runtime_receipt["python_real_path"]).is_absolute()
        or not isinstance(runtime_receipt["python_file_sha256"], str)
        or SHA256.fullmatch(runtime_receipt["python_file_sha256"]) is None
        or runtime_receipt["python_version"] != "3.13.9"
        or runtime_receipt["requirements_lock_sha256"]
        != digest(requirements_raw)
        or not isinstance(distributions, list)
        or distributions
        != sorted(set(distributions), key=lambda value: (value.casefold(), value))
        or installed_pins != locked_pins
        or runtime_receipt["installed_distributions_sha256"]
        != digest(canonical(distributions))
        or runtime_receipt["data_root"] != str(data_root)
        or runtime_receipt["data_root_provenance_file_sha256"]
        != digest(provenance_raw)
        or runtime_receipt["database_path"] != str(data_root / "casepath.db")
        or runtime_receipt["artifact_registry_path"]
        != str(data_root / "artifact-registry")
    ):
        raise HistoryError(f"boot receipt authority is invalid: {path.name}")
    attestation = receipt["attestation"]
    expected_attestation_keys = (
        DURABLE_ATTESTATION_KEYS
        if receipt["contract"]
        in {
            "casepath.local-runtime-boot/2.1.0",
            "casepath.local-runtime-boot/2.2.0",
        }
        else LEGACY_ATTESTATION_KEYS
    )
    require_keys(attestation, expected_attestation_keys, "boot attestation")
    for field in (
        "health_response_sha256",
        "ready_response_sha256",
        "model_ledger_response_sha256",
        "root_html_sha256",
        "workspace_seed_receipt_file_sha256",
        "workspace_seed_receipt_sha256",
        "workspace_seed_event_roster_sha256",
        "workspace_response_sha256",
        "workspace_projection_sha256",
        "workspace_state_roster_sha256",
        "workspace_corpus_identity_sha256",
    ):
        require_sha256(attestation[field], f"boot attestation {field}")
    if (
        attestation["credential_configured"] is not False
        or attestation["model_ledger_records"] != 0
        or attestation["model_ledger_network_calls"] != 0
        or attestation["source_reverified_after_ready"] is not True
    ):
        raise HistoryError("boot activity attestation is invalid")
    validate_embedded_workspace(receipt, source_roster_sha)
    if receipt["contract"] in {
        "casepath.local-runtime-boot/2.1.0",
        "casepath.local-runtime-boot/2.2.0",
    }:
        validate_durable_attestation(attestation)
    if receipt["contract"] == "casepath.local-runtime-boot/2.2.0":
        validate_runtime_closure(receipt, runtime, data_root, repository, capsule)
    return raw, receipt, digest(raw)


def require_monotonic_durable_chain(chain: list[dict[str, object]]) -> None:
    prior: dict[str, object] | None = None
    durable_started = False
    runtime_closure_started = False
    closure_by_source_manifest: dict[str, str] = {}
    for receipt in chain:
        if receipt["contract"] not in {
            "casepath.local-runtime-boot/2.1.0",
            "casepath.local-runtime-boot/2.2.0",
        }:
            if durable_started:
                raise HistoryError("boot history downgraded after durable authority")
            continue
        durable_started = True
        if receipt["contract"] == "casepath.local-runtime-boot/2.2.0":
            runtime_closure_started = True
            source_sha = receipt["source"]["source_manifest_file_sha256"]
            closure_sha = receipt["runtime_closure"]["baseline_closure_sha256"]
            prior_closure = closure_by_source_manifest.get(source_sha)
            if prior_closure is not None and prior_closure != closure_sha:
                raise HistoryError("executable runtime closure changed across restart")
            closure_by_source_manifest[source_sha] = closure_sha
        elif runtime_closure_started:
            raise HistoryError("boot history downgraded after runtime-closure authority")
        if prior is not None:
            current_events = {
                (row["session_id"], row["loop_id"], row["sequence"]): row
                for row in receipt["attestation"]["durable_event_roster"]
            }
            current_registry = {
                row["path"]: row
                for row in receipt["attestation"]["durable_registry_inventory"]
            }
            for row in prior["attestation"]["durable_event_roster"]:
                key = (row["session_id"], row["loop_id"], row["sequence"])
                if current_events.get(key) != row:
                    raise HistoryError("durable event history rolled back")
            for row in prior["attestation"]["durable_registry_inventory"]:
                if current_registry.get(row["path"]) != row:
                    raise HistoryError("durable registry history rolled back")
        prior = receipt


def reconcile_boot_staging(runtime: Path, *, allow_reconcile: bool) -> None:
    staging = runtime / "boot-staging"
    boots = runtime / "boots"
    if staging.is_symlink() or not staging.is_dir():
        raise HistoryError("boot staging root is not a regular directory")
    removed = False
    for candidate in sorted(staging.iterdir()):
        if not allow_reconcile:
            raise HistoryError("boot staging is not empty during read-only verification")
        match = STAGING_NAME.fullmatch(candidate.name)
        if match is None or candidate.is_symlink() or not candidate.is_file():
            raise HistoryError("boot staging contains a noncanonical entry")
        metadata = candidate.stat()
        history = boots / f"{match.group(1)}.json"
        if metadata.st_nlink == 1:
            candidate.unlink()
            removed = True
            continue
        if metadata.st_nlink != 2 or history.is_symlink() or not history.is_file():
            raise HistoryError("boot staging has an unknown hard-link authority")
        history_metadata = history.stat()
        if (
            history_metadata.st_dev != metadata.st_dev
            or history_metadata.st_ino != metadata.st_ino
        ):
            raise HistoryError("boot staging hard link does not bind its history")
        candidate.unlink()
        removed = True
    if removed:
        descriptor = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def reconcile_pointer_temps(runtime: Path, *, allow_reconcile: bool) -> None:
    removed = False
    for candidate in sorted(runtime.iterdir()):
        if not candidate.name.startswith(".runtime-boot-receipt."):
            continue
        if (
            not allow_reconcile
            or POINTER_TEMP_NAME.fullmatch(candidate.name) is None
            or candidate.is_symlink()
            or not candidate.is_file()
            or candidate.stat().st_nlink != 1
        ):
            raise HistoryError("runtime contains an invalid boot-pointer temporary")
        candidate.unlink()
        removed = True
    if removed:
        descriptor = os.open(runtime, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def validate_event_journal(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    previous_by_loop: dict[tuple[str, str], str] = {}
    sequence_by_loop: dict[tuple[str, str], int] = {}
    idempotency_keys: set[tuple[str, str, str]] = set()
    event_hashes: set[tuple[str, str, str]] = set()
    query = """SELECT session_id,loop_id,sequence,idempotency_key,
        command_sha256,event_sha256,event_json,created_at
        FROM claim_loop_events ORDER BY session_id,loop_id,sequence"""
    for row in connection.execute(query):
        event = require_keys(
            parse_json(row[6].encode("utf-8"), "durable journal event"),
            EVENT_KEYS,
            "durable journal event",
        )
        session_id, loop_id, sequence, idempotency_key = row[:4]
        loop_key = (session_id, loop_id)
        expected_sequence = sequence_by_loop.get(loop_key, 0) + 1
        expected_previous = previous_by_loop.get(loop_key)
        contract = event["contract"]
        command = event["command"]
        event_material = {
            key: value
            for key, value in event.items()
            if key not in {"event_sha256", "resulting_state_sha256"}
        }
        identity_key = (session_id, loop_id, idempotency_key)
        event_key = (session_id, loop_id, row[5])
        if (
            not isinstance(session_id, str)
            or not session_id
            or not isinstance(loop_id, str)
            or not loop_id
            or isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence != expected_sequence
            or not isinstance(idempotency_key, str)
            or not idempotency_key
            or contract not in EVENT_TYPES
            or event["event_type"] not in EVENT_TYPES[contract]
            or event["session_id"] != session_id
            or event["loop_id"] != loop_id
            or event["sequence"] != sequence
            or event["idempotency_key"] != idempotency_key
            or event["previous_event_sha256"] != expected_previous
            or event["command_sha256"] != row[4]
            or event["event_sha256"] != row[5]
            or event["created_at"] != row[7]
            or not isinstance(command, dict)
            or require_sha256(row[4], "durable command hash")
            != digest(canonical(command))
            or require_sha256(row[5], "durable event hash")
            != digest(canonical(event_material))
            or require_sha256(
                event["resulting_state_sha256"], "durable resulting-state hash"
            )
            != event["resulting_state_sha256"]
            or row[6].encode("utf-8") != canonical(event)
            or identity_key in idempotency_keys
            or event_key in event_hashes
        ):
            raise HistoryError("durable journal event chain is invalid")
        idempotency_keys.add(identity_key)
        event_hashes.add(event_key)
        sequence_by_loop[loop_key] = sequence
        previous_by_loop[loop_key] = row[5]
        rows.append(
            {
                "session_id": session_id,
                "loop_id": loop_id,
                "sequence": sequence,
                "event_sha256": row[5],
                "event_json_sha256": digest(row[6].encode("utf-8")),
            }
        )
    return rows


def validate_tip_against_data_root(
    receipt: dict[str, object], data_root: Path
) -> None:
    if receipt["contract"] == "casepath.local-runtime-boot/2.0.0":
        return
    module_path = (
        Path(receipt["source"]["execution_root"])
        / "casepath-api/casepath_api/local_data_root.py"
    )
    module_raw, _ = read_regular(
        module_path, "sealed durable-data provenance controller"
    )
    module = types.ModuleType("casepath_history_local_data_root")
    module.__file__ = str(module_path)
    module.__package__ = ""
    sys.modules[module.__name__] = module
    try:
        exec(compile(module_raw, str(module_path), "exec"), module.__dict__)
        validate_existing = getattr(module, "_validate_existing", None)
        if not callable(validate_existing):
            raise HistoryError(
                "sealed durable-data provenance controller is incomplete"
            )
        validate_existing(data_root)
    except HistoryError:
        raise
    except Exception as exc:
        raise HistoryError(
            "durable data root differs from its sealed provenance"
        ) from exc
    attestation = receipt["attestation"]
    database = data_root / "casepath.db"
    database_metadata = stat_regular(database, "durable database")
    if database_metadata.st_nlink != 1:
        raise HistoryError("durable database has an external hard link")
    with sqlite3.connect(
        f"file:{database.as_posix()}?mode=ro", uri=True
    ) as connection:
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise HistoryError("durable database failed integrity check")
        event_rows = validate_event_journal(connection)
    event_by_key = {
        (row["session_id"], row["loop_id"], row["sequence"]): row
        for row in event_rows
    }
    for row in attestation["durable_event_roster"]:
        key = (row["session_id"], row["loop_id"], row["sequence"])
        if event_by_key.get(key) != row:
            raise HistoryError("durable database rolled back behind boot history")
    registry = data_root / "artifact-registry"
    if registry.is_symlink() or not registry.is_dir():
        raise HistoryError("durable registry is not a regular directory")
    registry_by_path: dict[str, dict[str, object]] = {}
    for candidate in sorted(registry.rglob("*")):
        metadata = candidate.lstat()
        if candidate.is_symlink() or (
            not stat.S_ISREG(metadata.st_mode)
            and not stat.S_ISDIR(metadata.st_mode)
        ):
            raise HistoryError("durable registry contains an invalid entry")
        if stat.S_ISREG(metadata.st_mode):
            if metadata.st_nlink != 1:
                raise HistoryError("durable registry contains a linked file")
            raw, _ = read_regular(candidate, "durable registry file")
            relative = candidate.relative_to(registry).as_posix()
            registry_by_path[relative] = {
                "path": relative,
                "sha256": digest(raw),
                "size_bytes": len(raw),
            }
    for row in attestation["durable_registry_inventory"]:
        if registry_by_path.get(row["path"]) != row:
            raise HistoryError("durable registry rolled back behind boot history")


def reconcile(
    runtime: Path,
    data_root: Path,
    repository: Path,
    *,
    allow_reconcile: bool = True,
) -> None:
    boots = runtime / "boots"
    current = runtime / "runtime-boot-receipt.json"
    if boots.is_symlink() or not boots.is_dir():
        raise HistoryError("boot history root is not a regular directory")
    if tree_has_posix_acl(boots):
        raise HistoryError("boot history contains an ACL-bearing entry")
    reconcile_pointer_temps(runtime, allow_reconcile=allow_reconcile)
    reconcile_boot_staging(runtime, allow_reconcile=allow_reconcile)
    entries: dict[str, tuple[bytes, dict[str, object], Path]] = {}
    for candidate in sorted(boots.iterdir()):
        if not BOOT_NAME.fullmatch(candidate.name):
            raise HistoryError(
                f"boot history contains a noncanonical entry: {candidate.name}"
            )
        raw, receipt, file_sha = validate_receipt(
            candidate, runtime, data_root, repository
        )
        if file_sha in entries:
            raise HistoryError("boot history duplicates receipt bytes")
        entries[file_sha] = (raw, receipt, candidate)
    if not entries:
        if current.exists() or current.is_symlink():
            raise HistoryError("current boot receipt exists without immutable history")
        return
    roots = [
        file_sha
        for file_sha, (_, value, _) in entries.items()
        if value["prior_boot_receipt_file_sha256"] is None
    ]
    if len(roots) != 1:
        raise HistoryError("boot history does not have exactly one root")
    children: dict[str, list[str]] = {}
    for file_sha, (_, value, _) in entries.items():
        prior = value["prior_boot_receipt_file_sha256"]
        if prior is not None:
            if prior not in entries:
                raise HistoryError("boot history is missing a prior receipt")
            children.setdefault(prior, []).append(file_sha)
    chain_sha = [roots[0]]
    while children.get(chain_sha[-1]):
        successors = children[chain_sha[-1]]
        if len(successors) != 1:
            raise HistoryError("boot history contains a fork")
        chain_sha.append(successors[0])
    if set(chain_sha) != set(entries):
        raise HistoryError("boot history contains an unreachable receipt")
    chain = [entries[file_sha][1] for file_sha in chain_sha]
    require_monotonic_durable_chain(chain)
    validate_tip_against_data_root(chain[-1], data_root)
    current_sha = None
    if current.exists() or current.is_symlink():
        current_raw, _ = read_regular(current, "current boot receipt")
        current_sha = digest(current_raw)
        if current_sha not in entries:
            raise HistoryError("current boot receipt is outside the history chain")
    tip_sha = chain_sha[-1]
    if current_sha == tip_sha:
        return
    if not allow_reconcile:
        raise HistoryError("current boot receipt is not the immutable history tip")
    temporary = runtime / (
        f".runtime-boot-receipt.reconcile-{os.getpid()}-{uuid.uuid4()}.tmp"
    )
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        remaining = memoryview(entries[tip_sha][0])
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise HistoryError("boot receipt reconciliation made no progress")
            remaining = remaining[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, current)
    descriptor = os.open(runtime, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    verify_only = len(sys.argv) == 5 and sys.argv[1] == "--verify-only"
    if len(sys.argv) != 4 and not verify_only:
        raise HistoryError(
            "usage: validate_local_runtime_history.py [--verify-only] "
            "RUNTIME DATA_ROOT REPOSITORY"
        )
    offset = 2 if verify_only else 1
    runtime = Path(sys.argv[offset]).resolve()
    data_root = Path(sys.argv[offset + 1]).resolve()
    repository = Path(sys.argv[offset + 2]).resolve()
    reconcile(runtime, data_root, repository, allow_reconcile=not verify_only)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HistoryError as exc:
        raise SystemExit(f"CasePath boot-history validation failed: {exc}") from exc
