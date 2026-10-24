"""Serve the existing owned engineering QA store from the released code capsule.

Install beside verify_promoted_review_qa.py in commander-demo-polish/release.
The parent first takes that verifier's checkpoint and stops only its recorded
Commander session. This launcher never stops a process, copies a store, seeds
claims, or starts/resumes/replays investigation work. Importing it is read-only.
Invoke with Python -B; assertions must remain enabled.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Assertions required; do not use Python -O")

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import socket
import sqlite3
import sys

sys.dont_write_bytecode = True
ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024")
NS = ROOT / ".runtime/commander-demo-polish"
BASE = NS / "release"
OLD_ROOT = ROOT.parent / "casepath-commander-northstar-20261024"
OLD_NS = OLD_ROOT / ".runtime/commander-northstar"
DEMO = OLD_NS / "engineering-demo"
DATA = DEMO / "data"
ORIGINAL_QA = OLD_NS / "sealed-browser"
SHA = "4864e7347c299bf1b580a5b35667635bc1c47f15"
PREVIOUS = "b20685d1670b33b941b1bfcb902638a879c01b93"
MANIFEST = "4bbdb036e69777937f19647f55fca80896ad96ae971a43928220bf93a5ddedef"
ORIGINAL_QA_SHA = "83517c45d484e4623ca1744fdf209595196f0aca3e4f8d6c761778e787111f36"
INSTANCE = "c249a178e95272f914805278"
PREVIOUS_PID = 40476
PREVIOUS_SESSION = "cp-ns-20261024-engineering-demo-resumed-4194"
PREVIOUS_BOOT = "0c9e89e863ce5f24fb840cd4"
CASES = ("clm_f69b1747447bc221", "clm_0e538990cc6ba7ef")
HOST, PORT = "127.0.0.1", 4194
LABEL = "Isolated engineering demo — no qualified approval is asserted by this launcher"
LAUNCHER = BASE / "resume_promoted_review_qa.py"
VERIFIER = BASE / "verify_promoted_review_qa.py"
PROMOTIONS = NS / "engineering-demo-promotions"
STATIC_PATHS = (
    "index.html", "source-manifest.json", "assets/app.js", "assets/styles.css",
    "assets/review-northstar-v1.js", "assets/review-northstar-v1.css",
    "assets/autonomous-workspace-v1.js", "assets/autonomous-workspace-v1.css",
    "assets/autonomous-presentation-v1.js", "assets/autonomous-entry-v1.js",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def canonical_hash(value):
    def encode(item):
        if isinstance(item, bytes):
            return {"sqlite_blob_hex": item.hex()}
        raise TypeError(type(item).__name__)
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, default=encode).encode()
    return hashlib.sha256(raw).hexdigest()


def plain_path(path, anchor):
    path, anchor = Path(path), Path(anchor)
    assert path.is_absolute() and path.is_relative_to(anchor), str(path)
    assert ".." not in path.parts
    for candidate in (path, *path.parents):
        assert not candidate.is_symlink(), str(candidate)
        if candidate == anchor:
            break
    return path


def evidence_path(path):
    result = plain_path(Path(path), NS)
    assert result.is_file(), str(result)
    return result


def write_new(path, value):
    path = plain_path(path, NS)
    assert path.parent.is_dir() and not path.exists(), str(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def inventory(folder, exclude=()):
    folder = Path(folder)
    assert folder.is_dir() and not folder.is_symlink(), str(folder)
    result = {}
    for path in sorted(folder.rglob("*")):
        assert not path.is_symlink(), str(path)
        relative = path.relative_to(folder).as_posix()
        if path.is_file() and relative not in exclude:
            result[relative] = digest(path)
        else:
            assert path.is_dir() or path.is_file(), str(path)
    return result


def capsule_at(root, manifest_sha, *, count=None, receipt_sha=None):
    assert isinstance(manifest_sha, str) and len(manifest_sha) == 64
    assert all(char in "0123456789abcdef" for char in manifest_sha)
    capsule = plain_path(root / ".runtime/casepath-dev-v2/source-capsules" / manifest_sha, root)
    assert capsule.is_dir()
    manifest_path = plain_path(capsule / "casepath/source-manifest.json", capsule)
    assert digest(manifest_path) == manifest_sha
    receipt_path = plain_path(capsule / "CAPSULE_RECEIPT.json", capsule)
    if receipt_sha is not None:
        assert digest(receipt_path) == receipt_sha
    receipt = read(receipt_path)
    assert receipt["contract"] == "casepath.sealed-source-capsule/1.0.0"
    assert receipt["source_manifest_file_sha256"] == manifest_sha
    rows = read(manifest_path)["files"]
    assert receipt["source_file_count"] == len(rows)
    if count is not None:
        assert len(rows) == count
    assert receipt["static_file_count"] == 45
    assert len({row["path"] for row in rows}) == len(rows)
    for row in rows:
        relative = PurePosixPath(row["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        assert str(relative) == row["path"]
        path = plain_path(capsule / relative, capsule)
        assert path.is_file() and digest(path) == row["sha256"], row["path"]
    for relative in STATIC_PATHS:
        assert plain_path(capsule / "casepath" / relative, capsule).is_file()
    return capsule


def published_acceptance():
    """Validate the completed runner and its actual stage exits and bound output."""
    sequence_path = BASE / "published-acceptance-sequence.json"
    sequence = read(sequence_path)
    binding_path = BASE / "helper-acceptance-binding.json"
    binding = read(binding_path)
    assert sequence["source_commit"] == binding["source_commit"] == SHA
    assert sequence["status"] == "passed" and sequence["finished_at"]
    assert sequence["script_sha256"] == binding["acceptance_runner_sha256"] == digest(NS / "run_published_acceptance.py")
    assert sequence["helper_binding_sha256"] == digest(binding_path)
    for name, expected in binding["helpers"].items():
        assert digest(evidence_path(BASE / name)) == expected, name
    soak_dir = BASE / ("published-soak-" + SHA[:8])
    browser_dir = BASE / ("published-browser-" + SHA[:8])
    expected = {
        "soak": [soak_dir / "summary.json", soak_dir / "receipts.jsonl"],
        "browser": [browser_dir / "summary.json", browser_dir / "published-verification.json"],
        "image": [BASE / "public-image-verified.json"],
        "readback": [BASE / "readback-after.json"],
        "verify_readback": [BASE / "readback-verified.json"],
    }
    assert [stage["name"] for stage in sequence["stages"]] == list(expected)
    for stage in sequence["stages"]:
        assert stage["status"] == "completed" and stage["exit_code"] == 0
        assert isinstance(stage["pid"], int) and stage["pid"] > 0 and stage["finished_at"]
        log = BASE / ("published-" + stage["name"] + "-command.log")
        assert stage["log"] == str(log) and stage["log_sha256"] == digest(log)
        assert [item["path"] for item in stage["artifacts"]] == [str(path) for path in expected[stage["name"]]]
        for item in stage["artifacts"]:
            assert digest(evidence_path(item["path"])) == item["sha256"]
    soak = read(soak_dir / "summary.json")
    assert soak["source_commit"] == SHA and soak["passed"] is True
    assert soak["observed_soak_requests"] == soak["successful_soak_requests"] == 300
    assert soak["soak_http_503_count"] == soak["runner_retries"] == soak["provider_calls_initiated"] == 0
    assert soak["verification_requests"] == 7
    browser = read(browser_dir / "summary.json")
    assert [row["rendered"] for row in browser["windows"]] == [18, 9]
    for row in browser["windows"]:
        assert row["commit_ok"] and row["rendered"] == row["total"]
        assert not any(row[key] for key in ("identity_failures", "errors", "writes", "overflow"))
        assert row["served_assets_verified"] >= 11 and row["required_static_assets_verified"] > 0
        assert row["review_assets_verified"] == 2
    assert browser["windows"][1]["mobile_document_rows"] > 0
    assert browser["windows"][1]["mobile_document_failures"] == 0
    assert browser["film"]["reached_end"] and browser["film"]["duration_ms"] == 88050
    final = read(BASE / "readback-verified.json")
    assert final["canonical_commit"] == final["api_commit"] == final["frontend_commit"] == SHA
    assert all(final[key] is True for key in ("primary_reads_verified", "collection_unchanged", "knowledge_unchanged", "ledger_unchanged", "read_only"))
    assert final["writable"] is False and final["storage"] == "remote_primary"
    assert final["claims"] == 159 and final["provider_calls"] == 42
    assert final["original_nine_workflows"] == 9 and final["original_nine_calls"] == 18
    image = read(BASE / "public-image-verified.json")
    assert image["source_commit"] == SHA and image["passed"] and image["matches_sealed_original"]
    assert image["local_pillow"] == "13.0.0"
    return {"sequence_sha256": digest(sequence_path), "helper_binding_sha256": digest(binding_path)}


def release_context():
    assert LAUNCHER.resolve() == Path(__file__).resolve(), "Install this helper at NEW_NS/release"
    binding_path = NS / "source-binding.json"
    binding = read(binding_path)
    assert binding["source_commit"] == SHA and binding["source_manifest_sha256"] == MANIFEST
    assert binding["source_files"] == 1746
    # Preserve the authoritative verifier's own __file__ and ROOT calculation.
    path = NS / "require_completed_gate.py"
    spec = importlib.util.spec_from_file_location("casepath_demo_polish_authoritative_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    gate = module.require_completed_gate(BASE, SHA)
    acceptance = published_acceptance()
    capsule = capsule_at(ROOT, MANIFEST, count=1746)
    return {"capsule": capsule, "binding": binding,
            "proof": {"source_binding_sha256": digest(binding_path), "gate": gate,
                      "published_acceptance": acceptance,
                      "capsule_receipt_sha256": digest(capsule / "CAPSULE_RECEIPT.json")}}


def original_context():
    """The old Git HEAD may advance; only its immutable initial evidence is used."""
    for folder in (DEMO, DATA, ORIGINAL_QA):
        assert plain_path(folder, OLD_ROOT).is_dir()
    owner_path, copy_path = DEMO / "owner.json", DEMO / "data-copy.json"
    owner, copied = read(plain_path(owner_path, OLD_ROOT)), read(plain_path(copy_path, OLD_ROOT))
    assert owner["source_commit"] == copied["source_commit"] == PREVIOUS
    assert owner["host"] == HOST and owner["port"] == PORT and owner["instance_id"] == INSTANCE
    assert owner["data_root"] == copied["copied_data"] == str(DATA)
    assert copied["source_data"] == str(ORIGINAL_QA / "data") and copied["byte_identical_at_copy"] is True
    assert owner["qa_receipt_sha256"] == copied["qa_receipt_sha256"] == digest(ORIGINAL_QA / "receipt.json") == ORIGINAL_QA_SHA
    qa = read(ORIGINAL_QA / "receipt.json")
    assert qa["status"] == "passed" and not qa["browser_errors"] and not qa["unexpected_destinations"]
    assert tuple(qa["cases"]) == CASES
    applications = [row for row in qa["stages"] if row["stage"] == "later-case-application"]
    assert len(applications) == 1
    original_files = inventory(ORIGINAL_QA / "data")
    assert original_files == copied["files"], "Original QA data changed"
    old_capsule = capsule_at(OLD_ROOT, owner["source_manifest_sha256"], receipt_sha=owner["capsule_receipt_sha256"])
    assert owner["source_capsule"] == str(old_capsule)
    assert owner["launcher_sha256"] == digest(OLD_NS / "release/serve_existing_review_qa.py")
    for name in ("casepath.db", "work.sqlite3"):
        assert plain_path(DATA / name, OLD_ROOT).is_file()
    assert (DATA / "evidence").is_dir()
    return {"owner": owner, "old_capsule": old_capsule, "application": applications[0],
            "proof": {"initial_owner_sha256": digest(owner_path), "initial_copy_sha256": digest(copy_path),
                      "original_qa_receipt_sha256": ORIGINAL_QA_SHA,
                      "original_qa_inventory_sha256": canonical_hash(original_files),
                      "original_qa_file_count": len(original_files),
                      "original_capsule_manifest_sha256": owner["source_manifest_sha256"],
                      "original_capsule_receipt_sha256": owner["capsule_receipt_sha256"]}}


def database_snapshot(path):
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=15)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        schema = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        tables = {}
        for kind, name, _, _ in schema:
            if kind != "table":
                continue
            rows = connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall()
            tables[name] = {"rows": len(rows), "sha256": canonical_hash(sorted(rows, key=repr))}
        return {"schema_sha256": canonical_hash(schema), "tables": tables}
    finally:
        connection.close()


def data_fingerprints():
    databases = {name: database_snapshot(DATA / name) for name in ("casepath.db", "work.sqlite3")}
    assert "claim_loop_events" in databases["casepath.db"]["tables"]
    assert {"work_events", "work_runs"} <= databases["work.sqlite3"]["tables"].keys()
    sqlite_files = {name + suffix for name in databases for suffix in ("", "-wal", "-shm", "-journal")}
    return {"databases": databases, "other_files": inventory(DATA, exclude=sqlite_files)}


def view_fingerprint(value, claim, original):
    assert value["claim_decision_authorized"] is False
    graph = value["graph"]
    instances_present = "fragment_instances" in graph
    instances = graph.get("fragment_instances")
    assert not instances_present or isinstance(instances, list), "Fragment instances must be a list when present"
    if claim == CASES[1]:
        applied = original["application"]
        assert instances_present and isinstance(instances, list), "Receiving-case fragment instances are missing"
        assert applied["pin"] in instances, "Original exact fragment pin is missing"
        assert any(row["event_sha256"] == applied["event"]
                   and row["operation"]["type"] == "fragment.apply"
                   and row["operation"]["fragment_sha256"] == applied["pin"]["fragment_sha256"]
                   for row in value["history"]), "Original accepted application is missing"
    result = {key: value[key] for key in ("workspace_revision", "workspace_state_sha256", "view_sha256")}
    result.update(history_sha256=canonical_hash(value["history"]),
                  process_view_sha256=canonical_hash(value),
                  fragment_instances_present=instances_present,
                  fragment_instances_sha256=canonical_hash(instances),
                  claim_decision_authorized=False)
    return result


def commander_evidence(path, session_id, predicate, *, observation_field="state"):
    path = evidence_path(path)
    found = []
    def visit(value):
        if isinstance(value, dict):
            if value.get("sessionId") == session_id and observation_field in value:
                found.append(value)
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    visit(child)
                elif key == "text" and isinstance(child, str):
                    try:
                        visit(json.loads(child))
                    except json.JSONDecodeError:
                        pass
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(read(path))
    assert found, "No matching actual Commander observation: " + str(path)
    assert all(predicate(row) for row in found), "Commander observation does not establish the required state"
    assert all(row == found[0] for row in found), "Conflicting Commander observations"
    return found[0], {"path": str(path), "sha256": digest(path)}


def validate_current(current, health, original, release):
    assert current["source_commit"] == health["source_commit"] in (PREVIOUS, SHA)
    assert current["instance_id"] == health["instance_id"] == INSTANCE
    assert current["pid"] == health["pid"] and isinstance(health["pid"], int) and health["pid"] > 0
    assert current["boot_id"] == health["boot_id"]
    assert current["restart_id"] == health["restart_id"]
    assert current["host"] == HOST and current["port"] == PORT and current["data_root"] == str(DATA)
    assert current["initial_owner_sha256"] == original["proof"]["initial_owner_sha256"]
    assert current["initial_copy_sha256"] == original["proof"]["initial_copy_sha256"]
    assert health["status"] == "ok" and health["model_mode"] == "deterministic_reference"
    assert health["external_facts_enabled"] is False and health["isolated_writable_qa_store"] is True
    assert health["review_actions_at_startup"] == 0 and tuple(health["cases"]) == CASES
    assert current["copied_or_reset_data"] is False and current["seeded_or_replayed_work"] is False
    assert current["review_actions_at_startup"] == 0 and current["qualified_human_approval_asserted"] is False
    if current["source_commit"] == PREVIOUS:
        assert current["pid"] == PREVIOUS_PID and current["commander_session"] == PREVIOUS_SESSION
        assert current["boot_id"] == PREVIOUS_BOOT and health["startup_kind"] == "existing_owned_qa"
        assert current["source_manifest_sha256"] == original["owner"]["source_manifest_sha256"]
        assert current["launcher_sha256"] == digest(OLD_NS / "release/resume_existing_review_qa.py")
        return original["old_capsule"]
    assert current["contract"] == "casepath.owned-qa-source-promotion/1"
    assert current["source_manifest_sha256"] == MANIFEST
    assert current["source_capsule"] == str(release["capsule"])
    assert current["launcher_sha256"] == digest(LAUNCHER)
    assert health["startup_kind"] == "promoted_existing_owned_qa" and health["source_manifest_sha256"] == MANIFEST
    assert current["release_proof"] == release["proof"]
    return release["capsule"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--stop-receipt", type=Path, required=True)
    parser.add_argument("--terminal-receipt", type=Path, required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    assert args.session_id and len(args.session_id) <= 100
    assert all(char.isalnum() or char in "._:-" for char in args.session_id)
    release, original = release_context(), original_context()
    before_path = evidence_path(args.before)
    before = read(before_path)
    assert before["contract"] == "casepath.owned-qa-promotion-checkpoint/1" and before["status"] == "passed"
    assert before["target_source_commit"] == SHA and before["get_only"] is True
    assert before["verifier_sha256"] == digest(VERIFIER) and before["launcher_sha256"] == digest(LAUNCHER)
    assert before["release_proof"] == release["proof"] and before["original_proof"] == original["proof"]
    current_path = plain_path(DEMO / "current-server.json", OLD_ROOT)
    current_bytes = current_path.read_bytes()
    current = json.loads(current_bytes)
    assert hashlib.sha256(current_bytes).hexdigest() == before["current_server_sha256"]
    assert current == before["current_server"]
    validate_current(current, before["health"], original, release)
    prior_session, prior_pid = current["commander_session"], current["pid"]
    assert args.session_id != prior_session
    stopped, stop_proof = commander_evidence(args.stop_receipt, prior_session,
        lambda row: row.get("terminated") is True, observation_field="terminated")
    ended, terminal_proof = commander_evidence(args.terminal_receipt, prior_session, lambda row: row.get("state") in ("completed", "terminated", "failed"))
    for record in (stopped, ended):
        if "pid" in record:
            assert record["pid"] == prior_pid
    lock_path = plain_path(OLD_NS / "engineering-demo.lock", OLD_ROOT)
    assert lock_path.is_file(), "The existing ownership lock is required"
    lock = lock_path.open("r+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Bind before initializing the existing store; keep this same socket for Uvicorn.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((HOST, PORT))
    assert current_path.read_bytes() == current_bytes
    fingerprints = data_fingerprints()
    assert fingerprints == before["data_fingerprints"], "QA changed after checkpoint; take a fresh checkpoint"
    plain_path(PROMOTIONS, NS)
    PROMOTIONS.mkdir(mode=0o700, exist_ok=True)
    restart_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + str(os.getpid())
    attempt = PROMOTIONS / restart_id
    attempt.mkdir(mode=0o700)
    previous_path = attempt / "previous-current-server.json"
    with previous_path.open("xb") as output:
        output.write(current_bytes)
        output.flush()
        os.fsync(output.fileno())
    assert digest(previous_path) == before["current_server_sha256"]
    write_new(attempt / "before-snapshot.json", before)
    # A cleared environment cannot provide provider credentials to the app.
    environment = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin", "LANG": "C.UTF-8",
                   "LC_ALL": "C.UTF-8", "TZ": "UTC", "PYTHONDONTWRITEBYTECODE": "1",
                   "CASEPATH_AGENT_WORK_EXTERNAL_FACTS": "0", "CASEPATH_MODEL_MODE": "deterministic_reference",
                   "CASEPATH_SOURCE_COMMIT": SHA}
    if "HOME" in os.environ:
        environment["HOME"] = os.environ["HOME"]
    os.environ.clear()
    os.environ.update(environment)
    capsule = release["capsule"]
    sys.path[:0] = [str(capsule / "casepath-api"), str(capsule / "casepath-api/tests")]
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    from test_workspace_claim_loop_v1 import _system
    from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
    from casepath_api.claim_loop_router import create_claim_loop_router
    from casepath_api.workspace_packet_preview import create_packet_preview_router
    from casepath_api.causal_workspace_v1 import CausalWorkspaceService
    from casepath_api.agent_work.authority import ExistingCasePathAuthority
    from casepath_api.agent_work.service import AgentWorkService
    from casepath_api.agent_work.store import WorkStore
    from casepath_api.agent_work.api import create_agent_work_router
    from casepath_api.agent_desk_v1 import AgentDeskServiceV1, create_agent_desk_router
    storage, workspace, normal, facade = _system(DATA, corpus=PublicCorpus(default_workspace_corpus_root()))
    work = AgentWorkService(WorkStore(DATA / "work.sqlite3"), ExistingCasePathAuthority(lambda: workspace, lambda: facade),
                            facts_worker=None, external_configuration_status="disabled")
    desk = AgentDeskServiceV1(workspace, work)
    processes = CausalWorkspaceService(workspace)
    values = {claim: processes.view(claim) for claim in CASES}
    views = {claim: view_fingerprint(value, claim, original) for claim, value in values.items()}
    assert views == before["views"], "Current process views changed during promotion"
    assert data_fingerprints() == fingerprints, "Initialization changed the existing QA data"
    assert original_context()["proof"] == original["proof"]
    assert current_path.read_bytes() == current_bytes
    boot_id = secrets.token_hex(12)
    assert boot_id != current["boot_id"]
    record = {"contract": "casepath.owned-qa-source-promotion/1", "status": "initialization_verified",
              "source_commit": SHA, "source_manifest_sha256": MANIFEST, "source_capsule": str(capsule),
              "launcher_sha256": digest(LAUNCHER), "verifier_sha256": digest(VERIFIER),
              "release_proof": release["proof"], "original_proof": original["proof"],
              "initial_owner_sha256": original["proof"]["initial_owner_sha256"],
              "initial_copy_sha256": original["proof"]["initial_copy_sha256"], "qa_receipt_sha256": ORIGINAL_QA_SHA,
              "pid": os.getpid(), "instance_id": INSTANCE, "host": HOST, "port": PORT,
              "commander_session": args.session_id, "restart_id": restart_id, "boot_id": boot_id,
              "started_at": now(), "data_root": str(DATA), "previous_source_commit": current["source_commit"],
              "previous_pid": prior_pid, "previous_session": prior_session, "previous_boot_id": current["boot_id"],
              "checkpoint": {"path": str(before_path), "sha256": digest(before_path)},
              "previous_current_server": {"path": str(previous_path), "sha256": digest(previous_path)},
              "commander_stop": stop_proof, "commander_terminal": terminal_proof,
              "copied_or_reset_data": False, "seeded_or_replayed_work": False, "review_actions_at_startup": 0,
              "original_qa_data_preserved": True, "data_before": fingerprints, "data_after": data_fingerprints(),
              "views_before": before["views"], "views_after": views,
              "current_target_pins": values[CASES[1]]["graph"]["fragment_instances"],
              "qualified_human_approval_asserted": False, "label": LABEL}
    assert record["data_after"] == record["data_before"]
    app = FastAPI()
    app.include_router(create_packet_preview_router(lambda: workspace))
    app.include_router(create_agent_work_router(lambda: work))
    app.include_router(create_agent_desk_router(lambda: desk))
    app.include_router(create_claim_loop_router(lambda: storage, service_getter=lambda: normal,
        workspace_service_getter=lambda: workspace, workspace_loop_service_getter=lambda: facade,
        accepted_process_hook=lambda claim_id, result: desk.process_accepted(claim_id, result, dispatch=False)))
    @app.get("/healthz")
    def health():
        return {"status": "ok", "source_commit": SHA, "source_manifest_sha256": MANIFEST,
                "instance_id": INSTANCE, "label": LABEL, "restart_id": restart_id,
                "boot_id": boot_id, "pid": os.getpid(), "startup_kind": "promoted_existing_owned_qa",
                "model_mode": "deterministic_reference", "external_facts_enabled": False,
                "review_actions_at_startup": 0, "cases": list(CASES), "isolated_writable_qa_store": True}
    app.add_event_handler("shutdown", work.shutdown)
    app.mount("/", StaticFiles(directory=capsule / "casepath", html=True), name="review-ui")
    write_new(attempt / "owner.json", record)
    temporary = plain_path(DEMO / ("current-server-" + restart_id + ".next"), OLD_ROOT)
    with temporary.open("x") as output:
        json.dump(record, output, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    assert current_path.read_bytes() == current_bytes
    os.replace(temporary, current_path)
    print(json.dumps({"status": "initialization_verified", "source_commit": SHA, "pid": os.getpid(),
                      "instance_id": INSTANCE, "restart_id": restart_id, "owner_record": str(attempt / "owner.json")}), flush=True)
    # HTTP readiness is established only by the separate GET-only verifier.
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, access_log=False))
    try:
        server.run(sockets=[listener])
    finally:
        listener.close()
        lock.close()


if __name__ == "__main__":
    main()
