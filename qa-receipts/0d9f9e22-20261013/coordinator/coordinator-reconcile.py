import json,pathlib,collections,xml.etree.ElementTree as ET,ast
r=pathlib.Path(__file__).parent
candidate='0d9f9e225776195f47d335b38b4ca5244d8c555c'
manifest='a91a6ec3d947d82953fa7a07e35e394c6b444ff8901b99ea3084d5f56238302c'
sm=json.loads((r/'shard-map.json').read_text())['shards']
col=(r/'collected-ids.txt').read_text().splitlines();mac=(r/'mac-ids.txt').read_text().splitlines()
assert len(col)==len(set(col))==2571 and len(mac)==len(set(mac))==127
assigned_all=[i for rows in sm.values() for i in rows]
assert len(assigned_all)==len(set(assigned_all))==2444
assert not set(assigned_all)&set(mac) and set(assigned_all)|set(mac)==set(col)
known={x['id']:x for x in json.loads((r/'known-skips.json').read_text())}
results=[];skips={};errors=[];passed_total=0;phase_total=0
for n in range(1,7):
 p=r/f'shard{n}';assigned=sm[str(n)]
 assert [x['id'] for x in json.loads((p/'collected.json').read_text())]==assigned
 reports=[json.loads(x) for x in (p/'reports.jsonl').read_text().splitlines()];phase_total+=len(reports)
 byid=collections.defaultdict(list)
 for row in reports:assert row['id'] in assigned;byid[row['id']].append(row)
 assert set(byid)==set(assigned)
 error_ids=[]
 for i,rows in byid.items():
  phases=[x['when'] for x in rows];assert len(phases)==len(set(phases)) and 'setup' in phases and 'teardown' in phases
  bad=[x for x in rows if x['outcome']=='failed'];skipped=[x for x in rows if x['outcome']=='skipped']
  if bad:
   assert len(bad)==1 and bad[0]['when']=='setup' and set(phases)=={'setup','teardown'} and not skipped
   assert rows[-1]['outcome']=='passed' and 'could not create numbered dir' in bad[0]['failure']
   error_ids.append(i);errors.append({'shard':n,'id':i,'when':'setup','body_executed':False,'failure_epoch':bad[0]['utc_epoch']})
  elif skipped:
   assert len(skipped)==1 and i in known
   a=ast.literal_eval(skipped[0]['skip_reason']);b=ast.literal_eval(known[i]['skip_reason'])
   assert pathlib.Path(a[0]).name==pathlib.Path(b[0]).name and a[1:]==b[1:] and skipped[0]['when']==known[i]['when']
   skips[i]={'when':skipped[0]['when'],'file':pathlib.Path(a[0]).name,'line':a[1],'reason':a[2]}
  else:assert set(phases)=={'setup','call','teardown'} and all(x['outcome']=='passed' for x in rows)
 cases=ET.parse(p/'junit.xml').findall('.//testcase');assert len(cases)==len(assigned)
 idx={(pathlib.Path(i.split('::')[0]).stem+('.'+'.'.join(i.split('::')[1:-1]) if len(i.split('::'))>2 else ''),i.split('::')[-1]):i for i in assigned}
 assert len(idx)==len(assigned);jids=[];jskip=[];jerrors=[]
 for c in cases:
  matches=[i for (suffix,name),i in idx.items() if name==c.attrib['name'] and (not c.attrib['classname'] or c.attrib['classname']==suffix or c.attrib['classname'].endswith('.'+suffix))]
  assert len(matches)==1,(n,c.attrib,matches);i=matches[0];jids.append(i);assert c.find('failure') is None
  if c.find('error') is not None:assert i in error_ids;jerrors.append(i)
  if c.find('skipped') is not None:
   assert i in skips and c.find('skipped').attrib['message']==skips[i]['reason'].removeprefix('Skipped: ');jskip.append(i)
 assert len(jids)==len(set(jids)) and set(jids)==set(assigned) and set(jerrors)==set(error_ids)
 latch=json.loads((p/'ATTEMPT_STARTED.json').read_text());assert latch['retry_allowed'] is False
 result=json.loads((p/'result.json').read_text());assert result['candidate']==candidate and result['exit_code']==(1 if error_ids else 0)
 before=json.loads((p/'source-before/capsule-verification.json').read_text());after=json.loads((p/'source-after/capsule-verification.json').read_text())
 for proof in [before,after]:
  assert proof['head']==candidate and proof['status']=='' and proof['normal_clone'] and proof['source_artifact_static_bindings_verified'] and proof['sealed_files_verified']==1706 and proof['manifest_sha256']==manifest
  cap=proof['capsule_receipt'];assert [cap['source_file_count'],cap['artifact_file_count'],cap['static_file_count']]==[1706,25,37]
 assert before['capsule_receipt']==after['capsule_receipt'] and before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
 passed=len(cases)-len(jskip)-len(jerrors);passed_total+=passed
 results.append({'shard':n,'tests':len(cases),'passed':passed,'setup_errors':len(jerrors),'skipped':len(jskip),'runner_seconds':result['duration_seconds'],'raw_applicable_phases_and_junit_ids_exact':True,'body_unrun_ids':jerrors})
assert set(skips)==set(known) and passed_total==2428 and len(errors)==6 and phase_total==7317
out={'candidate':candidate,'status':'FAILED: six setup errors; six test bodies not run','full_inventory':2571,'cloud_assigned':2444,'cloud_passed':passed_total,'cloud_known_skipped':10,'cloud_call_failures':0,'cloud_setup_errors':6,'mac_attested_passed':127,'combined_passed_with_mac_attestation':2555,'mac_raw_receipts_not_local':True,'all_selected_and_setup_attempted_ids_disjoint_complete':True,'full_body_execution_complete':False,'attempts_per_shard':1,'retries':0,'source_capsule_unchanged':True,'known_skips_exact_phase_file_line_reason':True,'raw_phase_count':phase_total,'shards':results,'unrun_body_setup_errors':errors,'known_skips':skips,'cause_limit':'Temporary directory creation failed. Pytest swallowed original mkdir exceptions, so exact errno/root cause is unproven. Disk pressure was observed.'}
(r/'coordinator-independent-reconciliation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='known_skips'},indent=2))
