"""Checkpoint or verify the owned QA source promotion using only local GETs.

Install with resume_promoted_review_qa.py in NEW_NS/release. Both modes require
the completed release gate and published acceptance. Checkpoint runs while the
current owned service is still live. Verify takes that fresh checkpoint plus
the parent's preserved actual Commander running observation. It makes no API
mutations and opens both existing SQLite databases in read-only mode.
"""
from __future__ import annotations

if not __debug__:
    raise RuntimeError("Assertions required; do not use Python -O")

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
# Explicit loading also supports Python -I without importing another checkout.
helper_path = Path(__file__).resolve().with_name("resume_promoted_review_qa.py")
spec = importlib.util.spec_from_file_location("casepath_promoted_review_helpers", helper_path)
assert spec is not None and spec.loader is not None
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def observation(release, original):
    import httpx
    current_path = helper.plain_path(helper.DEMO / "current-server.json", helper.OLD_ROOT)
    current_bytes = current_path.read_bytes()
    current = json.loads(current_bytes)
    before = helper.data_fingerprints()
    requests = []
    with httpx.Client(timeout=30, trust_env=False, follow_redirects=False) as client:
        def get(path):
            response = client.get("http://127.0.0.1:4194" + path)
            assert response.status_code == 200, (path, response.status_code)
            requests.append({"method": "GET", "path": path, "status": response.status_code,
                             "response_sha256": hashlib.sha256(response.content).hexdigest()})
            return response
        health = get("/healthz").json()
        capsule = helper.validate_current(current, health, original, release)
        views = {}
        for claim in helper.CASES:
            value = get("/api/claim-loops/v1/workspace/claims/" + claim + "/process").json()
            views[claim] = helper.view_fingerprint(value, claim, original)
        assets = {}
        for relative in helper.STATIC_PATHS:
            path = "/" if relative == "index.html" else "/" + relative
            response = get(path)
            expected = helper.digest(capsule / "casepath" / relative)
            actual = hashlib.sha256(response.content).hexdigest()
            assert actual == expected, "Served display asset differs from immutable capsule: " + relative
            assets[relative] = {"sha256": actual, "bytes": len(response.content)}
        final_health = get("/healthz").json()
        assert final_health == health, "Service identity changed during the GET-only observation"
    assert helper.data_fingerprints() == before, "GET-only observation changed or raced with current QA data"
    assert current_path.read_bytes() == current_bytes, "Current server changed during observation"
    assert helper.original_context()["proof"] == original["proof"]
    return {"current_server": current, "current_server_sha256": hashlib.sha256(current_bytes).hexdigest(),
            "health": health, "views": views, "data_fingerprints": before,
            "display_assets": assets, "get_requests": requests}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="mode", required=True)
    checkpoint = subcommands.add_parser("checkpoint")
    checkpoint.add_argument("--out", type=Path, required=True)
    verify = subcommands.add_parser("verify")
    verify.add_argument("--before", type=Path, required=True)
    verify.add_argument("--running-receipt", type=Path, required=True)
    verify.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert Path(__file__).resolve() == helper.VERIFIER.resolve()
    helper.plain_path(args.out, helper.NS)
    assert args.out.parent.is_dir() and not args.out.exists(), "Use a fresh evidence filename"
    release, original = helper.release_context(), helper.original_context()
    observed = observation(release, original)
    common = {"status": "passed", "observed_at": helper.now(), "target_source_commit": helper.SHA,
              "source_commit": observed["health"]["source_commit"], "instance_id": helper.INSTANCE,
              "data_root": str(helper.DATA), "get_only": True, "original_qa_files_unchanged": True,
              "original_application_retained": True, "qualified_human_approval_asserted": False,
              "release_proof": release["proof"], "original_proof": original["proof"],
              "verifier_sha256": helper.digest(__file__), "launcher_sha256": helper.digest(helper.LAUNCHER)}
    if args.mode == "checkpoint":
        record = {**common, **observed, "contract": "casepath.owned-qa-promotion-checkpoint/1"}
    else:
        before_path = helper.evidence_path(args.before)
        before = helper.read(before_path)
        assert before["contract"] == "casepath.owned-qa-promotion-checkpoint/1" and before["status"] == "passed"
        assert before["get_only"] is True and before["target_source_commit"] == helper.SHA
        assert before["launcher_sha256"] == common["launcher_sha256"] and before["verifier_sha256"] == common["verifier_sha256"]
        assert before["release_proof"] == common["release_proof"] and before["original_proof"] == common["original_proof"]
        current, health = observed["current_server"], observed["health"]
        assert current["source_commit"] == health["source_commit"] == helper.SHA
        assert current["contract"] == "casepath.owned-qa-source-promotion/1"
        prior = before["current_server"]
        assert current["previous_source_commit"] == before["source_commit"] == prior["source_commit"]
        assert current["previous_pid"] == prior["pid"] == before["health"]["pid"]
        assert current["previous_session"] == prior["commander_session"]
        assert current["previous_boot_id"] == prior["boot_id"] == before["health"]["boot_id"]
        assert current["pid"] != prior["pid"] and current["boot_id"] != prior["boot_id"]
        assert current["commander_session"] != prior["commander_session"]
        assert current["checkpoint"] == {"path": str(before_path), "sha256": helper.digest(before_path)}
        previous_path = helper.evidence_path(current["previous_current_server"]["path"])
        assert previous_path.is_relative_to(helper.PROMOTIONS)
        assert helper.digest(previous_path) == current["previous_current_server"]["sha256"] == before["current_server_sha256"]
        assert helper.read(previous_path) == prior
        assert helper.read(previous_path.parent / "before-snapshot.json") == before
        assert helper.read(previous_path.parent / "owner.json") == current
        assert current["original_proof"] == original["proof"]
        assert current["verifier_sha256"] == common["verifier_sha256"]
        assert current["data_before"] == current["data_after"] == before["data_fingerprints"] == observed["data_fingerprints"]
        assert current["views_before"] == current["views_after"] == before["views"] == observed["views"]
        for key, predicate, field in (
            ("commander_stop", lambda row: row.get("terminated") is True, "terminated"),
            ("commander_terminal", lambda row: row.get("state") in ("completed", "terminated", "failed"), "state"),
        ):
            actual, proof = helper.commander_evidence(current[key]["path"], prior["commander_session"],
                                                     predicate, observation_field=field)
            assert proof == current[key]
            if "pid" in actual:
                assert actual["pid"] == prior["pid"]
        running, running_proof = helper.commander_evidence(args.running_receipt, current["commander_session"],
            lambda row: row.get("state") == "running" and row.get("pid") == current["pid"])
        assert running["pid"] == health["pid"]
        record = {**common, **observed, "contract": "casepath.owned-qa-source-promotion-verified/1",
                  "checkpoint": current["checkpoint"], "previous_current_server": current["previous_current_server"],
                  "known_owned_previous_process_terminated": True, "actual_previous_terminal_observed": True,
                  "promoted_process_observed_running": True, "initial_owner_preserved": True,
                  "initial_copy_receipt_preserved": True, "same_data_root": True,
                  "current_claim_and_work_data_unchanged": True, "source_and_target_views_unchanged": True,
                  "display_assets_match_new_capsule": True, "copied_or_reset_data": False,
                  "seeded_or_replayed_work": False,
                  "commander_evidence": {"stop": current["commander_stop"], "terminal": current["commander_terminal"],
                                         "running": running_proof}}
    helper.write_new(args.out, record)
    print(json.dumps({"status": "checkpointed" if args.mode == "checkpoint" else "verified",
                      "source_commit": common["source_commit"], "target_source_commit": helper.SHA,
                      "instance_id": helper.INSTANCE, "pid": observed["health"]["pid"],
                      "views": observed["views"], "get_requests": len(observed["get_requests"]),
                      "display_assets_verified": len(observed["display_assets"]),
                      "receipt": str(args.out), "receipt_sha256": helper.digest(args.out)}), flush=True)


if __name__ == "__main__":
    main()
