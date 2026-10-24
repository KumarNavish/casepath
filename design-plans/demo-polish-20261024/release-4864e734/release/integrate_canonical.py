"""Fast-forward the authorized integration branch to the verified sealed source."""
if not __debug__:
    raise RuntimeError('Canonical integration requires Python assertions enabled.')
from pathlib import Path
import datetime, hashlib, json, os, re, subprocess, sys
sys.dont_write_bytecode = True
assert len(sys.argv) == 2
base=Path(sys.argv[1]).resolve()
ROOT=Path('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024')
NS=ROOT/'.runtime/commander-demo-polish'
assert base == NS/'release' and Path(__file__).resolve().parent == base
binding=json.loads((NS/'source-binding.json').read_text())
candidate=binding['source_commit']
assert re.fullmatch(r'[0-9a-f]{40}',candidate)
previous='f75af1ac22a7260487556fc9231f4e290489c2e0'
assert binding['base_commit']==previous
branch='codex/casepath-causal-experience-integration-20261009'
parent=Path('/Users/kumar0002/Documents/Die Mobiliar/.work')
integration=parent/'casepath-sites-hosting-20261009'
sealed=ROOT
from require_completed_gate import require_completed_gate
require_completed_gate(base, candidate)
proof_path=base/'full-gate-verified.json'
proof=json.loads(proof_path.read_text())
assert proof['canonical_commit']==candidate and proof['exit_code']==0
assert all(proof[key]==0 for key in ['new_skips','deselected','failed','errors'])
def git(cwd,*args):
    return subprocess.check_output(['/usr/bin/git',*args],cwd=cwd,text=True,timeout=60).strip()
for path in [sealed]:
    assert git(path,'rev-parse','HEAD')==candidate
    assert not git(path,'status','--porcelain')
assert git(integration,'branch','--show-current')==branch
assert git(integration,'rev-parse','HEAD')==previous
assert not git(integration,'status','--porcelain')
remote=git(integration,'remote','get-url','origin')
assert remote in ['https://github.com/KumarNavish/casepath.git','git@github.com:KumarNavish/casepath.git'], 'Unexpected canonical remote'
reference='refs/heads/'+branch
assert git(integration,'ls-remote','origin',reference)==previous+'\t'+reference
receipt=base/'canonical-integration.json'
assert not receipt.exists(), 'Reconcile the original integration before repeating it'
record={'canonical_commit':candidate,'previous_commit':previous,'branch':branch,'remote':remote,
        'gate_proof_sha256':hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'authorized'}
def persist(value,first=False):
    if first:
        with receipt.open('x') as output:
            json.dump(value,output,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
    else:
        temporary=receipt.with_suffix('.next')
        with temporary.open('w') as output:
            json.dump(value,output,indent=2);output.write('\n');output.flush();os.fsync(output.fileno())
        os.replace(temporary,receipt)
persist(record,True)
subprocess.run(['/usr/bin/git','fetch','--no-tags',str(sealed),candidate],cwd=integration,check=True,timeout=120)
assert git(integration,'rev-parse','FETCH_HEAD')==candidate
subprocess.run(['/usr/bin/git','merge-base','--is-ancestor',previous,candidate],cwd=integration,check=True)
record['object_import_source']=str(sealed)
record['status']='candidate_object_imported';persist(record)
subprocess.run(['/usr/bin/git','merge','--ff-only',candidate],cwd=integration,check=True)
assert git(integration,'rev-parse','HEAD')==candidate and not git(integration,'status','--porcelain')
record['status']='local_fast_forward_complete';persist(record)
require_completed_gate(base,candidate)
assert git(integration,'ls-remote','origin',reference)==previous+'\t'+reference
record['status']='push_requested';persist(record)
subprocess.run(['/usr/bin/git','-c','http.postBuffer=268435456','-c','http.version=HTTP/1.1','push','origin','HEAD:'+reference],cwd=integration,check=True,timeout=120)
assert git(integration,'ls-remote','origin',reference)==candidate+'\t'+reference
assert git(integration,'rev-parse','HEAD')==candidate and not git(integration,'status','--porcelain')
record.update(status='pushed_and_verified',finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
persist(record)
print(json.dumps(record),flush=True)

