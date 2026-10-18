from pathlib import Path
import hashlib,json,os,re,subprocess,time
R=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');O=R/'independent-review';SHA='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59';BASE='8f230fd4ad455a15a7a53803ae7b857a4db2aaff';MAN='0d713ebe1ea45681c139ac8ed39b5d9c811cdfb6ea08af55617e155ecf60c2b8';BACK='af78642d485e050674b462718517f6e2cadaa308';TOOLS='8b92084acd150783b5f728893fed47d9e2b71f5c'
def read(p):return json.loads(p.read_text())
def h(raw):return hashlib.sha256(raw).hexdigest()
def git(repo,*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=repo,env=dict(os.environ,GIT_NO_LAZY_FETCH='1'))
def save(name,x):
 p=O/name
 if p.exists():print(json.dumps({'path':str(p),'sha256':h(p.read_bytes()),'status':read(p)['status']}));return
 x.update(candidate=SHA,manifest_sha256=MAN,reviewer='/root/gate_4bf_review',reviewed_epoch=time.time());p.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':h(p.read_bytes()),'status':x['status']}))
assert Path('/proc/sys/kernel/hostname').read_text().strip()=='656813ef2295'
proof=read(R/'approved-retirement-proof.json');result=read(R/'approved-retirement-result.json');assert proof['candidate']==SHA and proof['manifest_sha256']==MAN and proof['source_file_count']==1718 and proof['owned_processes']==[]
expected=['/workspace/casepath-release-ae0-shard3/.runtime/casepath-dev-v2','/workspace/casepath-read-seed-20261018/backend/warm-proof-tmp','/workspace/casepath-read-seed-20261018/review/fixtures','/workspace/read-seed-tools-test/tmp']
assert [x['path'] for x in proof['approved_paths']]==result['retired_only']==expected and sum(x['entries'] for x in proof['approved_paths'])==6675
for x in proof['approved_paths']:
 assert x['entries']==len(x['inventory']) and len({a['path'] for a in x['inventory']})==x['entries']
 for row in x['inventory']:
  assert not Path(row['path']).is_absolute() and '..' not in Path(row['path']).parts
  if 'sha256' in row:assert re.fullmatch('[0-9a-f]{64}',row['sha256'])
assert result['remote_ref_exact'] and result['remote_actual_bytes_match'] and result['remote_proof_sha256']==h((R/'approved-retirement-proof.json').read_bytes()) and result['owned_processes_before_delete']==[] and result['all_receipts_logs_sources_exports_package_selector_preserved']
er=Path('/workspace/casepath-transport-gate-evidence-git-20261015');P='66977e5eacec68c98e37c99b09a6a5f2e1771ef5';prefix='qa-receipts/read-seed-gate-addc5a77-20261018/'
assert git(er,'show',P+':'+prefix+'approved-retirement-proof.json')==(R/'approved-retirement-proof.json').read_bytes()
for row in proof['source_branches_preserved']:assert git(Path(row['path']),'rev-parse','refs/heads/'+row['branch']).decode().strip()==row['head']==row['remote'] and row['status']==''
save('preflight-retirement-review.json',{'status':'PASS_APPROVED_RETIREMENT_PROOF','proof_commit':P,'proof_sha256':h((R/'approved-retirement-proof.json').read_bytes()),'result_sha256':h((R/'approved-retirement-result.json').read_bytes()),'local_immutable_git_bytes_equal':True,'remote_exact_byte_verification':'Coordinator receipt; reviewer performed no network operation.','approved_paths':expected,'inventory_entries':6675,'source_branch_refs_preserved':[BACK,TOOLS],'prior_runtime_identity_qualified':proof['runtime_identity'],'retired_only_four_approved_paths':True,'no_own_cleanup':True,'limits':['Initial retirement EACCES13 and subsequent narrow chmod authorization were conveyed by parent; separate negative raw receipt not inspected at this snapshot.','Prior8f1714 runtime/capsule inventory is deliberately separate from current addc1718 source and prior focused af786 source.']})
manifest=read(R/'source-manifest.json');assert h((R/'source-manifest.json').read_bytes())==MAN and len(manifest['files'])==manifest['file_count']==1718
repos=read(R/'clone-map.json')['repos'];obs=[];source_bindings={};changes=None;branch_repos={BACK:Path('/workspace/casepath-release-ae0-shard3'),TOOLS:Path('/workspace/casepath-release-ae0-shard4')}
for n in range(1,7):
 repo=Path(repos[str(n)]);assert (repo/'.git').is_dir() and not (repo/'.git').is_symlink() and git(repo,'rev-parse','HEAD').decode().strip()==SHA and not git(repo,'status','--porcelain') and h((repo/'casepath/source-manifest.json').read_bytes())==MAN
 for row in manifest['files']:
  p=repo/row['path'];assert not p.is_symlink() and p.stat().st_size==row['size_bytes'] and h(p.read_bytes())==row['sha256']
 paths=[]
 for tip in [BACK,TOOLS]:
  fs=git(branch_repos[tip],'diff','--name-only',BASE,tip).decode().splitlines();assert len(fs)==5
  for f in fs:assert (repo/f).read_bytes()==git(branch_repos[tip],'show',tip+':'+f);source_bindings[f]={'reviewed_commit':tip,'sha256':h((repo/f).read_bytes())}
  paths+=fs
 changed=git(repo,'diff','--name-only',BASE,SHA).decode().splitlines();assert len(set(paths))==10 and set(changed)==set(paths)|{'casepath/source-manifest.json'};changes=changed
 assert not (repo/'casepath-api/casepath_api/artifacts/hosted-read-seed-v1.json').exists()
 obs.append({'shard':n,'repo':str(repo),'head':SHA,'status':'','normal_clone':True,'direct_sealed_files_verified':1718,'backend_and_tools_bytes_equal_reviewed_branches':True,'optional_private_seed_absent':True})
q=read(R/'optional-seed-isolation.json');assert q['candidate']==SHA and not q['parent_CASEPATH_READ_SEED_PATH_present'] and not q['inherited_to_children'] and q['package_seed_absent_in_all_six'] and not q['real_seed_or_private_data_allowed'] and q['synthetic_test_fixtures_only']
save('source-admission-review.json',{'status':'PASS_SOURCE_ADMISSION','actual_cloud_host':'656813ef2295','source_file_count':1718,'base':BASE,'reviewed_backend_commit':BACK,'reviewed_tools_commit':TOOLS,'source_bindings':source_bindings,'changed_paths_vs_8f':changes,'clone_observations':obs,'optional_seed_isolation_sha256':h((R/'optional-seed-isolation.json').read_bytes()),'limits':['Read-only source admission; six terminal raw/JUnit/source/runtime results remain pending.','No production requests, private seed acquisition, private data inspection, exporter execution, upload, package publication, or deployment by this reviewer.']})
