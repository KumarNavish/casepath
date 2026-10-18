from pathlib import Path
import hashlib,json,os,subprocess,time
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');O=R/'independent-review'
OLD=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018')
SHA='16c10bc21c1b2b3b6602cb028028adf28e20823b';MAN='e7fbfd43062c19ed04468966aee9a2c61dcb1064b8baaa449cd4a2fe841e0442'
BASE='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59';BMAN='0d713ebe1ea45681c139ac8ed39b5d9c811cdfb6ea08af55617e155ecf60c2b8';REVIEWED='023a9d1365d94f4c84a4c59dbacbc2dae871ec92'
def read(p):return json.loads(p.read_text())
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(repo,*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=repo,env=dict(os.environ,GIT_NO_LAZY_FETCH='1'))
def save(n,d):
 d.update(candidate=SHA,manifest_sha256=MAN,reviewer='/root/gate_4bf_review',reviewed_epoch=time.time());p=O/n;p.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':h(p),'status':d['status']}))
m=read(R/'source-manifest.json');assert h(R/'source-manifest.json')==MAN and m['file_count']==len(m['files'])==1719
repos=read(R/'clone-map.json')['repos'];source=[]
for n,p in repos.items():
 repo=Path(p);assert (repo/'.git').is_dir() and not (repo/'.git').is_symlink()
 assert git(repo,'rev-parse','HEAD').decode().strip()==SHA and git(repo,'status','--porcelain')==b''
 assert git(repo,'show',SHA+':casepath/source-manifest.json')==(R/'source-manifest.json').read_bytes()
 for row in m['files']:
  f=repo/row['path'];assert not f.is_symlink() and f.stat().st_size==row['size_bytes'] and h(f)==row['sha256']
 assert not (repo/'casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json').exists()
 source.append({'shard':n,'repo':p,'normal_clone':True,'head':SHA,'status':'','direct_sealed_file_hashes_verified':1719,'optional_package_seed_absent':True})
repo=Path(repos['6']);paths=['casepath-api/casepath_api/hosted_sql_v1.py','casepath-api/tests/test_hosted_idle_transport_v1.py'];bindings={}
for p in paths:
 a=git(repo,'show',REVIEWED+':'+p);b=git(repo,'show',SHA+':'+p);assert a==b==(repo/p).read_bytes();bindings[p]=hashlib.sha256(a).hexdigest()
assert git(repo,'diff','--name-only',BASE,SHA).decode().splitlines()==paths[:1]+paths[1:]+['casepath/source-manifest.json']
instructions={}
for p in ['AGENTS.md','CONTRIBUTING.md','docs/HYBRID_DEVELOPMENT.md']:
 a=git(repo,'show',SHA+':'+p);assert a==git(repo,'show',BASE+':'+p);instructions[p]=hashlib.sha256(a).hexdigest()
save('source-admission.json',{'status':'PASS_SOURCE_ADMISSION','actual_host':'656813ef2295','source_file_count':1719,'reviewed_source_commit':REVIEWED,'reviewed_source_blobs_byte_identical':bindings,'changed_paths_vs_addc':paths+['casepath/source-manifest.json'],'six_clones':source,'instructions_read_immutable_candidate':instructions,'bindings':{n:h(R/n) for n in ['source-manifest.json','clone-map.json','canonical-fetch.json','candidate-diff-vs-addc.json']},'limits':['Read-only source admission; no product test, prepare, provider call, source edit, or process probe by reviewer.','Current Mac127 requires the current candidate owner attestation and is not inferred from prior gates.']})
prov=read(R/'harness-provenance.json');verified=[]
for row in prov['files']:
 assert h(Path(row['source']))==row['source_sha256'] and h(Path(row['target']))==row['target_sha256'];verified.append(row['target'])
for f in ['harness/prepare_clones.py','harness/run_shard.py','harness/verify_prepared_capsules.py','harness/casepath_shard_observer.py','harness/runtime_inventory.py']:
 a=(OLD/f).read_text().replace(str(OLD),str(R)).replace(BASE,SHA).replace(BMAN,MAN).replace('/workspace/rsh','/workspace/ilh').replace('/workspace/rst','/workspace/ilt').replace('1718','1719');assert a==(R/f).read_text(),f
budget=read(R/'heavy-budget.json');assert budget['min_workspace_free_bytes']==3*1024**3 and budget['global_max_heavy']==budget['max_gate_heavy']==2 and budget['actual_serial_schedule_heavy_cap']==1
stage=(R/'coordinator/stage_one.py').read_text();assert 'assert free >= 3 * 1024**3 + 500 * 1024**2' in stage
save('harness-review.json',{'status':'PASS_HARNESS_ADMISSION','provenance_source_and_target_hashes_verified':len(verified),'five_harness_files_equal_validated_addc_after_identity_count_path_substitutions':True,'observer_unchanged':h(R/'harness/casepath_shard_observer.py')==h(OLD/'harness/casepath_shard_observer.py'),'exclusive_original_attempt_latch_no_retry_unchanged':True,'exact_collection_phase_observer_unchanged':True,'sanitized_configured_env_unchanged':True,'actual_serial_cap':1,'global_heavy_cap':2,'disk_floor_bytes':3*1024**3,'prepare_reservation_bytes':500*1024**2,'bindings':{str(Path(p).relative_to(R)):h(Path(p)) for p in verified},'limits':['Configured child isolation only; no environment sampling or new proc audit.','Resource admission does not establish terminal test results.']})
