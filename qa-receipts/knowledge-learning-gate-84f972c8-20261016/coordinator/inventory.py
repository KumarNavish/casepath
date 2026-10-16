import collections,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-knowledge-learning-gate-84f972c8-20261016')
P=Path('/workspace/casepath-transport-gate-evidence-git-20261015/qa-receipts/b8616d4c-20261016')
SHA='84f972c86fe556ccf5cac7e2aacddc6e154fdbb9';OLD='b8616d4cfd5bf5667587dd1a0bf4ed58e9436d2b'
MAN='83d09acf9bfae53fd19d5effbae68bf2db2d20d3844938f0c6734454fd0a8382'
repo=Path('/workspace/casepath-release-ae0-shard6')
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
prep=json.loads((R/'shard6/prepare.json').read_text());assert prep['exit_code']==0 and prep['after_head']==SHA and prep['after_status']==''
env=prep['env'];cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/verify_prepared_capsules.py'),'shard6','before'];start=time.time()
with (R/'shard6/verify-before.log').open('x') as f:p=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
save(R/'source-proof-commands.json',[{'name':'shard6','phase':'before','command':cmd,'cwd':str(repo),'env':env,'exit_code':p.returncode,'started_epoch':start,'finished_epoch':time.time()}]);assert p.returncode==0
for source,target in [(repo/'casepath/source-manifest.json',R/'source-manifest.json'),(repo/'casepath-api/artifacts/artifact-manifest.json',R/'artifact-manifest.json')]:shutil.copy2(source,target)
shutil.copy2('/workspace/knowledge-learning-coordinator-20261016/root-sealed-source84.json',R/'root-sealed-source84.json')
known=json.loads((R/'known-skips.json').read_text());mac=(R/'mac-ids.txt').read_text().splitlines();assert len(known)==10 and len(mac)==len(set(mac))==127
for name,ids in [('known-skip',[x['id'] for x in known]),('mac-partition',mac)]:
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
iprep=dict(prep);iprep['env']=dict(env);iprep['env'].update(HOME='/workspace/kh0',TMPDIR='/workspace/kt0',TMP='/workspace/kt0',TEMP='/workspace/kt0',PYTHONPYCACHEPREFIX=str(R/'inventory/pycache'));save(R/'inventory/prepare.json',iprep)
cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(R/'harness/run_shard.py'),'collect']
with (R/'inventory/collection-wrapper.log').open('x') as f:p=subprocess.run(cmd,cwd=repo,env=iprep['env'],stdout=f,stderr=subprocess.STDOUT)
assert p.returncode==0
rows=json.loads((R/'inventory/collected.json').read_text());ids=[x['id'] for x in rows];assert len(ids)==len(set(ids)) and set(mac)<=set(ids)
assert collections.Counter(i.split('::')[0] for i in mac)=={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
prior=json.loads((P/'shard-map.json').read_text());prior_ids=(P/'collected-ids.txt').read_text().splitlines();dur=json.loads((P/'per-file-durations.json').read_text());cloud=[i for i in ids if i not in set(mac)];byfile=collections.defaultdict(list)
for i in cloud:byfile[i.split('::')[0]].append(i)
# Preserve prior whole-file membership and serialized launcher/port groups; add every new file once to the least estimated load.
files={n:[f for f in fs if f in byfile] for n,fs in prior['files'].items()};assigned_files={f for fs in files.values() for f in fs};loads={n:sum(dur.get(f,{}).get('phase_seconds',0) for f in fs) for n,fs in files.items()};estimated={}
for file in sorted(set(byfile)-assigned_files):
 n=min(loads,key=loads.get);estimate=max(5.,len(byfile[file])*1.0);files[n].append(file);loads[n]+=estimate;estimated[file]=estimate
# Existing files with additional IDs remain in their original serialized file group.
groups={n:[i for f in fs for i in byfile[f]] for n,fs in files.items()};assigned=[i for g in groups.values() for i in g]
assert len(assigned)==len(set(assigned))==len(ids)-127 and not set(assigned)&set(mac) and set(assigned)|set(mac)==set(ids) and all(x['id'] in assigned for x in known)
for file,data in [('collected-ids.txt',sorted(ids)),('collection-order-ids.txt',ids),('cloud-assigned-ids.txt',sorted(assigned))]:(R/file).write_text('\n'.join(data)+'\n')
delta={'candidate':SHA,'prior_candidate':OLD,'fresh_count':len(ids),'baseline_count':2613,'count_delta':len(ids)-2613,'added_ids':sorted(set(ids)-set(prior_ids)),'removed_ids':sorted(set(prior_ids)-set(ids)),'prior_shard_map_sha256':digest(P/'shard-map.json')};save(R/'fresh-inventory-delta.json',delta)
mapping={**prior,'candidate':SHA,'manifest_sha256':MAN,'basis':'Fresh full collection; prior whole-file duration groups preserved and all new/non-Mac IDs assigned exactly once','duration_source':str(P/'per-file-durations.json'),'duration_source_sha256':digest(P/'per-file-durations.json'),'new_files_estimated':estimated,'shards':groups,'files':files,'counts':{n:len(v) for n,v in groups.items()},'estimated_phase_seconds':loads,'created_epoch':time.time(),'execution_schedule':'At most three heavy prepare/test/generation processes; floor checked during scheduling; no retries'};save(R/'shard-map.json',mapping)
for filename in ['shard-map.json','collected-ids.txt','per-file-durations.json']:
 shutil.copy2(P/filename,R/'coordinator'/('prior-'+filename))
out={'candidate':SHA,'full_inventory':len(ids),'baseline_inventory':2613,'inventory_delta':len(ids)-2613,'new_ids':len(delta['added_ids']),'removed_ids':len(delta['removed_ids']),'cloud_assigned':len(assigned),'mac_explicit_partition':127,'mac_attested_passed':127,'mac_raw_inspected_in_cloud':False,'known_skips':10,'counts':mapping['counts'],'estimated_phase_seconds':loads,'no_overlap_or_gaps':True,'whole_file_partition':True,'collection_physical_clone':'shard6','mac_ids_sha256':digest(R/'mac-ids.txt'),'cloud_ids_sha256':digest(R/'cloud-assigned-ids.txt'),'full_ids_sha256':digest(R/'collected-ids.txt'),'free_bytes':shutil.disk_usage('/workspace').free,'minimum_headroom_bytes':3*1024**3,'test_run_authorization':'FINAL_GATE_AUTHORIZED'};save(R/'proof-disjoint-union-before.json',out)
print(json.dumps(out),flush=True)
