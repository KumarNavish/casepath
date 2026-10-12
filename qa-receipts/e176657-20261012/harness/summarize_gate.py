import ast,collections,hashlib,json,pathlib,socket,subprocess,time,xml.etree.ElementTree as ET
ROOT=pathlib.Path('/tmp/casepath-release-e176-20261012'); OLD=pathlib.Path('/tmp/casepath-release-ae0-20261012'); SHA='e176657b9307ad657fd895e57e83ce88e140bcf5'
def digest(items):return hashlib.sha256(('\n'.join(sorted(items))+'\n').encode()).hexdigest()
def skip_reason(row):return ast.literal_eval(row['skip_reason'])[-1]
full=(ROOT/'collected-ids.txt').read_text().splitlines(); mac=(ROOT/'mac-ids.txt').read_text().splitlines(); mapping=json.loads((ROOT/'shard-map.json').read_text())
old_skips={r['id']:skip_reason(r) for r in json.loads((OLD/'known-skips.json').read_text())}; known_skips=[]; executed=[]; summaries={}; seals=[]; durations=[]
for n,assigned in mapping['shards'].items():
 out=ROOT/('shard'+n); repo=pathlib.Path('/workspace/casepath-release-ae0-shard'+n)
 result=json.loads((out/'result.json').read_text()); items=json.loads((out/'collected.json').read_text()); collected=[i['id'] for i in items]
 reports=[json.loads(l) for l in (out/'reports.jsonl').read_text().splitlines()]; byid=collections.defaultdict(list)
 for r in reports:byid[r['id']].append(r)
 assert len(assigned)==len(set(assigned))==len(collected)==len(set(collected))==len(byid)
 assert set(assigned)==set(collected)==set(byid)
 counts=collections.Counter()
 for i,rows in byid.items():
  assert len({r['when'] for r in rows})==len(rows),(i,'duplicate phase')
  if any(r['outcome']=='failed' for r in rows):outcome='failed'
  elif any(r['outcome']=='skipped' for r in rows):
   outcome='skipped'; skip=[r for r in rows if r['outcome']=='skipped']; assert len(skip)==1
   known_skips+=skip
  else:
   assert {r['when'] for r in rows}=={'setup','call','teardown'} and all(r['outcome']=='passed' for r in rows),i
   outcome='passed'
  counts[outcome]+=1
  durations.append({'id':i,'shard':int(n),'outcome':outcome,'observer_duration_seconds':sum(r['duration'] for r in rows)})
 cases=ET.parse(out/'junit.xml').findall('.//testcase'); junit_ids=[]; junit_counts=collections.Counter()
 for c in cases:
  matches=[]
  for row in items:
   parts=row['id'].split('::'); ending='.'.join([pathlib.Path(parts[0]).stem]+parts[1:-1]); cn=c.get('classname')
   if c.get('name')==parts[-1] and ((not cn and parts[0].startswith('casepath/tools/')) or cn==ending or cn.endswith('.'+ending)):matches.append(row['id'])
  assert len(matches)==1,(c.attrib,matches)
  i=matches[0]; junit_ids.append(i); outcome='failed' if c.find('failure') is not None or c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed'; junit_counts[outcome]+=1
  next(r for r in durations if r['id']==i)['junit_duration_seconds']=float(c.get('time'))
 assert len(junit_ids)==len(set(junit_ids))==len(assigned) and set(junit_ids)==set(assigned)
 assert counts==junit_counts,(n,counts,junit_counts)
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(); status=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True)
 raw_manifest=(repo/'casepath/source-manifest.json').read_bytes(); manifest=json.loads(raw_manifest)
 for row in manifest['files']:
  p=repo/row['path']; raw=p.read_bytes(); assert not p.is_symlink() and len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],row['path']
 assert head==SHA and not status and result['after_head']==SHA and not result['after_status']
 seal={'repo':str(repo),'head':head,'status':status,'manifest_sha256':hashlib.sha256(raw_manifest).hexdigest(),'sealed_files_verified':len(manifest['files']),'verified_epoch':time.time()}; seals.append(seal)
 summary={'tests':len(assigned),'passed':counts['passed'],'failed':counts['failed'],'skipped':counts['skipped'],'exit_code':result['exit_code'],'duration_seconds':result['duration_seconds'],'junit_duration_seconds':sum(float(c.get('time')) for c in cases),'assigned_collected_executed_junit_equal':True,'assigned_sorted_sha256':digest(assigned),'executed_sorted_sha256':digest(byid),'after_head':head,'after_status':status,'sealed_files_verified':len(manifest['files']),'source_manifest_sha256':seal['manifest_sha256'],'started_epoch':result['started_epoch'],'finished_epoch':result['finished_epoch']}
 summary['status']='passed' if result['exit_code']==0 and counts['failed']==0 else 'failed'
 summaries[n]=summary; executed+=list(byid)
 (out/'shard-summary.json').write_text(json.dumps(summary,indent=2))
assert len(executed)==len(set(executed))==2327
assert set(executed).isdisjoint(mac) and set(executed)|set(mac)==set(full)
assert len(known_skips)==10 and {r['id']:skip_reason(r) for r in known_skips}==old_skips,'New/missing/changed skips'
cloud={'tests':len(executed),'passed':sum(s['passed'] for s in summaries.values()),'failed':sum(s['failed'] for s in summaries.values()),'skipped':sum(s['skipped'] for s in summaries.values())}
mac_record=json.loads((ROOT/'mac-coordinator-attestation.json').read_text())
assert mac_record['candidate']==SHA and mac_record['tests']==len(mac)==mac_record['passed']==127 and mac_record['failed']==mac_record['skipped']==0 and mac_record['assigned_sorted_sha256']==digest(mac)
summary={'candidate':SHA,'host':socket.gethostname(),'targets':['casepath-api/tests','casepath/tools/test_build_deployment_identity.py','casepath/tools/test_casepath_release.py'],'collected_count':len(full),'collected_sorted_sha256':digest(full),'mac_ids_sorted_sha256':digest(mac),'cloud_executed_sorted_sha256':digest(executed),'shards':summaries,'cloud':cloud,'mac':mac_record,'full_combined':{'tests':len(full),'passed':cloud['passed']+mac_record['passed'],'failed':cloud['failed']+mac_record['failed'],'skipped':cloud['skipped']+mac_record['skipped'],'mac_basis':'Mac coordinator attested exact candidate and exact127 ID equality; Mac JUnit not present on Cloud','cloud_basis':'Six independently parsed Cloud JUnits and exact-ID observer phase reports'},'coverage':{'missing':0,'duplicates':0,'extra':0,'all_assigned_collected_executed_junit_equal':True},'finished_epoch':time.time(),'wall_span_seconds':max(s['finished_epoch'] for s in summaries.values())-min(s['started_epoch'] for s in summaries.values()),'source_edits':False,'new_skips':False,'provider_credentials_in_test_environment':False,'test_environment_transport_or_provider_variables':False,'paid_inference':False,'production_operations':False,'status':'passed' if all(s['exit_code']==0 and s['failed']==0 for s in summaries.values()) else 'failed','limits':['Mac JUnit/receipt/coverage remain on Mac F2; the combined union relies on explicit coordinator attestation for those exact127 IDs.','Ten unchanged skips require unavailable frozen research fixtures.','Prior JUnit timings only estimate shard balance; no performance bound is asserted.']}
(ROOT/'coverage-summary.json').write_text(json.dumps(summary,indent=2))
(ROOT/'cloud-executed-ids.txt').write_text('\n'.join(sorted(executed))+'\n')
(ROOT/'known-skips.json').write_text(json.dumps(known_skips,indent=2))
(ROOT/'per-test-durations.json').write_text(json.dumps(sorted(durations,key=lambda r:r['id']),indent=2))
(ROOT/'post-run-seal-verification.json').write_text(json.dumps(seals,indent=2))
artifacts=[ROOT/'coverage-summary.json',ROOT/'shard-map.json',ROOT/'shard-map-summary.json',ROOT/'collected-ids.txt',ROOT/'mac-ids.txt',ROOT/'cloud-executed-ids.txt',ROOT/'known-skips.json',ROOT/'per-test-durations.json',ROOT/'source-manifest.json',ROOT/'running-seal-verification.json',ROOT/'post-run-seal-verification.json',ROOT/'prior-junit-durations.json',ROOT/'preparation-summary.json',ROOT/'processes.json',ROOT/'mac-coordinator-attestation.json',ROOT/'failure-environment-observation.json',ROOT/'failure-after-shutdown-events.json',ROOT/'failure-after-shutdown-state.json',ROOT/'harness-provenance.json']
for name in ['inventory']+[f'shard{i}' for i in range(1,7)]:
 for basename in ['command.json','result.json','collected.json','collection.log','pytest.log','junit.xml','reports.jsonl','prepare.json','prepare.log','prepare.json.attempt-1','prepare.log.attempt-1','fetch.log','fetch.log.attempt-1','shard-summary.json','ids.txt','pytest-arguments.txt','runner.log','failure-call.txt','failure-setup.txt','failure-teardown.txt']:
  p=ROOT/name/basename
  if p.exists():artifacts.append(p)
for p in sorted((ROOT/'harness').glob('*.py')):artifacts.append(p)
manifest={p.relative_to(ROOT).as_posix():{'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(artifacts)}
(ROOT/'artifact-sha256.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'cloud':cloud,'shards':{n:{k:v for k,v in s.items() if k in ['tests','passed','failed','skipped','exit_code','duration_seconds']} for n,s in summaries.items()},'wall_span_seconds':summary['wall_span_seconds'],'coverage':summary['coverage'],'evidence_files':len(manifest)},indent=2))
