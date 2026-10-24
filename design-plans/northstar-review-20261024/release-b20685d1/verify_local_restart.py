"""Record and verify a controlled GET-only stop/start rehearsal of the owned QA demo."""
if not __debug__:raise RuntimeError("Assertions required")
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sqlite3,sys,httpx
ROOT=Path(__file__).resolve().parents[3];NS=ROOT/".runtime/commander-northstar";BASE=NS/"release";DEMO=NS/"engineering-demo"
SHA="b20685d1670b33b941b1bfcb902638a879c01b93"
assert len(sys.argv)==2 and sys.argv[1] in ("checkpoint","verify")
mode=sys.argv[1]
read=lambda p:json.loads(p.read_text())
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
owner=read(DEMO/"owner.json");copied=read(DEMO/"data-copy.json");DATA=DEMO/"data"
assert owner["source_commit"]==copied["source_commit"]==SHA
assert owner["data_root"]==copied["copied_data"]==str(DATA)
def table_snapshot(file,tables):
 db=sqlite3.connect(file.as_uri()+"?mode=ro",uri=True)
 try:values={table:db.execute("SELECT * FROM "+table).fetchall() for table in tables}
 finally:db.close()
 result={}
 for table,rows in values.items():
  raw=json.dumps(sorted(rows,key=repr),sort_keys=True,default=lambda value:value.hex() if isinstance(value,bytes) else str(value)).encode()
  result[table]={"rows":len(rows),"sha256":hashlib.sha256(raw).hexdigest()}
 return result
def journals():
 return {"claim":table_snapshot(DATA/"casepath.db",["claim_loop_events"])["claim_loop_events"],"work":table_snapshot(DATA/"work.sqlite3",["work_events","work_runs"])}
before=journals()
with httpx.Client(timeout=30,trust_env=False) as client:
 response=client.get("http://127.0.0.1:4194/healthz");response.raise_for_status();health=response.json()
 assert health["source_commit"]==SHA and health["instance_id"]==owner["instance_id"]
 assert health["model_mode"]=="deterministic_reference" and health["external_facts_enabled"] is False
 views={}
 for claim in ("clm_f69b1747447bc221","clm_0e538990cc6ba7ef"):
  response=client.get("http://127.0.0.1:4194/api/claim-loops/v1/workspace/claims/"+claim+"/process");response.raise_for_status();value=response.json()
  assert value["claim_decision_authorized"] is False
  views[claim]={key:value[key] for key in ("workspace_revision","workspace_state_sha256","view_sha256")}
assert journals()==before
origin=Path(copied["source_data"])
original={}
for path in sorted(origin.rglob("*")):
 assert not path.is_symlink()
 if path.is_file():original[path.relative_to(origin).as_posix()]=digest(path)
assert original==copied["files"]
checkpoint=BASE/"local-demo-before-restart.json"
if mode=="checkpoint":
 assert before["claim"]==owner["journal_after"]
 record={"status":"passed","source_commit":SHA,"observed_at":datetime.now(timezone.utc).isoformat(),"instance_id":owner["instance_id"],"initial_pid":owner["pid"],"initial_session":owner["commander_session"],"initial_owner_sha256":digest(DEMO/"owner.json"),"initial_copy_sha256":digest(DEMO/"data-copy.json"),"health":health,"views":views,"journals":before,"get_only":True,"original_qa_files_unchanged":True}
 with checkpoint.open("x") as file:json.dump(record,file,indent=2);file.write("\n")
 print(json.dumps({"status":"checkpointed","source_commit":SHA,"instance_id":owner["instance_id"],"views":views}),flush=True)
else:
 prior=read(checkpoint);current=read(DEMO/"current-server.json")
 stop=read(BASE/"commander-initial-demo-stop.json");stopped=stop.get("result",stop)
 terminal=read(BASE/"commander-initial-demo-terminal.json");ended=terminal.get("result",terminal)
 live=read(BASE/"commander-resumed-demo-running.json");running=live.get("result",live)
 assert stopped["sessionId"]==ended["sessionId"]==prior["initial_session"]=="cp-ns-20261024-engineering-demo-4194"
 assert stopped["terminated"] is True and ended["state"] in ("completed","terminated","failed")
 assert running["sessionId"]==current["commander_session"]=="cp-ns-20261024-engineering-demo-resumed-4194"
 assert running["state"]=="running" and running["pid"]==current["pid"]==health["pid"]
 assert current["pid"]!=prior["initial_pid"]
 assert current["source_commit"]==SHA and current["instance_id"]==prior["instance_id"]==health["instance_id"]
 assert current["boot_id"]==health["boot_id"] and current["boot_id"]!=prior["health"].get("boot_id")
 assert current["restart_id"]==health["restart_id"] and health["startup_kind"]=="existing_owned_qa"
 assert current["launcher_sha256"]==digest(BASE/"resume_existing_review_qa.py")
 assert current["initial_owner_sha256"]==prior["initial_owner_sha256"]==digest(DEMO/"owner.json")
 assert current["initial_copy_sha256"]==prior["initial_copy_sha256"]==digest(DEMO/"data-copy.json")
 assert current["copied_or_reset_data"] is False and current["seeded_or_replayed_work"] is False
 assert current["journal_before"]==current["journal_after"]==before["claim"]
 assert current["work_before"]==current["work_after"]==before["work"]
 assert prior["journals"]==before and prior["views"]==views,"Controlled rehearsal preserves the exact current state."
 record={"status":"passed","source_commit":SHA,"observed_at":datetime.now(timezone.utc).isoformat(),"instance_id":owner["instance_id"],"boot_id":current["boot_id"],"pid":current["pid"],"resumed_session":current["commander_session"],"known_owned_initial_process_terminated":True,"actual_initial_terminal_observed":True,"resumed_process_observed_running":True,"get_only":True,"initial_owner_preserved":True,"initial_copy_receipt_preserved":True,"original_qa_files_unchanged":True,"current_claim_and_work_journals_unchanged":True,"source_and_target_views_unchanged":True,"copied_or_reset_data":False,"seeded_or_replayed_work":False,"checkpoint_sha256":digest(checkpoint),"current_server_receipt_sha256":digest(DEMO/"current-server.json"),"resume_launcher_sha256":digest(BASE/"resume_existing_review_qa.py"),"claim_and_work_journals":before,"views":views,"commander_evidence":{name:digest(BASE/name) for name in ("commander-initial-demo-stop.json","commander-initial-demo-terminal.json","commander-resumed-demo-running.json")}}
 with (BASE/"local-demo-restart-verified.json").open("x") as file:json.dump(record,file,indent=2);file.write("\n")
 print(json.dumps(record),flush=True)
