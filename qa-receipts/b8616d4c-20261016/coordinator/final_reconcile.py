import collections,hashlib,json,shutil,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path
R=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016')
SHA='b8616d4cfd5bf5667587dd1a0bf4ed58e9436d2b'
MAN='f96041e43695b6cc82899e4ccf8bb08ade79a69a0b74792acedb40716166f23e'
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
terminal=json.loads((R/'all-shard-terminal.json').read_text());assert terminal['all_executed'] and terminal['all_green'] and len(terminal['results'])==6
cmd=['/usr/bin/python3',str(R/'coordinator/coordinator-reconcile.py')];start=time.time()
with (R/'coordinator/reconciliation.log').open('x') as f:p=subprocess.run(cmd,cwd=R,stdout=f,stderr=subprocess.STDOUT)
save(R/'coordinator/reconciliation-command.json',{'command':cmd,'cwd':str(R),'exit_code':p.returncode,'started_epoch':start,'finished_epoch':time.time()});assert p.returncode==0
reconciled=json.loads((R/'coordinator/coordinator-independent-reconciliation.json').read_text())
sm=json.loads((R/'shard-map.json').read_text());assigned=[i for g in sm['shards'].values() for i in g];selected=[];junit_ids=[];phases=[];before=[];after=[];equality=[];intervals=[];retirements=[]
perfile=collections.defaultdict(lambda:{'ids':set(),'phase_seconds':0.,'call_seconds':0.})
for n in range(1,7):
 out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}')
 assert (repo/'.git').is_dir() and subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==SHA and not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip() and digest(repo/'casepath/source-manifest.json')==MAN
 prep=json.loads((out/'prepare.json').read_text());assert prep['exit_code']==0 and prep['before_head']==prep['after_head']==SHA and prep['before_status']==prep['after_status']==''
 for phase,proofs in [('before',before),('after',after)]:
  proof=json.loads((out/f'source-{phase}/capsule-verification.json').read_text());assert proof['head']==SHA and proof['status']=='' and proof['normal_clone'] and proof['manifest_sha256']==MAN and proof['sealed_files_verified']==1709 and proof['source_artifact_static_bindings_verified'];assert digest(out/f'source-{phase}/CAPSULE_RECEIPT.json')==proof['capsule_receipt_file_sha256'];proofs.append(proof)
 assert before[-1]['capsule_receipt']==after[-1]['capsule_receipt'] and before[-1]['capsule_receipt_file_sha256']==after[-1]['capsule_receipt_file_sha256']
 if (R/f'completed-shard{n}-runtime-retirement.json').exists():
  retired=json.loads((R/f'completed-shard{n}-runtime-retirement.json').read_text());assert retired['pre_post_source_capsule_proofs_and_raw_receipts_locally_archived_and_verified'];retirements.append(retired)
 equality.append({'name':f'shard{n}','head':SHA,'manifest_sha256':MAN,'capsule_receipt_file_sha256':after[-1]['capsule_receipt_file_sha256'],'unchanged_at_actual_pre_post_verification':True,'runtime_retired_after_verified_archival':n in [x['shard'] for x in retirements]})
 result=json.loads((out/'result.json').read_text());assert result['exit_code']==0 and result['candidate']==SHA and result['after_head']==SHA and result['after_status']=='';intervals.extend([(result['started_epoch'],1,n),(result['finished_epoch'],-1,n)])
 got=[x['id'] for x in json.loads((out/'collected.json').read_text())];assert got==sm['shards'][str(n)];selected.extend(got)
 reports=[json.loads(x) for x in (out/'reports.jsonl').read_text().splitlines()];phases.extend(reports)
 for x in reports:
  d=perfile[x['id'].split('::')[0]];d['ids'].add(x['id']);d['phase_seconds']+=x['duration']
  if x['when']=='call':d['call_seconds']+=x['duration']
 idx={(Path(i.split('::')[0]).stem+('.'+'.'.join(i.split('::')[1:-1]) if len(i.split('::'))>2 else ''),i.split('::')[-1]):i for i in got}
 for c in ET.parse(out/'junit.xml').findall('.//testcase'):
  matches=[i for (suffix,name),i in idx.items() if name==c.attrib['name'] and (not c.attrib['classname'] or c.attrib['classname']==suffix or c.attrib['classname'].endswith('.'+suffix))];assert len(matches)==1;junit_ids.append(matches[0]);assert c.find('failure') is None and c.find('error') is None
 assert json.loads((out/'ATTEMPT_STARTED.json').read_text())['retry_allowed'] is False
assert len({x['capsule_receipt_file_sha256'] for x in before+after})==1
assert len(selected)==len(set(selected))==2486 and set(selected)==set(assigned) and len(junit_ids)==len(set(junit_ids))==2486 and set(junit_ids)==set(assigned)
assert {x['id'] for x in phases}==set(assigned) and not any(x['outcome']=='failed' for x in phases)
observed=[x for x in phases if x['outcome']=='skipped'];assert len(observed)==10
for filename,ids in [('selected-cloud-ids.txt',selected),('executed-cloud-ids.txt',{x['id'] for x in phases}),('junit-cloud-ids.txt',junit_ids)]:(R/filename).write_text('\n'.join(sorted(ids))+'\n')
for filename,data in [('capsule-verification-before.json',before),('capsule-verification-after.json',after),('source-capsule-before-after.json',equality),('observed-known-skips.json',observed),('per-test-durations.json',phases),('per-file-durations.json',{f:{'tests':len(x['ids']),'phase_seconds':x['phase_seconds'],'call_seconds':x['call_seconds']} for f,x in perfile.items()})]:save(R/filename,data)
events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()];starts=[x for x in events if x['type']=='start'];finishes=[x for x in events if x['type']=='finish'];assert len(starts)==len(finishes)==6 and {x['shard'] for x in starts}==set(range(1,7)) and all(x['free_bytes']>=3*1024**3 for x in starts)
active=0;maximum=0
for epoch,delta,n in sorted(intervals):active+=delta;maximum=max(maximum,active)
assert active==0 and maximum<=3 and all(len(x['active'])<=3 for x in events if 'active' in x)
observations=[json.loads(x) for x in (R/'resource-observations.jsonl').read_text().splitlines()]
resource={'epoch':time.time(),'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'minimum_observed_workspace_free_bytes':min(x['free_bytes'] for x in observations),'minimum_prelaunch_headroom_bytes':3*1024**3,'minimum_actual_prelaunch_free_bytes':min(x['free_bytes'] for x in starts),'all_attempt_start_headroom_checks_passed':True,'max_native_interval_concurrency':maximum,'allowed_host_ceiling':3,'scheduling_limit_used':3,'completed_runtime_retirements_after_archived_source_proofs':[x['shard'] for x in retirements],'below_floor_terminal_events':[x for x in finishes if x['free_bytes']<3*1024**3]};save(R/'resource-after.json',resource);assert resource['free_bytes']>=3*1024**3
save(R/'source-verification.json',{'candidate':SHA,'manifest_sha256':MAN,'source_artifact_static_counts':[1709,25,39],'normal_source_clones':6,'normally_prepared_clones':6,'pre_post_capsule_proofs':12,'all_capsule_receipts_identical':True,'source_after_checks':after,'source_status_after_all_six':''})
proof={'candidate':SHA,'full_inventory':2613,'cloud_assigned':2486,'cloud_raw_passed':2476,'cloud_known_skipped':10,'cloud_failed':0,'mac_explicit_partition':127,'mac_owner_attested_passed':127,'mac_raw_inspected_in_cloud':False,'mac_independent_raw_combination_pending':True,'no_overlap_or_gaps':True,'selected_collected_executed_junit_cloud_ids_identical':True,'cloud_ids_sha256':digest(R/'cloud-assigned-ids.txt'),'mac_ids_sha256':digest(R/'mac-ids.txt'),'full_ids_sha256':digest(R/'collected-ids.txt'),'all_six_source_capsules_unchanged_at_actual_pre_post_verification':True,'all_attempts_first_only':True,'max_heavy_active_observed':maximum,'resource_after':resource};save(R/'proof-disjoint-union-after.json',proof)
aggregate={**reconciled,'status':'CLOUD_PASSED_WITH_MAC_OWNER_ATTESTATION_PENDING_INDEPENDENT_RAW_COMBINATION','full_cloud_gate_complete':True,'independent_cross_host_raw_receipt_combination_complete':False,'mac_independent_raw_combination_pending':True,'source_verification_physical_normal_clones':6,'collection_reuses_physical_clone':'shard1','completed_runtimes_retired_after_actual_pre_post_source_proofs':[x['shard'] for x in retirements],'no_automatic_retries':True,'manifest_sha256':MAN,'full_inventory_ids_sha256':proof['full_ids_sha256'],'cloud_ids_sha256':proof['cloud_ids_sha256'],'mac_ids_sha256':proof['mac_ids_sha256'],'source_artifact_static_counts':[1709,25,39],'all_six_capsules_verified_before_after':True,'capsule_receipt_file_sha256':after[0]['capsule_receipt_file_sha256'],'resource_after':resource,'native_attempt_interval_max_concurrency':maximum,'raw_phase_rows':len(phases),'artifact_manifest_sha256':digest(R/'artifact-manifest.json'),'no_product_edits':True,'no_source_seal_deploy_provider_or_production_requests':True,'focused_receipt_reference':json.loads((R/'coordinator/focused-receipt-reference.json').read_text())};save(R/'aggregate.json',aggregate)
save(R/'harness-provenance-final.json',[{'path':p.relative_to(R).as_posix(),'sha256':digest(p)} for p in sorted([*R.joinpath('harness').glob('*.py'),*R.joinpath('coordinator').glob('*.py')])])
print(json.dumps({k:v for k,v in aggregate.items() if k not in ['known_skips','shards']}),flush=True)
