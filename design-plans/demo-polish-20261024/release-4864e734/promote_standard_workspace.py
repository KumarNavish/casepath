"""Promote the existing standard workspace without replacing its data or history.

Install this separately bound helper at NEW_NS/promote_standard_workspace.py.
Run it with an isolated Python outside the old workspace's runtime: python -I -B.
The caller owns stopping and starting Commander sessions; this helper does neither.

Commands (use a fresh, descriptive --attempt value):
  snapshot --attempt <id>
  source --attempt <id> --stop-receipt <absolute-json-path>
  verify --attempt <id> --running-receipt <absolute-json-path>

The stop receipt is an envelope with exactly these evidence members:
  {"contract": "casepath.standard-promotion-stop/1",
   "snapshot_sha256": "<hash of this attempt's snapshot/receipt.json>",
   "stop_response": <unmodified actual Commander stop tool response>,
   "terminal_response": <unmodified actual Commander terminal tool response>}
The raw responses may be the structured result, a {"result": ...} wrapper,
structuredContent, or MCP content text containing JSON. stop_response must
identify the known old session and contain terminated:true. terminal_response
must identify that same session and have terminal state completed, terminated,
or failed. It must contain its actual integer exitCode, or an explicit signal
when no numeric exit code was supplied (signal, exitSignal, or terminationSignal;
SIGTERM/TERM/15, SIGINT/INT/2, or SIGKILL/KILL/9). A nonzero stop exit
does not mean that the old service is still running. A closed local port is
checked independently. Convenience flags such as stopped:true are not evidence.

For verify, --running-receipt is the unmodified actual Commander structured
response for the newly started session. It must identify a different nonempty
sessionId, have state:running, and include its actual positive integer PID.
Native boot lineage and GET health bind the service to its source and data.

No original database rows, artifact contents, credentials, or unfiltered health
payloads are written to evidence. Only logical counts/hashes, file inventories,
safe identities, and command/validation receipts are retained. The existing
23-file publication-helper binding is never changed.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import socket
import sqlite3
import stat
import struct
import subprocess
import time
import urllib.error
import urllib.request


NEW_ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024")
NS = NEW_ROOT / ".runtime/commander-demo-polish"
BASE = NS / "release"
PROMOTIONS = NS / "standard-promotion"
OLD_ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-northstar-20261024")
OLD_SHA = "b20685d1670b33b941b1bfcb902638a879c01b93"
OLD_BRANCH = "codex/casepath-northstar-review-20261024"
OLD_SESSION = "cp-ns-20261024-standard-workspace-repaired-4173"
DATA = OLD_ROOT / ".runtime/casepath-data-v1"
RUNTIME = OLD_ROOT / ".runtime/casepath-dev-v2"
BOOT_RECEIPT = RUNTIME / "runtime-boot-receipt.json"
BOOTS = RUNTIME / "boots"
DATABASES = ("casepath.db", "agent-work-v1.sqlite3")
ORIGIN = "http://127.0.0.1:4173"
ASSETS = (
    "review-northstar-v1.js", "review-northstar-v1.css",
    "autonomous-workspace-v1.js", "autonomous-workspace-v1.css",
    "autonomous-presentation-v1.js", "autonomous-language-v1.js",
)


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_regular(path):
    path = Path(path)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(), "Expected a regular evidence/source file: " + str(path))
    require(stat.S_ISREG(path.stat().st_mode), "Special files are not admissible")
    return path


def digest(path):
    path = safe_regular(path)
    before = path.stat()
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "File changed while hashing: " + str(path))
    return result.hexdigest()


def read(path):
    return json.loads(safe_regular(path).read_bytes())


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, ensure_ascii=True, allow_nan=False)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def identity(path):
    value = Path(path).stat()
    return {"device": value.st_dev, "inode": value.st_ino}


def environment(candidate=None):
    # Forward only the real account HOME. Do not redirect HOME into a task tree.
    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    supplied_home = os.environ.get("HOME")
    require(supplied_home is not None and Path(supplied_home).resolve() == real_home.resolve(), "A real account HOME must be forwarded")
    result = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/Users/kumar0002/.local/bin:/usr/local/bin",
        "HOME": supplied_home, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "SOURCE_DATE_EPOCH": "1786406400", "CASEPATH_UV": "/Users/kumar0002/.local/bin/uv",
        "CASEPATH_MODEL_MODE": "deterministic_reference", "CASEPATH_AGENT_WORK_EXTERNAL_FACTS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }
    if candidate is not None:
        result["CASEPATH_SOURCE_COMMIT"] = candidate
    return result


def git(root, *arguments):
    # Read-only queries; mutations use command() with separately retained logs.
    raw = subprocess.check_output(["/usr/bin/git", "--no-optional-locks", *arguments], cwd=root,
                                  env=environment(), timeout=60, stderr=subprocess.PIPE)
    return raw.decode("utf-8").strip()


def checkout(root, expected, branch=None):
    require((root / ".git").is_dir() and not (root / ".git").is_symlink(), "A normal local clone is required")
    require(Path(git(root, "rev-parse", "--show-toplevel")).resolve() == root.resolve(), "Unexpected git worktree root")
    require(git(root, "rev-parse", "HEAD") == expected, "Unexpected workspace HEAD")
    if branch is not None:
        require(git(root, "branch", "--show-current") == branch, "Unexpected standard workspace branch")
    require(not git(root, "status", "--porcelain", "--untracked-files=all"), "Workspace must be clean")
    return {"head": expected, "tree": git(root, "rev-parse", "HEAD^{tree}"), "branch": git(root, "branch", "--show-current"), "clean": True}


def add_part(hasher, value):
    hasher.update(struct.pack(">Q", len(value)))
    hasher.update(value)


def row_digest(row):
    result = hashlib.sha256(b"casepath.sqlite-typed-row/1\0")
    for value in row:
        if value is None:
            raw = b"n"
        elif isinstance(value, int):
            raw = b"i" + str(value).encode("ascii")
        elif isinstance(value, float):
            raw = b"f" + struct.pack(">d", value)
        elif isinstance(value, str):
            raw = b"t" + value.encode("utf-8")
        elif isinstance(value, bytes):
            raw = b"b" + value
        else:
            raise RuntimeError("Unsupported SQLite value type")
        add_part(result, raw)
    return result.digest()


def quote_identifier(name):
    require(isinstance(name, str) and "\0" not in name, "Invalid SQLite identifier")
    return '"' + name.replace('"', '""') + '"'


def database_fingerprint(connection, path):
    # A read transaction covers every schema/table query. No VACUUM, checkpoint,
    # backup, replay, migration or writes are used. Include sqlite_* tables too.
    schema = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name,tbl_name,sql").fetchall()
    tables = {}
    for kind, name, _owner, definition in schema:
        if kind != "table":
            continue
        quoted = quote_identifier(name)
        columns = connection.execute("PRAGMA table_xinfo(" + quoted + ")").fetchall()
        visible_names = {row[1].casefold() for row in columns}
        implicit = next((key for key in ("_rowid_", "rowid", "oid") if key not in visible_names), None)
        projection = "*"
        if implicit is not None:
            try:
                # An unquoted rowid name avoids SQLite's quoted-string fallback.
                connection.execute("SELECT " + implicit + " FROM " + quoted + " LIMIT 0")
                projection = implicit + ",*"
            except sqlite3.OperationalError as error:
                require("no such column" in str(error), "Unexpected rowid query error")
                implicit = None
        values = [row_digest(row) for row in connection.execute("SELECT " + projection + " FROM " + quoted)]
        values.sort()
        combined = hashlib.sha256(b"casepath.sqlite-row-multiset/1\0")
        combined.update(struct.pack(">Q", len(values)))
        for value in values:
            combined.update(value)
        tables[name] = {
            "rows": len(values), "row_multiset_sha256": combined.hexdigest(),
            "schema_sha256": sha(encoded(definition)), "columns_sha256": sha(encoded(columns)),
            "columns": len(columns), "implicit_rowid_included": implicit is not None,
        }
    require(tables, "Database contains no tables")
    logical = {"schema_sha256": sha(encoded(schema)), "tables": tables,
               "user_version": connection.execute("PRAGMA user_version").fetchone()[0],
               "application_id": connection.execute("PRAGMA application_id").fetchone()[0]}
    return {"path": str(path), "file_identity": identity(path), "table_count": len(tables),
            "logical_sha256": sha(encoded(logical)), **logical}


def files_inventory(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), "Required directory missing or symlinked: " + str(directory))
    values = {}
    def traversal_error(error):
        raise error
    for parent, directories, files in os.walk(directory, followlinks=False, onerror=traversal_error):
        directories.sort()
        files.sort()
        for name in directories:
            path = Path(parent) / name
            require(path.is_dir() and not path.is_symlink(), "Directory symlink or special entry is not admissible")
        for name in files:
            path = Path(parent) / name
            relative = path.relative_to(directory).as_posix()
            values[relative] = {"sha256": digest(path), "bytes": path.stat().st_size}
    return values


def data_fingerprint():
    require(DATA.is_dir() and not DATA.is_symlink(), "The original data root is required")
    with ExitStack() as stack:
        opened = []
        for name in DATABASES:
            path = safe_regular(DATA / name)
            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, isolation_level=None, timeout=5)
            stack.callback(connection.close)
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("BEGIN")
            # Acquire each snapshot before reading either complete database.
            connection.execute("SELECT count(*) FROM sqlite_schema").fetchone()
            opened.append((name, path, connection))
        databases = {name: database_fingerprint(connection, path) for name, path, connection in opened}
    registry = DATA / "artifact-registry"
    files = files_inventory(registry)
    provenance = DATA / "DATA_ROOT_PROVENANCE.json"
    return {
        "contract": "casepath.standard-logical-data/1", "data_root": str(DATA),
        "data_root_identity": identity(DATA), "databases": databases,
        "artifact_registry": {"path": str(registry), "file_count": len(files),
                              "bytes": sum(row["bytes"] for row in files.values()),
                              "aggregate_sha256": sha(encoded(files)), "root_identity": identity(registry)},
        "provenance": {"sha256": digest(provenance), "bytes": provenance.stat().st_size, "file_identity": identity(provenance)},
        "scope": "All SQLite tables and schema, typed row multisets with accessible implicit rowids; registry relative paths and exact file bytes; exact provenance bytes. No table rows are serialized. SQLite WAL/checkpoint byte layout is deliberately not treated as logical content.",
    }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Local verification must not redirect")


def get_bytes(path, limit, timeout=5):
    require(path.startswith("/") and not path.startswith("//"), "Only local absolute URL paths are permitted")
    request = urllib.request.Request(ORIGIN + path, method="GET", headers={"Cache-Control": "no-cache", "Accept-Encoding": "identity"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        require(response.status == 200 and response.geturl() == ORIGIN + path, "Unexpected local GET response")
        value = response.read(limit + 1)
        require(len(value) <= limit, "Local GET exceeded its response bound")
        return value


def port_closed():
    # Both loopback families are checked. A timeout/other error does not prove closure.
    checked = []
    for family, address in ((socket.AF_INET, ("127.0.0.1", 4173)), (socket.AF_INET6, ("::1", 4173))):
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.settimeout(2)
            code = probe.connect_ex(address)
        require(code == errno.ECONNREFUSED, "Port 4173 is not conclusively closed on " + address[0])
        checked.append(address[0])
    return {"observed_at": now(), "port": 4173, "closed_loopbacks": checked}


def native_canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def native_boot():
    value = read(BOOT_RECEIPT)
    inventory = files_inventory(BOOTS)
    current_hash = digest(BOOT_RECEIPT)
    matching = [name for name, row in inventory.items() if row["sha256"] == current_hash]
    require(len(matching) == 1, "The current native boot must match exactly one immutable boot record")
    entries = {}
    for name, row in inventory.items():
        require(re.fullmatch(r"boot-[A-Za-z0-9TZ-]+\.json", name) is not None, "Noncanonical immutable boot filename")
        path = BOOTS / name
        require(path.stat().st_mode & 0o222 == 0, "Immutable boot history is writable")
        record = read(path)
        require(record.get("contract") in ("casepath.local-runtime-boot/2.0.0", "casepath.local-runtime-boot/2.1.0", "casepath.local-runtime-boot/2.2.0"), "Unknown native boot contract")
        require(record.get("boot_id") == Path(name).stem, "Native boot identity differs from its immutable filename")
        semantic = dict(record)
        stated = semantic.pop("receipt_sha256", None)
        require(stated == sha(native_canonical(semantic)), "Native boot semantic self-hash changed")
        prior = record.get("prior_boot_receipt_file_sha256")
        require(prior is None or isinstance(prior, str) and re.fullmatch(r"[0-9a-f]{64}", prior) is not None, "Invalid native prior-boot hash")
        require(row["sha256"] not in entries and digest(path) == row["sha256"], "Native history changed during inspection")
        entries[row["sha256"]] = record
    roots = [key for key, row in entries.items() if row.get("prior_boot_receipt_file_sha256") is None]
    require(len(roots) == 1, "Native boot lineage requires exactly one root")
    children = {}
    for key, row in entries.items():
        prior = row.get("prior_boot_receipt_file_sha256")
        if prior is not None:
            require(prior in entries, "Native boot predecessor is missing")
            children.setdefault(prior, []).append(key)
    chain = [roots[0]]
    while children.get(chain[-1]):
        successors = children[chain[-1]]
        require(len(successors) == 1 and successors[0] not in chain, "Native boot history fork or cycle")
        chain.append(successors[0])
    require(set(chain) == set(entries) and current_hash == chain[-1], "Current native boot is not the unique complete history tip")
    require(value == entries[current_hash], "Current native boot changed while inspected")
    return {"current_sha256": current_hash, "current_bytes": BOOT_RECEIPT.stat().st_size,
            "current_immutable_file": matching[0], "inventory": inventory,
            "inventory_sha256": sha(encoded(inventory)), "history_count": len(inventory), "record": value}


def validate_boot_source(boot, expected, manifest_hash, launcher_hash):
    value = boot["record"]
    source, runtime, process = value["source"], value["runtime"], value["process"]
    require(value["contract"] == "casepath.local-runtime-boot/2.2.0" and value["url"] == ORIGIN + "/", "Unexpected current native boot contract/origin")
    require(value["topology"] == "single_fastapi_same_origin_static_api_and_in_process_worker", "Unexpected native topology")
    require(source["git_head"] == expected and source["git_branch"] == OLD_BRANCH and source["repository"] == str(OLD_ROOT), "Native boot source/workspace mismatch")
    require(all(source[key] == manifest_hash for key in ("source_manifest_before_child_sha256", "source_manifest_file_sha256", "source_manifest_after_ready_sha256")), "Native boot source manifest differs from the sealed source")
    capsule = RUNTIME / "source-capsules" / manifest_hash
    require(source["execution_root"] == str(capsule) and source["source_capsule_receipt_file_sha256"] == digest(capsule / "CAPSULE_RECEIPT.json"), "Native execution capsule identity changed")
    require(value["launcher"]["path"] == "bin/casepath" and value["launcher"]["sha256"] == launcher_hash == digest(capsule / "bin/casepath"), "Native launcher does not match sealed source")
    require(runtime["data_root"] == str(DATA) and runtime["database_path"] == str(DATA / "casepath.db") and
            runtime["artifact_registry_path"] == str(DATA / "artifact-registry"), "Native boot uses a different data root")
    require(runtime["data_root_provenance_file_sha256"] == digest(DATA / "DATA_ROOT_PROVENANCE.json"), "Native boot provenance differs from the original store")
    require(type(process["pid"]) is int and process["pid"] > 0 and process["listener_owner_pid"] == process["pid"] and
            process["workers"] == 1 and process["cwd"] == str(OLD_ROOT), "Invalid native serving-process identity")
    env = value["environment"]
    require(env["provider_credential_names_present"] == [] and env["values"]["CASEPATH_MODEL_MODE"] == "deterministic_reference" and
            env["values"]["CASEPATH_SOURCE_COMMIT"] == expected, "Native boot does not attest a credential-free deterministic source")
    attest = value["attestation"]
    require(attest["credential_configured"] is False and attest["model_ledger_records"] == 0 and attest["model_ledger_network_calls"] == 0 and
            attest["source_reverified_after_ready"] is True and attest["workspace_authority"] == "claim_loop_events", "Native readiness attestation is not complete")
    closure = value["runtime_closure"]
    require(closure["phase_closure_equality"] is True and
            [row["phase"] for row in closure["phases"]] == ["after_sync", "before_child", "after_ready"] and
            all(row["closure_sha256"] == closure["baseline_closure_sha256"] for row in closure["phases"]), "Native runtime closure did not remain equal through startup")


def health(expected, timeout=5):
    raw = get_bytes("/healthz", 1024 * 1024, timeout)
    value = json.loads(raw)
    require(isinstance(value, dict) and value.get("status") == "ok", "Local health is not ready")
    require(value.get("source_commit") == expected and value.get("source_commit_aligned") is True and value.get("source_commit_conflict") is False, "Local health reports an unaligned or different source")
    require(value.get("model_mode") == value.get("runtime_profile") == "deterministic_reference" and value.get("model") is None, "Local model mode is not deterministic_reference")
    runtime = value.get("agentic_runtime", {})
    require(all(runtime.get(key) == "deterministic_reference" for key in ("profile", "execution_mode", "authority_mode", "implementation")), "Live runtime is not deterministic")
    safety = runtime.get("safety", {})
    require(safety.get("credential_configured") is False and safety.get("external_tracing") is False, "Live runtime has credentials or external tracing configured")
    keys = ("status", "source_commit", "source_commit_aligned", "source_commit_conflict", "model_mode", "runtime_profile", "model")
    return {"observed_at": now(), "response_sha256": sha(raw), "bytes": len(raw),
            "identity": {key: value[key] for key in keys}, "credential_configured": False, "external_tracing": False}


def readiness_and_ledger(timeout=5):
    ready_raw = get_bytes("/readyz", 1024 * 1024, timeout)
    ready = json.loads(ready_raw)
    require(ready.get("status") == "ready" and ready.get("model_budget", {}).get("credential_configured") is False, "Native readiness is not credential-free")
    ledger_raw = get_bytes("/api/model-ledger", 1024 * 1024, timeout)
    ledger = json.loads(ledger_raw)
    require(ledger.get("summary", {}).get("network_calls") == 0 and ledger.get("items") == [], "Local model ledger is not empty with zero network calls")
    return {"readiness": {"response_sha256": sha(ready_raw), "bytes": len(ready_raw), "status": "ready", "credential_configured": False},
            "model_ledger": {"response_sha256": sha(ledger_raw), "bytes": len(ledger_raw), "records": 0, "network_calls": 0}}


def listener_identity(boot):
    raw = subprocess.check_output(["/usr/sbin/lsof", "-nP", "-iTCP:4173", "-sTCP:LISTEN", "-t"], env=environment(), timeout=5, stderr=subprocess.PIPE)
    require(all(re.fullmatch(r"[0-9]+", line) for line in raw.decode("ascii").splitlines()), "Unexpected listener PID output")
    pids = {int(line) for line in raw.decode("ascii").splitlines()}
    pid = boot["record"]["process"]["pid"]
    require(pids == {pid}, "Native receipt does not identify the actual 4173 listener")
    ancestors = [pid]
    for _ in range(64):
        raw = subprocess.check_output(["/bin/ps", "-p", str(ancestors[-1]), "-o", "ppid="], env=environment(), timeout=5, stderr=subprocess.PIPE)
        parent = int(raw.decode("ascii").strip())
        if parent <= 1:
            break
        require(parent not in ancestors, "Process ancestry cycle")
        ancestors.append(parent)
    else:
        raise RuntimeError("Process ancestry exceeds its bound")
    return {"listener_pid": pid, "ancestor_pids": ancestors, "observed_at": now(), "port": 4173}


def terminal_candidates(value, session=None):
    """Read structured tool envelopes, never infer state from prose/log lines."""
    found = []
    if isinstance(value, dict):
        if isinstance(value.get("sessionId"), str) and (session is None or value["sessionId"] == session):
            found.append(value)
        for key in ("result", "structuredContent"):
            if key in value:
                found.extend(terminal_candidates(value[key], session))
        for child in value.get("content", []) if isinstance(value.get("content"), list) else []:
            if isinstance(child, dict) and child.get("type") == "text" and isinstance(child.get("text"), str):
                try:
                    found.extend(terminal_candidates(json.loads(child["text"]), session))
                except json.JSONDecodeError:
                    pass
    elif isinstance(value, list):
        for child in value:
            found.extend(terminal_candidates(child, session))
    return found


def stopped_receipt(path, snapshot_path, prior_ancestors):
    path = safe_regular(path)
    value = read(path)
    require(value.get("contract") == "casepath.standard-promotion-stop/1", "Wrong stop evidence contract")
    require(value.get("snapshot_sha256") == digest(snapshot_path), "Stop evidence is not bound to this snapshot")
    stopped = terminal_candidates(value.get("stop_response"), OLD_SESSION)
    terminal = terminal_candidates(value.get("terminal_response"), OLD_SESSION)
    require(stopped and all(row.get("terminated") is True for row in stopped), "Actual Commander stop result is missing")
    signals = ("SIGTERM", "TERM", "SIGINT", "INT", "SIGKILL", "KILL", 15, 2, 9)
    def explicit_signal(row):
        return {key: row[key] for key in ("signal", "exitSignal", "terminationSignal")
                if key in row and type(row[key]) in (str, int) and row[key] in signals}
    def terminal_exit(row):
        return type(row.get("exitCode")) is int or (row.get("exitCode") is None and bool(explicit_signal(row)))
    require(terminal and all(row.get("state") in ("completed", "terminated", "failed") and terminal_exit(row) for row in terminal), "Actual Commander terminal exit or terminating signal is missing")
    pids = {row.get("pid") for row in [*stopped, *terminal]}
    require(len(pids) == 1 and all(type(pid) is int and pid > 0 and pid in prior_ancestors for pid in pids), "Commander supervisor is not in the snapshotted serving-process ancestry")
    return {"path": str(path), "sha256": digest(path), "sessionId": OLD_SESSION,
            "supervisor_pid": next(iter(pids)),
            "terminal_states": sorted({row["state"] for row in terminal}),
            "exit_codes": [row.get("exitCode") for row in terminal],
            "explicit_signals": [explicit_signal(row) for row in terminal], "actual_structured_stop_and_terminal": True}


def running_receipt(path):
    path = safe_regular(path)
    rows = terminal_candidates(read(path))
    require(rows and all(row.get("state") == "running" for row in rows), "Actual running Commander result is missing")
    sessions = {row["sessionId"] for row in rows}
    require(len(sessions) == 1 and OLD_SESSION not in sessions and all(sessions), "A distinct new Commander session is required")
    require(all(type(row.get("pid")) is int and row["pid"] > 0 for row in rows), "Invalid Commander process identity")
    require(len({row["pid"] for row in rows}) == 1, "Conflicting Commander process identities")
    return {"path": str(path), "sha256": digest(path), "sessionId": next(iter(sessions)),
            "pids": sorted({row["pid"] for row in rows if "pid" in row}), "state": "running"}


def release_prerequisites(candidate):
    guard_path = NS / "require_completed_gate.py"
    spec = importlib.util.spec_from_file_location("_standard_promotion_completed_gate", safe_regular(guard_path))
    require(spec is not None and spec.loader is not None, "Gate validator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(Path(module.__file__).resolve() == guard_path and module.NS.resolve() == NS, "Wrong gate namespace")
    completed = module.require_completed_gate(BASE, candidate)
    acceptance_path = BASE / "published-acceptance-sequence.json"
    acceptance = read(acceptance_path)
    require(acceptance.get("status") == "passed" and acceptance.get("source_commit") == candidate, "Published acceptance has not passed for this source")
    require(isinstance(acceptance.get("stages"), list) and acceptance["stages"], "Published acceptance contains no stages")
    for stage in acceptance["stages"]:
        require(stage.get("status") == "completed" and stage.get("exit_code") == 0, "A published acceptance stage is incomplete")
        require(digest(stage["log"]) == stage["log_sha256"], "Published acceptance log changed")
        for artifact in stage.get("artifacts", []):
            require(digest(artifact["path"]) == artifact["sha256"], "Published acceptance artifact changed")
    existing_binding_path = BASE / "helper-acceptance-binding.json"
    require(acceptance["helper_binding_sha256"] == digest(existing_binding_path), "Existing publication helper binding changed")
    return {"completed_gate": completed, "gate_guard_sha256": digest(guard_path),
            "published_acceptance_sha256": digest(acceptance_path), "publication_helper_binding_sha256": digest(existing_binding_path)}


def command(stage, name, argv, cwd, candidate):
    # No kill/signal/server launch. The finite child stays in the Commander's
    # inherited process group, so the parent retains ownership if interrupted.
    log = stage / (name + ".log")
    started = {"command": argv, "cwd": str(cwd), "started_at": now(), "log": str(log),
               "environment_keys": sorted(environment(candidate)), "inherits_caller_process_group": True}
    write_new(stage / (name + "-requested.json"), started)
    with log.open("xb") as output:
        child = subprocess.Popen(argv, cwd=cwd, env=environment(candidate), stdin=subprocess.DEVNULL,
                                 stdout=output, stderr=subprocess.STDOUT)
        write_new(stage / (name + "-started.json"), {**started, "pid": child.pid})
        code = child.wait()
    result = {**started, "pid": child.pid, "exit_code": code, "finished_at": now(), "log_sha256": digest(log)}
    write_new(stage / (name + "-completed.json"), result)
    require(code == 0, "Command failed; preserve its attempt log: " + name)
    return result


def safe_boot(boot):
    # The immutable inventory contains only relative boot filenames and hashes.
    # Native identity fields are selected explicitly after validation below.
    value = boot["record"]
    return {**{key: item for key, item in boot.items() if key != "record"},
            "identity": {"boot_id": value["boot_id"], "ready_at_utc": value["ready_at_utc"],
                         "semantic_receipt_sha256": value["receipt_sha256"],
                         "prior_boot_receipt_file_sha256": value["prior_boot_receipt_file_sha256"],
                         "source_commit": value["source"]["git_head"],
                         "source_manifest_sha256": value["source"]["source_manifest_file_sha256"],
                         "launcher_sha256": value["launcher"]["sha256"],
                         "listener_pid": value["process"]["listener_owner_pid"],
                         "runtime_closure_sha256": value["runtime_closure"]["baseline_closure_sha256"]}}


def unchanged_data(expected):
    observed = data_fingerprint()
    require(observed == expected, "Original database/registry/provenance fingerprint changed")
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("snapshot", "source", "verify"))
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--stop-receipt", type=Path)
    parser.add_argument("--running-receipt", type=Path)
    parser.add_argument("--readiness-seconds", type=int, default=90)
    args = parser.parse_args()
    require(__debug__ and sys.flags.dont_write_bytecode and sys.flags.isolated, "Use python -I -B without -O")
    require(not Path(sys.prefix).resolve().is_relative_to(RUNTIME.resolve()), "Do not import from or run the old runtime Python")
    require(Path(__file__).resolve() == NS / "promote_standard_workspace.py", "Install the helper in the new namespace")
    require(re.fullmatch(r"[a-z][a-z0-9-]{0,79}", args.attempt) is not None, "Invalid attempt identifier")
    require(5 <= args.readiness_seconds <= 180, "Readiness wait must be bounded to 5-180 seconds")
    require((args.mode == "source") == (args.stop_receipt is not None), "Only source mode requires --stop-receipt")
    require((args.mode == "verify") == (args.running_receipt is not None), "Only verify mode requires --running-receipt")
    binding_path = NS / "source-binding.json"
    binding = read(binding_path)
    candidate = binding["source_commit"]
    require(isinstance(candidate, str) and re.fullmatch(r"[0-9a-f]{40}", candidate) is not None and candidate != OLD_SHA, "Invalid candidate source")
    source_binding_hash = digest(binding_path)
    helper_hash = digest(Path(__file__))
    checkout(NEW_ROOT, candidate)
    environment(candidate)
    PROMOTIONS.mkdir(exist_ok=True)
    require(not PROMOTIONS.is_symlink(), "Promotion namespace must not be symlinked")
    # Lock only the new helper namespace. No old workspace/history lock or file is changed.
    with (PROMOTIONS / "promotion.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt = PROMOTIONS / args.attempt
        if args.mode == "snapshot":
            attempt.mkdir()
            write_new(attempt / "helper-binding.json", {
                "contract": "casepath.standard-promotion-helper/1", "created_at": now(),
                "helper_path": str(Path(__file__)), "helper_sha256": helper_hash,
                "source_binding_sha256": source_binding_hash, "source_commit": candidate,
                "old_source_commit": OLD_SHA, "old_root": str(OLD_ROOT), "data_root": str(DATA),
                "old_commander_session": OLD_SESSION, "publication_helper_binding_modified": False,
            })
        require(attempt.is_dir() and not attempt.is_symlink(), "Start with a fresh snapshot attempt")
        helper_binding = read(attempt / "helper-binding.json")
        require(helper_binding["helper_sha256"] == helper_hash and helper_binding["source_binding_sha256"] == source_binding_hash and
                helper_binding["source_commit"] == candidate, "This attempt was bound to a different helper/source")
        stage = attempt / args.mode
        stage.mkdir()  # Never rerun/overwrite an existing stage, even if it failed.
        start = {"contract": "casepath.standard-promotion/1", "mode": args.mode,
                 "source_commit": candidate, "old_source_commit": OLD_SHA, "started_at": now(),
                 "helper_binding_sha256": digest(attempt / "helper-binding.json"),
                 "source_binding_sha256": source_binding_hash, "helper_sha256": helper_hash,
                 "server_stop_or_launch_by_helper": False, "seed_or_replay_by_helper": False}
        write_new(stage / "started.json", start)
        try:
            result = execute_mode(args, attempt, stage, candidate, binding)
            checkout(NEW_ROOT, candidate)
            require(digest(binding_path) == source_binding_hash and digest(Path(__file__)) == helper_hash, "Source/helper binding changed during promotion")
            record = {**start, **result, "status": "passed", "finished_at": now()}
            write_new(stage / "receipt.json", record)
            print(json.dumps({"status": "passed", "mode": args.mode, "source_commit": candidate,
                              "receipt": str(stage / "receipt.json"), "receipt_sha256": digest(stage / "receipt.json")}), flush=True)
        except BaseException as error:
            # Do not echo arbitrary database/HTTP payloads or command log tails.
            write_new(stage / "failure.json", {**start, "status": "failed", "finished_at": now(),
                      "error_type": type(error).__name__, "reason": str(error) if isinstance(error, RuntimeError) else "See preserved stage evidence; no private payload is serialized."})
            raise


def execute_mode(args, attempt, stage, candidate, binding):
    if args.mode == "snapshot":
        prior_git = checkout(OLD_ROOT, OLD_SHA, OLD_BRANCH)
        initial = data_fingerprint()
        boot = native_boot()
        validate_boot_source(boot, OLD_SHA, digest(OLD_ROOT / "casepath/source-manifest.json"), digest(OLD_ROOT / "bin/casepath"))
        live_health = health(OLD_SHA)
        ready = readiness_and_ledger()
        listener = listener_identity(boot)
        unchanged_data(initial)
        require(safe_boot(native_boot()) == safe_boot(boot), "Boot changed during snapshot")
        require(checkout(OLD_ROOT, OLD_SHA, OLD_BRANCH) == prior_git, "Old workspace changed during snapshot")
        return {"git": prior_git, "health": live_health, **ready, "data": initial,
                "native_boot": safe_boot(boot), "listener": listener,
                "known_commander_session": OLD_SESSION, "get_only": True,
                "repeated_full_fingerprint_equal": True}

    snapshot_path = attempt / "snapshot/receipt.json"
    snapshot = read(snapshot_path)
    require(snapshot.get("status") == "passed" and snapshot.get("mode") == "snapshot" and snapshot.get("source_commit") == candidate and
            snapshot.get("old_source_commit") == OLD_SHA and snapshot.get("helper_binding_sha256") == digest(attempt / "helper-binding.json"), "A passed matching snapshot is required")
    snapshot_reference = {"path": str(snapshot_path), "sha256": digest(snapshot_path)}
    proof = release_prerequisites(candidate)
    initial = snapshot["data"]
    old_boot = snapshot["native_boot"]

    if args.mode == "source":
        stop = stopped_receipt(args.stop_receipt, snapshot_path, snapshot["listener"]["ancestor_pids"])
        closure = port_closed()
        require(checkout(OLD_ROOT, OLD_SHA, OLD_BRANCH) == snapshot["git"], "Old workspace no longer matches the snapshot")
        unchanged_data(initial)
        require(safe_boot(native_boot()) == old_boot, "Native history changed before source promotion")
        require(git(NEW_ROOT, "merge-base", OLD_SHA, candidate) == OLD_SHA, "New candidate is not a fast-forward of the old source")
        write_new(stage / "prerequisites.json", {"snapshot_receipt": snapshot_reference, "stop_evidence": stop,
                  "port_closed": closure, "release": proof, "original_data_matches": True, "native_history_matches": True})
        port_closed()
        fetch = command(stage, "fetch", ["/usr/bin/git", "-c", "protocol.allow=never", "-c", "protocol.file.allow=always",
                        "-c", "core.hooksPath=/dev/null", "fetch", "--no-tags", "--no-recurse-submodules", str(NEW_ROOT), candidate], OLD_ROOT, candidate)
        require(git(OLD_ROOT, "rev-parse", "FETCH_HEAD") == candidate and git(OLD_ROOT, "merge-base", OLD_SHA, candidate) == OLD_SHA, "Local fetch did not import the exact fast-forward candidate")
        checkout(OLD_ROOT, OLD_SHA, OLD_BRANCH)
        port_closed()
        advance = command(stage, "fast-forward", ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-c", "submodule.recurse=false",
                          "merge", "--ff-only", "--no-edit", "--no-autostash", candidate], OLD_ROOT, candidate)
        promoted = checkout(OLD_ROOT, candidate, OLD_BRANCH)
        require(digest(OLD_ROOT / "bin/casepath") == digest(NEW_ROOT / "bin/casepath"), "Official launcher differs from the sealed candidate")
        require(digest(OLD_ROOT / "casepath/source-manifest.json") == binding["source_manifest_sha256"], "Promoted source manifest mismatch")
        port_closed()
        prepared = command(stage, "official-prepare", ["./bin/casepath", "prepare"], OLD_ROOT, candidate)
        require(checkout(OLD_ROOT, candidate, OLD_BRANCH) == promoted, "Prepare changed sealed source")
        unchanged_data(initial)
        require(safe_boot(native_boot()) == old_boot, "Prepare altered existing native boot history")
        after_closed = port_closed()
        require(release_prerequisites(candidate) == proof, "Release evidence changed during promotion")
        require(digest(args.stop_receipt) == stop["sha256"] and digest(snapshot_path) == snapshot_reference["sha256"], "Promotion inputs changed")
        return {"snapshot_receipt": snapshot_reference, "stop_evidence": stop, "release": proof,
                "git": promoted, "commands": [fetch, advance, prepared],
                "original_data_unchanged": True, "native_boot_unchanged": True,
                "port_closed_after_prepare": after_closed, "official_prepare_exit_code": 0,
                "next_action": "Parent starts ./bin/casepath dev in this original workspace under a new owned Commander session, then runs verify."}

    source_path = attempt / "source/receipt.json"
    source = read(source_path)
    require(source.get("status") == "passed" and source.get("mode") == "source" and source.get("source_commit") == candidate and
            source.get("snapshot_receipt") == snapshot_reference and source.get("helper_binding_sha256") == digest(attempt / "helper-binding.json"), "A passed matching source/prepare stage is required")
    require(source.get("original_data_unchanged") is True and source.get("native_boot_unchanged") is True and
            source.get("official_prepare_exit_code") == 0 and source.get("release") == proof, "Source promotion did not preserve its prerequisites")
    require([row["command"][-1] for row in source["commands"]] == [candidate, candidate, "prepare"], "Unexpected source promotion command sequence")
    for row in source["commands"]:
        require(row["exit_code"] == 0 and digest(row["log"]) == row["log_sha256"], "Source promotion log/exit changed")
    require(digest(source["stop_evidence"]["path"]) == source["stop_evidence"]["sha256"], "Original Commander stop evidence changed")
    source_reference = {"path": str(source_path), "sha256": digest(source_path)}
    running = running_receipt(args.running_receipt)
    checkout(OLD_ROOT, candidate, OLD_BRANCH)
    deadline = time.monotonic() + args.readiness_seconds
    count = 0
    with (stage / "readiness-observations.jsonl").open("x", encoding="utf-8") as observations:
        while True:
            count += 1
            try:
                remaining = deadline - time.monotonic()
                require(remaining > 0, "Readiness deadline exceeded")
                timeout = min(2, remaining)
                live_health = health(candidate, timeout)
                ready = readiness_and_ledger(timeout)
                boot = native_boot()
                validate_boot_source(boot, candidate, binding["source_manifest_sha256"], digest(NEW_ROOT / "bin/casepath"))
                listener = listener_identity(boot)
                require(running["pids"][0] in listener["ancestor_pids"], "New Commander supervisor is not an ancestor of the native serving process")
                observations.write(json.dumps({"attempt": count, "observed_at": now(), "status": "ready"}) + "\n")
                observations.flush()
                break
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
                observations.write(json.dumps({"attempt": count, "observed_at": now(), "status": "not_ready", "error_type": type(error).__name__}) + "\n")
                observations.flush()
                require(time.monotonic() < deadline, "Readiness did not complete within the bounded wait; inspect preserved evidence")
                time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    new_boot = safe_boot(boot)
    require(new_boot["identity"]["prior_boot_receipt_file_sha256"] == old_boot["current_sha256"], "New native boot does not directly extend the exact old receipt")
    require(new_boot["identity"]["boot_id"] != old_boot["identity"]["boot_id"] and new_boot["current_sha256"] != old_boot["current_sha256"], "Native boot did not advance")
    require(all(new_boot["inventory"].get(name) == row for name, row in old_boot["inventory"].items()), "An old immutable boot file changed or disappeared")
    added = sorted(set(new_boot["inventory"]) - set(old_boot["inventory"]))
    require(added == [new_boot["current_immutable_file"]] and new_boot["history_count"] == old_boot["history_count"] + 1, "Expected exactly one appended native boot receipt")
    unchanged_data(initial)
    assets_dir = stage / "assets"
    assets_dir.mkdir()
    assets = []
    for name in ASSETS:
        expected = digest(NEW_ROOT / "casepath/assets" / name)
        require(digest(OLD_ROOT / "casepath/assets" / name) == expected, "Promoted asset differs from sealed source")
        raw = get_bytes("/assets/" + name, 8 * 1024 * 1024)
        require(sha(raw) == expected, "Served asset differs from current sealed source: " + name)
        target = assets_dir / name
        with target.open("xb") as output:
            output.write(raw)
        assets.append({"path": str(target), "url": ORIGIN + "/assets/" + name, "sha256": sha(raw), "bytes": len(raw),
                       "source_path": str(NEW_ROOT / "casepath/assets" / name), "source_sha256": expected})
    deployment_raw = get_bytes("/deployment.json", 1024 * 1024)
    deployment = json.loads(deployment_raw)
    require(deployment.get("source_commit") == candidate and deployment.get("alignment_eligible") is True, "Served static deployment is not the promoted source")
    require(sha(deployment_raw) == digest(OLD_ROOT / "casepath-public/deployment.json"), "Served deployment bytes differ from the native static build")
    unchanged_data(initial)
    require(safe_boot(native_boot()) == new_boot, "Native boot changed during GET-only verification")
    require(listener_identity(boot)["listener_pid"] == listener["listener_pid"], "Native listener changed during verification")
    promoted = checkout(OLD_ROOT, candidate, OLD_BRANCH)
    require(release_prerequisites(candidate) == proof, "Release evidence changed during verification")
    require(digest(args.running_receipt) == running["sha256"] and digest(source_path) == source_reference["sha256"] and
            digest(snapshot_path) == snapshot_reference["sha256"], "Verification inputs changed")
    return {"snapshot_receipt": snapshot_reference, "source_receipt": source_reference, "release": proof,
            "commander_running": running, "git": promoted, "health": live_health, **ready,
            "readiness_observations": {"path": str(stage / "readiness-observations.jsonl"), "sha256": digest(stage / "readiness-observations.jsonl"), "attempts": count},
            "listener": listener, "native_boot": new_boot, "added_immutable_boot": added[0],
            "data_fingerprint_sha256": sha(encoded(initial)), "data_table_counts": {name: row["table_count"] for name, row in initial["databases"].items()},
            "assets": assets, "deployment": {"response_sha256": sha(deployment_raw), "bytes": len(deployment_raw), "source_commit": candidate},
            "boot_lineage_advanced": True, "prior_boot_files_unchanged": True,
            "original_data_unchanged": True, "repeated_full_fingerprint_equal": True,
            "get_only": True, "qualified_human_approval": "pending; this is engineering release verification"}


if __name__ == "__main__":
    main()
