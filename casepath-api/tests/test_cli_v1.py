from __future__ import annotations

from argparse import Namespace
import importlib.util
import json
from pathlib import Path
import shutil
import os
import sqlite3
import stat
import subprocess
import sys
import time

import pytest

import casepath_api.cli as cli_module

from casepath_api.cli import CasePathCLIError, _adapter_module, adapter_check, seed
from casepath_api.claim_workspace_v1 import (
    EVENT_CONTRACT as WORKSPACE_EVENT_CONTRACT,
    EVENT_TYPES as WORKSPACE_EVENT_TYPES,
)
from casepath_api.validate_journal import JournalValidationError, validate_journal


REPOSITORY = Path(__file__).resolve().parents[2]
BUNDLED_CORPUS_ID = "synthetic-dev-60"


def test_read_only_journal_validator_accepts_only_an_exact_pristine_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "casepath.db"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version=0")
    receipt = validate_journal(database)
    assert receipt["loop_count"] == 0
    assert receipt["event_count"] == 0

    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE untrusted_authority (value TEXT)")
    with pytest.raises(JournalValidationError, match="not pristine"):
        validate_journal(database)


def test_audited_local_adapter_completes_exact_once_lifecycle() -> None:
    example_root = REPOSITORY / "examples"
    before = {
        path.relative_to(example_root).as_posix(): path.read_bytes()
        for path in example_root.rglob("*")
        if path.is_file()
    }
    assert adapter_check(
        Namespace(path=str(REPOSITORY / "examples/local_source_adapter.py"))
    ) == 0
    after = {
        path.relative_to(example_root).as_posix(): path.read_bytes()
        for path in example_root.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not any("__pycache__" in path for path in after)


@pytest.mark.parametrize(
    "escape_kind",
    (
        "top_level_write",
        "dynamic_import",
    ),
)
def test_adapter_check_rejects_executable_escape_before_import(
    tmp_path: Path, escape_kind: str
) -> None:
    source = (REPOSITORY / "examples/local_source_adapter.py").read_text()
    marker = tmp_path / "escape-marker"
    extra_source = (
        f"\nopen({str(marker)!r}, 'w').write('escaped')\n"
        if escape_kind == "top_level_write"
        else "\ndef alternate():\n    return __import__('socket')\n"
    )
    candidate = tmp_path / "candidate.py"
    candidate.write_text(source + extra_source)
    with pytest.raises(CasePathCLIError, match="audited"):
        adapter_check(Namespace(path=str(candidate)))
    assert not marker.exists()


@pytest.mark.parametrize(
    "signature",
    (
        "root: Path = Path(MARKER).write_text('escaped')",
        "root: Path(MARKER).write_text('escaped')",
    ),
)
def test_adapter_check_rejects_import_time_signature_escape(
    tmp_path: Path, signature: str
) -> None:
    marker = tmp_path / "signature-marker"
    source = (REPOSITORY / "examples/local_source_adapter.py").read_text()
    source = source.replace(
        "root: Path) -> LocalArtifactRegistryAdapterV1",
        signature.replace("MARKER", repr(str(marker)))
        + ") -> LocalArtifactRegistryAdapterV1",
    )
    candidate = tmp_path / "candidate.py"
    candidate.write_text(source)
    with pytest.raises(CasePathCLIError, match="audited stub"):
        adapter_check(Namespace(path=str(candidate)))
    assert not marker.exists()


def test_adapter_check_rejects_import_time_return_annotation_escape(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "return-annotation-marker"
    source = (REPOSITORY / "examples/local_source_adapter.py").read_text()
    source = source.replace(
        "-> LocalArtifactRegistryAdapterV1:",
        f"-> Path({str(marker)!r}).write_text('escaped'):",
    )
    candidate = tmp_path / "candidate.py"
    candidate.write_text(source)
    with pytest.raises(CasePathCLIError, match="audited stub"):
        adapter_check(Namespace(path=str(candidate)))
    assert not marker.exists()


def test_adapter_module_executes_only_captured_bytes_after_path_replacement(
    tmp_path: Path,
) -> None:
    from casepath_api.local_artifact_registry import LocalArtifactRegistryAdapterV1

    candidate = tmp_path / "candidate.py"
    source = (REPOSITORY / "examples/local_source_adapter.py").read_bytes()
    candidate.write_bytes(source)
    marker = tmp_path / "replacement-marker"
    candidate.write_text(f"open({str(marker)!r}, 'w').write('escaped')\n")
    adapter = _adapter_module(
        candidate,
        tmp_path / "registry",
        source,
        LocalArtifactRegistryAdapterV1,
    )
    assert adapter.capability_id == "source.register@1"
    assert not marker.exists()


def test_adapter_check_rejects_symlink_before_read(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    shutil.copyfile(REPOSITORY / "examples/local_source_adapter.py", source)
    candidate = tmp_path / "candidate.py"
    candidate.symlink_to(source)
    with pytest.raises(CasePathCLIError, match="one regular file"):
        adapter_check(Namespace(path=str(candidate)))


def test_adapter_check_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.py"
    os.mkfifo(candidate)
    with pytest.raises(CasePathCLIError, match="one regular file"):
        adapter_check(Namespace(path=str(candidate)))


def test_adapter_check_rejects_local_implementation_source_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    implementation = (
        REPOSITORY / "casepath-api/casepath_api/local_artifact_registry.py"
    )
    original = cli_module._read_regular_nofollow
    implementation_reads = 0

    def drifted_read(path: Path, **kwargs: object) -> bytes:
        nonlocal implementation_reads
        value = original(path, **kwargs)
        if path == implementation:
            implementation_reads += 1
            if implementation_reads == 3:
                return value + b"\n# drift\n"
        return value

    monkeypatch.setattr(cli_module, "_read_regular_nofollow", drifted_read)
    with pytest.raises(CasePathCLIError, match="drifted during conformance"):
        adapter_check(
            Namespace(path=str(REPOSITORY / "examples/local_source_adapter.py"))
        )
    assert implementation_reads == 3


def test_adapter_check_rejects_partial_source_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = REPOSITORY / "casepath/source-manifest.json"
    original = cli_module._read_regular_nofollow

    def partial_read(path: Path, **kwargs: object) -> bytes:
        if path == manifest:
            return b'{"contract":"casepath.source-manifest/2.1.0","files":[]}'
        return original(path, **kwargs)

    monkeypatch.setattr(cli_module, "_read_regular_nofollow", partial_read)
    with pytest.raises(CasePathCLIError, match="schema or policy"):
        adapter_check(
            Namespace(path=str(REPOSITORY / "examples/local_source_adapter.py"))
        )


def test_adapter_check_rejects_transitive_source_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = REPOSITORY / "casepath-api/casepath_api/claim_workspace_v1.py"
    original = cli_module._read_regular_nofollow
    exercised = False

    def drifted_read(path: Path, **kwargs: object) -> bytes:
        nonlocal exercised
        value = original(path, **kwargs)
        if path == dependency:
            exercised = True
            return value + b"\n# transitive drift\n"
        return value

    monkeypatch.setattr(cli_module, "_read_regular_nofollow", drifted_read)
    with pytest.raises(CasePathCLIError, match="identity differs"):
        adapter_check(
            Namespace(path=str(REPOSITORY / "examples/local_source_adapter.py"))
        )
    assert exercised is True


def test_seed_rejects_stale_source_before_opening_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dependency = REPOSITORY / "casepath-api/casepath_api/workspace_corpus.py"
    original = cli_module._read_regular_nofollow
    service_opened = False

    def drifted_read(path: Path, **kwargs: object) -> bytes:
        value = original(path, **kwargs)
        if path == dependency:
            return value + b"\n# stale source canary\n"
        return value

    def forbidden_service(_corpus: object) -> object:
        nonlocal service_opened
        service_opened = True
        raise AssertionError("storage opened before sealed-source admission")

    database = tmp_path / "casepath.db"
    monkeypatch.setenv("CASEPATH_DB_PATH", str(database))
    monkeypatch.setenv(
        "CASEPATH_ARTIFACT_REGISTRY_PATH", str(tmp_path / "artifact-registry")
    )
    monkeypatch.setattr(cli_module, "_read_regular_nofollow", drifted_read)
    monkeypatch.setattr(cli_module, "_service", forbidden_service)
    with pytest.raises(CasePathCLIError, match="source manifest file identity differs"):
        seed(Namespace(corpus=BUNDLED_CORPUS_ID))
    assert service_opened is False
    assert not database.exists()


def test_seed_rejects_source_drift_after_service_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = REPOSITORY / "casepath-api/casepath_api/workspace_corpus.py"
    original = cli_module._read_regular_nofollow
    service_constructed = False
    seed_called = False

    class FakeService:
        def seed(self) -> dict[str, object]:
            nonlocal seed_called
            seed_called = True
            return {}

    def construct_service(_corpus: object) -> FakeService:
        nonlocal service_constructed
        service_constructed = True
        return FakeService()

    def drift_after_construction(path: Path, **kwargs: object) -> bytes:
        value = original(path, **kwargs)
        if service_constructed and path == dependency:
            return value + b"\n# post-construction drift canary\n"
        return value

    monkeypatch.setattr(cli_module, "_service", construct_service)
    monkeypatch.setattr(cli_module, "_read_regular_nofollow", drift_after_construction)
    with pytest.raises(CasePathCLIError, match="identity differs"):
        seed(Namespace(corpus=BUNDLED_CORPUS_ID))
    assert service_constructed is True
    assert seed_called is False


def test_seed_withholds_receipt_when_source_drifts_during_mutation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dependency = REPOSITORY / "casepath-api/casepath_api/workspace_corpus.py"
    original = cli_module._read_regular_nofollow
    seed_finished = False

    class FakeService:
        def seed(self) -> dict[str, object]:
            nonlocal seed_finished
            seed_finished = True
            return {"contract": "test.seed", "receipt_sha256": "0" * 64}

    def drift_after_seed(path: Path, **kwargs: object) -> bytes:
        value = original(path, **kwargs)
        if seed_finished and path == dependency:
            return value + b"\n# post-seed drift canary\n"
        return value

    monkeypatch.setattr(cli_module, "_service", lambda _corpus: FakeService())
    monkeypatch.setattr(cli_module, "_read_regular_nofollow", drift_after_seed)
    with pytest.raises(CasePathCLIError, match="identity differs"):
        seed(Namespace(corpus=BUNDLED_CORPUS_ID))
    assert seed_finished is True
    assert capsys.readouterr().out == ""


def test_adapter_static_byte_cap_has_exact_boundary(tmp_path: Path) -> None:
    source = (REPOSITORY / "examples/local_source_adapter.py").read_bytes()
    exact = source + b"#" + b"x" * (4096 - len(source) - 2) + b"\n"
    assert len(exact) == 4096
    candidate = tmp_path / "exact.py"
    candidate.write_bytes(exact)
    assert adapter_check(Namespace(path=str(candidate))) == 0
    candidate.write_bytes(exact + b"\n")
    with pytest.raises(CasePathCLIError, match="static byte cap"):
        adapter_check(Namespace(path=str(candidate)))


def test_adapter_static_ast_and_literal_caps_are_enforced(tmp_path: Path) -> None:
    source = (REPOSITORY / "examples/local_source_adapter.py").read_text()
    ast_heavy = tmp_path / "ast-heavy.py"
    ast_heavy.write_text(source + "\n" + "1\n" * 80)
    with pytest.raises(CasePathCLIError, match="AST-node cap"):
        adapter_check(Namespace(path=str(ast_heavy)))
    literal_heavy = tmp_path / "literal-heavy.py"
    literal_heavy.write_text('"' + "x" * 1100 + '"\n' + source)
    with pytest.raises(CasePathCLIError, match="literal-byte cap"):
        adapter_check(Namespace(path=str(literal_heavy)))


@pytest.mark.parametrize("mutation", ("relative", "duplicate"))
def test_adapter_import_roster_is_exact(tmp_path: Path, mutation: str) -> None:
    source = (REPOSITORY / "examples/local_source_adapter.py").read_text()
    if mutation == "relative":
        source = source.replace("from pathlib import Path", "from .pathlib import Path")
    else:
        source = source.replace(
            "from pathlib import Path", "from pathlib import Path\nfrom pathlib import Path"
        )
    candidate = tmp_path / "candidate.py"
    candidate.write_text(source)
    with pytest.raises(CasePathCLIError, match="audited local-registry"):
        adapter_check(Namespace(path=str(candidate)))


def test_launcher_safe_path_blocks_caller_package_shadow(tmp_path: Path) -> None:
    poison = tmp_path / "casepath_api"
    poison.mkdir()
    marker = tmp_path / "shadow-imported"
    poison.joinpath("__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n"
    )
    candidate = tmp_path / "adapter.py"
    shutil.copyfile(REPOSITORY / "examples/local_source_adapter.py", candidate)
    environment = {
        "PATH": os.environ["PATH"],
        "CASEPATH_SOURCE_COMMIT": os.environ.get("CASEPATH_SOURCE_COMMIT", ""),
        "CASEPATH_UV": os.environ.get("CASEPATH_UV") or shutil.which("uv") or "",
        "CASEPATH_ENV_LOCK_HELD": os.environ.get("CASEPATH_ENV_LOCK_HELD", ""),
        "CASEPATH_ENV_READY": os.environ.get("CASEPATH_ENV_READY", ""),
    }
    completed = subprocess.run(
        [str(REPOSITORY / "bin/casepath"), "adapter-check", candidate.name],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    assert not marker.exists()


@pytest.mark.parametrize("operation", ("adapter-check", "dev"))
def test_launcher_early_python_ignores_ambient_startup_code(
    tmp_path: Path, operation: str
) -> None:
    poison = tmp_path / "poison"
    poison.mkdir()
    site_marker = tmp_path / "sitecustomize-imported"
    platform_marker = tmp_path / "platform-imported"
    poison.joinpath("sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(site_marker)!r}).write_text('bad')\n"
    )
    poison.joinpath("platform.py").write_text(
        f"from pathlib import Path\nPath({str(platform_marker)!r}).write_text('bad')\n"
    )
    uv_stub = tmp_path / "uv"
    uv_stub.write_text("#!/bin/sh\nexit 97\n")
    uv_stub.chmod(0o755)
    arguments = [str(REPOSITORY / "bin/casepath"), operation]
    if operation == "adapter-check":
        arguments.append(str(REPOSITORY / "examples/local_source_adapter.py"))
    completed = subprocess.run(
        arguments,
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(poison),
            "CASEPATH_UV": str(uv_stub),
            "CASEPATH_ENV_LOCK_HELD": os.environ.get("CASEPATH_ENV_LOCK_HELD", ""),
            "CASEPATH_ENV_READY": "0",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode != 0
    assert not site_marker.exists()
    assert not platform_marker.exists()


@pytest.mark.skipif(
    sys.platform != "darwin" or not Path("/usr/bin/lockf").is_file(),
    reason="macOS lockf release-boundary canary",
)
def test_launcher_lockf_handoffs_preserve_one_inode_and_one_owner(
    tmp_path: Path,
) -> None:
    launcher_source = (REPOSITORY / "bin/casepath").read_text()
    assert launcher_source.count(
        'exec "$trusted_lock_executable" -k -t 0'
    ) == 3
    assert "command -v lockf" not in launcher_source

    lock_path = tmp_path / "lease.lock"
    lock_path.write_bytes(b"")
    initial_identity = (lock_path.stat().st_dev, lock_path.stat().st_ino)
    sentinel = tmp_path / "active"
    log = tmp_path / "critical.log"
    release = tmp_path / "release-owner-a"
    worker = tmp_path / "worker.py"
    wrapper = tmp_path / "attempt.py"
    worker.write_text(
        """from pathlib import Path
import os
import sys
import time

lock_path = Path(sys.argv[1])
sentinel = Path(sys.argv[2])
log = Path(sys.argv[3])
label = sys.argv[4]
delay = float(sys.argv[5])
release = Path(sys.argv[6])
try:
    descriptor = os.open(sentinel, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
except FileExistsError:
    with log.open("a") as stream:
        stream.write(f"COLLISION {label}\\n")
    raise SystemExit(91)
identity = lock_path.stat()
with log.open("a") as stream:
    stream.write(f"ENTER {label} {identity.st_dev}:{identity.st_ino}\\n")
    stream.flush()
    os.fsync(stream.fileno())
if label == "A":
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not release.exists():
        time.sleep(0.01)
    if not release.exists():
        raise SystemExit(92)
else:
    time.sleep(delay)
os.close(descriptor)
sentinel.unlink()
with log.open("a") as stream:
    stream.write(f"EXIT {label}\\n")
    stream.flush()
    os.fsync(stream.fileno())
"""
    )
    wrapper.write_text(
        """from pathlib import Path
import os
import sys

Path(sys.argv[1]).write_text("ATTEMPTING\\n")
os.execv("/usr/bin/lockf", ["/usr/bin/lockf", *sys.argv[2:]])
"""
    )

    def launch(label: str, delay: float) -> subprocess.Popen[str]:
        attempt = tmp_path / f"attempt-{label}"
        return subprocess.Popen(
            [
                sys.executable,
                str(wrapper),
                str(attempt),
                "-k",
                "-t",
                "5",
                str(lock_path),
                sys.executable,
                str(worker),
                str(lock_path),
                str(sentinel),
                str(log),
                label,
                str(delay),
                str(release),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    owner = launch("A", 0.25)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if log.exists() and "ENTER A" in log.read_text():
            break
        time.sleep(0.01)
    else:
        owner.kill()
        raise AssertionError("first lock owner did not enter")
    contenders = [launch("B", 0.05), launch("C", 0.05)]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        contenders_at_kernel_boundary = []
        for contender, label in zip(contenders, ("B", "C"), strict=True):
            command = subprocess.run(
                ["/bin/ps", "-p", str(contender.pid), "-o", "comm="],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            contenders_at_kernel_boundary.append(
                (tmp_path / f"attempt-{label}").exists()
                and command == "/usr/bin/lockf"
                and contender.poll() is None
            )
        if all(contenders_at_kernel_boundary):
            break
        time.sleep(0.01)
    else:
        owner.kill()
        for contender in contenders:
            contender.kill()
        raise AssertionError("contenders did not reach the lock acquisition boundary")
    time.sleep(0.1)
    assert all(contender.poll() is None for contender in contenders)
    assert all(
        subprocess.run(
            ["/bin/ps", "-p", str(contender.pid), "-o", "comm="],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        == "/usr/bin/lockf"
        for contender in contenders
    )
    release.write_text("release\n")
    completed = [
        process.communicate(timeout=10) + (process.returncode,)
        for process in [owner, *contenders]
    ]
    assert all(returncode == 0 for _, _, returncode in completed), completed
    rows = log.read_text().splitlines()
    assert not any(row.startswith("COLLISION") for row in rows)
    assert sorted(row.split()[1] for row in rows if row.startswith("ENTER")) == [
        "A",
        "B",
        "C",
    ]
    assert len([row for row in rows if row.startswith("EXIT")]) == 3
    assert all(
        row.split()[2] == f"{initial_identity[0]}:{initial_identity[1]}"
        for row in rows
        if row.startswith("ENTER")
    )
    assert (lock_path.stat().st_dev, lock_path.stat().st_ino) == initial_identity


def test_nested_dev_reuses_the_verified_environment_without_sync() -> None:
    source = (REPOSITORY / "bin/casepath").read_text()
    expected = """if [[ "${CASEPATH_ENV_READY:-}" != "1" ]]; then
  "$uv_command" pip sync \\
    --python "$python_command" \\
    "$repository_root/casepath-api/requirements.lock" >/dev/null
  export CASEPATH_ENV_READY=1
fi"""
    assert expected in source


def test_launcher_accepts_only_a_closed_manifest_roster_without_git() -> None:
    source = (REPOSITORY / "bin/casepath").read_text()
    verifier = source[
        source.index("verify_sealed_source_tree() {") : source.index(
            "\n}\n\nmaterialize_sealed_source_capsule()", source.index(
                "verify_sealed_source_tree() {"
            )
        )
    ]
    assert 'if git_authority.is_dir():' in verifier
    assert 'for root_name in source_roots:' in verifier
    assert 'for path in root.rglob("*"):' in verifier
    assert 'candidates.append(path.relative_to(repository).as_posix())' in verifier
    assert 'candidates.extend(extra_files)' in verifier
    assert 'if paths != sorted(set(actual_paths)):' in verifier
    assert 'manifest["source_commit"]' not in verifier
    assert 'casepath.source-manifest/2.1.0' in verifier


def test_launcher_resolves_runtime_commit_from_git_authority() -> None:
    source = (REPOSITORY / "bin/casepath").read_text()
    start = source.index("resolve_source_identity() {")
    end = source.index("\n}\n", start)
    resolver = source[start:end]
    assert 'rev-parse --verify HEAD' in resolver
    assert 'CASEPATH_SOURCE_COMMIT="$supplied_commit"' in resolver
    assert "source archive requires CASEPATH_SOURCE_COMMIT" in resolver
    assert "source-manifest.json" not in resolver


def test_prepare_rebuilds_ignored_outputs_after_source_only_preflight() -> None:
    source = (REPOSITORY / "bin/casepath").read_text()
    operation = source.index('if [[ "$operation" != "dev" ]]')
    source_only = source.index("verify_sealed_source_tree source-only", operation)
    sync = source.index('"$uv_command" pip sync', source_only)
    prepare = source.index("prepare_generated_outputs", sync)
    complete = source.index('preflight_source_manifest_sha256="$(verify_sealed_source_tree)"', prepare)
    assert source_only < sync < prepare < complete


def test_data_root_bootstrap_executes_the_hash_bound_captured_controller() -> None:
    source = (REPOSITORY / "bin/casepath").read_text()
    start = source.index("bootstrap_data_root() {")
    end = source.index("\n}\n", start)
    controller = source[start:end]
    assert "module_raw = read_regular_nofollow(module_path)" in controller
    assert '"sha256": hashlib.sha256(module_raw).hexdigest()' in controller
    assert 'exec(compile(module_raw, str(module_path), "exec")' in controller
    assert controller.count("sys.path.insert") == 1
    assert 'str(repository / "casepath-api")' in controller
    assert "runpy.run_module('casepath_api.validate_journal'" in controller
    assert "staged_database_validator=validate_staged_database" in controller
    assert "from casepath_api.local_data_root import" not in controller


def _history_verifier_module() -> object:
    path = REPOSITORY / "casepath/tools/validate_local_runtime_history.py"
    spec = importlib.util.spec_from_file_location("casepath_history_verifier", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_validates_capsule_bound_history_before_pointer_or_child() -> None:
    source = (REPOSITORY / "bin/casepath").read_text()
    dev = source.index("# Hold one kernel-backed launch lease")
    capsule = source.index("materialize_sealed_source_capsule", dev)
    verifier = source.index(
        '"$execution_root/casepath/tools/validate_local_runtime_history.py"', capsule
    )
    child_guard = source.index("assert_origin_idle", verifier)
    bootstrap = source.index('bootstrap_data_root "$execution_root"', verifier)
    child = source.index("uvicorn", bootstrap)
    assert capsule < verifier < child_guard < bootstrap < child


def test_capsule_publisher_sets_the_exact_modes_its_validator_requires() -> None:
    source = (REPOSITORY / "bin/casepath").read_text()
    start = source.index("materialize_sealed_source_capsule() {")
    end = source.index("\n}\n", start)
    materializer = source[start:end]
    assert "os.chmod(directory, 0o500)" in materializer
    assert "os.chmod(staging, 0o500)" in materializer
    assert (
        "0o555 if file_path.stat().st_mode & stat.S_IXUSR else 0o444"
        in materializer
    )
    assert materializer.index("os.chmod(directory, 0o500)") < materializer.rindex(
        "validate_capsule()"
    )
    file_chmod = materializer.index("0o555 if file_path.stat().st_mode")
    file_fsync = materializer.index("os.fsync(descriptor)", file_chmod)
    directory_chmod = materializer.index("os.chmod(directory, 0o500)")
    root_chmod = materializer.index("os.chmod(staging, 0o500)")
    root_fsync = materializer.index("os.fsync(descriptor)", root_chmod)
    rename = materializer.index("os.rename(staging, target)")
    assert file_chmod < file_fsync < directory_chmod < root_chmod < root_fsync < rename


def test_launcher_makes_every_mutable_runtime_root_private_before_locking() -> None:
    source = (REPOSITORY / "bin/casepath").read_text()
    start = source.index("ensure_private_runtime_root() {")
    end = source.index("\n}\n", start)
    guard = source[start:end]
    assert 'for candidate in "$mutable_parent" "$runtime_root"' in guard
    assert 'if [[ -L "$candidate" ]]' in guard
    assert '(umask 077; /bin/mkdir -p "$runtime_root")' in guard
    assert '/bin/chmod 0700 "$mutable_parent" "$runtime_root"' in guard
    assert 'if [[ ! -d "$candidate" || -L "$candidate" ]]' in guard

    operation_guard = source.index('if [[ "$operation" != "dev"')
    uv_lookup = source.index('if [[ -z "$uv_command" ]]')
    environment_lock = source.index('environment_lock_path="$runtime_root/environment.lock"')
    launch_lock = source.index("# Hold one kernel-backed launch lease")
    first_guard = source.index("ensure_private_runtime_root", operation_guard)
    second_guard = source.index("ensure_private_runtime_root", environment_lock)
    assert operation_guard < first_guard < uv_lookup < environment_lock
    assert environment_lock < second_guard < launch_lock


@pytest.mark.parametrize(
    "operation, extra_arguments",
    (
        ("adapter-check", ("fixture.py",)),
        ("dev", ()),
        ("prepare", ()),
        ("seed", ("--corpus", BUNDLED_CORPUS_ID)),
        ("test", ()),
        ("replay", ("claim-1",)),
    ),
)
@pytest.mark.parametrize("preexisting", (False, True))
def test_launcher_runtime_root_is_private_before_dependency_or_source_access(
    tmp_path: Path,
    operation: str,
    extra_arguments: tuple[str, ...],
    preexisting: bool,
) -> None:
    candidate = tmp_path / f"candidate-{operation}-{preexisting}"
    launcher = candidate / "bin/casepath"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes((REPOSITORY / "bin/casepath").read_bytes())
    launcher.chmod(0o755)
    runtime = candidate / ".runtime/casepath-dev-v2"
    if preexisting:
        runtime.mkdir(parents=True)
        runtime.chmod(0o755)
    uv_stub = tmp_path / f"uv-{operation}-{preexisting}"
    uv_stub.write_text("#!/bin/sh\nexit 97\n")
    uv_stub.chmod(0o755)

    completed = subprocess.run(
        [str(launcher), operation, *extra_arguments],
        cwd=candidate,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "CASEPATH_UV": str(uv_stub),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 97
    assert runtime.is_dir() and not runtime.is_symlink()
    assert stat.S_IMODE(runtime.stat().st_mode) == 0o700
    for name in ("home", "tmp", "pycache", "boots", "boot-staging"):
        directory = runtime / name
        assert directory.is_dir() and not directory.is_symlink()
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_launcher_rejects_symlinked_runtime_without_changing_target_mode(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate-symlink"
    launcher = candidate / "bin/casepath"
    launcher.parent.mkdir(parents=True)
    launcher.write_bytes((REPOSITORY / "bin/casepath").read_bytes())
    launcher.chmod(0o755)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o755)
    mutable = candidate / ".runtime"
    mutable.mkdir()
    mutable.joinpath("casepath-dev-v2").symlink_to(outside, target_is_directory=True)
    uv_stub = tmp_path / "uv-symlink"
    uv_stub.write_text("#!/bin/sh\nexit 97\n")
    uv_stub.chmod(0o755)

    completed = subprocess.run(
        [str(launcher), "test"],
        cwd=candidate,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "CASEPATH_UV": str(uv_stub),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 2
    assert "mutable runtime boundary is a symlink" in completed.stderr
    assert stat.S_IMODE(outside.stat().st_mode) == 0o755


def test_history_verifier_canonicalizes_component_order_before_roster_compare() -> None:
    source = (
        REPOSITORY / "casepath/tools/validate_local_runtime_history.py"
    ).read_text()
    walk = source.index('for candidate in sorted(capsule_root.rglob("*"))')
    compare = source.index('if actual_files != sorted(expected)', walk)
    block = source[walk:compare]
    assert "actual_files.sort()" in block
    assert "actual_directories.sort()" in block


def test_history_verifier_empty_lineage_is_exact_and_current_without_history_fails(
    tmp_path: Path,
) -> None:
    verifier = _history_verifier_module()
    runtime = tmp_path / "runtime"
    data = tmp_path / "data"
    runtime.joinpath("boots").mkdir(parents=True)
    runtime.joinpath("boot-staging").mkdir()
    data.mkdir()
    verifier.reconcile(runtime, data, REPOSITORY)
    runtime.joinpath("runtime-boot-receipt.json").write_text("{}")
    with pytest.raises(verifier.HistoryError, match="without immutable history"):
        verifier.reconcile(runtime, data, REPOSITORY)


def test_history_verifier_reconciles_only_canonical_staging_links(
    tmp_path: Path,
) -> None:
    verifier = _history_verifier_module()
    runtime = tmp_path / "runtime"
    boots = runtime / "boots"
    staging = runtime / "boot-staging"
    boots.mkdir(parents=True)
    staging.mkdir()
    boot_id = "boot-20260831T010203Z-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    staged = staging / f".{boot_id}.123.11111111-2222-3333-4444-555555555555.tmp"
    staged.write_text("receipt\n")
    staged.chmod(0o444)
    history = boots / f"{boot_id}.json"
    os.link(staged, history)
    verifier.reconcile_boot_staging(runtime, allow_reconcile=True)
    assert not staged.exists()
    assert history.stat().st_nlink == 1
    assert stat.S_IMODE(history.stat().st_mode) == 0o444

    hostile = staging / f".{boot_id}.124.66666666-7777-8888-9999-aaaaaaaaaaaa.tmp"
    hostile.write_text("hostile\n")
    outside = tmp_path / "outside"
    os.link(hostile, outside)
    with pytest.raises(verifier.HistoryError, match="hard link"):
        verifier.reconcile_boot_staging(runtime, allow_reconcile=True)


def test_history_verifier_reconciles_only_canonical_pointer_temps(
    tmp_path: Path,
) -> None:
    verifier = _history_verifier_module()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    publisher = runtime / (
        ".runtime-boot-receipt.123.11111111-2222-3333-4444-555555555555.tmp"
    )
    reconciler = runtime / (
        ".runtime-boot-receipt.reconcile-124-66666666-7777-8888-9999-"
        "aaaaaaaaaaaa.tmp"
    )
    publisher.write_text("partial")
    reconciler.write_text("partial")
    verifier.reconcile_pointer_temps(runtime, allow_reconcile=True)
    assert not publisher.exists()
    assert not reconciler.exists()

    invalid = runtime / ".runtime-boot-receipt.hostile.tmp"
    invalid.write_text("hostile")
    with pytest.raises(verifier.HistoryError, match="boot-pointer temporary"):
        verifier.reconcile_pointer_temps(runtime, allow_reconcile=True)


@pytest.mark.parametrize(
    ("contract", "event_type"),
    [("casepath.claim-loop-event/1.0.0", event_type) for event_type in
     ("EVIDENCE_PROPOSAL_REJECTED", "NATIVE_PROPOSAL_REVISION_RECORDED")]
    + [(WORKSPACE_EVENT_CONTRACT, event_type) for event_type in sorted(WORKSPACE_EVENT_TYPES)],
)
def test_history_verifier_accepts_current_journal_event_types(
    tmp_path: Path, contract: str, event_type: str,
) -> None:
    verifier = _history_verifier_module()
    command = {"value": "recorded"}
    material = {
        "contract": contract,
        "session_id": "session-1",
        "loop_id": "loop-1",
        "sequence": 1,
        "previous_event_sha256": None,
        "event_type": event_type,
        "idempotency_key": "record-1",
        "command_sha256": verifier.digest(verifier.canonical(command)),
        "command": command,
        "created_at": "2026-08-31T00:00:00+00:00",
    }
    event = {
        **material,
        "event_sha256": verifier.digest(verifier.canonical(material)),
        "resulting_state_sha256": "a" * 64,
    }
    with sqlite3.connect(tmp_path / "events.db") as connection:
        connection.execute(
            """CREATE TABLE claim_loop_events (
            session_id TEXT, loop_id TEXT, sequence INTEGER,
            idempotency_key TEXT, command_sha256 TEXT, event_sha256 TEXT,
            event_json TEXT, created_at TEXT)"""
        )
        connection.execute(
            "INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)",
            (
                event["session_id"], event["loop_id"], event["sequence"],
                event["idempotency_key"], event["command_sha256"],
                event["event_sha256"], verifier.canonical(event).decode(),
                event["created_at"],
            ),
        )
        assert verifier.validate_event_journal(connection)[0]["event_sha256"] == event["event_sha256"]


def test_history_verifier_rejects_event_json_corruption_and_broken_chain(
    tmp_path: Path,
) -> None:
    verifier = _history_verifier_module()
    database = tmp_path / "events.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE claim_loop_events (
            session_id TEXT, loop_id TEXT, sequence INTEGER,
            idempotency_key TEXT, command_sha256 TEXT, event_sha256 TEXT,
            event_json TEXT, created_at TEXT)"""
        )
        command = {"value": "one"}
        event_material = {
            "contract": "casepath.claim-loop-event/1.0.0",
            "session_id": "session-1",
            "loop_id": "loop-1",
            "sequence": 1,
            "previous_event_sha256": None,
            "event_type": "LOOP_CREATED",
            "idempotency_key": "create-1",
            "command_sha256": verifier.digest(verifier.canonical(command)),
            "command": command,
            "created_at": "2026-08-31T00:00:00+00:00",
        }
        event = {
            **event_material,
            "event_sha256": verifier.digest(verifier.canonical(event_material)),
            "resulting_state_sha256": "a" * 64,
        }
        connection.execute(
            "INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)",
            (
                event["session_id"],
                event["loop_id"],
                event["sequence"],
                event["idempotency_key"],
                event["command_sha256"],
                event["event_sha256"],
                verifier.canonical(event).decode(),
                event["created_at"],
            ),
        )
        assert verifier.validate_event_journal(connection)[0]["event_sha256"] == event["event_sha256"]
        connection.execute(
            "UPDATE claim_loop_events SET event_json=?",
            (
                verifier.canonical(
                    {**event, "command": {"value": "tampered"}}
                ).decode(),
            ),
        )
        with pytest.raises(verifier.HistoryError, match="event chain is invalid"):
            verifier.validate_event_journal(connection)
        connection.execute(
            "UPDATE claim_loop_events SET event_json=?",
            (verifier.canonical(event).decode(),),
        )
        second_material = {
            **event_material,
            "sequence": 2,
            "idempotency_key": "create-2",
            "previous_event_sha256": "f" * 64,
        }
        second = {
            **second_material,
            "event_sha256": verifier.digest(verifier.canonical(second_material)),
            "resulting_state_sha256": "b" * 64,
        }
        connection.execute(
            "INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)",
            (
                second["session_id"], second["loop_id"], second["sequence"],
                second["idempotency_key"], second["command_sha256"],
                second["event_sha256"], verifier.canonical(second).decode(),
                second["created_at"],
            ),
        )
        with pytest.raises(verifier.HistoryError, match="event chain is invalid"):
            verifier.validate_event_journal(connection)


def test_history_verifier_rejects_durable_roster_rollback() -> None:
    verifier = _history_verifier_module()
    event = {
        "session_id": "session-1",
        "loop_id": "loop-1",
        "sequence": 1,
        "event_sha256": "1" * 64,
    }
    artifact = {"path": "a.json", "sha256": "2" * 64, "size_bytes": 1}
    prior = {
        "contract": "casepath.local-runtime-boot/2.1.0",
        "attestation": {
            "durable_event_roster": [event],
            "durable_registry_inventory": [artifact],
        },
    }
    current = {
        "contract": "casepath.local-runtime-boot/2.1.0",
        "attestation": {
            "durable_event_roster": [],
            "durable_registry_inventory": [],
        },
    }
    with pytest.raises(verifier.HistoryError, match="event history rolled back"):
        verifier.require_monotonic_durable_chain([prior, current])


def test_standalone_seed_rejects_drift_before_sync_or_durable_open(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    manifest = json.loads(
        (REPOSITORY / "casepath/source-manifest.json").read_text()
    )
    for row in manifest["files"]:
        source = REPOSITORY / row["path"]
        destination = candidate / row["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    candidate.joinpath("casepath/source-manifest.json").write_bytes(
        (REPOSITORY / "casepath/source-manifest.json").read_bytes()
    )
    drifted = candidate / "README.md"
    original = drifted.read_bytes()
    drifted.unlink()
    drifted.write_bytes(original + b"\nsource drift canary\n")

    runtime = candidate / ".runtime/casepath-dev-v2"
    runtime.mkdir(parents=True)
    runtime.joinpath("venv").symlink_to(
        REPOSITORY / ".runtime/casepath-dev-v2/venv",
        target_is_directory=True,
    )
    uv_called = tmp_path / "uv-called"
    uv_stub = tmp_path / "uv"
    uv_stub.write_text(f"#!/bin/sh\ntouch {str(uv_called)!r}\nexit 97\n")
    uv_stub.chmod(0o755)

    completed = subprocess.run(
        [str(candidate / "bin/casepath"), "seed", "--corpus", BUNDLED_CORPUS_ID],
        cwd=candidate,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "CASEPATH_UV": str(uv_stub),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 1
    assert "sealed source file identity differs from disk" in completed.stderr
    assert not uv_called.exists()
    assert not candidate.joinpath(".runtime/casepath-data-v1").exists()


@pytest.mark.parametrize(
    "mutation",
    ("release_id", "contract", "unexpected_source_commit"),
)
def test_standalone_seed_rejects_self_excluded_identity_drift_before_open(
    tmp_path: Path, mutation: str
) -> None:
    candidate = tmp_path / "candidate"
    manifest = json.loads(
        (REPOSITORY / "casepath/source-manifest.json").read_text()
    )
    for row in manifest["files"]:
        source = REPOSITORY / row["path"]
        destination = candidate / row["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    subprocess.run(["/usr/bin/git", "init", "-q", str(candidate)], check=True)
    subprocess.run(["/usr/bin/git", "-C", str(candidate), "add", "--all"], check=True)
    subprocess.run(
        ["/usr/bin/git", "-C", str(candidate), "commit", "-q", "--allow-empty", "-m", "fixture"],
        check=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "CasePath Test",
            "GIT_AUTHOR_EMAIL": "casepath-test@example.invalid",
            "GIT_COMMITTER_NAME": "CasePath Test",
            "GIT_COMMITTER_EMAIL": "casepath-test@example.invalid",
        },
    )
    if mutation == "release_id":
        manifest["release_id"] = "not-the-bound-release"
    elif mutation == "contract":
        manifest["contract"] = "casepath.source-manifest/unsupported"
    else:
        manifest["source_commit"] = {
            "source": "CASEPATH_SOURCE_COMMIT",
            "value": "f" * 40,
        }
    candidate.joinpath("casepath/source-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    runtime = candidate / ".runtime/casepath-dev-v2"
    runtime.mkdir(parents=True)
    runtime.joinpath("venv").symlink_to(
        REPOSITORY / ".runtime/casepath-dev-v2/venv",
        target_is_directory=True,
    )
    uv_called = tmp_path / "uv-called"
    uv_stub = tmp_path / "uv"
    uv_stub.write_text(f"#!/bin/sh\ntouch {str(uv_called)!r}\nexit 97\n")
    uv_stub.chmod(0o755)

    completed = subprocess.run(
        [str(candidate / "bin/casepath"), "seed", "--corpus", BUNDLED_CORPUS_ID],
        cwd=candidate,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "CASEPATH_UV": str(uv_stub),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 1
    assert "sealed source manifest is invalid" in completed.stderr
    assert not uv_called.exists()
    assert not candidate.joinpath(".runtime/casepath-data-v1").exists()
