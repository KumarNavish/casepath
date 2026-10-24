"""Read the completed API build and verify its pinned Pillow installation."""
if not __debug__:raise RuntimeError("Assertions required")
from pathlib import Path
import hashlib,json,subprocess
BASE=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
SHA=read(BASE.parent/"source-binding.json")["source_commit"]
released=read(BASE/"api-release-sequence.json")
assert released["source_commit"]==SHA and released["status"]=="passed"
deployment=read(BASE/"api-deployment-uploaded.json")
assert deployment["source_commit"]==SHA
assert not (BASE/"api-build-log.json").exists() and not (BASE/"api-build-version.json").exists()
command=["/Users/kumar0002/.local/bin/uv","run","--offline","--no-project","--with","fastapi[standard]","--with","fastapi-cloud-cli==0.26.0","fastapi","cloud","deployments","build-logs",deployment["deployment_id"],"--app-id","ebd0862c-cd35-4da4-aae5-d32f1c40ca60","--no-follow","--json"]
result=subprocess.run(command,capture_output=True,text=True,timeout=120,cwd="/private/tmp")
data=json.loads(result.stdout)
with (BASE/"api-build-log.json").open("x") as f:json.dump(data,f,indent=2);f.write("\n")
assert result.returncode==0 and data["data"]["deployment_id"]==deployment["deployment_id"] and data["data"]["failed"] is False
lines=[str(row["message"]).strip() for row in data["data"]["logs"] if "pillow==" in str(row.get("message","")).lower()]
assert "+ pillow==13.0.0" in lines,lines
record={"source_commit":SHA,"status":"passed","deployment_id":deployment["deployment_id"],"pillow_version":"13.0.0","evidence_kind":"successful hosted image build installation log","installation_line":"+ pillow==13.0.0","raw_build_log_sha256":hashlib.sha256((BASE/"api-build-log.json").read_bytes()).hexdigest(),"build_log_command_exit":result.returncode,"server_decoder_invoked":False}
with (BASE/"api-build-version.json").open("x") as f:json.dump(record,f,indent=2);f.write("\n")
print(json.dumps(record),flush=True)

