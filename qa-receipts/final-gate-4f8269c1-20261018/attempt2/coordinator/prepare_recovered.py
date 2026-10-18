from pathlib import Path
import json,sys,time,subprocess,hashlib,shutil
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018/attempt2');n=sys.argv[1];assert n in ['3','4']
repo=Path(json.loads((R/'clone-map.json').read_text())['repos'][n]);out=R/f'shard{n}';SHA='4f8269c1781c4097f79790f39dd0312a2f9f32bf';HIST='80939f0ec4430402b029a646d60f5bf8b465e9f8';MAN='3532003ba5f916e4d45d02ff57139fb4122d69001667d14f4431f2b4771dd790'
def git(*a):return subprocess.check_output(['git','-C',str(repo),*a],text=True).strip()
assert git('rev-parse','HEAD')==SHA and not git('status','--porcelain') and shutil.disk_usage('/workspace').free>3*1024**3+500*1024**2
assert not (out/'HISTORY_REPAIR_STARTED.json').exists()
(out/'HISTORY_REPAIR_STARTED.json').write_text(json.dumps({'candidate':SHA,'historical_commit':HIST,'epoch':time.time(),'original_failure_receipt':'e598661d3cf39c5bb36bf3427bb260d0b3ada3d4'},indent=2)+'\n')
with (out/'history-fetch.log').open('x') as f:subprocess.run(['git','-C',str(repo),'fetch','origin',HIST],check=True,stdout=f,stderr=subprocess.STDOUT)
assert git('cat-file','-t',HIST)=='commit'
raw=subprocess.check_output(['git','-C',str(repo),'show',HIST+':docs/product/NINE_CASE_SELECTION_20261009.json']);digest=hashlib.sha256(raw).hexdigest();assert digest=='7d70edaf6e886ace18ea55f6b41ab3e44dd5760431bcf8f844ee47ab30b9537e'
with (out/'fetch.log').open('x') as f:subprocess.run(['git','-C',str(repo),'fetch','origin','codex/casepath-causal-experience-integration-20261009'],check=True,stdout=f,stderr=subprocess.STDOUT)
assert git('rev-parse','FETCH_HEAD')==git('rev-parse','HEAD')==SHA and not git('status','--porcelain')
manifest=repo/'casepath/source-manifest.json';assert hashlib.sha256(manifest.read_bytes()).hexdigest()==MAN
rows=json.loads(manifest.read_bytes())['files']
for x in rows:
 p=repo/x['path'];b=p.read_bytes();assert not p.is_symlink() and len(b)==x['size_bytes'] and hashlib.sha256(b).hexdigest()==x['sha256']
(out/'history-repair-proof.json').write_text(json.dumps({'candidate':SHA,'HEAD_before_after':SHA,'source_clean_before_after':True,'manifest_sha256':MAN,'sealed_files_verified':len(rows),'historical_commit':HIST,'historical_file_sha256':digest,'matches_Mac_independent_digest':True,'only_Git_object_metadata_acquired':True},indent=2)+'\n')
for script,args in [('harness/prepare_clones.py',[f'shard{n}']),('coordinator/verify.py',[n,'before'])]:
 with (out/(Path(script).stem+'-wrapper.log')).open('x') as f:p=subprocess.run(['/usr/bin/python3',str(R/script),*args],stdout=f,stderr=subprocess.STDOUT)
 assert p.returncode==0,(script,p.returncode)
print(json.dumps({'shard':n,'attempt':2,'history_digest':digest,'normal_prepare_and_fresh_before_proofs':True}),flush=True)
