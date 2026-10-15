import json,pathlib,collections,xml.etree.ElementTree as ET,ast
r=pathlib.Path(__file__).parent.parent
sm=json.loads((r/'shard-map.json').read_text())['shards']
col=(r/'collected-ids.txt').read_text().splitlines(); mac=(r/'mac-ids.txt').read_text().splitlines()
assert len(col)==len(set(col))==2613 and len(mac)==len(set(mac))==127
all_assigned=[i for rows in sm.values() for i in rows]
assert len(all_assigned)==len(set(all_assigned))==2486
assert not set(all_assigned)&set(mac) and set(all_assigned)|set(mac)==set(col)
known={x['id']:x for x in json.loads((r/'known-skips.json').read_text())}
results=[]; skips={}; cloudpassed=0
for n in range(1,7):
 p=r/f'shard{n}'; assigned=sm[str(n)]; collected=[x['id'] for x in json.loads((p/'collected.json').read_text())]
 assert collected==assigned,(n,'collection differs')
 reports=[json.loads(x) for x in (p/'reports.jsonl').read_text().splitlines()]
 byid=collections.defaultdict(list)
 for x in reports:
  assert x['id'] in assigned and x['outcome']!='failed', (n,x)
  byid[x['id']].append(x)
 assert set(byid)==set(assigned)
 for i,rs in byid.items():
  phases=[x['when'] for x in rs]; assert len(phases)==len(set(phases)) and 'setup' in phases and 'teardown' in phases,(n,i)
  sr=[x for x in rs if x['outcome']=='skipped']
  if sr:
   assert len(sr)==1 and i in known
   k=known[i]; x=sr[0]
   a=ast.literal_eval(x['skip_reason']); b=ast.literal_eval(k['skip_reason'])
   assert pathlib.Path(a[0]).name==pathlib.Path(b[0]).name and a[1:]==b[1:] and x['when']==k['when']
   skips[i]={'when':x['when'],'file':pathlib.Path(a[0]).name,'line':a[1],'reason':a[2]}
  else: assert set(phases)=={'setup','call','teardown'} and all(x['outcome']=='passed' for x in rs)
 cases=ET.parse(p/'junit.xml').findall('.//testcase'); assert len(cases)==len(assigned)
 idx={(pathlib.Path(i.split('::')[0]).stem + ('.'+'.'.join(i.split('::')[1:-1]) if len(i.split('::'))>2 else ''),i.split('::')[-1]):i for i in assigned}; assert len(idx)==len(assigned)
 junitids=[]; jskip=[]
 for c in cases:
  matches=[i for (suffix,name),i in idx.items() if name==c.attrib['name'] and (not c.attrib['classname'] or c.attrib['classname']==suffix or c.attrib['classname'].endswith('.'+suffix))]
  assert len(matches)==1,(n,c.attrib,matches); i=matches[0]; junitids.append(i)
  assert c.find('failure') is None and c.find('error') is None
  if c.find('skipped') is not None:
   assert i in skips and c.find('skipped').attrib['message']==skips[i]['reason'].removeprefix('Skipped: ')
   jskip.append(i)
 assert len(junitids)==len(set(junitids)) and set(junitids)==set(assigned)
 latch=json.loads((p/'ATTEMPT_STARTED.json').read_text()); assert latch.get('retry_allowed') is False
 expected_attempt = 1
 assert latch.get('attempt_number',1)==expected_attempt
 if expected_attempt==2: assert latch['prior_original_attempt_preserved'] and latch['one_environment_repaired_recheck_explicitly_authorized']
 result=json.loads((p/'result.json').read_text()); assert result['exit_code']==0 and result['candidate']=='5086624c8a024ba298819e5e27d749efbd0cc7fc'
 before=json.loads((p/'source-before/capsule-verification.json').read_text()); after=json.loads((p/'source-after/capsule-verification.json').read_text())
 for proof in [before,after]:
  assert proof['head']==result['candidate'] and proof['status']=='' and proof['normal_clone'] and proof['source_artifact_static_bindings_verified'] and proof['sealed_files_verified']==1709 and proof['manifest_sha256']=='39f03a9ebb1287c5e03f57a444ea97bb079dc44e84cff90a86805c19fba35c3f'
 assert before['capsule_receipt']==after['capsule_receipt'] and before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
 passed=len(cases)-len(jskip);cloudpassed+=passed
 results.append({'shard':n,'tests':len(cases),'passed':passed,'skipped':len(jskip),'runner_seconds':result['duration_seconds'],'all_raw_phases_and_junit_ids_exact':True})
assert set(skips)==set(known) and cloudpassed==2476
macfile=r/'coordinator/mac-attestation.json'
macattest=json.loads(macfile.read_text()) if macfile.exists() else None
if macattest: assert macattest['candidate']=='5086624c8a024ba298819e5e27d749efbd0cc7fc' and macattest['passed']==127 and macattest['failed']==0 and macattest['skipped']==0 and macattest['exit_code']==0 and macattest['source_clean_after'] and macattest['source_clean_before'] is None and macattest['raw_mac_junit_or_phase_rows_inspected_in_cloud'] is False
out={'status':'PASSED_WITH_MAC_OWNER_ATTESTATION' if macattest else 'CLOUD_PASSED_MAC_PENDING','mac_source_clean_before':None,'mac_source_clean_after':True if macattest else None,'candidate':'5086624c8a024ba298819e5e27d749efbd0cc7fc','full_inventory':2613,'cloud_assigned':2486,'cloud_passed':cloudpassed,'cloud_known_skipped':len(skips),'cloud_failed':0,'mac_attestation_status':'OWNER_ATTESTED' if macattest else 'PENDING','mac_attested_passed':127 if macattest else None,'combined_passed_with_mac_attestation':cloudpassed+127 if macattest else None,'mac_raw_receipts_not_local':True,'no_overlap_or_gaps':True,'selected_attempts_per_shard':[1,1,1,1,1,1],'authorized_full_shard_rechecks':0,'initial_setup_failures_preserved':False,'source_capsule_unchanged':True,'known_skips_exact_phase_file_line_reason':True,'shards':results,'known_skips':skips}
(pathlib.Path(__file__).parent/'coordinator-independent-reconciliation.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='known_skips'},indent=2))
