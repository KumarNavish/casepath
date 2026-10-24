"""Capture the remaining evidence artifacts only after actual published acceptance."""
if not __debug__:raise RuntimeError("Assertions required")
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,signal,subprocess,sys
NS=Path(__file__).resolve().parent;ROOT=NS.parents[1];BASE=NS/"release"
SHA="b20685d1670b33b941b1bfcb902638a879c01b93";PY=str(ROOT/".runtime/casepath-dev-v2/venv/bin/python")
read=lambda p:json.loads(p.read_text())
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
sys.path.insert(0,str(BASE))
from require_completed_gate import require_completed_gate
require_completed_gate(BASE,SHA)
acceptance=read(BASE/"published-acceptance-sequence.json")
assert acceptance["source_commit"]==SHA and acceptance["status"]=="passed"
terminal=read(BASE/"commander-acceptance-terminal.json");actual=terminal.get("result",terminal)
assert actual["state"]=="completed" and actual["exitCode"]==0 and actual["sessionId"]=="cp-ns-20261024-published-acceptance"
binding=read(NS/"evidence-helpers-prepared.json")
assert binding["source_commit"]==SHA and binding["status"]=="prepared"
assert digest(Path(__file__))==binding["artifact_runner_sha256"]
for name,expected in binding["artifact_helpers"].items():assert digest(BASE/name)==expected,name
git=lambda *args:subprocess.check_output(["/usr/bin/git",*args],cwd=ROOT,text=True).strip()
assert git("rev-parse","HEAD")==SHA and not git("status","--porcelain")
receipt=BASE/"northstar-artifacts-sequence.json"
state={"source_commit":SHA,"status":"running","started_at":now(),"script_sha256":digest(Path(__file__)),"helper_binding_sha256":digest(NS/"evidence-helpers-prepared.json"),"stages":[],"source_clean_before":True}
with receipt.open("x") as f:json.dump(state,f,indent=2);f.write("\n")
def persist():
 temporary=receipt.with_suffix(".next");temporary.write_text(json.dumps(state,indent=2)+"\n");os.replace(temporary,receipt)
active=None
def cleanup():
 global active
 if active is None or active.poll() is not None:active=None;return
 try:os.killpg(active.pid,signal.SIGTERM)
 except ProcessLookupError:pass
 try:active.wait(timeout=10)
 except subprocess.TimeoutExpired:
  try:os.killpg(active.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  active.wait(timeout=10)
 active=None
def interrupted(signum,frame):raise SystemExit(128+signum)
signal.signal(signal.SIGTERM,interrupted)
stages=[
 ("film_frames",[PY,str(BASE/"decode_public_film.py")],900,BASE/"public-film-review/frames-index.json"),
 ("contact_sheet",["/usr/local/bin/node",str(BASE/"make_film_contact_sheet.mjs")],120,BASE/"public-film-review/contact-sheet.json"),
 ("eight_states",["/usr/local/bin/node",str(BASE/"capture_eight_states.mjs")],300,BASE/"eight-state-capture/eight-state-evidence.json"),
 ("fidelity",[PY,str(BASE/"measure_northstar_fidelity.py")],400,BASE/"northstar-fidelity/fidelity-measurements.json")]
try:
 for name,command,timeout,artifact in stages:
  log=BASE/("northstar-"+name+"-command.log")
  row={"name":name,"status":"running","command":command,"started_at":now(),"log":str(log)}
  state["stages"].append(row);persist();print(json.dumps({"stage":name,"status":"running"}),flush=True)
  with log.open("x") as output:
   active=subprocess.Popen(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
   row["pid"]=active.pid;persist()
   try:code=active.wait(timeout=timeout)
   except subprocess.TimeoutExpired:cleanup();raise RuntimeError("Owned artifact capture timed out: "+name)
  row.update(status="completed" if code==0 else "failed",exit_code=code,finished_at=now(),log_sha256=digest(log));persist()
  assert code==0,"Preserve failed artifact evidence: "+name
  row["artifact"]={"path":str(artifact),"sha256":digest(artifact)};persist()
  print(json.dumps({"stage":name,"exit_code":code}),flush=True)
 assert git("rev-parse","HEAD")==SHA and not git("status","--porcelain")
 state.update(status="passed",finished_at=now(),source_clean_after=True);persist()
 print(json.dumps({"status":"passed","source_commit":SHA,"eight_states":8,"cold_review_frames":24,"concept_comparisons":3,"cold_viewer_and_visual_review":"pending actual inspection"}),flush=True)
except BaseException as error:
 state.update(status="failed",failure=repr(error),finished_at=now());persist();raise
finally:cleanup()
