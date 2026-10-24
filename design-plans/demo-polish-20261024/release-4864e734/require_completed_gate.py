"""Shared release checks; require externally observed Commander completion last.

This file lives beside seal_candidate.py, commit_prepare.py and run_full_gate.py
in .runtime/commander-demo-polish. Importing it performs no release operation.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Assertions must remain enabled; do not use python -O.")

import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
NS = ROOT / ".runtime/commander-demo-polish"
BASE = "f75af1ac22a7260487556fc9231f4e290489c2e0"
BRANCH = "codex/casepath-demo-polish-20261024"
BASELINE_COMMIT = "b20685d1670b33b941b1bfcb902638a879c01b93"
REFERENCE_REL = "design-plans/northstar-review-20261024/release-b20685d1/full-gate.json"
REFERENCE = ROOT / REFERENCE_REL
SUITES_REL = "casepath-api/tests/test_frontend_node_suites_v1.py"
MANIFEST_REL = "casepath/source-manifest.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def environment():
    # Explicit allowlist: never forward provider configuration or credentials.
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/Users/kumar0002/.local/bin:/usr/local/bin",
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
        "PYTHONDONTWRITEBYTECODE": "1", "SOURCE_DATE_EPOCH": "1786406400",
        "CASEPATH_UV": "/Users/kumar0002/.local/bin/uv",
    }
    if "HOME" in os.environ:
        env["HOME"] = os.environ["HOME"]
    return env


def git_bytes(*args):
    return subprocess.check_output(["/usr/bin/git", *args], cwd=ROOT, env=environment())


def git(*args):
    return git_bytes(*args).decode().strip()


def git_paths(*args):
    return set(filter(None, git_bytes(*args, "-z").decode().split("\0")))


def changed_files():
    return git_paths("diff", "HEAD", "--name-only") | git_paths("ls-files", "--others", "--exclude-standard")


def source_path(relative):
    assert isinstance(relative, str) and relative, "Invalid source path"
    path = PurePosixPath(relative)
    assert not path.is_absolute() and ".." not in path.parts
    assert str(path) == relative and path.parts[0] not in (".git", ".runtime")
    result = ROOT / relative
    assert result.resolve().is_relative_to(ROOT.resolve()), relative
    assert result.is_file() and not result.is_symlink(), relative
    return result


def evidence_path(path):
    result = Path(path)
    if not result.is_absolute():
        result = ROOT / result
    result = result.resolve()
    assert result.is_relative_to((ROOT / ".runtime").resolve()) or result.is_relative_to((ROOT / "design-plans").resolve()), result
    assert result.is_file(), result
    return result


def write_new(path, record):
    with Path(path).open("x") as output:
        json.dump(record, output, indent=2)
        output.write("\n")


def save_record(path, record):
    path = Path(path)
    temporary = path.with_name(path.name + ".next")
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    os.replace(temporary, path)


def assert_checkout(commit=BASE):
    assert (ROOT / ".git").is_dir(), "A normal isolated clone is required."
    assert git("rev-parse", "HEAD") == commit
    assert git("branch", "--show-current") == BRANCH


def reference():
    # A committed historical proof supplies only the expected inventory/skips.
    # It can never establish a passing result for this candidate.
    raw = REFERENCE.read_bytes()
    assert raw == git_bytes("show", BASE + ":" + REFERENCE_REL), "Historical proof changed"
    result = json.loads(raw)
    assert result["canonical_commit"] == BASELINE_COMMIT
    assert result["fresh_complete_gate"] is True and result["strict_reused"] is False
    assert result["exit_code"] == 0 and result["passed"] == 2927 and result["skipped"] == 10
    assert all(result[key] == 0 for key in ("failed", "errors", "deselected", "new_skips"))
    assert result["frontend_suites_mandatory"] is True
    assert len(result["skip_reports"]) == 10 and len(result["frontend_suites_required"]) == 18
    return result


def suites():
    tree = ast.parse((ROOT / SUITES_REL).read_text())
    values = [ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and any(
                  isinstance(target, ast.Name) and target.id == "SUITES"
                  for target in node.targets)]
    assert len(values) == 1
    result = values[0]
    assert len(result) == 18
    assert all(isinstance(row, (tuple, list)) and len(row) == 2
               and isinstance(row[0], str) and isinstance(row[1], bool) for row in result)
    assert [name for name, _ in result] == reference()["frontend_suites_required"]
    assert len({name for name, _ in result}) == 18
    baseline_tree = ast.parse(git_bytes("show", BASE + ":" + SUITES_REL).decode())
    baseline_values = [ast.literal_eval(node.value) for node in baseline_tree.body
                       if isinstance(node, ast.Assign) and any(
                           isinstance(target, ast.Name) and target.id == "SUITES"
                           for target in node.targets)]
    assert len(baseline_values) == 1 and result == baseline_values[0], "Frontend suite declarations or browser requirements changed"
    return result


def verify_manifest(expected_hash=None, expected_count=None):
    path = ROOT / MANIFEST_REL
    if expected_hash is not None:
        assert digest(path) == expected_hash, "Source manifest changed"
    manifest = read(path)
    rows = manifest["files"]
    if expected_count is not None:
        assert len(rows) == expected_count
    assert len({row["path"] for row in rows}) == len(rows)
    for row in rows:
        assert digest(source_path(row["path"])) == row["sha256"], row["path"]
    return manifest


def verify_source(binding):
    assert_checkout(binding["source_commit"])
    assert binding["base_commit"] == BASE
    assert git("rev-parse", "HEAD^{tree}") == binding["source_tree"]
    assert not git("status", "--porcelain"), "Candidate source is no longer clean"
    assert git_paths("diff", BASE, binding["source_commit"], "--name-only") == set(binding["changed_files"])
    assert not git("diff", BASE, binding["source_commit"], "--name-only", "--",
                   "casepath-api/source-assets", "casepath-api/casepath_api/corpora", "examples")
    assert binding["expected_pytest_passed"] == 2927 and binding["expected_pytest_skipped"] == 10
    assert binding["frontend_suites_required"] == [name for name, _ in suites()]
    assert digest(ROOT / SUITES_REL) == binding["frontend_declaration_sha256"]
    assert digest(REFERENCE) == binding["historical_reference_sha256"]
    assert binding["historical_skip_reports"] == reference()["skip_reports"]
    assert binding["seal_sha256"] == digest(NS / "seal-candidate.json")
    assert binding["sealed_patch_sha256"] == digest(NS / "sealed-candidate.patch")
    for relative, sha in binding["authored_sha256"].items():
        assert digest(source_path(relative)) == sha, relative
    for key in ("independent_review", "preseal_browser_receipt", "authored_files_input"):
        item = binding[key]
        assert digest(evidence_path(item["path"])) == item["sha256"], key
    return verify_manifest(binding["source_manifest_sha256"], binding["source_files"])


def parse_complete_log(path, binding):
    text = Path(path).read_text()
    count_item = r"[0-9]+ (?:passed|failed|skipped|errors?|deselected|xfailed|xpassed|warnings?)"
    pattern = (r"^(?:=+[ \t]*)?(?P<counts>" + count_item + r"(?:,[ \t]*" + count_item + r")*)"
               r"[ \t]+in[ \t]+(?P<seconds>[0-9]+(?:\.[0-9]+)?)s"
               r"(?:[ \t]+\([0-9]+:[0-9]{2}(?::[0-9]{2})?\))?(?:[ \t]*=+)?[ \t]*$")
    matches = list(re.finditer(pattern, text, re.M))
    assert matches, "No complete pytest terminal summary"
    final = matches[-1]
    counts = {}
    for value, key in re.findall(r"([0-9]+) (passed|failed|skipped|errors?|deselected|xfailed|xpassed|warnings?)", final.group("counts")):
        key = {"error": "errors", "warning": "warnings"}.get(key, key)
        assert key not in counts
        counts[key] = int(value)
    assert counts.get("passed") == binding["expected_pytest_passed"] == 2927, counts
    assert counts.get("skipped") == binding["expected_pytest_skipped"] == 10, counts
    assert all(counts.get(key, 0) == 0 for key in ("failed", "errors", "deselected", "xfailed", "xpassed")), counts
    skips = [line for line in text.splitlines() if line.startswith("SKIPPED")]
    assert skips == binding["historical_skip_reports"] == reference()["skip_reports"]
    assert not any("test_frontend_node_suites_v1.py" in line for line in skips)
    attestations = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("contract") == "casepath.isolated-backend-static-test/1.0.0":
            attestations.append(item)
    assert len(attestations) == 1, "Expected the official deterministic isolation attestation"
    isolation = attestations[0]
    assert isolation["model_mode"] == "deterministic_reference"
    assert isolation["provider_credential_names_present"] == []
    assert isolation["persistent_product_database_used"] is False
    assert isolation["persistent_artifact_registry_used"] is False
    assert isolation["targets"] == ["casepath-api/tests", "casepath/tools/test_build_deployment_identity.py", "casepath/tools/test_casepath_release.py"]
    return counts, skips, isolation, final.group("counts"), float(final.group("seconds"))


def _terminal_candidates(value, session_id):
    """Unwrap a preserved raw Commander tool response without inventing fields."""
    found = []
    if isinstance(value, dict):
        if value.get("sessionId") == session_id and "state" in value and "exitCode" in value:
            found.append(value)
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                found.extend(_terminal_candidates(child, session_id))
            elif key == "text" and isinstance(child, str):
                try:
                    found.extend(_terminal_candidates(json.loads(child), session_id))
                except json.JSONDecodeError:
                    pass
    elif isinstance(value, list):
        for child in value:
            found.extend(_terminal_candidates(child, session_id))
    return found


def require_completed_gate(base, source, expected_session=None):
    """Read-only final gate. Parent records actual Commander terminal evidence.

    base is NS/release. It must contain gate-actual-completion.json and the
    preserved raw commander-terminal.json; the wrapper cannot author either.
    """
    base = Path(base).resolve()
    assert base == (NS / "release").resolve()
    command_path = NS / "full-gate-command.json"
    proof_path = base / "full-gate-verified.json"
    observed_path = base / "gate-actual-completion.json"
    terminal_path = base / "commander-terminal.json"
    binding = read(NS / "source-binding.json")
    command, proof, observed = read(command_path), read(proof_path), read(observed_path)
    assert binding["source_commit"] == source
    assert command["source_commit"] == proof["canonical_commit"] == observed["source_commit"] == source
    assert command["source_tree"] == proof["source_tree"] == binding["source_tree"]
    session_id = command["commander_session_id"]
    assert isinstance(session_id, str) and session_id and observed["sessionId"] == session_id
    if expected_session is not None:
        assert session_id == expected_session
    assert observed["state"] == "completed" and observed["exitCode"] == 0
    assert observed["commander_terminal_sha256"] == digest(terminal_path)
    terminals = _terminal_candidates(read(terminal_path), session_id)
    assert terminals and all(item["state"] == "completed" and item["exitCode"] == 0 for item in terminals), "No actual successful Commander terminal result"
    assert command["status"] == "passed" and command["exit_code"] == 0
    assert command["command"] == ["/usr/bin/nice", "-n", "10", "./bin/casepath", "test"]
    assert command["strict_reused"] is False and command["frontend_suites_mandatory"] is True
    assert command["environment"]["CASEPATH_REQUIRE_FRONTEND_SUITES"] == "1"
    assert command["verified_receipt_sha256"] == observed["proof_sha256"] == digest(proof_path)
    assert observed["terminal_receipt_sha256"] == digest(command_path)
    log = NS / "full-gate.log"
    assert Path(command["log"]).resolve() == log.resolve()
    assert command["log_sha256"] == observed["log_sha256"] == digest(log)
    assert command["source_binding_sha256"] == digest(NS / "source-binding.json")
    assert command["runner_sha256"] == digest(NS / "run_full_gate.py")
    assert command["verifier_sha256"] == digest(__file__)
    assert command["preparation_sha256"] == digest(NS / "prepare-candidate.json")
    prepared = read(NS / "prepare-candidate.json")
    assert prepared["status"] == "passed" and prepared["exit_code"] == 0 and prepared["source_commit"] == source
    assert prepared["log_sha256"] == digest(NS / "prepare-candidate.log")
    assert proof["fresh_complete_gate"] is True and proof["strict_reused"] is False
    assert proof["frontend_suites_mandatory"] is True and proof["exit_code"] == 0
    assert proof["frontend_suites_required"] == binding["frontend_suites_required"]
    assert proof["manifest_sha256"] == binding["source_manifest_sha256"]
    assert all(proof[key] == 0 for key in ("failed", "errors", "new_skips", "deselected"))
    counts, skips, isolation, summary, seconds = parse_complete_log(log, binding)
    assert command["counts"] == counts
    assert proof["passed"] == counts["passed"] and proof["skipped"] == counts["skipped"]
    assert proof["summary_line"] == summary and proof["seconds"] == seconds
    assert proof["skip_reports"] == skips and proof["isolation"] == isolation
    for item in proof["evidence"].values():
        assert digest(evidence_path(item["path"])) == item["sha256"]
    verify_source(binding)
    return {"source_commit": source, "terminal_gate_exit": 0,
            "proof_sha256": digest(proof_path), "actual_completion_sha256": digest(observed_path),
            "commander_terminal_sha256": digest(terminal_path)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    print(json.dumps(require_completed_gate(NS / "release", args.source, args.session_id), indent=2))
