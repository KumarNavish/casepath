import os,json,hashlib,subprocess,time,shutil
from pathlib import Path
R=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');P=Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
R.mkdir(exist_ok=True);(R/'coordinator').mkdir(exist_ok=True)
for p in ['/workspace/rsh0','/workspace/rst0']:Path(p).mkdir(exist_ok=True)
s=(P/'coordinator/export_receipts.py').read_text().replace(str(P),str(R)).replace('outcome-wait-gate-8f230fd4','read-seed-gate-addc5a77').replace('/workspace/owh0','/workspace/rsh0').replace('/workspace/owt0','/workspace/rst0');(R/'coordinator/export_receipts.py').write_text(s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a):return subprocess.check_output(['git','-C',str(G),*a]).decode().strip()
F='81919a0beceab6672f72daf1e823120e9046e2cc';sub='qa-evidence/read-seed-startup-8f230fd4-20261018';sums=git('show',F+':'+sub+'/SHA256SUMS');checks=[]
for row in sums.splitlines():
 h,rel=row.split(None,1);raw=subprocess.check_output(['git','-C',str(G),'show',F+':'+sub+'/'+rel.strip()]);assert hashlib.sha256(raw).hexdigest()==h;checks.append({'path':rel.strip(),'sha256':h})
assert len(checks)==18
branches=[]
for name,branch,expected in [('casepath-release-ae0-shard3','codex/casepath-read-seed-startup-20261018','af78642d485e050674b462718517f6e2cadaa308'),('casepath-release-ae0-shard4','codex/casepath-read-seed-tools-20261018','8b92084acd150783b5f728893fed47d9e2b71f5c')]:
 p=Path('/workspace')/name
 def run(*a):return subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
 assert run('rev-parse','HEAD')==expected and not run('status','--porcelain') and run('rev-parse',branch)==expected
 remote=run('ls-remote','origin','refs/heads/'+branch).split()[0];assert remote==expected
 branches.append({'path':str(p),'branch':branch,'head':expected,'remote':remote,'status':''})
paths=[Path('/workspace/casepath-release-ae0-shard3/.runtime/casepath-dev-v2'),Path('/workspace/casepath-read-seed-20261018/backend/warm-proof-tmp'),Path('/workspace/casepath-read-seed-20261018/review/fixtures'),Path('/workspace/read-seed-tools-test/tmp')]
owned=[]
for q in Path('/proc').iterdir():
 if not q.name.isdigit():continue
 try:
  cwd=os.readlink(q/'cwd')
  if any(cwd==str(p) or cwd.startswith(str(p)+'/') for p in paths+[Path(x['path']) for x in branches]):owned.append({'pid':q.name,'cwd':cwd})
 except OSError:pass
assert not owned
records=[]
for p in paths:
 assert p.is_dir() and not p.is_symlink();entries=[]
 for q in sorted(p.rglob('*')):
  if q.is_symlink():entries.append({'path':q.relative_to(p).as_posix(),'symlink':os.readlink(q)})
  elif q.is_file():entries.append({'path':q.relative_to(p).as_posix(),'bytes':q.stat().st_size,'sha256':sha(q)})
 records.append({'path':str(p),'entries':len(entries),'apparent_bytes':sum(x.get('bytes',0) for x in entries),'allocated_bytes':sum(q.lstat().st_blocks*512 for q in p.rglob('*')),'inventory':entries})
receipt={'candidate':'addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59','manifest_sha256':'0d713ebe1ea45681c139ac8ed39b5d9c811cdfb6ea08af55617e155ecf60c2b8','source_file_count':1718,'host':os.uname().nodename,'epoch':time.time(),'focused_commit':F,'focused_subtree':sub,'focused_checksums_verified':checks,'source_branches_preserved':branches,'runtime_identity':'Prior normal prepared8f capsule1714+venv; focused working source af786 recorded separately','approved_paths':records,'owned_processes':owned,'workspace_free_bytes':shutil.disk_usage('/workspace').free,'memory_current':int(Path('/sys/fs/cgroup/memory.current').read_text()),'memory_max':int(Path('/sys/fs/cgroup/memory.max').read_text()),'decision':'Retire ONLY these four approved owned disposable directories AFTER this proof is pushed and exact remote bytes verified; retain all logs/sources/exports/receipts/package-selector builds/global UV cache','optional_seed_environment_in_parent_present':'CASEPATH_READ_SEED_PATH' in os.environ,'heavy_limit_selected':1}
assert receipt['host']=='656813ef2295' and not receipt['optional_seed_environment_in_parent_present']
(R/'approved-retirement-proof.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'proof':str(R/'approved-retirement-proof.json'),'entries':sum(x['entries'] for x in records),'allocated_bytes':sum(x['allocated_bytes'] for x in records),'free':receipt['workspace_free_bytes']}))
