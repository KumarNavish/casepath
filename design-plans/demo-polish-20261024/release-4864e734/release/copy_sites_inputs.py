"""Copy the canonical public Sites inputs into the distribution checkout and rebind provenance.

The input list is derived from build_static_site.py at the release commit (root files and
public assets) plus the build tools and .openai/hosting.json, so new public assets are included.
Usage: copy_sites_inputs.py <release-commit> <receipt-dir>. Performs no Git operations in the distribution.
"""
if not __debug__:
    raise RuntimeError('Release helpers require Python assertions enabled.')
from pathlib import Path
from hashlib import sha256
import json, re, subprocess, sys

SHA, BASE = sys.argv[1], Path(sys.argv[2]).resolve()
ROOT = Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024')
DIST = Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-sites-distribution-20261009')
from require_completed_gate import require_completed_gate
require_completed_gate(BASE, SHA)
assert json.loads((BASE.parent / 'source-binding.json').read_text())['source_commit'] == SHA
proof = json.loads((BASE / 'full-gate-verified.json').read_text())
assert proof['canonical_commit'] == SHA and proof['new_skips'] == 0 and proof['deselected'] == 0 and proof['failed'] == 0 and proof['errors'] == 0 and proof['exit_code'] == 0
assert subprocess.check_output(['/usr/bin/git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SHA
assert not subprocess.check_output(['/usr/bin/git', 'status', '--porcelain'], cwd=ROOT, text=True)
assert not subprocess.check_output(['/usr/bin/git', 'status', '--porcelain'], cwd=DIST, text=True), 'distribution has uncommitted changes'
sys.path.insert(0, str(ROOT / 'casepath/tools'))
import build_static_site as site
names = sorted({'casepath/' + p for p in (*site.PUBLIC_ROOT_FILES, *site.PUBLIC_ASSETS)} | {
    '.openai/hosting.json', 'casepath/tools/build_deployment_identity.py', 'casepath/tools/build_sites_site.py',
    'casepath/tools/build_static_site.py', 'casepath/tools/sites_worker.mjs'})
p = DIST / 'casepath-source-provenance.json'
old = json.loads(p.read_text())
assert old['canonical_commit'] == 'b20685d1670b33b941b1bfcb902638a879c01b93'
assert set(old['source_files']) <= set(names), sorted(set(old['source_files']) - set(names))
records = {}
for name in names:
    assert '..' not in Path(name).parts and name.startswith(('casepath/', '.openai/'))
    raw = (ROOT / name).read_bytes()
    target = DIST / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    assert target.read_bytes() == raw
    records[name] = {'sha256': sha256(raw).hexdigest(), 'size_bytes': len(raw)}
old.update(canonical_commit=SHA, source_files=records,
           canonical_tree=subprocess.check_output(['/usr/bin/git', 'rev-parse', 'HEAD^{tree}'], cwd=ROOT, text=True).strip())
old['build_environment']['CASEPATH_SOURCE_COMMIT'] = SHA
p.write_text(json.dumps(old, indent=2, sort_keys=True) + '\n')
readme = DIST / 'README.md'
readme.write_text(readme.read_text().replace('b20685d1670b33b941b1bfcb902638a879c01b93', SHA))
assert not any('hosted-read-seed' in str(x) for x in DIST.rglob('*') if '.git' not in x.parts)
changed = subprocess.check_output(['/usr/bin/git', 'status', '--porcelain'], cwd=DIST, text=True).splitlines()
added = sorted(set(names) - set(json.loads(subprocess.check_output(
    ['/usr/bin/git', 'show', 'HEAD:casepath-source-provenance.json'], cwd=DIST, text=True))['source_files']))
(BASE / 'sites-inputs-verified.json').write_text(json.dumps({'canonical_commit': SHA, 'source_files': len(records),
    'added_inputs': added, 'all_canonical_inputs_exact': True, 'private_seed_excluded': True,
    'changed_paths': changed}, indent=2) + '\n')
print(f'{len(records)} canonical public inputs copied and verified ({len(added)} new); {len(changed)} distribution paths changed; no Git commands run.')

