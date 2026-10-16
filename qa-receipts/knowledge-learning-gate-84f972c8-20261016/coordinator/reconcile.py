import collections,hashlib,json,os,shutil,subprocess,time,xml.etree.ElementTree as ET
from pathlib import Path
R=Path('/workspace/casepath-knowledge-learning-gate-84f972c8-20261016')
SHA='84f972c86fe556ccf5cac7e2aacddc6e154fdbb9';MAN='83d09acf9bfae53fd19d5effbae68bf2db2d20d3844938f0c6734454fd0a8382'
MIN=3*1024**3
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(repo,*a):return subprocess.check_output(['git',*a],cwd=repo,text=True).strip()
terminal=json.loads((R/'all-shard-terminal.json').read_text());assert terminal['all_executed'] and len(terminal['results'])==6
mapping=json.loads((R/'shard-map.json').read_text());assigned=[i for ids in mapping['shards'].values() for i in ids];full=(R/'collected-ids.txt').read_text().splitlines();mac=(R/'mac-ids.txt').read_text().splitlines();known=json.loads((R/'known-skips.json').read_text());selected=[];junit_ids=[];phases=[];before=[];after=[];equal=[];intervals=[];summaries=[];prepare_intervals=[]
assert len(full)==len(set(full))==2630 and len(assigned)==len(set(assigned))==2503 and len(mac)==len(set(mac))==127
assert not set(assigned)&set(mac) and set(assigned)|set(mac)==set(full)
assert digest(R/'mac-ids.txt')=='e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'
perfile=collections.defaultdict(lambda:{'ids':set(),'phase_seconds':0.,'call_seconds':0.})
for n in range(1,7):
 out=R/f'shard{n}';repo=Path(f'/workspace/casepath-release-ae0-shard{n}')
 assert (repo/'.git').is_dir() and git(repo,'rev-parse','HEAD')==SHA and git(repo,'status','--porcelain')=='' and digest(repo/'casepath/source-manifest.json')==MAN
 prep=json.loads((out/'prepare.json').read_text());assert prep['exit_code']==0 and prep['before_head']==prep['after_head']==SHA and prep['before_status']==prep['after_status']=='';prepare_intervals.extend([(prep['started_epoch'],1,'prepare',n),(prep['finished_epoch'],-1,'prepare',n)])
 for phase,proofs in [('before',before),('after',after)]:
  proof=json.loads((out/f'source-{phase}/capsule-verification.json').read_text());assert proof['head']==SHA and proof['status']=='' and proof['normal_clone'] and proof['manifest_sha256']==MAN and proof['sealed_files_verified']==1709 and proof['source_artifact_static_bindings_verified'];assert digest(out/f'source-{phase}/CAPSULE_RECEIPT.json')==proof['capsule_receipt_file_sha256'];proofs.append(proof)
 assert before[-1]['capsule_receipt']==after[-1]['capsule_receipt'] and before[-1]['capsule_receipt_file_sha256']==after[-1]['capsule_receipt_file_sha256']
 equal.append({'name':f'shard{n}','head':SHA,'manifest_sha256':MAN,'capsule_receipt_file_sha256':after[-1]['capsule_receipt_file_sha256'],'unchanged_at_actual_pre_post_verification':True})
 result=json.loads((out/'result.json').read_text());assert result['candidate']==SHA and result['after_head']==SHA and result['after_status']=='';intervals.extend([(result['started_epoch'],1,'test',n),(result['finished_epoch'],-1,'test',n)])
 got=[x['id'] for x in json.loads((out/'collected.json').read_text())];assert got==mapping['shards'][str(n)];selected.extend(got)
 reports=[json.loads(x) for x in (out/'reports.jsonl').read_text().splitlines()];phases.extend(reports)
 assert {x['id'] for x in reports}==set(got)
 for i in got:
  r=[x for x in reports if x['id']==i];assert len({x['when'] for x in r})==len(r) and {x['when'] for x in r} in [{'setup','call','teardown'},{'setup','teardown'}]
 for x in reports:
  d=perfile[x['id'].split('::')[0]];d['ids'].add(x['id']);d['phase_seconds']+=x['duration']
  if x['when']=='call':d['call_seconds']+=x['duration']
 idx={(Path(i.split('::')[0]).stem+('.'+'.'.join(i.split('::')[1:-1]) if len(i.split('::'))>2 else ''),i.split('::')[-1]):i for i in got};junit_skips=[];junit_failed=[]
 for c in ET.parse(out/'junit.xml').findall('.//testcase'):
  matches=[i for (suffix,name),i in idx.items() if name==c.attrib['name'] and (not c.attrib['classname'] or c.attrib['classname']==suffix or c.attrib['classname'].endswith('.'+suffix))];assert len(matches)==1,(n,c.attrib,matches);junit_ids.append(matches[0])
  if c.find('skipped') is not None:junit_skips.append(matches[0])
  if c.find('failure') is not None or c.find('error') is not None:junit_failed.append(matches[0])
 assert json.loads((out/'ATTEMPT_STARTED.json').read_text())['retry_allowed'] is False
 assert len(junit_skips)==sum(x['outcome']=='skipped' for x in reports)
 summary={'shard':n,'selected':len(got),'junit':len(got),'passed':sum(x['when']=='call' and x['outcome']=='passed' for x in reports),'skipped':len(junit_skips),'failed_phase_rows':sum(x['outcome']=='failed' for x in reports),'junit_failed':junit_failed,'exit_code':result['exit_code'],'duration_seconds':result['duration_seconds'],'raw_phase_rows':len(reports)};summaries.append(summary)
assert len({x['capsule_receipt_file_sha256'] for x in before+after})==1
assert len(selected)==len(set(selected))==len(junit_ids)==len(set(junit_ids))==2503 and set(selected)==set(junit_ids)==set(assigned)
observed=[x for x in phases if x['outcome']=='skipped'];skipkey=lambda x:(x['id'],x['when'],x['skip_reason']);assert sorted(map(skipkey,known))==sorted(map(skipkey,observed)),(known,observed)
failed=[x for x in phases if x['outcome']=='failed'];passed=sum(x['when']=='call' and x['outcome']=='passed' for x in phases)
for filename,ids in [('selected-cloud-ids.txt',selected),('executed-cloud-ids.txt',{x['id'] for x in phases}),('junit-cloud-ids.txt',junit_ids)]:(R/filename).write_text('\n'.join(sorted(ids))+'\n')
for filename,data in [('capsule-verification-before.json',before),('capsule-verification-after.json',after),('source-capsule-before-after.json',equal),('observed-known-skips.json',observed),('per-test-durations.json',phases),('per-file-durations.json',{f:{'tests':len(x['ids']),'phase_seconds':x['phase_seconds'],'call_seconds':x['call_seconds']} for f,x in perfile.items()})]:save(R/filename,data)
events=[json.loads(x) for x in (R/'scheduler-events.jsonl').read_text().splitlines()];starts=[x for x in events if x['type']=='start'];finishes=[x for x in events if x['type']=='finish'];observations=[json.loads(x) for x in (R/'resource-observations.jsonl').read_text().splitlines()]
assert len(starts)==len(finishes)==6 and {x['shard'] for x in starts}==set(range(1,7)) and all(x['free_bytes']>=MIN for x in starts)
active=0;maximum=0
for epoch,delta,kind,n in sorted(intervals+prepare_intervals):active+=delta;maximum=max(maximum,active)
assert active==0 and maximum<=3
breaches=[x for x in observations if x['free_bytes']<MIN]
resource={'free_bytes':shutil.disk_usage('/workspace').free,'tmp_free_bytes':shutil.disk_usage('/tmp').free,'minimum_observed_workspace_free_bytes':min(x['free_bytes'] for x in observations),'floor_bytes':MIN,'minimum_actual_attempt_start_free_bytes':min(x['free_bytes'] for x in starts),'all_attempt_start_headroom_checks_passed':True,'maximum_prepare_plus_test_interval_concurrency':maximum,'ceiling':3,'floor_continuously_satisfied':not breaches,'below_floor_observations':breaches,'qualification':'Transient normalprepare2 uv-cache allocation exceeded the 300MiB estimate; no test attempt started below floor; raw violation retained; completed owned cache was retired after successful prepare; extra completed reproducible checkout retired before subsequent prepares.' if breaches else None};save(R/'resource-after.json',resource)
save(R/'source-verification.json',{'candidate':SHA,'manifest_sha256':MAN,'source_artifact_static_counts':[1709,25,39],'normal_source_clones':6,'normally_prepared_clones':6,'pre_post_capsule_proofs':12,'all_capsule_receipts_identical':True,'source_after_checks':after,'source_status_after_all_six':''})
mac_attestation={'candidate':SHA,'explicit_partition':127,'mac_ids_sha256':digest(R/'mac-ids.txt'),'passed':127,'skipped':0,'failed':0,'phases':381,'junit':127,'duration_seconds':126.0978,'source_files':1709,'manifest_sha256':MAN,'clean_before_after':True,'source':'Root forwarded actual Mac owner attestation during this gate','raw_receipts_location':'Retained on Mac; not inspected in Cloud','independent_raw_combination_pending':True};save(R/'mac-owner-attestation.json',mac_attestation)
green=not failed and all(s['exit_code']==0 and not s['junit_failed'] for s in summaries)
proof={'candidate':SHA,'full_inventory':2630,'baseline_inventory':2613,'delta_new_tests':17,'cloud_assigned':2503,'cloud_raw_passed':passed,'cloud_known_skipped':len(observed),'cloud_failed_phase_rows':len(failed),'mac_explicit_partition':127,'mac_owner_attested_passed':127,'combined_passed_with_mac_attestation':passed+127,'combined_known_skipped':len(observed),'mac_raw_inspected_in_cloud':False,'mac_independent_raw_combination_pending':True,'no_overlap_or_gaps':True,'selected_collected_executed_junit_cloud_ids_identical':True,'cloud_ids_sha256':digest(R/'cloud-assigned-ids.txt'),'mac_ids_sha256':digest(R/'mac-ids.txt'),'full_ids_sha256':digest(R/'collected-ids.txt'),'all_six_source_capsules_unchanged_at_actual_pre_post_verification':True,'all_attempts_first_only':True,'resource_floor_continuously_satisfied':not breaches};save(R/'proof-disjoint-union-after.json',proof)
aggregate={**proof,'status':'CLOUD_FUNCTIONAL_PASSED_RESOURCE_FLOOR_QUALIFICATION_MAC_RAW_PENDING' if green and breaches else ('CLOUD_PASSED_MAC_RAW_PENDING' if green else 'CLOUD_FAILED'),'all_cloud_functional_checks_passed':green,'full_release_gate_all_guards_satisfied':green and not breaches,'independent_cross_host_raw_receipt_combination_complete':False,'manifest_sha256':MAN,'shards':summaries,'raw_phase_rows':len(phases),'source_artifact_static_counts':[1709,25,39],'source_files_unchanged':True,'all_six_capsules_verified_before_after':True,'capsule_receipt_file_sha256':after[0]['capsule_receipt_file_sha256'],'resource_after':resource,'artifact_manifest_sha256':digest(R/'artifact-manifest.json'),'no_product_edits':True,'no_source_seal_deploy_provider_or_production_requests':True,'no_automatic_retries':True,'known_skips_exact_ids_reasons_and_phases_preserved':True};save(R/'aggregate.json',aggregate)
aggregate.update(cloud_passed=passed,cloud_failed=len({x['id'] for x in failed}),mac_attestation_status='OWNER_ATTESTED_RAW_COMBINATION_PENDING',mac_attested_passed=127,mac_source_clean_after=True,mac_raw_receipts_not_local=True,authorized_full_shard_rechecks=0,native_test_setup_failures=sum(x['when']=='setup' for x in failed),source_capsule_unchanged=True,known_skips_exact_phase_file_line_reason=True,full_cloud_gate_complete=True,source_verification_physical_normal_clones=6,collection_reuses_physical_clone='shard6',full_inventory_ids_sha256=proof['full_ids_sha256'],native_attempt_interval_max_concurrency=maximum)
save(R/'aggregate.json',aggregate)
save(R/'harness-provenance-final.json',[{'path':p.relative_to(R).as_posix(),'sha256':digest(p)} for p in sorted([*R.joinpath('harness').glob('*.py'),*R.joinpath('coordinator').glob('*.py')])])
print(json.dumps({k:v for k,v in aggregate.items() if k!='resource_after'}),flush=True)
