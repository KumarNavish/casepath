from pathlib import Path
import os,json,hashlib,subprocess,shutil,time
R=Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018');P=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');T=Path('/workspace/casepath-idle-read-transport-20261018');B='qa-receipts/idle-read-gate-16c10bc2-20261018';F='98c4b3042ee29678507dac09076a1bf8a8a99eb6';FB='qa-receipts/idle-read-transport-023a9d13-20261018';FS='qa-evidence/idle-read-transport-20261018'
R.mkdir(exist_ok=True);(R/'coordinator').mkdir(exist_ok=True)
for n in ['0']:
 for prefix in ['ilh','ilt']:Path('/workspace/'+prefix+n).mkdir(mode=0o700,exist_ok=True)
def git(*a):return subprocess.check_output(['git','-C',str(G),*a]).decode().strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert os.uname().nodename=='656813ef2295' and git('rev-parse','HEAD')=='cc395aa627e2063965780c7fb63a0e3a41982ad5' and sha(G/'.git/index')=='0022046a23b158d171f6a239bd7b0f21c23ec4372594997f0b4f7cd7d2ba3153'
assert git('ls-remote','origin','refs/heads/'+FB).split()[0]==F
subprocess.run(['git','-C',str(G),'fetch','origin','refs/heads/'+FB],check=True,capture_output=True);assert git('rev-parse','FETCH_HEAD')==F
sums=git('show',F+':'+FS+'/SHA256SUMS');checks=[]
for line in sums.splitlines():
 h,rel=line.split(None,1);raw=subprocess.check_output(['git','-C',str(G),'show',F+':'+FS+'/'+rel.strip()]);assert hashlib.sha256(raw).hexdigest()==h;checks.append({'path':rel.strip(),'sha256':h})
assert len(checks)==26
writer=Path('/workspace/casepath-release-ae0-shard3');branch='codex/casepath-idle-read-transport-20261018';WH='023a9d1365d94f4c84a4c59dbacbc2dae871ec92'
def wgit(*a):return subprocess.check_output(['git','-C',str(writer),*a],text=True).strip()
assert wgit('rev-parse','HEAD')==wgit('rev-parse',branch)==WH and not wgit('status','--porcelain') and wgit('ls-remote','origin','refs/heads/'+branch).split()[0]==WH
paths=[T/n for n in ['pytest-tools','proof-tools','pytest-basetemp','proof-pytest-basetemp','tmp']];owned=[];unreadable=0
for q in Path('/proc').iterdir():
 if not q.name.isdigit() or int(q.name)==os.getpid():continue
 try:
  args=[x.decode(errors='replace') for x in (q/'cmdline').read_bytes().split(b'\0') if x]
  if any(a.startswith(str(T)+'/') or a.startswith(str(writer)+'/.runtime/') for a in args):owned.append({'pid':int(q.name),'comm':(q/'comm').read_text().strip()})
 except OSError:unreadable+=1
assert not owned,owned
records=[]
for p in paths:
 assert p.is_dir() and not p.is_symlink();entries=[]
 for q in sorted(p.rglob('*')):
  if q.is_symlink():entries.append({'path':q.relative_to(p).as_posix(),'symlink':os.readlink(q)})
  elif q.is_file():entries.append({'path':q.relative_to(p).as_posix(),'bytes':q.stat().st_size,'sha256':sha(q)})
 records.append({'path':str(p),'allocated_bytes':sum(q.lstat().st_blocks*512 for q in p.rglob('*')),'file_inventory':entries})
d={'candidate':'16c10bc21c1b2b3b6602cb028028adf28e20823b','manifest_sha256':'e7fbfd43062c19ed04468966aee9a2c61dcb1064b8baaa449cd4a2fe841e0442','source_file_count':1719,'host':os.uname().nodename,'focused_commit':F,'focused_subtree':FS,'focused_checksums_verified':checks,'source_branch':{'path':str(writer),'branch':branch,'head':WH,'remote':WH,'clean':True},'approved_derived_paths':records,'owned_targeted_processes':owned,'cmdline_metadata_unreadable_count':unreadable,'process_qualification':'Bounded cmdline/cwd scope; no environments or proc maps inspected; parent reports targeted task complete','workspace_free_bytes':shutil.disk_usage('/workspace').free,'memory_current':Path('/sys/fs/cgroup/memory.current').read_text().strip(),'memory_max':Path('/sys/fs/cgroup/memory.max').read_text().strip(),'parent_seed_env_present':'CASEPATH_READ_SEED_PATH' in os.environ,'retirement_authorization':'Parent explicitly authorizes ONLY these completed targeted dependency/cache/temp directories after durable hash proof and no-active-process recheck; preserve every evidence/review/export/source/commit and all oldgate roots','epoch':time.time()}
assert not d['parent_seed_env_present'];(R/'approved-retirement-proof.json').write_text(json.dumps(d,indent=2)+'\n')
s=(P/'coordinator/export_receipts.py').read_text().replace(str(P),str(R)).replace('qa-receipts/read-seed-gate-addc5a77-20261018',B).replace('/workspace/rsh','/workspace/ilh').replace('/workspace/rst','/workspace/ilt');(R/'coordinator/export_receipts.py').write_text(s)
shutil.copy2('/workspace/idle16-proof.py',R/'coordinator/idle16-proof.py')
print(json.dumps({'proof_ready':str(R),'derived_allocated_bytes':sum(x['allocated_bytes'] for x in records),'focused26checksums_verified':True,'no_owned_target_processes':True}))
