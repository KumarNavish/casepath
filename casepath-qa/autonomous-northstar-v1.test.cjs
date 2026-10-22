'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{gunzipSync}=require('node:zlib');
const ui=require('../casepath/assets/autonomous-workspace-v1.js'),fixture=JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures/desk-v3.json.gz'))));
test('role table uses recorded kind and stage; unknown operations retain the previous role',()=>{
 for(const [kind,role]of Object.entries({'verification.check':'checker','document.check':'finder','decision':'result','answer':'result','condition.evaluate':'builder','node.evaluate':'builder','dependency.evaluate':'builder','process.inspect':'builder','document.require':'builder','step.complete':'builder','knowledge.reuse':'builder'}))assert.equal(ui.northStarRole({kind}),role);
 for(const kind of ['source.open','span.read','phrase.match','fact.extract']){assert.equal(ui.northStarRole({kind,stage:'interpret_reference'}),'reader');assert.equal(ui.northStarRole({kind,stage:'verify_reference'}),'checker');assert.equal(ui.northStarRole({kind,actor:'Reader'}),'reader');}
 assert.equal(ui.northStarRole({kind:'future.kind',actor:'Reader'},'finder'),'finder');assert.equal(ui.northStarRole({kind:'unknown'}),null);
});
for(const c of fixture.cases)test(`north-star plans and exact locators remain bound to recorded operations: ${c.id}`,()=>{
 const state=c.envelope.state,rows=c.trace.trim().split('\n').map(JSON.parse).filter(f=>f.type==='operation'),model=ui.northStarPlanModel(state,rows),byId=new Map(rows.map(o=>[o.id,o])),sources=new Map();
 let role=null,pins=0;
 for(const o of rows){if(o.kind==='source.open')sources.set(o.object.id,{...state.source_descriptors.find(s=>s.artifact_id===o.object.id),...o.result});role=ui.northStarRole(o,role);if(o.source){const pin=ui.northStarPin(o,sources);assert.ok(pin);assert.equal(pin.quote,Array.from(sources.get(pin.artifact_id).text).slice(pin.start_char,pin.end_char).join(''));assert.equal(ui.northStarPin({...o,source:{...pin,start_char:pin.start_char+1}},sources),null);assert.equal(ui.northStarPin({...o,source:{...pin,text_sha256:'0'.repeat(64)}},sources),null);pins++;}else assert.equal(ui.northStarPin(o,sources),null);}
 assert.equal(role,'result');assert.ok(pins>20);
 for(const node of state.graph.nodes){const plan=model.plans.get(node.node_id),complete=rows.find(o=>o.kind==='step.complete'&&o.object.id===node.node_id&&o.result.status==='completed');assert.ok(plan.length);assert.equal(plan.at(-1).operation.id,complete.id);assert.equal(plan.at(-1).label,`Decide: ${ui.northStarQuestion(node)}`);let seq=0;for(const r of plan){assert.equal(r.operation,byId.get(r.operation.id));assert.equal(model.links.get(r.operation.id),node.node_id);assert.ok(r.operation.seq>seq&&r.operation.seq<=complete.seq);seq=r.operation.seq;assert.ok(['source.open','span.read','fact.extract','verification.check','document.check','step.complete'].includes(r.operation.kind));}}
 const html=ui.northStarMarkup(state,{headState:state,rows:[],sources:new Map(),nsReady:true,nsCatalogue:model},{});assert.match(html,/Watch the analysis/);assert.doesNotMatch(html,/UI fixture|Reading now|Wants:|files read|facts found|checks run|steps done|From the customer/);assert.doesNotMatch(html,/data-au-ns-node=/);
});
test('unlinked and ambiguous source reads cannot be attributed to a node',()=>{
 const state={graph:{nodes:[{node_id:'a',document_types:['a']},{node_id:'b',document_types:['b']}]}},source={artifact_id:'s',file_name:'Source.txt'},open={id:'open',seq:1,kind:'source.open',object:{id:'s'},cause_ids:[],result:{}},rows=[open,...['a','b'].map((id,i)=>({id,seq:i+2,kind:'verification.check',object:{id:'fact:'+id,type:'fact'},input:{document_type:id},cause_ids:['open'],source:{artifact_id:'s'}}))];state.source_descriptors=[source];const model=ui.northStarPlanModel(state,rows);assert.equal(model.links.has('open'),false);assert.equal(model.plans.get('a').length,1);assert.equal(model.plans.get('b').length,1);
});
test('unknown process IDs preserve their exact recorded label',()=>assert.equal(ui.northStarQuestion({node_id:'future',label:'Recorded question?'}),'Recorded question?'));
test('executive completion highlights the latest visible fact or its own recorded completion',()=>{
 for(const c of fixture.cases){
  const state=c.envelope.state,all=completedTrace(c),catalogue=ui.northStarPlanModel(state,all.rows);
  for(const op of all.rows.filter(row=>row.kind==='step.complete'&&row.result.status==='completed')){
   const trace={...all,executive:true,current:op,rows:all.rows.filter(row=>row.seq<=op.seq),nsCatalogue:catalogue};
   const m=ui.northStarModel(state,trace),latest=m.facts.at(-1);
   assert.deepEqual(m.pin,latest?.source||op.source);assert.equal(m.source.artifact_id,m.pin.artifact_id);
   const markup=ui.northStarMarkup(state,trace,{playing:true});assert.ok(markup.includes(`data-start="${m.pin.start_char}" data-end="${m.pin.end_char}"`));
  }
 }
});
test('a completion stays visually pending until its plan has receded',()=>{
 const c=fixture.cases[0],state=c.envelope.state,rows=c.trace.trim().split('\n').map(JSON.parse).filter(f=>f.type==='operation'),op=rows.find(o=>o.kind==='step.complete'),prefix=rows.filter(o=>o.seq<=op.seq),trace={headState:state,rows:prefix,current:op,sources:new Map(),nsCatalogue:ui.northStarPlanModel(state,rows),nsPendingCompletion:op.id};
 assert.equal(ui.northStarModel(state,trace).done.has(op.object.id),false);assert.equal(ui.northStarModel(state,{...trace,nsPendingCompletion:null}).done.has(op.object.id),true);
});
function completedTrace(c){const state=c.envelope.state,rows=c.trace.trim().split('\n').map(JSON.parse).filter(o=>o.type==='operation'),sources=new Map();for(const o of rows)if(o.kind==='source.open')sources.set(o.object.id,{...state.source_descriptors.find(s=>s.artifact_id===o.object.id),...o.result});return {headState:state,rows,sources,binding:{},verifiedResult:true,finished:true};}
for(const c of fixture.cases)test(`completed process keeps columns and exact passages local: ${c.id}`,()=>{
 const state=c.envelope.state,trace=completedTrace(c);
 for(const node of state.graph.nodes){const m=ui.northStarCompletedModel(state,trace,node.node_id),ids=new Set(trace.rows.filter(o=>o.kind==='fact.extract'&&ui.operationNodeId(o,state.graph,state,trace)===node.node_id).map(o=>o.object.id));
  assert.deepEqual(m.facts,state.facts.filter(f=>ids.has(f.fact_id)));assert.deepEqual(m.predicates,state.outcome.legal_predicates.filter(f=>ids.has(f.predicate_id)));assert.ok(m.documents.every(d=>node.document_types.includes(d.document_type)));assert.ok(m.columns.every(c=>c.rows.length));assert.equal(m.references.length,0);assert.ok(!m.columns.some(c=>c.id==='reference'));assert.equal(m.missing.length,0);assert.ok(!m.columns.some(c=>c.id==='missing'));
  if(m.pin){const original=Array.from(m.source.text);assert.equal(m.pin.quote,original.slice(m.pin.start_char,m.pin.end_char).join(''));const preview=ui.northStarSourcePreview(m.source,m.pin);assert.equal(preview.before+m.pin.quote+preview.after,original.slice(preview.offset).join(''));assert.doesNotMatch(preview.text,/^Synthetic demonstration document/);assert.match(preview.date,/^\d{2}\.\d{2}\.\d{4}$/);}
 }
 const d=ui.northStarCompletedModel(state,trace);if(d.decisive.length)assert.equal(d.nodeId,d.decisive[0].node_id);
});
test('one source Read row retains interleaved operations and rows sort by first seq',()=>{const plan=[{label:'Read source',operation:{id:'a',seq:1}},{label:'Read source',operation:{id:'b',seq:2}},{label:'Check source',operation:{id:'c',seq:3}},{label:'Read source',operation:{id:'d',seq:4}}],groups=ui.northStarPlanGroups(plan);assert.deepEqual(groups.map(g=>g.operations.map(o=>o.id)),[['a','b','d'],['c']]);assert.equal(plan.length,4);});
for(const c of fixture.cases)test(`first node-bound extraction is visibly building and its read plan is active: ${c.id}`,()=>{
 const state=c.envelope.state,all=completedTrace(c),catalogue=ui.northStarPlanModel(state,all.rows),op=all.rows.find(o=>o.kind==='fact.extract'&&catalogue.links.has(o.id)),rows=all.rows.filter(o=>o.seq<=op.seq),trace={...all,rows,current:op,nsCatalogue:catalogue},nodeId=catalogue.links.get(op.id);
 assert.ok(!rows.some(o=>o.kind==='node.evaluate'&&o.object.id===nodeId));
 const html=ui.northStarMarkup(state,trace,{playing:true});assert.ok(html.includes(`data-au-ns-node="${nodeId}" data-state="building"`));
 const active=[...html.matchAll(/<li data-au-ns-plan-row="[^"]+" data-au-ns-plan-operations="([^"]+)" data-state="active"[^>]*>/g)].filter(match=>decodeMarkup(match[1]).includes(op.id));assert.equal(active.length,1);assert.match(html,/au-ns-plan-progress/);
 const fact=state.facts.find(f=>f.fact_id===op.object.id);assert.ok(fact?.label);assert.ok(html.includes(fact.label));assert.ok(!html.includes(fact.label.split(' ').slice(0,2).join(' ')+'…'));
 const readGroup=ui.northStarPlanGroups(catalogue.plans.get(nodeId)).find(g=>g.operations.some(o=>o.id===op.id)),later=all.rows.find(o=>o.seq>readGroup.operations.at(-1).seq&&catalogue.links.get(o.id)===nodeId);if(later){const after=ui.northStarMarkup(state,{...all,rows:all.rows.filter(o=>o.seq<=later.seq),current:later,nsCatalogue:catalogue},{});assert.match(after,/data-au-ns-plan-operations="[^"]+" data-state="done"><span class="au-ns-plan-status"[^>]*><svg/);}
});
test('a source header cited by the original locator is never hidden',()=>{const source={text:'Synthetic demonstration document (fictional)\nSource date: 2025-02-21\nReview as-of: 2025-03-01\n\nBody'},pin={start_char:0,end_char:9};const preview=ui.northStarSourcePreview(source,pin);assert.equal(preview.offset,0);assert.equal(preview.date,null);assert.equal(preview.before+source.text.slice(0,9)+preview.after,source.text);});
test('an unrelated passage cannot replace the selected node evidence',()=>{const c=fixture.cases[0],trace=completedTrace(c),state=c.envelope.state,baseline=ui.northStarCompletedModel(state,trace,'dh_scope'),other=trace.rows.find(o=>o.source&&ui.operationNodeId(o,state.graph,state,trace)==='dh_notice');assert.ok(other);const selected=ui.northStarCompletedModel(state,trace,'dh_scope',{operation:other.id});assert.equal(selected.operation.id,baseline.operation.id);});
test('only node-bound missing evidence and references enter the local chain',()=>{const c=fixture.cases[0],state=structuredClone(c.envelope.state),trace=completedTrace(c);state.outcome.missing_evidence=[{label:'Current lease',node_ids:['dh_scope'],document_type:'new_doc'},{label:'Other',node_ids:['dh_notice'],document_type:'another'}];state.knowledge_uses=[{knowledge_id:'local',node_id:'dh_scope',version:1},{knowledge_id:'whole-procedure',version:2}];const m=ui.northStarCompletedModel(state,trace,'dh_scope');assert.deepEqual(m.missing.map(g=>g.label),['Current lease']);assert.deepEqual(m.references.map(r=>r.knowledge_id),['local']);assert.deepEqual(m.columns.map(c=>c.id),['facts','law','evidence','missing','reference']);});
const knowledge=JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures/knowledge-w6.json.gz'))));
for(const c of fixture.cases)test(`memory payoff uses the exact checklist and case-local evidence: ${c.id}`,()=>{
 const trace={...completedTrace(c),journal:c.envelope.events},state=c.envelope.state,m=ui.northStarMemoryModel(state,trace,knowledge),html=ui.northStarMemoryMarkup(state,trace,{knowledge});assert.ok(m);assert.equal(m.operation.input.receiving_claim_id,state.claim_id);assert.equal(m.reuse.pin.knowledge_sha256,m.operation.input.knowledge_sha256);assert.equal(m.recipes.length,m.operation.result.reused_evidence_recipes);const version=knowledge.versions.find(v=>v.knowledge_id===m.reuse.pin.knowledge_id&&v.version===m.reuse.pin.version);assert.equal(Boolean(m.earlierCase),Boolean(version.source_claim_id&&version.source_claim_id!==state.claim_id));assert.equal(html.includes('saved from an earlier case'),Boolean(m.earlierCase));assert.match(html,/3 document checks reused/);assert.match(html,/Facts come from this case only/);assert.match(html,/Qualified review is still required/);assert.doesNotMatch(html,/expert-reviewed|Edited by reviewer|reviewed memory|Before|Now ·|Recorded checklist reuse|Recorded effect|Used an earlier checklist/);
 for(const node of state.graph.nodes){const n=ui.northStarMemoryModel(state,trace,knowledge,node.node_id);assert.equal(n.local.nodeId,node.node_id);assert.ok(n.localRecipes.every(r=>n.recipes.includes(r)));if(node.document_types.length&&n.recipes.some(r=>node.document_types.includes(r.document_type)))assert.ok(n.localRecipes.every(r=>node.document_types.includes(r.document_type)));}
});
test('memory connections fail closed on an unverified trace or a mismatched identity',()=>{const c=fixture.cases[0],trace={...completedTrace(c),journal:c.envelope.events};assert.equal(ui.northStarMemoryModel(c.envelope.state,{...trace,verifiedResult:false},knowledge),null);const bad=structuredClone(trace);bad.rows.find(o=>o.kind==='knowledge.reuse').input.knowledge_sha256='0'.repeat(64);assert.equal(ui.northStarMemoryModel(c.envelope.state,bad,knowledge),null);});
test('whole-case wording changes never imply a changed step decision',()=>{const c=fixture.cases[0],trace={...completedTrace(c),journal:c.envelope.events};const html=ui.northStarMemoryMarkup(c.envelope.state,trace,{knowledge});assert.doesNotMatch(html,/Before|NOW|whole.case|au-ns-memory-comparison/);});
test('node marks separate failed and open legal tests from completed operations',()=>{const c=fixture.cases[3],trace=completedTrace(c),state=c.envelope.state,m=ui.northStarCompletedModel(state,trace,'lt_intake'),form=m.desk.nodes.find(n=>n.node_id==='lt_form');assert.equal(ui.northStarNodeVerdict(m,form),'failed');let html=ui.northStarCompletedMarkup(state,trace,'step',{chosenNode:'lt_intake'});assert.match(html,/data-au-ns-node-verdict="failed"/);assert.match(html,/Legal test not met">✕/);html=ui.northStarCompletedMarkup(state,trace,'step',{chosenNode:'lt_form'});assert.ok(html.indexOf('✕ Notice given on the canton-approved form')<html.indexOf('CO 266l'));const open={...m,predicatesByNode:new Map([['lt_form',[{status:'unresolved'}]]])};assert.equal(ui.northStarNodeVerdict(open,form),'open');assert.equal(ui.northStarQuestion({node_id:'dh_cause'}),'Is it outside the tenant’s responsibility?');});
test('preview whitespace remains identical to the immutable source, including its missing spaces',()=>{const c=fixture.cases[3],trace=completedTrace(c),m=ui.northStarCompletedModel(c.envelope.state,trace),p=ui.northStarSourcePreview(m.source,m.pin);assert.ok(p.text.includes('forSeefeldstrasse'));assert.ok(p.text.includes('On2026'));assert.ok(p.text.includes('toTaylor'));assert.equal(p.before+m.pin.quote+p.after,Array.from(m.source.text).slice(p.offset).join(''));});
test('Source checker lists each accepted exact passage once and retains its source identity',()=>{for(const c of fixture.cases){const trace=completedTrace(c),pins=new Map();for(const o of trace.rows){const p=o.kind==='verification.check'&&o.result.accepted&&ui.northStarPin(o,trace.sources);if(p)pins.set(`${p.artifact_id}:${p.start_char}:${p.end_char}`,p);}const html=ui.northStarCompletedMarkup(c.envelope.state,trace,'verified',{});assert.equal((html.match(/data-au-ns-verified=/g)||[]).length,pins.size);for(const p of pins.values())assert.ok(html.includes(`data-au-source="${p.artifact_id}"`));}});

test('Claim reader exposes only established facts with exact source locators',()=>{for(const c of fixture.cases){const state=c.envelope.state,trace=completedTrace(c),html=ui.northStarCompletedMarkup(state,trace,'sources',{});assert.doesNotMatch(html.slice(html.indexOf('data-au-ns-source-view')),/<h2>Sources/);const established=state.facts.filter(f=>['established','supported'].includes(f.status||f.verdict)&&f.citations?.length);assert.equal((html.match(/data-au-ns-reader-fact=/g)||[]).length,established.length);for(const f of established){assert.ok(html.includes(`data-au-ns-reader-fact="${f.fact_id}"`));assert.ok(html.includes(f.short_label||f.label||f.fact_id));}for(const f of state.facts.filter(f=>f.status==='unresolved'))assert.ok(!html.includes(`data-au-ns-reader-fact="${f.fact_id}"`));}});

const decodeMarkup=value=>value.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
test('Source checker groups all exact passages beneath one heading for each source',()=>{
 for(const c of fixture.cases){
  const trace=completedTrace(c),model=ui.deskOperationModel(c.envelope.state,trace),html=ui.northStarCompletedMarkup(c.envelope.state,trace,'verified',{});
  const groups=[...html.matchAll(/<section class="au-ns-reader-source" data-au-ns-verified-source="([^"]+)">([\s\S]*?)<\/section>/g)];assert.ok(groups.length);
  const names=groups.map(g=>decodeMarkup(g[2].match(/<h3>([\s\S]*?)<\/h3>/)[1].replace(/<[^>]*>/g,'')));assert.equal(new Set(names).size,groups.length);
  for(const [,id,body]of groups){const file=model.files.find(f=>f.ids.includes(id));assert.ok(file);assert.equal((body.match(/<h3>/g)||[]).length,1);for(const passage of body.matchAll(/data-au-ns-verified="[^"]+" data-au-source="([^"]+)" data-au-citation="([^"]+)"/g)){assert.ok(file.ids.includes(passage[1]));const pin=JSON.parse(decodeMarkup(passage[2]));assert.ok(trace.sources.get(pin.artifact_id).text.includes(pin.quote));}}
 }
});

test('Claim reader quotes a request only when it exists verbatim in the recorded message source',()=>{
 for(const c of fixture.cases){
  const state=c.envelope.state,trace=completedTrace(c),html=ui.northStarCompletedMarkup(state,trace,'sources',{});
  const quoted=html.match(/<p class="au-ns-reader-request">Wants: "<span data-au-ns-request>([\s\S]*?)<\/span>"<\/p>/);assert.ok(quoted);const request=decodeMarkup(quoted[1]);assert.equal(request,ui.deskRequest(state.message));
  const ids=state.source_descriptors.filter(s=>s.role==='customer_message').map(s=>s.artifact_id);assert.ok(state.acquired_sources.some(s=>ids.includes(s.artifact_id)&&s.text.includes(request)));
  const altered=structuredClone(state);altered.message='My specific request is: an invented remedy.';const rejected=ui.northStarCompletedMarkup(altered,trace,'sources',{});assert.doesNotMatch(rejected,/data-au-ns-request/);assert.match(rejected,/No facts from this source\./);
 }
});

for(const c of fixture.cases)test(`every recorded seq drives plan progress and matching spine/title: ${c.id}`,()=>{
 const state=c.envelope.state,all=completedTrace(c),catalogue=ui.northStarPlanModel(state,all.rows),prefix=[],done=new Set();let nodeId=null;
 for(const op of all.rows){
  prefix.push(op);nodeId=catalogue.links.get(op.id)||nodeId;
  const groups=ui.northStarPlanGroups(catalogue.plans.get(nodeId)||[]);
  for(const group of groups){
   const seqs=group.operations.map(o=>o.seq),before=seqs.filter(seq=>seq<op.seq).length;
   for(const finished of [false,true]){const n=before+(finished&&seqs.includes(op.seq)?1:0),actual=ui.northStarPlanProgress(group,op.seq,finished);assert.equal(actual.state,n===seqs.length?'done':op.seq>=seqs[0]?'active':'waiting');assert.equal(actual.percent,100*n/seqs.length);assert.equal(actual.completed,n);}
  }
  const html=ui.northStarMarkup(state,{...all,rows:prefix,current:op,nsCatalogue:catalogue,nsPendingCompletion:op.kind==='step.complete'?op.id:null},{playing:true}),rings=[...html.matchAll(/data-au-ns-node="([^"]+)" data-state="building"/g)].map(m=>m[1]),node=state.graph.nodes.find(n=>n.node_id===nodeId);
  const rendered=[...html.matchAll(/<li data-au-ns-plan-row="([^"]+)"[^>]*data-state="([^"]+)"[^>]*>([\s\S]*?)<\/li>/g)];assert.equal(rendered.length,groups.length);
  for(const row of rendered){const group=groups.find(g=>g.operations.at(-1).id===row[1]),seqs=group.operations.map(o=>o.seq),completed=seqs.filter(seq=>seq<op.seq).length,want=completed===seqs.length?'done':op.seq>=seqs[0]?'active':'waiting';assert.equal(row[2],want,`row at seq ${op.seq}`);if(want==='active'){const bar=+row[3].match(/--au-plan-progress:([0-9.]+)%/)[1];assert.equal(bar,100*completed/seqs.length);}}
  assert.deepEqual(rings,node&&!done.has(nodeId)?[nodeId]:[],`seq ${op.seq}`);
  if(rings.length)assert.ok(html.includes(`Checking “${ui.northStarQuestion(node)}”`),`title/ring at seq ${op.seq}`);
  if(op.kind==='step.complete'&&op.result.status==='completed')done.add(op.object.id);
 }
});
test('unlabelled fact quotes retain the exact full DOM text and hover title',()=>{
 for(const c of fixture.cases){const state=c.envelope.state;for(const op of completedTrace(c).rows.filter(o=>o.kind==='fact.extract'&&o.source&&!state.facts.some(f=>f.fact_id===o.object.id))){const html=ui.northStarFactCopy(state,op),quoted=html.match(/data-au-ns-fact-quote>([\s\S]*?)<\/span>/),title=html.match(/title="([^"]+)"/);assert.equal(decodeMarkup(quoted[1]),op.source.quote);assert.equal(decodeMarkup(title[1]),op.source.quote);}}
});

test('customer envelope is formatted only from recorded fields, without losing Unicode source offsets',()=>{
 const source={text:'Channel: phone_note\nTimestamp: 2025-02-20T13:00:00+01:00\nFrom: Zoë <zoe@example.test>\nTo: Intake\nSubject: Heat\n\nA 🏠 with no heat.'};
 const start=Array.from(source.text.split('A 🏠')[0]).length,pin={start_char:start,end_char:start+3};
 const p=ui.northStarSourcePreview(source,pin);assert.deepEqual(p.fields,[['From','Zoë <zoe@example.test>'],['To','Intake'],['Date','2025-02-20T13:00:00+01:00'],['Subject','Heat']]);assert.equal(p.channel,'phone_note');
 assert.equal(p.before+Array.from(source.text).slice(pin.start_char,pin.end_char).join('')+p.after,'A 🏠 with no heat.');
 const header=ui.northStarSourcePreview(source,{start_char:0,end_char:7});assert.equal(header.offset,0);assert.deepEqual(header.fields,[]);
 assert.deepEqual(ui.northStarSourcePreview({text:'Hello\nFrom: a body quotation'}).fields,[]);
});
test('intake and law expose recorded provenance; draft uses the saved body without sending',()=>{
 const c=fixture.cases[0],state=c.envelope.state,trace=completedTrace(c),m=ui.northStarCompletedModel(state,trace,'dh_scope');
 assert.match(ui.northStarIntakeMarkup(state),/Customer intake · phone note/);
 const law=ui.northStarLawMarkup(state,m);assert.match(law,/publisher: Fedlex/);assert.match(law,/https:\/\/www.fedlex.admin.ch/);assert.match(law,/Qualified legal review is still required/);
 const draft=ui.deskDraftReadMarkup(ui.deskDraftBinding(state));assert.ok(draft.includes(state.outcome.request_draft.body));assert.match(draft,/Not sent — you decide/);assert.doesNotMatch(draft,/data-au-draft-save/);
 assert.match(ui.northStarInitialDateMarkup(fixture.cases[1].envelope.state),/Ein genaues Anfangsdatum/);assert.equal(ui.northStarInitialDateMarkup(state),'');
 assert.match(ui.northStarTabsMarkup('reader'),/automated assistant; recorded work/);
 assert.match(ui.northStarTabsMarkup('checker'),/Checks quoted passages against recorded sources/);
 const checks=ui.northStarCompletedMarkup(state,trace,'verified',{});assert.match(checks,/matches quoted passages to received files/);assert.match(checks,/Qualified legal review is still required/);
});

test('completion evidence answers the question using only that completion’s recorded citations',()=>{
 const expected={dh_scope:'residential_tenancy_scope',dh_notice:'landlord_first_knowledge',dh_cause:'outside_small_tenant_maintenance_and_no_tenant_cause',dh_evidence:'objective_use_impairment',dh_response:'continuing_defect_without_remedy'};
 for(const c of fixture.cases.slice(0,3)){
  const state=c.envelope.state,all=completedTrace(c),catalogue=ui.northStarPlanModel(state,all.rows);
  for(const [node,predicate]of Object.entries(expected)){
   const op=all.rows.find(row=>row.kind==='step.complete'&&row.object.id===node),trace={...all,executive:true,current:op,rows:all.rows.filter(row=>row.seq<=op.seq),nsCatalogue:catalogue},m=ui.northStarModel(state,trace);
   assert.equal(m.facts.length,1);assert.equal(m.facts[0].object.id,predicate);
   assert.ok(op.result.citations.some(p=>p.artifact_id===m.pin.artifact_id&&p.start_char===m.pin.start_char&&p.end_char===m.pin.end_char&&p.quote===m.pin.quote));
   assert.deepEqual(m.pin,m.facts[0].source);assert.ok(m.facts[0].seq<op.seq);
   assert.deepEqual(ui.northStarCompletedModel(state,all,node).pin,m.pin,'completed view uses the same cited evidence');
   if(node==='dh_cause')assert.notEqual(m.pin.artifact_id,op.source.artifact_id,'do not show the default tenancy paragraph for cause');
  }
 }
 const c=fixture.cases[0],state=c.envelope.state,all=completedTrace(c),op=structuredClone(all.rows.find(row=>row.kind==='step.complete'&&row.object.id==='dh_cause'));op.result.citations=[];
 const m=ui.northStarModel(state,{...all,executive:true,current:op,rows:all.rows.filter(row=>row.seq<=op.seq),nsCatalogue:ui.northStarPlanModel(state,all.rows)});
 assert.deepEqual(m.pin,op.source);assert.equal(m.facts.length,0,'do not invent a source connection without a completion citation');
});
test('clarity labels distinguish document readiness, draft content and checklist provenance',()=>{
 const c=fixture.cases[1],state=c.envelope.state,trace={...completedTrace(c),journal:c.envelope.events},html=ui.northStarMemoryMarkup(state,trace,{knowledge}),m=ui.northStarMemoryModel(state,trace,knowledge);
 assert.ok(html.includes(`data-au-claim="${m.earlierCase}"`));assert.match(html,/Automated checks passed · 243 rule scenarios. Human review is still required/);
 assert.match(html,/Built from document checks in/);assert.match(html,/Reused for the same case type/);assert.match(html,/Reuse the checks. Recheck the facts/);
 assert.match(ui.deskNextStepMarkup(state),/Documents checked for this assessment. Review before replying/);
 const draft=ui.deskDraftReadMarkup(ui.deskDraftBinding(state));assert.match(draft,/Assessment draft/);assert.match(draft,/Review and complete this draft/);assert.ok(draft.includes(state.outcome.request_draft.body));
});
