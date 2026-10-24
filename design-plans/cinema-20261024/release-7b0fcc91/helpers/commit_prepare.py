"""Commit only the sealed explicit allowlist, then prepare the actual new commit.

Run only after the integration owner approves execution. This helper never
creates review evidence, pushes, deploys, or claims a completed full gate.
"""
if not __debug__:
    raise RuntimeError("Assertions must remain enabled; do not use python -O.")

import sys
sys.dont_write_bytecode = True
import argparse
import fcntl
import json
import subprocess
from require_completed_gate import (
    ROOT, NS, BASE, BRANCH, MANIFEST_REL, REFERENCE, SUITES_REL, assert_checkout,
    changed_files, digest, environment, evidence_path, git, git_bytes, git_paths,
    now, read, reference, save_record, source_path, suites, verify_manifest,
    verify_source, write_new,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default="Synchronize the CasePath cinematic demonstration")
    args = parser.parse_args()
    assert args.message.strip()
    assert_checkout()
    lock = (NS / "release.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    seal_path = NS / "seal-candidate.json"
    seal = read(seal_path)
    assert seal["status"] == "passed" and seal["base_commit"] == BASE and seal["branch"] == BRANCH
    assert seal["runner_sha256"] == digest(NS / "seal_candidate.py")
    assert seal["verifier_sha256"] == digest(NS / "require_completed_gate.py")
    assert [item["name"] for item in seal["stages"]] == ["generate-artifacts", "photographic-evidence", "build-static", "generate-seal"]
    for item in seal["stages"]:
        assert item["status"] == "passed" and item["exit_code"] == 0
        assert digest(evidence_path(item["log"])) == item["log_sha256"]
    expected = set(seal["authored_files"]) | {MANIFEST_REL}
    assert set(seal["changed_files"]) == expected and changed_files() == expected
    assert not git_paths("diff", "--cached", "--name-only"), "Index must be empty before explicit staging"
    assert set(seal["authored_sha256"]) == set(seal["authored_files"])
    for relative, sha in seal["authored_sha256"].items():
        assert digest(source_path(relative)) == sha, relative
    for key in ("authored_files_input", "independent_review", "preseal_browser_receipt"):
        assert digest(evidence_path(seal[key]["path"])) == seal[key]["sha256"], key
    review = read(seal["independent_review"]["path"])
    assert review["status"] == "passed" and review["blocking_findings"] == []
    assert review["reviewed_source_files"] == seal["authored_sha256"]
    assert review["preseal_browser_receipt_sha256"] == seal["preseal_browser_receipt"]["sha256"]
    verify_manifest(seal["manifest_sha256"], seal["source_files"])
    assert digest(REFERENCE) == seal["historical_reference_sha256"]
    assert reference()["skip_reports"] == seal["historical_skip_reports"]
    assert [name for name, _ in suites()] == seal["frontend_suites_required"]
    assert digest(ROOT / SUITES_REL) == seal["frontend_declaration_sha256"]
    reserved = ["commit-candidate.json", "commit-candidate.log", "sealed-candidate.patch", "source-binding.json", "prepare-candidate.json", "prepare-candidate.log"]
    assert all(not (NS / name).exists() for name in reserved), "Never overwrite a previous commit/prepare attempt"
    target = NS / "commit-candidate.json"
    record = {"contract": "casepath.cinema-commit/1", "status": "running", "started_at": now(),
              "base_commit": BASE, "allowed_paths": sorted(expected), "seal_sha256": digest(seal_path),
              "runner_sha256": digest(__file__), "message": args.message}
    write_new(target, record)
    env = environment()
    try:
        subprocess.run(["/usr/bin/git", "add", "--", *sorted(expected)], cwd=ROOT, env=env, check=True)
        assert git_paths("diff", "--cached", "--name-only") == expected
        assert changed_files() == expected
        assert not git_paths("diff", "--name-only"), "Worktree differs from staged reviewed bytes"
        subprocess.run(["/usr/bin/git", "diff", "--cached", "--check"], cwd=ROOT, env=env, check=True)
        patch = NS / "sealed-candidate.patch"
        with patch.open("xb") as output:
            output.write(git_bytes("diff", "--cached", "--binary"))
        record["sealed_patch_sha256"] = digest(patch)
        record["staged_tree"] = git("write-tree")
        save_record(target, record)
        log = NS / "commit-candidate.log"
        with log.open("x") as output:
            child = subprocess.Popen(["/usr/bin/git", "commit", "-m", args.message], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
            record["pid"] = child.pid
            save_record(target, record)
            code = child.wait()
        record.update(exit_code=code, log_sha256=digest(log), command_finished_at=now())
        save_record(target, record)
        assert code == 0, log.read_text()[-4000:]
        sha, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
        assert_checkout(sha)
        assert git("rev-parse", "HEAD^") == BASE and tree == record["staged_tree"]
        assert not git("status", "--porcelain")
        assert git_paths("diff", BASE, sha, "--name-only") == expected
        verify_manifest(seal["manifest_sha256"], seal["source_files"])
        binding = {"contract": "casepath.cinema-source-binding/1", "source_commit": sha,
                   "source_tree": tree, "base_commit": BASE, "branch": BRANCH, "created_at": now(),
                   "source_manifest_sha256": seal["manifest_sha256"], "source_files": seal["source_files"],
                   "changed_files": sorted(expected), "authored_sha256": seal["authored_sha256"],
                   "sealed_patch_sha256": digest(patch), "seal_sha256": digest(seal_path),
                   "expected_pytest_passed": seal["expected_pytest_passed"],
                   "expected_pytest_skipped": seal["expected_pytest_skipped"],
                   "expected_count_basis": seal["expected_count_basis"],
                   **{key: seal[key] for key in ("authored_files_input", "independent_review", "preseal_browser_receipt",
                                               "frontend_suites_required", "frontend_declaration_sha256",
                                               "historical_reference_sha256", "historical_skip_reports")}}
        write_new(NS / "source-binding.json", binding)
        verify_source(binding)
        record.update(status="passed", source_commit=sha, source_tree=tree, finished_at=now(),
                      source_binding_sha256=digest(NS / "source-binding.json"))
        save_record(target, record)
    except BaseException as error:
        record.update(status="failed", failure=type(error).__name__ + ": " + str(error), finished_at=now())
        save_record(target, record)
        raise

    target = NS / "prepare-candidate.json"
    log = NS / "prepare-candidate.log"
    env["CASEPATH_SOURCE_COMMIT"] = sha
    record = {"contract": "casepath.cinema-prepare/1", "source_commit": sha, "source_tree": tree,
              "status": "running", "started_at": now(), "command": ["./bin/casepath", "prepare"],
              "source_binding_sha256": digest(NS / "source-binding.json"), "log": str(log)}
    write_new(target, record)
    try:
        with log.open("x") as output:
            child = subprocess.Popen(record["command"], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
            record["pid"] = child.pid
            save_record(target, record)
            code = child.wait()
        record.update(exit_code=code, log_sha256=digest(log), command_finished_at=now())
        save_record(target, record)
        assert code == 0, log.read_text()[-4000:]
        verify_source(binding)
        record.update(status="passed", finished_at=now())
        save_record(target, record)
        print(json.dumps({"binding": binding, "preparation": record, "log_tail": log.read_text()[-4000:]}), flush=True)
    except BaseException as error:
        record.update(status="failed", failure=type(error).__name__ + ": " + str(error), finished_at=now())
        if log.exists():
            record["log_sha256"] = digest(log)
        save_record(target, record)
        raise


if __name__ == "__main__":
    main()
