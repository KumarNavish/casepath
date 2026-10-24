"""Seal supplied, independently reviewed source once; never commit or deploy.

Required inputs are an authored-files.json list (or {"files": [...]}); an
independent-review.json with status=passed, blocking_findings=[], nonempty
reviews, reviewed_source_files={relative_path: sha256} for the exact allowlist,
and preseal_browser_receipt_sha256; and the actual passing browser receipt.
The caller must stop the development server owned by this checkout first.
"""
if not __debug__:
    raise RuntimeError("Assertions must remain enabled; do not use python -O.")

import sys
sys.dont_write_bytecode = True
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
from require_completed_gate import (
    ROOT, NS, BASE, BRANCH, MANIFEST_REL, REFERENCE, SUITES_REL, assert_checkout,
    changed_files, digest, environment, evidence_path, git, git_paths, now,
    read, reference, save_record, source_path, suites, verify_manifest, write_new,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authored-files", default=str(NS / "authored-files.json"))
    parser.add_argument("--independent-review", default=str(NS / "independent-review.json"))
    parser.add_argument("--browser-receipt", required=True)
    args = parser.parse_args()
    assert_checkout()
    lock = (NS / "release.lock").open("a+")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    authored_input = evidence_path(args.authored_files)
    review_path = evidence_path(args.independent_review)
    browser_path = evidence_path(args.browser_receipt)
    supplied = read(authored_input)
    authored = supplied["files"] if isinstance(supplied, dict) else supplied
    assert isinstance(authored, list) and authored and all(isinstance(p, str) for p in authored)
    assert len(set(authored)) == len(authored), "Duplicate authored paths"
    authored = sorted(authored)
    assert MANIFEST_REL not in authored and REFERENCE.relative_to(ROOT).as_posix() not in authored
    assert not any(p.startswith(("casepath-api/source-assets/", "casepath-api/casepath_api/corpora/", "examples/")) for p in authored)
    authored_hashes = {p: digest(source_path(p)) for p in authored}
    assert changed_files() == set(authored), sorted(changed_files() ^ set(authored))
    assert not git_paths("diff", "--cached", "--name-only"), "Index must be empty before sealing"
    review, browser = read(review_path), read(browser_path)
    assert review["status"] == "passed" and review["blocking_findings"] == []
    assert isinstance(review["reviews"], list) and review["reviews"], "Actual independent reviews required"
    assert all(isinstance(item, dict) and item.get("verdict") for item in review["reviews"])
    assert review["reviewed_source_files"] == authored_hashes, "Review does not bind these exact source bytes"
    assert review["preseal_browser_receipt_sha256"] == digest(browser_path)
    assert browser["status"] == "passed"
    assert browser["browser_errors"] == [] and browser["unexpected_destinations"] == []
    declared = suites()
    historical = reference()
    inputs = {"authored_files_input": {"path": str(authored_input), "sha256": digest(authored_input)},
              "independent_review": {"path": str(review_path), "sha256": digest(review_path)},
              "preseal_browser_receipt": {"path": str(browser_path), "sha256": digest(browser_path)}}
    target = NS / "seal-candidate.json"
    python = str(ROOT / ".runtime/casepath-dev-v2/venv/bin/python")
    assert Path(python).is_file()
    stages = [
        ("generate-artifacts", [python, "-B", "casepath-api/generate_artifacts.py"]),
        ("photographic-evidence", [python, "-B", "casepath-api/replace_photographic_evidence.py", "."]),
        ("build-static", [python, "-B", "casepath/tools/build_static_site.py", "--require-known-commit"]),
        ("generate-seal", [python, "-B", "casepath/tools/casepath_release.py", "generate"]),
    ]
    assert not target.exists() and all(not (NS / ("seal-" + name + ".log")).exists() for name, _ in stages)
    record = {"contract": "casepath.demo-polish-seal/1", "status": "running",
              "base_commit": BASE, "branch": BRANCH, "started_at": now(), "stages": [],
              "authored_files": authored, "authored_sha256": authored_hashes,
              "runner_sha256": digest(__file__), "verifier_sha256": digest(NS / "require_completed_gate.py"),
              "historical_reference_sha256": digest(REFERENCE), "historical_skip_reports": historical["skip_reports"],
              "frontend_suites_required": [name for name, _ in declared],
              "frontend_declaration_sha256": digest(ROOT / SUITES_REL),
              "expected_pytest_passed": 2927, "expected_pytest_skipped": 10,
              "expected_count_basis": "Unchanged 2927-test Python parameterization and 18 mandatory frontend suites; exact prior ten historical skips.",
              **inputs}
    write_new(target, record)
    env = environment()
    env["CASEPATH_SOURCE_COMMIT"] = BASE
    try:
        for name, command in stages:
            log = NS / ("seal-" + name + ".log")
            item = {"name": name, "command": command, "status": "running", "started_at": now(), "log": str(log)}
            record["stages"].append(item)
            save_record(target, record)
            with log.open("x") as output:
                child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
                item["pid"] = child.pid
                save_record(target, record)
                code = child.wait()
            item.update(exit_code=code, status="passed" if code == 0 else "failed", finished_at=now(), log_sha256=digest(log))
            save_record(target, record)
            print(json.dumps(item), flush=True)
            assert code == 0, log.read_text()[-4000:]
        assert_checkout()
        assert {p: digest(source_path(p)) for p in authored} == authored_hashes, "Sealing changed reviewed authored bytes"
        assert changed_files() == set(authored) | {MANIFEST_REL}, sorted(changed_files())
        assert not git_paths("diff", "--cached", "--name-only"), "Index changed during sealing"
        for item in inputs.values():
            assert digest(item["path"]) == item["sha256"], "Review input changed during sealing"
        assert digest(ROOT / SUITES_REL) == record["frontend_declaration_sha256"]
        manifest = verify_manifest()
        subprocess.run(["/usr/bin/git", "diff", "--check"], cwd=ROOT, env=env, check=True)
        record.update(status="passed", finished_at=now(), source_files=len(manifest["files"]),
                      manifest_sha256=digest(ROOT / MANIFEST_REL), changed_files=sorted(changed_files()))
        save_record(target, record)
        print(json.dumps({key: record[key] for key in ("status", "source_files", "manifest_sha256", "changed_files")}), flush=True)
    except BaseException as error:
        record.update(status="failed", failure=type(error).__name__ + ": " + str(error), finished_at=now())
        save_record(target, record)
        raise


if __name__ == "__main__":
    main()
