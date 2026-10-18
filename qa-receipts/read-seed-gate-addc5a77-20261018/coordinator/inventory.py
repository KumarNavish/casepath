import collections,hashlib,json,shutil,subprocess,time
from pathlib import Path
R=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018')
SHA='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59';MAN='0d713ebe1ea45681c139ac8ed39b5d9c811cdfb6ea08af55617e155ecf60c2b8'
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads((R/'inventory/collected.json').read_text());ids=[x['id'] for x in rows]
prior=(R/'coordinator/prior-collected-ids.txt').read_text().splitlines();mac=(R/'mac-ids.txt').read_text().splitlines();known=json.loads((R/'known-skips.json').read_text())
rename=[]
assert len(ids)==len(set(ids)) and len(prior)==len(set(prior))==2777
assert set(prior)<=set(ids),'Unexpected prior test ID removed'
assert set(prior)<=set(ids), 'Prior inventory must remain an exact subset'
original=(R/'coordinator/original2613-collected-ids.txt').read_text().splitlines();assert len(original)==len(set(original))==2613 and set(original)<=set(ids)
assert len(mac)==len(set(mac))==127 and len(known)==10 and set(mac)<=set(ids)
assert collections.Counter(i.split('::')[0] for i in mac)=={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
repo=Path(json.loads((R/'clone-map.json').read_text())['repos']['1'])
comparison=[]
for f in sorted(set(i.split('::')[0] for i in mac)):
 a=subprocess.check_output(['git','show','c925a0267971edb52fea5f2bd9653a2495b7ac15:'+f],cwd=repo);b=(repo/f).read_bytes();assert a==b
 comparison.append({'file':f,'baseline_sha256':hashlib.sha256(a).hexdigest(),'candidate_sha256':hashlib.sha256(b).hexdigest(),'byte_equal':True})
save(R/'mac-partition-source-comparison.json',{'candidate':SHA,'partition_count':127,'all_current':True,'all_unchanged':True,'files':comparison,'mac_ids_sha256':digest(R/'mac-ids.txt')})
cloud=[i for i in ids if i not in set(mac)];byfile=collections.defaultdict(list)
for ident in cloud:byfile[ident.split('::')[0]].append(ident)
dur=json.loads((R/'coordinator/prior-per-file-durations.json').read_text())
serial=[f for f in ['casepath-api/tests/test_agent_demo_launcher.py','casepath/tools/test_casepath_release.py','casepath/tools/test_build_deployment_identity.py'] if f in byfile]
groups=([serial] if serial else [])+[[f] for f in byfile if f not in serial]
estimated={f:max(5.,len(byfile[f])*1.) for f in byfile if f not in dur}
def weight(g):return sum(dur.get(f,{}).get('phase_seconds',estimated.get(f,0)) for f in g)
prior_map=json.loads((R/'coordinator/prior-shard-map.json').read_text());files={n:list(fs) for n,fs in prior_map['files'].items()};oldfiles={f for fs in files.values() for f in fs};assert oldfiles<=set(byfile)
loads={n:weight(fs) for n,fs in files.items()}
new_file_assignments={}
for f in sorted(set(byfile)-oldfiles):
 n=min(files,key=lambda n:(loads[n],int(n)));files[n].append(f);loads[n]+=weight([f]);new_file_assignments[f]=n
assert all(set(prior_map['files'][n])<=set(files[n]) for n in files)

shards={n:[ident for f in fs for ident in byfile[f]] for n,fs in files.items()};assigned=[i for v in shards.values() for i in v]
assert len(assigned)==len(set(assigned))==len(ids)-127 and not set(assigned)&set(mac)
assert set(assigned)|set(mac)==set(ids) and all(x['id'] in assigned for x in known)
assert len({n for n,fs in files.items() if set(serial)&set(fs)})==1
for name,data in [('collected-ids.txt',sorted(ids)),('collection-order-ids.txt',ids),('cloud-assigned-ids.txt',sorted(assigned))]:(R/name).write_text('\n'.join(data)+'\n')
delta={'candidate':SHA,'prior_candidate':'8f230fd4ad455a15a7a53803ae7b857a4db2aaff','fresh_count':len(ids),'baseline_count':len(prior),'count_delta':len(ids)-len(prior),'added_ids':sorted(set(ids)-set(prior)),'removed_ids':sorted(set(prior)-set(ids)),'renamed_tests':rename,'genuinely_new_ids':sorted(set(ids)-set(prior)),'all_other_prior_ids_included':True,'prior_ids_sha256':digest(R/'coordinator/prior-collected-ids.txt')};save(R/'fresh-inventory-delta.json',delta)
mapping={'candidate':SHA,'manifest_sha256':MAN,'basis':'Fresh full collection; baseline2777 exact IDs retained; existing file ownership unchanged; new files sorted and assigned to lowest prior duration load; launcher/tool files serialized','duration_source':str(R/'coordinator/prior-per-file-durations.json'),'duration_source_sha256':digest(R/'coordinator/prior-per-file-durations.json'),'new_files_estimated':estimated,'new_file_assignments':new_file_assignments,'shards':shards,'files':files,'counts':{n:len(v) for n,v in shards.items()},'estimated_phase_seconds':loads,'max_active_heavy':2,'global_max_heavy':2,'serialized_launcher_port_group':serial,'protected_ports':[4173,4189,4190],'created_epoch':time.time(),'no_retries':True,'no_new_skips_or_deselection':True};save(R/'shard-map.json',mapping)
proof={'candidate':SHA,'manifest_sha256':MAN,'full_inventory':len(ids),'baseline_inventory':len(prior),'genuinely_new_ids':len(delta['genuinely_new_ids']),'raw_added_ids':len(delta['added_ids']),'raw_removed_ids':0,'explicit_renames':rename,'all2777_baseline_ids_included_unchanged':True,'cloud_assigned':len(assigned),'mac_explicit_partition':127,'mac_raw_inspected_in_cloud':False,'known_skips':10,'counts':mapping['counts'],'estimated_phase_seconds':loads,'no_overlap_or_gaps':True,'whole_file_partition':True,'serialized_launcher_port_group':serial,'collection_physical_clone':str(repo),'mac_ids_sha256':digest(R/'mac-ids.txt'),'cloud_ids_sha256':digest(R/'cloud-assigned-ids.txt'),'full_ids_sha256':digest(R/'collected-ids.txt'),'free_bytes':shutil.disk_usage('/workspace').free,'test_run_authorization':'FINAL_GATE_AUTHORIZED'};save(R/'proof-disjoint-union-before.json',proof)
print(json.dumps(proof),flush=True)
