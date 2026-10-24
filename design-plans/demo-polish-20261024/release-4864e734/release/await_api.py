"""Poll the created FastAPI Cloud deployment to a terminal state, then confirm /healthz names the release.

Usage: await_api.py <release-commit> <receipt-dir>   (read-only; reads api-deployment-uploaded.json)
"""
if not __debug__:
    raise RuntimeError('Release helpers require Python assertions enabled.')
from pathlib import Path
import json, re, subprocess, sys, time
sys.dont_write_bytecode = True
import httpx

assert len(sys.argv)==3, 'usage: await_api.py <actual-release-commit> <receipt-dir>'
B=Path(sys.argv[2]).resolve();ROOT=Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024');NS=ROOT/'.runtime/commander-demo-polish'
assert B==NS/'release' and Path(__file__).resolve().parent==B
binding=json.loads((NS/'source-binding.json').read_text());SHA=binding['source_commit']
assert re.fullmatch(r'[0-9a-f]{40}',SHA) and sys.argv[1]==SHA and binding['base_commit']=='f75af1ac22a7260487556fc9231f4e290489c2e0'
from require_completed_gate import require_completed_gate
require_completed_gate(B,SHA)
deployment = json.loads((B / 'api-deployment-uploaded.json').read_text())
assert deployment['source_commit'] == SHA
command = ['/Users/kumar0002/.local/bin/uv', 'run', '--offline', '--no-project', '--with', 'fastapi[standard]', '--with', 'fastapi-cloud-cli==0.26.0', 'fastapi', 'cloud', 'deployments', 'get',
           deployment['deployment_id'], '--app-id', 'ebd0862c-cd35-4da4-aae5-d32f1c40ca60', '--json']
started, status = time.time(), None
while time.time() - started < 1800:
    r = subprocess.run(command, capture_output=True, text=True, cwd='/private/tmp',timeout=90)
    if r.returncode == 0:
        data = json.loads(r.stdout)
        status = data['data']['deployment']['status']
        (B / 'api-deployment-observed.json').write_text(json.dumps(data,indent=2)+'\n')
        print(time.strftime('%H:%M:%S'), status, flush=True)
        if status == 'success' or 'fail' in status or status in ('expired', 'cancelled', 'canceled'):
            (B / 'api-deployment-status.json').write_text(json.dumps(data, indent=2) + '\n')
            break
    time.sleep(15)
assert status == 'success', 'The original API deployment did not reach success; reconcile its receipt before retrying'
health = None
for _ in range(20):
    try:
        response = httpx.get('https://casepath-agent.fastapicloud.dev/healthz', timeout=20, trust_env=False)
        response.raise_for_status()
        health = response.json()
        if health.get('source_commit') == SHA:
            break
    except Exception as error:  # a waking deployment may briefly refuse
        health = {'error_type': type(error).__name__}
    time.sleep(15)
(B / 'api-health-after.json').write_text(json.dumps(health, indent=2) + '\n')
print(json.dumps({'status': status, 'health': health}))

assert health.get('source_commit') == SHA and health.get('status') == 'ok' and health.get('read_only') is True and health.get('writable') is False and health.get('storage') == 'remote_primary', 'The deployed API identity or read-only storage contract did not verify'

