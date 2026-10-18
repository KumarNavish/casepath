import collections, hashlib, json, os, stat, subprocess, tarfile, time
import xml.etree.ElementTree as ET
from pathlib import Path
R=Path('/workspace/casepath-mobile-context-gate-a89b97bb-20261018')
SHA='a89b97bb8eecdd8e98771c99ca879d4e253f7881'
MAN='416eea6c4831046fca1bab76ec7072bc116cdc2912a169b094341d3a2ee68b0a'
OUT=R/'shard6'
REPO=Path('/workspace/casepath-operations-review-20261013')
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
assignment=read(R/'shard-map.json')
assert assignment['candidate']==SHA and assignment['manifest_sha256']==MAN
assigned=assignment['shards']['6']; assert len(assigned)==len(set(assigned))==658
arguments=(OUT/'pytest-arguments.txt').read_text().splitlines()
collected_rows=read(OUT/'collected.json');collected=[x['id'] for x in collected_rows]
assert assigned==arguments==collected
result=read(OUT/'result.json');attempt=read(OUT/'ATTEMPT_STARTED.json')
assert result['candidate']==attempt['candidate']==SHA and result['exit_code']==0
assert result['after_head']==SHA and result['after_status']==''
assert attempt['retry_allowed'] is False and attempt['started_epoch']==result['started_epoch']
assert result['command']==attempt['command']==read(OUT/'command.json')['command']
assert result['env']['HOME']=='/workspace/a9h6' and result['env']['TMPDIR']=='/workspace/a9t6'
assert result['env']['CASEPATH_MODEL_MODE']=='deterministic_reference'
assert result['env']['CASEPATH_DB_PATH']==str(OUT/'casepath.db')
terminal=read(OUT/'worker-terminal.json')
assert terminal['candidate']==SHA and terminal['results']==[{'shard':6,'exit_code':0,'source_after_exit_code':0,'attempt_count':1,'result_path':str(OUT/'result.json')}]
reports=[json.loads(x) for x in (OUT/'reports.jsonl').read_text().splitlines()]
assert len(reports)==3*len(assigned)
assert set(x['id'] for x in reports)==set(assigned)
assert len({(x['id'],x['when']) for x in reports})==len(reports)
per=collections.defaultdict(list)
for x in reports:per[x['id']].append((x['when'],x['outcome']))
assert all(v==[('setup','passed'),('call','passed'),('teardown','passed')] for v in per.values())
known_assigned=[x for x in read(R/'known-skips.json') if x['id'] in assigned]
assert not known_assigned
jroot=ET.parse(OUT/'junit.xml').getroot(); cases=jroot.findall('.//testcase')
assert len(cases)==658
expected=[]
for x in collected_rows:
 parts=x['pytest_nodeid'].split('::')
 classname='.'.join([parts[0].removesuffix('.py').replace('/','.')]+parts[1:-1])
 expected.append((classname,parts[-1]))
assert [(x.attrib['classname'],x.attrib['name']) for x in cases]==expected
assert all(not x.findall('failure') and not x.findall('error') and not x.findall('skipped') for x in cases)
suites=jroot.findall('.//testsuite')
assert sum(int(s.attrib['tests']) for s in suites)==658
assert all(all(int(s.attrib.get(k,'0'))==0 for k in ['errors','failures','skipped']) for s in suites)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
status=subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True)
assert head==SHA and status=='' and (REPO/'.git').is_dir()
before=read(OUT/'source-before/capsule-verification.json');after=read(OUT/'source-after/capsule-verification.json')
assert before['head']==after['head']==SHA and before['status']==after['status']==''
assert before['manifest_sha256']==after['manifest_sha256']==MAN
assert before['capsule_receipt']==after['capsule_receipt']
assert before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
CAPSULE=Path(after['capsule_root']); receipt=read(CAPSULE/'CAPSULE_RECEIPT.json')
assert receipt==before['capsule_receipt']
semantic=dict(receipt); stated=semantic.pop('receipt_sha256')
assert hashlib.sha256(canon(semantic)).hexdigest()==stated
assert digest(CAPSULE/'CAPSULE_RECEIPT.json')==before['capsule_receipt_file_sha256']
assert digest(OUT/'source-before/CAPSULE_RECEIPT.json')==digest(OUT/'source-after/CAPSULE_RECEIPT.json')==before['capsule_receipt_file_sha256']
source=read(REPO/'casepath/source-manifest.json')
assert digest(REPO/'casepath/source-manifest.json')==MAN
assert len(source['files'])==source['file_count']==receipt['source_file_count']==1714
for root in [REPO,CAPSULE]:
 assert digest(root/'casepath/source-manifest.json')==MAN
 for x in source['files']:
  p=root/x['path'];assert not p.is_symlink() and p.stat().st_size==x['size_bytes'] and digest(p)==x['sha256'],str(p)
artifactrel=source['artifact_manifest']['path']
artifact=read(REPO/artifactrel)
assert digest(REPO/artifactrel)==source['artifact_manifest']['sha256']==receipt['artifact_manifest_file_sha256']
assert len(artifact['files'])==artifact['file_count']==receipt['artifact_file_count']==25
static_inventories=[]
for root in [REPO,CAPSULE]:
 assert digest(root/artifactrel)==receipt['artifact_manifest_file_sha256']
 for x in artifact['files']:
  p=root/'casepath-api/artifacts'/x['path'];assert not p.is_symlink() and p.stat().st_size==x['size_bytes'] and digest(p)==x['sha256'],str(p)
 rows=[];public=root/'casepath-public'
 for p in sorted(public.rglob('*')):
  assert not p.is_symlink()
  if p.is_file():
   rows.append({'path':p.relative_to(public).as_posix(),'sha256':digest(p),'size_bytes':p.stat().st_size,'executable':bool(p.stat().st_mode & stat.S_IXUSR)})
   if p.name!='deployment.json':assert p.read_bytes()==(root/'casepath'/p.relative_to(public)).read_bytes()
 assert len(rows)==receipt['static_file_count']==40
 assert hashlib.sha256(canon(rows)).hexdigest()==receipt['static_inventory_sha256']
 static_inventories.append(rows)
assert static_inventories[0]==static_inventories[1]
rb=read(OUT/'runtime-before.json');ra=read(OUT/'runtime-after.json')
assert rb['candidate']==ra['candidate']==SHA and rb['observed_before_test_start'] is True
assert rb['original_test_attempt_started_epoch'] is None and rb['observed_epoch']<attempt['started_epoch']
assert rb['rows']==ra['rows'] and rb['inventory_sha256']==ra['inventory_sha256']
assert ra['before_after_inventory_equal'] is True
runtime_root=REPO/'.runtime/casepath-dev-v2/venv';rows=[]
for p in sorted(runtime_root.rglob('*')):
 rel=p.relative_to(runtime_root).as_posix()
 if p.is_symlink():
  dest=p.resolve(strict=True);rows.append({'path':rel,'symlink':os.readlink(p),'resolved_path':str(dest),'resolved_file_sha256':digest(dest) if dest.is_file() else None})
 elif p.is_file():rows.append({'path':rel,'size_bytes':p.stat().st_size,'mode':stat.S_IMODE(p.stat().st_mode),'sha256':digest(p)})
assert len(rows)==rb['file_and_symlink_count']==ra['file_and_symlink_count']==3800
assert rows==ra['rows']
assert hashlib.sha256(canon(rows)).hexdigest()==ra['inventory_sha256']
arch=read(R/'retirement-receipts/shard6-raw-archive.json');archive_path=Path(arch['archive'])
assert arch['shard']=='6' and arch['raw_archive_byte_verified'] is True
assert digest(archive_path)==arch['archive_sha256']
with tarfile.open(archive_path,'r:gz') as t:
 members=t.getmembers();assert len(members)==len(arch['files']) and {m.name for m in members}==set(arch['files'])
 for m in members:
  assert m.isfile()
  raw=t.extractfile(m).read();assert hashlib.sha256(raw).hexdigest()==arch['files'][m.name]==digest(OUT/m.name)
rawfiles=['ATTEMPT_STARTED.json','command.json','result.json','collected.json','pytest-arguments.txt','reports.jsonl','junit.xml','pytest.log','process-ownership.json','worker-terminal.json']
receipt_out={'candidate':SHA,'manifest_sha256':MAN,'shard':6,'validation_epoch':time.time(),'attempt_count':1,'counts':{'assigned':658,'arguments':658,'collected':658,'junit':658,'passed':658,'failed':0,'skipped':0,'xfailed':0,'phase_reports':len(reports)},'exact_ordered_map_arguments_collected_junit_ids_equal':True,'every_assigned_id_has_exactly_one_passed_setup_call_teardown':True,'phase_counts':dict(collections.Counter(x['when']+':'+x['outcome'] for x in reports)),'known_skip_ids_assigned':len(known_assigned),'pytest_exit_code':result['exit_code'],'started_epoch':result['started_epoch'],'finished_epoch':result['finished_epoch'],'duration_seconds':result['duration_seconds'],'junit_suites':[x.attrib for x in suites],'source':{'head':head,'status':status,'sealed_files_independently_byte_verified_each_root':1714,'artifact_files_independently_byte_verified_each_root':25,'static_files_independently_byte_verified_each_root':40,'capsule_receipt_equal_before_after':True,'capsule_receipt_file_sha256':before['capsule_receipt_file_sha256'],'before_proof_sha256':digest(OUT/'source-before/capsule-verification.json'),'after_proof_sha256':digest(OUT/'source-after/capsule-verification.json')},'runtime':{'before_observed_before_test_start':True,'before_after_inventory_equal':True,'current_runtime_independently_matches':True,'file_and_symlink_count':len(rows),'inventory_sha256':ra['inventory_sha256'],'before_record_sha256':digest(OUT/'runtime-before.json'),'after_record_sha256':digest(OUT/'runtime-after.json')},'raw_archive':{'path':str(archive_path),'sha256':arch['archive_sha256'],'file_count':len(arch['files']),'byte_verified_independently':True,'pushed_flag_at_receipt_read':arch['pushed']},'raw_evidence_hashes':{x:digest(OUT/x) for x in rawfiles},'runtime_retired_by_worker':False,'source_edits':False,'retries':0,'extra_test_commands':0}
with (OUT/'independent-terminal-validation.json').open('x') as f:json.dump(receipt_out,f,indent=2);f.write('\n')
print(json.dumps(receipt_out,indent=2))
