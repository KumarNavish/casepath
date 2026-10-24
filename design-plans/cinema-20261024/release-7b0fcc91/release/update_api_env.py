"""Set CASEPATH_SOURCE_COMMIT and CASEPATH_READ_SEED_SHA256 on FastAPI Cloud without redeploying.

Usage: update_api_env.py <release-commit> <receipt-dir>   (values go to the CLI over stdin)
"""
if not __debug__:
    raise RuntimeError('Release helpers require Python assertions enabled.')
from pathlib import Path
import hashlib, json, os, re, subprocess, sys
sys.dont_write_bytecode = True

assert len(sys.argv)==3, 'usage: update_api_env.py <actual-release-commit> <receipt-dir>'
B=Path(sys.argv[2]).resolve()
ROOT=Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-cinema-final-20261024');NS=ROOT/'.runtime/cinema-release'
assert B==NS/'release' and Path(__file__).resolve().parent==B
binding=json.loads((NS/'source-binding.json').read_text());SHA=binding['source_commit']
assert re.fullmatch(r'[0-9a-f]{40}',SHA) and sys.argv[1]==SHA and binding['base_commit']=='0ccf1eafcd27e0827e2d0778f9c2642e34cd05f9'
from require_completed_gate import require_completed_gate
require_completed_gate(B,SHA)
gate = json.loads((B / 'full-gate-verified.json').read_text()); assert gate['canonical_commit'] == SHA and gate['new_skips']==0 and gate['deselected']==0 and gate['failed']==0 and gate['errors']==0 and gate['exit_code']==0
seed = json.loads((B / 'seed-renewal-receipt.json').read_text()); assert seed['deployment_commit'] == SHA
assert seed['input_commit']=='4864e7347c299bf1b580a5b35667635bc1c47f15' and seed['input_sha256']=='be37e32d5498aeaf6d61d39de41d26424a009e8d90859de9b95fedd14e3d3997'
assert seed['input_bytes']==13330327 and seed['raw_records_and_sources_unchanged'] is True and seed['native_replay_and_full_fresh_atomic_proof'] is True
assert seed['read_only'] is True and seed['requests']==1 and seed['retries']==0
seed_path=Path('/Users/kumar0002/Library/Application Support/CasePath')/('private-release-'+SHA[:12])/'hosted-read-seed-v1.json'
assert Path(seed['artifact_path'])==seed_path and seed_path.stat().st_size==seed['bytes']
assert hashlib.sha256(seed_path.read_bytes()).hexdigest()==seed['sha256']
receipt = B / 'api-environment-updated.json'
assert not receipt.exists(), 'Read the existing receipt before repeating environment changes'
rows = []
state={'source_commit':SHA,'status':'running','seed_sha256':seed['sha256'],'receipts':rows}
with receipt.open('x') as f:
    json.dump(state,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def persist():
    temporary=receipt.with_suffix('.next')
    with temporary.open('w') as f:
        json.dump(state,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary,receipt)
for name, value in [('CASEPATH_SOURCE_COMMIT', SHA), ('CASEPATH_READ_SEED_SHA256', seed['sha256'])]:
    command = ['/Users/kumar0002/.local/bin/uv', 'run', '--offline', '--no-project', '--with', 'fastapi[standard]', '--with', 'fastapi-cloud-cli==0.26.0', 'fastapi', 'cloud', 'env', 'set', name,
               '--app-id', 'ebd0862c-cd35-4da4-aae5-d32f1c40ca60', '--value-stdin', '--secret', '--no-redeploy', '--json']
    row={'name':name,'status':'requested','no_redeploy':True};rows.append(row);persist()
    try:
        r = subprocess.run(command, input=value + '\n', text=True, capture_output=True,timeout=120)
    except BaseException as error:
        state.update(status='uncertain',error_type=type(error).__name__);persist();raise
    row.update(status='completed' if r.returncode==0 else 'failed',exit_code=r.returncode);persist()
    if r.returncode:
        state['status']='failed';persist()
        raise RuntimeError('Environment update failed; reconcile the named receipt before continuing')
state['status']='passed';persist()
print('Both deployment identity values updated without redeploying.')

