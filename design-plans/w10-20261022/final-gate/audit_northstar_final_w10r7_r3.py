from pathlib import Path
import ast,datetime,hashlib,json,re,subprocess,math
r=Path.cwd();rt=r/'.runtime';sha=(rt/'northstar-frozen-sha').read_text().strip()
read=lambda p:json.loads(Path(p).read_text())
hashfile=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==sha
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
binding=read(rt/'northstar-final-source-binding.json');capture_sha=binding['captureSourceCommit'];assert binding['finalSourceCommit']==sha and binding['productBytesUnchanged'] is True
assert not subprocess.check_output(['git','diff',capture_sha,sha,'--name-only','--','casepath/assets','casepath/index.html','casepath-api','casepath-qa','bin/casepath','examples'],text=True).strip()
assert set(subprocess.check_output(['git','diff',capture_sha,sha,'--name-only','--','casepath'],text=True).splitlines()) <= {'casepath/source-manifest.json'}
sequence=read(rt/'final-sequence-w10r7-r2.json');assert sequence['sourceCommit']==sha and sequence['status']=='failed'
assert [x['name'] for x in sequence['stages']]==['strict','walk']
assert sequence['stages'][0]['exitCode']==0 and sequence['stages'][1]['exitCode']==1
strict=sequence['stages'][0];text=Path(strict['log']).read_text();assert strict['logSha256']==hashfile(strict['log'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=strict['cwd'],text=True).strip()==sha
assert not subprocess.check_output(['git','status','--porcelain'],cwd=strict['cwd'],text=True).strip()
admission=read(rt/'final-w10r7-r2-admission.json');assert admission['sourceCommit']==sha and admission['prepareExit']==0 and admission['sourceUnchanged'] and admission['workingTreeClean']
assert hashfile(Path(strict['cwd'])/'casepath-api/artifacts/artifact-manifest.json')==admission['artifactManifestSha256']
counts=re.findall(r'(\d+) passed, (\d+) skipped',text);assert counts and tuple(map(int,counts[-1]))==(2866,10)
skips=[x for x in text.splitlines() if x.startswith('SKIPPED')];assert len(skips)==10 and all('test_document_lifecycle_shadow_v' in x for x in skips)
assert strict['environment']['CASEPATH_REQUIRE_FRONTEND_SUITES']=='1'
attestations=[]
for line in text.splitlines():
 try:
  d=json.loads(line)
  if isinstance(d,dict) and d.get('contract')=='casepath.isolated-backend-static-test/1.0.0':attestations.append(d)
 except json.JSONDecodeError:pass
assert len(attestations)==1;isolation=attestations[0]
assert isolation['model_mode']=='deterministic_reference' and not isolation['provider_credential_names_present'] and not isolation['persistent_product_database_used'] and not isolation['persistent_artifact_registry_used']
front=ast.parse((r/'casepath-api/tests/test_frontend_node_suites_v1.py').read_text())
suites=next(ast.literal_eval(n.value) for n in front.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SUITES' for t in n.targets));assert len(suites)==11
assert not subprocess.check_output(['git','diff','5ecbb5b767e4c410f99cd7ae29d75d72360a122c',sha,'--name-only','--','casepath-api','bin/casepath'],text=True).strip()
protected_path='casepath-api/tests/test_public_hosted_read_only_v1.py'
protected_bytes=subprocess.check_output(['git','show','5ecbb5b767e4c410f99cd7ae29d75d72360a122c:'+protected_path])
assert protected_bytes==(r/protected_path).read_bytes()
cold_path='casepath-qa/autonomous-presentation-browser-v1.test.cjs'
cold_name="test('a slow cold read keeps the north-star frame on landing and on opening a recorded case'"
cold_base=subprocess.check_output(['git','show','5ecbb5b767e4c410f99cd7ae29d75d72360a122c:'+cold_path],text=True)
cold_now=(r/cold_path).read_text();assert cold_base[cold_base.index(cold_name):]==cold_now[cold_now.index(cold_name):]
protected_evidence={'hostedReadOnlyFile':protected_path,'hostedReadOnlySha256':hashlib.sha256(protected_bytes).hexdigest(),'coldLandingFile':cold_path,'coldLandingTestSha256':hashlib.sha256(cold_now[cold_now.index(cold_name):].encode()).hexdigest(),'unchangedFrom':'5ecbb5b767e4c410f99cd7ae29d75d72360a122c'}
walk=read(rt/'northstar-final-walk-w10r7-r3/walk.json');assert walk['status']=='passed' and walk['review_commit']==sha
assert (walk['cases'],walk['errors'],walk['writes'],walk['overlaps'])==(9,0,0,0)
assert list(walk['scripts'])==['process','memory','acceptance','reduced','motion','live-layout','presentation']
for name,stage in walk['scripts'].items():
 assert stage['exit_code']==0
 p=rt/f'northstar-final-walk-w10r7-r3/{name}-receipt.json';v=read(p)
 assert hashfile(p)==walk['receipt_sha256'][p.name]
 assert v['passed'] and not v['errors'] and not v['writes'] and not v.get('overrides')
 assert v['deployment']['source_commit']==sha
 assert len(v['cleanup'])==3 and all(x.get('closed') is True or x.get('status')=='closed' for x in v['cleanup'])
adapter=read(rt/'northstar-final-walk-w10r7-r3/origin-adapter.json')
original=(r/'design-plans/w8-20261021-mac-r1/verify-acceptance.mjs').read_text()
assert adapter['sourceSha256']==hashlib.sha256(original.encode()).hexdigest()
assert adapter['from']=="base='http://127.0.0.1:4180'" and adapter['to']=='base=proofOrigin'
assert original.count(adapter['from'])==1
assert adapter['executedSha256']==hashlib.sha256(original.replace(adapter['from'],adapter['to']).encode()).hexdigest()
assert adapter['origin']=='http://127.0.0.1:4192' and adapter['assertionsUnchanged'] is True
assert walk['origin_adapter']['sha256']==hashfile(rt/'w10-walk-origin-adapter.mjs')
previous=datetime.datetime.fromisoformat(walk['started_at'])
for name,stage in walk['scripts'].items():
 assert datetime.datetime.fromisoformat(stage['started_at'])>=previous
 previous=datetime.datetime.fromisoformat(stage['finished_at'])
 assert hashfile(rt/f'northstar-final-walk-w10r7-r3/{name}.log')==stage['log_sha256']
assert datetime.datetime.fromisoformat(walk['started_at'])>datetime.datetime.fromisoformat(sequence['finishedAt'])
assert datetime.datetime.fromisoformat(sequence['stages'][1]['startedAt'])>=datetime.datetime.fromisoformat(strict['finishedAt'])
fseq=read(rt/'film-sequence-w10r7.json');assert fseq['status']=='passed' and fseq['sourceCommit']==capture_sha
filmroot=Path(fseq['out']);film=read(filmroot/'film-receipt.json');repeat=read(filmroot/'repeat-receipt.json');live=read(filmroot/'live-proof/live-film-receipt.json')
for v in [film,repeat,live]:
 assert v['passed'] and v['sourceCommit']==capture_sha and not v['errors'] and not v['writes'] and not v['missingReads']
 assert all(x['status']=='closed' for x in v['cleanup'])
 assert v['deployment']['source_commit']==capture_sha
 for name,h in v.get('assets',film['assets']).items(): assert hashfile(r/'casepath/assets'/name)==h
expected_frames=math.ceil(film['duration']*60)
assert film['frameCount']==repeat['replayedFrames']==expected_frames and 0<film['duration']<90 and film['fps']==60
assert film['droppedIndices']==film['duplicateIndices']==0
assert film['checksums']==repeat['checksums'] and repeat['verifiedSamples']==len(film['checksums'])
assert [x['n'] for x in film['checksums']]==list(range(0,expected_frames,60))
assert all(abs(x['time']-x['n']*1000/60)<1e-8 for x in film['checksums'])
assert len(live['comparisons'])==6 and live['live']['maxNativeAnimations']==0 and live['live']['observedFrames']>0
assert all(x['byteIdentical'] and x['meanPixelDifference']==0 and x['maxChannelDifference']==0 for x in live['comparisons'])
assert len(film['contactFrames'])==24
assert [x['n'] for x in film['contactFrames']]==[math.floor(i*(expected_frames-1)/23+0.5) for i in range(24)]
assert hashfile(filmroot/'frame-index.jsonl')==film['frameIndexSha256']
for encode in film['encodes']:
 assert hashfile(filmroot/encode['name'])==encode['sha256']
 assert int(encode['ffprobe']['streams'][0]['nb_frames'])==expected_frames and encode['ffprobe']['streams'][0]['avg_frame_rate']=='60/1'
assert {(e['width'],e['height']) for e in film['encodes']}=={(2880,1800),(1920,1200),(1920,1080)}
cold=read(rt/'cold-viewer-w10r7.json');assert cold['assessment']['passed'] is True and cold['assessment']['learningEffectRecognized'] is True and cold['sourceCommit']==capture_sha
assert cold['filmSha256']==hashfile(filmroot/'casepath-executive-1920x1200.mp4')
assert len(cold['frames'])==24 and cold['forkTurns']=='none' and cold['response']
assert [x['name'] for x in cold['frames']]==[f'frame-{n:02d}.png' for n in range(1,25)]
for frame in cold['frames']:assert hashfile(filmroot/'contact'/frame['name'])==frame['sha256']
fidelity=read(rt/'northstar-fidelity-w10r7/fidelity.json');assert fidelity['sourceCommit']==capture_sha and fidelity['visualReview']['passed'] and not fidelity['visualReview']['pending']
assert len(fidelity['comparisons'])==3
for x in fidelity['comparisons']:assert hashfile(x['frame'])==x['frame_sha256']
result={'sourceCommit':sha,'captureSourceCommit':capture_sha,'sourceBinding':binding,'verifiedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':True,'strict':{'counts':{'passed':2866,'skipped':10},'knownSkips':skips,'frontendSuites':[x[0] for x in suites],'protectedMacTestUnchanged':True,'protectedTestEvidence':protected_evidence,'isolation':isolation,'logSha256':hashfile(strict['log'])},'walk':{'originAdapter':adapter,'strictReceipt':'.runtime/final-sequence-w10r7-r2.json','cleanWalkReceipt':'.runtime/northstar-final-walk-w10r7-r3/walk.json','scripts':list(walk['scripts']),'cases':9,'errors':0,'writes':0,'overlapChecks':walk['overlap_checks'],'overlaps':0},'film':{'duration':film['duration'],'frames':film['frameCount'],'denseReplayFrames':repeat['replayedFrames'],'denseSamples':repeat['verifiedSamples'],'exactLiveComparisons':6,'encodes':[{k:e[k] for k in ['name','width','height','bytes','sha256']} for e in film['encodes']],'frameIndexSha256':film['frameIndexSha256'],'livePlayback':live['live']},'fidelityMeanDifferencePct':[x['mean_difference_pct'] for x in fidelity['comparisons']],'coldViewerPassed':True,'limits':['Deterministic fictional histories; not real-case accuracy or deployment.','No human-reviewed memory edit exists.','Mobile retains the existing claim view.','No remaining original-nine allowance; no spending authorized.']}
(rt/'northstar-final-audit-w10r7-r3.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
