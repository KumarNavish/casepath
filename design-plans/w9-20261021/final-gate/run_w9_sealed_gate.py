from pathlib import Path
import subprocess, os, datetime, json, hashlib
owner=Path.cwd()
root=owner.parent/'casepath-w9-sealed-gate-20261022-r1'
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert sha==(owner/'.runtime/w9-final-frozen-sha').read_text().strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
env={'HOME':str(Path.home()),'USER':os.environ.get('USER','kumar0002'),'PATH':'/Users/kumar0002/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','CASEPATH_REQUIRE_FRONTEND_SUITES':'1','CASEPATH_NODE':'/usr/local/bin/node','CASEPATH_UV':'/Users/kumar0002/.local/bin/uv','NODE_PATH':str(owner/'casepath-qa/node_modules'),'PLAYWRIGHT_EXECUTABLE_PATH':'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'}
for operation,name in [('prepare','w9-sealed-final-prepare'),('test','w9-sealed-final-gate')]:
 path=owner/'.runtime'/name
 log=path.with_suffix('.log');receipt=path.with_suffix('.json')
 assert not log.exists() and not receipt.exists(),str(path)
 data={'review_commit':sha,'wrapper_pid':os.getpid(),'validation_checkout':str(root),'command':['./bin/casepath',operation],'environment':{k:v for k,v in env.items() if k.startswith('CASEPATH_') or k in ['NODE_PATH','PLAYWRIGHT_EXECUTABLE_PATH']},'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'running'}
 with log.open('w') as out:
  proc=subprocess.Popen(['./bin/casepath',operation],cwd=root,env=env,stdout=out,stderr=subprocess.STDOUT)
  data['pid']=proc.pid;receipt.write_text(json.dumps(data,indent=2)+'\n')
  print(json.dumps(data),flush=True)
  code=proc.wait()
 data.update(status='completed',exit_code=code,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
 receipt.write_text(json.dumps(data,indent=2)+'\n')
 print(json.dumps(data),flush=True)
 print('\n'.join(log.read_text().splitlines()[-16:]),flush=True)
 if code: raise SystemExit(code)
