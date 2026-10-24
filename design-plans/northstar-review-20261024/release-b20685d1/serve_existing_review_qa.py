"""Serve an isolated copy of the completed engineering demo from the sealed capsule.

This launcher never seeds, starts, replays or approves a review. Its first launch
makes a verified copy of the completed QA data and leaves that evidence intact.
"""
if not __debug__:raise RuntimeError("Assertions required")
from pathlib import Path
from datetime import datetime,timezone
import fcntl,hashlib,json,os,secrets,shutil,sqlite3,sys
ROOT=Path(__file__).resolve().parents[3]
NS=ROOT/".runtime/commander-northstar";BASE=NS/"release"
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
binding=read(NS/"source-binding.json");SHA=binding["source_commit"]
assert SHA=="b20685d1670b33b941b1bfcb902638a879c01b93"
sys.path.insert(0,str(BASE))
from require_completed_gate import require_completed_gate
require_completed_gate(BASE,SHA)
completed=read(NS/"sealed-browser-command.json")
assert completed["status"]=="passed" and completed["exit_code"]==0 and completed["source_clean_after"] is True
assert completed["source_commit"]==SHA
QA=NS/"sealed-browser"
assert digest(QA/"receipt.json")==completed["artifact_hashes"]["receipt.json"]
qa=read(QA/"receipt.json")
assert qa["status"]=="passed" and not qa["browser_errors"] and not qa["unexpected_destinations"]
applied=next(row for row in qa["stages"] if row["stage"]=="later-case-application")
SOURCE,TARGET=qa["cases"]
assert (SOURCE,TARGET)==("clm_f69b1747447bc221","clm_0e538990cc6ba7ef")
CAPSULE=ROOT/".runtime/casepath-dev-v2/source-capsules"/binding["source_manifest_sha256"]
assert CAPSULE.is_dir() and not CAPSULE.is_symlink()
assert digest(CAPSULE/"casepath/source-manifest.json")==binding["source_manifest_sha256"]
capsule_receipt=read(CAPSULE/"CAPSULE_RECEIPT.json")
assert capsule_receipt["contract"]=="casepath.sealed-source-capsule/1.0.0"
assert capsule_receipt["source_manifest_file_sha256"]==binding["source_manifest_sha256"]
assert capsule_receipt["source_file_count"]==binding["source_files"] and capsule_receipt["static_file_count"]==45
for row in read(CAPSULE/"casepath/source-manifest.json")["files"]:
 assert digest(CAPSULE/row["path"])==row["sha256"],row["path"]
origin=QA/"data"
for name in ("casepath.db","work.sqlite3"):
 assert (origin/name).is_file() and not (origin/name).is_symlink()
assert (origin/"evidence").is_dir() and not (origin/"evidence").is_symlink()
lock=(NS/"engineering-demo.lock").open("a+")
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
DEMO=NS/"engineering-demo"
assert not DEMO.exists(),"Reconcile the owned demo before any restart or replacement."
DEMO.mkdir(mode=0o700)
DATA=DEMO/"data"
def inventory(folder):
 records={}
 for p in sorted(folder.rglob("*")):
  assert not p.is_symlink(),str(p)
  if p.is_file():records[p.relative_to(folder).as_posix()]=digest(p)
 return records
original_files=inventory(origin)
shutil.copytree(origin,DATA)
assert inventory(DATA)==original_files
def journal(folder):
 db=sqlite3.connect((folder/"casepath.db").as_uri()+"?mode=ro",uri=True)
 try:rows=db.execute("SELECT * FROM claim_loop_events").fetchall()
 finally:db.close()
 raw=json.dumps(sorted(rows,key=repr),sort_keys=True,default=lambda value:value.hex() if isinstance(value,bytes) else str(value)).encode()
 return {"rows":len(rows),"sha256":hashlib.sha256(raw).hexdigest()}
before=journal(DATA)  # Journal content of the byte-verified source snapshot; never open the original SQLite files.
with (DEMO/"data-copy.json").open("x") as f:
 json.dump({"source_commit":SHA,"qa_receipt_sha256":digest(QA/"receipt.json"),"source_data":str(origin),"copied_data":str(DATA),"files":original_files,"journal":before,"byte_identical_at_copy":True},f,indent=2);f.write("\n")
os.environ["CASEPATH_AGENT_WORK_EXTERNAL_FACTS"]="0"
os.environ["CASEPATH_MODEL_MODE"]="deterministic_reference"
sys.path[:0]=[str(CAPSULE/"casepath-api"),str(CAPSULE/"casepath-api/tests")]
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
from test_workspace_claim_loop_v1 import _system
from casepath_api.workspace_corpus import PublicCorpus,default_workspace_corpus_root
from casepath_api.claim_loop_router import create_claim_loop_router
from casepath_api.workspace_packet_preview import create_packet_preview_router
from casepath_api.causal_workspace_v1 import CausalWorkspaceService
from casepath_api.agent_work.authority import ExistingCasePathAuthority
from casepath_api.agent_work.service import AgentWorkService
from casepath_api.agent_work.store import WorkStore
from casepath_api.agent_work.api import create_agent_work_router
from casepath_api.agent_desk_v1 import AgentDeskServiceV1,create_agent_desk_router
storage,workspace,normal,facade=_system(DATA,corpus=PublicCorpus(default_workspace_corpus_root()))
work=AgentWorkService(WorkStore(DATA/"work.sqlite3"),ExistingCasePathAuthority(lambda:workspace,lambda:facade),facts_worker=None,external_configuration_status="disabled")
desk=AgentDeskServiceV1(workspace,work)
processes=CausalWorkspaceService(workspace)
source=processes.view(SOURCE);target=processes.view(TARGET)
pin=next(row for row in target["graph"]["fragment_instances"] if row["fragment_sha256"]==applied["pin"]["fragment_sha256"])
assert pin==applied["pin"] and pin["version"]==1
event=next(row for row in reversed(target["history"]) if row["operation"]["type"]=="fragment.apply" and row["operation"]["fragment_sha256"]==pin["fragment_sha256"])
assert event["event_sha256"]==applied["event"]
assert target["workspace_revision"]==applied["workspace_revision"] and target["claim_decision_authorized"] is False
assert journal(DATA)==before
assert inventory(origin)==original_files
app=FastAPI()
app.include_router(create_packet_preview_router(lambda:workspace))
app.include_router(create_agent_work_router(lambda:work))
app.include_router(create_agent_desk_router(lambda:desk))
app.include_router(create_claim_loop_router(lambda:storage,service_getter=lambda:normal,workspace_service_getter=lambda:workspace,workspace_loop_service_getter=lambda:facade,accepted_process_hook=lambda claim_id,result:desk.process_accepted(claim_id,result,dispatch=False)))
instance=secrets.token_hex(12)
owner={"source_commit":SHA,"source_manifest_sha256":binding["source_manifest_sha256"],"launcher_sha256":digest(__file__),"qa_receipt_sha256":digest(QA/"receipt.json"),"capsule_receipt_sha256":digest(CAPSULE/"CAPSULE_RECEIPT.json"),"pid":os.getpid(),"instance_id":instance,"host":"127.0.0.1","port":4194,"commander_session":"cp-ns-20261024-engineering-demo-4194","status":"initialization_verified","started_at":datetime.now(timezone.utc).isoformat(),"data_root":str(DATA),"work_store":str(DATA/"work.sqlite3"),"evidence_root":str(DATA/"evidence"),"source_capsule":str(CAPSULE),"review_actions_at_startup":0,"original_qa_data_preserved":True,"journal_before":before,"journal_after":journal(DATA),"target_pin":pin,"target_event_sha256":event["event_sha256"],"target_workspace_state_sha256":target["workspace_state_sha256"],"target_view_sha256":target["view_sha256"],"qualified_human_approval":False,"label":"Isolated engineering demo — recorded Test handler actions; no human approval"}
with (DEMO/"owner.json").open("x") as f:json.dump(owner,f,indent=2);f.write("\n")
@app.get("/healthz")
def health():
 return {"status":"ok","source_commit":SHA,"instance_id":instance,"label":owner["label"],"model_mode":"deterministic_reference","external_facts_enabled":False,"review_actions_at_startup":0,"cases":[SOURCE,TARGET],"isolated_writable_qa_store":True}
app.add_event_handler("shutdown",work.shutdown)
app.mount("/",StaticFiles(directory=CAPSULE/"casepath",html=True),name="review-ui")
print(json.dumps(owner),flush=True)
uvicorn.run(app,host="127.0.0.1",port=4194,access_log=False)
