"""Bind previously acquired bytes to this release only after native validation."""
if not __debug__:
    raise RuntimeError('Release helpers require Python assertions enabled.')
import sys
from pathlib import Path
import hashlib, json, os, re, secrets, subprocess, tempfile, time
sys.dont_write_bytecode = True
assert len(sys.argv)==3 and len(sys.argv[1])==40, 'usage: renew_seed.py <release-commit> <receipt-dir>'

BASE = Path(sys.argv[2]).resolve()
ROOT = Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024')
NS=ROOT/'.runtime/documentary-release-20261025'
assert BASE == NS/'release' and Path(__file__).resolve().parent == BASE
binding=json.loads((NS/'source-binding.json').read_text())
COMMIT=binding['source_commit']
assert re.fullmatch(r'[0-9a-f]{40}',COMMIT) and sys.argv[1]==COMMIT
assert binding['base_commit']=='5da3233a0aa04ad29843c8ec55dfb685118381c9'
from require_completed_gate import require_completed_gate
require_completed_gate(BASE,COMMIT)
gate = json.loads((BASE / 'full-gate-verified.json').read_text())
assert gate['canonical_commit'] == COMMIT and gate['new_skips'] == 0 and gate['deselected'] == 0 and gate['failed'] == 0 and gate['errors'] == 0 and gate['exit_code'] == 0
OLD = '5da3233a0aa04ad29843c8ec55dfb685118381c9'
EXPECTED = '061746e5806fd801796cfcbc8137189696e5415d465671c9e3b945fe2070af3c'
EXPECTED_BYTES = 13330327
PRIVATE = Path('/Users/kumar0002/Library/Application Support/CasePath')
source = PRIVATE / 'private-release-5da3233a0aa0/hosted-read-seed-v1.json'
output = PRIVATE / ('private-release-' + COMMIT[:12]) / 'hosted-read-seed-v1.json'
receipt_path=BASE/'seed-renewal-receipt.json'
attempt_path=BASE/'seed-renewal-attempt.json'
assert not output.exists() and not receipt_path.exists() and not attempt_path.exists(), 'Reconcile the original seed attempt before any retry'
assert source.stat().st_size==EXPECTED_BYTES
attempt={'source_commit':COMMIT,'input_commit':OLD,'input_sha256':EXPECTED,'input_bytes':EXPECTED_BYTES,
         'status':'native_validation_requested','started_at_unix':time.time(),'read_only':True,'retries':0}
with attempt_path.open('x') as f:
    json.dump(attempt,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
output.parent.mkdir(mode=0o700, exist_ok=True)
assert sys.platform == 'darwin'
assert subprocess.check_output(['/usr/bin/git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == COMMIT
assert not subprocess.check_output(['/usr/bin/git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
sys.path.insert(0, str(ROOT / 'casepath-api/tools'))
import export_read_seed as export
from casepath_api.hosted_read_seed_v1 import load_seed, pack_seed, decode_seed

export._output_path(output)
candidate = load_seed(source, deployment_commit=OLD, expected_sha256=EXPECTED)
assert candidate is not None
assert hashlib.sha256(pack_seed(OLD, candidate['journal_rows'], candidate['sources'])).hexdigest() == EXPECTED
raw = pack_seed(COMMIT, candidate['journal_rows'], candidate['sources'])
renewed = decode_seed(raw, deployment_commit=COMMIT)
assert {k: v for k, v in renewed.items() if k != 'deployment_commit'} == {
    k: v for k, v in candidate.items() if k != 'deployment_commit'}
secret = subprocess.check_output(['/usr/bin/security', 'find-generic-password', '-a', 'kumarnavish',
                                 '-s', 'CasePath Turso database', '-w'], text=True,
                                stderr=subprocess.DEVNULL).strip()
db = export.TursoDatabase('libsql://casepath-autonomous-kumarnavish.aws-eu-west-1.turso.io', secret,
                          client_factory=export._BoundedClient, reuse_http=True)
del secret
started = time.time()
try:
    with tempfile.TemporaryDirectory(prefix='casepath-release-seed-proof-') as folder:
        store = export._pristine(db.connect, Path(folder))
        if not store.admit_read_seed(renewed, deployment_commit=COMMIT):
            raise RuntimeError('The current database differs from the previously acquired bytes.')
    db._shared_client._consume(0)
    assert db._shared_client.requests == 1
    require_completed_gate(BASE,COMMIT)
    export._output_path(output)
    directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = '.hosted-read-seed-' + secrets.token_hex(16)
    created = False
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        created = True
        with os.fdopen(fd, 'wb') as target:
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        export._output_path(output)
        current, opened = output.parent.stat(), os.fstat(directory)
        assert (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino)
        os.link(temporary, output.name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        os.fsync(directory)
    finally:
        if created:
            os.unlink(temporary, dir_fd=directory)
        os.close(directory)
    receipt = {'deployment_commit': COMMIT, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
        'journal_rows': len(renewed['journal_rows']), 'sources': len(renewed['sources']),
        'input_commit': OLD, 'input_sha256': EXPECTED, 'input_bytes': EXPECTED_BYTES, 'raw_records_and_sources_unchanged': True,
        'native_replay_and_full_fresh_atomic_proof': True, 'read_only': True, 'requests': db._shared_client.requests,
        'wire_bytes': db._shared_client.wire_bytes, 'seconds': time.time() - started,
        'artifact_path': str(output), 'mode': oct(output.stat().st_mode & 0o777), 'retries': 0}
    with receipt_path.open('x') as f:
        json.dump(receipt,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    attempt.update(status='passed',finished_at_unix=time.time(),receipt_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest())
    attempt_path.write_text(json.dumps(attempt,indent=2)+'\n')
    print(json.dumps(receipt), flush=True)
except BaseException as error:
    attempt.update(status='failed',finished_at_unix=time.time(),error_type=type(error).__name__)
    attempt_path.write_text(json.dumps(attempt,indent=2)+'\n')
    raise
finally:
    db.close()

