import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

R = Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018')
G = Path('/workspace/casepath-transport-gate-evidence-git-20261015')
SHA = 'a89b97bb8eecdd8e98771c99ca879d4e253f7881'
MAN = '416eea6c4831046fca1bab76ec7072bc116cdc2912a169b094341d3a2ee68b0a'
BRANCH = 'qa-receipts/mobile-context-gate-a89b97bb-20261018'
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
paths = [repo / '.runtime/casepath-dev-v2/source-capsules' / MAN,
         repo / '.runtime/casepath-dev-v2/venv', out / 'uv-cache']
record = {'candidate': SHA, 'shard': n, 'pushed_receipts_commit': remote,
          'pushed_receipt_file_bindings': bindings,
          'source_capsule_before_after_equal': True,
          'full_venv_before_after_equal': True,
          'runtime_observed_before_first_test_start': True,
          'raw_archive_byte_verified': True, 'archive_sha256': archive['archive_sha256'],
          'only_this_gate_reproducible_runtime_paths': list(map(str, paths)),
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
