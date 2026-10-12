import collections,copy,hashlib,json,pathlib,shutil,socket,subprocess,time,xml.etree.ElementTree as ET
ROOT=pathlib.Path('/tmp/casepath-release-e176-20261012'); SHA='e176657b9307ad657fd895e57e83ce88e140bcf5'
OUT=ROOT/'full-shard6-rerun/shard6'; original=json.loads((ROOT/'coverage-summary.json').read_text()); mapping=json.loads((ROOT/'shard-map.json').read_text()); assigned=mapping['shards']['6']; result=json.loads((OUT/'result.json').read_text()); items=json.loads((OUT/'collected.json').read_text()); reports=[json.loads(l) for l in (OUT/'reports.jsonl').read_text().splitlines()]
def digest(items):return hashlib.sha256(('\n'.join(sorted(items))+'\n').encode()).hexdigest()
byid=collections.defaultdict(list)
for row in reports:byid[row['id']].append(row)
collected=[i['id'] for i in items]
assert len(assigned)==len(set(assigned))==len(collected)==len(set(collected))==len(byid)==542
assert set(assigned)==set(collected)==set(byid)
counts=collections.Counter(); duration_rows=[]
for i,rows in byid.items():
 assert len({r['when'] for r in rows})==len(rows),(i,'duplicate phase')
 if any(r['outcome']=='failed' for r in rows):outcome='failed'
 elif any(r['outcome']=='skipped' for r in rows):outcome='skipped'
 else:
  assert {r['when'] for r in rows}=={'setup','call','teardown'} and all(r['outcome']=='passed' for r in rows)
  outcome='passed'
 counts[outcome]+=1; duration_rows.append({'id':i,'outcome':outcome,'observer_duration_seconds':sum(r['duration'] for r in rows)})
cases=ET.parse(OUT/'junit.xml').findall('.//testcase'); junit_ids=[]; junit_counts=collections.Counter()
for c in cases:
 matches=[]
 for row in items:
  parts=row['id'].split('::'); ending='.'.join([pathlib.Path(parts[0]).stem]+parts[1:-1]); cn=c.get('classname')
  if c.get('name')==parts[-1] and ((not cn and parts[0].startswith('casepath/tools/')) or cn==ending or cn.endswith('.'+ending)):matches.append(row['id'])
 assert len(matches)==1,(c.attrib,matches)
 i=matches[0];junit_ids.append(i);outcome='failed' if c.find('failure') is not None or c.find('error') is not None else 'skipped' if c.find('skipped') is not None else 'passed';junit_counts[outcome]+=1
 next(r for r in duration_rows if r['id']==i)['junit_duration_seconds']=float(c.get('time'))
assert len(junit_ids)==len(set(junit_ids))==542 and set(junit_ids)==set(assigned) and counts==junit_counts
assert (OUT/'pytest-arguments.txt').read_bytes()==(ROOT/'shard6/pytest-arguments.txt').read_bytes()
assert result['candidate']==result['after_head']==SHA and not result['after_status']
assert result['started_epoch']>max(x['finished_epoch'] for x in original['shards'].values())
diag=json.loads((ROOT/'diagnostic-summary.json').read_text());diag_result=json.loads((ROOT/'diagnostic-timeout-rerun/shard6/result.json').read_text());assert result['started_epoch']>diag_result['finished_epoch']
seals=[]
for n in range(1,7):
 repo=pathlib.Path(f'/workspace/casepath-release-ae0-shard{n}'); raw_manifest=(repo/'casepath/source-manifest.json').read_bytes();manifest=json.loads(raw_manifest)
 for row in manifest['files']:
  p=repo/row['path'];raw=p.read_bytes();assert not p.is_symlink() and len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],row['path']
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip();status=subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True);assert head==SHA and not status
 seals.append({'repo':str(repo),'head':head,'status':status,'manifest_sha256':hashlib.sha256(raw_manifest).hexdigest(),'sealed_files_verified':len(manifest['files']),'verified_epoch':time.time()})
retry_summary={'candidate':SHA,'role':'User-directed full542-ID replacement shard attempt after contention removed; original failure preserved','tests':542,'passed':counts['passed'],'failed':counts['failed'],'skipped':counts['skipped'],'exit_code':result['exit_code'],'duration_seconds':result['duration_seconds'],'junit_duration_seconds':sum(float(c.get('time')) for c in cases),'assigned_collected_executed_junit_equal':True,'assigned_sorted_sha256':digest(assigned),'executed_sorted_sha256':digest(byid),'after_head':SHA,'after_status':'','source_manifest_sha256':seals[-1]['manifest_sha256'],'sealed_files_verified':seals[-1]['sealed_files_verified'],'started_epoch':result['started_epoch'],'finished_epoch':result['finished_epoch'],'started_after_all_six_original_and_single_diagnostic_terminated':True,'identical_argument_file_sha256':hashlib.sha256((OUT/'pytest-arguments.txt').read_bytes()).hexdigest()}
(OUT/'shard-summary.json').write_text(json.dumps(retry_summary,indent=2));(OUT/'per-test-durations.json').write_text(json.dumps(sorted(duration_rows,key=lambda r:r['id']),indent=2))
selected=copy.deepcopy(original);selected['shards']['6']=retry_summary;selected['cloud']={'tests':2327,'passed':sum(s['passed'] for s in selected['shards'].values()),'failed':sum(s['failed'] for s in selected['shards'].values()),'skipped':sum(s['skipped'] for s in selected['shards'].values())};selected['full_combined']['passed']=selected['cloud']['passed']+selected['mac']['passed'];selected['full_combined']['failed']=selected['cloud']['failed']+selected['mac']['failed'];selected['full_combined']['skipped']=selected['cloud']['skipped']+selected['mac']['skipped']
selected['status']='passed' if all(s['exit_code']==0 and s['failed']==0 for s in selected['shards'].values()) and counts['skipped']==0 else 'failed';selected['role']='Selected complete shard gate: original shards1-5 plus user-directed complete shard6 rerun, and Mac127 coordinator attestation'
selected['selected_attempts']={str(i):f'shard{i}' for i in range(1,6)}|{'6':'full-shard6-rerun/shard6'}
selected['prior_attempts']={'original_cloud':original['cloud'],'original_shard_exit_codes':{n:s['exit_code'] for n,s in original['shards'].items()},'original_shard6':original['shards']['6'],'single_exact_id_diagnostic':diag,'all_prior_receipts_preserved':True,'total_cloud_test_executions_across_original_diagnostic_and_full_retry':2327+1+542,'intentional_repeat_executions':1+542,'selected_gate_duplicate_ids':0}
selected['finished_epoch']=time.time();selected['wall_span_seconds']=result['finished_epoch']-min(s['started_epoch'] for s in original['shards'].values());selected['source_edits']=False;selected['new_skips']=counts['skipped']!=0
chosen=[]
for n in mapping['shards']:
 folder=ROOT/selected['selected_attempts'][n];chosen.extend({json.loads(x)['id'] for x in (folder/'reports.jsonl').read_text().splitlines()})
mac=(ROOT/'mac-ids.txt').read_text().splitlines();full=(ROOT/'collected-ids.txt').read_text().splitlines();assert len(chosen)==len(set(chosen))==2327 and set(chosen).isdisjoint(mac) and set(chosen)|set(mac)==set(full)
selected['cloud_executed_sorted_sha256']=digest(chosen);assert selected['cloud_executed_sorted_sha256']==original['cloud_executed_sorted_sha256']
(ROOT/'selected-coverage-summary.json').write_text(json.dumps(selected,indent=2));(ROOT/'selected-post-run-seal-verification.json').write_text(json.dumps(seals,indent=2));(ROOT/'selected-cloud-executed-ids.txt').write_text('\n'.join(sorted(chosen))+'\n')
selected_durations=[r for r in json.loads((ROOT/'per-test-durations.json').read_text()) if r['shard']!=6]+[dict(r,shard=6) for r in duration_rows];(ROOT/'selected-per-test-durations.json').write_text(json.dumps(sorted(selected_durations,key=lambda r:r['id']),indent=2))
source_files=[ROOT/'README.md',ROOT/'runtime-versions.json',ROOT/'mac-independent-recheck-attestation.json']+[ROOT/p for p in json.loads((ROOT/'artifact-sha256.json').read_text())];source_files+=[ROOT/'artifact-sha256.json',ROOT/'selected-coverage-summary.json',ROOT/'selected-post-run-seal-verification.json',ROOT/'selected-cloud-executed-ids.txt',ROOT/'selected-per-test-durations.json',ROOT/'diagnostic-summary.json',ROOT/'harness/finalize_selected_gate.py']
for attempt in ['diagnostic-timeout-rerun','full-shard6-rerun']:
 for relative in ['shard-map.json','harness/run_shard.py','harness/casepath_shard_observer.py','shard6/command.json','shard6/result.json','shard6/collected.json','shard6/junit.xml','shard6/pytest.log','shard6/reports.jsonl','shard6/pytest-arguments.txt','shard6/shard-summary.json','shard6/per-test-durations.json']:
  p=ROOT/attempt/relative
  if p.exists():source_files.append(p)
destination=ROOT/'durable-evidence';destination.mkdir(exist_ok=True)
for p in set(source_files):
 target=destination/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
manifest={p.relative_to(destination).as_posix():{'size_bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(destination.rglob('*')) if p.is_file()}
(destination/'bundle-sha256.json').write_text(json.dumps(manifest,indent=2));(ROOT/'selected-artifact-sha256.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'status':selected['status'],'cloud':selected['cloud'],'combined':selected['full_combined'],'retry':retry_summary,'original_cloud':original['cloud'],'selected_coverage':selected['coverage'],'durable_evidence':str(destination),'bundle_files':len(manifest)},indent=2))
