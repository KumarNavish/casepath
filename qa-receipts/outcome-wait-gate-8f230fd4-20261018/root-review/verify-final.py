import ast, collections, hashlib, json, time, xml.etree.ElementTree as ET
from pathlib import Path
R=Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018')
A=Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018')
B=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016')
SHA='8f230fd4ad455a15a7a53803ae7b857a4db2aaff';MAN='b7af849b48589e598bcb5385d7dd4ad63bc9a868e634f62ff0be96910ec453e3'
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
mp=read(R/'shard-map.json');full=[x['id'] for x in read(R/'inventory/collected.json')];mac=(R/'mac-ids.txt').read_text().splitlines();prior=(A/'collected-ids.txt').read_text().splitlines();baseline=(B/'collected-ids.txt').read_text().splitlines()
assert mp['candidate']==SHA and mp['manifest_sha256']==MAN
assert len(full)==len(set(full))==2777 and set(full)==set(prior) and len(baseline)==2613 and set(baseline)<=set(full)
fourbf=(Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018')/'collected-ids.txt').read_text().splitlines()
assert len(fourbf)==2777 and set(fourbf)==set(full)
assert len(mac)==len(set(mac))==127 and digest(R/'mac-ids.txt')=='e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'
cloud=[x for n in range(1,7) for x in mp['shards'][str(n)]]
assert len(cloud)==len(set(cloud))==2650 and not set(cloud)&set(mac) and set(cloud)|set(mac)==set(full)
known={x['id']:x for x in read(A/'known-skips.json')};assert len(known)==10
summaries=[];allreports=[];seen=[];allskips=set();homes=set();tmps=set();dbs=set();intervals=[];bindings={}
for n in range(1,7):
 p=R/f'shard{n}';expected=mp['shards'][str(n)];result=read(p/'result.json');command=read(p/'command.json');latch=read(p/'ATTEMPT_STARTED.json');prep=read(p/'prepare.json')
 assert result['candidate']==command['candidate']==latch['candidate']==SHA and result['manifest_sha256']==MAN and result['exit_code']==0 and result['after_head']==SHA and not result['after_status'] and latch['retry_allowed'] is False
 assert result['env']==command['env'] and prep['candidate']==SHA and prep['exit_code']==0
 env=command['env'];assert env['TMPDIR']==env['TMP']==env['TEMP'] and env['TMPDIR'].startswith('/workspace/') and env['HOME'].startswith('/workspace/') and env['CASEPATH_DB_PATH'].startswith(str(p)+'/')
 assert env['CASEPATH_MODEL_MODE']=='deterministic_reference' and not any(k.endswith(('_API_KEY','_TOKEN')) for k in env)
 homes.add(env['HOME']);tmps.add(env['TMPDIR']);dbs.add(env['CASEPATH_DB_PATH'])
 assert (p/'pytest-arguments.txt').read_text().splitlines()==expected
 assert [x['id'] for x in read(p/'collected.json')]==expected
 rows=[json.loads(x) for x in (p/'reports.jsonl').read_text().splitlines()];by=collections.defaultdict(list)
 for row in rows:assert row['id'] in expected and row['outcome']!='failed';by[row['id']].append(row)
 assert set(by)==set(expected);skipped=set()
 for ident,phases in by.items():
  names=[x['when'] for x in phases];assert len(names)==len(set(names)) and {'setup','teardown'}<=set(names)
  skips=[x for x in phases if x['outcome']=='skipped']
  if skips:
   assert len(skips)==1 and ident in known
   actual=skips[0];old=known[ident];aa=ast.literal_eval(actual['skip_reason']);bb=ast.literal_eval(old['skip_reason'])
   assert actual['when']==old['when'] and Path(aa[0]).name==Path(bb[0]).name and aa[1:]==bb[1:]
   skipped.add(ident);assert all(x['outcome']=='passed' for x in phases if x is not actual)
  else:assert set(names)=={'setup','call','teardown'} and all(x['outcome']=='passed' for x in phases)
 cases=ET.parse(p/'junit.xml').findall('.//testcase');assert len(cases)==len(expected);jids=[];jskips=set()
 for case in cases:
  matches=[]
  for ident in expected:
   parts=ident.split('::');suffix=Path(parts[0]).stem+('.'+'.'.join(parts[1:-1]) if len(parts)>2 else '')
   if case.attrib['name']==parts[-1] and (not case.attrib['classname'] or case.attrib['classname']==suffix or case.attrib['classname'].endswith('.'+suffix)):matches.append(ident)
  assert len(matches)==1 and case.find('error') is None and case.find('failure') is None
  ident=matches[0];jids.append(ident)
  if case.find('skipped') is not None:jskips.add(ident);assert ident in skipped
 assert len(jids)==len(set(jids)) and set(jids)==set(expected) and jskips==skipped
 before=read(p/'source-before/capsule-verification.json');after=read(p/'source-after/capsule-verification.json')
 for phase,item in [('before',before),('after',after)]:
  assert item['head']==SHA and item['status']=='' and item['normal_clone'] and item['manifest_sha256']==MAN and item['sealed_files_verified']==1714 and item['source_artifact_static_bindings_verified']
  assert digest(p/f'source-{phase}/CAPSULE_RECEIPT.json')==item['capsule_receipt_file_sha256']
 assert before['capsule_receipt']==after['capsule_receipt'] and before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
 rb=read(p/'runtime-before.json');ra=read(p/'runtime-after.json');assert rb['rows']==ra['rows'] and rb['inventory_sha256']==ra['inventory_sha256'] and ra['before_after_inventory_equal'] and ra['before_observed_before_test_start']
 assert rb['observed_epoch']<latch['started_epoch']<=ra['observed_epoch']
 seen+=jids;allskips|=skipped;allreports+=rows
 for kind,item in [('prepare',prep),('pytest',result)]:intervals.append({'shard':n,'kind':kind,'start':item['started_epoch'],'finish':item['finished_epoch']})
 summaries.append({'shard':n,'selected':len(expected),'passed':len(expected)-len(skipped),'skipped':len(skipped),'raw_phases':len(rows),'junit':len(cases),'exit_code':0,'seconds':result['duration_seconds'],'source_capsule_runtime_equal':True})
 for rel in ['collected.json','reports.jsonl','junit.xml','command.json','result.json','source-before/capsule-verification.json','source-after/capsule-verification.json','runtime-before.json','runtime-after.json']:bindings[f'shard{n}/{rel}']=digest(p/rel)
assert len(seen)==len(set(seen))==2650 and set(seen)==set(cloud) and allskips==set(known)
assert len(homes)==len(tmps)==len(dbs)==6 and len(allreports)==7941
for ident in read(A/'timing-regression-ids.json')['ids']:
 rows=[x for x in allreports if x['id']==ident];assert len(rows)==3 and {x['when'] for x in rows}=={'setup','call','teardown'} and all(x['outcome']=='passed' for x in rows)
events=sorted([(i['start'],1) for i in intervals]+[(i['finish'],-1) for i in intervals]);active=maximum=0
for epoch,change in events:active+=change;maximum=max(maximum,active)
assert active==0 and maximum<=2
resource=[json.loads(x) for x in (R/'global-resource-observations.jsonl').read_text().splitlines()];minimum=min(x['free_bytes'] for x in resource);assert minimum>=3*1024**3
att=read(R/'mac-owner-attestation.json')
assert att['candidate']==SHA and att['manifest_sha256']==MAN and att['passed']==127 and att['failed']==att['skipped']==att['exit_code']==0 and att['attempt_count']==1
assert att['source_file_count']==1714 and att['source_clean_before_after_owner_reported'] and att['source_all1714_manifest_verified_owner_reported'] and att['raw_receipts_inspected_in_cloud'] is False
# Mac execution is explicitly owner-attested; its raw reports remain on Mac.
output={'candidate':SHA,'manifest_sha256':MAN,'verdict':'PASS','full_unique_inventory':2777,'a89_all_ids_retained':True,'fourbf_all2777_ids_retained':True,'b861_all2613_ids_retained':True,'cloud_selected':2650,'cloud_passed':2640,'cloud_known_skips':10,'cloud_failed':0,'cloud_raw_phases':len(allreports),'cloud_junit_cases':len(seen),'mac_partition':127,'mac_raw_inspected_in_cloud':False,'combined_expected_pass_using_mac_owner_attestation':2767,'known_skips_combined':10,'disjoint_union_no_gaps_duplicates':True,'six_once_only_attempts':True,'all_source_capsule_runtime_before_after_equal':True,'all13_timing_regressions_pass':True,'independently_computed_prepare_pytest_max_overlap':maximum,'minimum_global_observed_free_bytes':minimum,'configured_isolation_verified_from_command_receipts':True,'child_environment_observation_coverage':False,'child_environment_limit':'Child environments were not sampled; command/result records prove configured isolation only. Prior Cloud environ access denial remains unchanged.','shards':summaries,'bindings':bindings,'verified_epoch':time.time()}
p=R/'root-review/final-verification.json';p.write_text(json.dumps(output,indent=2)+'\n');print(json.dumps({k:v for k,v in output.items() if k not in ['bindings','shards']}))
