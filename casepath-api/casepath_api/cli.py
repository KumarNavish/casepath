from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
from typing import Any

from .claim_workspace_v1 import ClaimWorkspaceService
from .insurance_protocol_v1 import (
    ActionIntentV1,
    AdapterDryRunReceiptV1,
    SOURCE_REGISTER_CAPABILITY,
    capability_catalog_sha256_v1,
    capability_catalog_v1,
)
from .storage import Storage
from .workspace_corpus import PublicCorpus, default_public_corpus_root, default_workspace_corpus_root, sha256_bytes


class CasePathCLIError(RuntimeError):
    pass


ADAPTER_SOURCE_MAX_BYTES = 4096
ADAPTER_SOURCE_MAX_AST_NODES = 128
ADAPTER_SOURCE_MAX_UNIQUE_LITERAL_BYTES = 1024
SOURCE_MANIFEST_ROOTS = ("casepath", "casepath-api", "casepath-qa", "docs", "examples")
SOURCE_MANIFEST_EXTRA_FILES = (
    ".gitattributes",
    ".gitignore",
    "AGENTS.md",
    "bin/casepath",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "CASEPATH_MASTER_KNOWLEDGE_TRANSFER.md",
)
SOURCE_MANIFEST_EXCLUSIONS = {
    "casepath/deployment.json",
    "casepath/source-manifest.json",
}


def _read_regular_nofollow(
    path: Path,
    *,
    label: str,
    max_bytes: int | None = None,
    require_single_link: bool = False,
) -> bytes:
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or (
            require_single_link and metadata.st_nlink != 1
        ):
            raise CasePathCLIError(f"{label} must be one regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            if max_bytes is not None and sum(map(len, chunks)) > max_bytes:
                raise CasePathCLIError(f"{label} exceeds its static byte cap")
        return b"".join(chunks)
    except (FileNotFoundError, OSError) as exc:
        raise CasePathCLIError(f"{label} must be one regular file") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _print(value: Any) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _adapter_static_metrics(raw: bytes, tree: ast.AST) -> dict[str, int]:
    unique_literals = {
        (type(row.value).__name__, repr(row.value))
        for row in ast.walk(tree)
        if isinstance(row, ast.Constant)
    }
    return {
        "source_bytes": len(raw),
        "ast_nodes": len(list(ast.walk(tree))),
        "unique_literal_bytes": sum(
            len(
                json.dumps(
                    row, ensure_ascii=False, separators=(",", ":")
                ).encode()
            )
            for row in sorted(unique_literals)
        ),
    }


def _source_inventory(repository: Path) -> list[str]:
    git_directory = repository / ".git"
    if git_directory.exists():
        try:
            output = subprocess.check_output(
                [
                    "/usr/bin/git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "--",
                    *SOURCE_MANIFEST_ROOTS,
                    *SOURCE_MANIFEST_EXTRA_FILES,
                ],
                cwd=repository,
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CasePathCLIError("source-manifest inventory cannot be resolved") from exc
        candidates = output.splitlines()
    else:
        candidates = []
        for root in SOURCE_MANIFEST_ROOTS:
            root_path = repository / root
            if root_path.is_symlink() or not root_path.is_dir():
                raise CasePathCLIError("source-manifest root is not a regular directory")
            candidates.extend(
                path.relative_to(repository).as_posix()
                for path in root_path.rglob("*")
                if path.is_file()
            )
        candidates.extend(SOURCE_MANIFEST_EXTRA_FILES)
    paths: list[str] = []
    for candidate in candidates:
        normalized = Path(candidate).as_posix()
        if (
            normalized in SOURCE_MANIFEST_EXCLUSIONS
            or normalized.startswith("casepath-api/artifacts/")
            or "__pycache__" in Path(normalized).parts
            or Path(normalized).suffix in {".pyc", ".pyo"}
        ):
            continue
        path = repository / normalized
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise CasePathCLIError("source-manifest inventory contains an absent path") from exc
        if path.is_symlink() or not stat.S_ISREG(mode):
            raise CasePathCLIError("source-manifest inventory contains a non-regular path")
        paths.append(normalized)
    return sorted(set(paths))


def _validate_source_manifest(
    repository: Path, raw: bytes
) -> tuple[dict[str, dict[str, object]], str]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CasePathCLIError("source manifest is not canonical JSON") from exc
    expected_keys = {
        "artifact_manifest",
        "contract",
        "file_count",
        "files",
        "gate_count",
        "gates",
        "inventory_policy",
        "release_id",
    }
    expected_roots = [*SOURCE_MANIFEST_ROOTS, *SOURCE_MANIFEST_EXTRA_FILES]
    if (
        not isinstance(value, dict)
        or set(value) != expected_keys
        or value.get("contract") != "casepath.source-manifest/2.1.0"
        or not isinstance(value.get("release_id"), str)
        or not value["release_id"]
        or value.get("inventory_policy")
        != {
            "includes_nonignored_pending_files": True,
            "roots": expected_roots,
            "self_output_excluded": "casepath/source-manifest.json",
        }
        or not isinstance(value.get("files"), list)
        or type(value.get("file_count")) is not int
        or not isinstance(value.get("gates"), list)
        or type(value.get("gate_count")) is not int
    ):
        raise CasePathCLIError("source manifest schema or policy is invalid")
    artifact_manifest = value.get("artifact_manifest")
    if (
        not isinstance(artifact_manifest, dict)
        or set(artifact_manifest) != {"model_visible_files", "path", "sha256"}
        or artifact_manifest.get("path")
        != "casepath-api/artifacts/artifact-manifest.json"
        or not isinstance(artifact_manifest.get("model_visible_files"), list)
        or not isinstance(artifact_manifest.get("sha256"), str)
    ):
        raise CasePathCLIError("source manifest artifact binding is invalid")
    rows: dict[str, dict[str, object]] = {}
    ordered_paths: list[str] = []
    for row in value["files"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"executable", "path", "sha256", "size_bytes"}
            or type(row.get("executable")) is not bool
            or not isinstance(row.get("path"), str)
            or not row["path"]
            or "\\" in row["path"]
            or Path(row["path"]).is_absolute()
            or Path(row["path"]).as_posix() != row["path"]
            or any(part in {"", ".", ".."} for part in Path(row["path"]).parts)
            or not isinstance(row.get("sha256"), str)
            or len(row["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in row["sha256"])
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] < 0
        ):
            raise CasePathCLIError("source manifest contains an invalid file row")
        path_text = row["path"]
        if path_text in rows:
            raise CasePathCLIError("source manifest contains duplicate file rows")
        path = repository / path_text
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise CasePathCLIError("source manifest contains an absent file") from exc
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise CasePathCLIError("source manifest contains a non-regular file")
        file_raw = _read_regular_nofollow(path, label=f"source file {path_text}")
        if row != {
            "executable": bool(metadata.st_mode & stat.S_IXUSR),
            "path": path_text,
            "sha256": sha256_bytes(file_raw),
            "size_bytes": len(file_raw),
        }:
            raise CasePathCLIError("source manifest file identity differs from disk")
        rows[path_text] = row
        ordered_paths.append(path_text)
    actual_paths = _source_inventory(repository)
    if (
        ordered_paths != sorted(ordered_paths)
        or ordered_paths != actual_paths
        or value["file_count"] != len(ordered_paths)
    ):
        raise CasePathCLIError("source manifest roster is incomplete or unordered")
    expected_gates = [
        {"path": path, "sha256": rows[path]["sha256"]}
        for path in ordered_paths
        if path.startswith("casepath-qa/")
        and Path(path).suffix in {".mjs", ".py"}
        and Path(path).name.startswith(("browser-", "check-", "reset-", "patch_"))
    ]
    if value["gates"] != expected_gates or value["gate_count"] != len(expected_gates):
        raise CasePathCLIError("source manifest gate roster is invalid")
    artifact_path = repository / artifact_manifest["path"]
    artifact_raw = _read_regular_nofollow(
        artifact_path, label="artifact manifest"
    )
    if artifact_manifest["sha256"] != sha256_bytes(artifact_raw):
        raise CasePathCLIError("source manifest artifact identity differs from disk")
    roster_sha256 = sha256_bytes(
        json.dumps(
            value["files"],
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    )
    return rows, roster_sha256


def _service(corpus: PublicCorpus | None = None) -> ClaimWorkspaceService:
    return ClaimWorkspaceService(
        Storage(), corpus=corpus or PublicCorpus(default_public_corpus_root())
    )


def seed(args: argparse.Namespace) -> int:
    repository = Path(__file__).resolve().parents[2]
    source_manifest_path = repository / "casepath/source-manifest.json"
    source_manifest_raw = _read_regular_nofollow(
        source_manifest_path, label="source manifest"
    )
    _, source_roster_sha256 = _validate_source_manifest(
        repository, source_manifest_raw
    )
    corpus = PublicCorpus(default_public_corpus_root(args.corpus))
    corpus_id = corpus.manifest["corpus_id"]
    if args.corpus != corpus_id:
        raise CasePathCLIError(
            f"only the bundled public-safe {corpus_id} corpus is available"
        )
    service = _service(corpus)
    source_manifest_before_seed = _read_regular_nofollow(
        source_manifest_path, label="source manifest"
    )
    _, source_roster_before_seed = _validate_source_manifest(
        repository, source_manifest_before_seed
    )
    if (
        source_manifest_before_seed != source_manifest_raw
        or source_roster_before_seed != source_roster_sha256
    ):
        raise CasePathCLIError("source manifest drifted before seed mutation")
    receipt = service.seed()
    source_manifest_after_seed = _read_regular_nofollow(
        source_manifest_path, label="source manifest"
    )
    _, source_roster_after_seed = _validate_source_manifest(
        repository, source_manifest_after_seed
    )
    if (
        source_manifest_after_seed != source_manifest_raw
        or source_roster_after_seed != source_roster_sha256
    ):
        raise CasePathCLIError("source manifest drifted during seed mutation")
    source_authority = {
        "contract": "casepath.sealed-seed-source-authority/1.0.0",
        "source_manifest_file_sha256": sha256_bytes(source_manifest_raw),
        "source_manifest_roster_sha256": source_roster_sha256,
    }
    material = {
        "contract": "casepath.sealed-workspace-seed/1.0.0",
        "seed_receipt": receipt,
        "source_authority": source_authority,
    }
    _print(
        {
            **material,
            "receipt_sha256": sha256_bytes(
                json.dumps(
                    material,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ),
        }
    )
    return 0


def replay(args: argparse.Namespace) -> int:
    database_path = Path(
        os.getenv("CASEPATH_DB_PATH", "/tmp/casepath-useful-demo/casepath.db")
    )
    service = ClaimWorkspaceService.open_read_only(
        database_path,
        corpus=PublicCorpus(default_workspace_corpus_root()),
    )
    detail = service.detail(args.claim_id)
    state = detail["state"]
    receipt = {
        "contract": "casepath.read-only-claim-replay/1.0.0",
        "claim_id": args.claim_id,
        "revision": state["revision"],
        "last_event_sha256": state["last_event_sha256"],
        "state_sha256": state["state_sha256"],
        "binding_sha256": state["binding"]["binding_sha256"],
        "detail_sha256": detail["detail_sha256"],
        "journal_verified": True,
        "model_calls": 0,
        "provider_calls": 0,
        "credential_reads": 0,
        "cost_usd": 0,
    }
    _print({**receipt, "receipt_sha256": sha256_bytes(json.dumps(receipt, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode())})
    return 0


def run_tests(args: argparse.Namespace) -> int:
    repository = Path(__file__).resolve().parents[2]
    source_manifest_raw = _read_regular_nofollow(
        repository / "casepath/source-manifest.json", label="source manifest"
    )
    _validate_source_manifest(repository, source_manifest_raw)
    source_commit = (os.getenv("CASEPATH_SOURCE_COMMIT") or "").strip().lower()
    if (
        not isinstance(source_commit, str)
        or len(source_commit) != 40
        or any(character not in "0123456789abcdef" for character in source_commit)
    ):
        raise CasePathCLIError("runtime source commit is unavailable")
    targets = [
        repository / "casepath-api" / "tests" / "test_claim_workspace_v1.py"
    ] if args.workspace_only else [
        repository / "casepath-api" / "tests",
        repository / "casepath" / "tools" / "test_build_deployment_identity.py",
        repository / "casepath" / "tools" / "test_casepath_release.py",
    ]
    with tempfile.TemporaryDirectory(prefix="casepath-product-test-") as temporary:
        root = Path(temporary)
        for directory in ("home", "tmp", "pycache", "artifact-registry"):
            (root / directory).mkdir()
        environment = {
            "HOME": str(root / "home"),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "PYTHONSAFEPATH": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": str(root / "pycache"),
            "PYTHONPATH": str(repository / "casepath-api"),
            "SOURCE_DATE_EPOCH": "1786406400",
            "TMPDIR": str(root / "tmp"),
            "TZ": "UTC",
            "CASEPATH_MODEL_MODE": "deterministic_reference",
            "CASEPATH_SOURCE_COMMIT": source_commit,
            "CASEPATH_DB_PATH": str(root / "casepath.db"),
            "CASEPATH_ARTIFACT_REGISTRY_PATH": str(root / "artifact-registry"),
            "CASEPATH_ENV_LOCK_HELD": os.getenv("CASEPATH_ENV_LOCK_HELD", ""),
            "CASEPATH_ENV_READY": os.getenv("CASEPATH_ENV_READY", ""),
            "CASEPATH_UV": os.getenv("CASEPATH_UV_RESOLVED", ""),
        }
        command = [
            sys.executable,
            "-P",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *(str(target) for target in targets),
        ]
        completed = subprocess.run(
            command, cwd=repository, env=environment, check=False
        )
        if completed.returncode == 0:
            receipt = {
                "contract": "casepath.isolated-backend-static-test/1.0.0",
                "targets": [target.relative_to(repository).as_posix() for target in targets],
                "persistent_product_database_used": False,
                "persistent_artifact_registry_used": False,
                "model_mode": "deterministic_reference",
                "provider_credential_names_present": [],
                "external_network_activity_attested": False,
            }
            _print(
                {
                    **receipt,
                    "receipt_sha256": sha256_bytes(
                        json.dumps(
                            receipt,
                            ensure_ascii=False,
                            allow_nan=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ),
                }
            )
        return completed.returncode


def _adapter_module(path: Path, root: Path, raw: bytes, adapter_class: type[Any]) -> Any:
    tree = ast.parse(raw, filename=str(path))
    factory_nodes = [row for row in tree.body if isinstance(row, ast.FunctionDef)]
    if len(factory_nodes) != 1:
        raise CasePathCLIError("captured adapter source lacks its audited factory")
    namespace = {
        "__builtins__": {},
        "Path": Path,
        "LocalArtifactRegistryAdapterV1": adapter_class,
    }
    try:
        factory_module = ast.fix_missing_locations(
            ast.Module(body=[factory_nodes[0]], type_ignores=[])
        )
        exec(compile(factory_module, str(path), "exec", dont_inherit=True), namespace)
    except Exception as exc:
        raise CasePathCLIError("captured adapter factory could not be loaded") from exc
    factory = namespace.get("build_adapter")
    if not callable(factory):
        raise CasePathCLIError("adapter module must export build_adapter(root)")
    return factory(root)


def adapter_check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = Path(os.path.abspath(path))
    raw = _read_regular_nofollow(
        path,
        label="adapter",
        max_bytes=ADAPTER_SOURCE_MAX_BYTES,
        require_single_link=True,
    )
    try:
        tree = ast.parse(raw, filename=str(path))
    except SyntaxError as exc:
        raise CasePathCLIError("adapter source is invalid Python") from exc
    static_metrics = _adapter_static_metrics(raw, tree)
    if static_metrics["ast_nodes"] > ADAPTER_SOURCE_MAX_AST_NODES:
        raise CasePathCLIError("adapter exceeds its static AST-node cap")
    if (
        static_metrics["unique_literal_bytes"]
        > ADAPTER_SOURCE_MAX_UNIQUE_LITERAL_BYTES
    ):
        raise CasePathCLIError("adapter exceeds its static literal-byte cap")
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(
        body[0].value, ast.Constant
    ) and isinstance(body[0].value.value, str):
        body.pop(0)
    imports = [row for row in body if isinstance(row, (ast.Import, ast.ImportFrom))]
    functions = [row for row in body if isinstance(row, ast.FunctionDef)]
    expected_imports = {
        ("pathlib", (("Path", None),)),
        (
            "casepath_api.local_artifact_registry",
            (("LocalArtifactRegistryAdapterV1", None),),
        ),
    }
    actual_imports = {
        (
            row.module if isinstance(row, ast.ImportFrom) else None,
            tuple((name.name, name.asname) for name in row.names),
        )
        for row in imports
    }
    if (
        any(isinstance(row, ast.Import) for row in imports)
        or len(imports) != 2
        or any(
            not isinstance(row, ast.ImportFrom) or row.level != 0
            for row in imports
        )
        or actual_imports != expected_imports
        or len(functions) != 1
        or len(body) != len(imports) + 1
    ):
        raise CasePathCLIError(
            "adapter-check v1 accepts only the audited local-registry constructor stub"
        )
    factory_node = functions[0]
    statements = list(factory_node.body)
    if statements and isinstance(statements[0], ast.Expr) and isinstance(
        statements[0].value, ast.Constant
    ) and isinstance(statements[0].value.value, str):
        statements.pop(0)
    if (
        factory_node.name != "build_adapter"
        or factory_node.decorator_list
        or factory_node.args.defaults
        or factory_node.args.kw_defaults
        or factory_node.args.posonlyargs
        or factory_node.args.kwonlyargs
        or factory_node.args.vararg is not None
        or factory_node.args.kwarg is not None
        or len(factory_node.args.args) != 1
        or factory_node.args.args[0].arg != "root"
        or not isinstance(factory_node.args.args[0].annotation, ast.Name)
        or factory_node.args.args[0].annotation.id != "Path"
        or not isinstance(factory_node.returns, ast.Name)
        or factory_node.returns.id != "LocalArtifactRegistryAdapterV1"
        or factory_node.type_comment is not None
        or bool(getattr(factory_node, "type_params", ()))
        or len(statements) != 1
        or not isinstance(statements[0], ast.Return)
        or not isinstance(statements[0].value, ast.Call)
        or not isinstance(statements[0].value.func, ast.Name)
        or statements[0].value.func.id != "LocalArtifactRegistryAdapterV1"
        or len(statements[0].value.args) != 1
        or not isinstance(statements[0].value.args[0], ast.Name)
        or statements[0].value.args[0].id != "root"
        or statements[0].value.keywords
    ):
        raise CasePathCLIError("adapter build_adapter(root) body is not the audited stub")
    repository = Path(__file__).resolve().parents[2]
    implementation_relative = "casepath-api/casepath_api/local_artifact_registry.py"
    implementation_path = repository / implementation_relative
    source_manifest_path = repository / "casepath/source-manifest.json"
    implementation_raw = _read_regular_nofollow(
        implementation_path, label="local adapter implementation"
    )
    source_manifest_raw = _read_regular_nofollow(
        source_manifest_path, label="source manifest"
    )
    source_rows, source_roster_sha256 = _validate_source_manifest(
        repository, source_manifest_raw
    )
    implementation_row = source_rows.get(implementation_relative)
    if implementation_row != {
        "path": implementation_relative,
        "sha256": sha256_bytes(implementation_raw),
        "size_bytes": len(implementation_raw),
        "executable": False,
    }:
        raise CasePathCLIError(
            "local adapter implementation differs from source-manifest authority"
        )
    checker_relative = "casepath-api/casepath_api/cli.py"
    checker_path = repository / checker_relative
    checker_raw = _read_regular_nofollow(checker_path, label="adapter checker")
    checker_row = source_rows.get(checker_relative)
    if checker_row != {
        "path": checker_relative,
        "sha256": sha256_bytes(checker_raw),
        "size_bytes": len(checker_raw),
        "executable": False,
    }:
        raise CasePathCLIError("adapter checker differs from source-manifest authority")
    implementation_manifest_file_sha256 = sha256_bytes(
        source_manifest_raw
    )
    implementation_module_name = "casepath_api._checked_local_artifact_registry"
    implementation_module = types.ModuleType(implementation_module_name)
    implementation_module.__file__ = str(implementation_path)
    implementation_module.__package__ = "casepath_api"
    sys.modules[implementation_module_name] = implementation_module
    try:
        exec(
            compile(
                implementation_raw,
                str(implementation_path),
                "exec",
                dont_inherit=True,
            ),
            implementation_module.__dict__,
        )
        adapter_class = implementation_module.LocalArtifactRegistryAdapterV1
        material_class = implementation_module.LocalRegistryMaterialV1
    except Exception as exc:
        raise CasePathCLIError(
            "source-manifest-bound local adapter implementation could not be loaded"
        ) from exc
    with tempfile.TemporaryDirectory(prefix="casepath-adapter-check-") as temporary:
        adapter = _adapter_module(path, Path(temporary), raw, adapter_class)
        if (
            getattr(adapter, "capability_id", None) != "source.register@1"
            or not isinstance(getattr(adapter, "adapter_id", None), str)
            or not callable(getattr(adapter, "stage", None))
            or not callable(getattr(adapter, "execute", None))
            or not callable(getattr(adapter, "status", None))
            or not callable(getattr(adapter, "reconcile", None))
            or not callable(getattr(adapter, "cancel", None))
        ):
            raise CasePathCLIError("adapter does not implement the source.register@1 boundary")
        if adapter.implementation_source_sha256 != sha256_bytes(implementation_raw):
            raise CasePathCLIError(
                "executed adapter implementation differs from captured source authority"
            )
        content = "Synthetic adapter-check evidence. No provider or external system was used."
        material = material_class(
            filename="adapter-check.txt",
            media_type="text/plain; charset=utf-8",
            content=content,
            claimed_content_sha256=sha256_bytes(content.encode("utf-8")),
        )
        staged = adapter.stage(
            session_id="adapter-check-session",
            loop_id="adapter-check-loop",
            claim_id="adapter-check-claim",
            record_version="adapter-check-v1",
            material=material,
            staged_at="2026-01-01T00:00:00+00:00",
        )
        if adapter.staged(staged.receipt_sha256) != staged:
            raise CasePathCLIError("adapter stage replay is not byte-identical")
        source_state_sha256 = sha256_bytes(b"adapter-check-source-state")
        proposal_sha256 = sha256_bytes(b"adapter-check-proposal")
        decision_sha256 = sha256_bytes(b"adapter-check-decision")
        compatibility_action_sha256 = sha256_bytes(b"adapter-check-action")
        authorized = {
            item.capability_id: item for item in capability_catalog_v1()
        }[SOURCE_REGISTER_CAPABILITY]
        dry_run_material = {
            "contract": "casepath.artifact-registry-dry-run/1.0.0",
            "source_state_sha256": source_state_sha256,
            "proposal_sha256": proposal_sha256,
            "staged_artifact_receipt_sha256": staged.receipt_sha256,
            "content_sha256": staged.content_sha256,
            "capability_id": SOURCE_REGISTER_CAPABILITY,
            "adapter_id": adapter.adapter_id,
            "adapter_implementation_id": adapter.implementation_id,
            "adapter_implementation_source_sha256": (
                adapter.implementation_source_sha256
            ),
            "adapter_implementation_sha256": adapter.implementation_sha256,
            "evaluated_at": "2026-01-01T00:01:00+00:00",
            "would_commit": True,
        }
        dry_run = AdapterDryRunReceiptV1.model_validate(
            {
                **dry_run_material,
                "receipt_sha256": sha256_bytes(
                    json.dumps(
                        dry_run_material,
                        ensure_ascii=False,
                        allow_nan=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ),
            }
        )
        effect_material = {
            "contract": "casepath.local-registration-effect/1.0.0",
            "session_id": staged.session_id,
            "loop_id": staged.loop_id,
            "claim_id": staged.claim_id,
            "record_version": staged.record_version,
            "capability_id": SOURCE_REGISTER_CAPABILITY,
            "content_sha256": staged.content_sha256,
        }
        effect_idempotency_key = sha256_bytes(
            json.dumps(
                effect_material,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )
        intent_material = {
            "contract": "casepath.action-intent/1.0.0",
            "session_id": staged.session_id,
            "loop_id": staged.loop_id,
            "claim_id": staged.claim_id,
            "record_version": staged.record_version,
            "source_revision": 1,
            "source_state_sha256": source_state_sha256,
            "proposal_sha256": proposal_sha256,
            "decision_sha256": decision_sha256,
            "capability_id": SOURCE_REGISTER_CAPABILITY,
            "adapter_id": adapter.adapter_id,
            "policy_version": "casepath.insurance-action-authority/1.0.0",
            "capability_catalog_sha256": capability_catalog_sha256_v1(),
            "authorized_descriptor_sha256": authorized.descriptor_sha256,
            "adapter_implementation_id": adapter.implementation_id,
            "adapter_implementation_source_sha256": (
                adapter.implementation_source_sha256
            ),
            "adapter_implementation_sha256": adapter.implementation_sha256,
            "compatibility_action_sha256": compatibility_action_sha256,
            "dry_run_receipt_sha256": dry_run.receipt_sha256,
            "staged_artifact_receipt_sha256": staged.receipt_sha256,
            "content_sha256": staged.content_sha256,
            "effect_idempotency_key": effect_idempotency_key,
            "created_at": "2026-01-01T00:01:00+00:00",
            "expires_at": "2026-01-01T01:01:00+00:00",
            "dry_run_passed": True,
        }
        intent = ActionIntentV1.model_validate(
            {
                **intent_material,
                "intent_sha256": sha256_bytes(
                    json.dumps(
                        intent_material,
                        ensure_ascii=False,
                        allow_nan=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ),
            }
        )
        if adapter.dry_run(
            intent=intent,
            staged=staged,
            evaluated_at=intent.created_at,
        ) != dry_run:
            raise CasePathCLIError("adapter dry-run receipt differs")
        committed = adapter.execute(
            intent=intent,
            staged=staged,
            executed_at="2026-01-01T00:02:00+00:00",
        )
        replayed = adapter.execute(
            intent=intent,
            staged=staged,
            executed_at="2026-01-01T00:02:00+00:00",
        )
        if (
            committed.status != "committed"
            or replayed != committed
            or adapter.status(intent=intent) != committed
            or adapter.reconcile(intent=intent, staged=staged) != committed
            or adapter.effect_count() != 1
            or adapter.content_blob_count() != 1
        ):
            raise CasePathCLIError("adapter exact-once lifecycle is invalid")
        receipt = {
            "contract": "casepath.local-adapter-check/1.0.0",
            "adapter_source_sha256": sha256_bytes(raw),
            "adapter_id": adapter.adapter_id,
            "implementation_id": adapter.implementation_id,
            "implementation_source_sha256": adapter.implementation_source_sha256,
            "implementation_sha256": adapter.implementation_sha256,
            "staged_receipt_sha256": staged.receipt_sha256,
            "stage_replay_exact": True,
            "dry_run_receipt_sha256": dry_run.receipt_sha256,
            "action_receipt_sha256": committed.receipt_sha256,
            "execute_replay_exact": True,
            "status_replay_exact": True,
            "reconcile_replay_exact": True,
            "effect_count": adapter.effect_count(),
            "content_blob_count": adapter.content_blob_count(),
            "adapter_source_profile": "exact_local_registry_constructor_stub_v1",
            "adapter_source_profile_enforced_before_import": True,
            "adapter_static_metrics": static_metrics,
            "adapter_static_caps": {
                "source_bytes": ADAPTER_SOURCE_MAX_BYTES,
                "ast_nodes": ADAPTER_SOURCE_MAX_AST_NODES,
                "unique_literal_bytes": ADAPTER_SOURCE_MAX_UNIQUE_LITERAL_BYTES,
            },
            "implementation_source_manifest_row": implementation_row,
            "checker_source_manifest_row": checker_row,
            "source_manifest_file_sha256": implementation_manifest_file_sha256,
            "source_manifest_roster_sha256": source_roster_sha256,
            "source_manifest_closed_and_complete": True,
            "candidate_stub_network_primitive_count": 0,
            "network_claim_boundary": "the accepted candidate stub contains no network-capable code; this receipt does not infer OS-level network denial for imported dependencies",
            "model_calls": 0,
            "provider_calls": 0,
            "credential_reads": 0,
            "cost_usd": 0,
        }
        if (
            _read_regular_nofollow(
                implementation_path, label="local adapter implementation"
            )
            != implementation_raw
            or _read_regular_nofollow(source_manifest_path, label="source manifest")
            != source_manifest_raw
            or _read_regular_nofollow(checker_path, label="adapter checker")
            != checker_raw
        ):
            raise CasePathCLIError(
                "local adapter implementation drifted during conformance execution"
            )
        _validate_source_manifest(repository, source_manifest_raw)
        _print({**receipt, "receipt_sha256": sha256_bytes(json.dumps(receipt, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode())})
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="casepath")
    commands = value.add_subparsers(dest="command", required=True)
    seed_parser = commands.add_parser("seed", help="import a bundled observable corpus")
    seed_parser.add_argument("--corpus", required=True)
    seed_parser.set_defaults(handler=seed)
    replay_parser = commands.add_parser("replay", help="verify and replay one claim journal")
    replay_parser.add_argument("claim_id")
    replay_parser.set_defaults(handler=replay)
    test_parser = commands.add_parser("test", help="run the deterministic product test suite")
    test_parser.add_argument("--workspace-only", action="store_true", help=argparse.SUPPRESS)
    test_parser.set_defaults(handler=run_tests)
    adapter_parser = commands.add_parser("adapter-check", help="validate a local evidence adapter")
    adapter_parser.add_argument("path")
    adapter_parser.set_defaults(handler=adapter_check)
    return value


def main() -> int:
    try:
        args = parser().parse_args()
        return int(args.handler(args))
    except (CasePathCLIError, ValueError) as exc:
        print(f"CasePath command failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
