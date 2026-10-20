'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {gunzipSync} = require('node:zlib');
const {createHash,webcrypto} = require('node:crypto');
const {chromium} = require('playwright');
if (!globalThis.crypto) globalThis.crypto = webcrypto;
const ui = require('../casepath/assets/autonomous-workspace-v1.js');
const language = require('../casepath/assets/autonomous-language-v1.js');
const root = path.resolve(__dirname,'..');
const base = '/api/claim-loops/v1/autonomous';
const captured = JSON.parse(gunzipSync(fs.readFileSync(path.join(root,'design/evidence-path/recorded-fixtures.json.gz'))));
const responses = captured.responses;
const claims = responses[`${base}/claims`].claims;
const envelope = id => responses[`${base}/claims/${id}`];
const saved = id => envelope(id).state;
const robin = 'auto_265cf377bb7485dce74573c8';
const sha = value => createHash('sha256').update(value).digest('hex');
const escaped = value => String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const sorted = values => [...values].sort();

// These are recorded fictional product states, never evaluator targets or new inference.
test('all nine recorded claims retain their complete actual DAG, edge applicability and unprocessed states',async t=>{
 assert.equal(claims.length,9);
 assert.equal(claims.filter(claim=>saved(claim.claim_id).graph.nodes.length===1).length,3);
 for (const claim of claims) await t.test(claim.title,()=>{
  const data=envelope(claim.claim_id),state=saved(claim.claim_id),before=JSON.stringify(data);
  assert.equal(ui.readState(data,claim.claim_id).state,state);
  const batch=responses[`${base}/claims/${claim.claim_id}/events?after=0`];
  const accepted=ui.acceptEvents(null,batch,state);
  assert.equal(accepted.ready,true);assert.equal(accepted.cursor,state.revision);assert.deepEqual(accepted.animate,[]);
  const layout=ui.layoutGraph(state.graph),html=ui.graphMarkup(state,ui.preferredNode(state),data.projection);
  assert.deepEqual(sorted([...html.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1])),sorted(state.graph.nodes.map(node=>node.node_id)));
  const renderedEdges=[...html.matchAll(/<path[^>]*data-au-edge="([^"]+)"[^>]*data-state="([^"]+)"/g)];
  assert.deepEqual(sorted(renderedEdges.map(match=>match[1])),sorted(state.graph.edges.map(edge=>edge.edge_id)));
  for(const edge of state.graph.edges){
   const evaluation=state.evaluation.edges.find(row=>row.edge_id===edge.edge_id);
   assert.equal(renderedEdges.find(match=>match[1]===edge.edge_id)[2],evaluation.activation || evaluation.condition_verdict || 'unresolved');
   assert.ok(layout.parents.get(edge.target_node_id).includes(edge.source_node_id));
   assert.ok(layout.children.get(edge.source_node_id).includes(edge.target_node_id));
  }
  for(const node of state.graph.nodes) assert.ok(html.includes(`<strong class="au-node-title">${escaped(language.stepLabel(node))}</strong>`),`complete display label ${node.node_id}`);
  if(state.graph.nodes.length===1){
   assert.equal(state.graph.nodes[0].node_id,'investigate_packet');assert.equal(state.graph.edges.length,0);assert.equal(state.status,'deferred');
   assert.deepEqual([...html.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1]),['investigate_packet']);
   assert.doesNotMatch(html,/data-au-node="lt_/);
  }
  assert.equal(JSON.stringify(data),before,'rendering must leave saved authority unchanged');
 });
});

test('an excluded incoming route remains excluded when its shared target still applies',()=>{
 const state=saved(robin),edge=state.graph.edges.find(row=>row.edge_id==='lt_e06');
 assert.equal(state.evaluation.edges.find(row=>row.edge_id===edge.edge_id).activation,'false');
 assert.equal(state.evaluation.nodes.find(row=>row.node_id===edge.target_node_id).activation,'true');
 const html=ui.graphMarkup(state,'lt_abuse');
 assert.match(html,/<path[^>]*data-au-edge="lt_e06"[^>]*data-state="false"/);
 assert.match(html,/<path[^>]*data-au-edge="lt_e08"[^>]*data-state="true"/);
});

test('every recorded source and all 73 cited spans verify against original and extracted identities',async()=>{
 let sourceCount=0,spanCount=0;
 for(const claim of claims){
  const state=saved(claim.claim_id);
  for(const descriptor of state.source_descriptors){
   const source=responses[`${base}/sources/${state.claim_id}/${descriptor.artifact_id}/text`];
   const checked=await ui.checkedSource(state,descriptor,source);
   assert.equal(checked.source.text_sha256,sha(checked.source.text));sourceCount++;
  }
  for(const fact of state.facts) for(const citation of fact.citations || []){
   const descriptor=state.source_descriptors.find(row=>row.artifact_id===citation.artifact_id);
   const source=responses[`${base}/sources/${state.claim_id}/${citation.artifact_id}/text`];
   const checked=await ui.checkedSource(state,descriptor,source,citation);
   assert.equal(checked.span.quote,citation.quote);assert.equal(Array.from(checked.span.before).length,citation.start_char);spanCount++;
  }
 }
 assert.equal(sourceCount,23);assert.equal(spanCount,73);
});

test('family-home applicability does not establish separate spouse service or advance its requirement',()=>{
 const state=saved(robin),before=JSON.stringify(state),relationship=ui.evidenceRelationships(state,'lt_family',{fact:'condition:family_home',document:'spouse_notice_copy'});
 assert.equal(relationship.fact.status,'true');assert.equal(relationship.fact.citations.length,1);
 assert.equal(relationship.evaluation.execution_state,'blocked');assert.deepEqual(relationship.evaluation.blocked_by,['lt_type']);
 assert.equal(relationship.document.route_state,'needed_later');assert.equal(relationship.document.review_state,'missing');
 assert.equal(state.facts.find(fact=>fact.fact_id==='fact:spouse_notice_copy').status,'unresolved');
 assert.deepEqual(state.facts.find(fact=>fact.fact_id==='fact:spouse_notice_copy').citations,[]);
 const html=ui.evidencePathMarkup(state,'lt_family',envelope(robin).projection,{fact:'condition:family_home',document:'spouse_notice_copy',trace:true});
 assert.match(html,/data-au-document="spouse_notice_copy"[^>]*data-route="needed_later"/);
 assert.match(html,/Needed after its step is reached\./);assert.match(html,/Requires[\s\S]*Check the type of termination/);
 assert.ok(html.includes(`<q>${escaped(relationship.fact.citations[0].quote)}</q>`));
 assert.ok(html.includes(escaped(relationship.fact.summary)),'the reading column retains the actual saved condition assessment');
 assert.doesNotMatch(html,/data-au-inspect="(?!step")/,'the reading view presents its case evidence without raw record controls');assert.match(html,/data-au-inspect="step" data-au-record-id="lt_family">Details</);
 const history=ui.workMarkup(state,envelope(robin).projection,'lt_family',[],'activity');
 assert.match(history,/data-au-inspect="claim" data-au-record-id="">Case details</,'the complete saved claim remains accessible through History');
 assert.doesNotMatch(html,/spouse_notice_copy"[^>]*data-route="needed_now"|Spouse service established|Separate spouse service completed/);
 assert.equal(JSON.stringify(state),before);
});

test('shared document timing preserves its process-wide route without declaring a blocked selected step executable',()=>{
 const state=structuredClone(saved(robin)),document=state.evaluation.documents.find(row=>row.document_type==='notice_period_evidence');
 document.route_state='needed_now';document.required_at_node_ids=['lt_deadline','lt_family'];document.active_node_ids=['lt_deadline','lt_family'];
 state.obligations.push({obligation_id:'isolated:shared-notice-period',node_id:'lt_family',decision_node_id:'lt_family',document_type:document.document_type,label:document.label,required_fact_ids:['fact:notice_period_evidence']});
 const before=JSON.stringify(state),html=ui.evidencePathMarkup(state,'lt_family',{}, {document:'notice_period_evidence',fact:'fact:notice_period_evidence'});
 assert.match(html,/data-au-document="notice_period_evidence"[^>]*data-route="needed_now"/);
 assert.match(html,/Listed as needed now\./);assert.match(html,/class="au-step-status">Waiting for prerequisites/);
 assert.equal(state.evaluation.nodes.find(node=>node.node_id==='lt_family').execution_state,'blocked');
 assert.match(html,/Requires[\s\S]*Check the type of termination/);
 assert.doesNotMatch(html,/Needed at the current step|Selected step ready|This step is executable/);
 assert.equal(JSON.stringify(state),before);
});

let browser;
test.before(async()=>{
 const executablePath=process.env.PLAYWRIGHT_EXECUTABLE_PATH || (fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
 browser=await chromium.launch({headless:true,...(executablePath ? {executablePath} : {}),args:['--no-sandbox']});
});
test.after(async()=>{await browser?.close();});

// A real browser exercises the production controller with an entirely local response seam.
// It does not contact the capture origin, a provider, or any actual API.
async function fixturePage(t,{width=1440,reducedMotion='no-preference'}={}){
 const context=await browser.newContext({viewport:{width,height:1000},reducedMotion,serviceWorkers:'block'});
 const page=await context.newPage(),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>route.request().isNavigationRequest() ? route.fulfill({status:200,contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><main id="workspace"></main></body></html>'}) : route.abort('blockedbyclient'));
 await page.goto('http://localhost:41999/');
 await page.addStyleTag({path:path.join(root,'casepath/assets/autonomous-workspace-v1.css')});
 await page.addScriptTag({path:path.join(root,'casepath/assets/autonomous-language-v1.js')});
 await page.addScriptTag({path:path.join(root,'casepath/assets/autonomous-workspace-v1.js')});
 await page.evaluate(({responses,base})=>{
  responses[`${base}/claims`].claims=responses[`${base}/claims`].claims.map(row=>({...row,origin:'native_intake'}));
  history.replaceState(null,'','#autonomous/cases?scope=added');
  window.__responses=responses;window.__base=base;window.__calls=[];window.__animations=[];window.__throwWrites=false;
  const animate=Element.prototype.animate;
  Element.prototype.animate=function(...args){window.__animations.push({node:this.dataset.auNode,edge:this.dataset.auEdge,fact:this.dataset.auFact,document:this.dataset.auDocument});return animate.apply(this,args);};
  const fetch=async(url,init={})=>{
   window.__calls.push({url,method:init.method || 'GET',body:init.body,headers:init.headers});
   if(init.method && init.method!=='GET'){
    if(window.__throwWrites) throw new Error('Isolated fixture response was not confirmed');
    return {ok:false,status:405,json:async()=>({detail:'This fixture only permits saved GET responses.'})};
   }
   let data=window.__responses[url];
   if(!data && url.includes('/events?')){
    const parsed=new URL(url,location.origin),id=parsed.pathname.split('/').at(-2),full=window.__responses[`${base}/claims/${id}/events?after=0`],after=Number(parsed.searchParams.get('after'));
    if(full)data={...full,events:full.events.filter(event=>event.seq>after)};
   }
   if(!data) return {ok:false,status:404,json:async()=>({detail:'No recorded response exists for this fixture read.'})};
   return {ok:true,status:200,json:async()=>structuredClone(data)};
  };
  window.__controller=window.CasePathAutonomous.mount(document.querySelector('#workspace'),{fetch});
 },{responses,base});
 await page.waitForSelector('[data-au-claim-row]');
 t.after(async()=>{await noWrites(page);await page.evaluate(()=>window.__controller?.destroy());assert.deepEqual(errors,[],'production controller page errors');await context.close();});
 return page;
}
async function open(page,id){await page.evaluate(id=>window.__controller.openClaim(id),id);await page.waitForSelector('[data-au-claim-title]');}
async function advance(page,id,changes={}){
 await page.evaluate(({id,changes})=>{
  const data=window.__responses[`${window.__base}/claims/${id}`],state=data.state,batch=window.__responses[`${window.__base}/claims/${id}/events?after=0`];
  Object.assign(state,changes);state.revision++;state.state_sha256='f'.repeat(64);
  if(data.projection){data.projection.claim_id=state.claim_id;data.projection.revision=state.revision;data.projection.state_sha256=state.state_sha256;}
  batch.current_revision=state.revision;batch.current_state_sha256=state.state_sha256;
  batch.events.push({seq:state.revision,claim_id:id,kind:'work.phase',revision:state.revision,state_sha256:state.state_sha256,payload:{summary:'Isolated saved revision'}});
 },{id,changes});
}
async function noWrites(page){assert.deepEqual(await page.evaluate(()=>window.__calls.filter(call=>call.method!=='GET')),[]);}
async function recordData(page){return JSON.parse(await page.locator('.au-record-dialog[open] pre').textContent());}
async function closeRecord(page){
 await page.evaluate(()=>{window.__recordClosed=new Promise(resolve=>document.querySelector('.au-record-dialog').addEventListener('close',resolve,{once:true}));});
 await page.locator('.au-record-dialog [data-au-close-record]').click();await page.locator('.au-record-dialog[open]').waitFor({state:'detached'});
 await page.evaluate(()=>window.__recordClosed);
}
async function escapeSource(page){
 await page.evaluate(()=>{window.__sourceClosed=new Promise(resolve=>document.querySelector('.au-source-dialog').addEventListener('close',resolve,{once:true}));});
 await page.keyboard.press('Escape');await page.locator('.au-source-dialog[open]').waitFor({state:'detached'});
 await page.evaluate(()=>window.__sourceClosed);
}
async function openFullProcess(page){
 const control=page.locator('[data-au-expand-process]');
 if(await control.getAttribute('aria-expanded')!=='true') await control.click();
 assert.equal(await control.getAttribute('aria-expanded'),'true');
 await page.waitForFunction(()=>[...document.querySelectorAll('[data-au-edge]')].every(edge=>edge.getAttribute('d') && !/NaN|Infinity/.test(edge.getAttribute('d'))));
}
async function caseHistoryRecord(page){
 const previous=await page.locator('[data-au-panel]').getAttribute('data-au-panel');
 const pins=await page.evaluate(()=>Object.fromEntries([...new URLSearchParams(location.hash.split('?')[1] || '')].filter(([key])=>['node','fact','document','obligation'].includes(key))));
 const history=page.locator('.au-work-controls [data-au-detail="activity"]');
 assert.equal(await page.locator('[data-au-detail="activity"]').count(),1,'each case has one History access point');
 assert.equal(await history.textContent(),'History');assert.equal(await page.locator('[data-au-refresh-claim]').count(),0);
 await history.click();
 const trigger=page.locator('[data-au-panel="activity"] [data-au-inspect="claim"]');
 assert.equal(await trigger.textContent(),'Case details');await trigger.click();
 assert.equal(await page.locator('.au-record-dialog[open] pre').count(),1);
 const record=await recordData(page);await closeRecord(page);
 if(previous!=='activity') await page.locator(`[data-au-detail="${previous}"]`).click();
 const returnedPins=await page.evaluate(()=>Object.fromEntries([...new URLSearchParams(location.hash.split('?')[1] || '')].filter(([key])=>['node','fact','document','obligation'].includes(key))));
 for(const [key,value] of Object.entries(pins)) assert.equal(returnedPins[key],value,`History preserves the explicit ${key} route pin`);
 return record;
}
async function knowledgeHistoryRecord(page){
 const trigger=page.locator('.au-quiet-knowledge > .au-work-head [data-au-inspect="knowledge-index"]');
 assert.equal(await trigger.textContent(),'History');assert.equal(await page.locator('.au-quiet-knowledge [data-au-inspect]').count(),1);
 await trigger.click();const record=await recordData(page);await closeRecord(page);return record;
}

test('zero recorded active gaps still expose held requirements, questions and the exact saved draft',async t=>{
 const id='auto_7373bbf206ab25bacf71b82e',state=saved(id),before=JSON.stringify(state);
 assert.deepEqual(state.outcome.missing_evidence,[]);
 assert.equal(state.evaluation.documents.filter(doc=>doc.route_state==='held_behind_question').length,11);
 const page=await fixturePage(t);await open(page,id);
 assert.equal(await page.locator('[data-au-panel]').count(),1,'only the current case view is mounted');
 await page.locator('[data-au-detail="activity"]').click();
 await page.locator('[data-au-inspect="outcome"]').click();
 assert.deepEqual(await recordData(page),{outcome:state.outcome,deferral:state.deferral},'the saved outcome and unsent request remain exactly inspectable');
 assert.equal((await recordData(page)).outcome.request_draft.body,state.outcome.request_draft.body);
 assert.equal((await recordData(page)).outcome.request_draft.status,'prepared_not_sent');
 assert.equal(await page.locator('.au-source-dialog[open]').count(),0);
 await closeRecord(page);
 await page.locator('[data-au-detail="documents"]').click();
 assert.equal(await page.locator('[data-au-panel="documents"]').isVisible(),true);
 const held=state.evaluation.documents.filter(doc=>doc.route_state==='held_behind_question');
 assert.deepEqual(sorted(await page.locator('[data-au-panel="documents"] [data-au-document]').evaluateAll(nodes=>nodes.filter(node=>node.dataset.status==='held_behind_question').map(node=>node.dataset.auDocument))),sorted(held.map(doc=>doc.document_type)));
 assert.deepEqual(await page.locator('[data-au-panel="documents"] [data-status="held_behind_question"] .au-document-state').allTextContents(),held.map(()=>'May be needed.'));
 const node=state.evaluation.nodes.find(node=>node.activation==='unresolved' && node.condition_flags.includes('termination_received')).node_id;
 await page.locator('[data-au-detail="step"]').click();await page.locator(`[data-au-node="${node}"]`).click();
 assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),node);
 assert.equal(await page.locator('[data-au-panel="step"]').isVisible(),true);
 assert.match(await page.locator('.au-reading-decision').innerText(),/Not established/);
 assert.equal(await page.locator(`[data-au-node="${node}"]`).getAttribute('data-activation'),'unresolved');
 const record=await caseHistoryRecord(page);assert.deepEqual(record,{state,projection:envelope(id).projection});
 assert.deepEqual(record.state.evaluation.documents.filter(doc=>doc.route_state==='held_behind_question'),held,'concise document labels retain every exact held requirement and its saved review state');
 const decision=record.state.evaluation.nodes.find(row=>row.node_id===node);
 assert.deepEqual(decision,state.evaluation.nodes.find(row=>row.node_id===node));assert.equal(decision.execution_state,'unresolved');
 assert.equal(await page.evaluate(id=>JSON.stringify(window.__responses[`${window.__base}/claims/${id}`].state),id),before);
 await noWrites(page);
});

test('Documents opens an unassigned received JPEG through the verified original source viewer',async t=>{
 const page=await fixturePage(t),artifact_id='isolated-unassigned-photo';
 await page.evaluate(({id,artifact_id,emptyHash})=>{
  const state=window.__responses[`${window.__base}/claims/${id}`].state;
  const descriptor={claim_id:id,artifact_id,file_name:'termination_notice.jpg',media_type:'image/jpeg',role:'supporting_document',sha256:'d'.repeat(64)};
  const source={...descriptor,text:'',text_sha256:emptyHash,extraction:'unsupported_metadata',complete:false,coverage:{visual_interpretation_performed:false}};
  state.source_descriptors.push(descriptor);state.acquired_sources.push(source);
  window.__responses[`${window.__base}/sources/${id}/${artifact_id}/text`]=source;
 },{id:robin,artifact_id,emptyHash:sha('')});
 const before=await page.evaluate(id=>JSON.stringify(window.__responses[`${window.__base}/claims/${id}`].state),robin);
 await open(page,robin);await page.getByRole('button',{name:'Documents',exact:true}).click();
 const files=page.locator('[data-au-panel="documents"] .au-supporting').filter({has:page.getByRole('heading',{name:'Files awaiting a document assignment',exact:true})});
 assert.deepEqual(await files.locator('[data-au-source]').evaluateAll(nodes=>nodes.map(node=>node.dataset.auSource)),[artifact_id]);
 assert.match(await files.innerText(),/Termination notice[\s\S]*Text could not be read/);
 const trigger=files.locator(`[data-au-source="${artifact_id}"]`);await trigger.click();
 await page.locator('.au-source-dialog[open] .au-source-capability').waitFor();
 assert.match(await page.locator('.au-source-dialog').innerText(),/Original image preview unavailable\. CasePath could not read this image\./);
 assert.equal(await page.locator('.au-source-dialog .au-source-body').count(),0);
 assert.equal(await page.locator('.au-record-dialog[open]').count(),0);
 await page.locator('.au-source-dialog .au-source-identity > summary').click();
 assert.match(await page.locator('.au-source-dialog').innerText(),/Source text verified[\s\S]*Received · interpretation unsupported[\s\S]*No readable text was extracted/);
 await escapeSource(page);
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.auSourceOrigin),`documents:${artifact_id}`);
 assert.equal(await page.evaluate(id=>JSON.stringify(window.__responses[`${window.__base}/claims/${id}`].state),robin),before);
 await noWrites(page);
});

test('the production browser draws all nine saved graphs without demo substitution, stage reports or initial motion',async t=>{
 const page=await fixturePage(t);
 for(const claim of claims){
  await open(page,claim.claim_id);const state=saved(claim.claim_id);
  const compact=await page.evaluate(()=>{
   window.__graphObjects={nodes:[...document.querySelectorAll('[data-au-node]')],edges:[...document.querySelectorAll('[data-au-edge]')],reading:document.querySelector('[data-au-evidence-path]'),question:document.querySelector('.au-reading-question')};
   return {selected:document.querySelector('[data-au-selected-step]')?.dataset.auSelectedStep,fact:document.querySelector('.au-reading-fact')?.dataset.auFact || null,requirement:document.querySelector('.au-reading-requirement')?.dataset.auObligation || null,visibleNodes:window.__graphObjects.nodes.filter(node=>node.getBoundingClientRect().width>0).map(node=>node.dataset.auNode)};
  });
  const parents=state.graph.edges.filter(edge=>edge.target_node_id===compact.selected).map(edge=>edge.source_node_id),children=state.graph.edges.filter(edge=>edge.source_node_id===compact.selected).map(edge=>edge.target_node_id);
  assert.deepEqual(sorted(compact.visibleNodes),sorted(new Set([compact.selected,...parents,...children])),'the compact map shows the actual selected decision and its neighbors');
  assert.equal(await page.locator('[data-au-expand-process]').getAttribute('aria-expanded'),'false');
  await openFullProcess(page);
  const actual=await page.evaluate(()=>({nodes:[...document.querySelectorAll('[data-au-node]')].map(node=>({id:node.dataset.auNode,label:node.querySelector('.au-node-title').textContent,selected:node.getAttribute('aria-pressed'),visible:node.getBoundingClientRect().width>0})),edges:[...document.querySelectorAll('[data-au-edge]')].map(edge=>({id:edge.dataset.auEdge,state:edge.dataset.state,path:edge.getAttribute('d'),visible:getComputedStyle(edge).display!=='none'})),selected:document.querySelector('[data-au-selected-step]')?.dataset.auSelectedStep,animations:window.__animations.filter(row=>row.node || row.edge || row.fact || row.document).length,stages:[...document.querySelectorAll('[data-au-stage="sources"],[data-au-stage="interpretation"],[data-au-stage="verification"],[data-au-stage="process"],[data-au-stage="knowledge"]')].filter(row=>!row.closest('[hidden],details:not([open])')).length}));
  assert.deepEqual(sorted(actual.nodes.map(node=>node.id)),sorted(state.graph.nodes.map(node=>node.node_id)),claim.claim_id);
  assert.deepEqual(sorted(actual.edges.map(edge=>edge.id)),sorted(state.graph.edges.map(edge=>edge.edge_id)),claim.claim_id);
  for(const node of actual.nodes){assert.equal(node.label,language.stepLabel(state.graph.nodes.find(row=>row.node_id===node.id)));assert.equal(node.visible,true,'every saved node is exposed in the full process');}
  for(const edge of actual.edges){assert.equal(edge.state,state.evaluation.edges.find(row=>row.edge_id===edge.id).activation);assert.ok(edge.path && !/NaN|Infinity/.test(edge.path));assert.equal(edge.visible,true,'every saved edge is exposed in the full process');}
  assert.equal(actual.selected,ui.preferredNode(state,null,responses[`${base}/claims/${claim.claim_id}/events?after=0`].events));assert.equal(actual.nodes.filter(node=>node.selected==='true').length,1);
  assert.equal(actual.animations,0);assert.equal(actual.stages,0);
  await page.locator('[data-au-expand-process]').click();
  assert.equal(await page.locator('[data-au-expand-process]').getAttribute('aria-expanded'),'false');
  const collapsed=await page.evaluate(()=>({selected:document.querySelector('[data-au-selected-step]')?.dataset.auSelectedStep,fact:document.querySelector('.au-reading-fact')?.dataset.auFact || null,requirement:document.querySelector('.au-reading-requirement')?.dataset.auObligation || null,visibleNodes:[...document.querySelectorAll('[data-au-node]')].filter(node=>node.getBoundingClientRect().width>0).map(node=>node.dataset.auNode),sameNodes:[...document.querySelectorAll('[data-au-node]')].every((node,index)=>node===window.__graphObjects.nodes[index]),sameEdges:[...document.querySelectorAll('[data-au-edge]')].every((edge,index)=>edge===window.__graphObjects.edges[index]),sameReading:document.querySelector('[data-au-evidence-path]')===window.__graphObjects.reading,sameQuestion:document.querySelector('.au-reading-question')===window.__graphObjects.question}));
  assert.deepEqual(collapsed,{...compact,sameNodes:true,sameEdges:true,sameReading:true,sameQuestion:true},'collapsing keeps the exact graph objects and selected evidence context');
  assert.equal(await page.locator('[data-au-panel]').count(),1);
  assert.equal(await page.locator('[data-au-panel] details pre, [data-au-panel] details [data-au-inspect]').count(),0,'the current reading view has no nested record disclosures');
  assert.deepEqual(await caseHistoryRecord(page),{state,projection:envelope(claim.claim_id).projection},`${claim.claim_id} retains its complete exact saved claim record through History`);
 }
 await noWrites(page);
});

test('manual graph focus survives saved refresh and return navigation instead of reverting to the verified default',async t=>{
 const page=await fixturePage(t,{width:390});await open(page,robin);
 assert.equal(await page.locator('[data-au-node][aria-pressed="true"]').getAttribute('data-au-node'),ui.preferredNode(saved(robin),null,responses[`${base}/claims/${robin}/events?after=0`].events));
 await openFullProcess(page);
 await page.locator('[data-au-node="lt_family"]').click();
 assert.equal(await page.locator('[data-au-node][aria-pressed="true"]').getAttribute('data-au-node'),'lt_family');
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.auNode),'lt_family');
 await advance(page,robin);await page.evaluate(()=>window.__controller.refresh());
 assert.equal(await page.locator('[data-au-selected-step]').getAttribute('data-au-selected-step'),'lt_family');
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.auNode),'lt_family');
 await open(page,claims.find(claim=>saved(claim.claim_id).graph.nodes.length===1).claim_id);await open(page,robin);
 assert.equal(await page.locator('[data-au-node][aria-pressed="true"]').getAttribute('data-au-node'),'lt_family');
 await noWrites(page);
});

test('fact selection exposes only its exact original passage and source inspection verifies it with focus return',async t=>{
 const page=await fixturePage(t);await open(page,robin);await openFullProcess(page);await page.locator('[data-au-node="lt_family"]').click();
 const fact=saved(robin).facts.find(fact=>fact.fact_id==='condition:family_home'),citation=fact.citations[0];
 if(await page.locator('.au-reading-fact').getAttribute('data-au-fact')===fact.fact_id) await page.locator('[data-au-panel="step"] [data-au-fact-select]').first().click();
 await page.locator('[data-au-panel="step"] [data-au-fact-select="condition:family_home"]').click();
 assert.deepEqual(await page.locator('[data-au-evidence-path] .au-reading-passages q').allTextContents(),[citation.quote]);
 assert.equal(await page.locator('.au-reading-fact').getAttribute('data-au-fact'),fact.fact_id);
 assert.equal(await page.locator('.au-reading-fact [aria-current="true"] .au-subject-verdict').textContent(),'Applies');assert.equal(await page.locator('.au-reading-fact .au-fact-summary').textContent(),fact.summary,'the selected subject shows its recorded reason, not folded');
 assert.equal(await page.locator('.au-reading-question').textContent(),language.stepLabel(saved(robin).graph.nodes.find(node=>node.node_id==='lt_family')));
 assert.equal(await page.locator('[data-au-evidence-path] select').count(),0,'objects are selected with contextual buttons');
 const requirement=page.locator('[data-au-evidence-path] [data-au-document="spouse_notice_copy"]');
 assert.equal(await requirement.getAttribute('data-route'),'needed_later');assert.match(await requirement.innerText(),/Needed after its step is reached\./);
 const obligation=saved(robin).obligations.find(row=>row.node_id==='lt_family' && row.document_type==='spouse_notice_copy');
 assert.equal(await requirement.getAttribute('data-au-obligation'),obligation.obligation_id);
 assert.equal(await page.locator('[data-au-panel="step"] [data-au-inspect]:not([data-au-inspect="step"])').count(),0);
 const record=await caseHistoryRecord(page);assert.deepEqual(record,{state:saved(robin),projection:envelope(robin).projection});
 assert.deepEqual(record.state.facts.find(row=>row.fact_id===fact.fact_id),fact);
 assert.deepEqual(record.state.obligations.find(row=>row.obligation_id===obligation.obligation_id),obligation);
 assert.deepEqual(record.state.evaluation.documents.find(row=>row.document_type==='spouse_notice_copy'),saved(robin).evaluation.documents.find(row=>row.document_type==='spouse_notice_copy'));
 assert.deepEqual(record.state.evaluation.nodes.find(row=>row.node_id==='lt_family'),saved(robin).evaluation.nodes.find(row=>row.node_id==='lt_family'));
 assert.deepEqual(await page.locator('[data-au-evidence-path] .au-reading-passages q').allTextContents(),[citation.quote]);
 const source=page.locator('[data-au-evidence-path] .au-evidence-source').first();await source.click();
 await page.locator('.au-source-dialog[open] .au-source-body mark').waitFor();
 assert.equal(await page.locator('.au-source-dialog .au-source-body mark').textContent(),citation.quote);
 const originalText=responses[`${base}/sources/${robin}/${citation.artifact_id}/text`].text;
 assert.equal(await page.locator('.au-source-dialog .au-source-body').textContent(),originalText,'the complete verified extraction is preserved around the exact cited span');
 assert.equal(sha(await page.locator('.au-source-dialog .au-source-body').textContent()),citation.text_sha256);
 assert.equal(await page.locator('.au-record-dialog[open]').count(),0);
 assert.equal(await page.evaluate(()=>document.activeElement?.hasAttribute('data-au-close')),true);
 const passageBounds=await page.locator('.au-source-dialog .au-source-body mark').boundingBox(),dialogBounds=await page.locator('.au-source-dialog').boundingBox();
 assert.ok(passageBounds.y>=dialogBounds.y && passageBounds.y+passageBounds.height<=dialogBounds.y+dialogBounds.height,'the exact span is visible in the source dialog');
 await page.locator('.au-source-dialog details summary').click();
 assert.ok((await page.locator('.au-source-dialog').innerText()).includes(citation.text_sha256));
 assert.ok((await page.locator('.au-source-dialog').innerText()).includes(citation.sha256));
 await page.locator('.au-source-dialog').evaluate(dialog=>{dialog.scrollTop=dialog.scrollHeight;});
 const closeBounds=await page.locator('.au-source-dialog [data-au-close]').boundingBox(),scrolledBounds=await page.locator('.au-source-dialog').boundingBox();
 assert.ok(closeBounds.y>=scrolledBounds.y && closeBounds.y+closeBounds.height<=scrolledBounds.y+scrolledBounds.height,'Close source remains visible when the full verified text and identity record are scrolled');
 await advance(page,robin);await page.evaluate(()=>window.__controller.refresh());
 await escapeSource(page);
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.auSource),citation.artifact_id);
 assert.equal(await page.evaluate(()=>document.activeElement?.dataset.auSourceOrigin),'path:lt_family:condition:family_home');
 assert.equal(await page.evaluate(()=>document.activeElement?.classList.contains('au-evidence-source')),true);
 assert.equal(JSON.parse(await page.evaluate(()=>document.activeElement.dataset.auCitation)).quote,citation.quote);
 await noWrites(page);
});

test('receiving claims bind to their exact knowledge version, with id/version fallback only for an absent hash',async t=>{
 const page=await fixturePage(t),knowledge=responses[`${base}/knowledge`];
 await page.evaluate(()=>window.__controller.showKnowledge());
 async function receiving(number){
  const version=knowledge.versions.find(row=>row.knowledge_id==='procedure.lease_termination_dispute' && row.version===number);
  await page.locator(`.au-learning-track .au-learning-node[data-au-learning-event-id*="version:"][data-au-knowledge="${version.knowledge_id}"][data-au-version="${number}"][data-au-knowledge-sha="${version.knowledge_sha256}"]`).click();
  const selected=page.locator(`[data-au-knowledge-identity="${version.knowledge_id}:${number}"]`);await selected.waitFor();
  assert.equal(await page.locator('[data-au-knowledge-identity]').count(),1,'one exact reusable procedure is open for reading');
  await selected.locator('[data-au-knowledge-facet="changes"]').click();
  assert.equal(await selected.locator('[data-au-knowledge-facet-panel="changes"]').count(),1);
  assert.equal(await page.locator('[data-au-knowledge-facet-panel]').count(),1,'one procedure facet is open for reading');
  const expected=await page.evaluate(()=>window.__responses[`${window.__base}/knowledge`]),record=await knowledgeHistoryRecord(page);
  assert.deepEqual(record,expected,'Knowledge History preserves the complete saved versions, uses and quarantined candidates');
  assert.deepEqual(record.versions.find(row=>row.knowledge_id===version.knowledge_id && row.version===number && row.knowledge_sha256===version.knowledge_sha256),version);
  return selected.locator('.au-procedure-provenance > article [data-au-claim]').evaluateAll(nodes=>nodes.map(node=>node.dataset.auClaim));
 }
 assert.deepEqual(sorted(await receiving(1)),sorted([robin,'auto_571f85327c290a71cde37df8','auto_7373bbf206ab25bacf71b82e']));
 assert.deepEqual(sorted(await receiving(2)),sorted(['auto_764f712d3833988ce6ff6cfd','auto_80bf8f54f289f5e4a966e645']));
 const version=knowledge.versions.find(version=>version.version===2),identity=version.knowledge_id;
 const exact={knowledge_id:identity,version:2,knowledge_sha256:version.knowledge_sha256,claim_id:'hash-match'};
 const variants=[exact,{...exact,knowledge_sha256:'0'.repeat(64),claim_id:'wrong-hash'},{...exact,knowledge_sha256:'',claim_id:'empty-hash'},{...exact,version:1,claim_id:'hash-other-version'},{knowledge_id:identity,version:2,claim_id:'legacy-absent-hash'},{knowledge_id:identity,version:1,claim_id:'legacy-other-version'}];
 await page.evaluate(uses=>{window.__responses[`${window.__base}/knowledge`].uses=uses;},variants);await page.evaluate(()=>window.__controller.showKnowledge());
 assert.deepEqual(sorted(await receiving(2)),sorted(['hash-match','legacy-absent-hash']));
 assert.deepEqual(await receiving(1),['legacy-other-version']);
 await noWrites(page);
});

test('repeated logical action IDs retain the exact saved receipt, drawer and return focus when a later run appends an assessment',async t=>{
 const page=await fixturePage(t),logicalId='assessment:lt_deadline',markers=['Isolated assessment alpha','Isolated assessment beta','Isolated assessment gamma','Isolated assessment delta'];
 const action=(summary,parent_revision,workflow_id)=>{
  const identity={operation:'assess_process_step',parent_revision,workflow_id};
  return {result:{action_id:logicalId,type:'step_assessment',label:'Recorded deadline assessment',node_ids:['lt_deadline'],status:'unresolved',summary},receipt:{...identity,receipt_sha256:sha(JSON.stringify(identity))}};
 };
 const initial=[action(markers[0],1,'isolated.earlier-run'),action(markers[1],saved(robin).revision-1,saved(robin).run_id)];
 const receipts=new Map(initial.map(row=>[row.result.summary,row.receipt.receipt_sha256]));
 await page.evaluate(({id,actions})=>{window.__responses[`${window.__base}/claims/${id}`].state.actions=actions;},{id:robin,actions:initial});
 await open(page,robin);await page.locator('.au-work-controls [data-au-detail="activity"]').click();
 const records=()=>page.locator('[data-au-panel="activity"] .au-history-record[data-au-action-instance]');
 const record=summary=>page.locator(`[data-au-panel="activity"] .au-history-record[data-au-action-instance$=":receipt:${receipts.get(summary)}"]`);
 assert.equal(await record(markers[0]).getAttribute('data-au-action-scope'),'historical');
 assert.equal(await record(markers[1]).getAttribute('data-au-action-scope'),'current');
 for(let index=0;index<2;index++){
  const chosen=record(markers[index+1]),trigger=chosen.locator('[data-au-inspect="action"]'),key=await trigger.getAttribute('data-au-record-id');
  const beforeKeys=await records().locator('[data-au-inspect="action"]').evaluateAll(nodes=>nodes.map(node=>node.dataset.auRecordId));
  assert.equal(new Set(beforeKeys).size,index+2,'distinct saved assessments need distinct disclosure identities');
  assert.equal(await chosen.getAttribute('data-au-action-instance'),key);
  const expected=await page.evaluate(({id,summary})=>window.__responses[`${window.__base}/claims/${id}`].state.actions.find(row=>row.result.summary===summary),{id:robin,summary:markers[index+1]});
  assert.ok(key.includes(expected.receipt.receipt_sha256),'the saved receipt distinguishes this instance from its logical action ID');
  await trigger.click();
  const initialRecord=await recordData(page);assert.deepEqual(initialRecord.result,expected.result);assert.deepEqual(initialRecord.receipt,expected.receipt);assert.equal(initialRecord.scope,'current');
  assert.equal(await page.locator('.au-record-dialog pre').getAttribute('data-au-record-id'),key);
  assert.equal(await page.evaluate(()=>document.activeElement?.hasAttribute('data-au-close-record')),true);
  await page.evaluate(()=>{window.__recordClose=document.activeElement;});
  const runId=`isolated.rerun-${index+1}`;
  await advance(page,robin,{run_id:runId});
  const parentRevision=await page.evaluate(id=>{
   const state=window.__responses[`${window.__base}/claims/${id}`].state,batch=window.__responses[`${window.__base}/claims/${id}/events?after=0`];
   batch.events.at(-1).kind='work.started';batch.events.at(-1).payload={run_id:state.run_id};return state.revision;
  },robin);
  const appended=action(markers[index+2],parentRevision,runId);
  receipts.set(appended.result.summary,appended.receipt.receipt_sha256);
  await page.evaluate(({id,action})=>{window.__responses[`${window.__base}/claims/${id}`].state.actions.push(action);},{id:robin,action:appended});
  await advance(page,robin);await page.evaluate(()=>window.__controller.refresh());
  assert.equal(await records().count(),index+3);
  assert.equal(await trigger.getAttribute('data-au-record-id'),key,'the chosen saved record identity is stable across a later run');
  assert.equal(await page.locator('.au-record-dialog[open]').count(),1);
  assert.equal(await page.locator('.au-record-dialog pre').getAttribute('data-au-record-id'),key);
  const afterRecord=await recordData(page);assert.deepEqual(afterRecord.result,expected.result);assert.deepEqual(afterRecord.receipt,expected.receipt);assert.equal(afterRecord.scope,'historical');
  assert.equal(await page.evaluate(()=>document.activeElement===window.__recordClose),true,'accepted updates preserve the drawer close control and its focus');
  const after=await records().locator('[data-au-inspect="action"]').evaluateAll(nodes=>nodes.map(node=>node.dataset.auRecordId));
  assert.equal(new Set(after).size,index+3);
  assert.notEqual(await record(markers[index+2]).locator('[data-au-inspect="action"]').getAttribute('data-au-record-id'),key,'a matching logical action ID cannot select another saved assessment');
  assert.equal(await chosen.getAttribute('data-au-action-scope'),'historical');
  assert.equal(await record(markers[index+2]).getAttribute('data-au-action-scope'),'current');
  assert.equal(await record(markers[0]).getAttribute('data-au-action-scope'),'historical');
  await closeRecord(page);
  assert.deepEqual(await page.evaluate(()=>({kind:document.activeElement?.dataset.auInspect,id:document.activeElement?.dataset.auRecordId,summary:document.activeElement?.closest('[data-au-action-instance]')?.innerText,panel:document.activeElement?.closest('[data-au-panel]')?.dataset.auPanel})),{kind:'action',id:key,summary:await chosen.innerText(),panel:'activity'},'closing returns focus to the same saved assessment instance');
 }
 await noWrites(page);
});

test('native intake and arrival drafts keep their FileList and DOM identity through connected evidence navigation',async t=>{
 const page=await fixturePage(t);await page.evaluate(()=>window.__controller.showIntake());
 await page.locator('#auTitle').fill('Retained native draft');await page.locator('#auMessage').fill('Original fictional message');
 await page.locator('#auFiles').setInputFiles({name:'draft.txt',mimeType:'text/plain',buffer:Buffer.from('Original draft bytes')});
 await page.evaluate(()=>{window.__intake=document.querySelector('[data-au-intake]');window.__intakeFiles=window.__intake.elements.files.files;});
 await page.evaluate(()=>window.__controller.showWork());await page.evaluate(()=>window.__controller.showKnowledge());await page.evaluate(()=>window.__controller.showIntake());
 assert.equal(await page.locator('#auTitle').inputValue(),'Retained native draft');assert.equal(await page.locator('#auMessage').inputValue(),'Original fictional message');
 assert.deepEqual(await page.evaluate(()=>({sameForm:document.querySelector('[data-au-intake]')===window.__intake,sameFileList:document.querySelector('#auFiles').files===window.__intakeFiles,names:[...document.querySelector('#auFiles').files].map(file=>file.name)})),{sameForm:true,sameFileList:true,names:['draft.txt']});
 await open(page,robin);await page.locator('[data-au-detail="sources"]').click();
 await page.locator('#auAdditionalFiles').setInputFiles({name:'arrival.txt',mimeType:'text/plain',buffer:Buffer.from('Original arrival bytes')});
 await page.evaluate(()=>{window.__arrival=document.querySelector('[data-au-arrival]');window.__arrivalFiles=window.__arrival.elements.files.files;});
 await page.locator('[data-au-detail="step"]').click();await openFullProcess(page);await page.locator('[data-au-node="lt_family"]').click();await advance(page,robin);await page.evaluate(()=>window.__controller.refresh());
 await page.locator('[data-au-detail="sources"]').click();
 assert.deepEqual(await page.evaluate(()=>({sameForm:document.querySelector('[data-au-arrival]')===window.__arrival,sameFileList:document.querySelector('#auAdditionalFiles').files===window.__arrivalFiles,names:[...document.querySelector('#auAdditionalFiles').files].map(file=>file.name)})),{sameForm:true,sameFileList:true,names:['arrival.txt']});
 await noWrites(page);
});

test('fresh changes remain still for reduced motion, hidden views and reconnect history',async t=>{
 const page=await fixturePage(t,{reducedMotion:'reduce'});await open(page,robin);
 await page.evaluate(id=>{const state=window.__responses[`${window.__base}/claims/${id}`].state;state.facts.find(fact=>fact.fact_id==='condition:family_home').summary='A new recorded summary';},robin);
 await advance(page,robin);await page.evaluate(()=>window.__controller.refresh());assert.equal(await page.evaluate(()=>window.__animations.length),0);
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,value:true}));
 await page.evaluate(id=>{window.__responses[`${window.__base}/claims/${id}`].state.evaluation.nodes.find(node=>node.node_id==='lt_deadline').execution_state='completed';},robin);
 await advance(page,robin);await page.evaluate(()=>window.__controller.refresh());assert.equal(await page.evaluate(()=>window.__animations.length),0);
 // A saved event that arrived while hidden must settle on reconnect, even though it changes a visible node.
 await page.evaluate(id=>{window.__responses[`${window.__base}/claims/${id}`].state.evaluation.nodes.find(node=>node.node_id==='lt_form').execution_state='ready';},robin);
 await advance(page,robin);
 await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
 await page.locator('[data-au-node="lt_form"][data-status="ready"]').waitFor();
 assert.equal(await page.evaluate(()=>window.__animations.length),0);await noWrites(page);
});
