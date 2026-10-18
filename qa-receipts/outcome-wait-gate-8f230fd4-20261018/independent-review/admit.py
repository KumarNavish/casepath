from pathlib import Path
import hashlib,json,re,subprocess,time
R=Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018');O=R/'independent-review';SHA='8f230fd4ad455a15a7a53803ae7b857a4db2aaff';BASE='4bf9b439813ae5dd82c8820cbe96e4c1ec6db2cd';MAN='b7af849b48589e598bcb5385d7dd4ad63bc9a868e634f62ff0be96910ec453e3';F6='f6e6f7bb033f38b4d999fe0f5b353f656eef87bd'
EXPECTED={'casepath/assets/autonomous-language-v1.js':'a803c34ceb0f995fb1eb05eeb6ba52cc9c8d9c210d767a3c6140ba381b651594','casepath-qa/autonomous-language-v1.test.cjs':'f6202f002fdad90f661f75891b18e11e04f8f191f345eaaceb9997754c06b90f'}
def h(raw):return hashlib.sha256(raw).hexdigest()
def read(p):return json.loads(p.read_text())
def git(repo,*args):return subprocess.check_output(['git','--no-optional-locks',*args],cwd=repo)
def save(name,x):
 x.update(candidate=SHA,manifest_sha256=MAN,reviewer='/root/gate_4bf_review',reviewed_epoch=time.time());p=O/name;p.write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'path':str(p),'sha256':h(p.read_bytes()),'status':x['status']}))
manifest=read(R/'source-manifest.json');assert h((R/'source-manifest.json').read_bytes())==MAN and len(manifest['files'])==manifest['file_count']==1714
assert Path('/proc/sys/kernel/hostname').read_text().strip()=='656813ef2295'
repos=read(R/'clone-map.json')['repos'];observations=[];diff=None
for n in range(1,7):
 repo=Path(repos[str(n)]);assert (repo/'.git').is_dir() and not (repo/'.git').is_symlink() and git(repo,'rev-parse','HEAD').decode().strip()==SHA and not git(repo,'status','--porcelain') and h((repo/'casepath/source-manifest.json').read_bytes())==MAN
 for row in manifest['files']:
  p=repo/row['path'];assert not p.is_symlink() and p.stat().st_size==row['size_bytes'] and h(p.read_bytes())==row['sha256']
 for path,sha in EXPECTED.items():assert h((repo/path).read_bytes())==sha and (repo/path).read_bytes()==git(repo,'show',F6+':'+path)
 changed=git(repo,'diff','--name-only',BASE,SHA).decode().splitlines();assert set(changed)==set(EXPECTED)|{'casepath/index.html','casepath/source-manifest.json'};diff=changed
 index=(repo/'casepath/index.html').read_text();assert 'autonomous-language-v1.js?sha256='+EXPECTED['casepath/assets/autonomous-language-v1.js'] in index
 observations.append({'shard':n,'repo':str(repo),'head':SHA,'status':'','normal_clone':True,'direct_sealed_files_verified':1714,'reviewed_f6_language_bytes_equal':True})
save('source-admission-review.json',{'status':'PASS_SOURCE_ADMISSION','actual_cloud_host':'656813ef2295','source_file_count':1714,'base':BASE,'reviewed_language_commit':F6,'changed_paths_vs_4bf':diff,'language_source_hashes':EXPECTED,'index_pin_matches':True,'clone_observations':observations,'limits':['Source admission only; current fresh pytest collection, six terminal attempts, and current Mac127 attestation remain pending.','Protected f6 writer checkout was not selected, reset, or mutated by this reviewer.']})
er=Path('/workspace/casepath-transport-gate-evidence-git-20261015');E='81c71464a5e33b51de0159f064b7cd4d2e713ed4';sub='qa-evidence/outcome-wait-reasons-20261018/'
def show(path):return git(er,'show',E+':'+sub+path)
sums={}
for line in show('SHA256SUMS').decode().splitlines():
 sha,path=line.split('  ',1);assert h(show(path))==sha;sums[path]=sha
assert len(sums)==28 and sums['review/review-receipt.json']=='dba1935a26616fc35ef08fd0fedb5f9a6d8bf32016353d35f7a1b1e2ff7787c1'
review=json.loads(show('review/review-receipt.json'));native=json.loads(show('root/native-nine.json'));coord=json.loads(show('coordinator-verification.json'))
def counts(path):
 tap=show(path).decode();return {k:int(re.search(r'^[#ℹ] '+k+r' (\d+)\s*$',tap,re.M)[1]) for k in ['tests','pass','fail','skipped']}
assert counts('writer/green.tap')=={'tests':62,'pass':62,'fail':0,'skipped':0} and counts('writer/red.tap')=={'tests':45,'pass':0,'fail':45,'skipped':0} and int(show('writer/green.exit').strip())==0 and int(show('writer/red.exit').strip())==1
assert native['count']==9 and native['all_passed'] and native['patched_language_sha256']==EXPECTED['casepath/assets/autonomous-language-v1.js'] and coord['source_sha256']==EXPECTED
save('focused-evidence-binding.json',{'status':'PASS_EXISTING_FOCUSED_EVIDENCE_BINDING','source_commit':F6,'evidence_commit':E,'evidence_subtree':sub,'prior_independent_review_sha256':sums['review/review-receipt.json'],'prior_independent_verdict':review['verdict'],'all28_immutable_evidence_checksums_verified':True,'focused_tests':62,'top_level_cases':21,'nested_cases':41,'new_regressions':45,'retained_cases':17,'passed':62,'failed':0,'skipped':0,'red_tests':45,'red_failed':45,'red_exit_code':1,'green_exit_code':0,'native_fixture_rows':9,'native_fixture_all_passed':True,'native_classification':native['classification'],'pytest_inventory_delta':0,'language_source_hashes':EXPECTED,'source_bytes_equal_authored_f6':True,'reexecution_by_this_reviewer':False,'immutable_evidence_bindings':sums,'limits':['Existing approved language62 Node cases and root nine-fixture proof reused without rerun.','Prior touch-target14 proof stays preserved as baseline; no current touch-target14 exact asset/test claim is made for this changed language scope.','Cold Knowledge TTFB and native VoiceOver remain unchanged, unwaived, and outside this gate review.']})
