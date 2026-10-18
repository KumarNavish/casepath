"""Run the unverified gate remainder once on the prepared, isolated Mac clone."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent / 'casepath-operations-validation-20261013'
OUT = BASE / 'mac-final-cloud6/shard1'
HARNESS = BASE / 'mac-final-cloud6/harness'
SHA = '4f8269c1781c4097f79790f39dd0312a2f9f32bf'
PYTHON = ROOT / '.runtime/casepath-dev-v2/venv/bin/python'
assert not (OUT / 'ATTEMPT_STARTED.json').exists()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SHA
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
assert not (ROOT / 'casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json').exists()
for port in (4173, 4187):
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(('127.0.0.1', port)) != 0, 'Preview listener is active.'

env = json.loads((BASE / 'gate/mac-shard-environment.json').read_text())
env = {key: value.replace(str(BASE / 'gate/mac-shard-runtime'), str(OUT / 'runtime')).replace(str(BASE / 'gate/harness'), str(HARNESS)) for key, value in env.items()}
env['CASEPATH_QA_ARTIFACTS'] = str(OUT)
env['PYTHONPATH'] = str(HARNESS) + os.pathsep + str(ROOT / 'casepath-api')
assert env['CASEPATH_SOURCE_COMMIT'] == SHA
assert not any(key in env for key in ('OPENROUTER_API_KEY', 'TURSO_AUTH_TOKEN', 'CASEPATH_PROXY_TOKEN', 'CASEPATH_READ_SEED_PATH'))
for key in ('HOME', 'TMPDIR', 'PYTHONPYCACHEPREFIX', 'CASEPATH_ARTIFACT_REGISTRY_PATH'):
    Path(env[key]).mkdir(parents=True, exist_ok=True)

proof_command = [str(PYTHON), '-P', str(HARNESS / 'verify_prepared_capsules.py'), 'shard1']
subprocess.run(proof_command + ['before'], cwd=ROOT, env=env, check=True)
sys.path.insert(0, str(HARNESS))
from runtime_inventory import capture_runtime
capture_runtime(ROOT, OUT, 'before')

ids = (OUT / 'pytest-arguments.txt').read_text().splitlines()
assert len(ids) == len(set(ids)) == 658
command = [str(PYTHON), '-P', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-p', 'casepath_shard_observer',
           '-o', 'tmp_path_retention_policy=failed', '--durations=0', '--junitxml=' + str(OUT / 'junit.xml'),
           '--basetemp=' + str(OUT / 'pytest-tmp'), '@' + str(OUT / 'pytest-arguments.txt')]
record = {'candidate': SHA, 'cwd': str(ROOT), 'command': command, 'env': env, 'started_epoch': time.time(),
          'nice': os.getpriority(os.PRIO_PROCESS, 0), 'test_count': len(ids), 'single_process': True,
          'manifest_sha256': hashlib.sha256((ROOT / 'casepath/source-manifest.json').read_bytes()).hexdigest()}
assert record['nice'] >= 15
with (OUT / 'ATTEMPT_STARTED.json').open('x') as target:
    json.dump(record, target, indent=2)
(OUT / 'command.json').write_text(json.dumps(record, indent=2) + '\n')
with (OUT / 'pytest.log').open('x') as target:
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=target, stderr=subprocess.STDOUT)
record.update(exit_code=result.returncode, finished_epoch=time.time())
record['duration_seconds'] = record['finished_epoch'] - record['started_epoch']
record['after_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
record['after_status'] = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
(OUT / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
subprocess.run(proof_command + ['after'], cwd=ROOT, env=env, check=True)
print(json.dumps({key: record[key] for key in ('candidate', 'exit_code', 'duration_seconds', 'test_count', 'nice', 'after_head', 'after_status')}), flush=True)
raise SystemExit(result.returncode)
