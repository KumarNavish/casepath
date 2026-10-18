import hashlib,json,os,subprocess,sys,time
from pathlib import Path
R=Path('/workspace/casepath-startup-timing-gate-4a03578b-20261018');G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
BRANCH='qa-receipts/startup-timing-gate-4a03578b-20261018';SUBTREE=BRANCH
EXCLUDE={'home','tmp','pycache','uv-cache','artifact-registry','pytest-tmp','__pycache__'}
def selected():
 return [p for p in sorted(R.rglob('*')) if p.is_file() and not p.is_symlink() and not any(x in EXCLUDE for x in p.relative_to(R).parts) and (p.suffix in {'.py','.json','.jsonl','.txt','.log','.xml'} or p.name in {'SHA256SUMS','raw-evidence.tar.gz'} or p.name.endswith('-raw.tar.gz'))]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
transport=['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','NODE_EXTRA_CA_CERTS']
env={k:os.environ[k] for k in transport if k in os.environ};env.update(PATH='/usr/local/bin:/usr/bin:/bin',HOME='/workspace/t4h0',TMPDIR='/workspace/t4t0',TMP='/workspace/t4t0',TEMP='/workspace/t4t0',LANG='C.UTF-8',LC_ALL='C.UTF-8')
def git(*args,raw=None):return subprocess.check_output(['git',*args],cwd=G,env=env,input=raw).decode().strip()
before={'head':git('rev-parse','HEAD'),'index_sha256':digest(G/'.git/index') if (G/'.git/index').exists() else None}
ref='refs/heads/'+BRANCH
exists=subprocess.run(['git','show-ref','--verify','--quiet',ref],cwd=G,env=env).returncode==0
parent=git('rev-parse',ref) if exists else before['head']
env['GIT_INDEX_FILE']=str(R/'coordinator/evidence-isolated.index')
git('read-tree',parent)
files=selected();entries=[]
for p in files:
 oid=git('hash-object','-w','--stdin',raw=p.read_bytes());rel=SUBTREE+'/'+p.relative_to(R).as_posix();entries.append(('100644 '+oid+'\t'+rel+'\0').encode())
git('update-index','-z','--index-info',raw=b''.join(entries))
tree=git('write-tree')
commit=git('-c','user.name=Codex','-c','user.email=codex@openai.com','commit-tree',tree,'-p',parent,'-F','-',raw=(sys.argv[1]+'\n').encode())
git('update-ref',ref,commit,parent if exists else '0'*40)
assert git('rev-parse','HEAD')==before['head'] and (digest(G/'.git/index') if (G/'.git/index').exists() else None)==before['index_sha256']
push=subprocess.run(['git','push','origin',ref+':'+ref],cwd=G,env=env,capture_output=True,text=True)
record={'commit':commit,'branch':BRANCH,'subtree':SUBTREE,'selected_files':len(files),'push_exit_code':push.returncode,'push_output':push.stdout+push.stderr,'transport_checkout_head_index_unchanged':True,'transport_checkout_before':before,'isolated_index':env['GIT_INDEX_FILE'],'epoch':time.time()}
(R/'coordinator'/('export-'+commit[:12]+'.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
raise SystemExit(push.returncode)
