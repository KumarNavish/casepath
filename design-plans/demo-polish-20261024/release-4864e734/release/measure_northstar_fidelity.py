"""Measure all three references; leave the substantive visual verdict pending."""
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

ROOT = Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024")
NS = ROOT / ".runtime/commander-demo-polish"
BASE = NS / "release"
CAPTURE = BASE / "eight-state-capture"
OUT = BASE / "northstar-fidelity"
read = lambda p: json.loads(Path(p).read_text())
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
SHA = read(NS / "source-binding.json")["source_commit"]
assert re.fullmatch(r"[0-9a-f]{40}", SHA)
binding = read(BASE / "northstar-artifact-inputs.json")
assert binding["source_commit"] == SHA and binding["helpers"]["measure_northstar_fidelity.py"] == digest(__file__)
assert binding["source_binding_sha256"] == digest(NS / "source-binding.json")
states = read(CAPTURE / "eight-state-evidence.json")
assert states["status"] == "passed" and states["source_commit"] == SHA
assert not OUT.exists()
OUT.mkdir()
env = {
    "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
    "PLAYWRIGHT_MODULE": "/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/node_modules/playwright/index.mjs",
    "PLAYWRIGHT_CHROMIUM": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "PYTHONDONTWRITEBYTECODE": "1",
}
assert Path(env["PLAYWRIGHT_MODULE"]).is_file()
tool = ROOT / "design-plans/tools/fidelity.mjs"
report = {
    "source_commit": SHA, "created_at": datetime.now(timezone.utc).isoformat(), "status": "running",
    "script_sha256": digest(__file__), "tool_sha256": digest(tool),
    "helper_binding_sha256": digest(BASE / "northstar-artifact-inputs.json"),
    "capture_receipt_sha256": digest(CAPTURE / "eight-state-evidence.json"),
    "scope": "Pixel measurements of unchanged concept images against actual captured states. Numeric differences do not establish semantic acceptance.",
    "comparisons": [], "visual_review": "pending",
}
receipt = OUT / "fidelity-measurements.json"
with receipt.open("x") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")

def persist():
    temporary = receipt.with_suffix(".next")
    with temporary.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    os.replace(temporary, receipt)

active = None

def cleanup():
    global active
    if active is None:
        return
    owned, active = active, None
    if owned.poll() is None:
        try:
            os.killpg(owned.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            owned.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    try:
        os.killpg(owned.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    owned.wait(timeout=3)

def interrupted(signum, _frame):
    raise SystemExit(128 + signum)

signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGINT, interrupted)
try:
    for number, concept in ((4, "01-decision-building.png"), (6, "02-completed-process.png"), (8, "03-reviewed-memory-payoff.png")):
        state = next(row for row in states["states"] if row["state"] == number)
        frame = CAPTURE / state["file"]
        assert digest(frame) == state["sha256"]
        reference = ROOT / "design/northstar" / concept
        prefix = OUT / ("concept-" + concept[:2])
        command = ["/usr/local/bin/node", str(tool), str(reference), str(frame), str(prefix)]
        log = OUT / (prefix.name + "-command.log")
        with log.open("x") as stream:
            active = subprocess.Popen(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            try:
                stdout, stderr = active.communicate(timeout=120)
                code = active.returncode
                stream.write(stdout + stderr)
            except subprocess.TimeoutExpired as error:
                for partial in (error.stdout, error.stderr):
                    if partial:
                        stream.write(partial.decode(errors="replace") if isinstance(partial, bytes) else partial)
                raise
            finally:
                cleanup()
        assert code == 0, log.read_text()[-2000:]
        measured = json.loads(stdout.strip().splitlines()[-1])
        row = {"concept": concept, "concept_sha256": digest(reference), "state": number, "frame": state["file"], "frame_sha256": digest(frame), "mean_difference_pct": measured["mean_difference_pct"], "command_log_sha256": digest(log), "outputs": []}
        for kind in ("side", "overlay", "diff"):
            image = Path(str(prefix) + "-" + kind + ".png")
            assert image.is_file() and not image.is_symlink()
            row["outputs"].append({"kind": kind, "file": image.name, "sha256": digest(image), "bytes": image.stat().st_size})
        report["comparisons"].append(row)
        persist()
    assert digest(tool) == report["tool_sha256"]
    report["status"] = "measured"
    persist()
    print(json.dumps({"status": "measured", "source_commit": SHA, "visual_review": "pending", "mean_difference_pct": [row["mean_difference_pct"] for row in report["comparisons"]]}))
except BaseException as error:
    report["status"] = "failed"
    report["failure"] = repr(error)
    persist()
    raise
finally:
    cleanup()
