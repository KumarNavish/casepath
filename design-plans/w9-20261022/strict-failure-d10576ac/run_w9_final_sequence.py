from pathlib import Path
import subprocess, os, json, datetime, hashlib
root=Path.cwd();now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
sha=(root/'.runtime/w9-final-frozen-sha').read_text().strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==sha
assert not subprocess.check_output(['git','diff','--name-only','HEAD'],text=True).strip()
receipt=root/'.runtime/w9-final-sequence.json';assert not receipt.exists()
for path in ['w9-sealed-final-prepare.json','w9-sealed-final-prepare.log','w9-sealed-final-gate.json','w9-sealed-final-gate.log','w9-final-head-proof']:
 assert not (root/'.runtime'/path).exists(),path
state={'sourceCommit':sha,'wrapperPid':os.getpid(),'startedAt':now(),'status':'running','serialized':True,'stages':[]}
def save(): receipt.write_text(json.dumps(state,indent=2)+'\n')
save()
try:
 for name,script in [('strict','run_w9_sealed_gate.py'),('walk','run_w9_final_walk.py')]:
  if name=='walk':
   g=json.loads((root/'.runtime/w9-sealed-final-gate.json').read_text())
   assert g['status']=='completed' and g['exit_code']==0 and g['review_commit']==sha
  log=root/'.runtime'/('w9-final-'+name+'-controller.log');assert not log.exists()
  row={'name':name,'command':[str(root/'.runtime/casepath-dev-v2/venv/bin/python'),str(root/'.runtime'/script)],'log':str(log),'status':'running','startedAt':now()}
  state['stages'].append(row)
  with log.open('w') as output:
   proc=subprocess.Popen(row['command'],cwd=root,stdout=output,stderr=subprocess.STDOUT)
   row['pid']=proc.pid;save();print(json.dumps(row),flush=True);code=proc.wait()
  row.update(status='completed',exitCode=code,finishedAt=now(),logSha256=hashlib.sha256(log.read_bytes()).hexdigest());save()
  assert code==0,name+' failed; inspect original receipt and log'
  print(json.dumps(row),flush=True)
 state['status']='passed'
except Exception as error:
 state.update(status='failed',failure=repr(error));raise
finally:
 state['finishedAt']=now();save();print(json.dumps(state),flush=True)
