"""Execute one verified API release with durable, sequential stage receipts."""
if not __debug__:
    raise RuntimeError('API release execution requires Python assertions enabled.')
from pathlib import Path
import datetime, hashlib, json, os, re, subprocess, sys
sys.dont_write_bytecode = True
BASE=Path(__file__).resolve().parent
ROOT=Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024')
NS=ROOT/'.runtime/documentary-release-20261025'
assert BASE == NS/'release'
binding=json.loads((NS/'source-binding.json').read_text())
SHA=binding['source_commit']
assert re.fullmatch(r'[0-9a-f]{40}',SHA) and binding['base_commit']=='5da3233a0aa04ad29843c8ec55dfb685118381c9'
PYTHON=ROOT/'.runtime/casepath-dev-v2/venv/bin/python'
from require_completed_gate import require_completed_gate
require_completed_gate(BASE, SHA)
proof_path=BASE/'full-gate-verified.json'
proof=json.loads(proof_path.read_text())
assert proof['canonical_commit']==SHA and proof['exit_code']==0
assert all(proof[k]==0 for k in ['new_skips','deselected','failed','errors'])
integration=json.loads((BASE/'canonical-integration.json').read_text())
assert integration['canonical_commit']==SHA and integration['status']=='pushed_and_verified'
assert subprocess.check_output(['/usr/bin/git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SHA
assert not subprocess.check_output(['/usr/bin/git','status','--porcelain'],cwd=ROOT,text=True).strip()
hashes=json.loads((BASE/"helper-final-binding.json").read_text())["api_helpers"]
required_helpers={'integrate_canonical.py','run_api_release.py','renew_seed.py','update_api_env.py','deploy_api.py','await_api.py','require_completed_gate.py'}
assert set(hashes)==required_helpers, 'Bind exactly the six API helpers and release guard shim'
for name,expected in hashes.items():
    assert re.fullmatch(r'[0-9a-f]{64}',expected),name
    assert hashlib.sha256((BASE/name).read_bytes()).hexdigest()==expected,name
import httpx
previous='5da3233a0aa04ad29843c8ec55dfb685118381c9'
response=httpx.get('https://casepath-agent.fastapicloud.dev/healthz',timeout=20,trust_env=False)
response.raise_for_status()
current=response.json()
assert current.get('status')=='ok' and current.get('source_commit')==previous and current.get('read_only') is True and current.get('writable') is False and current.get('storage')=='remote_primary'
with (BASE/'api-identity-immediately-before.json').open('x') as f:json.dump(current,f,indent=2);f.write('\n')
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
receipt=BASE/'api-release-sequence.json'
state={'source_commit':SHA,'status':'running','started_at':now(),'stages':[],
       'gate_sha256':hashlib.sha256(proof_path.read_bytes()).hexdigest(),'helper_sha256':hashes}
with receipt.open('x') as output:
    json.dump(state,output,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
def persist():
    temporary=receipt.with_suffix('.next')
    with temporary.open('w') as output:
        json.dump(state,output,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
    os.replace(temporary,receipt)
environment={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin:/Users/kumar0002/.local/bin:/usr/local/bin',
             'PYTHONPATH':str(ROOT/'casepath-api'),'PYTHONDONTWRITEBYTECODE':'1',
             'SOURCE_DATE_EPOCH':'1786406400','CASEPATH_SOURCE_COMMIT':SHA,
             'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC'}
if 'HOME' in os.environ:environment['HOME']=os.environ['HOME']
commands=[
    ('seed',[str(PYTHON),'-B',str(BASE/'renew_seed.py'),SHA,str(BASE)]),
    ('environment',[str(PYTHON),'-B',str(BASE/'update_api_env.py'),SHA,str(BASE)]),
    ('deployment',['/Users/kumar0002/.local/bin/uv','run','--offline','--no-project','--with','fastapi[standard]','--with','fastapi-cloud-cli==0.26.0','python','-B',str(BASE/'deploy_api.py'),SHA,str(BASE)]),
    ('activation',[str(PYTHON),'-B',str(BASE/'await_api.py'),SHA,str(BASE)]),
]
try:
    for name,command in commands:
        require_completed_gate(BASE,SHA)
        for helper,expected in hashes.items():
            assert hashlib.sha256((BASE/helper).read_bytes()).hexdigest()==expected,helper
        log=BASE/('api-release-'+name+'.log')
        stage={'name':name,'command':command,'status':'starting','started_at':now(),'log':str(log)}
        state['stages'].append(stage);persist()
        with log.open('x') as output:
            process=subprocess.Popen(command,cwd=ROOT,env=environment,stdout=output,stderr=subprocess.STDOUT)
            stage.update(status='running',pid=process.pid);persist()
            print(json.dumps({'stage':name,'status':'running','pid':process.pid}),flush=True)
            code=process.wait()
        stage.update(status='completed' if code==0 else 'failed',exit_code=code,finished_at=now(),
                     log_sha256=hashlib.sha256(log.read_bytes()).hexdigest());persist()
        print(json.dumps({'stage':name,'exit_code':code}),flush=True)
        if code!=0:
            raise RuntimeError('The '+name+' stage failed. Reconcile its original receipts before continuing.')
    state.update(status='passed',finished_at=now());persist()
    print(json.dumps({'status':'passed','source_commit':SHA,'receipt':str(receipt)}),flush=True)
except BaseException as error:
    state.update(status='failed',finished_at=now(),error_type=type(error).__name__);persist()
    raise

