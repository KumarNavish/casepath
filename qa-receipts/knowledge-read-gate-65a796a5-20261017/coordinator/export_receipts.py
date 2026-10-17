from pathlib import Path
import hashlib,json,os,shutil,stat,subprocess,sys
R=Path('/workspace/casepath-knowledge-read-gate-65a796a5-20261017');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015');SUBTREE='qa-receipts/knowledge-read-gate-65a796a5-20261017';D=G/SUBTREE
files=[p for p in R.iterdir() if p.is_file() and (p.suffix in {'.json','.jsonl','.txt','.log'} or p.name in ['SHA256SUMS','raw-evidence.tar.gz'])]
for name in ['harness','coordinator','inventory','retirement-receipts']:
 directory=R/name
 if directory.exists():files += [p for p in directory.iterdir() if p.is_file() and (p.suffix in {'.py','.json','.jsonl','.txt','.log','.xml'} or p.name.endswith('-raw.tar.gz'))]
completed=[]
for n in range(1,7):
 directory=R/f'shard{n}'
 if not (directory/'source-after/capsule-verification.json').exists() or not (R/f'retirement-receipts/shard{n}-raw-archive.json').exists():continue
 completed.append(n)
 files += [p for p in directory.iterdir() if p.is_file() and p.suffix in {'.json','.jsonl','.txt','.log','.xml'}]
 for phase in ['before','after']:files += [p for p in (directory/f'source-{phase}').iterdir() if p.is_file()]
env={k:v for k,v in os.environ.items() if k in ['PATH','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','NODE_EXTRA_CA_CERTS']};env.update(HOME='/workspace/k65h0',TMPDIR='/workspace/k65t0',TMP='/workspace/k65t0',TEMP='/workspace/k65t0',LANG='C.UTF-8',LC_ALL='C.UTF-8')
def git(*args):return subprocess.check_output(['git',*args],cwd=G,env=env,text=True).rstrip('\n')
assert git('branch','--show-current')=='qa-receipts/knowledge-read-gate-65a796a5-20261017'
status=git('status','--porcelain');assert all(line[3:].startswith(SUBTREE+'/') for line in status.splitlines())
identical=0;copied=0
for p in sorted(set(files)):
 assert not p.is_symlink()
 q=D/p.relative_to(R);q.parent.mkdir(parents=True,exist_ok=True)
 if q.exists() and q.read_bytes()==p.read_bytes():identical+=1;continue
 if q.exists():q.chmod(q.stat().st_mode|stat.S_IWUSR)
 shutil.copy2(p,q);copied+=1
assert all((D/p.relative_to(R)).read_bytes()==p.read_bytes() for p in files if p.name not in ['resource-observations.jsonl','scheduler-events.jsonl'])
git('add','--',SUBTREE)
git('-c','user.name=Codex','-c','user.email=codex@openai.com','commit','-m',sys.argv[1])
print(json.dumps({'commit':git('rev-parse','HEAD'),'branch':git('branch','--show-current'),'subtree':SUBTREE,'completed_shards_exported':completed,'identical_existing_files_preserved':identical,'files_copied':copied,'status':git('status','--porcelain')}),flush=True)
