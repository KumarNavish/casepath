"""Preserve the exact browser artifacts produced inside the completed fresh gate.

This does not run the browser again. Its receipt identifies the mandatory gate
suite as the execution origin and keeps every copied artifact byte-identical.
"""
if not __debug__:raise RuntimeError("Assertions required")
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,shutil,subprocess
NS=Path(__file__).resolve().parent;ROOT=NS.parents[1];BASE=NS/'release'
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
binding=read(NS/'source-binding.json');SHA=binding['source_commit']
from require_completed_gate import require_completed_gate
require_completed_gate(BASE,SHA)
gate=read(NS/'full-gate-command.json')
assert gate['source_commit']==SHA and gate['status']=='passed' and gate['exit_code']==0
source=NS/'gate-browser';dest=NS/'sealed-browser'
assert gate['environment']['CASEPATH_REVIEW_EVIDENCE_DIR']==str(source)
proof=read(BASE/'full-gate-verified.json')
assert 'review-northstar-browser-v1.test.cjs' in proof['frontend_suites_required']
assert not dest.exists() and not (NS/'sealed-browser-command.json').exists()
browser=read(source/'receipt.json')
assert browser['status']=='passed' and not browser['browser_errors'] and not browser['unexpected_destinations']
assert browser['mobile']=={'pageOverflow':0,'panelOverflow':0,'reduced':True,'animations':0}
artifacts=['receipt.json','source-review.png','later-case-preview.png','later-case-reuse.png','mobile-review.png','review-walkthrough.webm','server.log']
before={name:digest(source/name) for name in artifacts}
dest.mkdir()
for name in artifacts:
 with (dest/name).open('xb') as output:output.write((source/name).read_bytes())
 assert digest(dest/name)==before[name],name
assert subprocess.check_output(['/usr/bin/git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SHA
assert not subprocess.check_output(['/usr/bin/git','status','--porcelain'],cwd=ROOT,text=True).strip()
record={'source_commit':SHA,'source_tree':binding['source_tree'],'source_manifest_sha256':binding['source_manifest_sha256'],
 'status':'passed','exit_code':gate['exit_code'],'execution_origin':'Mandatory review browser suite within the completed fresh full release gate; no second browser execution',
 'command':gate['command'],'gate_session_id':gate['commander_session_id'],'gate_command_sha256':digest(NS/'full-gate-command.json'),
 'gate_proof_sha256':digest(BASE/'full-gate-verified.json'),'gate_actual_completion_sha256':digest(BASE/'gate-actual-completion.json'),
 'original_artifact_directory':str(source),'out':str(dest),'artifact_hashes':before,'copied_byte_identically':True,'source_clean_after':True,
 'authority':'Isolated deterministic engineering QA; Test handler is not qualified human approval',
 'recorded_at':datetime.now(timezone.utc).isoformat(),'runner_sha256':digest(__file__)}
with (NS/'sealed-browser-command.json').open('x') as output:json.dump(record,output,indent=2);output.write('\n')
print(json.dumps(record),flush=True)

