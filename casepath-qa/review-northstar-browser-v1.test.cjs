'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net'),{spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const SOURCE='clm_f69b1747447bc221',TARGET='clm_0e538990cc6ba7ef';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function fixture(){
 const out=process.env.CASEPATH_REVIEW_EVIDENCE_DIR?path.resolve(process.env.CASEPATH_REVIEW_EVIDENCE_DIR):fs.mkdtempSync(path.join(os.tmpdir(),'casepath-northstar-browser-'));
 if(process.env.CASEPATH_REVIEW_EVIDENCE_DIR)fs.mkdirSync(out,{recursive:false});
 const port=await new Promise(resolve=>{const socket=net.createServer();socket.listen(0,'127.0.0.1',()=>{const value=socket.address().port;socket.close(()=>resolve(value));});});
 const python=process.env.CASEPATH_PYTHON||path.join(root,'.runtime/casepath-dev-v2/venv/bin/python');
 const child=spawn(python,[path.join(__dirname,'serve-review-northstar-fixture-v1.py'),'--data-root',path.join(out,'data'),'--port',String(port)],{cwd:root,env:{PATH:process.env.PATH||'/usr/bin:/bin',PYTHONDONTWRITEBYTECODE:'1',CASEPATH_MODEL_MODE:'deterministic_reference',CASEPATH_AGENT_WORK_EXTERNAL_FACTS:'0'},stdio:['ignore','pipe','pipe']});
 let log='';child.stdout.on('data',d=>log+=d);child.stderr.on('data',d=>log+=d);
 const base='http://127.0.0.1:'+port;
 async function close(){
  if(child.exitCode===null){child.kill('SIGTERM');await Promise.race([new Promise(r=>child.once('exit',r)),pause(5000)]);if(child.exitCode===null)child.kill('SIGKILL');}
  fs.writeFileSync(path.join(out,'server.log'),log);
 }
 try{
  for(let attempt=0;attempt<250;attempt++){
   if(child.exitCode!==null)throw Error('Fixture exited: '+log.slice(-3000));
   try{const r=await fetch(base+'/healthz');if(r.ok)return {base,out,close};}catch(_){}
   await pause(100);
  }
  throw Error('Fixture did not become ready: '+log.slice(-3000));
 }catch(error){await close();throw error;}
}
test('source, correction, accepted version and later-case consequence stay connected', {timeout:180000},async()=>{
 const server=await fixture(),browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH||(fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':chromium.executablePath())});
 const context=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block',...(process.env.CASEPATH_REVIEW_RECORD_VIDEO==='1'?{recordVideo:{dir:path.join(server.out,'video'),size:{width:1440,height:900}}}:{})}),page=await context.newPage();
 const errors=[],unexpected=[],writes=[],receipt={scope:'isolated deterministic QA; Test handler is not a human approval',cases:[SOURCE,TARGET],stages:[]};
 page.on('pageerror',e=>errors.push(e.stack||e.message));
 page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push({method:r.method(),path:new URL(r.url()).pathname});if(new URL(r.url()).origin!==server.base&&!r.url().startsWith('blob:')&&!r.url().startsWith('data:'))unexpected.push(r.url());});
 const apiPath=id=>'/api/claim-loops/v1/workspace/claims/'+id;
 const get=async suffix=>{const r=await context.request.get(server.base+suffix);assert.equal(r.status(),200,await r.text());return r.json();};
 const detail=id=>get(apiPath(id)),processView=id=>get(apiPath(id)+'/process');
 const open=async id=>{await page.goto(server.base+'/?journey=review&view=northstar#claim='+id,{waitUntil:'domcontentloaded'});await page.locator('#cpCausalProcess[data-claim-id="'+id+'"]').waitFor({state:'visible'});await page.evaluate(()=>document.fonts.ready);};
 const visible=async selector=>{
  const value=await page.locator(selector).first().evaluate(el=>{
   const samples=[...el.getClientRects()].map(own=>{
    let left=Math.max(0,own.left),top=Math.max(0,own.top),right=Math.min(innerWidth,own.right),bottom=Math.min(innerHeight,own.bottom);
    for(let parent=el.parentElement;parent;parent=parent.parentElement){const style=getComputedStyle(parent);if(style.display==='contents')continue;const r=parent.getBoundingClientRect();if(/auto|scroll|hidden|clip/.test(style.overflowX)){left=Math.max(left,r.left);right=Math.min(right,r.right);}if(/auto|scroll|hidden|clip/.test(style.overflowY)){top=Math.max(top,r.top);bottom=Math.min(bottom,r.bottom);}}
    const hit=right>left&&bottom>top?document.elementFromPoint((left+right)/2,(top+bottom)/2):null;
    return {left,top,right,bottom,exposed:!!hit&&(hit===el||el.contains(hit)),display:getComputedStyle(el).display};
   });
   return samples.find(sample=>sample.exposed)||samples[0]||{exposed:false};
  });
  assert.ok(value.right>value.left&&value.bottom>value.top&&value.exposed&&value.display!=='none',selector+' has exposed pixels in the current viewport: '+JSON.stringify(value));return value;
 };
 const meta=async form=>{await form.locator('[name="actor"]').fill('Test handler');await form.locator('[name="reason"]').fill('QA only: compare complete paired notices before joint resolution; preserve deadline protection.');};
 async function preview(id,submit){
  const before=(await detail(id)).state;
  const [r]=await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith(apiPath(id)+'/process/preview')),submit()]);assert.equal(r.status(),200,await r.text());const value=await r.json();
  await page.locator('#cpProcessImpact').waitFor({state:'visible'});
  assert.deepEqual((await detail(id)).state,before,'preview must not change any authoritative state');
  await visible('[data-review-process-map]');await visible('#cwSourceInspector');await visible('#cpProcessImpact .nr-consequence-heading');
  return value;
 }
 async function apply(id){
  const [r]=await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith(apiPath(id)+'/process/apply')),page.locator('[data-causal-apply]').click()]);assert.equal(r.status(),200,await r.text());const value=await r.json();
  await page.waitForFunction(({id,revision})=>{const e=document.querySelector('#cpCausalProcess');return e?.dataset.claimId===id&&Number(e.dataset.workspaceRevision)>=revision&&!document.querySelector('#cpProcessImpact');},{id,revision:value.process.workspace_revision});
  return value;
 }
 try{
  // A missing presentation module must fail with a concrete recovery action.
  const pattern='**/assets/review-northstar-v1.js?*';
  await page.route(pattern,route=>route.abort());
  await page.goto(server.base+'/?journey=review&view=northstar#claim='+SOURCE);
  await page.locator('#reviewStartupError button').waitFor({state:'visible'});
  await page.unroute(pattern);
  await page.locator('#reviewStartupError button').click();
  await page.locator('#cpCausalProcess').waitFor({state:'visible'});await page.evaluate(()=>document.fonts.ready);
  assert.equal(writes.length,0,'opening the operator canvas does not start six other reviews');
  assert.equal(await page.locator('[data-review-role="builder"]').getAttribute('aria-selected'),'true');
  const labels=await page.evaluate(()=>[...document.querySelectorAll('.nr-role-tabs [aria-controls],[data-claim-pane][aria-labelledby]')].flatMap(e=>['aria-controls','aria-labelledby'].map(a=>e.getAttribute(a)).filter(Boolean).filter(id=>!document.getElementById(id))));
  assert.deepEqual(labels,[],'navigation references real panels and labels');
  const fixtureManifest=JSON.parse(fs.readFileSync(path.join(root,'casepath-api/casepath_api/corpora/synthetic-150/manifest.json'),'utf8'));
  const freshClaim=fixtureManifest.claims.find(row=>![SOURCE,TARGET].includes(row.claim_id));
  assert.ok(freshClaim);const openingWrites=writes.length,freshBefore=await detail(freshClaim.claim_id);
  await page.goto(server.base+'/?journey=review&view=northstar#claim='+freshClaim.claim_id);
  await page.locator('#cpPane-process #cwStart').waitFor({state:'visible'});
  assert.equal(await page.locator('#cwStart').count(),1);assert.ok(await page.locator('#cwStart').isEnabled());
  await visible('#cwStart');await visible('#cwSourceInspector');assert.equal(writes.length,openingWrites);
  assert.deepEqual((await detail(freshClaim.claim_id)).state,freshBefore.state);
  await open(SOURCE);
  const sourceBefore=await detail(SOURCE),sourceGraphBefore=await processView(SOURCE),targetBefore=await detail(TARGET),targetGraphBefore=await processView(TARGET);
  const tenantIndex=sourceBefore.artifacts.findIndex(a=>/tenant/i.test(a.file_name||a.filename||''));
  assert.ok(tenantIndex>=0);
  await page.locator('[data-packet-artifact="'+tenantIndex+'"]').click();
  await page.locator('#cpPreviewPageWrap .cp-preview-page').waitFor({state:'visible'});
  await page.locator('[data-preview-page="next"]').click();
  await page.waitForFunction(()=>document.querySelector('#cpPreviewPageLabel')?.textContent==='Page 2 of 2'&&document.querySelector('#cpPreviewPageWrap')?.getAttribute('aria-busy')==='false');
  const retainedReader=await page.locator('#cwSourceInspector').elementHandle();
  assert.equal(await page.locator('#cwSourceLibrary').getAttribute('open'),'');
  await page.locator('[data-review-role="finder"]').click();await visible('#cpPane-documents');await visible('[data-review-process-map]');await visible('#cwSourceInspector');
  await page.locator('[data-review-role="builder"]').click();
  await page.locator('.nr-edit-decision').click();
  const wording=page.locator('[data-causal-form="node"]');
  await wording.locator('[name="meaning"]').fill('QA wording preview only; keep the current process.');
  await meta(wording);
  const wordingPreview=await preview(SOURCE,()=>wording.locator('button[type="submit"]').click());
  assert.equal(wordingPreview.impact.next_action_changed,false);
  assert.match(await page.locator('#cpProcessImpact .nr-consequence-heading').innerText(),/No process or document requirement changes/);
  await page.locator('[data-causal-cancel]').click();
  await page.locator('[data-causal-add]').click();
  let form=page.locator('[data-causal-form="node"]');
  await form.locator('[name="label"]').fill('Compare both complete notices');
  await form.locator('[name="meaning"]').fill('Review both complete served notices and resolve their differing end dates before preparing a joint resolution. Missing scan pages alone do not establish invalidity.');
  await form.locator('[data-causal-disclosure="edit-condition"] > summary').click();
  await form.locator('[data-expr-kind]').selectOption('flag');
  await form.locator('[data-expr-flag]').selectOption('family_home');
  await form.locator('[data-causal-disclosure="edit-documents"] > summary').click();
  for(const type of ['termination_notice','spouse_notice_copy'])await form.locator('[name="documents"][value="'+type+'"]').check();
  await form.locator('[name="follows"]').selectOption('lt_deadline');await meta(form);
  await form.locator('[name="reason"]').press('ArrowLeft');
  assert.equal(await page.locator('[data-review-role="builder"]').getAttribute('aria-selected'),'true','editing arrow keys do not activate role navigation');
  const addedPreview=await preview(SOURCE,()=>form.locator('button[type="submit"]').click());
  const added=await apply(SOURCE);
  let sourceProcess=await processView(SOURCE),newNode=sourceProcess.graph.nodes.find(n=>n.label==='Compare both complete notices');
  assert.ok(newNode);assert.deepEqual(sourceProcess.graph.conditions,sourceGraphBefore.graph.conditions,'a structural correction preserves the source case facts');
  assert.ok(await retainedReader.evaluate(e=>e.isConnected),'a settled original reader survives the accepted refresh');
  assert.equal(await page.locator('#cpPreviewPageLabel').innerText(),'Page 2 of 2');
  receipt.stages.push({stage:'new-prerequisite',preview:addedPreview.preview_sha256,event:added.event_sha256,node_id:newNode.node_id,impact:addedPreview.impact});

  await page.locator('.nr-process-map [data-causal-node="'+newNode.node_id+'"]').click();
  await page.locator('.cp-node-connections > summary').click();
  await page.locator('[data-causal-connection]').click();
  form=page.locator('[data-causal-form="edge"]');
  await form.locator('[name="target"]').selectOption('lt_resolution');
  await form.locator('[name="relation"]').selectOption('requires');await meta(form);
  const relationPreview=await preview(SOURCE,()=>form.locator('button[type="submit"]').click());
  const relation=await apply(SOURCE);
  sourceProcess=await processView(SOURCE);
  const boundary=sourceProcess.graph.edges.find(e=>e.source_node_id===newNode.node_id&&e.target_node_id==='lt_resolution'&&e.relation==='requires');
  assert.ok(boundary);
  assert.ok(sourceProcess.evaluation.nodes.find(n=>n.node_id==='lt_resolution').blocked_by.includes(newNode.node_id));
  receipt.stages.push({stage:'resolution-dependency',preview:relationPreview.preview_sha256,event:relation.event_sha256,impact:relationPreview.impact});
  await page.locator('.nr-process-map [data-causal-node="'+newNode.node_id+'"]').click();
  await page.locator('[data-causal-action="validate"]').click();
  form=page.locator('[data-causal-confirm]');await meta(form);
  await preview(SOURCE,()=>form.locator('button[type="submit"]').click());await apply(SOURCE);
  await page.locator('.cp-local-context [data-causal-edge="'+boundary.edge_id+'"]').click();
  await page.locator('[data-edge-validate="'+boundary.edge_id+'"]').click();
  form=page.locator('[data-causal-confirm]');await meta(form);
  await preview(SOURCE,()=>form.locator('button[type="submit"]').click());await apply(SOURCE);
  await page.locator('#cpProcessLibrary > summary').click();
  await page.locator('.cp-fragment-create > summary').click();
  form=page.locator('[data-causal-fragment]');
  await form.locator('[name="name"]').fill('Paired-notice consistency review');
  for(const box of await form.locator('[name="nodes"]').all())await box.uncheck();
  await form.locator('[name="nodes"][value="'+newNode.node_id+'"]').check();await meta(form);
  const saveResponse=page.waitForResponse(r=>r.request().method()==='POST'&&r.url().endsWith(apiPath(SOURCE)+'/process/fragments'));
  await form.locator('button[type="submit"]').click();const savedResponse=await saveResponse;
  assert.equal(savedResponse.status(),200,await savedResponse.text());const saved=await savedResponse.json();
  await page.waitForFunction(()=>document.querySelector('.cp-process-status')?.textContent.includes('Saved a reusable process version'));
  sourceProcess=await processView(SOURCE);
  const fragments=Array.isArray(sourceProcess.fragments)?sourceProcess.fragments:sourceProcess.fragments.items;
  const fragment=fragments.find(f=>f.name==='Paired-notice consistency review');
  assert.ok(fragment);assert.equal(fragment.source_claim_id,SOURCE);assert.equal(fragment.version,1);
  assert.ok(fragment.nodes.every(n=>n.completed===false));
  assert.ok(fragment.document_catalog.every(d=>d.held_files.length===0));
  assert.deepEqual((await detail(SOURCE)).state.intake_assessment,sourceBefore.state.intake_assessment);
  assert.deepEqual((await detail(SOURCE)).state.binding,sourceBefore.state.binding);
  receipt.stages.push({stage:'saved-version',event:saved.event_sha256,fragment_sha256:fragment.fragment_sha256,version:fragment.version,actor:fragment.actor});
  await page.screenshot({path:path.join(server.out,'source-review.png')});
  await open(TARGET);
  await page.locator('#cpProcessLibrary > summary').click();
  await page.locator('[data-causal-fragment-apply="'+fragment.fragment_sha256+'"]').click();
  form=page.locator('[data-causal-confirm]');await meta(form);
  const reusePreview=await preview(TARGET,()=>form.locator('button[type="submit"]').click());
  const resolutionChange=reusePreview.impact.node_changes.find(n=>n.node_id==='lt_resolution');
  assert.equal(resolutionChange.before.execution_state,'blocked');assert.equal(resolutionChange.after.execution_state,'blocked');
  assert.deepEqual(resolutionChange.before.blocked_by,['lt_evidence']);assert.deepEqual(resolutionChange.after.blocked_by,[newNode.node_id]);
  assert.equal(reusePreview.impact.next_action_changed,false);assert.deepEqual(reusePreview.impact.changed_requirement_document_types,[]);
  for(const type of ['termination_notice','spouse_notice_copy']){
   const change=reusePreview.impact.document_changes.find(d=>d.document_type===type);
   assert.ok(change);assert.ok(!change.before.required_at_node_ids.includes(newNode.node_id));assert.ok(change.after.required_at_node_ids.includes(newNode.node_id));
   assert.equal(change.before.route_state,change.after.route_state);assert.equal(change.before.request,change.after.request);assert.deepEqual(change.before.held_files,change.after.held_files);
  }
  assert.match(await page.locator('#cpProcessImpact .nr-consequence').innerText(),/Compare both complete notices/);
  await page.screenshot({path:path.join(server.out,'later-case-preview.png')});
  const reused=await apply(TARGET),targetAfter=await detail(TARGET),targetProcess=await processView(TARGET);
  const pin=targetProcess.graph.fragment_instances.find(f=>f.fragment_sha256===fragment.fragment_sha256);
  assert.ok(pin);assert.equal(pin.version,1);assert.equal(pin.source_claim_id,SOURCE);
  assert.deepEqual(targetAfter.state.intake_assessment,targetBefore.state.intake_assessment);
  assert.deepEqual(targetAfter.state.binding,targetBefore.state.binding);
  assert.deepEqual(targetProcess.graph.conditions,targetGraphBefore.graph.conditions);
  for(const before of targetGraphBefore.graph.document_catalog){
   assert.deepEqual(targetProcess.graph.document_catalog.find(d=>d.document_type===before.document_type).held_files,before.held_files,'target evidence reviews stay local: '+before.document_type);
  }
  assert.ok(targetProcess.evaluation.nodes.find(n=>n.node_id==='lt_resolution').blocked_by.includes(newNode.node_id));
  assert.equal(targetProcess.graph.nodes.find(n=>n.node_id===newNode.node_id).completed,false);
  assert.equal(targetProcess.graph.edges.find(e=>e.edge_id===boundary.edge_id).validation.status,'unvalidated','the receiving claim must review its imported dependency');
  assert.equal(targetProcess.claim_decision_authorized,false);
  for(const edge of targetGraphBefore.graph.edges)assert.deepEqual(targetProcess.graph.edges.find(e=>e.edge_id===edge.edge_id),edge,'all earlier process connections remain unchanged');
  assert.equal(await page.locator('[data-review-role="result"]').getAttribute('aria-selected'),'true');
  await page.locator('[data-review-role="result"]').click();
  await page.locator('[data-review-current-dependency]').scrollIntoViewIfNeeded();
  await visible('[data-review-process-map]');await visible('#cwSourceInspector');await visible('[data-review-current-dependency]');
  assert.match(await page.locator('[data-review-current-dependency]').innerText(),/Prepare challenge, extension or settlement now also requires “Compare both complete notices”/);
  assert.match(await page.locator('[data-review-preserved-connection]').innerText(),/Collect type-specific evidence/);
  assert.match(await page.locator('[data-review-reuse="'+fragment.fragment_sha256+'"]').innerText(),/This case keeps its own facts/);
  await page.screenshot({path:path.join(server.out,'later-case-reuse.png')});
  receipt.stages.push({stage:'later-case-application',preview:reusePreview.preview_sha256,event:reused.event_sha256,impact:reusePreview.impact,pin,workspace_revision:targetProcess.workspace_revision,target_facts_preserved:true,target_source_bindings_preserved:true});
  await page.reload();await page.locator('#cpCausalProcess[data-claim-id="'+TARGET+'"]').waitFor({state:'visible'});
  assert.ok((await processView(TARGET)).graph.fragment_instances.some(f=>f.fragment_sha256===fragment.fragment_sha256),'reload preserves the exact pin');
  await page.locator('[data-review-role="result"][aria-selected="true"]').waitFor({state:'visible'});await visible('[data-review-current-dependency]');
  // Publishing a new version must not silently advance the receiving case.
  sourceProcess=await processView(SOURCE);
  const newerResponse=await context.request.post(server.base+apiPath(SOURCE)+'/process/fragments',{headers:{'X-CasePath-Idempotency-Key':'northstar.qa.fragment.version2'},data:{name:fragment.name,node_ids:[newNode.node_id],fragment_id:fragment.fragment_id,actor:'Test handler',reason:'QA only: publish the next reviewed version without changing the target pin.',expected_revision:sourceProcess.workspace_revision,expected_state_sha256:sourceProcess.workspace_state_sha256}});
  receipt.api_writes=[{method:'POST',path:apiPath(SOURCE)+'/process/fragments',purpose:'QA version 2 pin check',status:newerResponse.status()}];
  assert.equal(newerResponse.status(),200,await newerResponse.text());
  assert.deepEqual((await processView(TARGET)).graph.fragment_instances,targetProcess.graph.fragment_instances);
  await page.reload();await page.locator('[data-review-reuse="'+fragment.fragment_sha256+'"]').waitFor({state:'attached'});
  assert.match(await page.locator('[data-review-reuse="'+fragment.fragment_sha256+'"]').innerText(),/Exact saved version 1/);
  assert.equal(await page.locator('[data-review-role="result"]').getAttribute('aria-selected'),'true');await visible('[data-review-current-dependency]');
  await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});
  await page.locator('[data-review-role="finder"]').click();await visible('#cpPane-documents');
  await page.locator('[data-review-role="checker"]').click();await visible('#cwSourceInspector');
  const mobile=await page.evaluate(()=>({pageOverflow:document.documentElement.scrollWidth-innerWidth,panelOverflow:document.querySelector('#cwDetailPanel').scrollWidth-document.querySelector('#cwDetailPanel').clientWidth,reduced:matchMedia('(prefers-reduced-motion: reduce)').matches,animations:document.getAnimations().filter(a=>a.playState==='running'||a.pending).length}));
  assert.equal(mobile.pageOverflow,0);assert.equal(mobile.panelOverflow,0);assert.equal(mobile.reduced,true);assert.equal(mobile.animations,0);
  await page.screenshot({path:path.join(server.out,'mobile-review.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);
  receipt.status='passed';receipt.browser_errors=errors;receipt.unexpected_destinations=unexpected;receipt.browser_writes=writes;receipt.mobile=mobile;
  fs.writeFileSync(path.join(server.out,'receipt.json'),JSON.stringify(receipt,null,2));
  console.log('North-star review evidence: '+server.out);
 }catch(error){
  receipt.status='failed';receipt.error=error.message;receipt.browser_errors=errors;receipt.browser_writes=writes;
  fs.writeFileSync(path.join(server.out,'receipt.json'),JSON.stringify(receipt,null,2));
  fs.writeFileSync(path.join(server.out,'failure-body.txt'),(await page.locator('body').innerText()).slice(0,24000));
  await page.screenshot({path:path.join(server.out,'failure.png')});throw error;
 }finally{await context.close();const video=page.video();if(video){const videoPath=await video.path();fs.renameSync(videoPath,path.join(server.out,'review-walkthrough.webm'));}await browser.close();await server.close();}
});
