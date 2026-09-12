from __future__ import annotations

from datetime import datetime, timezone
import ctypes
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
from typing import Any, Callable
import uuid


PROVENANCE_CONTRACT = "casepath.local-durable-data-provenance/1.3.0"
ACCEPTED_PROVENANCE_CONTRACTS = {
    "casepath.local-durable-data-provenance/1.2.0",
    PROVENANCE_CONTRACT,
}
PROVENANCE_FILE = "DATA_ROOT_PROVENANCE.json"
REGISTRY_MODE_LEASE_CONTRACT = "casepath.legacy-registry-mode-lease/1.0.0"


class LocalDataRootError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, raw: bytes) -> None:
    remaining = memoryview(raw)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise LocalDataRootError("durable publication made no progress")
        remaining = remaining[written:]


def _publish_regular_noreplace(path: Path, raw: bytes) -> None:
    temporary = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4()}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        _write_all(descriptor, raw)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.link(temporary, path, follow_symlinks=False)
        _fsync_directory(path.parent)
        temporary.unlink()
        _fsync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()
            _fsync_directory(path.parent)


def _event_roster(connection: sqlite3.Connection) -> list[dict[str, object]]:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='claim_loop_events'"
    ).fetchone()
    if table is None:
        rows: list[dict[str, object]] = []
    else:
        rows = []
        for row in connection.execute(
            """SELECT session_id,loop_id,sequence,event_sha256,event_json
            FROM claim_loop_events
            ORDER BY session_id,loop_id,sequence"""
        ):
            if not isinstance(row[4], str):
                raise LocalDataRootError(
                    "durable event JSON is not canonical text"
                )
            rows.append(
                {
                    "session_id": row[0],
                    "loop_id": row[1],
                    "sequence": row[2],
                    "event_sha256": row[3],
                    "event_json_sha256": hashlib.sha256(
                        row[4].encode("utf-8")
                    ).hexdigest(),
                }
            )
    return rows


def _event_identity(connection: sqlite3.Connection) -> tuple[int, str]:
    rows = _event_roster(connection)
    return len(rows), hashlib.sha256(_canonical(rows)).hexdigest()


def _reject_extended_acl(path: Path) -> None:
    if os.uname().sysname == "Darwin":
        completed = subprocess.run(
            ["/bin/ls", "-lde", "--", str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = completed.stdout.splitlines()
        if completed.returncode != 0 or not lines or not lines[0].split():
            raise LocalDataRootError("artifact registry ACL audit failed")
        if lines[0].split()[0].endswith("+") or any(
            re.match(r"^\s*\d+:\s", line) for line in lines[1:]
        ):
            raise LocalDataRootError(
                "artifact registry contains an extended ACL"
            )
    elif os.uname().sysname == "Linux":
        try:
            names = os.listxattr(path, follow_symlinks=False)
        except OSError as exc:
            raise LocalDataRootError("artifact registry ACL audit failed") from exc
        if any(name.startswith("system.posix_acl_") for name in names):
            raise LocalDataRootError(
                "artifact registry contains an extended ACL"
            )


def _registry_inventory(root: Path) -> list[dict[str, object]]:
    if root.is_symlink():
        raise LocalDataRootError("legacy artifact registry is invalid")
    if not root.exists():
        return []
    if not root.is_dir():
        raise LocalDataRootError("legacy artifact registry is invalid")
    _reject_extended_acl(root)
    rows = []
    for path in sorted(root.rglob("*")):
        _reject_extended_acl(path)
        metadata = path.lstat()
        if path.is_symlink() or (
            not stat.S_ISREG(metadata.st_mode)
            and not stat.S_ISDIR(metadata.st_mode)
        ):
            raise LocalDataRootError(
                "legacy artifact registry contains a non-regular entry"
            )
        if stat.S_ISREG(metadata.st_mode):
            if metadata.st_nlink != 1:
                raise LocalDataRootError(
                    "artifact registry file must have exactly one link"
                )
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": _digest_file(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    return rows


def _validate_existing(destination: Path) -> dict[str, Any]:
    if destination.is_symlink() or not destination.is_dir():
        raise LocalDataRootError("durable data root is not a regular directory")
    receipt_path = destination / PROVENANCE_FILE
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise LocalDataRootError("durable data root lacks provenance")
    try:
        value = json.loads(receipt_path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalDataRootError("durable data provenance is invalid") from exc
    expected_keys = {
        "contract",
        "created_at",
        "destination",
        "origin",
        "destination_database_file_sha256_at_creation",
        "destination_database_file_identity_at_creation",
        "destination_registry_inventory_sha256_at_creation",
        "destination_registry_directory_identity_at_creation",
        "receipt_sha256",
    }
    material = dict(value) if isinstance(value, dict) else {}
    stated = material.pop("receipt_sha256", None)
    origin = value.get("origin") if isinstance(value, dict) else None
    common_origin_keys = {
        "kind",
        "legacy_database_path",
        "legacy_database_file_sha256_at_backup",
        "claim_loop_event_count",
        "claim_loop_event_roster_sha256",
        "claim_loop_event_roster",
        "legacy_registry_inventory_sha256",
        "legacy_registry_inventory",
        "legacy_registry_cutover",
    }
    try:
        datetime.fromisoformat(value.get("created_at", ""))
    except (TypeError, ValueError) as exc:
        raise LocalDataRootError("durable data provenance is invalid") from exc
    if (
        not isinstance(value, dict)
        or set(value) != expected_keys
        or value.get("contract") not in ACCEPTED_PROVENANCE_CONTRACTS
        or value.get("destination") != str(destination)
        or not isinstance(origin, dict)
        or set(origin) != common_origin_keys
        or origin.get("kind") not in {
            "hash_bound_sqlite_backup_from_casepath_dev_v1",
            "new_empty_durable_data_root",
        }
        or type(origin.get("claim_loop_event_count")) is not int
        or origin["claim_loop_event_count"] < 0
        or not _sha256(origin.get("claim_loop_event_roster_sha256"))
        or not _sha256(origin.get("legacy_registry_inventory_sha256"))
        or not isinstance(origin.get("claim_loop_event_roster"), list)
        or not isinstance(origin.get("legacy_registry_inventory"), list)
        or not isinstance(origin.get("legacy_registry_cutover"), dict)
        or set(origin["legacy_registry_cutover"])
        != {
            "applied",
            "mode_lease_receipt",
            "mode_lease_receipt_sha256",
            "mode_roster_sha256",
            "open_handle_count_after_freeze",
            "policy",
        }
        or type(origin["legacy_registry_cutover"].get("applied")) is not bool
        or (
            origin["legacy_registry_cutover"].get("mode_lease_receipt")
            is not None
            and not isinstance(
                origin["legacy_registry_cutover"].get("mode_lease_receipt"),
                dict,
            )
        )
        or not _sha256(
            origin["legacy_registry_cutover"].get("mode_roster_sha256")
        )
        or (
            origin["legacy_registry_cutover"].get(
                "mode_lease_receipt_sha256"
            )
            is not None
            and not _sha256(
                origin["legacy_registry_cutover"].get(
                    "mode_lease_receipt_sha256"
                )
            )
        )
        or origin["legacy_registry_cutover"].get("applied")
        != (
            origin["legacy_registry_cutover"].get(
                "mode_lease_receipt_sha256"
            )
            is not None
        )
        or origin["legacy_registry_cutover"].get("applied")
        != (
            origin["legacy_registry_cutover"].get("mode_lease_receipt")
            is not None
        )
        or origin["legacy_registry_cutover"].get("open_handle_count_after_freeze")
        != 0
        or origin["legacy_registry_cutover"].get("policy")
        != "write_bits_removed_and_zero_open_handles_through_atomic_publication"
        or (
            value.get("destination_database_file_sha256_at_creation") is not None
            and not _sha256(
                value.get("destination_database_file_sha256_at_creation")
            )
        )
        or not isinstance(
            value.get("destination_database_file_identity_at_creation"), dict
        )
        or set(value["destination_database_file_identity_at_creation"])
        != {"device", "inode"}
        or any(
            type(value["destination_database_file_identity_at_creation"][key])
            is not int
            or value["destination_database_file_identity_at_creation"][key] < 0
            for key in ("device", "inode")
        )
        or not _sha256(
            value.get("destination_registry_inventory_sha256_at_creation")
        )
        or not isinstance(
            value.get("destination_registry_directory_identity_at_creation"), dict
        )
        or set(value["destination_registry_directory_identity_at_creation"])
        != {"device", "inode"}
        or stated != hashlib.sha256(_canonical(material)).hexdigest()
    ):
        raise LocalDataRootError("durable data provenance is invalid")
    baseline_events = origin["claim_loop_event_roster"]
    baseline_registry = origin["legacy_registry_inventory"]
    if (
        len(baseline_events) != origin["claim_loop_event_count"]
        or hashlib.sha256(_canonical(baseline_events)).hexdigest()
        != origin["claim_loop_event_roster_sha256"]
        or hashlib.sha256(_canonical(baseline_registry)).hexdigest()
        != origin["legacy_registry_inventory_sha256"]
        or any(
            not isinstance(row, dict)
            or set(row)
            != {
                "session_id",
                "loop_id",
                "sequence",
                "event_sha256",
                "event_json_sha256",
            }
            or not isinstance(row["session_id"], str)
            or not isinstance(row["loop_id"], str)
            or type(row["sequence"]) is not int
            or row["sequence"] < 1
            or not _sha256(row["event_sha256"])
            or not _sha256(row["event_json_sha256"])
            for row in baseline_events
        )
        or any(
            not isinstance(row, dict)
            or set(row) != {"path", "sha256", "size_bytes"}
            or not isinstance(row["path"], str)
            or row["path"].startswith("/")
            or ".." in Path(row["path"]).parts
            or not _sha256(row["sha256"])
            or type(row["size_bytes"]) is not int
            or row["size_bytes"] < 0
            for row in baseline_registry
        )
    ):
        raise LocalDataRootError("durable data provenance roster is invalid")
    if origin["kind"] == "hash_bound_sqlite_backup_from_casepath_dev_v1":
        if not isinstance(origin["legacy_database_path"], str) or not _sha256(
            origin["legacy_database_file_sha256_at_backup"]
        ):
            raise LocalDataRootError("durable data provenance origin is invalid")
        mode_lease_receipt = origin["legacy_registry_cutover"][
            "mode_lease_receipt"
        ]
        if mode_lease_receipt is not None:
            _validate_mode_lease_receipt_value(
                mode_lease_receipt,
                Path(origin["legacy_database_path"]).parent
                / "artifact-registry",
                destination,
                baseline_registry,
            )
            if (
                mode_lease_receipt["receipt_sha256"]
                != origin["legacy_registry_cutover"][
                    "mode_lease_receipt_sha256"
                ]
                or mode_lease_receipt["mode_roster_sha256"]
                != origin["legacy_registry_cutover"]["mode_roster_sha256"]
            ):
                raise LocalDataRootError(
                    "durable data provenance mode lease differs"
                )
    elif (
        origin["legacy_database_path"] is not None
        or origin["legacy_database_file_sha256_at_backup"] is not None
        or baseline_events
        or baseline_registry
    ):
        raise LocalDataRootError("durable data provenance origin is invalid")
    registry = destination / "artifact-registry"
    if registry.is_symlink() or not registry.is_dir():
        raise LocalDataRootError("durable artifact registry is missing")
    registry_metadata = registry.stat()
    # ``st_dev`` is a mount-instance identifier on macOS and may be renumbered
    # after a reboot/remount even though the underlying object and inode are
    # unchanged.  Treat it as diagnostic provenance, while the inode remains
    # the replacement guard.  The exact destination path, no-symlink checks,
    # baseline registry inventory, and complete journal validation below stay
    # authoritative.  This also permits a v1.2 receipt to survive a legitimate
    # device renumbering without rewriting its append-only provenance bytes.
    if (
        value["destination_registry_directory_identity_at_creation"]["inode"]
        != registry_metadata.st_ino
    ):
        raise LocalDataRootError("durable artifact registry identity changed")
    current_registry = _registry_inventory(registry)
    current_registry_by_path = {row["path"]: row for row in current_registry}
    if any(current_registry_by_path.get(row.get("path")) != row for row in baseline_registry):
        raise LocalDataRootError("durable artifact registry lost baseline authority")
    database = destination / "casepath.db"
    database_present = database.exists() or database.is_symlink()
    if not database_present:
        raise LocalDataRootError("durable database lost baseline authority")
    if database_present:
        descriptor = -1
        try:
            descriptor = os.open(
                database,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            )
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise LocalDataRootError("durable database is not one regular file")
            database_metadata = os.fstat(descriptor)
            if database_metadata.st_nlink != 1:
                raise LocalDataRootError(
                    "durable database must have exactly one link"
                )
            if (
                value["destination_database_file_identity_at_creation"]["inode"]
                != database_metadata.st_ino
            ):
                raise LocalDataRootError("durable database identity changed")
        except OSError as exc:
            raise LocalDataRootError("durable database is not one regular file") from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        try:
            with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
                if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise LocalDataRootError("durable database failed integrity check")
                current_events = _event_roster(connection)
        except sqlite3.DatabaseError as exc:
            raise LocalDataRootError("durable database failed integrity check") from exc
        current_event_keys = {
            (row["session_id"], row["loop_id"], row["sequence"]): row
            for row in current_events
        }
        if any(
            current_event_keys.get(
                (row["session_id"], row["loop_id"], row["sequence"])
            )
            != row
            for row in baseline_events
        ):
            raise LocalDataRootError("durable database lost baseline authority")
    return value


def _fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        elif path.is_dir():
            descriptor = os.open(path, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    descriptor = os.open(root, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _registry_mode_roster(root: Path) -> list[dict[str, object]]:
    if root.is_symlink() or not root.is_dir():
        raise LocalDataRootError("legacy artifact registry is invalid")
    rows: list[dict[str, object]] = []
    for path in [root, *sorted(root.rglob("*"))]:
        _reject_extended_acl(path)
        metadata = path.lstat()
        if path.is_symlink() or (
            not stat.S_ISREG(metadata.st_mode)
            and not stat.S_ISDIR(metadata.st_mode)
        ):
            raise LocalDataRootError(
                "legacy artifact registry contains a non-regular entry"
            )
        if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
            raise LocalDataRootError(
                "artifact registry file must have exactly one link"
            )
        rows.append(
            {
                "path": "." if path == root else path.relative_to(root).as_posix(),
                "mode": stat.S_IMODE(metadata.st_mode),
                "kind": "directory" if stat.S_ISDIR(metadata.st_mode) else "file",
            }
        )
    return rows


def _registry_mode_lease_path(destination: Path) -> Path:
    return destination.parent / f".{destination.name}.legacy-registry-mode-lease.json"


def _validate_mode_roster(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list) or not rows:
        raise LocalDataRootError("legacy registry mode lease is invalid")
    paths: list[str] = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"kind", "mode", "path"}
            or row.get("kind") not in {"directory", "file"}
            or type(row.get("mode")) is not int
            or not 0 <= row["mode"] <= 0o7777
            or not isinstance(row.get("path"), str)
            or (
                row["path"] != "."
                and (
                    Path(row["path"]).is_absolute()
                    or Path(row["path"]).as_posix() != row["path"]
                    or any(
                        part in {"", ".", ".."}
                        for part in Path(row["path"]).parts
                    )
                )
            )
        ):
            raise LocalDataRootError("legacy registry mode lease is invalid")
        paths.append(row["path"])
    if paths[0] != "." or len(paths) != len(set(paths)):
        raise LocalDataRootError("legacy registry mode lease is invalid")
    if paths[1:] != sorted(paths[1:]):
        raise LocalDataRootError("legacy registry mode lease is not canonical")
    return rows


def _mode_lease_receipt(
    root: Path,
    destination: Path,
    rows: list[dict[str, object]],
    registry_inventory: list[dict[str, object]],
) -> dict[str, object]:
    validated = _validate_mode_roster(rows)
    metadata = root.stat()
    material: dict[str, object] = {
        "contract": REGISTRY_MODE_LEASE_CONTRACT,
        "destination": str(destination),
        "legacy_registry": str(root),
        "legacy_registry_identity": {
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
        },
        "mode_roster": validated,
        "mode_roster_sha256": hashlib.sha256(_canonical(validated)).hexdigest(),
        "registry_inventory_sha256": hashlib.sha256(
            _canonical(registry_inventory)
        ).hexdigest(),
    }
    return {
        **material,
        "receipt_sha256": hashlib.sha256(_canonical(material)).hexdigest(),
    }


def _validate_mode_lease_receipt_value(
    receipt: object,
    root: Path,
    destination: Path,
    expected_inventory: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    material = dict(receipt) if isinstance(receipt, dict) else {}
    stated = material.pop("receipt_sha256", None)
    if (
        not isinstance(receipt, dict)
        or set(receipt)
        != {
            "contract",
            "destination",
            "legacy_registry",
            "legacy_registry_identity",
            "mode_roster",
            "mode_roster_sha256",
            "registry_inventory_sha256",
            "receipt_sha256",
        }
        or receipt.get("contract") != REGISTRY_MODE_LEASE_CONTRACT
        or receipt.get("destination") != str(destination)
        or receipt.get("legacy_registry") != str(root)
        or not isinstance(receipt.get("legacy_registry_identity"), dict)
        or set(receipt["legacy_registry_identity"]) != {"device", "inode"}
        or any(
            type(receipt["legacy_registry_identity"].get(key)) is not int
            or receipt["legacy_registry_identity"][key] < 0
            for key in ("device", "inode")
        )
        or not _sha256(receipt.get("mode_roster_sha256"))
        or not _sha256(receipt.get("registry_inventory_sha256"))
        or stated != hashlib.sha256(_canonical(material)).hexdigest()
    ):
        raise LocalDataRootError("legacy registry mode lease is invalid")
    rows = _validate_mode_roster(receipt["mode_roster"])
    if hashlib.sha256(_canonical(rows)).hexdigest() != receipt[
        "mode_roster_sha256"
    ]:
        raise LocalDataRootError("legacy registry mode lease is invalid")
    if expected_inventory is not None and receipt[
        "registry_inventory_sha256"
    ] != hashlib.sha256(_canonical(expected_inventory)).hexdigest():
        raise LocalDataRootError("legacy registry mode lease is invalid")
    return rows


def _publish_registry_mode_lease(
    root: Path,
    destination: Path,
    rows: list[dict[str, object]],
    registry_inventory: list[dict[str, object]],
) -> tuple[Path, dict[str, object]]:
    receipt = _mode_lease_receipt(
        root, destination, rows, registry_inventory
    )
    path = _registry_mode_lease_path(destination)
    raw = json.dumps(
        receipt, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    try:
        _publish_regular_noreplace(path, raw)
    except FileExistsError as exc:
        raise LocalDataRootError(
            "legacy registry mode lease already exists"
        ) from exc
    return path, receipt


def _read_registry_mode_lease(
    root: Path, destination: Path
) -> tuple[Path, dict[str, object]] | None:
    path = _registry_mode_lease_path(destination)
    if not path.exists() and not path.is_symlink():
        return None
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise LocalDataRootError("legacy registry mode lease is not regular")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
    except OSError as exc:
        raise LocalDataRootError("legacy registry mode lease is not regular") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        receipt = json.loads(b"".join(chunks))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LocalDataRootError("legacy registry mode lease is invalid") from exc
    _validate_mode_lease_receipt_value(receipt, root, destination)
    metadata = root.stat()
    if receipt["legacy_registry_identity"] != {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
    } or receipt["registry_inventory_sha256"] != hashlib.sha256(
        _canonical(_registry_inventory(root))
    ).hexdigest():
        raise LocalDataRootError("legacy registry changed while recovery was pending")
    return path, receipt


def _sync_registry_modes(root: Path, rows: list[dict[str, object]]) -> None:
    for row in rows:
        path = root if row["path"] == "." else root / str(row["path"])
        metadata = path.lstat()
        expected_kind = "directory" if stat.S_ISDIR(metadata.st_mode) else "file"
        if (
            path.is_symlink()
            or expected_kind != row["kind"]
            or stat.S_IMODE(metadata.st_mode) != row["mode"]
        ):
            raise LocalDataRootError(
                "legacy registry changed before mode restoration"
            )
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _clear_registry_mode_lease(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    _fsync_directory(path.parent)


def _recover_registry_mode_lease(root: Path, destination: Path) -> None:
    loaded = _read_registry_mode_lease(root, destination)
    if loaded is None:
        return
    path, receipt = loaded
    rows = _validate_mode_roster(receipt["mode_roster"])
    _restore_registry_modes(root, rows)
    _sync_registry_modes(root, rows)
    _clear_registry_mode_lease(path)


def _remove_stale_staging(destination: Path) -> None:
    parent = destination.parent
    changed = False
    for candidate in sorted(parent.glob(f".{destination.name}.*.tmp")):
        if candidate.is_symlink() or not candidate.is_dir():
            raise LocalDataRootError("durable data staging is invalid")
        shutil.rmtree(candidate)
        changed = True
    if changed:
        _fsync_directory(parent)


def _remove_stale_mode_lease_temps(destination: Path) -> None:
    """Remove only exact unpublished temp links left by a killed publisher."""

    parent = destination.parent
    lease_path = _registry_mode_lease_path(destination)
    pattern = re.compile(
        rf"^\.{re.escape(lease_path.name)}\.[0-9]+\."
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.tmp$"
    )
    changed = False
    for candidate in sorted(parent.iterdir()):
        if not pattern.fullmatch(candidate.name):
            continue
        metadata = candidate.lstat()
        if candidate.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise LocalDataRootError(
                "legacy registry mode-lease staging is invalid"
            )
        if lease_path.exists() or lease_path.is_symlink():
            lease_metadata = lease_path.lstat()
            if (
                lease_path.is_symlink()
                or not stat.S_ISREG(lease_metadata.st_mode)
                or (metadata.st_dev, metadata.st_ino)
                != (lease_metadata.st_dev, lease_metadata.st_ino)
            ):
                raise LocalDataRootError(
                    "legacy registry mode-lease staging conflicts with authority"
                )
        candidate.unlink()
        changed = True
    if changed:
        _fsync_directory(parent)


def _open_registry_handle_count(root: Path) -> int:
    if os.uname().sysname == "Darwin":
        executable = Path("/usr/sbin/lsof")
        if not executable.is_file():
            raise LocalDataRootError("registry cutover requires trusted lsof")
        completed = subprocess.run(
            [str(executable), "-n", "-F", "p", "+D", str(root)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode not in {0, 1}:
            raise LocalDataRootError("registry open-handle audit failed")
        return len(
            {
                line[1:]
                for line in completed.stdout.splitlines()
                if line.startswith("p") and line[1:].isdigit()
            }
        )
    if os.uname().sysname == "Linux":
        resolved = root.resolve()
        owners: set[str] = set()
        for process in Path("/proc").iterdir():
            if not process.name.isdigit():
                continue
            try:
                status_lines = (process / "status").read_text().splitlines()
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
            uid_lines = [line for line in status_lines if line.startswith("Uid:")]
            if len(uid_lines) != 1:
                raise LocalDataRootError("registry process ownership audit failed")
            uid_fields = uid_lines[0].split()
            if len(uid_fields) < 2 or not uid_fields[1].isdigit():
                raise LocalDataRootError("registry process ownership audit failed")
            if int(uid_fields[1]) != os.geteuid():
                continue
            candidates = [process / "cwd", process / "root"]
            descriptor_root = process / "fd"
            try:
                candidates.extend(descriptor_root.iterdir())
            except (FileNotFoundError, PermissionError):
                pass
            for candidate in candidates:
                try:
                    target = candidate.resolve(strict=True)
                    target.relative_to(resolved)
                except (FileNotFoundError, OSError, PermissionError, ValueError):
                    continue
                owners.add(process.name)
                break
            if process.name in owners:
                continue
            try:
                maps = (process / "maps").read_text(
                    encoding="utf-8", errors="surrogateescape"
                )
            except (FileNotFoundError, ProcessLookupError):
                continue
            except PermissionError as exc:
                raise LocalDataRootError(
                    "registry memory-map audit is unavailable"
                ) from exc
            for line in maps.splitlines():
                fields = line.split(maxsplit=5)
                if len(fields) != 6 or not fields[5].startswith("/"):
                    continue
                mapped = fields[5]
                if mapped.endswith(" (deleted)"):
                    mapped = mapped[: -len(" (deleted)")]
                for escaped, decoded in (
                    (r"\040", " "),
                    (r"\011", "\t"),
                    (r"\012", "\n"),
                    (r"\134", "\\"),
                ):
                    mapped = mapped.replace(escaped, decoded)
                try:
                    Path(mapped).resolve(strict=False).relative_to(resolved)
                except (OSError, ValueError):
                    continue
                owners.add(process.name)
                break
        return len(owners)
    raise LocalDataRootError("registry cutover platform is unsupported")


def _freeze_registry(
    root: Path, expected_rows: list[dict[str, object]]
) -> tuple[list[dict[str, object]], str]:
    rows = _registry_mode_roster(root)
    if rows != expected_rows:
        raise LocalDataRootError(
            "legacy registry changed before its mode lease was acquired"
        )
    paths = {
        row["path"]: root if row["path"] == "." else root / str(row["path"])
        for row in rows
    }
    try:
        for row in rows:
            os.chmod(paths[str(row["path"])], int(row["mode"]) & ~0o222)
        if _open_registry_handle_count(root) != 0:
            raise LocalDataRootError(
                "legacy artifact registry has a live open handle during cutover"
            )
        mode_roster_sha256 = hashlib.sha256(_canonical(rows)).hexdigest()
        return rows, mode_roster_sha256
    except Exception:
        for row in reversed(rows):
            os.chmod(paths[str(row["path"])], int(row["mode"]))
        raise


def _restore_registry_modes(
    root: Path, rows: list[dict[str, object]] | None
) -> None:
    if rows is None:
        return
    for row in reversed(rows):
        path = root if row["path"] == "." else root / str(row["path"])
        os.chmod(path, int(row["mode"]))


def _publish_directory_noreplace(source: Path, destination: Path) -> None:
    """Atomically publish one directory while refusing an existing target."""

    library = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if hasattr(library, "renamex_np"):
        rename = library.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(source_bytes, destination_bytes, 0x00000004)  # RENAME_EXCL
    elif hasattr(library, "renameat2"):
        rename = library.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(-100, source_bytes, -100, destination_bytes, 1)
    else:
        raise LocalDataRootError(
            "platform lacks atomic no-replace directory publication"
        )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def _bootstrap_data_root_locked(
    legacy_root: str | Path,
    destination_root: str | Path,
    *,
    fault_point: str | None = None,
    staged_database_validator: Callable[[Path], None] | None = None,
) -> dict[str, Any]:
    """Create one durable data root without modifying the predecessor bytes."""

    if fault_point not in {
        None,
        "after_staging",
        "after_database",
        "before_publish",
        "hard_exit_after_registry_freeze",
        "hard_exit_after_publish_before_registry_restore",
    }:
        raise LocalDataRootError("data-root fault point is invalid")
    supplied_legacy = Path(legacy_root)
    if supplied_legacy.is_symlink():
        raise LocalDataRootError("legacy data root is invalid")
    legacy = supplied_legacy.resolve()
    destination = Path(destination_root).absolute()
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return _validate_existing(destination)
    staging = parent / f".{destination.name}.{os.getpid()}.{uuid.uuid4()}.tmp"
    source_write_lease: sqlite3.Connection | None = None
    frozen_registry_root: Path | None = None
    registry_mode_roster: list[dict[str, object]] | None = None
    registry_mode_lease_path: Path | None = None
    registry_mode_lease_receipt: dict[str, object] | None = None
    try:
        staging.mkdir(mode=0o700)
        if fault_point == "after_staging":
            raise LocalDataRootError("injected failure after staging")
        source_db = legacy / "casepath.db"
        target_db = staging / "casepath.db"
        target_registry = staging / "artifact-registry"
        source_db_present = source_db.exists() or source_db.is_symlink()
        if source_db_present:
            source_db_metadata = source_db.lstat()
            if (
                source_db.is_symlink()
                or not stat.S_ISREG(source_db_metadata.st_mode)
                or source_db_metadata.st_nlink != 1
            ):
                raise LocalDataRootError(
                    "legacy database is not one single-link regular file"
                )
        if source_db_present:
            # The predecessor launcher did not expose a lock that a successor
            # could safely join.  SQLite itself is therefore the cutover
            # authority: hold one RESERVED writer lease from before the
            # snapshot until after atomic destination publication.  Existing
            # readers remain available, while any late predecessor append is
            # blocked rather than silently falling outside the migration.
            try:
                source_write_lease = sqlite3.connect(
                    source_db, timeout=30, isolation_level=None
                )
                source_write_lease.execute("BEGIN IMMEDIATE")
            except sqlite3.DatabaseError as exc:
                if source_write_lease is not None:
                    source_write_lease.close()
                    source_write_lease = None
                raise LocalDataRootError(
                    "legacy database writer cutover lease is unavailable"
                ) from exc
            source_uri = f"file:{source_db.as_posix()}?mode=ro"
            with sqlite3.connect(source_uri, uri=True) as source:
                source_before = _event_identity(source)
                with sqlite3.connect(target_db) as target:
                    source.backup(target)
                    target.commit()
                source_after = _event_identity(source)
            with sqlite3.connect(target_db) as target:
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise LocalDataRootError(
                        "durable database copy failed integrity check"
                    )
                target_identity = _event_identity(target)
                target_roster = _event_roster(target)
            if source_before != source_after or source_before != target_identity:
                raise LocalDataRootError(
                    "legacy event journal changed during durable copy"
                )
            if fault_point == "after_database":
                raise LocalDataRootError("injected failure after database")
            source_registry = legacy / "artifact-registry"
            registry_before = _registry_inventory(source_registry)
            if source_registry.exists():
                registry_mode_roster = _registry_mode_roster(source_registry)
                frozen_registry_root = source_registry
                (
                    registry_mode_lease_path,
                    registry_mode_lease_receipt,
                ) = _publish_registry_mode_lease(
                    source_registry,
                    destination,
                    registry_mode_roster,
                    registry_before,
                )
                registry_mode_roster, registry_mode_roster_sha256 = (
                    _freeze_registry(source_registry, registry_mode_roster)
                )
                if fault_point == "hard_exit_after_registry_freeze":
                    os._exit(91)
                if registry_before != _registry_inventory(source_registry):
                    raise LocalDataRootError(
                        "artifact registry changed while its cutover lease was acquired"
                    )
            else:
                registry_mode_roster_sha256 = hashlib.sha256(
                    _canonical([])
                ).hexdigest()
            if source_registry.exists():
                shutil.copytree(source_registry, target_registry)
                _restore_registry_modes(target_registry, registry_mode_roster)
            else:
                target_registry.mkdir()
            if (
                registry_before != _registry_inventory(source_registry)
                or registry_before != _registry_inventory(target_registry)
            ):
                raise LocalDataRootError(
                    "artifact registry changed during durable copy"
                )
            origin = {
                "kind": "hash_bound_sqlite_backup_from_casepath_dev_v1",
                "legacy_database_path": str(source_db),
                "legacy_database_file_sha256_at_backup": _digest_file(source_db),
                "claim_loop_event_count": source_before[0],
                "claim_loop_event_roster_sha256": source_before[1],
                "claim_loop_event_roster": target_roster,
                "legacy_registry_inventory_sha256": hashlib.sha256(
                    _canonical(registry_before)
                ).hexdigest(),
                "legacy_registry_inventory": registry_before,
                "legacy_registry_cutover": {
                    "applied": source_registry.exists(),
                    "mode_lease_receipt": registry_mode_lease_receipt,
                    "mode_lease_receipt_sha256": (
                        registry_mode_lease_receipt["receipt_sha256"]
                        if registry_mode_lease_receipt is not None
                        else None
                    ),
                    "mode_roster_sha256": registry_mode_roster_sha256,
                    "open_handle_count_after_freeze": 0,
                    "policy": (
                        "write_bits_removed_and_zero_open_handles_through_"
                        "atomic_publication"
                    ),
                },
            }
        else:
            if legacy.exists():
                if legacy.is_symlink() or not legacy.is_dir():
                    raise LocalDataRootError("legacy data root is invalid")
                allowed = {"artifact-registry"}
                if any(path.name not in allowed for path in legacy.iterdir()):
                    raise LocalDataRootError(
                        "legacy data root lacks its database"
                    )
                source_registry = legacy / "artifact-registry"
                if _registry_inventory(source_registry):
                    raise LocalDataRootError(
                        "legacy registry exists without its database"
                    )
            target_registry.mkdir()
            with sqlite3.connect(target_db) as target:
                target.execute("PRAGMA user_version=0")
                target.execute("VACUUM")
            empty_sha = hashlib.sha256(_canonical([])).hexdigest()
            origin = {
                "kind": "new_empty_durable_data_root",
                "legacy_database_path": None,
                "legacy_database_file_sha256_at_backup": None,
                "claim_loop_event_count": 0,
                "claim_loop_event_roster_sha256": empty_sha,
                "claim_loop_event_roster": [],
                "legacy_registry_inventory_sha256": empty_sha,
                "legacy_registry_inventory": [],
                "legacy_registry_cutover": {
                    "applied": False,
                    "mode_lease_receipt": None,
                    "mode_lease_receipt_sha256": None,
                    "mode_roster_sha256": empty_sha,
                    "open_handle_count_after_freeze": 0,
                    "policy": (
                        "write_bits_removed_and_zero_open_handles_through_"
                        "atomic_publication"
                    ),
                },
            }
        if staged_database_validator is not None:
            try:
                staged_database_validator(target_db)
            except Exception as exc:
                raise LocalDataRootError(
                    "staged durable database failed semantic replay"
                ) from exc
        database_metadata = target_db.stat()
        registry_metadata = target_registry.stat()
        material = {
            "contract": PROVENANCE_CONTRACT,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "destination": str(destination),
            "origin": origin,
            "destination_database_file_sha256_at_creation": (
                _digest_file(target_db) if target_db.exists() else None
            ),
            "destination_database_file_identity_at_creation": {
                "device": database_metadata.st_dev,
                "inode": database_metadata.st_ino,
            },
            "destination_registry_inventory_sha256_at_creation": hashlib.sha256(
                _canonical(_registry_inventory(target_registry))
            ).hexdigest(),
            "destination_registry_directory_identity_at_creation": {
                "device": registry_metadata.st_dev,
                "inode": registry_metadata.st_ino,
            },
        }
        receipt = {
            **material,
            "receipt_sha256": hashlib.sha256(_canonical(material)).hexdigest(),
        }
        receipt_path = staging / PROVENANCE_FILE
        with receipt_path.open("xb") as stream:
            stream.write(
                json.dumps(
                    receipt, indent=2, ensure_ascii=False, sort_keys=True
                ).encode()
                + b"\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        _fsync_tree(staging)
        if fault_point == "before_publish":
            raise LocalDataRootError("injected failure before publication")
        try:
            _publish_directory_noreplace(staging, destination)
        except OSError as exc:
            # macOS reports ENOTEMPTY (rather than EEXIST) when a concurrent
            # publisher won the directory rename.  Only those two precise
            # collisions may fall through to winner validation; every other
            # publication error remains terminal.
            if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                raise
            return _validate_existing(destination)
        descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        if fault_point == "hard_exit_after_publish_before_registry_restore":
            os._exit(92)
        return receipt
    finally:
        if frozen_registry_root is not None:
            _restore_registry_modes(frozen_registry_root, registry_mode_roster)
            if registry_mode_roster is None:
                raise LocalDataRootError("legacy registry mode roster was lost")
            _sync_registry_modes(frozen_registry_root, registry_mode_roster)
        if registry_mode_lease_path is not None:
            _clear_registry_mode_lease(registry_mode_lease_path)
        if source_write_lease is not None:
            try:
                source_write_lease.rollback()
            finally:
                source_write_lease.close()
        if staging.exists():
            shutil.rmtree(staging)


def bootstrap_data_root(
    legacy_root: str | Path,
    destination_root: str | Path,
    *,
    fault_point: str | None = None,
    staged_database_validator: Callable[[Path], None] | None = None,
) -> dict[str, Any]:
    """Recover and create one durable data root under a kernel-held election."""

    supplied_legacy = Path(legacy_root)
    if supplied_legacy.is_symlink():
        raise LocalDataRootError("legacy data root is invalid")
    legacy = supplied_legacy.resolve()
    destination = Path(destination_root).absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    lock_path = destination.parent / f".{destination.name}.bootstrap.lock"
    descriptor = -1
    try:
        descriptor = os.open(
            lock_path,
            os.O_RDWR
            | os.O_CREAT
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise LocalDataRootError("durable data bootstrap lock is not regular")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        _recover_registry_mode_lease(
            legacy / "artifact-registry", destination
        )
        _remove_stale_mode_lease_temps(destination)
        _remove_stale_staging(destination)
        return _bootstrap_data_root_locked(
            legacy,
            destination,
            fault_point=fault_point,
            staged_database_validator=staged_database_validator,
        )
    except OSError as exc:
        raise LocalDataRootError("durable data bootstrap lock failed") from exc
    finally:
        if descriptor >= 0:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
