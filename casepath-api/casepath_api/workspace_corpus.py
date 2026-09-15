from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from types import MappingProxyType
from typing import Any, Mapping


AUTHORIZED_SOURCE_MANIFEST_SHA256 = (
    "638630886a1d291dfe9009839eb0519130e56700bb4d454277ce2e45c6044f4c"
)
AUTHORIZED_SOURCE_CASE_COUNT = 150
AUTHORIZED_SOURCE_SPLIT = "public_dev"
AUTHORIZED_PUBLIC_CASE_COUNT = 60
AUTHORIZED_PUBLIC_FILE_COUNT = 255
AUTHORIZED_PUBLIC_FILE_BYTES = 12_890_036
CORPUS_CONTRACT = "casepath.public-observable-corpus/1.0.0"
CORPUS_ID = "synthetic-dev-60"
CORPUS_VERSION = "1.0.0"
WORKSPACE_CORPUS_ID = "synthetic-150"
# (source split, claim count, non-policy file count, non-policy bytes).
# Both profiles are derived solely from the exact original source manifest.
CORPUS_PROFILES = MappingProxyType({
    CORPUS_ID: (AUTHORIZED_SOURCE_SPLIT, 60, 255, 12_890_036),
    WORKSPACE_CORPUS_ID: (None, 150, 657, 45_506_779),
})
CLAIM_BINDING_CONTRACT = "casepath.claim-binding/1.0.0"
STATIC_TEMPLATE_CONTRACT = "casepath.static-playbook-template/1.0.0"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class WorkspaceCorpusError(ValueError):
    """Raised when the public observable corpus is not an exact closed package."""


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _read_regular(root: Path, relative_path: str) -> bytes:
    if not isinstance(relative_path, str) or not relative_path:
        raise WorkspaceCorpusError("corpus path must be a nonempty string")
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise WorkspaceCorpusError("corpus path escapes its root")
    candidate = root / relative
    if candidate.is_symlink() or not candidate.is_file():
        raise WorkspaceCorpusError(f"corpus file is not regular: {relative_path}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise WorkspaceCorpusError("corpus path escapes its root") from exc
    return candidate.read_bytes()


def _closed_json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceCorpusError(f"{label} is not canonical JSON") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        raise WorkspaceCorpusError(f"{label} is not canonical JSON")
    return value


def _manifest_file_map(source_root: Path, manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise WorkspaceCorpusError("source manifest lacks its file roster")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "file_sha256",
                "grounding_locator_count",
                "relative_path",
                "role",
                "size_bytes",
            }
            or not isinstance(row.get("relative_path"), str)
            or not isinstance(row.get("file_sha256"), str)
            or SHA256_PATTERN.fullmatch(row["file_sha256"]) is None
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] < 0
            or row["relative_path"] in result
        ):
            raise WorkspaceCorpusError("source manifest file row is invalid")
        result[row["relative_path"]] = {
            "path": row["relative_path"],
            "sha256": row["file_sha256"],
            "size_bytes": row["size_bytes"],
            "role": row["role"],
        }
    return result


def _verified_source_file(
    source_root: Path,
    roster: Mapping[str, Mapping[str, Any]],
    relative_path: str,
) -> bytes:
    row = roster.get(relative_path)
    if row is None:
        raise WorkspaceCorpusError(f"source path is outside the manifest: {relative_path}")
    raw = _read_regular(source_root, relative_path)
    if len(raw) != row["size_bytes"] or sha256_bytes(raw) != row["sha256"]:
        raise WorkspaceCorpusError(f"source file identity drifted: {relative_path}")
    return raw


def _safe_name(value: str) -> str:
    name = Path(value).name
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise WorkspaceCorpusError("artifact filename is invalid")
    return name


def _write_regular(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise WorkspaceCorpusError(f"bundle destination already exists: {path}")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _file_receipt(path: str, raw: bytes) -> dict[str, Any]:
    return {"path": path, "sha256": sha256_bytes(raw), "size_bytes": len(raw)}


def build_public_corpus_bundle(source_root: Path, destination: Path, *, corpus_id: str = CORPUS_ID) -> dict[str, Any]:
    """Build the exact public-safe bundle without copying benchmark labels or gold."""

    try:
        source_split, case_count, data_file_count, data_bytes = CORPUS_PROFILES[corpus_id]
    except (KeyError, TypeError) as exc:
        raise WorkspaceCorpusError("unsupported intake corpus profile") from exc
    source_root = source_root.resolve()
    destination = destination.resolve()
    source_manifest_raw = _read_regular(source_root, "manifest.json")
    if sha256_bytes(source_manifest_raw) != AUTHORIZED_SOURCE_MANIFEST_SHA256:
        raise WorkspaceCorpusError("authorized source manifest identity differs")
    source_manifest = _closed_json(source_manifest_raw, label="source manifest")
    file_roster = _manifest_file_map(source_root, source_manifest)
    source_cases = source_manifest.get("cases")
    if (
        not isinstance(source_cases, list)
        or len(source_cases) != AUTHORIZED_SOURCE_CASE_COUNT
        or not all(isinstance(case, dict) for case in source_cases)
    ):
        raise WorkspaceCorpusError("authorized source case roster is invalid")
    cases = [
        case for case in source_cases if source_split is None or case.get("split") == source_split
    ]
    if len(cases) != case_count:
        raise WorkspaceCorpusError("authorized intake roster differs from its profile")
    case_ids: set[str] = set()

    if destination.exists() or destination.is_symlink():
        raise WorkspaceCorpusError("bundle destination must be absent")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.build-", dir=destination.parent)
    )
    written_rows: list[dict[str, Any]] = []
    binding_rows: list[dict[str, Any]] = []
    try:
        license_raw = _verified_source_file(source_root, file_roster, "LICENSE-DATA")
        _write_regular(staging / "LICENSE-DATA", license_raw)
        license_receipt = _file_receipt("LICENSE-DATA", license_raw)
        written_rows.append(license_receipt)
        policy_sources = (
            ("rules/static-rule-templates-v3.json", "policy/static-rule-templates-v3.json"),
            ("rules/swiss-authority-passages-v3.json", "policy/swiss-authority-passages-v3.json"),
        )
        policy_rows: list[dict[str, Any]] = []
        for source_path, bundle_path in policy_sources:
            raw = _verified_source_file(source_root, file_roster, source_path)
            _closed_json(raw, label=source_path)
            _write_regular(staging / bundle_path, raw)
            receipt = _file_receipt(bundle_path, raw)
            policy_rows.append(receipt)
            written_rows.append(receipt)
        static_material = {
            "contract": STATIC_TEMPLATE_CONTRACT,
            "template_id": "casepath.synthetic-static-policy-v3",
            "template_version": "3.0.0",
            "files": policy_rows,
            "claim_roster_in_policy_identity": False,
        }
        static_template = {
            **static_material,
            "template_sha256": digest_value(static_material),
        }

        for case in cases:
            if not isinstance(case, dict):
                raise WorkspaceCorpusError("source case row is invalid")
            # The allowlist is intentionally narrower than the source row. Domain,
            # family, split, commitments, gold paths, and evaluator hashes are not
            # copied into product authority.
            claim_id = case.get("case_id")
            claim_source_path = case.get("observable_claim_path")
            registry_source_path = case.get("source_registry_path")
            document_source_paths = case.get("source_document_paths")
            if (
                not isinstance(claim_id, str)
                or not claim_id
                or claim_id in case_ids
                or not isinstance(claim_source_path, str)
                or not isinstance(registry_source_path, str)
                or not isinstance(document_source_paths, list)
                or not document_source_paths
                or len(document_source_paths) != len(set(document_source_paths))
                or not all(isinstance(item, str) for item in document_source_paths)
            ):
                raise WorkspaceCorpusError("source case pointers are invalid")
            case_ids.add(claim_id)

            claim_raw = _verified_source_file(source_root, file_roster, claim_source_path)
            registry_raw = _verified_source_file(
                source_root, file_roster, registry_source_path
            )
            claim = _closed_json(claim_raw, label=f"claim {claim_id}")
            registry = _closed_json(registry_raw, label=f"registry {claim_id}")
            claim_contract = claim.get("contract")
            if (
                not isinstance(claim_contract, dict)
                or claim_contract.get("name") != "casepath_observable_claim"
                or claim_contract.get("version") != "intake-only/1.2.0"
                or claim_contract.get("complete_downstream_input") is not True
                or claim_contract.get("contains_post_intake_information") is not False
                or claim.get("submission", {}).get("claim_id") != claim_id
                or registry.get("contract")
                != "casepath.model-visible-source-registry/3.1.0"
                or registry.get("case_id") != claim_id
                or registry.get("contains_case_activation_values") is not False
                or registry.get("contains_selected_paths") is not False
            ):
                raise WorkspaceCorpusError("observable claim boundary is invalid")

            claim_bundle_path = f"claims/{claim_id}.json"
            registry_bundle_path = f"registries/{claim_id}.json"
            _write_regular(staging / claim_bundle_path, claim_raw)
            _write_regular(staging / registry_bundle_path, registry_raw)
            claim_receipt = _file_receipt(claim_bundle_path, claim_raw)
            registry_receipt = _file_receipt(registry_bundle_path, registry_raw)
            written_rows.extend((claim_receipt, registry_receipt))

            source_documents: list[dict[str, Any]] = []
            document_by_sha: dict[str, dict[str, Any]] = {}
            for index, source_path in enumerate(document_source_paths):
                raw = _verified_source_file(source_root, file_roster, source_path)
                source_name = _safe_name(source_path)
                bundle_path = (
                    f"artifacts/{claim_id}/{index:02d}-{sha256_bytes(raw)[:12]}-{source_name}"
                )
                _write_regular(staging / bundle_path, raw)
                receipt = _file_receipt(bundle_path, raw)
                source_documents.append(receipt)
                written_rows.append(receipt)
                if receipt["sha256"] in document_by_sha:
                    raise WorkspaceCorpusError("claim source documents duplicate content")
                document_by_sha[receipt["sha256"]] = receipt

            observable_artifacts: list[dict[str, Any]] = []
            message = claim.get("customer_message")
            attachments = claim.get("attachments")
            submission = claim.get("submission")
            if (
                not isinstance(message, dict)
                or not isinstance(attachments, list)
                or not isinstance(submission, dict)
            ):
                raise WorkspaceCorpusError("observable claim structure is invalid")
            embedded = [("customer_message", message.get("raw_file"))]
            embedded.extend(("attachment", item) for item in attachments)
            for role, artifact in embedded:
                if not isinstance(artifact, dict):
                    raise WorkspaceCorpusError("observable artifact is invalid")
                expected_fields = {
                    "artifact_id",
                    "content_base64",
                    "file_name",
                    "media_type",
                    "sha256",
                    "size_bytes",
                }
                if set(artifact) != expected_fields:
                    raise WorkspaceCorpusError("observable artifact field set is invalid")
                try:
                    decoded = base64.b64decode(artifact["content_base64"], validate=True)
                except (TypeError, ValueError) as exc:
                    raise WorkspaceCorpusError("observable artifact encoding is invalid") from exc
                if (
                    sha256_bytes(decoded) != artifact["sha256"]
                    or len(decoded) != artifact["size_bytes"]
                    or artifact["sha256"] not in document_by_sha
                ):
                    raise WorkspaceCorpusError("observable artifact identity differs")
                document = document_by_sha[artifact["sha256"]]
                observable_artifacts.append(
                    {
                        "artifact_id": artifact["artifact_id"],
                        "role": role,
                        "file_name": artifact["file_name"],
                        "media_type": artifact["media_type"],
                        "path": document["path"],
                        "sha256": artifact["sha256"],
                        "size_bytes": artifact["size_bytes"],
                    }
                )

            binding_material = {
                "contract": CLAIM_BINDING_CONTRACT,
                "claim_id": claim_id,
                "static_template_sha256": static_template["template_sha256"],
                "claim": claim_receipt,
                "source_registry": registry_receipt,
                "source_documents": source_documents,
                "observable_artifacts": observable_artifacts,
                "subject": message.get("subject"),
                "language": submission.get("language"),
                "received_at": submission.get("received_at"),
                "message_id": message.get("message_id"),
            }
            if not all(
                isinstance(binding_material[field], str)
                and binding_material[field]
                for field in ("subject", "language", "received_at", "message_id")
            ):
                raise WorkspaceCorpusError("observable claim metadata is invalid")
            binding_rows.append(
                {
                    **binding_material,
                    "binding_sha256": digest_value(binding_material),
                }
            )

        written_rows.sort(key=lambda row: row["path"])
        binding_rows.sort(key=lambda row: row["claim_id"])
        if (
            len(binding_rows) != case_count
            or len(written_rows)
            != data_file_count + len(policy_sources) + 1
            or sum(
                row["size_bytes"]
                for row in written_rows
                if not row["path"].startswith("policy/")
                and row["path"] != "LICENSE-DATA"
            )
            != data_bytes
        ):
            raise WorkspaceCorpusError("public bundle aggregate differs")
        aggregate = {
            "file_count": len(written_rows),
            "size_bytes": sum(row["size_bytes"] for row in written_rows),
            "files_sha256": digest_value(written_rows),
            "claim_count": len(binding_rows),
            "bindings_sha256": digest_value(binding_rows),
        }
        manifest_material = {
            "contract": CORPUS_CONTRACT,
            "corpus_id": corpus_id,
            "corpus_version": "1.0.0",
            "source_manifest_file_sha256": AUTHORIZED_SOURCE_MANIFEST_SHA256,
            "contains_sealed_targets": False,
            "contains_expected_outputs": False,
            "license": license_receipt,
            "static_template": static_template,
            "claims": binding_rows,
            "aggregate": aggregate,
        }
        manifest = {
            **manifest_material,
            "manifest_sha256": digest_value(manifest_material),
        }
        manifest_raw = canonical_json_bytes(manifest)
        _write_regular(staging / "manifest.json", manifest_raw)
        directory_descriptor = os.open(staging, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        os.replace(staging, destination)
        parent_descriptor = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(parent_descriptor)
        finally:
            os.close(parent_descriptor)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


class PublicCorpus:
    """Strict, read-only access to the bundled observable product corpus."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        if root.is_symlink() or not root.is_dir():
            raise WorkspaceCorpusError("public corpus root is not a regular directory")
        raw = _read_regular(self.root, "manifest.json")
        self.manifest_file_sha256 = sha256_bytes(raw)
        self.manifest_size_bytes = len(raw)
        self.manifest = _closed_json(raw, label="public corpus manifest")
        profile = CORPUS_PROFILES.get(self.manifest.get("corpus_id"))
        if profile is None:
            raise WorkspaceCorpusError("unsupported intake corpus profile")
        self.corpus_id = self.manifest["corpus_id"]
        material = dict(self.manifest)
        manifest_sha256 = material.pop("manifest_sha256", None)
        if (
            set(self.manifest)
            != {
                "contract",
                "corpus_id",
                "corpus_version",
                "source_manifest_file_sha256",
                "contains_sealed_targets",
                "contains_expected_outputs",
                "license",
                "static_template",
                "claims",
                "aggregate",
                "manifest_sha256",
            }
            or self.manifest.get("contract") != CORPUS_CONTRACT
            or self.manifest.get("corpus_id") not in CORPUS_PROFILES
            or self.manifest.get("corpus_version") != CORPUS_VERSION
            or self.manifest.get("source_manifest_file_sha256")
            != AUTHORIZED_SOURCE_MANIFEST_SHA256
            or self.manifest.get("contains_sealed_targets") is not False
            or self.manifest.get("contains_expected_outputs") is not False
            or manifest_sha256 != digest_value(material)
        ):
            raise WorkspaceCorpusError("public corpus manifest is invalid")
        rows = self.manifest.get("claims")
        if not isinstance(rows, list) or len(rows) != profile[1]:
            raise WorkspaceCorpusError("public corpus claim roster is invalid")
        self.bindings: dict[str, dict[str, Any]] = {}
        expected_files = {"manifest.json"}
        file_rows: list[dict[str, Any]] = []
        for binding in rows:
            if not isinstance(binding, dict):
                raise WorkspaceCorpusError("claim binding is invalid")
            value = dict(binding)
            binding_sha = value.pop("binding_sha256", None)
            if (
                set(binding)
                != {
                    "contract",
                    "claim_id",
                    "static_template_sha256",
                    "claim",
                    "source_registry",
                    "source_documents",
                    "observable_artifacts",
                    "subject",
                    "language",
                    "received_at",
                    "message_id",
                    "binding_sha256",
                }
                or binding.get("contract") != CLAIM_BINDING_CONTRACT
                or binding_sha != digest_value(value)
                or binding["claim_id"] in self.bindings
            ):
                raise WorkspaceCorpusError("claim binding identity is invalid")
            self.bindings[binding["claim_id"]] = dict(binding)
            for file_row in (
                binding["claim"],
                binding["source_registry"],
                *binding["source_documents"],
            ):
                file_rows.append(dict(file_row))
        static_template = self.manifest.get("static_template")
        if (
            not isinstance(static_template, dict)
            or set(static_template)
            != {
                "contract",
                "template_id",
                "template_version",
                "claim_roster_in_policy_identity",
                "files",
                "template_sha256",
            }
            or static_template.get("contract") != STATIC_TEMPLATE_CONTRACT
            or static_template.get("template_id")
            != "casepath.synthetic-static-policy-v3"
            or static_template.get("template_version") != "3.0.0"
            or static_template.get("claim_roster_in_policy_identity") is not False
        ):
            raise WorkspaceCorpusError("static template is invalid")
        static_material = dict(static_template)
        template_sha = static_material.pop("template_sha256", None)
        if template_sha != digest_value(static_material):
            raise WorkspaceCorpusError("static template identity is invalid")
        license_receipt = self.manifest.get("license")
        if not isinstance(license_receipt, dict):
            raise WorkspaceCorpusError("public corpus license receipt is invalid")
        file_rows.append(dict(license_receipt))
        file_rows.extend(dict(row) for row in static_template.get("files", ()))
        file_rows.sort(key=lambda row: row["path"])
        seen_paths: set[str] = set()
        for row in file_rows:
            if (
                set(row) != {"path", "sha256", "size_bytes"}
                or row["path"] in seen_paths
                or SHA256_PATTERN.fullmatch(str(row["sha256"])) is None
                or type(row["size_bytes"]) is not int
            ):
                raise WorkspaceCorpusError("public corpus file row is invalid")
            seen_paths.add(row["path"])
            raw_file = _read_regular(self.root, row["path"])
            if len(raw_file) != row["size_bytes"] or sha256_bytes(raw_file) != row["sha256"]:
                raise WorkspaceCorpusError(f"public corpus file drifted: {row['path']}")
            expected_files.add(row["path"])
        actual_files: set[str] = set()
        for candidate in self.root.rglob("*"):
            if candidate.is_symlink() or (not candidate.is_file() and not candidate.is_dir()):
                raise WorkspaceCorpusError("public corpus contains a non-regular entry")
            if candidate.is_file():
                actual_files.add(candidate.relative_to(self.root).as_posix())
        if actual_files != expected_files:
            raise WorkspaceCorpusError("public corpus inventory is not closed")
        self.file_identities = {row["path"]: dict(row) for row in file_rows}
        aggregate = self.manifest.get("aggregate")
        if (
            not isinstance(aggregate, dict)
            or aggregate.get("file_count") != len(file_rows)
            or aggregate.get("size_bytes") != sum(row["size_bytes"] for row in file_rows)
            or aggregate.get("files_sha256") != digest_value(file_rows)
            or aggregate.get("claim_count") != len(rows)
            or aggregate.get("bindings_sha256") != digest_value(rows)
        ):
            raise WorkspaceCorpusError("public corpus aggregate is invalid")
        # The bundle is immutable product authority.  Full admission above
        # hashes every file; this metadata inventory is a cheap, fail-closed
        # guard for subsequent reads.  It lets callers cache already validated
        # semantic projections without rereading 45 MB on every unrelated
        # ClaimLoop commit.  ctime/inode/size plus the closed path roster make
        # in-place edits, replacements, additions, removals and symlinks
        # invalidate the cache even when a writer restores mtime.
        self._admitted_runtime_inventory_token = self._runtime_inventory_token()

    def _runtime_inventory_token(self) -> str:
        rows: list[dict[str, Any]] = []
        expected_files = {"manifest.json", *self.file_identities}
        actual_files: set[str] = set()

        def add_row(relative: str, metadata: os.stat_result) -> bool:
            mode = metadata.st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise WorkspaceCorpusError(
                    "public corpus runtime inventory contains a non-regular entry"
                )
            kind = "file" if stat.S_ISREG(mode) else "directory"
            if kind == "file":
                actual_files.add(relative)
            rows.append(
                {
                    "path": relative,
                    "kind": kind,
                    "device": metadata.st_dev,
                    "inode": metadata.st_ino,
                    "size_bytes": metadata.st_size,
                    "mtime_ns": metadata.st_mtime_ns,
                    "ctime_ns": metadata.st_ctime_ns,
                }
            )
            return kind == "directory"

        try:
            add_row(".", os.stat(self.root, follow_symlinks=False))
            pending: list[tuple[Path, str]] = [(self.root, "")]
            while pending:
                directory, prefix = pending.pop()
                with os.scandir(directory) as entries:
                    for entry in entries:
                        relative = f"{prefix}/{entry.name}" if prefix else entry.name
                        metadata = entry.stat(follow_symlinks=False)
                        if add_row(relative, metadata):
                            pending.append((Path(entry.path), relative))
        except OSError as exc:
            raise WorkspaceCorpusError(
                "public corpus runtime inventory could not be read"
            ) from exc
        rows.sort(key=lambda row: row["path"])
        if actual_files != expected_files:
            raise WorkspaceCorpusError("public corpus runtime inventory is not closed")
        return digest_value(rows)

    def runtime_identity_token(self) -> str:
        """Return the admitted immutable inventory token or fail on drift."""

        current = self._runtime_inventory_token()
        if current != self._admitted_runtime_inventory_token:
            raise WorkspaceCorpusError("public corpus inventory drifted after admission")
        return current

    @property
    def admitted_runtime_identity_token(self) -> str:
        """The token established only after full byte-level corpus admission."""

        return self._admitted_runtime_inventory_token

    @property
    def identity(self) -> dict[str, Any]:
        self._assert_manifest_unchanged()
        return {
            "manifest_sha256": self.manifest["manifest_sha256"],
            "static_template_sha256": self.manifest["static_template"][
                "template_sha256"
            ],
            **self.manifest["aggregate"],
        }

    def binding(self, claim_id: str) -> dict[str, Any]:
        self._assert_manifest_unchanged()
        try:
            return json.loads(json.dumps(self.bindings[claim_id]))
        except KeyError as exc:
            raise WorkspaceCorpusError("claim is outside the public corpus") from exc

    def claim(self, claim_id: str) -> dict[str, Any]:
        binding = self.binding(claim_id)
        raw = self._read_bound_file(binding["claim"])
        return _closed_json(raw, label=f"claim {claim_id}")

    def source_registry(self, claim_id: str) -> dict[str, Any]:
        """Return the exact, manifest-bound public source registry for a claim."""

        binding = self.binding(claim_id)
        raw = self._read_bound_file(binding["source_registry"])
        value = _closed_json(raw, label=f"source registry {claim_id}")
        if (
            value.get("contract")
            != "casepath.model-visible-source-registry/3.1.0"
            or value.get("case_id") != claim_id
            or value.get("contains_case_activation_values") is not False
            or value.get("contains_selected_paths") is not False
            or not isinstance(value.get("entries"), list)
        ):
            raise WorkspaceCorpusError("public source registry is invalid")
        return value

    def _assert_manifest_unchanged(self) -> None:
        raw = _read_regular(self.root, "manifest.json")
        if (
            len(raw) != self.manifest_size_bytes
            or sha256_bytes(raw) != self.manifest_file_sha256
        ):
            raise WorkspaceCorpusError("public corpus manifest drifted after admission")

    def _read_bound_file(self, row: Mapping[str, Any]) -> bytes:
        self._assert_manifest_unchanged()
        path = row.get("path")
        expected = self.file_identities.get(path) if isinstance(path, str) else None
        if (
            expected is None
            or any(row.get(key) != expected[key] for key in ("path", "sha256", "size_bytes"))
        ):
            raise WorkspaceCorpusError("public corpus file identity is not admitted")
        raw = _read_regular(self.root, path)
        if len(raw) != row["size_bytes"] or sha256_bytes(raw) != row["sha256"]:
            raise WorkspaceCorpusError(f"public corpus file drifted: {path}")
        return raw

    @property
    def static_policy_file_identity(self) -> dict[str, Any]:
        matches = [
            dict(row)
            for row in self.manifest["static_template"]["files"]
            if row["path"] == "policy/static-rule-templates-v3.json"
        ]
        if len(matches) != 1:
            raise WorkspaceCorpusError("static policy file identity is unavailable")
        return matches[0]

    def static_policy(self) -> dict[str, Any]:
        row = self.static_policy_file_identity
        raw = self._read_bound_file(row)
        value = _closed_json(raw, label="static policy")
        if (
            set(value)
            != {
                "contract",
                "model_visibility",
                "case_activation_values_included",
                "rule_semantics",
                "templates",
            }
            or value.get("contract") != "casepath.static-rule-templates/3.0.0"
            or value.get("case_activation_values_included") is not False
            or not isinstance(value.get("templates"), list)
        ):
            raise WorkspaceCorpusError("static policy schema is invalid")
        return value

    def artifact(self, claim_id: str, artifact_id: str) -> tuple[bytes, dict[str, Any]]:
        binding = self.binding(claim_id)
        matches = [
            row for row in binding["observable_artifacts"] if row["artifact_id"] == artifact_id
        ]
        if len(matches) != 1:
            raise WorkspaceCorpusError("artifact is outside the claim binding")
        row = matches[0]
        raw = self._read_bound_file(row)
        return raw, row


def default_public_corpus_root(corpus_id: str = CORPUS_ID) -> Path:
    """Resolve one allowlisted corpus; the legacy no-argument profile is unchanged."""
    if not isinstance(corpus_id, str) or corpus_id not in CORPUS_PROFILES:
        raise WorkspaceCorpusError("unsupported intake corpus profile")
    return Path(__file__).resolve().parent / "corpora" / corpus_id


def default_workspace_corpus_root() -> Path:
    """The operational workspace contains all 150 original intake packets."""
    return default_public_corpus_root(WORKSPACE_CORPUS_ID)
