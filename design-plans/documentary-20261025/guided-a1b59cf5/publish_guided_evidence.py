#!/usr/bin/env python3
"""Commit and publish only the completed, reviewed film evidence prefix."""
from pathlib import Path
import subprocess,json,hashlib
W=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-guided-film-evidence-20261025");C=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-sites-hosting-20261009");G=Path("/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-documentary-20261024/.runtime/guided-film-20261025")
BASE="8e0509f84b1ef21262230243f9aa9ebaeb675d25"
PREFIX="design-plans/documentary-20261025/guided-a1b59cf5"
REMOTE_BRANCH="codex/casepath-causal-experience-integration-20261009"
def run(args,cwd=W):return subprocess.run(args,cwd=cwd,capture_output=True,text=True,check=True).stdout.strip()
assert run(["git","rev-parse","HEAD"])==BASE
assert run(["git","branch","--show-current"])=="codex/casepath-guided-film-20261025"
q=json.loads((W/PREFIX/"film-qa.json").read_text());assert q["status"]=="passed"
assert q["visual_review"]["encoded_temporal_review_status"]=="passed"
m=json.loads((W/PREFIX/"CasePath_Guided_Documentary_Music.media.json").read_text());assert m["passed"]
manifest=json.loads((W/PREFIX/"package-manifest.json").read_text())
for f in manifest["files"]:
 p=W/PREFIX/f["path"];assert p.stat().st_size==f["bytes"];assert hashlib.sha256(p.read_bytes()).hexdigest()==f["sha256"]
remote=run(["git","ls-remote","origin","refs/heads/"+REMOTE_BRANCH]).split()[0];assert remote==BASE
status=run(["git","status","--porcelain"])
assert all(line[3:].startswith(PREFIX+"/") for line in status.splitlines()),status
run(["git","add","-f","--",PREFIX])
names=run(["git","diff","--cached","--name-only"]).splitlines()
assert names and all(n.startswith(PREFIX+"/") for n in names)
expected={PREFIX+"/"+f["path"] for f in manifest["files"]}|{PREFIX+"/package-manifest.json"}
assert set(names)==expected,{"missing":sorted(expected-set(names)),"unexpected":sorted(set(names)-expected)}
run(["git","diff","--cached","--check"])
message="Add standalone guided CasePath documentary and verified film evidence"
commit_output=run(["git","commit","-m",message])
head=run(["git","rev-parse","HEAD"])
changed=run(["git","diff","--name-only",BASE,head]).splitlines();assert all(n.startswith(PREFIX+"/") for n in changed)
print(json.dumps({"stage":"committed","head":head,"files":len(changed),"message":message}),flush=True)
push=subprocess.run(["git","push","origin","HEAD:refs/heads/"+REMOTE_BRANCH],cwd=W,capture_output=True,text=True)
if push.returncode:raise RuntimeError("Ordinary push failed: "+push.stderr)
assert run(["git","ls-remote","origin","refs/heads/"+REMOTE_BRANCH]).split()[0]==head
assert run(["git","rev-parse","HEAD"],C)==BASE
assert run(["git","status","--porcelain"],C)==""
run(["git","merge","--ff-only",head],C)
assert run(["git","rev-parse","HEAD"],C)==head
assert run(["git","status","--porcelain"],C)==""
report={"status":"passed","head":head,"base":BASE,"branch":REMOTE_BRANCH,"files":len(changed),"only_prefix":PREFIX,"canonical_clean":True,"remote_verified":True,"product_source_unchanged":"a1b59cf5d78662b35790a11cfd2d46851310482d","commit_output":commit_output,"push_stdout":push.stdout,"push_stderr":push.stderr}
(G/"publication-receipt.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report),flush=True)
