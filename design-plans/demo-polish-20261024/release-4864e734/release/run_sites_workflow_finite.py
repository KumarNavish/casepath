"""Finite-stdin bridge to the installed official Sites workflow; never persists credentials."""
if not __debug__:raise RuntimeError('Assertions required')
from pathlib import Path
import datetime,hashlib,json,os,re,subprocess,sys
BASE=Path(__file__).resolve().parent
DIST=Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-sites-distribution-20261009')
SOURCE=json.loads((BASE.parent/'source-binding.json').read_text())['source_commit']
assert re.fullmatch('[0-9a-f]{40}',SOURCE)
PREVIOUS='b20685d1670b33b941b1bfcb902638a879c01b93'
EXPECTED='bb02a959c26b85681529f4a9e9e788ff1417f2aa'
PROJECT='appgprj_6ac8aab031988191b5c370f7a4dbf160'
from require_completed_gate import require_completed_gate
require_completed_gate(BASE, SOURCE)
assert len(sys.argv)==2 and sys.argv[1] in ('open','package')
mode=sys.argv[1]
print('Ready for Sites workflow JSON through finite stdin.',flush=True)
payload=json.loads(sys.stdin.readline())
assert payload['source']['project_id']==PROJECT and payload['source']['checkout_path']==str(DIST)
credential=payload['credential']
assert credential['branch']=='main' and credential['auth_mode'] in ('http_extra_header','work_proxy')
environment=dict(os.environ)
environment.pop('RENDER_GIT_COMMIT',None)
for key in list(environment):
 if key.startswith('GIT_TRACE') or key=='GIT_CURL_VERBOSE':environment.pop(key)
environment.update(CASEPATH_SOURCE_COMMIT=SOURCE,CASEPATH_FRONTEND_ORIGIN='https://casepath-autonomous.kumarnavish.chatgpt.site',COPYFILE_DISABLE='1')
def git(*args,env=None):return subprocess.check_output(['/usr/bin/git',*args],cwd=DIST,env=env,text=True,timeout=60).strip()
assert git('rev-parse','HEAD')==EXPECTED,'Distribution HEAD changed; reconcile before continuing'
assert git('branch','--show-current')=='main'
authenticated=dict(environment)
auth_args=['-c','credential.helper=','-c','http.extraHeader=','-c','http.followRedirects=false']
secret=None
if credential['auth_mode']=='http_extra_header':
 secret=credential['token']
 authenticated['SITES_GIT_AUTHORIZATION']='Authorization: Bearer '+secret
 auth_args+=['--config-env=http.'+credential['remote_url']+'.extraHeader=SITES_GIT_AUTHORIZATION']
reference='refs/heads/main'
def remote_head():return git(*auth_args,'ls-remote','--heads',credential['remote_url'],reference,env=authenticated)
remote=remote_head()
assert remote==EXPECTED+'\t'+reference,'Sites remote changed; reconcile before continuing'
provenance=json.loads((DIST/'casepath-source-provenance.json').read_text())
proof=json.loads((BASE/'full-gate-verified.json').read_text())
assert proof['canonical_commit']==SOURCE and proof['exit_code']==0
if mode=='open':
 assert not git('status','--porcelain')
 assert provenance['canonical_commit']==PREVIOUS
 assert 'archivePath' not in payload and not payload.get('commands')
 output_name='sites-source-open.json'
else:
 assert provenance['canonical_commit']==SOURCE
 inputs=json.loads((BASE/'sites-inputs-verified.json').read_text())
 assert inputs['canonical_commit']==SOURCE and inputs['all_canonical_inputs_exact'] and inputs['private_seed_excluded']
 assert subprocess.check_output(['/usr/bin/git','status','--porcelain'],cwd=DIST,text=True).splitlines()==inputs['changed_paths']
 assert payload['commands']==[['python3','casepath/tools/build_static_site.py','--require-known-commit'],['python3','casepath/tools/build_sites_site.py']]
 assert payload['archivePath']==str(BASE/('casepath-public-'+SOURCE[:8]+'.tar.gz'))
 assert not Path(payload['archivePath']).exists()
 output_name='sites-workflow-result.json'
receipt=BASE/('sites-'+mode+'-command.json')
assert not receipt.exists() and not (BASE/output_name).exists()
record={'source_commit':SOURCE,'mode':mode,'distribution_before':EXPECTED,'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'running','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with receipt.open('x') as f:json.dump(record,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
command=['/usr/local/bin/node','/Users/kumar0002/.codex/plugins/cache/openai-curated-remote/sites/1.1.2/scripts/site-workflow.mjs','--project-id',PROJECT]
result=subprocess.run(command,input=json.dumps(payload)+'\n',text=True,capture_output=True,cwd=DIST,env=environment,timeout=300)
# The official workflow hides credential input. Redact defensively before persisting diagnostics.
stdout=result.stdout.replace(secret,'[redacted]') if secret else result.stdout
stderr=result.stderr.replace(secret,'[redacted]') if secret else result.stderr
log=BASE/('sites-'+mode+'-command.log')
with log.open('x') as f:f.write(stdout);f.write(stderr)
record.update(exit_code=result.returncode,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),status='command_completed' if result.returncode==0 else 'failed')
def persist():
 tmp=receipt.with_suffix('.next');tmp.write_text(json.dumps(record,indent=2)+'\n');os.replace(tmp,receipt)
persist()
if result.returncode!=0:
 print((stdout+stderr)[-5000:],flush=True);raise SystemExit(result.returncode)
rows=[]
for line in stdout.splitlines():
 try:value=json.loads(line)
 except ValueError:continue
 if isinstance(value,dict) and value.get('project_id')==PROJECT and value.get('checkout_path')==str(DIST):rows.append(value)
assert len(rows)==1
value=rows[0]
assert re.fullmatch('[0-9a-f]{40}',value['commit_sha'])
assert git('rev-parse','HEAD')==value['commit_sha'] and not git('status','--porcelain')
assert remote_head()==value['commit_sha']+'\t'+reference
if mode=='open':
 assert value['commit_sha']==EXPECTED
 assert json.loads((DIST/'casepath-source-provenance.json').read_text())['canonical_commit']==PREVIOUS
else:
 assert value['commit_sha']!=EXPECTED
 assert value['archive']==payload['archivePath'] and Path(value['archive']).is_file()
 assert json.loads((DIST/'dist/client/deployment.json').read_text())['source_commit']==SOURCE
 assert json.loads((DIST/'casepath-source-provenance.json').read_text())['canonical_commit']==SOURCE
with (BASE/output_name).open('x') as f:json.dump(value,f,indent=2);f.write('\n')
record.update(status='passed',distribution_after=value['commit_sha'],result_sha256=hashlib.sha256((BASE/output_name).read_bytes()).hexdigest())
persist()
print(json.dumps({'exit_code':result.returncode,'mode':mode,'workflow':value}),flush=True)

