import json, os, shutil, subprocess, sys, time
from pathlib import Path

R = Path('/workspace/casepath-read-seed-gate-addc5a77-20261018')
n = sys.argv[1]
assert n in [str(i) for i in range(1, 7)]
out = R / ('shard' + n)
repo = Path(json.loads((R / 'clone-map.json').read_text())['repos'][n])
assert not (out / 'PREPARE_STARTED.json').exists()
assert not (out / 'ATTEMPT_STARTED.json').exists()
free = shutil.disk_usage('/workspace').free
assert free >= 3 * 1024**3 + 500 * 1024**2, free
with (out / 'prepare-admission.json').open('x') as f:
    json.dump({'shard': n, 'free_bytes': free, 'floor_bytes': 3 * 1024**3,
               'reserved_prepare_bytes': 500 * 1024**2, 'epoch': time.time()}, f, indent=2)
env = dict(os.environ)
env.update(TMPDIR='/workspace/rst' + n, TMP='/workspace/rst' + n, TEMP='/workspace/rst' + n)
for script, args, log in [('harness/prepare_clones.py', ['shard' + n], 'prepare-wrapper.log'),
                          ('coordinator/verify.py', [n, 'before'], 'verify-before-wrapper.log')]:
    with (out / log).open('x') as f:
        result = subprocess.run(['/usr/bin/python3', str(R / script), *args],
                                cwd=repo, env=env, stdout=f, stderr=subprocess.STDOUT)
    assert result.returncode == 0, (script, result.returncode)
    assert shutil.disk_usage('/workspace').free >= 3 * 1024**3
print(json.dumps({'shard': n, 'normal_prepare_and_before_proofs_complete': True,
                  'free_bytes': shutil.disk_usage('/workspace').free}), flush=True)
