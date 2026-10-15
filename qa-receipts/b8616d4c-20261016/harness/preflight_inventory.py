import collections,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016')
P=Path('/workspace/casepath-saved-history-gate-5086624c-20261015')
SHA='b8616d4cfd5bf5667587dd1a0bf4ed58e9436d2b'
OLD='5086624c8a024ba298819e5e27d749efbd0cc7fc'
MAN='f96041e43695b6cc82899e4ccf8bb08ade79a69a0b74792acedb40716166f23e'
repo=Path('/workspace/casepath-release-ae0-shard1')
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
prep=json.loads((R/'shard1/prepare.json').read_text());assert prep['exit_code']==0 and prep['after_head']==SHA and prep['after_status']==''
env=prep['env'];cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),'shard1','before']
started=time.time()
with (R/'shard1/verify-before.log').open('x') as f:p=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
save(R/'source-proof-commands.json',[{'name':'shard1','phase':'before','command':cmd,'cwd':str(repo),'env':env,'exit_code':p.returncode,'started_epoch':started,'finished_epoch':time.time()}]);assert p.returncode==0
proof=json.loads((R/'shard1/source-before/capsule-verification.json').read_text())
save(R/'source-verification.json',{'candidate':SHA,'manifest_sha256':MAN,'source_artifact_static_counts':[1709,25,39],'prepared_runtime_clones':1,'source_clones':6,'checks':[proof],'remaining_runtime_preparation':'Just before each shard; sequential capacity-safe scheduling'})
for source,target in [(repo/'casepath/source-manifest.json',R/'source-manifest.json'),(repo/'casepath-api/artifacts/artifact-manifest.json',R/'artifact-manifest.json')]:shutil.copy2(source,target)
known=json.loads((R/'known-skips.json').read_text());mac=(R/'mac-ids.txt').read_text().splitlines()
assert len(known)==10 and len(mac)==len(set(mac))==127 and digest(R/'mac-ids.txt')=='e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'
for name,ids in [('known-skip', [x['id'] for x in known]),('mac-partition',mac)]:
 rows=[]
 for file in sorted({i.split('::')[0] for i in ids}):
  old=subprocess.check_output(['git','show',OLD+':'+file],cwd=repo);new=(repo/file).read_bytes();assert old==new,file
  rows.append({'file':file,'prior_sha256':hashlib.sha256(old).hexdigest(),'current_sha256':hashlib.sha256(new).hexdigest(),'byte_identical':True})
 save(R/(name+'-source-comparison.json'),rows)
try:
 with open('/proc/1/maps') as f:f.read(1)
 audit={'path':'/proc/1/maps','readable':True}
except OSError as e:audit={'path':'/proc/1/maps','readable':False,'error_type':type(e).__name__,'errno':e.errno,'error':str(e)}
audit.update(fail_closed_source_unchanged=True,mac_partition_explicitly_assigned=True,cloud_skips_for_mac_partition=0);save(R/'migration-process-audit.json',audit)
iprep=dict(prep);iprep['env']=dict(env);iprep['env'].update(HOME='/workspace/bh0',TMPDIR='/workspace/bt0',TMP='/workspace/bt0',TEMP='/workspace/bt0',PYTHONPYCACHEPREFIX=str(R/'inventory/pycache'))
save(R/'inventory/prepare.json',iprep)
cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'collect']
with (R/'inventory/collection-wrapper.log').open('x') as f:p=subprocess.run(cmd,cwd=repo,env=iprep['env'],stdout=f,stderr=subprocess.STDOUT)
assert p.returncode==0
rows=json.loads((R/'inventory/collected.json').read_text());ids=[x['id'] for x in rows]
assert len(ids)==len(set(ids))==2613 and set(mac)<=set(ids)
assert collections.Counter(i.split('::')[0] for i in mac)=={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
prior=json.loads((P/'shard-map.json').read_text());prior_ids=(P/'collected-ids.txt').read_text().splitlines();order=(P/'collection-order-ids.txt').read_text().splitlines()
assert sorted(ids)==prior_ids
cloud=[i for i in ids if i not in set(mac)];byfile=collections.defaultdict(list)
for i in cloud:byfile[i.split('::')[0]].append(i)
files=prior['files'];groups={n:[i for f in fs for i in byfile[f]] for n,fs in files.items()}
assigned=[i for g in groups.values() for i in g]
assert len(assigned)==len(set(assigned))==2486 and not set(assigned)&set(mac) and set(assigned)|set(mac)==set(ids)
assert all(x['id'] in assigned for x in known) and groups==prior['shards']
dur=json.loads((P/'per-file-durations.json').read_text());loads={n:sum(dur[f]['phase_seconds'] for f in fs) for n,fs in files.items()}
eq={'candidate':SHA,'prior_candidate':OLD,'fresh_count':len(ids),'prior_count':len(prior_ids),'sorted_ids_identical':True,'collection_order_identical':ids==order,'same_shard_membership_and_order':True,'added_ids':[],'removed_ids':[],'prior_shard_map':str(P/'shard-map.json'),'prior_shard_map_sha256':digest(P/'shard-map.json')};save(R/'fresh-inventory-prior-map-equality.json',eq)
for f,data in [('collected-ids.txt',sorted(ids)),('collection-order-ids.txt',ids),('cloud-assigned-ids.txt',sorted(assigned))]:(R/f).write_text('\n'.join(data)+'\n')
mapping={**prior,'candidate':SHA,'manifest_sha256':MAN,'basis':'Fresh full inventory exactly matches prior complete gate; six whole-file assignments preserved; duration estimates refreshed from prior raw phases; no prior passing result reused','duration_source':str(P/'per-file-durations.json'),'duration_source_sha256':digest(P/'per-file-durations.json'),'shards':groups,'files':files,'counts':{n:len(v) for n,v in groups.items()},'estimated_phase_seconds':loads,'created_epoch':time.time(),'execution_schedule':'Sequential normal clone prepare/run/prove/archive/push/runtime retirement; max heavy is ceiling 3; launch floor 3 GiB'};save(R/'shard-map.json',mapping)
free=shutil.disk_usage('/workspace').free
summary={'candidate':SHA,'prepared':[{'name':'shard1','exit_code':0}],'source_clones':6,'runtime_preparation':'Just before each shard','collection_physical_clone':'shard1','free_bytes':free,'adequate_headroom':free>=3*1024**3,'minimum_headroom_bytes':3*1024**3,'test_execution_started':False};save(R/'prepare-summary.json',summary)
out={'candidate':SHA,'full_inventory':2613,'cloud_assigned':2486,'mac_pending':127,'known_skips':10,'counts':mapping['counts'],'estimated_phase_seconds':loads,'no_overlap_or_gaps':True,'whole_file_partition':True,'collection_physical_clone':'shard1','mac_ids_sha256':digest(R/'mac-ids.txt'),'cloud_ids_sha256':digest(R/'cloud-assigned-ids.txt'),'full_ids_sha256':digest(R/'collected-ids.txt'),'free_bytes':free,'minimum_headroom_bytes':3*1024**3,'adequate_headroom':free>=3*1024**3,'test_run_authorization':'FINAL_GATE_AUTHORIZED','prepared_physical_clones':1,'normal_source_clones':6};save(R/'proof-disjoint-union-before.json',out)
print(json.dumps(out),flush=True)
