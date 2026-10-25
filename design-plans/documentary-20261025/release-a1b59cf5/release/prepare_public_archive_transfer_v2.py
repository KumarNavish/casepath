"""Package the already built public Sites archive for a hash-checked tool transfer."""
from pathlib import Path
import base64, hashlib, json, tarfile

BASE = Path(__file__).resolve().parent
SOURCE = json.loads((BASE.parent / 'source-binding.json').read_text())['source_commit']
result = json.loads((BASE / 'sites-workflow-result.json').read_text())
archive = BASE / ('casepath-public-' + SOURCE[:8] + '.tar.gz')
assert result['archive'] == str(archive) and archive.is_file() and not archive.is_symlink()
assert result['project_id'] == 'appgprj_6ac8aab031988191b5c370f7a4dbf160'
with tarfile.open(archive, 'r:gz') as stream:
    members = stream.getmembers()
    names = [m.name.removeprefix('./') for m in members]
    assert 'dist/.openai/hosting.json' in names and 'dist/server/index.js' in names and 'dist/client/index.html' in names
    assert all(name == 'dist' or name.startswith('dist/') for name in names)
    assert len(names) == len(set(names))
    assert not any(m.issym() or m.islnk() or m.name.startswith('/') or '..' in Path(m.name).parts for m in members)
    assert not any(any(s in name.lower() for s in ('hosted-read-seed', 'private-release', '.env', 'credentials', 'casepath.db', 'work.sqlite3')) for name in names)
data = archive.read_bytes()
out = BASE / ('public-archive-transfer-' + SOURCE[:8])
out.mkdir()
rows = []
for i, offset in enumerate(range(0, len(data), 32768)):
    chunk = data[offset:offset + 32768]
    name = f'chunk-{i:04d}.b64'
    (out / name).write_text(base64.b64encode(chunk).decode('ascii') + '\n')
    rows.append({'file': name, 'bytes': len(chunk), 'sha256': hashlib.sha256(chunk).hexdigest()})
record = {'source_commit': SOURCE, 'project_id': result['project_id'], 'distribution_commit': result['commit_sha'],
          'archive': str(archive), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'chunks': rows}
(out / 'index.json').write_text(json.dumps(record, separators=(',', ':')) + '\n')
print(json.dumps({'source_commit': SOURCE, 'bytes': len(data), 'sha256': record['sha256'], 'chunks': len(rows), 'index': str(out / 'index.json')}))
