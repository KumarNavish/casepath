from pathlib import Path
import json,hashlib,time,subprocess
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018');SHA='4f8269c1781c4097f79790f39dd0312a2f9f32bf'
rows=[];resource=[]
for n in range(1,7):
 p=R/f'shard{n}';b=json.loads((p/'runtime-before.json').read_text());a=json.loads((p/'runtime-after.json').read_text());attempt=json.loads((p/'ATTEMPT_STARTED.json').read_text())
 assert b['observed_before_test_start'] and b['observed_epoch']<attempt['started_epoch']
 assert a['before_after_inventory_equal'] and a['rows']==b['rows'] and a['inventory_sha256']==b['inventory_sha256']
 assert a['candidate']==b['candidate']==SHA
 rows.append({'shard':n,'runtime_files_and_symlinks':len(a['rows']),'inventory_sha256':a['inventory_sha256'],'exact_before_after_equal':True,'observed_before_test_start':True,'attempt_count':1})
 obs=[json.loads(x) for x in (p/'resource-observations.jsonl').read_text().splitlines()]
 assert obs and all(x['free_disk_bytes']>=3*1024**3 and x['memory_current_bytes']<34359738368 for x in obs)
 admission=json.loads((p/'TEST_ADMITTED.json').read_text());assert admission['free_disk_bytes']>=3*1024**3+2*1024**3
 resource.extend(obs)
(R/'final-runtime-reconciliation.json').write_text(json.dumps({'candidate':SHA,'all_six_runtime_inventories_exact_before_after':True,'every_initial_inventory_before_test_start':True,'shards':rows},indent=2)+'\n')
(R/'resource-final-proof.json').write_text(json.dumps({'candidate':SHA,'floor_bytes':3*1024**3,'observations':len(resource),'minimum_sampled_disk_free_bytes':min(x['free_disk_bytes'] for x in resource),'peak_sampled_memory_bytes':max(x['memory_current_bytes'] for x in resource),'memory_limit_bytes':34359738368,'all_admissions_above_floor_and_2GiB_per_shard':True,'max_gate_heavy':6,'cpu_quota_vcpu':4,'no_cleanup_needed':True,'qualification':'Sampled every10s per shard; no unobserved interval guarantee.'},indent=2)+'\n')
ids=(R/'collected-ids.txt').read_text().splitlines();timing=[i for i in ids if '::test_hosted_read_timing_' in i]
assert len(timing)==13
m=json.loads((R/'shard-map.json').read_text());assert set(timing)<={i for v in m['shards'].values() for i in v}
(R/'coordinator/required-timing-regressions.json').write_text(json.dumps({'candidate':SHA,'count':13,'all_in_inventory_and_cloud_map':True,'ids':timing},indent=2)+'\n')
boot=subprocess.check_output(['git','-C','/workspace/casepath','rev-parse','HEAD'],text=True).strip();status=subprocess.check_output(['git','-C','/workspace/casepath','status','--porcelain'],text=True)
assert boot=='d9a47d738523c28b22444f0041d691a510550044' and not status
print(json.dumps({'runtime_proofs':len(rows),'resource_observations':len(resource),'timing_regressions':len(timing),'bootstrap_unchanged':True}))
