import collections, hashlib, json, shutil, time
from pathlib import Path
R=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017')
SHA='65a796a5dfb21f4cdbe0a3d1a4925b931710b30c'
MAN='6fec138ef5f8eacff8cc4fc19f0084f61b81fde81c2a37c300708c24b5eb2a2c'
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
rows=json.loads((R/'inventory/collected.json').read_text());ids=[x['id'] for x in rows]
prior=(R/'coordinator/prior-collected-ids.txt').read_text().splitlines()
mac=(R/'mac-ids.txt').read_text().splitlines();known=json.loads((R/'known-skips.json').read_text())
assert len(ids)==len(set(ids)) and len(prior)==len(set(prior))==2630
assert set(prior)<=set(ids),'Prior test ID removed'
assert len(mac)==len(set(mac))==127 and len(known)==10 and set(mac)<=set(ids)
assert collections.Counter(i.split('::')[0] for i in mac)=={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
cloud=[i for i in ids if i not in set(mac)];byfile=collections.defaultdict(list)
for ident in cloud:byfile[ident.split('::')[0]].append(ident)
dur=json.loads((R/'coordinator/prior-per-file-durations.json').read_text());prior_map=json.loads((R/'coordinator/prior-shard-map.json').read_text())
# Whole-file LPT using actual prior full-gate phase times. Keep all launcher/tool tests in one serial process.
serial=[f for f in ['casepath-api/tests/test_agent_demo_launcher.py','casepath/tools/test_casepath_release.py','casepath/tools/test_build_deployment_identity.py'] if f in byfile]
groups=[serial] if serial else []
groups += [[f] for f in byfile if f not in serial]
estimated={f:max(5.,len(byfile[f])*1.) for f in byfile if f not in dur}
def weight(group):return sum(dur.get(f,{}).get('phase_seconds',estimated.get(f,0)) for f in group)
files={str(i):[] for i in range(1,7)};loads={str(i):0. for i in range(1,7)}
for group in sorted(groups,key=lambda group:(-weight(group),group)):
 n=min(loads,key=lambda n:(loads[n],int(n)));files[n].extend(group);loads[n]+=weight(group)
shards={n:[ident for f in fs for ident in byfile[f]] for n,fs in files.items()};assigned=[i for v in shards.values() for i in v]
assert len(assigned)==len(set(assigned))==len(ids)-127 and not set(assigned)&set(mac)
assert set(assigned)|set(mac)==set(ids) and all(x['id'] in assigned for x in known)
assert len({n for n,fs in files.items() if set(serial)&set(fs)})==1
for name,data in [('collected-ids.txt',sorted(ids)),('collection-order-ids.txt',ids),('cloud-assigned-ids.txt',sorted(assigned))]:
 (R/name).write_text('\n'.join(data)+'\n')
delta={'candidate':SHA,'prior_candidate':prior_map['candidate'],'fresh_count':len(ids),'baseline_count':len(prior),'count_delta':len(ids)-len(prior),'added_ids':sorted(set(ids)-set(prior)),'removed_ids':sorted(set(prior)-set(ids)),'all_prior_ids_included':True,'prior_ids_sha256':digest(R/'coordinator/prior-collected-ids.txt')};save(R/'fresh-inventory-delta.json',delta)
mapping={'candidate':SHA,'manifest_sha256':MAN,'basis':'Fresh full collection, ALL 2630 prior IDs retained; whole-file LPT by actual 84 phase durations; launcher/tool files serialized together','duration_source':str(R/'coordinator/prior-per-file-durations.json'),'duration_source_sha256':digest(R/'coordinator/prior-per-file-durations.json'),'new_files_estimated':estimated,'shards':shards,'files':files,'counts':{n:len(v) for n,v in shards.items()},'estimated_phase_seconds':loads,'max_active_heavy':3,'serialized_launcher_port_group':serial,'protected_ports':[4173,4189,4190],'created_epoch':time.time(),'no_retries':True,'no_new_skips_or_deselection':True};save(R/'shard-map.json',mapping)
proof={'candidate':SHA,'manifest_sha256':MAN,'full_inventory':len(ids),'baseline_inventory':len(prior),'new_ids':len(delta['added_ids']),'removed_ids':0,'all_2630_prior_ids_included':True,'cloud_assigned':len(assigned),'mac_explicit_partition':127,'mac_raw_inspected_in_cloud':False,'known_skips':10,'counts':mapping['counts'],'estimated_phase_seconds':loads,'no_overlap_or_gaps':True,'whole_file_partition':True,'serialized_launcher_port_group':serial,'collection_physical_clone':json.loads((R/'clone-map.json').read_text())['repos']['1'],'mac_ids_sha256':digest(R/'mac-ids.txt'),'cloud_ids_sha256':digest(R/'cloud-assigned-ids.txt'),'full_ids_sha256':digest(R/'collected-ids.txt'),'free_bytes':shutil.disk_usage('/workspace').free,'test_run_authorization':'FINAL_GATE_AUTHORIZED'};save(R/'proof-disjoint-union-before.json',proof)
print(json.dumps(proof),flush=True)
