"""Resume failed evidence capture after a diagnosed stale-fixture oracle, preserving the original run."""
if not __debug__:raise RuntimeError("Assertions required")
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,signal,subprocess,sys
NS=Path(__file__).resolve().parent;ROOT=NS.parents[1];BASE=NS/"release"
SHA="b20685d1670b33b941b1bfcb902638a879c01b93";PY=str(ROOT/".runtime/casepath-dev-v2/venv/bin/python")
read=lambda p:json.loads(p.read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
sys.path.insert(0,str(BASE))
from require_completed_gate import require_completed_gate
require_completed_gate(BASE,SHA)
assert read(BASE/"published-acceptance-sequence.json")["status"]=="passed"
original=read(BASE/"northstar-artifacts-sequence.json")
failed=read(BASE/"commander-artifacts-failed-terminal.json")["result"]
assert original["source_commit"]==SHA and original["status"]=="failed"
assert failed["sessionId"]=="cp-ns-20261024-northstar-artifacts" and failed["state"]=="failed" and failed["exitCode"]==1
assert [s["name"] for s in original["stages"]]==["film_frames","contact_sheet","eight_states"]
assert original["stages"][-1]["exit_code"]==1
assert digest(original["stages"][-1]["log"])==original["stages"][-1]["log_sha256"]
original_binding=read(NS/"evidence-helpers-prepared.json")
assert digest(NS/"run_northstar_artifacts.py")==original_binding["artifact_runner_sha256"]==original["script_sha256"]
for name,expected in original_binding["artifact_helpers"].items():assert digest(BASE/name)==expected,name
prior_capture=read(BASE/"eight-state-capture/eight-state-evidence.json")
assert prior_capture["status"]=="failed" and "actual operation matches the frozen recorded reference" in prior_capture["failure"]
assert [r["state"] for r in prior_capture["states"]]==[1,2,3,4]
for row in prior_capture["states"]:assert digest(BASE/"eight-state-capture"/row["file"])==row["sha256"]
for stage in original["stages"][:2]:
 assert stage["status"]=="completed" and stage["exit_code"]==0
 assert digest(stage["log"])==stage["log_sha256"]
 assert digest(stage["artifact"]["path"])==stage["artifact"]["sha256"]
forensics=read(BASE/"operation-trace-forensics/identity-review.json")
assert forensics["status"]=="passed" and forensics["source_commit"]==SHA
for row in forensics["claims"]:
 assert row["official_checkedOperation_all_passed"] and row["final_binding_verified"]
 for field in ("trace","state_file","difference"):
  filename=row["state_file"] if field=="state_file" else row[field+"_file"]
  expected=row["state_file_sha256"] if field=="state_file" else row[field+"_sha256"]
  assert digest(BASE/"operation-trace-forensics"/filename)==expected
binding=read(NS/"evidence-recovery-prepared.json")
assert binding["source_commit"]==SHA and binding["status"]=="prepared"
assert digest(__file__)==binding["artifact_runner_sha256"]
assert digest(BASE/"operation-trace-forensics/identity-review.json")==binding["trace_forensics_sha256"]
for name,expected in binding["artifact_helpers"].items():assert digest(BASE/name)==expected,name
git=lambda *args:subprocess.check_output(["/usr/bin/git",*args],cwd=ROOT,text=True).strip()
assert git("rev-parse","HEAD")==SHA and not git("status","--porcelain")
receipt=BASE/"northstar-artifacts-recovery-sequence.json"
state={"contract":"casepath.artifact-recovery/1","source_commit":SHA,"status":"running","started_at":now(),"script_sha256":digest(__file__),"helper_binding_sha256":digest(NS/"evidence-recovery-prepared.json"),"original_failed_sequence_sha256":digest(BASE/"northstar-artifacts-sequence.json"),"original_failed_terminal_sha256":digest(BASE/"commander-artifacts-failed-terminal.json"),"original_failed_capture_sha256":digest(BASE/"eight-state-capture/eight-state-evidence.json"),"trace_forensics_sha256":digest(BASE/"operation-trace-forensics/identity-review.json"),"carried_forward_stages":original["stages"][:2],"stages":[],"source_clean_before":True,"original_failure_preserved":True,"product_changes":False}
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
 ("eight_states",["/usr/local/bin/node",str(BASE/"capture_eight_states_recovered.mjs")],300,BASE/"eight-state-capture-recovered/eight-state-evidence.json"),
 ("fidelity",[PY,"-B",str(BASE/"measure_northstar_fidelity_recovered.py")],400,BASE/"northstar-fidelity/fidelity-measurements.json")]
try:
 for name,command,timeout,artifact in stages:
  log=BASE/("northstar-recovered-"+name+"-command.log")
  row={"name":name,"status":"running","command":command,"started_at":now(),"log":str(log)}
  state["stages"].append(row);persist();print(json.dumps({"stage":name,"status":"running"}),flush=True)
  with log.open("x") as output:
   active=subprocess.Popen(command,cwd=ROOT,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
   row["pid"]=active.pid;persist()
   try:code=active.wait(timeout=timeout)
   except subprocess.TimeoutExpired:cleanup();raise RuntimeError("Owned recovery capture timed out: "+name)
  row.update(status="completed" if code==0 else "failed",exit_code=code,finished_at=now(),log_sha256=digest(log));persist()
  assert code==0,"Preserve failed recovery evidence: "+name
  row["artifact"]={"path":str(artifact),"sha256":digest(artifact)};persist()
  print(json.dumps({"stage":name,"exit_code":code}),flush=True)
 assert git("rev-parse","HEAD")==SHA and not git("status","--porcelain")
 assert digest(BASE/"northstar-artifacts-sequence.json")==state["original_failed_sequence_sha256"]
 assert digest(BASE/"eight-state-capture/eight-state-evidence.json")==state["original_failed_capture_sha256"]
 state.update(status="passed",finished_at=now(),source_clean_after=True);persist()
 print(json.dumps({"status":"passed","source_commit":SHA,"eight_states":8,"original_failure_preserved":True,"prior_film_frames_reused":24,"concept_comparisons":3}),flush=True)
except BaseException as error:
 state.update(status="failed",failure=repr(error),finished_at=now());persist();raise
finally:cleanup()
