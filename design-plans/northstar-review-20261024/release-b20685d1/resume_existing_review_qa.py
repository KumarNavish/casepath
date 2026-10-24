"""Restart the existing owned engineering demo without copying or resetting its data.

The original evidence, initial owner and original copy receipt remain unchanged.
This launcher never seeds, starts, resumes or replays investigation work.
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
lock_path=NS/"engineering-demo.lock"
assert lock_path.is_file() and not lock_path.is_symlink(),"Initial owned demo lock must exist."
lock=lock_path.open("r+")
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
DEMO=NS/"engineering-demo";DATA=DEMO/"data"
assert DEMO.is_dir() and not DEMO.is_symlink() and DATA.is_dir() and not DATA.is_symlink()
owner_path=DEMO/"owner.json";copy_path=DEMO/"data-copy.json"
assert owner_path.is_file() and not owner_path.is_symlink()
assert copy_path.is_file() and not copy_path.is_symlink()
owner=read(owner_path);copied=read(copy_path)
assert owner["source_commit"]==copied["source_commit"]==SHA
assert owner["host"]=="127.0.0.1" and owner["port"]==4194
assert owner["data_root"]==copied["copied_data"]==str(DATA)
assert copied["source_data"]==str(origin) and copied["byte_identical_at_copy"] is True
assert owner["qa_receipt_sha256"]==copied["qa_receipt_sha256"]==digest(QA/"receipt.json")
assert owner["source_manifest_sha256"]==binding["source_manifest_sha256"]
assert owner["source_capsule"]==str(CAPSULE)
assert owner["capsule_receipt_sha256"]==digest(CAPSULE/"CAPSULE_RECEIPT.json")
assert owner["launcher_sha256"]==digest(BASE/"serve_existing_review_qa.py")
initial_owner_sha256=digest(owner_path);initial_copy_sha256=digest(copy_path)
def inventory(folder):
 records={}
 for p in sorted(folder.rglob("*")):
  assert not p.is_symlink(),str(p)
  if p.is_file():records[p.relative_to(folder).as_posix()]=digest(p)
 return records
original_files=inventory(origin)
assert original_files==copied["files"],"Original sealed QA evidence changed."
inventory(DATA)
for name in ("casepath.db","work.sqlite3"):assert (DATA/name).is_file()
assert (DATA/"evidence").is_dir()
def journal(folder):
 db=sqlite3.connect((folder/"casepath.db").as_uri()+"?mode=ro",uri=True)
 try:rows=db.execute("SELECT * FROM claim_loop_events").fetchall()
 finally:db.close()
 raw=json.dumps(sorted(rows,key=repr),sort_keys=True,default=lambda value:value.hex() if isinstance(value,bytes) else str(value)).encode()
 return {"rows":len(rows),"sha256":hashlib.sha256(raw).hexdigest()}
before=journal(DATA)
def work_state(folder):
 db=sqlite3.connect((folder/"work.sqlite3").as_uri()+"?mode=ro",uri=True)
 try:
  events=db.execute("SELECT * FROM work_events ORDER BY run_id, sequence").fetchall()
  runs=db.execute("SELECT * FROM work_runs ORDER BY run_id").fetchall()
 finally:db.close()
 encode=lambda rows:json.dumps(sorted(rows,key=repr),sort_keys=True,default=lambda value:value.hex() if isinstance(value,bytes) else str(value)).encode()
 return {"work_events":{"rows":len(events),"sha256":hashlib.sha256(encode(events)).hexdigest()},"work_runs":{"rows":len(runs),"sha256":hashlib.sha256(encode(runs)).hexdigest()}}
before_work=work_state(DATA)
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
assert any(row["event_sha256"]==applied["event"] and row["operation"]["type"]=="fragment.apply" and row["operation"]["fragment_sha256"]==applied["pin"]["fragment_sha256"] for row in target["history"]),"Current QA journal does not retain its original accepted application."
assert source["claim_decision_authorized"] is False and target["claim_decision_authorized"] is False
assert journal(DATA)==before,"Restart must append no review events."
assert work_state(DATA)==before_work,"Restart must not append work events or change run states."
assert inventory(origin)==original_files
assert digest(owner_path)==initial_owner_sha256 and digest(copy_path)==initial_copy_sha256
app=FastAPI()
app.include_router(create_packet_preview_router(lambda:workspace))
app.include_router(create_agent_work_router(lambda:work))
app.include_router(create_agent_desk_router(lambda:desk))
app.include_router(create_claim_loop_router(lambda:storage,service_getter=lambda:normal,workspace_service_getter=lambda:workspace,workspace_loop_service_getter=lambda:facade,accepted_process_hook=lambda claim_id,result:desk.process_accepted(claim_id,result,dispatch=False)))
instance=owner["instance_id"]
boot_id=secrets.token_hex(12)
session_id=os.environ.get("CASEPATH_DEMO_SESSION","manual-terminal")
assert session_id and len(session_id)<=100 and all(c.isalnum() or c in "._:-" for c in session_id)
restart_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+str(os.getpid())
restarts=DEMO/"restarts"
assert not restarts.is_symlink()
restarts.mkdir(mode=0o700,exist_ok=True)
restart={"contract":"casepath.owned-qa-restart/1","source_commit":SHA,"source_manifest_sha256":binding["source_manifest_sha256"],"launcher_sha256":digest(__file__),"initial_owner_sha256":initial_owner_sha256,"initial_copy_sha256":initial_copy_sha256,"qa_receipt_sha256":digest(QA/"receipt.json"),"pid":os.getpid(),"instance_id":instance,"host":"127.0.0.1","port":4194,"commander_session":session_id,"restart_id":restart_id,"boot_id":boot_id,"status":"initialization_verified","started_at":datetime.now(timezone.utc).isoformat(),"data_root":str(DATA),"copied_or_reset_data":False,"seeded_or_replayed_work":False,"review_actions_at_startup":0,"original_qa_data_preserved":True,"journal_before":before,"journal_after":journal(DATA),"work_before":before_work,"work_after":work_state(DATA),"source_workspace_state_sha256":source["workspace_state_sha256"],"target_workspace_state_sha256":target["workspace_state_sha256"],"source_view_sha256":source["view_sha256"],"target_view_sha256":target["view_sha256"],"source_workspace_revision":source["workspace_revision"],"target_workspace_revision":target["workspace_revision"],"current_target_pins":target["graph"]["fragment_instances"],"qualified_human_approval_asserted":False,"label":"Isolated engineering demo — no qualified approval is asserted by this launcher"}
restart_path=restarts/(restart_id+".json")
with restart_path.open("x") as file:json.dump(restart,file,indent=2);file.write("\n")
current=DEMO/"current-server.json"
if current.exists():assert current.is_file() and not current.is_symlink()
temporary=DEMO/("current-server-"+restart_id+".next")
with temporary.open("x") as file:json.dump(restart,file,indent=2);file.write("\n")
os.replace(temporary,current)
@app.get("/healthz")
def health():
 return {"status":"ok","source_commit":SHA,"instance_id":instance,"label":restart["label"],"restart_id":restart_id,"boot_id":boot_id,"pid":os.getpid(),"startup_kind":"existing_owned_qa","model_mode":"deterministic_reference","external_facts_enabled":False,"review_actions_at_startup":0,"cases":[SOURCE,TARGET],"isolated_writable_qa_store":True}
app.add_event_handler("shutdown",work.shutdown)
app.mount("/",StaticFiles(directory=CAPSULE/"casepath",html=True),name="review-ui")
print(json.dumps(restart),flush=True)
uvicorn.run(app,host="127.0.0.1",port=4194,access_log=False)
