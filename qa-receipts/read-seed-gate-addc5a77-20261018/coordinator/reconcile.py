from pathlib import Path
import ast,collections,hashlib,json,time,xml.etree.ElementTree as ET
R=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018')
SHA='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59'; MAN='0d713ebe1ea45681c139ac8ed39b5d9c811cdfb6ea08af55617e155ecf60c2b8'
def read(p):return json.loads(p.read_text())
def hashfile(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=read(R/'shard-map.json');full=[x['id'] for x in read(R/'inventory/collected.json')];mac=(R/'mac-ids.txt').read_text().splitlines();allcloud=[x for n in range(1,7) for x in m['shards'][str(n)]];known={x['id']:x for x in read(R/'known-skips.json')}
assert m['candidate']==SHA and m['manifest_sha256']==MAN
full_count=len(full);cloud_count=full_count-127
assert len(full)==len(set(full)) and full_count>=2630
prior=set((R/'coordinator/prior-collected-ids.txt').read_text().splitlines()); rename=[]; assert len(prior)==2777 and prior<=set(full) and len(mac)==len(set(mac))==127
assert len(allcloud)==len(set(allcloud))==cloud_count and not set(allcloud)&set(mac) and set(allcloud)|set(mac)==set(full)
assert hashfile(R/'mac-ids.txt')=='e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'
assert len(known)==10
summaries=[];allskips={};allj=[];totalpassed=0;totalphases=0;capsules=[];environments=[];bindings={}
for n in range(1,7):
 p=R/f'shard{n}';expected=m['shards'][str(n)];collected=[x['id'] for x in read(p/'collected.json')]
 assert collected==expected
 result=read(p/'result.json');cmd=read(p/'command.json');latch=read(p/'ATTEMPT_STARTED.json');assert result['candidate']==cmd['candidate']==latch['candidate']==SHA and result['manifest_sha256']==cmd['manifest_sha256']==MAN and result['exit_code']==0 and result['after_head']==SHA and result['after_status']=='' and latch['retry_allowed'] is False
 env=cmd['env'];assert result['env']==env and not any(k for k in env if k.endswith('_API_KEY') or k.endswith('_TOKEN'))
 assert env['TMPDIR']==env['TMP']==env['TEMP'] and env['TMPDIR'].startswith('/workspace/') and env['HOME'].startswith('/workspace/')
 assert env['CASEPATH_DB_PATH'].startswith(str(p)+'/') and env['CASEPATH_MODEL_MODE']=='deterministic_reference'
 environments.append({'shard':n,'HOME':env['HOME'],'TMPDIR':env['TMPDIR'],'CASEPATH_DB_PATH':env['CASEPATH_DB_PATH']})
 reports=[json.loads(x) for x in (p/'reports.jsonl').read_text().splitlines()];byid=collections.defaultdict(list)
 for x in reports:
  assert x['id'] in expected and x['outcome']!='failed';byid[x['id']].append(x)
 assert set(byid)==set(expected)
 skipped=set()
 for ident,rs in byid.items():
  phases=[x['when'] for x in rs];assert len(phases)==len(set(phases)) and 'setup' in phases and 'teardown' in phases
  skip=[x for x in rs if x['outcome']=='skipped']
  if skip:
   assert len(skip)==1 and ident in known
   a=skip[0];b=known[ident];aa=ast.literal_eval(a['skip_reason']);bb=ast.literal_eval(b['skip_reason'])
   assert a['when']==b['when'] and Path(aa[0]).name==Path(bb[0]).name and aa[1:]==bb[1:]
   skipped.add(ident);allskips[ident]={'when':a['when'],'file':Path(aa[0]).name,'line':aa[1],'reason':aa[2]}
   assert all(x['outcome']=='passed' for x in rs if x is not a)
  else:assert set(phases)=={'setup','call','teardown'} and all(x['outcome']=='passed' for x in rs)
 cases=ET.parse(p/'junit.xml').findall('.//testcase');assert len(cases)==len(expected)
 jids=[];jskip=set()
 for c in cases:
  matches=[]
  for i in expected:
   parts=i.split('::');suffix=Path(parts[0]).stem+('.'+'.'.join(parts[1:-1]) if len(parts)>2 else '')
   if c.attrib['name']==parts[-1] and (not c.attrib['classname'] or c.attrib['classname']==suffix or c.attrib['classname'].endswith('.'+suffix)):matches.append(i)
  assert len(matches)==1 and c.find('failure') is None and c.find('error') is None
  ident=matches[0];jids.append(ident)
  if c.find('skipped') is not None:
   assert ident in skipped and c.find('skipped').attrib['message']==allskips[ident]['reason'].removeprefix('Skipped: ');jskip.add(ident)
 assert len(jids)==len(set(jids)) and set(jids)==set(expected) and jskip==skipped
 b=read(p/'source-before/capsule-verification.json');a=read(p/'source-after/capsule-verification.json')
 for phase,x in [('before',b),('after',a)]:
  assert x['head']==SHA and x['status']=='' and x['normal_clone'] and x['manifest_sha256']==MAN and x['sealed_files_verified']==1718 and x['source_artifact_static_bindings_verified']
  assert hashfile(p/f'source-{phase}/CAPSULE_RECEIPT.json')==x['capsule_receipt_file_sha256']
 assert b['capsule_receipt']==a['capsule_receipt'] and b['capsule_receipt_file_sha256']==a['capsule_receipt_file_sha256'];capsules.append(a['capsule_receipt_file_sha256'])
 passed=len(expected)-len(skipped);totalpassed+=passed;totalphases+=len(reports);allj+=jids
 summaries.append({'shard':n,'collected':len(expected),'passed':passed,'skipped':len(skipped),'raw_phase_rows':len(reports),'junit_cases':len(cases),'exit_code':0,'duration_seconds':result['duration_seconds'],'source_capsule_before_after_equal':True})
 for rel in ['collected.json','reports.jsonl','junit.xml','command.json','result.json','source-before/capsule-verification.json','source-after/capsule-verification.json']:bindings[f'shard{n}/{rel}']=hashfile(p/rel)
assert len(set(allj))==cloud_count and set(allj)==set(allcloud) and set(allskips)==set(known) and totalpassed==cloud_count-10 and len(set(capsules))==1
assert len({x['HOME'] for x in environments})==len({x['TMPDIR'] for x in environments})==len({x['CASEPATH_DB_PATH'] for x in environments})==6
out={'candidate':SHA,'manifest_sha256':MAN,'coordinator_raw_reconciliation':True,'full_inventory':full_count,'all_baseline_ids_retained_with_explicit_rename':True,'all2777_baseline_ids_retained_unchanged':True,'baseline_inventory':2777,'explicit_renames':[],'cloud_selected':cloud_count,'cloud_passed':cloud_count-10,'cloud_skipped':10,'cloud_failed':0,'cloud_raw_phase_rows':totalphases,'Mac':'Mac owner assigned unchanged127 partition; native receipt handled by parent; no independent Mac raw inspection or result asserted by Cloud gate','combined_known_skips':10,'no_gaps_duplicates_overlap':True,'all_six_first_only_attempts':True,'all_six_source_capsules_unchanged':True,'all_junit_ids_match_raw_phases_and_collected':True,'shards':summaries,'known_skips':allskips,'environment_isolation':environments,'bindings':bindings,'resource_qualification':'Read raw resource-observations.jsonl and headroom receipts for actual observed free space; no unobserved interval claim.','verified_epoch':time.time()}
p=R/'raw-reconciliation.json';p.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['known_skips','bindings','environment_isolation']},indent=2))
