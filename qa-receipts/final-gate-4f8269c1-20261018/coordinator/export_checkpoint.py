from pathlib import Path
import hashlib,json,subprocess,os,time,sys,tarfile,shutil
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018');repo=Path('/workspace/casepath-final-gate-4f8269c1-control-20261018');SHA='4f8269c1781c4097f79790f39dd0312a2f9f32bf'
branch='qa-receipts/final-gate-4f8269c1-20261018';prefix='qa-receipts/final-gate-4f8269c1-20261018';stage=R/'export-stage';stage.mkdir(exist_ok=True);dest=stage/prefix;dest.mkdir(parents=True,exist_ok=True)
# Include only immutable preparation inputs and terminal test outputs; no fixture DB or runtime caches.
allowed={'.json','.jsonl','.txt','.log','.py','.xml','.gz'}
rootnames=['EXECUTION_AUTHORIZATION.json','clone-map.json','mac-ids.txt','known-skips.json','mac-result-owner-reported.json','gate-host.json','shard-map.json','proof-disjoint-union-before.json','fresh-inventory-delta.json','baseline-inclusion-proof.json','collected-ids.txt','collection-order-ids.txt','cloud-assigned-ids.txt','raw-reconciliation.json','final-runtime-reconciliation.json','resource-final-proof.json','gate-negative-attempts.json']
paths=[R/n for n in rootnames if (R/n).exists()]
paths += [p for d in ['harness','coordinator','inventory'] for p in (R/d).rglob('*') if p.is_file() and p.suffix in allowed and '__pycache__' not in p.parts]
# Baseline IDs and historical split are immutable inputs, not a substituted run.
paths += [p for p in (R/'prior-harness').rglob('*') if p.is_file() and p.suffix in {'.txt','.json'}]
finished=[]
for n in range(1,7):
 out=R/f'shard{n}';terminal=(out/'worker-terminal.json').exists()
 if terminal:finished.append(n)
 for p in out.rglob('*'):
  rel=p.relative_to(out)
  if not p.is_file() or p.is_symlink() or p.suffix not in allowed or any(x in {'pytest-tmp','home','tmp','pycache','uv-cache','artifact-registry','__pycache__'} for x in rel.parts):continue
  if not terminal and p.name not in {'CLONE_STARTED.json','clone.log','fetch.log','PREPARE_STARTED.json','prepare.log','prepare.json','prepare_clones-wrapper.log','verify-wrapper.log','verify-before.log','verify-before-command.json','runtime-before.json','TEST_ADMITTED.json','TEST_PROCESS.json','ATTEMPT_STARTED.json','command.json','pytest-arguments.txt','CAPSULE_RECEIPT.json','capsule-verification.json'}:continue
  paths.append(p)
for area in ['attempt2','diagnostic-shard6']:
 base=R/area
 if base.exists():
  for p in base.rglob('*'):
   if not p.is_file() or p.is_symlink() or p.suffix not in allowed or any(x in {'pytest-tmp','home','tmp','pycache','uv-cache','artifact-registry','__pycache__'} for x in p.relative_to(base).parts):continue
   # A live file is a declared checkpoint snapshot; original terminal raws never change.
   paths.append(p)
for p in sorted(set(paths)):
 target=dest/p.relative_to(R);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
state={'candidate':SHA,'finished_shards':finished,'all_six_terminal':len(finished)==6,'partial':len(finished)!=6,'epoch':time.time(),'full_gate_not_admitted_until_raw_reconciliation':True,'original_shard_exit_codes':{str(n):json.loads((R/f'shard{n}/worker-terminal.json').read_text())['pytest_wrapper_exit'] for n in finished},'original_gate_passed':len(finished)==6 and all(json.loads((R/f'shard{n}/worker-terminal.json').read_text())['pytest_wrapper_exit']==0 for n in finished)}
(dest/'checkpoint.json').write_text(json.dumps(state,indent=2)+'\n')
files=[p for p in sorted(dest.rglob('*')) if p.is_file() and p.name not in {'SHA256SUMS','raw-evidence.tar.gz','raw-bundle.json'}]
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# Archive on completed checkpoints; preparation checkpoint remains directly inspectable.
if len(finished)==6:
 archive=dest/'raw-evidence.tar.gz'
 with tarfile.open(archive,'w:gz',compresslevel=6) as t:
  for p in files:t.add(p,arcname=p.relative_to(dest).as_posix(),recursive=False)
 with tarfile.open(archive,'r:gz') as t:
  for p in files:assert hashlib.sha256(t.extractfile(p.relative_to(dest).as_posix()).read()).hexdigest()==digest(p)
 (dest/'raw-bundle.json').write_text(json.dumps({'candidate':SHA,'raw_files':len(files),'archive_sha256':digest(archive),'archive_bytes':archive.stat().st_size,'all_members_byte_verified':True,'excludes':['fixture database content','venv/capsule bytes (before-after byte proofs included)','cache/tmp contents','credentials/private seeds/production records'],'Mac_raw':'Retained by Mac owner; owner-reported result only in Cloud'},indent=2)+'\n')
 files += [archive,dest/'raw-bundle.json']
(dest/'SHA256SUMS').write_text(''.join(digest(p)+'  '+p.relative_to(dest).as_posix()+'\n' for p in sorted(files)))
idx=R/'checkpoint-index';env=os.environ.copy();env['GIT_INDEX_FILE']=str(idx)
def git(*args,input=None):return subprocess.check_output(['git','-C',str(repo),*args],env=env,input=input).decode().strip()
refs=git('ls-remote','--heads','origin',branch);parent=refs.split()[0] if refs else SHA
if refs:git('fetch','origin',branch)
git('read-tree',parent)
for p in sorted(dest.rglob('*')):
 if not p.is_file():continue
 blob=git('hash-object','-w','--stdin',input=p.read_bytes());git('update-index','--add','--cacheinfo',f'100644,{blob},{p.relative_to(stage).as_posix()}')
tree=git('write-tree');commit=git('commit-tree',tree,'-p',parent,input=f'test(qa): preserve 4f8269c1 gate checkpoint ({len(finished)}/6 shards)\n'.encode())
git('update-ref','refs/heads/'+branch,commit)
subprocess.run(['git','-C',str(repo),'push','origin',f'{commit}:refs/heads/{branch}'],check=True,stdout=subprocess.DEVNULL)
assert git('ls-remote','--heads','origin',branch).split()[0]==commit
for p in sorted(dest.rglob('*')):
 if p.is_file():assert hashlib.sha256(subprocess.check_output(['git','-C',str(repo),'show',f'{commit}:{p.relative_to(stage).as_posix()}'])).hexdigest()==digest(p)
assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()==SHA
assert subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True)==''
record={**state,'receipt_commit':commit,'branch':branch,'subtree':prefix,'checksums':len(files),'SHA256SUMS_sha256':digest(dest/'SHA256SUMS'),'remote_and_all_blob_hashes_verified':True}
(R/f'export-{commit[:12]}.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
