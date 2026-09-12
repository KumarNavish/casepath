from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import threading

import pytest

import casepath_api.local_data_root as local_data_root_module
from casepath_api.local_data_root import (
    LocalDataRootError,
    bootstrap_data_root,
)


def _legacy_root(tmp_path: Path) -> Path:
    root = tmp_path / "legacy"
    registry = root / "artifact-registry/artifacts"
    registry.mkdir(parents=True)
    (registry / "evidence.txt").write_text("preserved evidence")
    with sqlite3.connect(root / "casepath.db") as connection:
        connection.execute(
            """CREATE TABLE claim_loop_events (
            session_id TEXT NOT NULL, loop_id TEXT NOT NULL,
            sequence INTEGER NOT NULL, idempotency_key TEXT NOT NULL,
            command_sha256 TEXT NOT NULL, event_sha256 TEXT NOT NULL,
            event_json TEXT NOT NULL, created_at TEXT NOT NULL)"""
        )
        connection.execute(
            "INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)",
            (
                "session",
                "loop",
                1,
                "command-key",
                "a" * 64,
                "b" * 64,
                '{"event":"preserved"}',
                "2026-08-31T00:00:00+00:00",
            ),
        )
    return root


def test_legacy_database_and_registry_are_copied_without_source_mutation(
    tmp_path: Path,
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    source_db_before = hashlib.sha256((legacy / "casepath.db").read_bytes()).hexdigest()
    source_artifact_before = (legacy / "artifact-registry/artifacts/evidence.txt").read_bytes()
    receipt = bootstrap_data_root(legacy, destination)
    assert receipt["origin"]["claim_loop_event_count"] == 1
    assert receipt["origin"]["kind"] == "hash_bound_sqlite_backup_from_casepath_dev_v1"
    assert hashlib.sha256((legacy / "casepath.db").read_bytes()).hexdigest() == source_db_before
    assert (legacy / "artifact-registry/artifacts/evidence.txt").read_bytes() == source_artifact_before
    assert (destination / "artifact-registry/artifacts/evidence.txt").read_bytes() == source_artifact_before
    with sqlite3.connect(destination / "casepath.db") as connection:
        assert connection.execute("SELECT event_json FROM claim_loop_events").fetchone()[0] == '{"event":"preserved"}'


def test_existing_root_is_validated_and_never_recopied(tmp_path: Path) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    first = bootstrap_data_root(legacy, destination)
    with sqlite3.connect(destination / "casepath.db") as connection:
        connection.execute("CREATE TABLE durable_tail (value TEXT)")
        connection.execute("INSERT INTO durable_tail VALUES ('new')")
    second = bootstrap_data_root(legacy, destination)
    assert second == first
    with sqlite3.connect(destination / "casepath.db") as connection:
        assert connection.execute("SELECT value FROM durable_tail").fetchone()[0] == "new"


def test_empty_predecessor_creates_a_provenance_bound_empty_root(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "data"
    receipt = bootstrap_data_root(tmp_path / "absent", destination)
    assert receipt["origin"]["kind"] == "new_empty_durable_data_root"
    assert receipt["origin"]["claim_loop_event_count"] == 0
    assert (destination / "casepath.db").is_file()
    assert (destination / "artifact-registry").is_dir()


def test_staged_semantic_replay_runs_under_source_lease_before_publication(
    tmp_path: Path,
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    observed: list[Path] = []

    def validate_staging(database: Path) -> None:
        assert database.is_file()
        assert not destination.exists()
        observed.append(database)
        contender = sqlite3.connect(
            legacy / "casepath.db", timeout=0, isolation_level=None
        )
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                contender.execute("BEGIN IMMEDIATE")
        finally:
            contender.close()

    bootstrap_data_root(
        legacy,
        destination,
        staged_database_validator=validate_staging,
    )
    assert len(observed) == 1


def test_staged_semantic_failure_never_publishes_successor(
    tmp_path: Path,
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"

    def reject_staging(_: Path) -> None:
        raise RuntimeError("reducer-invalid journal")

    with pytest.raises(
        LocalDataRootError, match="failed semantic replay"
    ):
        bootstrap_data_root(
            legacy,
            destination,
            staged_database_validator=reject_staging,
        )
    assert not destination.exists()
    assert not list(tmp_path.glob(".data.*.tmp"))


def test_killed_mode_lease_publisher_temp_is_removed_exactly(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "data"
    temporary = tmp_path / (
        "..data.legacy-registry-mode-lease.json.123."
        "12345678-1234-1234-1234-123456789abc.tmp"
    )
    temporary.write_bytes(b"unpublished")
    bootstrap_data_root(tmp_path / "absent", destination)
    assert not temporary.exists()


@pytest.mark.parametrize(
    "fault_point", ("after_staging", "after_database", "before_publish")
)
def test_partial_bootstrap_is_invisible_and_retryable(
    tmp_path: Path, fault_point: str
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    with pytest.raises(LocalDataRootError, match="injected failure"):
        bootstrap_data_root(legacy, destination, fault_point=fault_point)
    assert not destination.exists()
    assert not list(tmp_path.glob(".data.*.tmp"))
    assert bootstrap_data_root(legacy, destination)["origin"]["claim_loop_event_count"] == 1


def test_concurrent_first_publication_returns_one_exact_receipt(
    tmp_path: Path,
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    barrier = threading.Barrier(2)

    def publish(_: int) -> dict[str, object]:
        barrier.wait()
        return bootstrap_data_root(legacy, destination)

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(publish, (1, 2)))
    assert receipts[0] == receipts[1]
    assert json.loads((destination / "DATA_ROOT_PROVENANCE.json").read_text()) == receipts[0]


def test_predecessor_writer_is_excluded_until_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    original_inventory = local_data_root_module._registry_inventory
    writer_result: list[BaseException | str] = []
    exercised = False

    def attempt_late_append() -> None:
        try:
            with sqlite3.connect(legacy / "casepath.db", timeout=0.05) as connection:
                connection.execute(
                    "INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)",
                    (
                        "session",
                        "loop",
                        2,
                        "late-key",
                        "c" * 64,
                        "d" * 64,
                        '{"event":"late"}',
                        "2026-08-31T00:00:01+00:00",
                    ),
                )
            writer_result.append("committed")
        except BaseException as exc:  # noqa: BLE001 - exact competing writer result
            writer_result.append(exc)

    def guarded_inventory(root: Path) -> list[dict[str, object]]:
        nonlocal exercised
        if root == legacy / "artifact-registry" and not exercised:
            exercised = True
            writer = threading.Thread(target=attempt_late_append)
            writer.start()
            writer.join(timeout=2)
            assert not writer.is_alive()
        return original_inventory(root)

    monkeypatch.setattr(local_data_root_module, "_registry_inventory", guarded_inventory)
    receipt = bootstrap_data_root(legacy, destination)
    assert exercised is True
    assert len(writer_result) == 1
    assert isinstance(writer_result[0], sqlite3.OperationalError)
    assert "locked" in str(writer_result[0]).lower()
    assert receipt["origin"]["claim_loop_event_count"] == 1


def test_registry_is_frozen_without_open_handles_through_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    artifact = legacy / "artifact-registry/artifacts/evidence.txt"
    original_modes = {
        path: path.stat().st_mode & 0o777
        for path in [legacy / "artifact-registry", artifact.parent, artifact]
    }
    original_publish = local_data_root_module._publish_directory_noreplace
    observed = False

    def guarded_publish(source: Path, target: Path) -> None:
        nonlocal observed
        observed = True
        assert all(path.stat().st_mode & 0o222 == 0 for path in original_modes)
        attempted = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import pathlib,sys;pathlib.Path(sys.argv[1]).write_text('late')",
                str(artifact),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert attempted.returncode != 0
        assert artifact.read_text() == "preserved evidence"
        original_publish(source, target)

    monkeypatch.setattr(
        local_data_root_module, "_publish_directory_noreplace", guarded_publish
    )
    receipt = bootstrap_data_root(legacy, destination)
    assert observed is True
    assert {
        path: path.stat().st_mode & 0o777 for path in original_modes
    } == original_modes
    assert receipt["origin"]["legacy_registry_cutover"] == {
        "applied": True,
        "mode_lease_receipt": receipt["origin"][
            "legacy_registry_cutover"
        ]["mode_lease_receipt"],
        "mode_lease_receipt_sha256": receipt["origin"][
            "legacy_registry_cutover"
        ]["mode_lease_receipt_sha256"],
        "mode_roster_sha256": receipt["origin"]["legacy_registry_cutover"][
            "mode_roster_sha256"
        ],
        "open_handle_count_after_freeze": 0,
        "policy": (
            "write_bits_removed_and_zero_open_handles_through_atomic_publication"
        ),
    }


def test_registry_cutover_rejects_a_preopened_artifact_handle(tmp_path: Path) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    artifact = legacy / "artifact-registry/artifacts/evidence.txt"
    mode_before = artifact.stat().st_mode & 0o777
    with artifact.open("rb"):
        with pytest.raises(LocalDataRootError, match="live open handle"):
            bootstrap_data_root(legacy, destination)
    assert artifact.stat().st_mode & 0o777 == mode_before
    assert not destination.exists()


def test_registry_cutover_rejects_an_external_hardlink_alias(tmp_path: Path) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    artifact = legacy / "artifact-registry/artifacts/evidence.txt"
    os.link(artifact, tmp_path / "external-artifact-alias")
    with pytest.raises(LocalDataRootError, match="exactly one link"):
        bootstrap_data_root(legacy, destination)
    assert not destination.exists()


def test_database_cutover_rejects_an_external_hardlink_alias(tmp_path: Path) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    os.link(legacy / "casepath.db", tmp_path / "external-database-alias")
    with pytest.raises(LocalDataRootError, match="single-link"):
        bootstrap_data_root(legacy, destination)
    assert not destination.exists()


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS ACL canary")
@pytest.mark.parametrize("target_kind", ("file", "directory"))
def test_registry_cutover_rejects_extended_acl_authority(
    tmp_path: Path, target_kind: str
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    target = (
        legacy / "artifact-registry/artifacts/evidence.txt"
        if target_kind == "file"
        else legacy / "artifact-registry/artifacts"
    )
    user = subprocess.run(
        ["/usr/bin/id", "-un"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["/bin/chmod", "+a", f"user:{user} allow write", str(target)],
        check=True,
        capture_output=True,
        text=True,
    )
    with pytest.raises(LocalDataRootError, match="extended ACL"):
        bootstrap_data_root(legacy, destination)
    assert not destination.exists()


def test_registry_cutover_rejects_a_closed_descriptor_live_mapping(
    tmp_path: Path,
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    artifact = legacy / "artifact-registry/artifacts/evidence.txt"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import mmap,pathlib,sys;"
                "path=pathlib.Path(sys.argv[1]);"
                "stream=path.open('r+b');"
                "mapping=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_WRITE);"
                "stream.close();print('READY',flush=True);"
                "sys.stdin.readline();mapping[0:1]=b'P';mapping.flush();mapping.close()"
            ),
            str(artifact),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "READY"
        with pytest.raises(LocalDataRootError, match="live open handle"):
            bootstrap_data_root(legacy, destination)
        assert process.stdin is not None
        process.stdin.write("write\n")
        process.stdin.flush()
        assert process.wait(timeout=10) == 0
        assert artifact.read_bytes().startswith(b"P")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
    assert not destination.exists()


@pytest.mark.parametrize(
    ("fault_point", "return_code", "destination_was_published"),
    (
        ("hard_exit_after_registry_freeze", 91, False),
        ("hard_exit_after_publish_before_registry_restore", 92, True),
    ),
)
def test_registry_mode_lease_recovers_after_process_death(
    tmp_path: Path,
    fault_point: str,
    return_code: int,
    destination_was_published: bool,
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    registry_paths = [
        legacy / "artifact-registry",
        legacy / "artifact-registry/artifacts",
        legacy / "artifact-registry/artifacts/evidence.txt",
    ]
    original_modes = {
        path: stat.S_IMODE(path.stat().st_mode) for path in registry_paths
    }
    repository = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from casepath_api.local_data_root import bootstrap_data_root;"
                "import sys;bootstrap_data_root(sys.argv[1],sys.argv[2],"
                "fault_point=sys.argv[3])"
            ),
            str(legacy),
            str(destination),
            fault_point,
        ],
        cwd=repository,
        env={
            **os.environ,
            "PYTHONPATH": str(repository / "casepath-api"),
        },
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == return_code
    lease = tmp_path / ".data.legacy-registry-mode-lease.json"
    assert lease.is_file()
    assert all(path.stat().st_mode & 0o222 == 0 for path in registry_paths)
    assert destination.exists() is destination_was_published

    receipt = bootstrap_data_root(legacy, destination)
    assert receipt["origin"]["legacy_registry_cutover"]["applied"] is True
    assert not lease.exists()
    assert not list(tmp_path.glob(".data.*.tmp"))
    assert {
        path: stat.S_IMODE(path.stat().st_mode) for path in registry_paths
    } == original_modes


@pytest.mark.parametrize("damage", (None, "missing", "tampered"))
def test_candidate_verifier_checks_embedded_registry_mode_lease(
    tmp_path: Path, damage: str | None
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    receipt = bootstrap_data_root(legacy, destination)
    origin = deepcopy(receipt["origin"])
    if damage == "missing":
        del origin["legacy_registry_cutover"]["mode_lease_receipt"]
    elif damage == "tampered":
        origin["legacy_registry_cutover"]["mode_lease_receipt"][
            "mode_roster"
        ][0]["mode"] ^= 0o001
    repository = Path(__file__).resolve().parents[2]
    module_uri = (
        repository / "casepath-qa/candidate-source-identity.mjs"
    ).as_uri()
    completed = subprocess.run(
        [
            shutil.which("node") or "node",
            "--input-type=module",
            "-e",
            (
                "import {validateRegistryCutoverAuthority as validate} from "
                f"{module_uri!r};"
                "let raw='';for await(const chunk of process.stdin)raw+=chunk;"
                "const value=JSON.parse(raw);"
                "validate(value.origin,value.data_root);process.stdout.write('PASS')"
            ),
        ],
        input=json.dumps({"origin": origin, "data_root": str(destination)}),
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if damage is None:
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == "PASS"
    else:
        assert completed.returncode != 0
        assert "registry" in completed.stderr


def test_candidate_verifier_uses_launcher_casefold_distribution_order() -> None:
    repository = Path(__file__).resolve().parents[2]
    module_uri = (
        repository / "casepath-qa/candidate-source-identity.mjs"
    ).as_uri()
    completed = subprocess.run(
        [
            shutil.which("node") or "node",
            "--input-type=module",
            "-e",
            (
                "import {canonicalizeInstalledDistributions as canonicalize} "
                f"from {module_uri!r};"
                "const values=['Pygments==2.20.0','pydantic_core==2.33.2',"
                "'pydantic==2.11.7'];"
                "process.stdout.write(JSON.stringify(canonicalize(values)))"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == [
        "pydantic==2.11.7",
        "pydantic_core==2.33.2",
        "Pygments==2.20.0",
    ]


@pytest.mark.parametrize(
    ("live_sha256", "allow_advance", "accepted", "changed"),
    (
        ("a" * 64, False, True, False),
        ("b" * 64, False, False, None),
        ("b" * 64, True, True, True),
        ("not-a-sha256", True, False, None),
    ),
)
def test_candidate_verifier_workspace_roster_policy_is_strict_by_default(
    live_sha256: str,
    allow_advance: bool,
    accepted: bool,
    changed: bool | None,
) -> None:
    repository = Path(__file__).resolve().parents[2]
    module_uri = (
        repository / "casepath-qa/candidate-source-identity.mjs"
    ).as_uri()
    completed = subprocess.run(
        [
            shutil.which("node") or "node",
            "--input-type=module",
            "-e",
            (
                "import {requireWorkspaceRosterPolicy as requirePolicy} from "
                f"{module_uri!r};"
                "const result=requirePolicy({"
                "attestedStateRosterSha256:'a'.repeat(64),"
                "liveStateRosterSha256:process.argv[1],"
                "allowValidatedWorkspaceJournalAdvance:process.argv[2]==='true'"
                "});process.stdout.write(JSON.stringify(result))"
            ),
            live_sha256,
            str(allow_advance).lower(),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if accepted:
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout) == {"changed": changed}
    else:
        assert completed.returncode != 0
        assert "workspace roster" in completed.stderr


@pytest.mark.parametrize(
    ("contract", "accepted"),
    (
        ("casepath.local-durable-data-provenance/1.2.0", True),
        ("casepath.local-durable-data-provenance/1.3.0", True),
        ("casepath.local-durable-data-provenance/1.1.0", False),
        ("casepath.local-durable-data-provenance/1.4.0", False),
        ("casepath.local-durable-data-provenance/2.0.0", False),
    ),
)
def test_candidate_verifier_accepts_only_supported_data_provenance_contracts(
    contract: str, accepted: bool
) -> None:
    repository = Path(__file__).resolve().parents[2]
    module_uri = (
        repository / "casepath-qa/candidate-source-identity.mjs"
    ).as_uri()
    completed = subprocess.run(
        [
            shutil.which("node") or "node",
            "--input-type=module",
            "-e",
            (
                "import {validateDataRootProvenanceContract as validate} from "
                f"{module_uri!r};"
                "validate(process.argv[1]);process.stdout.write('PASS')"
            ),
            contract,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if accepted:
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == "PASS"
    else:
        assert completed.returncode != 0
        assert "unsupported" in completed.stderr


def test_precreated_empty_destination_is_never_replaced(tmp_path: Path) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    destination.mkdir()
    with pytest.raises(LocalDataRootError, match="lacks provenance"):
        bootstrap_data_root(legacy, destination)
    assert list(destination.iterdir()) == []


@pytest.mark.parametrize("kind", ("symlink", "directory", "registry_only"))
def test_damaged_predecessor_never_becomes_an_empty_product(
    tmp_path: Path, kind: str
) -> None:
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    if kind == "symlink":
        target = tmp_path / "source.db"
        target.write_bytes(b"not sqlite")
        (legacy / "casepath.db").symlink_to(target)
    elif kind == "directory":
        (legacy / "casepath.db").mkdir()
    else:
        registry = legacy / "artifact-registry"
        registry.mkdir()
        (registry / "preserved.txt").write_text("authority")
    destination = tmp_path / "data"
    with pytest.raises(LocalDataRootError, match="database|registry"):
        bootstrap_data_root(legacy, destination)
    assert not destination.exists()


def test_symlinked_predecessor_root_is_rejected(tmp_path: Path) -> None:
    legacy = _legacy_root(tmp_path)
    alias = tmp_path / "legacy-alias"
    alias.symlink_to(legacy, target_is_directory=True)
    destination = tmp_path / "data"
    with pytest.raises(LocalDataRootError, match="data root is invalid"):
        bootstrap_data_root(alias, destination)
    assert not destination.exists()


def test_corrupt_or_retargeted_provenance_fails_closed(tmp_path: Path) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    bootstrap_data_root(legacy, destination)
    receipt_path = destination / "DATA_ROOT_PROVENANCE.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["destination"] = str(tmp_path / "elsewhere")
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(LocalDataRootError, match="provenance"):
        bootstrap_data_root(legacy, destination)


def test_same_database_bytes_on_a_new_inode_fail_closed(tmp_path: Path) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    bootstrap_data_root(legacy, destination)
    database = destination / "casepath.db"
    replacement = destination / "replacement.db"
    shutil.copy2(database, replacement)
    database.unlink()
    replacement.rename(database)
    with pytest.raises(LocalDataRootError, match="database identity changed"):
        bootstrap_data_root(legacy, destination)


def test_v12_provenance_survives_device_renumbering_with_same_inodes(
    tmp_path: Path,
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    bootstrap_data_root(legacy, destination)
    receipt_path = destination / "DATA_ROOT_PROVENANCE.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["contract"] = "casepath.local-durable-data-provenance/1.2.0"
    for key in (
        "destination_database_file_identity_at_creation",
        "destination_registry_directory_identity_at_creation",
    ):
        receipt[key]["device"] += 1
    material = dict(receipt)
    material.pop("receipt_sha256")
    receipt["receipt_sha256"] = hashlib.sha256(
        local_data_root_module._canonical(material)
    ).hexdigest()
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    assert bootstrap_data_root(legacy, destination) == receipt


def test_same_registry_bytes_in_a_new_directory_fail_closed(
    tmp_path: Path,
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    bootstrap_data_root(legacy, destination)
    registry = destination / "artifact-registry"
    replacement = destination / "replacement-registry"
    original = destination / "original-registry"
    shutil.copytree(registry, replacement)
    registry.rename(original)
    replacement.rename(registry)
    with pytest.raises(LocalDataRootError, match="registry identity changed"):
        bootstrap_data_root(legacy, destination)


@pytest.mark.parametrize(
    "damage",
    (
        "database_deleted",
        "database_symlink",
        "event_removed",
        "event_json_changed",
        "registry_symlink",
        "artifact_deleted",
    ),
)
def test_existing_root_must_retain_every_migrated_authority(
    tmp_path: Path, damage: str
) -> None:
    legacy = _legacy_root(tmp_path)
    destination = tmp_path / "data"
    bootstrap_data_root(legacy, destination)
    database = destination / "casepath.db"
    registry = destination / "artifact-registry"
    if damage == "database_deleted":
        database.unlink()
    elif damage == "database_symlink":
        database.unlink()
        database.symlink_to(legacy / "casepath.db")
    elif damage == "event_removed":
        with sqlite3.connect(database) as connection:
            connection.execute("DELETE FROM claim_loop_events")
    elif damage == "event_json_changed":
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE claim_loop_events SET event_json='{}'"
            )
    elif damage == "registry_symlink":
        shutil.rmtree(registry)
        registry.symlink_to(legacy / "artifact-registry", target_is_directory=True)
    else:
        (registry / "artifacts/evidence.txt").unlink()
    with pytest.raises(LocalDataRootError, match="database|registry|authority"):
        bootstrap_data_root(legacy, destination)


def test_empty_origin_database_deletion_after_first_use_fails_closed(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "data"
    bootstrap_data_root(tmp_path / "absent", destination)
    with sqlite3.connect(destination / "casepath.db") as connection:
        connection.execute("CREATE TABLE durable_event (value TEXT)")
        connection.execute("INSERT INTO durable_event VALUES ('preserve')")
    (destination / "casepath.db").unlink()
    with pytest.raises(LocalDataRootError, match="database lost"):
        bootstrap_data_root(tmp_path / "absent", destination)


def test_dangling_registry_symlink_is_rejected(tmp_path: Path) -> None:
    destination = tmp_path / "data"
    bootstrap_data_root(tmp_path / "absent", destination)
    shutil.rmtree(destination / "artifact-registry")
    destination.joinpath("artifact-registry").symlink_to(
        tmp_path / "outside", target_is_directory=True
    )
    with pytest.raises(LocalDataRootError, match="registry"):
        bootstrap_data_root(tmp_path / "absent", destination)
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize(
    "markers",
    (
        {"CASEPATH_DATA_LOCK_HELD": "1"},
        {"CASEPATH_DATA_LOCK_HELD": "1", "CASEPATH_LAUNCH_LOCK_HELD": "1"},
    ),
)
def test_public_environment_cannot_spoof_the_data_lease(
    markers: dict[str, str],
) -> None:
    repository = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [str(repository / "bin/casepath"), "seed", "--corpus", "synthetic-dev-60"],
        cwd=repository,
        env={
            "PATH": os.environ["PATH"],
            "CASEPATH_UV": os.environ.get("CASEPATH_UV") or shutil.which("uv") or "",
            "CASEPATH_ENV_LOCK_HELD": os.environ.get("CASEPATH_ENV_LOCK_HELD", ""),
            "CASEPATH_ENV_READY": os.environ.get("CASEPATH_ENV_READY", ""),
            **markers,
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 2
    assert "data lease marker has no exact kernel lock owner" in completed.stderr
