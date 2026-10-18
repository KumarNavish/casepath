"""Run the unchanged Mac-only full-gate partition once, after normal prepare."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import time

BASE = Path(__file__).resolve().parent
PREVIOUS = BASE.parent / 'casepath-operation-motion-20261013'
ROOT = BASE.parent / 'casepath-operations-validation-20261013'
OUT = BASE / 'gate'
COMMIT = '4f8269c1781c4097f79790f39dd0312a2f9f32bf'
MANIFEST = '3532003ba5f916e4d45d02ff57139fb4122d69001667d14f4431f2b4771dd790'

def source_check():
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == COMMIT
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    raw = (ROOT / 'casepath/source-manifest.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == MANIFEST
    rows = json.loads(raw)['files']
    for row in rows:
        content = (ROOT / row['path']).read_bytes()
        assert len(content) == row['size_bytes'] and hashlib.sha256(content).hexdigest() == row['sha256']
    return len(rows)

assert (OUT / 'PREPARE_COMPLETED.json').exists()
assert not (OUT / 'ATTEMPT_STARTED.json').exists()
assert (ROOT / '.runtime/casepath-dev-v2/source-capsules' / MANIFEST).is_dir()
for port in (4173, 4187):
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(('127.0.0.1', port)) != 0, 'A preview must stop before the Mac gate.'
count = source_check()
runtime = OUT / 'mac-shard-runtime'
runtime.mkdir()
for name in ('home', 'tmp', 'pycache', 'artifact-registry'):
    (runtime / name).mkdir()
(OUT / 'harness').mkdir()
shutil.copy2(PREVIOUS / 'gate/harness/casepath_shard_observer.py', OUT / 'harness/casepath_shard_observer.py')
env = {key: value.replace(str(PREVIOUS / 'gate'), str(OUT)) for key, value in
       json.loads((PREVIOUS / 'gate/mac-shard-environment.json').read_text()).items()}
env['CASEPATH_SOURCE_COMMIT'] = COMMIT
command = [value.replace(str(PREVIOUS / 'gate'), str(OUT)) for value in
           json.loads((PREVIOUS / 'gate/mac-shard-command.json').read_text())]
assert not any(key in env for key in ('OPENROUTER_API_KEY', 'TURSO_AUTH_TOKEN', 'CASEPATH_PROXY_TOKEN'))
for name, data in (('mac-shard-command.json', command), ('mac-shard-environment.json', env)):
    (OUT / name).write_text(json.dumps(data, indent=2) + '\n')
started = time.time()
(OUT / 'ATTEMPT_STARTED.json').write_text(json.dumps({'source_commit': COMMIT, 'started_epoch': started}) + '\n')
with (OUT / 'mac-shard.log').open('x') as log:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
assert source_check() == count
receipt = {'source_commit': COMMIT, 'exit_code': result.returncode, 'seconds': time.time() - started,
    'source_files_verified': count, 'manifest_sha256': MANIFEST, 'source_clean_after': True}
(OUT / 'mac-shard-result.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt), flush=True)
raise SystemExit(result.returncode)
