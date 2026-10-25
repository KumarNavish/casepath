"""Inventory the prepared documentary helpers without running release operations.

The helper copies were prepared in separately recorded Commander calls.
This file verifies their exact bytes and records provenance only. It does not
copy historical success receipts or run product tests, capture, integration,
API mutations, or publication.
"""
from pathlib import Path
import hashlib, json, re, subprocess, sys
if not __debug__:
    raise RuntimeError("Assertions required")
ROOT=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024")
NS=ROOT/".runtime/documentary-release-20261025"
OLD=ROOT/".runtime/cinema-release"
BASE="5da3233a0aa04ad29843c8ec55dfb685118381c9"
BRANCH="codex/casepath-documentary-20261025"
RELEASE_HELPERS={
    "integrate_canonical.py","run_api_release.py","renew_seed.py","update_api_env.py",
    "deploy_api.py","await_api.py","require_completed_gate.py","copy_sites_inputs.py",
    "run_sites_workflow_finite.py","readback.py","verify_readback.py","verify_api_build_v2.py",
    "verify_public_image.py","published_soak.py","prepare_public_archive_transfer_v2.py",
    "verify_published.mjs","verify_supplement.mjs"
}
ROOT_HELPERS={
    "seal_candidate.py","commit_prepare.py","run_full_gate.py","require_completed_gate.py",
    "bind_actual_gate_completion.py","run_published_acceptance.py","capture_fresh_baseline.py",
    "capture_final_fidelity.py","bind_documentary_runtime.py"
}
def regular(path):
    path=Path(path)
    assert path.is_absolute() and path.is_relative_to(ROOT) and ".." not in path.parts
    assert path.is_file() and not path.is_symlink(),str(path)
    for parent in path.parents:
        assert not parent.is_symlink(),str(parent)
        if parent==ROOT:break
    return path
def sha(path):
    return hashlib.sha256(regular(path).read_bytes()).hexdigest()
def main():
    assert len(sys.argv)==1
    assert Path(__file__).resolve()==NS/"prepare_documentary_runtime.py"
    assert subprocess.check_output(["/usr/bin/git","branch","--show-current"],cwd=ROOT,text=True).strip()==BRANCH
    target=NS/"documentary-helper-adaptation.json"
    assert not target.exists(),"Preserve and reconcile an existing adaptation inventory"
    release_record=NS/"release/release-helper-adaptation.json"
    release=json.loads(regular(release_record).read_text())
    assert release.get("source_helpers_only") is True
    assert release.get("commands_executed") is False
    assert release.get("success_receipts_copied") is False
    assert set(release["helpers"])==RELEASE_HELPERS
    helpers={}
    release_helpers={}
    for name in sorted(RELEASE_HELPERS):
        path=NS/"release"/name
        origin=OLD/"release"/name
        relative=path.relative_to(ROOT).as_posix()
        row={"sha256":sha(path),"source_path":str(origin),"source_sha256":sha(origin),
             "target_name":name,"bytes":path.stat().st_size}
        declared=release["helpers"][name]
        for field in ("source_path","target_name","source_sha256","sha256"):
            assert declared[field]==row[field],(name,field)
        helpers[relative]=row
        release_helpers[name]=row
    for name in sorted(ROOT_HELPERS):
        path=NS/name;origin=OLD/name
        helpers[path.relative_to(ROOT).as_posix()]={
            "sha256":sha(path),"source_path":str(origin),"source_sha256":sha(origin),
            "bytes":path.stat().st_size}
    for relative in (".runtime/cinema-evidence/capture.cjs",".runtime/root-before/capture.cjs"):
        path=ROOT/relative
        helpers[relative]={"sha256":sha(path),"source_path":str(path),
                           "source_sha256":sha(path),"bytes":path.stat().st_size,
                           "adapted_this_turn":False}
    record={
        "contract":"casepath.documentary-helper-adaptation/1",
        "root":str(ROOT),"branch":BRANCH,"base_commit":BASE,
        "previous_deployed_source":BASE,"source_helpers_only":True,
        "commands_executed":False,"success_receipts_copied":False,
        "scope":"Inventories source helpers prepared by separate observed Commander filesystem calls. This inventory helper runs no test, capture, integration, API mutation or publication.",
        "adapter_sha256":sha(__file__),
        "preparation_receipts":{
            "initial_gate_helpers":"casepath-20261025-prepare-release-v1",
            "root_release_helpers":"casepath-20261025-prepare-root-release-helpers-v1",
            "current_baseline_binding":"casepath-20261025-bind-current-baseline-helper-v1",
            "new_evidence_output_paths":"casepath-20261025-adapt-evidence-output-paths-v1"
        },
        "release_adaptation":{"path":str(release_record),"sha256":sha(release_record)},
        "helpers":helpers,"release_helpers":release_helpers,
        "generated_helpers":{
            ".runtime/documentary-release-20261025/bind_documentary_runtime.py":{
                "sha256":sha(NS/"bind_documentary_runtime.py")}
        }
    }
    for relative,row in helpers.items():
        assert sha(ROOT/relative)==row["sha256"],relative
    with target.open("x") as stream:
        json.dump(record,stream,indent=2,sort_keys=True);stream.write("\n")
    print(json.dumps({"status":"source_helpers_inventoried","helpers":len(helpers),
        "release_helpers":len(release_helpers),"record":str(target),"sha256":sha(target),
        "gate_or_publication_success_claimed":False}))
if __name__=="__main__":main()
