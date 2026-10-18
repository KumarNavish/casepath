import hashlib, json, subprocess, sys
from pathlib import Path

R = Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018')
G = Path('/workspace/casepath-transport-gate-evidence-git-20261015')
B = 'qa-receipts/mobile-context-gate-a89b97bb-20261018'
def git(*args, raw=None):
    return subprocess.check_output(['git', *args], cwd=G, input=raw)
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
remote = git('ls-remote', 'origin', 'refs/heads/' + B).decode().split()[0]
assert remote == git('rev-parse', 'refs/heads/' + B).decode().strip()
if len(sys.argv) > 1:
    assert remote == sys.argv[1]
manifest = (R / 'SHA256SUMS').read_bytes()
assert git('show', remote + ':' + B + '/SHA256SUMS') == manifest
entries = [line.split('  ', 1) for line in manifest.decode().splitlines()]
tree = {}
for row in git('ls-tree', '-r', '-z', remote, '--', B).split(b'\0'):
    if not row:
        continue
    header, path = row.split(b'\t', 1)
    mode, kind, oid = header.split()
    assert kind == b'blob'
    tree[path.decode()] = oid
objects = []
for expected, rel in entries:
    assert sha((R / rel).read_bytes()) == expected, ('local', rel)
    objects.append((tree[B + '/' + rel], expected, rel))
batch = git('cat-file', '--batch', raw=b''.join(oid + b'\n' for oid, _, _ in objects))
pos = 0
for oid, expected, rel in objects:
    end = batch.index(b'\n', pos)
    actual_oid, kind, size = batch[pos:end].split()
    assert actual_oid == oid and kind == b'blob'
    pos = end + 1
    length = int(size)
    assert sha(batch[pos:pos + length]) == expected, ('pushed', rel)
    pos += length
    assert batch[pos:pos + 1] == b'\n'
    pos += 1
assert pos == len(batch)
exports = [json.loads(p.read_text()) for p in (R / 'coordinator').glob('export-*.json')]
first = min(exports, key=lambda x: x['epoch'])['transport_checkout_before']
head = git('rev-parse', 'HEAD').decode().strip()
index = sha((G / '.git/index').read_bytes()) if (G / '.git/index').exists() else None
assert head == first['head'] and index == first['index_sha256']
print(json.dumps({'commit': remote, 'branch': B, 'checksum_files_verified_local_and_pushed': len(entries),
                  'all_bytes_match': True, 'manifest_sha256': sha(manifest),
                  'archive_sha256': sha((R / 'raw-evidence.tar.gz').read_bytes()),
                  'transport_real_HEAD_index_preserved': True, 'real_HEAD': head,
                  'real_index_sha256': index}), flush=True)
