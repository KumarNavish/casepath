from pathlib import Path
import hashlib,json,os,subprocess,time
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');O=R/'independent-review';G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
def read(p):return json.loads(p.read_text())
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blob(commit,path):return subprocess.check_output(['git','--no-optional-locks','show',commit+':'+path],cwd=G,env=dict(os.environ,GIT_NO_LAZY_FETCH='1'))
bindings={};proofs=[]
for p,c in [('approved-retirement-proof.json','7d81520bf51369be5a7794aa49010af9305ba6da'),('additional-derived-retirement-proof.json','faca3517e8a14a445b057578facc1b04c76ee9fc')]:
 assert blob(c,'qa-receipts/idle-read-gate-16c10bc2-20261018/'+p)==(R/p).read_bytes();bindings[p]=h(R/p);proofs.append(read(R/p))
focused=proofs[0]
for row in focused['focused_checksums_verified']:
 assert hashlib.sha256(blob(focused['focused_commit'],focused['focused_subtree']+'/'+row['path'])).hexdigest()==row['sha256']
assert focused['owned_targeted_processes']==[] and not focused['parent_seed_env_present'] and focused['cmdline_metadata_unreadable_count']==0
expected={str(Path('/workspace/casepath-idle-read-transport-20261018')/x) for x in ['pytest-tools','proof-tools','pytest-basetemp','proof-pytest-basetemp','tmp']}
first=read(R/'approved-retirement-result.json');assert set(first['retired_only'])==expected and first['owned_targeted_processes_before_delete']==[] and first['remote_actual_proof_bytes_match']
extra=proofs[1];actual=read(R/'additional-derived-retirement-result.json');clones=read(R/'clone-map.json')['repos'];allowed={str(Path('/workspace/casepath-read-seed-gate-addc5a77-20261018')/f'shard{n}/pytest-tmp') for n in range(1,7)}|{str(Path(p)/'casepath-public') for p in clones.values()}|{'/workspace/casepath-outcome-wait-gate-8f230fd4-20261018/shard4/pytest-tmp'}
assert {x['path'] for x in extra['paths']}=={x['path'] for x in actual['retired_only']}==allowed and extra['owned_processes']==actual['no_owned_jobs_before_delete']==[]
assert actual['actual_remote_proof_bytes_matched'] and actual['prepare_guard_satisfied'] and actual['all_source_raw_receipts_phase_JUnit_commands_envs_and_DBs_outside_pytest_tmp_preserved']
floor=3*1024**3;guard=floor+500*1024**2;assert actual['unchanged_admission_bytes']==guard and actual['after_free_bytes']>=guard
conditional=actual['retired_only'][-1];assert conditional['path'].endswith('casepath-outcome-wait-gate-8f230fd4-20261018/shard4/pytest-tmp') and conditional['before_free_bytes']<guard
checksums=[]
for root,c,subtree,expected_count in [(Path('/workspace/casepath-read-seed-gate-addc5a77-20261018'),extra['addc_remote_commit'],'qa-receipts/read-seed-gate-addc5a77-20261018',397),(Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018'),extra['extra8f_pushed_verification']['commit'],'qa-receipts/outcome-wait-gate-8f230fd4-20261018',376)]:
 p=root/'SHA256SUMS';assert blob(c,subtree+'/SHA256SUMS')==p.read_bytes();rows=p.read_text().splitlines();assert len(rows)==expected_count
 for row in rows:
  stated,name=row.split(None,1);name=name.strip().removeprefix('*');assert h(root/name)==stated
 checksums.append({'root':str(root),'immutable_commit':c,'checksums_verified_local':len(rows),'sumfile_blob_identical':True,'sumfile_sha256':h(p)})
admission=read(R/'shard1/prepare-admission.json');assert admission['free_bytes']>=guard and admission['floor_bytes']==floor and admission['reserved_prepare_bytes']==500*1024**2
for n in ['approved-retirement-result.json','additional-derived-retirement-result.json','shard1/prepare-admission.json','heavy-budget.json','initial-resource.json','migration-process-audit.json','process-sampler-qualification.json']:bindings[n]=h(R/n)
d={'status':'PASS_SCOPED_PREFLIGHT','candidate':'16c10bc21c1b2b3b6602cb028028adf28e20823b','reviewer':'/root/gate_4bf_review','reviewed_epoch':time.time(),'immutable_retirement_proof_blobs_exact':True,'focused_preserved_evidence_hashes_verified':len(focused['focused_checksums_verified']),'prior_closed_gate_checksum_bindings':checksums,'retired_paths_within_exact_parent_scope':True,'conditional_extra8f_deletion_only_with_remaining_prepare_guard_deficit':True,'no_active_owned_jobs_reported_before_deletion':True,'source_raw_receipts_and_databases_outside_pytest_tmp_preserved':True,'first_prepare_admission_free_bytes':admission['free_bytes'],'disk_floor_bytes':floor,'unchanged_prepare_guard_bytes':guard,'actual_serial_heavy_cap':1,'global_heavy_cap':2,'bindings':bindings,'limits':['Cleanup was executor-owned; reviewer performed no deletion, prepare, test, network access, or process probe.','Process ownership is based on preserved bounded cmdline/cwd metadata; no environment or proc-map coverage inferred.','Memory is bounded admission/snapshot evidence, not continuous per-child memory observation.','Prior addc permission correction EACCES negative evidence remains preserved; no claim of a current permission failure.']};p=O/'preflight-review.json';p.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':h(p),'status':d['status']}))
