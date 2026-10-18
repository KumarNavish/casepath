from pathlib import Path
import collections,json,hashlib,time,shutil
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018');SHA='4f8269c1781c4097f79790f39dd0312a2f9f32bf';MAN='3532003ba5f916e4d45d02ff57139fb4122d69001667d14f4431f2b4771dd790'
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ids=[x['id'] for x in json.loads((R/'inventory/collected.json').read_text())]
prior=(R/'prior-harness/collected-ids.txt').read_text().splitlines();mac=(R/'mac-ids.txt').read_text().splitlines()
assert len(ids)==len(set(ids))==2842 and set(ids)==set(prior)
assert len(mac)==len(set(mac))==127 and set(mac)<=set(ids)
assert collections.Counter(i.split('::')[0] for i in mac)=={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
old=json.loads((R/'prior-harness/shard-map.json').read_text());byfile=collections.defaultdict(list)
for i in ids:
 if i not in set(mac):byfile[i.split('::')[0]].append(i)
assert {f for fs in old['files'].values() for f in fs}==set(byfile)
shards={n:[i for f in fs for i in byfile[f]] for n,fs in old['files'].items()}
assigned=[i for v in shards.values() for i in v]
assert len(assigned)==len(set(assigned))==2715 and not set(assigned)&set(mac) and set(assigned)|set(mac)==set(ids)
known=json.loads((R/'known-skips.json').read_text());assert len(known)==10 and all(x['id'] in assigned for x in known)
baselines=['coordinator/prior-collected-ids.txt','coordinator/legacy2777-collected-ids.txt','prior-harness/coordinator/b861-collected-ids.txt']
proof=[]
for f in baselines:
 p=R/f;rows=p.read_text().splitlines();assert len(rows)==len(set(rows)) and set(rows)<=set(ids)
 proof.append({'path':f,'count':len(rows),'sha256':digest(p),'exact_subset':True})
for name,values in [('collected-ids.txt',sorted(ids)),('collection-order-ids.txt',ids),('cloud-assigned-ids.txt',sorted(assigned))]:(R/name).write_text('\n'.join(values)+'\n')
m={**old,'candidate':SHA,'manifest_sha256':MAN,'shards':shards,'counts':{n:len(v) for n,v in shards.items()},'max_active_heavy':6,'global_max_heavy':6,'basis':'Fresh exact2842 collection; prior whole-file duration-balanced ownership unchanged; all fixed-port launcher/tool files in one shard','created_epoch':time.time()}
save(R/'shard-map.json',m)
save(R/'fresh-inventory-delta.json',{'candidate':SHA,'baseline16c_count':2842,'current_count':2842,'added_ids':[],'removed_ids':[],'renamed_ids':[],'frontend_parameter_loop_remains_inside_existing_Python_wrapper':True})
save(R/'baseline-inclusion-proof.json',{'candidate':SHA,'full_count':2842,'baselines':proof,'removed_ids':[],'renames':[]})
save(R/'proof-disjoint-union-before.json',{'candidate':SHA,'manifest_sha256':MAN,'full_inventory':2842,'cloud_selected':2715,'mac_partition':127,'counts':m['counts'],'no_overlap_or_gaps':True,'known_skips':10,'all16c_ids_unchanged':True,'b861_exact_subset':True,'estimated_phase_seconds':m['estimated_phase_seconds'],'fixed_port_group':m['serialized_launcher_port_group'],'free_disk_bytes':shutil.disk_usage('/workspace').free,'memory_limit_bytes':int(Path('/sys/fs/cgroup/memory.max').read_text()),'memory_current_bytes':int(Path('/sys/fs/cgroup/memory.current').read_text()),'cpu_quota_vcpu':4,'max_gate_heavy_authorized':6,'resource_reserve_per_running_shard_bytes':2*1024**3,'disk_floor_bytes':3*1024**3})
assert shutil.disk_usage('/workspace').free>=3*1024**3+6*2*1024**3
print(json.dumps({'inventory':len(ids),'Cloud':len(assigned),'Mac':len(mac),'shards':m['counts'],'known_skips':10,'all_prior_ids':True,'free_disk_bytes':shutil.disk_usage('/workspace').free}))
