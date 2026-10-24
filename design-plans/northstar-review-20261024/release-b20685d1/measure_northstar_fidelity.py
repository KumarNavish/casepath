"""Measure three concept comparisons without changing the product or its captures."""
if not __debug__:raise RuntimeError("Assertions required")
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os,subprocess
NS=Path(__file__).resolve().parent.parent;ROOT=NS.parents[1];BASE=NS/"release"
SHA="b20685d1670b33b941b1bfcb902638a879c01b93"
CAPTURE=BASE/"eight-state-capture";OUT=BASE/"northstar-fidelity"
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
states=json.loads((CAPTURE/"eight-state-evidence.json").read_text())
assert states["status"]=="passed" and states["source_commit"]==SHA
assert not OUT.exists();OUT.mkdir()
env=dict(os.environ)
env["PLAYWRIGHT_MODULE"]="/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/node_modules/playwright/index.mjs"
env["PLAYWRIGHT_CHROMIUM"]="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
assert Path(env["PLAYWRIGHT_MODULE"]).is_file()
tool=ROOT/"design-plans/tools/fidelity.mjs"
report={"source_commit":SHA,"created_at":datetime.now(timezone.utc).isoformat(),"tool_sha256":digest(tool),"scope":"Measured concept comparisons; numeric differences do not establish semantic acceptance.","comparisons":[],"status":"running"}
receipt=OUT/"fidelity-measurements.json"
def persist():receipt.write_text(json.dumps(report,indent=2)+"\n")
persist()
try:
 for number,concept in ((4,"01-decision-building.png"),(6,"02-completed-process.png"),(8,"03-reviewed-memory-payoff.png")):
  state=next(row for row in states["states"] if row["state"]==number);frame=CAPTURE/state["file"]
  assert digest(frame)==state["sha256"]
  reference=ROOT/"design/northstar"/concept;prefix=OUT/("concept-"+concept[:2])
  result=subprocess.run(["/usr/local/bin/node",str(tool),str(reference),str(frame),str(prefix)],cwd=ROOT,env=env,text=True,capture_output=True,timeout=120)
  log=OUT/(prefix.name+"-command.log");log.write_text(result.stdout+result.stderr)
  assert result.returncode==0,result.stderr[-2000:]
  measured=json.loads(result.stdout.strip().splitlines()[-1])
  row={"concept":concept,"concept_sha256":digest(reference),"state":number,"frame":state["file"],"frame_sha256":digest(frame),"mean_difference_pct":measured["mean_difference_pct"],"command_log_sha256":digest(log),"outputs":[]}
  for kind in ("side","overlay","diff"):
   image=Path(str(prefix)+"-"+kind+".png");assert image.is_file()
   row["outputs"].append({"kind":kind,"file":image.name,"sha256":digest(image),"bytes":image.stat().st_size})
  report["comparisons"].append(row);persist()
 report["status"]="measured";report["visual_review"]="pending";persist()
 print(json.dumps({"status":"measured","source_commit":SHA,"mean_difference_pct":[row["mean_difference_pct"] for row in report["comparisons"]]}))
except BaseException as error:
 report["status"]="failed";report["failure"]=repr(error);persist();raise
