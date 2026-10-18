import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

R = Path('/workspace/casepath-idle-read-gate-16c10bc2-20261018')
G = Path('/workspace/casepath-transport-gate-evidence-git-20261015')
SHA = '16c10bc21c1b2b3b6602cb028028adf28e20823b'
MAN = 'e7fbfd43062c19ed04468966aee9a2c61dcb1064b8baaa449cd4a2fe841e0442'
BRANCH = 'qa-receipts/idle-read-gate-16c10bc2-20261018'
n = sys.argv[1]
assert n in [str(i) for i in range(1, 7)]
out = R / ('shard' + n)
repo = Path(json.loads((R / 'clone-map.json').read_text())['repos'][n])

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def git(*args, cwd=G):
    return subprocess.check_output(['git', *args], cwd=cwd)

terminal = json.loads((out / 'worker-terminal.json').read_text())
assert terminal['results'][0]['exit_code'] == 0
result = json.loads((out / 'result.json').read_text())
before = json.loads((out / 'source-before/capsule-verification.json').read_text())
after = json.loads((out / 'source-after/capsule-verification.json').read_text())
runtime = json.loads((out / 'runtime-after.json').read_text())
archive = json.loads((R / f'retirement-receipts/shard{n}-raw-archive.json').read_text())
assert result['candidate'] == SHA and result['exit_code'] == 0
assert before['capsule_receipt'] == after['capsule_receipt']
assert before['capsule_receipt_file_sha256'] == after['capsule_receipt_file_sha256']
assert after['head'] == SHA and after['status'] == '' and after['manifest_sha256'] == MAN
assert runtime['before_after_inventory_equal'] and runtime['before_observed_before_test_start']
assert archive['raw_archive_byte_verified'] and digest(Path(archive['archive'])) == archive['archive_sha256']
assert git('rev-parse', 'HEAD', cwd=repo).decode().strip() == SHA
assert not git('status', '--porcelain', cwd=repo).strip()
assert digest(repo / 'casepath/source-manifest.json') == MAN
remote = git('ls-remote', 'origin', 'refs/heads/' + BRANCH).decode().split()[0]
assert remote == git('rev-parse', 'refs/heads/' + BRANCH).decode().strip()
bindings = {}
for rel in [f'shard{n}/prepare.json', f'shard{n}/command.json', f'shard{n}/result.json',
            f'shard{n}/reports.jsonl', f'shard{n}/junit.xml',
            f'shard{n}/source-before/capsule-verification.json',
            f'shard{n}/source-after/capsule-verification.json',
            f'shard{n}/runtime-before.json', f'shard{n}/runtime-after.json',
            f'retirement-receipts/shard{n}-raw.tar.gz']:
    local = digest(R / rel)
    pushed = hashlib.sha256(git('show', remote + ':' + BRANCH + '/' + rel)).hexdigest()
    assert local == pushed, rel
    bindings[rel] = local
public = repo / 'casepath-public'
assert public.is_dir() and not public.is_symlink()
assert subprocess.run(['git','check-ignore','-q','casepath-public'],cwd=repo).returncode == 0
static_rows=[]
for item in sorted(public.rglob('*')):
    assert not item.is_symlink()
    if item.is_file():
        raw=item.read_bytes()
        static_rows.append({'path':item.relative_to(public).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw),'executable':bool(item.stat().st_mode & 0o100)})
assert len(static_rows)==after['capsule_receipt']['static_file_count']==40
# Use the exact canonical encoder from the proven frozen capsule verifier.
import sys
sys.path.insert(0,str(R/'harness'))
from verify_prepared_capsules import canonical
assert hashlib.sha256(canonical(static_rows)).hexdigest()==after['capsule_receipt']['static_inventory_sha256']
paths = [repo / '.runtime/casepath-dev-v2/source-capsules' / MAN,
         repo / '.runtime/casepath-dev-v2/venv', out / 'uv-cache', public]
record = {'candidate': SHA, 'shard': n, 'pushed_receipts_commit': remote,
          'pushed_receipt_file_bindings': bindings,
          'source_capsule_before_after_equal': True,
          'full_venv_before_after_equal': True,
          'runtime_observed_before_first_test_start': True,
          'raw_archive_byte_verified': True, 'archive_sha256': archive['archive_sha256'],
          'only_this_gate_reproducible_runtime_paths': list(map(str, paths)),
          'completed_generated_static_inventory': static_rows,
          'completed_generated_static_matches_remotely_pushed_receipt': True,
          'current_generated_static_retirement_authorized_by_parent': True,
          'source_clones_fixture_databases_journals_and_failed_fixtures_preserved': True,
          'before_free_bytes': shutil.disk_usage('/workspace').free, 'epoch': time.time()}
for path in paths:
    if not path.exists():
        assert path == out / 'uv-cache'
        continue
    assert path.is_dir() and not path.is_symlink()
    for directory, dirs, files in os.walk(path):
        os.chmod(directory, 0o700)
    shutil.rmtree(path)
record['after_free_bytes'] = shutil.disk_usage('/workspace').free
(R / f'completed-shard{n}-runtime-retirement.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record), flush=True)
