import hashlib,json,subprocess,time
from pathlib import Path
r=Path('/workspace/casepath-source-wrap-gate-cbfa10ad-20261015');rec=json.loads((r/'CANCELLATION.json').read_text());commands=[];proofs=[]
for name in ['inventory']+[f'shard{i}' for i in range(1,7)]:
 out=r/name;repo=Path('/workspace/casepath-release-ae0-'+name);proofpath=out/'source-after/capsule-verification.json'
 if not proofpath.exists():
  env=json.loads((out/'prepare.json').read_text())['env'];cmd=[str(repo/'.runtime/casepath-dev-v2/venv/bin/python'),'-P',str(r/'harness/verify_prepared_capsules.py'),name,'after'];started=time.time()
  with (out/'verify-after.log').open('x') as f:result=subprocess.run(cmd,cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT)
  commands.append({'name':name,'command':cmd,'cwd':str(repo),'env':env,'started_epoch':started,'finished_epoch':time.time(),'exit_code':result.returncode,'purpose':'Read-only source/capsule checks after explicit cancellation; no test rerun','raw_log':str(out/'verify-after.log'),'raw_proof':str(proofpath)})
  (r/'coordinator/cancellation-source-proof-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
  if result.returncode:print(json.dumps({'name':name,'source_after_exit_code':result.returncode}),flush=True);continue
 before=json.loads((out/'source-before/capsule-verification.json').read_text());after=json.loads(proofpath.read_text());same=before['capsule_receipt']==after['capsule_receipt'] and before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
 proofs.append({'name':name,'proof':str(proofpath),'proof_sha256':hashlib.sha256(proofpath.read_bytes()).hexdigest(),'head':after['head'],'status':after['status'],'manifest_sha256':after['manifest_sha256'],'sealed_files_verified':after['sealed_files_verified'],'source_artifact_static_bindings_verified':after['source_artifact_static_bindings_verified'],'capsule_receipt_unchanged':same})
 print(json.dumps(proofs[-1]),flush=True)
rec=json.loads((r/'CANCELLATION.json').read_text());rec['after_source_proofs']=proofs;rec['after_source_verification_complete_epoch']=time.time();rec['gate_status']='CANCELLED_BY_USER';rec['no_test_retries']=True;rec['all_seven_sources_and_capsules_unchanged']=len(proofs)==7 and all(x['capsule_receipt_unchanged'] and x['source_artifact_static_bindings_verified'] and x['status']=='' for x in proofs)
for n in range(1,7):
 out=r/f'shard{n}';phases=[];f=out/'reports.jsonl'
 if f.exists():
  for line in f.read_text().splitlines():
   try:phases.append(json.loads(line))
   except json.JSONDecodeError:pass
 row={'shard':n,'selected_ids':len(json.loads((out/'collected.json').read_text())) if (out/'collected.json').exists() else None,'phase_rows':len(phases),'call_reports':sum(x['when']=='call' for x in phases),'failed_reports':sum(x['outcome']=='failed' for x in phases),'skipped_reports':sum(x['outcome']=='skipped' for x in phases),'junit_present':(out/'junit.xml').exists(),'result_present':(out/'result.json').exists(),'interrupted':(out/'INTERRUPTED.json').exists()}
 rec.setdefault('raw_attempt_observations',[]).append(row)
(r/'CANCELLATION.json').write_text(json.dumps(rec,indent=2)+'\n')
assert rec['all_seven_sources_and_capsules_unchanged']
