"""Capture fresh release evidence only after actual gate and public acceptance."""
if not __debug__:
    raise RuntimeError("Assertions required")

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import signal
import subprocess
import sys

ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024")
NS = ROOT / ".runtime/commander-demo-polish"
BASE = NS / "release"
PY = str(ROOT / ".runtime/casepath-dev-v2/venv/bin/python")
NODE = "/usr/local/bin/node"
read = lambda p: json.loads(Path(p).read_text())
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()
SHA = read(NS / "source-binding.json")["source_commit"]
assert re.fullmatch(r"[0-9a-f]{40}", SHA)
assert Path(__file__).resolve() == NS / "run_northstar_artifacts.py"
sys.path.insert(0, str(BASE))
from require_completed_gate import require_completed_gate

# This utility checks the actual completed terminal receipt, not merely a
# running job's optimistic output or a log line containing a success count.
require_completed_gate(BASE, SHA)
acceptance_path = BASE / "published-acceptance-sequence.json"
acceptance = read(acceptance_path)
assert acceptance["status"] == "passed" and acceptance["source_commit"] == SHA
assert acceptance["stages"], "Published acceptance has no completed stages"
for stage in acceptance["stages"]:
    assert stage["status"] == "completed" and stage["exit_code"] == 0
    assert digest(stage["log"]) == stage["log_sha256"]
    for artifact in stage.get("artifacts", []):
        assert digest(artifact["path"]) == artifact["sha256"]

git = lambda *args: subprocess.check_output(["/usr/bin/git", *args], cwd=ROOT, text=True).strip()
assert git("rev-parse", "HEAD") == SHA and not git("status", "--porcelain")
helpers = ["capture_eight_states.mjs", "measure_northstar_fidelity.py", "decode_public_film.py", "make_film_contact_sheet.mjs"]
helper_hashes = {name: digest(BASE / name) for name in helpers}
sealed_path = NS / "sealed-browser-command.json"
sealed = read(sealed_path)
assert sealed["source_commit"] == SHA and sealed["status"] == "passed" and sealed["exit_code"] == 0
assert sealed["source_clean_after"] is True
for name, expected in sealed["artifact_hashes"].items():
    artifact = (NS / "sealed-browser" / name).resolve()
    assert artifact.is_relative_to((NS / "sealed-browser").resolve())
    assert digest(artifact) == expected, name

receipt = BASE / "northstar-artifacts-sequence.json"
binding_path = BASE / "northstar-artifact-inputs.json"
outputs = [BASE / "public-film-review", BASE / "eight-state-capture", BASE / "northstar-fidelity"]
assert not receipt.exists() and not binding_path.exists()
assert all(not output.exists() for output in outputs), "Use a fresh artifact run; preserve prior evidence"
binding = {
    "contract": "casepath.fresh-artifact-inputs/1", "source_commit": SHA,
    "created_at": now(), "runner_sha256": digest(__file__), "helpers": helper_hashes,
    "source_binding_sha256": digest(NS / "source-binding.json"),
    "gate_validator_sha256": digest(BASE / "require_completed_gate.py"),
    "gate_proof_sha256": digest(BASE / "full-gate-verified.json"),
    "gate_actual_completion_sha256": digest(BASE / "gate-actual-completion.json"),
    "published_acceptance_sha256": digest(acceptance_path),
    "sealed_browser_command_sha256": digest(sealed_path),
    "sealed_browser_receipt_sha256": digest(NS / "sealed-browser/receipt.json"),
    "trace_inputs": "Fresh GET responses captured and independently checked during this run; no prior fixture or forensic receipt is an input.",
}
with binding_path.open("x") as stream:
    json.dump(binding, stream, indent=2)
    stream.write("\n")
state = {
    "contract": "casepath.northstar-artifacts/2", "source_commit": SHA,
    "status": "running", "started_at": now(), "script_sha256": digest(__file__),
    "helper_binding_sha256": digest(binding_path), "source_clean_before": True,
    "product_changes": False, "reused_prior_failed_artifacts": False, "stages": [],
    "qualified_human_approval": "pending", "visual_verdict": "pending",
}
with receipt.open("x") as stream:
    json.dump(state, stream, indent=2)
    stream.write("\n")

def persist():
    temporary = receipt.with_suffix(".next")
    with temporary.open("x") as stream:
        json.dump(state, stream, indent=2)
        stream.write("\n")
    os.replace(temporary, receipt)

active = None

def cleanup():
    global active
    if active is None:
        return
    owned = active
    active = None
    if owned.poll() is None:
        try:
            os.killpg(owned.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            owned.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    # Terminate any remaining members of this stage's owned process group.
    try:
        os.killpg(owned.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    owned.wait(timeout=10)

def interrupted(signum, _frame):
    raise SystemExit(128 + signum)

signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGINT, interrupted)
env = {
    "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
    "PYTHONDONTWRITEBYTECODE": "1", "CASEPATH_MODEL_MODE": "deterministic_reference",
    "CASEPATH_AGENT_WORK_EXTERNAL_FACTS": "0",
}
stages = [
    ("film_frames", [PY, "-I", "-B", str(BASE / "decode_public_film.py")], 1200, BASE / "public-film-review/frames-index.json"),
    ("contact_sheet", [NODE, str(BASE / "make_film_contact_sheet.mjs")], 180, BASE / "public-film-review/contact-sheet.json"),
    ("eight_states", [NODE, str(BASE / "capture_eight_states.mjs")], 600, BASE / "eight-state-capture/eight-state-evidence.json"),
    ("fidelity", [PY, "-I", "-B", str(BASE / "measure_northstar_fidelity.py")], 420, BASE / "northstar-fidelity/fidelity-measurements.json"),
]
try:
    for name, command, timeout, artifact in stages:
        for helper, expected in helper_hashes.items():
            assert digest(BASE / helper) == expected, helper
        log = BASE / ("northstar-" + name + "-command.log")
        row = {"name": name, "status": "running", "command": command, "started_at": now(), "log": str(log)}
        state["stages"].append(row)
        persist()
        print(json.dumps({"stage": name, "status": "running"}), flush=True)
        with log.open("x") as stream:
            active = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            row["pid"] = active.pid
            persist()
            try:
                code = active.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                cleanup()
                raise RuntimeError("Owned artifact stage timed out: " + name)
        cleanup()
        row.update(status="completed" if code == 0 else "failed", exit_code=code, finished_at=now(), log_sha256=digest(log))
        persist()
        assert code == 0, "Preserve failed artifact evidence: " + name
        result = read(artifact)
        assert result["source_commit"] == SHA
        assert result["status"] == ("measured" if name == "fidelity" else "passed")
        row["artifact"] = {"path": str(artifact), "sha256": digest(artifact)}
        persist()
        print(json.dumps({"stage": name, "exit_code": code}), flush=True)
    assert git("rev-parse", "HEAD") == SHA and not git("status", "--porcelain")
    assert digest(acceptance_path) == binding["published_acceptance_sha256"]
    assert digest(NS / "source-binding.json") == binding["source_binding_sha256"]
    for helper, expected in helper_hashes.items():
        assert digest(BASE / helper) == expected, helper
    state["outputs"] = [
        {"path": str(file), "sha256": digest(file), "bytes": file.stat().st_size}
        for directory in outputs for file in sorted(directory.rglob("*")) if file.is_file()
    ]
    state.update(status="passed", finished_at=now(), source_clean_after=True)
    persist()
    print(json.dumps({"status": "passed", "source_commit": SHA, "decoded_frames": 24, "eight_states": 8, "concept_comparisons": 3, "visual_verdict": "pending", "qualified_human_approval": "pending"}), flush=True)
except BaseException as error:
    state.update(status="failed", failure=repr(error), finished_at=now())
    persist()
    raise
finally:
    cleanup()
