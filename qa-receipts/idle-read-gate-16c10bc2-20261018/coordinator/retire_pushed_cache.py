import hashlib, json, shutil, subprocess, sys, time
from pathlib import Path

R = Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018')
G = Path('/workspace/casepath-transport-gate-evidence-git-20261015')
B = 'qa-receipts/idle-read-gate-16c10bc2-20261018'
n = sys.argv[1]
assert n in [str(i) for i in range(1, 7)]
out = R / ('shard' + n)
assert not (out / 'ATTEMPT_STARTED.json').exists()
assert json.loads((out / 'prepare.json').read_text())['exit_code'] == 0
assert json.loads((out / 'runtime-before.json').read_text())['observed_before_test_start']
remote = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/' + B], cwd=G, text=True).split()[0]
bindings = {}
for name in ['prepare.json', 'source-before/capsule-verification.json', 'runtime-before.json']:
    rel = f'shard{n}/{name}'
    local = hashlib.sha256((R / rel).read_bytes()).hexdigest()
    pushed = hashlib.sha256(subprocess.check_output(['git', 'show', remote + ':' + B + '/' + rel], cwd=G)).hexdigest()
    assert local == pushed
    bindings[rel] = local
cache = out / 'uv-cache'
assert cache.is_dir() and not cache.is_symlink()
record = {'shard': n, 'path': str(cache), 'normal_prepare_exit_code': 0,
          'only_owned_reproducible_pinned_cache': True,
          'pushed_source_prepare_runtime_receipts_commit': remote,
          'pushed_receipt_byte_bindings': bindings,
          'before_free_bytes': shutil.disk_usage('/workspace').free, 'epoch': time.time()}
shutil.rmtree(cache)
record['after_free_bytes'] = shutil.disk_usage('/workspace').free
(out / 'prepare-cache-retirement.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
