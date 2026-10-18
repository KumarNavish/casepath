import hashlib,json,os,stat,time
from pathlib import Path
def capture_runtime(repo,out,phase):
 target=out/('runtime-'+phase+'.json');root=repo/'.runtime/casepath-dev-v2/venv';rows=[]
 for p in sorted(root.rglob('*')):
  rel=p.relative_to(root).as_posix()
  if p.is_symlink():
   dest=p.resolve(strict=True);rows.append({'path':rel,'symlink':os.readlink(p),'resolved_path':str(dest),'resolved_file_sha256':hashlib.sha256(dest.read_bytes()).hexdigest() if dest.is_file() else None})
  elif p.is_file():rows.append({'path':rel,'size_bytes':p.stat().st_size,'mode':stat.S_IMODE(p.stat().st_mode),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 canon=json.dumps(rows,sort_keys=True,separators=(',',':')).encode();latch=out/'ATTEMPT_STARTED.json';observed=time.time();attempt=json.loads(latch.read_text()) if latch.exists() else None
 value={'phase':phase,'candidate':json.loads((out/'prepare.json').read_text())['candidate'],'root':str(root),'file_and_symlink_count':len(rows),'inventory_sha256':hashlib.sha256(canon).hexdigest(),'rows':rows,'observed_epoch':observed,'original_test_attempt_started_epoch':attempt['started_epoch'] if attempt else None,'observed_before_test_start':not bool(attempt),'qualification':'For shards1/2 initial full-venv inventory was added during original attempt; their pretest source/capsule/artifact proofs remain separately recorded. No unobserved earlier full-venv byte-equality claimed.' if phase=='before' and attempt else 'Exact full pinned-venv regular files and symlink targets; source/capsule/artifact/static verification is separate.'}
 if phase=='after':
  before=json.loads((out/'runtime-before.json').read_text())
  value.update(before_after_inventory_equal=before['rows']==rows and before['inventory_sha256']==value['inventory_sha256'],before_observed_epoch=before['observed_epoch'],before_observed_before_test_start=before['observed_before_test_start'],supplementary_only=True)
 with target.open('x') as f:json.dump(value,f,indent=2);f.write('\n')
 return value
