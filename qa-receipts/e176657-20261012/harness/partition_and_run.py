import collections,hashlib,json,pathlib,subprocess,sys,time
ROOT=pathlib.Path('/tmp/casepath-release-e176-20261012'); OLD=pathlib.Path('/tmp/casepath-release-ae0-20261012'); SHA='e176657b9307ad657fd895e57e83ce88e140bcf5'
rows=json.loads((ROOT/'inventory/collected.json').read_text()); ids=sorted(r['id'] for r in rows)
def digest(ids):return hashlib.sha256(('\n'.join(sorted(ids))+'\n').encode()).hexdigest()
assert len(ids)==2454 and len(set(ids))==len(ids)
old_ids=(OLD/'collected-ids.txt').read_text().splitlines(); assert set(ids)==set(old_ids)
assert digest(ids)=='a05e8ec49b6b94f092fedc740c12dab3e031a62e0400a890058896438a45d65a'
mac_files={'casepath-api/tests/test_cli_v1.py','casepath-api/tests/test_local_data_root.py','casepath-api/tests/test_journal_corpus_restart.py'}
mac_ids=[i for i in ids if i.split('::')[0] in mac_files]; cloud_ids=[i for i in ids if i not in set(mac_ids)]
assert len(mac_ids)==127 and set(mac_ids)==set((OLD/'mac-ids.txt').read_text().splitlines())
assert digest(mac_ids)=='e0689250a44b228a378ae46b3b320e03cc5c879453d69cd255ad0f48e402a7a8'
prior=json.loads((ROOT/'prior-junit-durations.json').read_text()); durations={r['id']:r['junit_seconds'] for r in prior}; assert set(durations)==set(cloud_ids)
files=collections.defaultdict(list)
for i in cloud_ids:files[i.split('::')[0]].append(i)
groups=[]
split_files={'casepath-api/tests/test_agent_demo_launcher.py','casepath-api/tests/test_agent_desk_v1.py'}
for f,items in files.items():
 if f in split_files:groups.extend([[i] for i in items])
 else:groups.append(items)
groups.sort(key=lambda g:(-sum(durations[i] for i in g),g[0]))
shards={str(i):[] for i in range(1,7)}; weights={str(i):0 for i in range(1,7)}
for g in groups:
 n=min(shards,key=lambda k:(weights[k],len(shards[k]),int(k))); shards[n]+=g; weights[n]+=sum(durations[i] for i in g)
for n in shards:shards[n].sort()
flatten=[i for items in shards.values() for i in items]
assert len(flatten)==2327 and len(flatten)==len(set(flatten)) and set(flatten)==set(cloud_ids)
for name,items in [('collected-ids',ids),('mac-ids',mac_ids),('cloud-assigned-ids',cloud_ids)]: (ROOT/(name+'.txt')).write_text('\n'.join(items)+'\n')
(ROOT/'inventory/collected-ids.json').write_text(json.dumps(ids,indent=2))
mapping={'candidate':SHA,'total':2454,'mac_ids':mac_ids,'shards':shards,'balance_basis':'Exact ae0 JUnit testcase durations, greedily grouped by file except launcher and agent_desk_v1 test IDs; candidate API tree unchanged. Prior timings are estimates and depend on concurrent host load.','prior_junit_duration_total_seconds':sum(durations.values()),'prior_junit_sha256':{str(i):hashlib.sha256((OLD/f'shard{i}/junit.xml').read_bytes()).hexdigest() for i in range(1,7)}}
(ROOT/'shard-map.json').write_text(json.dumps(mapping,indent=2))
summary={'candidate':SHA,'total':2454,'mac':127,'cloud':2327,'full_sorted_sha256':digest(ids),'mac_sorted_sha256':digest(mac_ids),'cloud_sorted_sha256':digest(cloud_ids),'same_exact_inventory_as_ae0':True,'mac_file_counts':dict(collections.Counter(i.split('::')[0] for i in mac_ids)),'shards':{n:{'count':len(items),'prior_junit_estimated_seconds':weights[n],'sorted_sha256':digest(items),'files':dict(collections.Counter(i.split('::')[0] for i in items))} for n,items in shards.items()},'missing':0,'duplicates':0,'extra':0,'limitation':'Prior JUnit timings estimate balance, not a runtime bound. No long-lived services are launched; API server fixtures use mocks or OS ephemeral ports.'}
(ROOT/'shard-map-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='shards'}),flush=True)
processes={}
for n,items in shards.items():
 out=ROOT/('shard'+n); (out/'ids.txt').write_text('\n'.join(items)+'\n')
 log=(out/'runner.log').open('w'); p=subprocess.Popen([sys.executable,str(ROOT/'harness/run_shard.py'),'run',n],stdout=log,stderr=subprocess.STDOUT)
 processes[n]=(p,log)
 print(json.dumps({'started_shard':n,'pid':p.pid,'count':len(items),'estimated_seconds':weights[n]}),flush=True)
(ROOT/'processes.json').write_text(json.dumps({n:{'pid':p.pid,'count':len(shards[n]),'estimated_seconds':weights[n]} for n,(p,_) in processes.items()},indent=2))
while processes:
 for n,(p,log) in list(processes.items()):
  code=p.poll()
  if code is not None:
   log.close(); print(json.dumps({'finished_shard':n,'exit_code':code}),flush=True); del processes[n]
 if processes:time.sleep(1)
print('ALL_SIX_COMPLETE',flush=True)
