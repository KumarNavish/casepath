"""Record one fresh review-browser run after the completed full release gate.

Install at NEW_NS/run_sealed_browser_capture.py; run Python -I -B --session-id
with the actual enclosing Commander session. The parent must separately save
its completed terminal at release/commander-sealed-browser-terminal.json.
The failed gate-artifact adopter and all its evidence remain unchanged.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import signal
import struct
import subprocess

ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024")
NS = ROOT / ".runtime/commander-demo-polish"
BASE, OUT = NS / "release", NS / "sealed-browser"
SHA = "4864e7347c299bf1b580a5b35667635bc1c47f15"
RECEIPT, LOG = NS / "sealed-browser-command.json", NS / "sealed-browser-capture.log"
TEST = "casepath-qa/review-northstar-browser-v1.test.cjs"
FIXTURE = "casepath-qa/serve-review-northstar-fixture-v1.py"
PYTHON = ROOT / ".runtime/casepath-dev-v2/venv/bin/python"
ORIGIN = "Fresh standalone recording of the review browser suite after the completed full release gate"
ARTIFACTS = ("receipt.json", "source-review.png", "later-case-preview.png", "later-case-reuse.png", "mobile-review.png", "review-walkthrough.webm", "server.log")
active = None

def require(value, reason):
    if not value:
        raise RuntimeError(reason)

def now():
    return datetime.now(timezone.utc).isoformat()

def digest(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Expected a regular file: " + str(path))
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def read(path):
    return json.loads(Path(path).read_bytes())

def persist(first=False):
    target = RECEIPT if first else RECEIPT.with_suffix(".next")
    with target.open("x") as output:
        json.dump(record, output, indent=2); output.write("\n"); output.flush(); os.fsync(output.fileno())
    if not first:
        os.replace(target, RECEIPT)

def cleanup():
    global active
    child, active = active, None
    if child is None:
        return
    # Signal only the process group created by this helper, never a shared server.
    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait(timeout=5)
    record["owned_process_group_cleanup"] = {"process_group": child.pid, "child_reaped": True, "child_exit_code": child.returncode}

def interrupted(signum, _frame):
    raise SystemExit(128 + signum)

def main():
    global record, active
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    require(__debug__ and sys.flags.isolated and sys.flags.dont_write_bytecode, "Use Python -I -B without -O")
    require(Path(__file__).resolve() == NS / "run_sealed_browser_capture.py", "Install in the new namespace")
    require(re.fullmatch(r"[A-Za-z0-9_.:-]+", args.session_id), "Use the actual Commander session ID")
    require(all(not path.exists() and not path.is_symlink() for path in (OUT, RECEIPT, RECEIPT.with_suffix(".next"), LOG)), "Preserve previous attempts; reconcile before retrying")
    guard_path = NS / "require_completed_gate.py"
    spec = importlib.util.spec_from_file_location("_sealed_browser_completed_gate", guard_path)
    require(spec is not None and spec.loader is not None, "Gate validator unavailable")
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    require(Path(guard.__file__).resolve() == guard_path and guard.NS.resolve() == NS, "Wrong gate validator namespace")
    completed = guard.require_completed_gate(BASE, SHA)
    binding, gate = read(NS / "source-binding.json"), read(NS / "full-gate-command.json")
    require(binding["source_commit"] == gate["source_commit"] == SHA and gate["status"] == "passed" and gate["exit_code"] == 0, "Completed gate source mismatch")
    require("review-northstar-browser-v1.test.cjs" in read(BASE / "full-gate-verified.json")["frontend_suites_required"], "Review browser was not a mandatory gate suite")
    require(args.session_id != gate["commander_session_id"], "Standalone capture needs its own Commander session")
    home = os.environ.get("HOME")
    require(home is not None and Path(home).resolve() == Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(), "Forward the real account HOME")
    tools = gate["environment"]
    require(tools["CASEPATH_NODE"] == "/usr/local/bin/node" and Path(tools["CASEPATH_NODE"]).is_file(), "Expected gate Node executable")
    require(Path(tools["NODE_PATH"]).is_absolute() and Path(tools["NODE_PATH"]).is_dir(), "Expected gate Node module directory")
    require(Path(tools["PLAYWRIGHT_EXECUTABLE_PATH"]).is_absolute() and Path(tools["PLAYWRIGHT_EXECUTABLE_PATH"]).is_file() and PYTHON.is_file(), "Expected gate browser and new-runtime Python")
    env = {"HOME": home, "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "SOURCE_DATE_EPOCH": "1786406400", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "CASEPATH_SOURCE_COMMIT": SHA, "CASEPATH_MODEL_MODE": "deterministic_reference", "CASEPATH_AGENT_WORK_EXTERNAL_FACTS": "0", "CASEPATH_PYTHON": str(PYTHON), "CASEPATH_REVIEW_EVIDENCE_DIR": str(OUT), "CASEPATH_REVIEW_RECORD_VIDEO": "1", **{key: tools[key] for key in ("CASEPATH_NODE", "NODE_PATH", "PLAYWRIGHT_EXECUTABLE_PATH")}}
    command = [env["CASEPATH_NODE"], "--test", TEST]
    record = {"contract": "casepath.sealed-review-browser-capture/1", "source_commit": SHA, "source_tree": binding["source_tree"], "source_manifest_sha256": binding["source_manifest_sha256"], "status": "running", "started_at": now(), "commander_session_id": args.session_id, "execution_origin": ORIGIN, "command": command, "environment": env, "out": str(OUT), "log": str(LOG), "runner_sha256": digest(__file__), "helper_sha256": digest(__file__), "verifier_sha256": digest(guard_path), "source_binding_sha256": digest(NS / "source-binding.json"), "test_sha256": digest(ROOT / TEST), "fixture_sha256": digest(ROOT / FIXTURE), "gate_session_id": gate["commander_session_id"], "gate_command_sha256": digest(NS / "full-gate-command.json"), "gate_proof_sha256": digest(BASE / "full-gate-verified.json"), "gate_actual_completion_sha256": digest(BASE / "gate-actual-completion.json"), "completed_gate": completed, "source_clean_before": True, "full_gate_repeated": False, "fresh_browser_recording": True, "qualified_human_approval": "pending", "authority": "Isolated deterministic engineering QA; Test handler is not qualified human approval", "stages": []}
    persist(True)
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGINT, interrupted)
    stage = {"name": "review_browser_capture", "status": "running", "started_at": now()}
    record["stages"].append(stage); persist()
    try:
        with LOG.open("xb") as output:
            try:
                active = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                record["pid"] = stage["pid"] = active.pid; persist()
                print(json.dumps({"status": "running", "source_commit": SHA, "pid": active.pid, "log": str(LOG)}), flush=True)
                code = active.wait(timeout=360)
            finally:
                cleanup(); output.flush(); os.fsync(output.fileno())
        stage.update(status="completed" if code == 0 else "failed", exit_code=code, finished_at=now())
        record.update(exit_code=code, log_sha256=digest(LOG)); persist()
        require(code == 0, "Standalone browser capture failed; preserve its exact log and artifacts")
        summary = {key: int(value) for key, value in re.findall(r"^# (tests|pass|fail|cancelled|skipped|todo) (\d+)\s*$", LOG.read_text(), re.M)}
        require(summary == {"tests": 1, "pass": 1, "fail": 0, "cancelled": 0, "skipped": 0, "todo": 0}, "Expected exactly one completed browser test without skips")
        require({path.name for path in OUT.iterdir() if path.is_file()} == set(ARTIFACTS), "Successful capture must have exactly seven top-level artifacts")
        require(all(not path.is_symlink() for path in OUT.iterdir()), "Unexpected capture symlink")
        browser = read(OUT / "receipt.json")
        require(browser["status"] == "passed" and browser["browser_errors"] == browser["unexpected_destinations"] == [], "Browser receipt did not pass")
        require(browser["cases"] == ["clm_f69b1747447bc221", "clm_0e538990cc6ba7ef"], "Unexpected isolated QA cases")
        require(browser["mobile"] == {"pageOverflow": 0, "panelOverflow": 0, "reduced": True, "animations": 0}, "Mobile review checks did not pass")
        require([row["stage"] for row in browser["stages"]] == ["new-prerequisite", "resolution-dependency", "saved-version", "later-case-application"], "Incomplete operator journey")
        applied = browser["stages"][-1]
        require(applied["pin"]["version"] == 1 and applied["full_process_keyboard_access"] is True and applied["original_reader_retained"] is True, "Incomplete saved-version/reader proof")
        for name in ARTIFACTS:
            if name.endswith(".png"):
                with (OUT / name).open("rb") as source:
                    header = source.read(24)
                require(header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR" and struct.unpack(">II", header[16:24]) == ((390, 844) if name == "mobile-review.png" else (1440, 900)), "Unexpected screenshot dimensions")
        with (OUT / "review-walkthrough.webm").open("rb") as source:
            require(source.read(4) == b"\x1aE\xdf\xa3", "Missing actual WebM recording")
        require(guard.require_completed_gate(BASE, SHA) == completed, "Completed gate binding changed during capture")
        require(digest(NS / "source-binding.json") == record["source_binding_sha256"] and digest(__file__) == record["runner_sha256"] and digest(guard_path) == record["verifier_sha256"], "Source/helper binding changed during capture")
        hashes = {name: digest(OUT / name) for name in ARTIFACTS}
        record.update(status="passed", finished_at=now(), source_clean_after=True, artifact_hashes=hashes, browser_receipt_sha256=hashes["receipt.json"], test_counts=summary)
        persist()
        print(json.dumps({"status": "passed", "source_commit": SHA, "exit_code": code, "execution_origin": ORIGIN, "out": str(OUT), "receipt": str(RECEIPT), "receipt_sha256": digest(RECEIPT)}), flush=True)
    except BaseException as error:
        record.update(status="failed", finished_at=now(), error_type=type(error).__name__, reason=str(error) if isinstance(error, RuntimeError) else "Inspect preserved command log and artifacts")
        if stage["status"] == "running":
            stage.update(status="failed", finished_at=now(), exit_code=record.get("owned_process_group_cleanup", {}).get("child_exit_code"))
            record["exit_code"] = stage["exit_code"]
        if LOG.is_file():
            record["log_sha256"] = digest(LOG)
        persist()
        raise
    finally:
        cleanup()

if __name__ == "__main__":
    main()
