"""Run the already-reviewed live acceptance helpers once, after confirmed Sites publication."""
if not __debug__: raise RuntimeError('Assertions required')
from pathlib import Path
import datetime, hashlib, json, os, signal, subprocess
NS=Path(__file__).resolve().parent
BASE=NS/'release'; OWN=NS.parent.parent
ROOT=OWN
DIST=OWN.parent/'casepath-sites-distribution-20261009'
SHA=json.loads((NS/'source-binding.json').read_text())['source_commit']
PROJECT='appgprj_6ac8aab031988191b5c370f7a4dbf160'
PYTHON=str(ROOT/'.runtime/casepath-dev-v2/venv/bin/python')
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
binding=read(BASE/'helper-acceptance-binding.json')
assert binding['source_commit']==SHA
expectation=read(BASE/'presentation-expectation.json')
assert expectation['source_commit']==SHA
assert digest(__file__)==binding['acceptance_runner_sha256'], 'Acceptance runner differs from the reviewed binding'
def verify_helpers():
 for name,expected in binding['helpers'].items(): assert digest(BASE/name)==expected,name
verify_helpers()
proof=read(BASE/'full-gate-verified.json')
assert proof['canonical_commit']==SHA and proof['exit_code']==0 and proof['fresh_complete_gate']
import sys
sys.path.insert(0,str(BASE))
from require_completed_gate import require_completed_gate
require_completed_gate(BASE,SHA)
api=read(BASE/'api-release-sequence.json')
assert api['source_commit']==SHA and api['status']=='passed'
saved=read(BASE/'sites-saved-version.json')
deployed=read(BASE/'sites-deployment.json')
workflow=read(BASE/'sites-workflow-result.json')
assert saved['project_id']==deployed['project_id']==workflow['project_id']==PROJECT
assert deployed['version_id']==saved['id'] and deployed['status']=='succeeded'
assert deployed['url']=='https://casepath-autonomous.kumarnavish.chatgpt.site'
assert saved['source']['commit_sha']==workflow['commit_sha']
git=lambda root,*args:subprocess.check_output(['/usr/bin/git',*args],cwd=root,text=True,timeout=60).strip()
for root in (ROOT,):
 assert git(root,'rev-parse','HEAD')==SHA and not git(root,'status','--porcelain')
assert git(DIST,'rev-parse','HEAD')==workflow['commit_sha'] and not git(DIST,'status','--porcelain')
assert read(DIST/'casepath-source-provenance.json')['canonical_commit']==SHA
assert read(DIST/'dist/client/deployment.json')['source_commit']==SHA
assert digest(BASE/'readback-before.json')==read(BASE/'baseline-binding.json')['readback_sha256']
SOAK=BASE/('published-soak-'+SHA[:8])
BROWSER=BASE/('published-browser-'+SHA[:8])
assert not SOAK.exists() and not BROWSER.exists()
assert not (BASE/'readback-after.json').exists() and not (BASE/'readback-verified.json').exists()
receipt=BASE/'published-acceptance-sequence.json'
state={'source_commit':SHA,'status':'running','started_at':now(),'stages':[],
       'script_sha256':digest(__file__),'helper_binding_sha256':digest(BASE/'helper-acceptance-binding.json'),
       'site_version_id':saved['id'],'site_version_number':saved['version_number'],
       'distribution_commit':workflow['commit_sha'],'site_deployment_id':deployed['id']}
with receipt.open('x') as f:json.dump(state,f,indent=2);f.write('\n')
def persist():
 temporary=receipt.with_suffix('.next')
 temporary.write_text(json.dumps(state,indent=2)+'\n');os.replace(temporary,receipt)
environment={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin:/Users/kumar0002/.local/bin:/usr/local/bin','PYTHONDONTWRITEBYTECODE':'1','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC'}
if 'HOME' in os.environ:environment['HOME']=os.environ['HOME']
active_proc=None
def cleanup_child():
 global active_proc
 child=active_proc
 if child is None or child.poll() is not None:
  active_proc=None;return
 try:
  os.killpg(child.pid,signal.SIGTERM)
 except ProcessLookupError:pass
 try:child.wait(timeout=15)
 except subprocess.TimeoutExpired:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  child.wait(timeout=15)
 active_proc=None
def interrupted(signum,frame):
 raise SystemExit(128+signum)
signal.signal(signal.SIGTERM,interrupted)
stages=[
 ('soak',[PYTHON,'-B',str(BASE/'published_soak.py'),'--source',SHA,'--baseline',str(BASE/'readback-before.json'),'--out',str(SOAK)],1200,
  [SOAK/'summary.json',SOAK/'receipts.jsonl']),
 ('browser',['/usr/local/bin/node',str(BASE/'verify_published.mjs'),SHA,str(BROWSER)],1200,
  [BROWSER/'summary.json',BROWSER/'published-verification.json']),
 ('image',[PYTHON,'-B',str(BASE/'verify_public_image.py'),SHA],120,
  [BASE/'public-image-verified.json']),
 ('readback',[PYTHON,'-B',str(BASE/'readback.py'),str(BASE/'readback-after.json'),'--require-primary'],180,
  [BASE/'readback-after.json']),
 ('verify_readback',[PYTHON,'-B',str(BASE/'verify_readback.py'),str(BASE),SHA],60,
  [BASE/'readback-verified.json'])]
try:
 for name,command,limit,artifacts in stages:
  verify_helpers()
  log=BASE/('published-'+name+'-command.log')
  stage={'name':name,'command':command,'status':'running','started_at':now(),'log':str(log)}
  state['stages'].append(stage);persist()
  print(json.dumps({'stage':name,'status':'running','source_commit':SHA}),flush=True)
  with log.open('x') as output:
   proc=subprocess.Popen(command,cwd=OWN,env=environment,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
   active_proc=proc
   stage['pid']=proc.pid;persist()
   try: code=proc.wait(timeout=limit)
   except subprocess.TimeoutExpired:
    cleanup_child()
    stage.update(status='timed_out',finished_at=now(),log_sha256=digest(log));persist()
    raise RuntimeError('Owned live verification timed out; reconcile original receipts: '+name)
  stage.update(exit_code=code,status='completed' if code==0 else 'failed',finished_at=now(),log_sha256=digest(log))
  stage['artifacts']=[{'path':str(path),'sha256':digest(path)} for path in artifacts if path.is_file()]
  persist()
  print(json.dumps({'stage':name,'exit_code':code}),flush=True)
  assert code==0,'Live acceptance failed; preserve and inspect original evidence: '+name
  assert len(stage['artifacts'])==len(artifacts)
 soak=read(SOAK/'summary.json');browser=read(BROWSER/'summary.json');final=read(BASE/'readback-verified.json')
 assert soak['source_commit']==SHA and soak['passed'] and soak['observed_soak_requests']==300
 assert soak['successful_soak_requests']==300 and soak['soak_http_503_count']==0
 assert soak['verification_requests']==7 and soak['runner_retries']==0 and soak['provider_calls_initiated']==0
 assert len(browser['windows'])==2
 assert [w['rendered'] for w in browser['windows']]==[18,9]
 assert all(w['commit_ok'] and w['rendered']==w['total'] and not w['identity_failures'] and not w['errors'] and not w['writes'] and not w['overflow'] and w['served_assets_verified']>=11 and w['required_static_assets_verified']>0 and w['review_assets_verified']==2 for w in browser['windows'])
 assert browser['windows'][1]['mobile_document_rows']>0 and browser['windows'][1]['mobile_document_failures']==0
 assert browser['film']['reached_end'] and browser['film']['duration_ms']==expectation['duration_ms']
 assert final['canonical_commit']==final['api_commit']==final['frontend_commit']==SHA
 assert final['primary_reads_verified'] and final['collection_unchanged'] and final['knowledge_unchanged'] and final['ledger_unchanged']
 assert final['read_only'] is True and final['writable'] is False and final['storage']=='remote_primary'
 assert final['claims']==159 and final['provider_calls']==42 and final['original_nine_workflows']==9 and final['original_nine_calls']==18
 image=read(BASE/'public-image-verified.json')
 assert image['source_commit']==SHA and image['passed'] and image['matches_sealed_original'] and image['local_pillow']=='13.0.0'
 state.update(status='passed',finished_at=now());persist()
 print(json.dumps({'status':'passed','source_commit':SHA,'sequential_soak_reads':300,'desktop_case_views':18,'mobile_case_views':9,'primary_final_readback':True}),flush=True)
except BaseException as error:
 state.update(status='failed',failure=repr(error),finished_at=now());persist();raise
finally:
 cleanup_child()

