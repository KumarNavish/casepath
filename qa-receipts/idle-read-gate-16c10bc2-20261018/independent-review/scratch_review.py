from pathlib import Path
import hashlib,json,os,subprocess,time
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');O=R/'independent-review'
def read(p):return json.loads(p.read_text())
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(c,p):return subprocess.check_output(['git','--no-optional-locks','show',c+':'+p],cwd=G,env=dict(os.environ,GIT_NO_LAZY_FETCH='1'))
proof=read(R/'future-admission-scratch-proof.json');retired=read(R/'future-admission-scratch-retirement.json');c='955e7fff4b1a9ae3bcd7d0b6c4a82b75f999d949'
assert blob(c,'qa-receipts/idle-read-gate-16c10bc2-20261018/future-admission-scratch-proof.json')==(R/'future-admission-scratch-proof.json').read_bytes()
allowed={f'/workspace/casepath-outcome-wait-gate-8f230fd4-20261018/shard{n}/pytest-tmp' for n in [5,6]}|{f'/workspace/casepath-touch-target-gate-4bf9b439-20261018/shard{n}/pytest-tmp' for n in [4,5,6]}
assert {x['path'] for x in proof['paths']}==allowed and proof['owned_processes']==[] and proof['no_search_beyond_explicit_paths']
assert {x['path'] for x in retired['retired_only']}==allowed and retired['owned_jobs_before_delete']==[] and retired['actual_remote_proof_bytes_match'] and retired['all_prior_raw_source_Git_and_DBs_outside_approved_tmp_preserved'] and retired['active_current_shard_untouched']
prior=Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018');sums=(prior/'SHA256SUMS').read_text().splitlines();assert len(sums)==380
for row in sums:
 stated,name=row.split(None,1);assert h(prior/name.strip().removeprefix('*'))==stated
assert blob('5366ea3eb1125230661dd2f31f1e3156447997e8','qa-receipts/touch-target-gate-4bf9b439-20261018/SHA256SUMS')==(prior/'SHA256SUMS').read_bytes()
f='coordinator/retire_pushed_runtime.py';before=blob('a1b16eb8842fe3389e5765e8c5378318ab3efc20','qa-receipts/idle-read-gate-16c10bc2-20261018/'+f).decode();after=(R/f).read_text()
added=after[after.index("public = repo / 'casepath-public'"):after.index('paths = [')]
assert "not public.is_symlink()" in added and "git','check-ignore','-q','casepath-public'" in added and 'assert not item.is_symlink()' in added and "static_file_count']==40" in added and "canonical(static_rows)" in added and "after['capsule_receipt']['static_inventory_sha256']" in added
normalized=after.replace(added,'').replace("out / 'uv-cache', public]","out / 'uv-cache']")
for line in ["          'completed_generated_static_inventory': static_rows,\n","          'completed_generated_static_matches_remotely_pushed_receipt': True,\n","          'current_generated_static_retirement_authorized_by_parent': True,\n"]:normalized=normalized.replace(line,'')
assert normalized==before
value={'status':'PASS_SCOPED_SCRATCH_AND_HOOK_REVIEW','candidate':proof['candidate'],'reviewer':'/root/gate_4bf_review','reviewed_epoch':time.time(),'immutable_proof_commit':c,'proof_bytes_identical':True,'exact_five_parent_authorized_old_passed_pytest_tmp_paths_only':True,'old4bf380_checksum_targets_preserved':True,'old8f376_targets_previously_verified_in_preflight_review':True,'no_owned_jobs_reported_before_retirement':True,'current_completed_static_hook_only_extension':True,'static_hook_nonlink_ignored_40rows_canonical_hash_matches_remotely_bound_capsule':True,'test_prepare_selection_and_admission_unchanged':True,'bindings':{n:h(R/n) for n in ['future-admission-scratch-proof.json','future-admission-scratch-retirement.json',f]},'limits':['Reviewer made no deletions, process probes, tests, prepare calls, or network requests.','Current static retirement is permitted only after the same completed terminal/raw/static proofs are byte-bound in pushed evidence; each actual per-shard retirement will be reconciled in final review.']};p=O/'scratch-hook-review.json';p.write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':h(p),'status':value['status']}))
