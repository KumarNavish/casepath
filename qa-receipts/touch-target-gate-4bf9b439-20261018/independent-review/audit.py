from pathlib import Path
import ast, collections, hashlib, json, os, subprocess, sys, time, xml.etree.ElementTree as ET
R=Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018'); O=R/'independent-review'
SHA='4bf9b439813ae5dd82c8820cbe96e4c1ec6db2cd'; MAN='98bd51f82f96e146314496cd41255781634d19c407ced1a37221927b91a6b32e'
FULL='2afdd1b449b87d017fd58ef7aa90c594c244dfd65fe64a9120225d562ba16c2c'; MAC='e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'; B861='9805b5fe6fc46cc5fa11c0a730135aa9066813487c9e8b22328d1fb0683b0720'
def read(p): return json.loads(p.read_text())
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(x): return hashlib.sha256(x).hexdigest()
def git(repo,*args): return subprocess.check_output(['git','--no-optional-locks',*args],cwd=repo,text=True).strip()
def bind(paths): return {str(p.relative_to(R)):h(p) for p in paths}
def save(name,data):
 p=O/name; data.update(candidate=SHA,manifest_sha256=MAN,reviewer='/root/gate_4bf_review',reviewed_epoch=time.time());p.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':h(p),'status':data['status']}));return data
m=read(R/'shard-map.json');repos=read(R/'clone-map.json')['repos']
assert m['candidate']==SHA and m['manifest_sha256']==MAN
if sys.argv[1]=='inventory':
 raw=read(R/'inventory/collected.json'); ids=[x['id'] for x in raw]; full=(R/'collected-ids.txt').read_text().splitlines(); prior=(R/'coordinator/prior-collected-ids.txt').read_text().splitlines();mac=(R/'mac-ids.txt').read_text().splitlines();cloud=(R/'cloud-assigned-ids.txt').read_text().splitlines()
 basepath=Path('/workspace/casepath-startup-itinerary-gate-b8616d4c-20261016/collected-ids.txt');base=basepath.read_text().splitlines()
 assert len(ids)==len(set(ids))==2777 and full==sorted(ids) and h(R/'collected-ids.txt')==FULL and h(R/'coordinator/prior-collected-ids.txt')==FULL and set(ids)==set(prior)
 assert len(base)==len(set(base))==2613 and h(basepath)==B861 and set(base)<=set(ids)
 assert len(mac)==len(set(mac))==127 and h(R/'mac-ids.txt')==MAC and len(cloud)==len(set(cloud))==2650
 assert collections.Counter(i.split('::')[0] for i in mac)=={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
 assigned=[i for n in range(1,7) for i in m['shards'][str(n)]]
 assert len(assigned)==len(set(assigned))==2650 and set(assigned)==set(cloud) and not set(assigned)&set(mac) and set(assigned)|set(mac)==set(ids)
 assert m['counts']=={'1':9,'2':598,'3':403,'4':473,'5':509,'6':658}
 files={}
 for n in range(1,7):
  expected=m['shards'][str(n)];assert len(expected)==m['counts'][str(n)]
  for ident in expected:
   f=ident.split('::')[0];assert f not in files or files[f]==n;files[f]=n
 assert len({files[f] for f in m['serialized_launcher_port_group']})==1
 timing=read(R/'timing-regression-ids.json')['ids'];assert len(timing)==len(set(timing))==13 and set(timing)<=set(m['shards']['5'])
 known=read(R/'known-skips.json');assert len(known)==10 and all(x['id'] in assigned for x in known)
 priorKnown=read(Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018/known-skips.json'));assert known==priorKnown
 result=read(R/'inventory/result.json');command=read(R/'inventory/command.json');latch=read(R/'inventory/ATTEMPT_STARTED.json')
 assert result['exit_code']==0 and result['candidate']==SHA and result['manifest_sha256']==MAN and result['after_head']==SHA and result['after_status']=='' and latch['retry_allowed'] is False and '--collect-only' in command['command']
 assert result['command']==command['command']==latch['command'] and result['started_epoch']==command['started_epoch']==latch['started_epoch']
 manifest=read(R/'source-manifest.json');assert h(R/'source-manifest.json')==MAN and len(manifest['files'])==manifest['file_count']==1714
 sources=[]
 for n in range(1,7):
  repo=Path(repos[str(n)]);assert (repo/'.git').is_dir() and not (repo/'.git').is_symlink() and git(repo,'rev-parse','HEAD')==SHA and git(repo,'status','--porcelain')=='' and h(repo/'casepath/source-manifest.json')==MAN
  for row in manifest['files']:
   p=repo/row['path'];assert not p.is_symlink() and p.stat().st_size==row['size_bytes'] and h(p)==row['sha256'],str(p)
  for f in sorted({i.split('::')[0] for i in mac}):
   b=subprocess.check_output(['git','--no-optional-locks','show','a89b97bb8eecdd8e98771c99ca879d4e253f7881:'+f],cwd=repo);assert b==(repo/f).read_bytes()
  sources.append({'shard':n,'repo':str(repo),'head':SHA,'status':'','normal_clone':True,'direct_sealed_file_hashes_verified':1714})
 paths=[R/x for x in ['source-manifest.json','collected-ids.txt','cloud-assigned-ids.txt','mac-ids.txt','shard-map.json','known-skips.json','timing-regression-ids.json','inventory/collected.json','inventory/command.json','inventory/result.json','inventory/ATTEMPT_STARTED.json','harness/run_shard.py','harness/casepath_shard_observer.py','harness/verify_prepared_capsules.py','harness/runtime_inventory.py']]
 save('inventory-review.json',{'status':'PASS_INVENTORY_TERMINAL_SHARDS_PENDING','full_count':2777,'full_sha256':FULL,'prior_a89_exact_set_equal':True,'baseline_b861_count':2613,'baseline_b861_sha256':h(basepath),'baseline_b861_exact_subset':True,'added_ids':0,'removed_ids':0,'renamed_ids':0,'cloud_count':2650,'mac_count':127,'mac_sha256':MAC,'mac_excluded_from_cloud':True,'whole_file_disjoint_partition':True,'counts':m['counts'],'known_skips_exact_prior_10':True,'timing_regressions_all_13_retained_in_shard5':True,'collection_exit_code':0,'collection_seconds':result['duration_seconds'],'direct_source_observations':sources,'bindings':bind(paths),'limits':['No product tests, prepare, browser, provider, network, or source edits run by this reviewer.','Mac result is owner attestation; Mac raw evidence is not inspected here.','Shard terminal phases/JUnit/runtime equality remain pending.']})
elif sys.argv[1]=='shard':
 n=int(sys.argv[2]);p=R/f'shard{n}';expected=m['shards'][str(n)]
 result=read(p/'result.json');command=read(p/'command.json');latch=read(p/'ATTEMPT_STARTED.json');prepare=read(p/'prepare.json');raw=read(p/'collected.json');collected=[x['id'] for x in raw]
 assert collected==expected and len(set(collected))==len(expected)
 for x in [result,command,latch,prepare]:assert x['candidate']==SHA
 assert result['exit_code']==prepare['exit_code']==0 and result['after_head']==prepare['before_head']==prepare['after_head']==SHA and result['after_status']==prepare['before_status']==prepare['after_status']==''
 assert result['manifest_sha256']==command['manifest_sha256']==prepare['manifest_sha256']==MAN
 assert latch['retry_allowed'] is False and result['command']==command['command']==latch['command'] and result['started_epoch']==command['started_epoch']==latch['started_epoch'] and result['finished_epoch']>result['started_epoch']
 assert (p/'pytest-arguments.txt').read_text().splitlines()==expected
 assert '--collect-only' not in command['command'] and not any(x in command['command'] for x in ['--lf','--last-failed','--reruns','--deselect','-k']) and '-m' not in command['command'][4:]
 env=command['env'];assert env==result['env'] and env['CASEPATH_MODEL_MODE']=='deterministic_reference' and env['CASEPATH_SOURCE_COMMIT']==SHA and env['TMPDIR']==env['TMP']==env['TEMP']==f'/workspace/tt4t{n}' and env['HOME']==f'/workspace/tt4h{n}' and env['CASEPATH_DB_PATH']==str(p/'casepath.db') and env['CASEPATH_ARTIFACT_REGISTRY_PATH']==str(p/'artifact-registry')
 assert not any(k.endswith('_API_KEY') or k.endswith('_TOKEN') for k in env)
 known={x['id']:x for x in read(R/'known-skips.json')};reports=[json.loads(x) for x in (p/'reports.jsonl').read_text().splitlines()];byid=collections.defaultdict(dict);skips={}
 for x in reports:
  assert x['id'] in expected and x['when'] in ['setup','call','teardown'] and x['when'] not in byid[x['id']] and x['outcome'] in ['passed','skipped'];byid[x['id']][x['when']]=x
 assert set(byid)==set(expected)
 for ident,ph in byid.items():
  assert set(ph) in [{'setup','call','teardown'},{'setup','teardown'}]
  skipped=[x for x in ph.values() if x['outcome']=='skipped']
  if skipped:
   assert len(skipped)==1 and ident in known
   x=skipped[0];old=known[ident];a=ast.literal_eval(x['skip_reason']);b=ast.literal_eval(old['skip_reason']);assert x['when']==old['when'] and Path(a[0]).name==Path(b[0]).name and a[1:]==b[1:];skips[ident]={'when':x['when'],'reason':a[2],'line':a[1]}
  else:assert set(ph)=={'setup','call','teardown'}
 cases=ET.parse(p/'junit.xml').findall('.//testcase');jids=[];jskips=[];lookup=collections.defaultdict(list)
 for ident in expected:
  parts=ident.split('::');suffix=Path(parts[0]).stem+('.'+'.'.join(parts[1:-1]) if len(parts)>2 else '');lookup[parts[-1]].append((suffix,ident))
 for case in cases:
  assert case.find('failure') is None and case.find('error') is None
  name=case.attrib['name'];cls=case.attrib.get('classname','');matches=[ident for suffix,ident in lookup[name] if not cls or cls==suffix or cls.endswith('.'+suffix)];assert len(matches)==1
  ident=matches[0];jids.append(ident)
  s=case.find('skipped')
  if s is not None:assert ident in skips and s.attrib['message']==skips[ident]['reason'].removeprefix('Skipped: ');jskips.append(ident)
 assert len(jids)==len(set(jids))==len(expected) and set(jids)==set(expected) and set(jskips)==set(skips)
 sources=[]
 for phase in ['before','after']:
  x=read(p/f'source-{phase}/capsule-verification.json');receipt=read(p/f'source-{phase}/CAPSULE_RECEIPT.json');sem=dict(receipt);stated=sem.pop('receipt_sha256');assert stated==digest(canon(sem))
  assert x['head']==SHA and x['status']=='' and x['normal_clone'] and x['manifest_sha256']==MAN and x['sealed_files_verified']==1714 and x['source_artifact_static_bindings_verified'] and x['capsule_receipt']==receipt and x['capsule_receipt_file_sha256']==h(p/f'source-{phase}/CAPSULE_RECEIPT.json')
  assert receipt['source_file_count']==1714 and receipt['artifact_file_count']==25 and receipt['static_file_count']==40 and receipt['source_manifest_file_sha256']==MAN
  manifest=read(R/'source-manifest.json');assert receipt['source_roster_sha256']==digest(canon(manifest['files'])) and receipt['artifact_manifest_file_sha256']==manifest['artifact_manifest']['sha256'] and receipt['contract']=='casepath.sealed-source-capsule/1.0.0'
  assert read(p/f'verify-{phase}-command.json')['exit_code']==0
  sources.append(x)
 assert sources[0]['capsule_receipt']==sources[1]['capsule_receipt'] and sources[0]['capsule_receipt_file_sha256']==sources[1]['capsule_receipt_file_sha256'] and sources[0]['verified_epoch']<result['started_epoch']<result['finished_epoch']<sources[1]['verified_epoch']
 before=read(p/'runtime-before.json');after=read(p/'runtime-after.json')
 for x in [before,after]:assert x['candidate']==SHA and x['inventory_sha256']==digest(canon(x['rows'])) and x['file_and_symlink_count']==len(x['rows']) and len({r['path'] for r in x['rows']})==len(x['rows'])
 assert before['rows']==after['rows'] and before['inventory_sha256']==after['inventory_sha256'] and after['before_after_inventory_equal'] and before['observed_before_test_start'] and before['observed_epoch']<result['started_epoch']<result['finished_epoch']<after['observed_epoch']
 repo=Path(repos[str(n)]);assert (repo/'.git').is_dir() and not (repo/'.git').is_symlink() and git(repo,'rev-parse','HEAD')==SHA and git(repo,'status','--porcelain')==''
 manifest=read(R/'source-manifest.json')
 for row in manifest['files']:
  f=repo/row['path'];assert not f.is_symlink() and f.stat().st_size==row['size_bytes'] and h(f)==row['sha256']
 timing=set(read(R/'timing-regression-ids.json')['ids'])&set(expected);assert all(set(byid[i])=={'setup','call','teardown'} and all(x['outcome']=='passed' for x in byid[i].values()) for i in timing)
 rels=['collected.json','reports.jsonl','junit.xml','command.json','result.json','ATTEMPT_STARTED.json','pytest-arguments.txt','pytest.log','prepare.json','source-before/capsule-verification.json','source-after/capsule-verification.json','source-before/CAPSULE_RECEIPT.json','source-after/CAPSULE_RECEIPT.json','runtime-before.json','runtime-after.json']
 save(f'shard{n}-review.json',{'status':'PASS_TERMINAL_SHARD','shard':n,'selected':len(expected),'passed':len(expected)-len(skips),'skipped':len(skips),'failed':0,'raw_phase_rows':len(reports),'junit_cases':len(cases),'raw_phase_and_junit_ids_exact':True,'known_skip_details':skips,'single_original_attempt':True,'exit_code':0,'pytest_duration_seconds':result['duration_seconds'],'prepare_seconds':prepare['duration_seconds'],'source_before_after_equal':True,'capsule_receipt_file_sha256':sources[0]['capsule_receipt_file_sha256'],'source_artifact_static_counts':[1714,25,40],'direct_terminal_clone_sealed_files_verified':1714,'runtime_file_and_symlink_count':len(before['rows']),'runtime_inventory_sha256':before['inventory_sha256'],'runtime_before_after_equal':True,'runtime_observed_before_test_start':True,'timing_regressions_passed':len(timing),'env_isolation':{k:env[k] for k in ['HOME','TMPDIR','TMP','TEMP','CASEPATH_DB_PATH','CASEPATH_ARTIFACT_REGISTRY_PATH']},'bindings':bind([p/x for x in rels])})
else: raise SystemExit('inventory | shard N')
