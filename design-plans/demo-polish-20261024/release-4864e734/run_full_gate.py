"""Run one fresh strict official gate and preserve its complete command evidence.

--session-id must be the actual enclosing Commander sessionId. Completion of
this helper still requires an independently captured actual terminal result;
require_completed_gate.py checks that evidence before any later release stage.
"""
if not __debug__:
    raise RuntimeError("Assertions must remain enabled; do not use python -O.")

import sys
sys.dont_write_bytecode = True
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
from require_completed_gate import (
    ROOT, NS, BASE, digest, environment, evidence_path, now, parse_complete_log,
    read, save_record, verify_source, write_new,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    assert re.fullmatch(r"[A-Za-z0-9_.:-]+", args.session_id), "Use the real stable Commander sessionId"
    binding_path = NS / "source-binding.json"
    preparation_path = NS / "prepare-candidate.json"
    binding = read(binding_path)
    sha = binding["source_commit"]
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    prepared = read(preparation_path)
    assert prepared["status"] == "passed" and prepared["exit_code"] == 0 and prepared["source_commit"] == sha
    assert prepared["source_binding_sha256"] == digest(binding_path)
    assert prepared["log_sha256"] == digest(NS / "prepare-candidate.log")
    lock = (NS / "release.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    release = NS / "release"
    release.mkdir(exist_ok=True)
    target = NS / "full-gate-command.json"
    proof_path = release / "full-gate-verified.json"
    log = NS / "full-gate.log"
    assert all(not path.exists() for path in (target, proof_path, log, release / "gate-actual-completion.json", release / "commander-terminal.json")), "Preserve all prior gate attempts; no cached reuse or overwrite"
    env = environment()
    env.update({
        "CASEPATH_SOURCE_COMMIT": sha,
        "CASEPATH_REQUIRE_FRONTEND_SUITES": "1",
        "CASEPATH_NODE": "/usr/local/bin/node",
        "NODE_PATH": "/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/node_modules",
        "PLAYWRIGHT_EXECUTABLE_PATH": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "CASEPATH_REVIEW_EVIDENCE_DIR": str(NS / "gate-browser"),
        "CASEPATH_REVIEW_RECORD_VIDEO": "1",
    })
    assert Path(env["CASEPATH_NODE"]).is_file() and Path(env["PLAYWRIGHT_EXECUTABLE_PATH"]).is_file()
    command = ["/usr/bin/nice", "-n", "10", "./bin/casepath", "test"]
    record = {"contract": "casepath.commander-demo-polish-full-gate/1", "source_commit": sha,
              "source_tree": binding["source_tree"], "base_commit": BASE, "status": "running",
              "started_at": now(), "wrapper_pid": os.getpid(), "command": command,
              "commander_session_id": args.session_id, "log": str(log), "strict_reused": False,
              "frontend_suites_mandatory": True, "environment": env,
              "runner_sha256": digest(__file__), "verifier_sha256": digest(NS / "require_completed_gate.py"),
              "source_binding_sha256": digest(binding_path), "preparation_sha256": digest(preparation_path)}
    verify_source(binding)
    write_new(target, record)
    awake = None
    try:
        awake = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-s", "-w", str(os.getpid())], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        record["caffeinate_pid"] = awake.pid
        save_record(target, record)
        with log.open("x") as output:
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
            record["pid"] = child.pid
            save_record(target, record)
            print(json.dumps({"source_commit": sha, "pid": child.pid, "status": "running", "log": str(log)}), flush=True)
            code = child.wait()
        record.update(exit_code=code, command_finished_at=now(), log_sha256=digest(log))
        save_record(target, record)
        print(json.dumps({"actual_exit_code": code, "tail": log.read_text()[-6000:]}), flush=True)
        assert code == 0, "Complete gate failed; preserve this receipt and log before any repair."
        counts, skips, isolation, summary, seconds = parse_complete_log(log, binding)
        manifest = verify_source(binding)
        assert digest(binding_path) == record["source_binding_sha256"]
        assert digest(preparation_path) == record["preparation_sha256"]
        assert digest(__file__) == record["runner_sha256"]
        assert digest(NS / "require_completed_gate.py") == record["verifier_sha256"]
        evidence = {
            "full_log": {"path": str(log), "sha256": digest(log)},
            "runner": {"path": str(Path(__file__).resolve()), "sha256": digest(__file__)},
            "verifier": {"path": str(NS / "require_completed_gate.py"), "sha256": digest(NS / "require_completed_gate.py")},
            "source_binding": {"path": str(binding_path), "sha256": digest(binding_path)},
            "preparation": {"path": str(preparation_path), "sha256": digest(preparation_path)},
            "independent_review": binding["independent_review"],
            "preseal_browser_receipt": binding["preseal_browser_receipt"],
        }
        proof = {"canonical_commit": sha, "source_tree": binding["source_tree"], "candidate_parent": BASE,
                 "verified_at": now(), "fresh_complete_gate": True, "strict_reused": False,
                 "command": "CASEPATH_REQUIRE_FRONTEND_SUITES=1 nice -n 10 ./bin/casepath test",
                 "host": str(ROOT), "exit_code": code, "summary_line": summary, "seconds": seconds,
                 "passed": counts["passed"], "failed": 0, "errors": 0, "skipped": counts["skipped"],
                 "deselected": 0, "new_skips": 0, "skip_reports": skips,
                 "frontend_suites_required": binding["frontend_suites_required"], "frontend_suites_mandatory": True,
                 "frontend_suite_evidence": "Unchanged bound 18-suite declaration, strict mandatory environment, complete official gate exit zero, and no frontend skips; successful TAP is captured inside the existing pytest tests.",
                 "manifest_sha256": binding["source_manifest_sha256"], "source_files": len(manifest["files"]),
                 "source_files_exact": True, "source_clean_after": True, "isolation": isolation,
                 "frontend_source_changed": any(path.startswith(("casepath/assets/", "casepath/index.html")) for path in binding["changed_files"]),
                 "current_visual_evidence_required": True,
                 "qualified_human_review": "not_claimed_by_automated_QA", "evidence": evidence}
        write_new(proof_path, proof)
        record.update(status="passed", finished_at=now(), counts=counts, verified_receipt_sha256=digest(proof_path))
        save_record(target, record)
        print(json.dumps({"status": "passed", "source_commit": sha, "counts": counts,
                          "actual_commander_completion_still_required": True}), flush=True)
    except BaseException as error:
        record.update(status="failed", failure=type(error).__name__ + ": " + str(error), finished_at=now())
        if log.exists():
            record["log_sha256"] = digest(log)
        save_record(target, record)
        raise
    finally:
        if awake is not None and awake.poll() is None:
            awake.terminate()
            awake.wait(timeout=10)


if __name__ == "__main__":
    main()
