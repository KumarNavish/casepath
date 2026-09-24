"""Verify every released file against manifest.json."""
import hashlib, json, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'manifest.json').read_text())
for row in manifest['files']:
    raw = (root / row['relative_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row['file_sha256']
print(f"verified {len(manifest['files'])} files")
