"""Prepare public handoff only after all fresh release checks actually complete."""
if not __debug__:
    raise RuntimeError("Assertions required.")
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess, sys
NS = Path(__file__).resolve().parent
ROOT = NS.parents[1]
BASE = NS / "release"
SHA = "b20685d1670b33b941b1bfcb902638a879c01b93"
PREVIOUS = "f6b1a9c201f7014d25e0573fa0d204c104894d42"
read = lambda p: json.loads(Path(p).read_text())
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()
sys.path.insert(0, str(BASE))
from require_completed_gate import require_completed_gate
require_completed_gate(BASE, SHA)
gate = read(BASE / "full-gate-verified.json")
acceptance = read(BASE / "published-acceptance-sequence.json")
assert acceptance["source_commit"] == SHA and acceptance["status"] == "passed"
assert acceptance["script_sha256"] == digest(NS / "run_published_acceptance.py")
assert acceptance["script_sha256"] == read(BASE / "helper-acceptance-binding.json")["acceptance_runner_sha256"]
assert acceptance["helper_binding_sha256"] == digest(BASE / "helper-acceptance-binding.json")
for name, expected in read(BASE / "helper-acceptance-binding.json")["helpers"].items():
    assert digest(BASE / name) == expected, name
assert [s["name"] for s in acceptance["stages"]] == ["soak", "browser", "image", "readback", "verify_readback"]
for stage in acceptance["stages"]:
    assert stage["status"] == "completed" and stage["exit_code"] == 0
    assert digest(stage["log"]) == stage["log_sha256"]
    for artifact in stage["artifacts"]:
        assert digest(artifact["path"]) == artifact["sha256"]

SOAK = BASE / ("published-soak-" + SHA[:8])
BROWSER = BASE / ("published-browser-" + SHA[:8])
soak = read(SOAK / "summary.json")
browser = read(BROWSER / "summary.json")
final = read(BASE / "readback-verified.json")
image = read(BASE / "public-image-verified.json")
api = read(BASE / "api-release-sequence.json")
wheel = read(BASE / "api-private-wheel-verified.json")
api_health = read(BASE / "api-health-after.json")
saved = read(BASE / "sites-saved-version.json")
deployment = read(BASE / "sites-deployment.json")
visual = read(BASE / "visual-inspection.json")
diagnostics = read(BASE / "diagnostics-reviewed.json")
assert api["status"] == "passed" and api["source_commit"] == SHA
assert wheel["canonical_commit"] == SHA and wheel["pillow_security_version"] == "13.0.0"
assert api_health["source_commit"] == SHA and api_health["read_only"] is True and api_health["writable"] is False
assert deployment["status"] == "succeeded" and deployment["version_id"] == saved["id"] == acceptance["site_version_id"]
assert saved["source"]["commit_sha"] == acceptance["distribution_commit"]
assert soak["passed"] and soak["source_commit"] == SHA
assert soak["observed_soak_requests"] == soak["successful_soak_requests"] == 300
assert soak["soak_http_503_count"] == 0 and soak["verification_requests"] == 7
assert soak["runner_retries"] == 0 and soak["provider_calls_initiated"] == 0
assert final["canonical_commit"] == final["api_commit"] == final["frontend_commit"] == SHA
assert all(final[key] is True for key in ("primary_reads_verified", "collection_unchanged", "knowledge_unchanged", "ledger_unchanged"))
assert (final["claims"], final["provider_calls"], final["original_nine_workflows"], final["original_nine_calls"]) == (159, 42, 9, 18)
assert image["passed"] and image["source_commit"] == SHA and image["local_pillow"] == "13.0.0"
assert visual["source_commit"] == diagnostics["source_commit"] == SHA
assert visual["status"] == diagnostics["status"] == "passed"
assert diagnostics["browser_report_sha256"] == digest(BROWSER / "published-verification.json")
assert diagnostics["unexplained_failures"] == []
assert len(visual["screenshots"]) == 6
assert {row["kind"] for row in visual["screenshots"]} == {"public-desktop", "public-mobile", "review-source", "review-preview", "review-reuse", "review-mobile"}
for shot in visual["screenshots"]:
    path = Path(shot["path"]).resolve()
    assert (path.is_relative_to(BROWSER.resolve()) or path.is_relative_to((NS/"sealed-browser").resolve())) and path.suffix == ".png"
    assert not path.is_symlink() and digest(path) == shot["sha256"]
assert subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SHA
assert not subprocess.check_output(["/usr/bin/git", "status", "--porcelain"], cwd=ROOT, text=True).strip()


sealed=read(NS/"sealed-browser-command.json")
assert sealed["source_commit"]==SHA and sealed["status"]=="passed" and sealed["exit_code"]==0 and sealed["source_clean_after"]
for name,expected in sealed["artifact_hashes"].items():assert digest(NS/"sealed-browser"/name)==expected,name
for filename,session in (("commander-sealed-browser-terminal.json","cp-ns-20261024-sealed-browser"),("commander-acceptance-terminal.json","cp-ns-20261024-published-acceptance")):
 observed=read(BASE/filename);actual=observed.get("result",observed)
 assert actual["sessionId"]==session and actual["state"]=="completed" and actual["exitCode"]==0
qa=read(NS/"sealed-browser/receipt.json")
assert qa["status"]=="passed" and not qa["browser_errors"] and not qa["unexpected_destinations"]
assert qa["mobile"]=={"pageOverflow":0,"panelOverflow":0,"reduced":True,"animations":0}
applied=next(row for row in qa["stages"] if row["stage"]=="later-case-application")
assert applied["target_facts_preserved"] and applied["target_source_bindings_preserved"] and applied["pin"]["version"]==1
assert applied["impact"]["next_action_changed"] is False and applied["impact"]["changed_requirement_document_types"]==[]
local=read(BASE/"local-demo-ready.json")
assert local["source_commit"]==SHA and local["status"]=="passed" and local["get_only"] is True
assert local["journal_unchanged_after_readonly_smoke"] is True
owner=read(NS/"engineering-demo/owner.json")
assert owner["instance_id"]==local["instance_id"] and owner["source_commit"]==SHA
assert owner["review_actions_at_startup"]==0 and owner["original_qa_data_preserved"] is True
assert owner["target_pin"]==applied["pin"] and owner["qualified_human_approval"] is False



restart=read(BASE/"local-demo-restart-verified.json")
current_server=read(NS/"engineering-demo/current-server.json")
assert restart["source_commit"]==current_server["source_commit"]==SHA and restart["status"]=="passed"
assert restart["instance_id"]==current_server["instance_id"]==owner["instance_id"]
assert restart["boot_id"]==current_server["boot_id"] and restart["pid"]==current_server["pid"]
assert restart["current_server_receipt_sha256"]==digest(NS/"engineering-demo/current-server.json")
assert restart["resume_launcher_sha256"]==digest(BASE/"resume_existing_review_qa.py")
for key in ("known_owned_initial_process_terminated","actual_initial_terminal_observed","resumed_process_observed_running","get_only","initial_owner_preserved","initial_copy_receipt_preserved","original_qa_files_unchanged","current_claim_and_work_journals_unchanged","source_and_target_views_unchanged"):
 assert restart[key] is True,key
assert restart["copied_or_reset_data"] is False and restart["seeded_or_replayed_work"] is False
for filename,expected in restart["commander_evidence"].items():assert digest(BASE/filename)==expected,filename

CAPTURE=BASE/"eight-state-capture-recovered"
FILM=BASE/"public-film-review"
FIDELITY=BASE/"northstar-fidelity"
artifacts=read(BASE/"northstar-artifacts-recovery-sequence.json")
assert artifacts["status"]=="passed" and artifacts["source_commit"]==SHA and artifacts["source_clean_after"]
assert artifacts["script_sha256"]==digest(NS/"run_northstar_artifacts_recovered.py")
observed=read(BASE/"commander-artifacts-recovery-terminal.json");actual=observed.get("result",observed)
assert actual["sessionId"]=="cp-ns-20261024-northstar-artifacts-recovered" and actual["state"]=="completed" and actual["exitCode"]==0
recovery_binding=read(NS/"evidence-recovery-prepared.json")
assert recovery_binding["source_commit"]==SHA and recovery_binding["status"]=="prepared"
assert digest(__file__)==recovery_binding["final_evidence_generator_sha256"]
assert digest(NS/"evidence-recovery-prepared.json")==artifacts["helper_binding_sha256"]
original_binding=read(NS/"evidence-helpers-prepared.json")
assert digest(NS/"prepare_final_evidence.py")==original_binding["final_evidence_generator_sha256"]
assert digest(NS/"run_northstar_artifacts.py")==original_binding["artifact_runner_sha256"]
for name,expected in original_binding["artifact_helpers"].items():assert digest(BASE/name)==expected,name
for name,expected in recovery_binding["artifact_helpers"].items():assert digest(BASE/name)==expected,name
original_artifacts=read(BASE/"northstar-artifacts-sequence.json")
original_terminal=read(BASE/"commander-artifacts-failed-terminal.json")["result"]
assert original_artifacts["status"]=="failed"
assert original_terminal["sessionId"]=="cp-ns-20261024-northstar-artifacts" and original_terminal["state"]=="failed" and original_terminal["exitCode"]==1
assert artifacts["original_failed_sequence_sha256"]==digest(BASE/"northstar-artifacts-sequence.json")
assert artifacts["original_failed_terminal_sha256"]==digest(BASE/"commander-artifacts-failed-terminal.json")
assert artifacts["original_failed_capture_sha256"]==digest(BASE/"eight-state-capture/eight-state-evidence.json")
assert artifacts["carried_forward_stages"]==original_artifacts["stages"][:2]
assert [row["name"] for row in artifacts["carried_forward_stages"]+artifacts["stages"]]==["film_frames","contact_sheet","eight_states","fidelity"]
forensics=read(BASE/"operation-trace-forensics/identity-review.json")
assert forensics["status"]=="passed" and forensics["source_commit"]==SHA
assert artifacts["trace_forensics_sha256"]==recovery_binding["trace_forensics_sha256"]==digest(BASE/"operation-trace-forensics/identity-review.json")
forensics_terminal=read(BASE/"commander-trace-forensics-terminal.json")["result"]
assert forensics_terminal["sessionId"]=="cp-ns-20261024-trace-forensics" and forensics_terminal["state"]=="completed" and forensics_terminal["exitCode"]==0
for row in forensics["claims"]:
 assert row["official_checkedOperation_all_passed"] and row["final_binding_verified"]
 for file_key,sha_key in (("trace_file","trace_sha256"),("state_file","state_file_sha256"),("difference_file","difference_sha256")):
  assert digest(BASE/"operation-trace-forensics"/row[file_key])==row[sha_key]
repair=read(BASE/"runtime-cache-repair.json")
assert repair["status"]=="passed" and repair["all_recorded_entries_unchanged"] and repair["recorded_entries"]==4147
local_terminal=read(BASE/"commander-local-handoff-terminal.json")["result"]
assert local_terminal["sessionId"]=="cp-ns-20261024-local-handoff-verified" and local_terminal["state"]=="completed" and local_terminal["exitCode"]==0
for stage in artifacts["carried_forward_stages"]+artifacts["stages"]:
 assert stage["status"]=="completed" and stage["exit_code"]==0
 assert digest(stage["log"])==stage["log_sha256"]
 assert digest(stage["artifact"]["path"])==stage["artifact"]["sha256"]
eight=read(CAPTURE/"eight-state-evidence.json")
assert eight["source_commit"]==SHA and eight["status"]=="passed"
assert [row["state"] for row in eight["states"]]==list(range(1,9))
assert not eight["errors"] and not eight["writes"]
assert eight["trace_forensics_sha256"]==digest(BASE/"operation-trace-forensics/identity-review.json")
assert len(eight["live_trace_validations"])==2
for row in eight["live_trace_validations"]:
 proof=next(item for item in forensics["claims"] if item["claim_id"]==row["claim_id"])
 assert row["trace_sha256"]==proof["trace_sha256"] and row["state_sha256"]==proof["state_sha256"]
 assert row["official_checkedOperation_all_passed"] and row["final_binding_verified"]
assert eight["literal_state_8_expert_review_acceptance"] is False
assert next(row for row in eight["states"] if row["state"]==5)["recorded_relationship"]["fact_count"]>=2
for row in eight["states"]:
 assert (row["width"],row["height"])==(1440,900) and digest(CAPTURE/row["file"])==row["sha256"]
public_detail=read(BROWSER/"published-verification.json")
public_video=BROWSER/"public-walkthrough.webm"
assert public_detail["expected_commit"]==SHA and public_detail["film"]["reached_end"] and public_detail["film"]["four_x_seen"]
assert digest(public_video)==public_detail["film"]["video_sha256"]
frames=read(FILM/"frames-index.json")
assert frames["source_commit"]==SHA and frames["status"]=="passed" and frames["decoded_frames"]==24
assert frames["video_sha256"]==digest(public_video) and frames["synthetic_or_seeked_browser_frames"] is False
for frame in frames["frames"]:assert digest(FILM/frame["file"])==frame["sha256"]
sheet=read(FILM/"contact-sheet.json")
assert sheet["source_commit"]==SHA and sheet["frame_index_sha256"]==digest(FILM/"frames-index.json")
assert digest(FILM/sheet["file"])==sheet["sha256"]
cold=read(FILM/"cold-viewer-review.json")
assert cold["source_commit"]==SHA and cold["frame_index_sha256"]==digest(FILM/"frames-index.json")
assert cold["video_sha256"]==digest(public_video) and cold["reviewed_frame_numbers"]==list(range(1,25))
assert cold["fresh_reviewer_without_project_history"] is True and cold["accepted_for_silent_film_clarity"] is True
assert all(isinstance(cold["answers"].get(key),str) and cold["answers"][key].strip() for key in ("what_it_does","how_it_reaches_results","why_valuable","what_was_unclear"))
fidelity=read(FIDELITY/"fidelity-measurements.json")
fidelity_review=read(FIDELITY/"visual-review.json")
assert fidelity["source_commit"]==SHA and fidelity["status"]=="measured" and len(fidelity["comparisons"])==3
assert fidelity_review["source_commit"]==SHA and fidelity_review["status"]=="passed" and fidelity_review["pending"]==[]
assert fidelity_review["measurement_sha256"]==digest(FIDELITY/"fidelity-measurements.json")
for comparison in fidelity["comparisons"]:
 for artifact in comparison["outputs"]:assert digest(FIDELITY/artifact["file"])==artifact["sha256"]
motion_modules=["casepath-qa/autonomous-presentation-browser-v1.test.cjs","casepath-qa/autonomous-northstar-v1.test.cjs"]
for module in motion_modules:assert any(Path(module).name in str(item) for item in gate["frontend_suites_required"])

bundle=NS/"final-evidence-bundle"
assert not bundle.exists()
bundle.mkdir()
index={"contract":"casepath.northstar-final-evidence/1","tested_and_deployed_source":SHA,"generated_at":now(),"generator_sha256":digest(__file__),"product_changes":False,"copies":[],"derived":[]}
copies=[
 (BASE/"full-gate-verified.json","full-gate.json"),(BASE/"gate-actual-completion.json","gate-actual-completion.json"),
 (BASE/"commander-gate-terminal.json","commander-gate-terminal.json"),(NS/"source-binding.json","source-binding.json"),
 (NS/"independent-review.json","independent-review.json"),(NS/"sealed-browser-command.json","sealed-browser-command.json"),
 (BASE/"commander-sealed-browser-terminal.json","commander-sealed-browser-terminal.json"),
 (NS/"sealed-browser/receipt.json","review-browser-receipt.json"),(NS/"sealed-browser/review-walkthrough.webm","review-walkthrough.webm"),
 (BASE/"api-private-wheel-verified.json","api-wheel-verification.json"),(BASE/"api-health-after.json","api-health.json"),
 (BASE/"api-deployment-uploaded.json","api-deployment.json"),(BASE/"sites-saved-version.json","sites-saved-version.json"),
 (BASE/"sites-deployment.json","sites-deployment.json"),(BASE/"published-acceptance-sequence.json","published-acceptance-sequence.json"),
 (BASE/"commander-acceptance-terminal.json","commander-acceptance-terminal.json"),
 (SOAK/"summary.json","published-soak-summary.json"),(BROWSER/"summary.json","published-browser-summary.json"),
 (BASE/"public-image-verified.json","public-image-verification.json"),(BASE/"readback-verified.json","readback-verified.json"),
 (BASE/"visual-inspection.json","visual-inspection.json"),(BASE/"diagnostics-reviewed.json","diagnostics-reviewed.json"),
 (BASE/"local-demo-ready.json","local-demo-ready.json"),(NS/"engineering-demo/owner.json","local-demo-owner.json"),
 (NS/"engineering-demo/data-copy.json","local-demo-copy.json"),(BASE/"serve_existing_review_qa.py","serve_existing_review_qa.py"),
]
copies += [(Path(row["path"]),row["kind"]+".png") for row in visual["screenshots"]]
if (BASE/"api-build-version.json").exists():copies.append((BASE/"api-build-version.json","api-build-version.json"))
copies += [
 (NS/"full-gate.log","full-gate.log"),(NS/"full-gate-command.json","full-gate-command.json"),
 (NS/"sealed-browser-command.log","sealed-browser-command.log"),
 (BROWSER/"published-verification.json","published-verification.json"),(public_video,"public-walkthrough.webm"),
 (BASE/"northstar-artifacts-sequence.json","northstar-artifacts-original-failed-sequence.json"),(BASE/"commander-artifacts-failed-terminal.json","commander-artifacts-failed-terminal.json"),
 (BASE/"northstar-artifacts-recovery-sequence.json","northstar-artifacts-recovery-sequence.json"),(BASE/"commander-artifacts-recovery-terminal.json","commander-artifacts-recovery-terminal.json"),
 (CAPTURE/"eight-state-evidence.json","eight-state-evidence.json"),
 (FILM/"frames-index.json","frames-index.json"),(FILM/"video-metadata.log","public-video-metadata.log"),
 (FILM/"contact-sheet.json","contact-sheet.json"),(FILM/"film-contact-sheet.png","film-contact-sheet.png"),
 (FILM/"cold-viewer-review.json","cold-viewer-review.json"),
 (FIDELITY/"fidelity-measurements.json","fidelity-measurements.json"),(FIDELITY/"visual-review.json","fidelity-review.json"),
 (NS/"evidence-helpers-prepared.json","evidence-helpers-prepared.json"),
 (NS/"run_northstar_artifacts.py","run_northstar_artifacts.py"),
]
copies += [(CAPTURE/row["file"],row["file"]) for row in eight["states"]]
copies += [(FILM/row["file"],row["file"]) for row in frames["frames"]]
for comparison in fidelity["comparisons"]:
 copies += [(FIDELITY/row["file"],row["file"]) for row in comparison["outputs"]]
for name in ("capture_eight_states.mjs","decode_public_film.py","make_film_contact_sheet.mjs","measure_northstar_fidelity.py"):
 copies.append((BASE/name,name))

copies += [
 (BASE/"local-demo-restart-verified.json","local-demo-restart-verified.json"),
 (BASE/"local-demo-before-restart.json","local-demo-before-restart.json"),
 (NS/"engineering-demo/current-server.json","local-demo-current-server.json"),
 (BASE/"resume_existing_review_qa.py","resume_existing_review_qa.py"),
 (BASE/"verify_local_restart.py","verify_local_restart.py"),
]
copies += [(BASE/name,name) for name in restart["commander_evidence"]]

copies += [
 (NS/"evidence-recovery-prepared.json","evidence-recovery-prepared.json"),
 (NS/"run_northstar_artifacts_recovered.py","run_northstar_artifacts_recovered.py"),
 (NS/"prepare_final_evidence.py","prepare_final_evidence_original.py"),
 (Path(__file__),"prepare_final_evidence_recovered.py"),
 (BASE/"capture_eight_states_recovered.mjs","capture_eight_states_recovered.mjs"),
 (BASE/"measure_northstar_fidelity_recovered.py","measure_northstar_fidelity_recovered.py"),
 (BASE/"eight-state-capture/eight-state-evidence.json","eight-state-original-failed-evidence.json"),
 (BASE/"northstar-eight_states-command.log","northstar-original-failed-capture-command.log"),
 (BASE/"operation-trace-forensics/identity-review.json","operation-trace-identity-review.json"),
 (BASE/"inspect_trace_forensics.mjs","inspect_trace_forensics.mjs"),
 (BASE/"commander-trace-forensics-terminal.json","commander-trace-forensics-terminal.json"),
 (BASE/"runtime-cache-repair.json","runtime-cache-repair.json"),
 (BASE/"quarantine_generated_cache.py","quarantine_generated_cache.py"),
 (BASE/"commander-standard-failed-terminal.json","commander-standard-failed-terminal.json"),
 (BASE/"commander-standard-running.json","commander-standard-running.json"),
 (BASE/"commander-local-handoff-terminal.json","commander-local-handoff-terminal.json"),
 (BASE/"local-restart-early-probe.json","local-restart-early-probe.json"),
 (BASE/"commander-trace-identity-failed-terminal.json","commander-trace-identity-failed-terminal.json"),
 (BASE/"inspect_trace_identity.mjs","inspect_trace_identity.mjs"),
 (BASE/"commander-readonly-diagnostic-terminal.json","commander-readonly-diagnostic-terminal.json"),
]
for stage in artifacts["carried_forward_stages"]+artifacts["stages"]:
 copies.append((Path(stage["log"]),Path(stage["log"]).name))
for row in read(BASE/"eight-state-capture/eight-state-evidence.json")["states"]:
 copies.append((BASE/"eight-state-capture"/row["file"],"failed-"+row["file"]))
for row in forensics["claims"]:
 for key in ("trace_file","state_file","difference_file"):
  copies.append((BASE/"operation-trace-forensics"/row[key],row[key]))
assert len({name for _,name in copies})==len(copies),"No evidence filename collisions"
for source,name in copies:
 raw=source.read_bytes()
 if name.endswith(".json"):json.loads(raw)
 with (bundle/name).open("xb") as f:f.write(raw)
 index["copies"].append({"file":name,"source_receipt":str(source),"original_sha256":digest(source),"committed_copy_sha256":digest(bundle/name),"byte_identical":True,"bytes":len(raw)})
def derived(name,text):
 p=bundle/name
 with p.open("x") as f:f.write(text)
 index["derived"].append({"file":name,"sha256":digest(p),"bytes":p.stat().st_size})
release={"contract":"casepath.northstar-demo-acceptance/1","completed_at":now(),"tested_and_deployed_source":SHA,"previous_live_source":PREVIOUS,"site_url":deployment["url"],"site_version_number":saved["version_number"],"site_version_id":saved["id"],"site_deployment_id":deployment["id"],"distribution_commit":saved["source"]["commit_sha"],"api_url":"https://casepath-agent.fastapicloud.dev","api_deployment_id":read(BASE/"api-deployment-uploaded.json")["deployment_id"],"public_read_only":True,"new_provider_workflows_started":0,"original_nine_repeated":False,"source_manifest_sha256":gate["manifest_sha256"],"gate_proof_sha256":digest(BASE/"full-gate-verified.json"),"sealed_review_sha256":digest(NS/"sealed-browser/receipt.json"),"soak_summary_sha256":digest(SOAK/"summary.json"),"browser_summary_sha256":digest(BROWSER/"summary.json"),"readback_verification_sha256":digest(BASE/"readback-verified.json"),"primary_final_reads":True,"collection_unchanged":True,"knowledge_unchanged":True,"ledger_unchanged":True,"engineering_eight_state_coverage_verified":True,"coverage_scope":eight["coverage_scope"],"literal_state_8_expert_review_acceptance":False,"eight_state_evidence_sha256":digest(CAPTURE/"eight-state-evidence.json"),"cold_viewer_review_sha256":digest(FILM/"cold-viewer-review.json"),"fidelity_review_sha256":digest(FIDELITY/"visual-review.json"),"qualified_human_approval":"pending; Test handler is engineering QA","claim_outcome_authorized":False,"evidence_commit_is_separate":True,"local_restart_rehearsed":True,"local_restart_proof_sha256":digest(BASE/"local-demo-restart-verified.json"),"local_engineering_demo":"http://127.0.0.1:4194/?journey=review&view=northstar","local_standard_workspace":"http://127.0.0.1:4173/?journey=review&view=northstar"}
release.update(artifact_capture_recovered=True,original_artifact_failure_preserved=True,live_trace_identity_verified=True,artifact_recovery_sequence_sha256=digest(BASE/"northstar-artifacts-recovery-sequence.json"),runtime_cache_repair_sha256=digest(BASE/"runtime-cache-repair.json"),cold_review_is_independent_assistant_not_human=True)
derived("release-acceptance.json",json.dumps(release,indent=2)+"\n")

motion={"contract":"casepath.motion-gate-mapping/1","source_commit":SHA,"verified_via_completed_strict_gate":True,"gate_proof_sha256":digest(BASE/"full-gate-verified.json"),"actual_completion_sha256":digest(BASE/"gate-actual-completion.json"),"additional_motion_run_claimed":False,"asserted_timeline_frames":5283,"modules":[{"path":module,"sha256":digest(ROOT/module)} for module in motion_modules],"coverage":["All timeline frames have intact rows, facts and labels and only the current recorded spinner","Recorded source pin, exact Unicode quote and bounds match the current fact or completion","Cursor arrival precedes highlight; source swap and camera motion do not prematurely highlight","Plan rows, roles and accepted node order remain bound to all nine recorded operation histories"],"published_playback":{"duration_ms":public_detail["film"]["duration_ms"],"reached_end":public_detail["film"]["reached_end"],"four_x_seen":public_detail["film"]["four_x_seen"],"video_sha256":digest(public_video)}}
derived("motion-evidence.json",json.dumps(motion,indent=2)+"\n")

p95=max(row["latency_ms"]["p95"] for row in soak["routes"].values())/1000
maximum=max(row["latency_ms"]["max"] for row in soak["routes"].values())/1000
fallback=soak["last_verified_soak_count"]
source_link="http://127.0.0.1:4194/?journey=review&view=northstar#claim=clm_f69b1747447bc221"
target_link="http://127.0.0.1:4194/?journey=review&view=northstar#claim=clm_0e538990cc6ba7ef"
readme=f"""# CasePath north-star review journey — verified engineering release

**Tested and deployed source: {SHA}. Sites version {saved['version_number']}.**

[Public CasePath]({deployment['url']}) · [Recorded presentation]({deployment['url']}/?present=1#autonomous/demonstration) · [Two-case presenter guide](demo-operator-guide.md) · [Recorded operator walkthrough](review-walkthrough.webm)

This evidence-only child commit records actual completed checks and deployment. It changes no sealed product file. The API and Site identify the tested source above; the later integration HEAD adds this handoff.

## What is now implemented

The local operator workspace keeps the original source reader and the working process graph together. Its five roles use the existing claim authority. An operator can select a graph step, edit a decision, inspect real before/after effects before saving, validate a selected structure, save an exact fragment version, and explicitly apply that version in another case.

The receiving case exposes its own source dates alongside the saved version and the actual added prerequisite. It keeps its own facts, original source bindings, held-document review states and earlier process connections. A newer source version does not silently replace the saved pin. Stale preview, claim-navigation and accepted-save races are guarded; accepted saves recover by reading current authority, without replaying a POST.

The public demonstration remains read-only. The editable completed example is an isolated engineering copy on the owner's Mac; its recorded actor is **Test handler**. It is not a human or expert approval.

## The demonstrated consequence

Both original cases contain a tenant notice stating **30. Juni** and a spouse notice stating **31. Juli**. The original scans and messages remain the evidence. A missing page in a scan does not establish that the original served notice was incomplete.

The QA correction adds **Compare both complete notices** as a prerequisite of **Prepare challenge, extension or settlement**. Resolution was blocked before and remains blocked afterwards. The added prerequisite changes the dependency and the notices' required-step associations. **Preserve challenge or extension deadline** remains the next action; document request timing is unchanged. The earlier evidence connection remains in the graph and cannot be bypassed by completing only the new prerequisite.

The receiving case must still review the imported dependency. Process validation does not authorize the claim outcome. [The source-bound operator review packet](../OPERATOR_REVIEW.md) sets out the remaining qualified judgment.

## Fresh verification

| Check | Observed result |
|---|---|
| Complete sealed gate | {gate['passed']:,} passed; exactly 10 historical skips; no failures, errors, deselections or new skips |
| Frontend gate | All {len(gate['frontend_suites_required'])} declared suites mandatory, including the complete operator browser journey |
| Source seal | {gate['source_files']:,} source files verified before and after; clean tested checkout |
| Sealed operator walkthrough | Actual source-bound terminal exit 0; four screenshots and video; no browser errors or unexpected destinations |
| Review semantics | Source/target facts and bindings preserved; exact version 1 retained after version 2; preview adds no event; outcome authority remains false |
| Repeated-use recovery | Result role and current consequence survive reload; accepted-save and stale-preview race regressions included |
| Mobile operator view | 390 × 844; no document/page overflow; reduced motion enabled; no running animations |
| Published read soak | 300/300 reads; zero 503s; {300-fallback} primary and {fallback} last-verified responses; 7 extra identity/readback checks |
| Published browser | 18 desktop and 9 mobile case views; all observed assets byte-verified, required initial assets present, both new review assets fetched and verified |
| Public presentation | Complete 88.05-second six-act playback; source, law, keyboard, draft and reduced-motion checks |
| Existing API compatibility | Built wheel contains the exact private seed and requires Pillow 13.0.0; deployed original JPEG matches its sealed bytes |
| Final primary readback | Matching API/Site source; case collection, Knowledge and complete reported usage/budget state unchanged |
| Local demo handoff | Exact QA pin/event verified; fresh data copy; startup and read-only smoke append no review event |
| Restart rehearsal | Owned first process fully stopped; existing QA data reopened under a new boot ID; both journals and both case views unchanged |

The highest per-route p95 in this sequential soak was {p95:.3f}s; the maximum was {maximum:.3f}s. These measurements describe this run. The historical skips remain explicit in the full-gate receipt.

All 159 intakes remain, with 42 total reported provider calls. The original nine saved investigations and their 18 provider calls were not repeated. The reported cost remains unchanged. The usage comparison covers the complete status.limits projection; it does not claim a raw ledger-row comparison.

## Eight states, motion and visual evidence

[Eight-state evidence](eight-state-evidence.json) binds six deterministic inspections of the actual public recording and two screenshots of the actual sealed operator run to this source. The accepted process question links to at least two distinct recorded facts. The preserved W10/W11 film shows the current source-matched fact one at a time; the underlying operation history retains the earlier contributors.

[The continuous public film](public-walkthrough.webm) was recorded at 1440 × 900. [The 24-frame index](frames-index.json) identifies evenly spaced frames decoded from that finalized video, including its actual opening and end. They are distinct from the deterministic state stills. [The fresh cold-viewer response](cold-viewer-review.json) records the four required answers without project-history context. [Motion evidence](motion-evidence.json) maps the completed strict gate to its recorded source, cursor, role and 5,283-frame geometry checks.

[Concept measurements](fidelity-measurements.json) and [the inspected deviations](fidelity-review.json) accompany the three side-by-side/overlay/difference sets. A pixel difference is a measurement, not a semantic acceptance score. No unresolved visual deviation remains in that review; qualified substantive review remains separate.

![24 frames from the continuous public recording](film-contact-sheet.png)

## What still requires a person

Engineering coverage of all eight stage categories is verified by recorded presentation evidence and the isolated Test handler correction/reuse run. Literal state 8 still requires qualified human approval of the exact reusable version. A qualified reviewer must decide whether this additional notice-comparison prerequisite, its scope and completion criterion are appropriate for reuse, while preserving protective actions and deadlines. No automated test, typed actor name or green process marker supplies that judgment.

## Recovered checks and retained observations

The first evidence-only eight-state capture stopped because it compared live operations against an older fixture from a different journal/reuse context. The original failed sequence, terminal result, log and four captured states remain in this packet. The recovery uses actual served claim states and complete live operation histories, verifies all 856 operations with the unchanged application validator, and checks every stream hash and final binding. The recovered capture must match those independently captured live bytes. No chain hash was discarded to make a comparison pass.

The standard local launcher initially rejected generated Python bytecode outside its sealed dependency roster. All 4,147 recorded entries were unchanged. The 179 generated extras were quarantined, the unchanged exact-closure validator passed, and the original boot receipt remained intact. Both local servers then passed the GET-only handoff. The earlier restart probe that ran before readiness and the incidental diagnostic browser/HTTP failures are also retained and classified.

The independent assistant cold viewer accepted purpose, mechanism and value without a briefing, while noting the temporary opening-case/loading screen, dense legal text, and limited explanation of checklist construction. This is an assistant visual assessment, not a human approval. Open the public link and wait for its introduction before presenting; pause on evidence or law when explanation is needed. The local review journey supplies the separate direct-edit/save/reuse demonstration.

## Evidence

[Release identities](release-acceptance.json) · [Full gate](full-gate.json) · [Complete gate log](full-gate.log) · [Actual gate completion](gate-actual-completion.json) · [Independent review](independent-review.json) · [Operator receipt](review-browser-receipt.json) · [Published acceptance](published-acceptance-sequence.json) · [Soak](published-soak-summary.json) · [Browser](published-browser-summary.json) · [Detailed browser evidence](published-verification.json) · [Primary readback](readback-verified.json) · [Reviewed diagnostics](diagnostics-reviewed.json) · [Hash index](evidence-manifest.json)

![Later-case reuse and its own source dates](review-reuse.png)

![Actual before/after preview](review-preview.png)
"""
derived("README.md",readme)
guide=f"""# CasePath presenter guide

Tested and deployed source: {SHA}

## Open the completed example

Use a 1440 × 900 browser window for the reference layout.

1. Open [the earlier case]({source_link}) on the owner's Mac. This is an isolated engineering demo with recorded Test handler actions. Select Process builder to inspect the added Compare both complete notices step and its connection. Use the source rail to inspect the original tenant and spouse PDFs.
2. Open [the receiving case]({target_link}). Select Result checker. The graph and own source reader stay present.
3. Show the two original receiving-case date passages: 30. Juni and 31. Juli. Click either source fact to open that case's exact source.
4. Show Exact saved version 1, its source-case link and version provenance. The source library also contains version 2; this receiving case still pins version 1.
5. Show the current effect: Prepare challenge, extension or settlement now also requires Compare both complete notices. Resolution remains blocked. The earlier evidence connection is retained, and Preserve challenge or extension deadline remains next.
6. Open When applied to inspect the actual historical before/after comparison. Separate that recorded change from the current evaluation shown above it.
7. Reload the receiving case. Result and the version pin are retained in that browser. For a fresh browser, choose Result checker again.

The [video](review-walkthrough.webm) records the actual edit, preview, accept, save and reuse interactions. It is evidence from the isolated deterministic run. Its Test handler events are engineering QA and do not authorize a real claim outcome.

## Public demonstration

Open the presentation before screen sharing and wait for its introduction/start control. The free host may need time to wake, and the recorded cold opening can briefly show a different loading case. The actual six-act presentation lasts 88.05 seconds. Pause on dense evidence or law text as needed; the film is a recorded fictional example, and the local review workspace is the editable demonstration.

[Open the public presentation]({deployment['url']}/?present=1#autonomous/demonstration). Start it once and let all six acts finish. The public site reviews recorded fictional cases and remains read-only. Its draft editor saves a local browser copy and does not send a message.

## Normal review workspace

The normal local workspace is available at http://127.0.0.1:4173/?journey=review&view=northstar. It uses its existing separate data directory. The completed engineering example uses port 4194 and an independently copied QA data directory. Its startup does not seed, start or replay investigations; opening it does not start a batch.

Edits made in the engineering example create real new events only in that isolated copy. The original sealed QA data and the public saved histories remain separate. Keep the original evidence receipt when rehearsing; do not relabel Test handler as a qualified human reviewer.

## Qualified review

Open [OPERATOR_REVIEW.md](../OPERATOR_REVIEW.md) for the exact original file identities, dates, proposed completion criterion and the decision that remains with a qualified reviewer. The concrete question is whether this prerequisite should be accepted for reuse and under what scope, without obstructing protective actions. The UI's process review is distinct from approval of a claim outcome.

## Recovery

The local servers run in owned Commander sessions on the owner's Mac. [The current server receipt](local-demo-current-server.json) identifies the restarted process, boot ID and Commander session. [The initial owner receipt](local-demo-owner.json) remains historical. [The actual stop/start rehearsal](local-demo-restart-verified.json) preserves both claim views, the claim journal and the work journal.

If the completed example is already running, use its existing URL. Once its recorded owned process has fully stopped, the following command reopens the same QA store without copying, resetting, seeding or replaying work. It refuses a concurrent owner and verifies the sealed source and original QA ancestry.

```bash
/usr/bin/env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC PYTHONDONTWRITEBYTECODE=1 CASEPATH_MODEL_MODE=deterministic_reference CASEPATH_AGENT_WORK_EXTERNAL_FACTS=0 CASEPATH_DEMO_SESSION=manual-terminal \\
  '{ROOT}/.runtime/casepath-dev-v2/venv/bin/python' -I -B -P \\
  '{BASE}/resume_existing_review_qa.py'
```

Keep that terminal open while using the demo. A future legitimate QA edit is preserved across restart; this command does not restore the original screenshot state. Do not rerun a mutation or overwrite a journal to repair an uncertain result. The normal workspace and completed example use separate stores; restarting one is not a reset of the other.

For a meeting, first open the two local links and the public presentation. The completed read soak and browser receipts describe the tested release; they are not a promise of future network availability.
"""
derived("demo-operator-guide.md",guide)
with (bundle/"evidence-manifest.json").open("x") as f:json.dump(index,f,indent=2);f.write("\n")
result={"source_commit":SHA,"bundle":str(bundle),"files":len(list(bundle.iterdir())),"manifest_sha256":digest(bundle/"evidence-manifest.json"),"status":"prepared"}
with (NS/"final-evidence-prepared.json").open("x") as f:json.dump(result,f,indent=2);f.write("\n")
print(json.dumps(result),flush=True)
