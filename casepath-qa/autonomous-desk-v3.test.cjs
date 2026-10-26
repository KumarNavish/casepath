'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {gunzipSync}=require('node:zlib');
const ui=require('../casepath/assets/autonomous-workspace-v1.js');
const fixture=JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures/desk-v3.json.gz'))));
for(const item of fixture.cases)test(`desk counters and legal labels follow the actual trace: ${item.id}`,()=>{
 const state=item.envelope.state;assert.ok(ui.deskRequest(state.message));assert.ok(state.message.includes(ui.deskRequest(state.message)));const frames=item.trace.trim().split('\n').map(JSON.parse),all=frames.filter(r=>r.type==='operation');
 const groups=new Map(state.source_descriptors.map(s=>[s.artifact_id,`${s.role}:${s.file_name}`]));
 for(const size of [0,1,Math.floor(all.length/2),all.length]){
  const rows=all.slice(0,size),model=ui.deskOperationModel(state,{binding:frames[0],headState:state,rows});
  assert.equal(model.counts.documents,new Set(rows.filter(r=>r.kind==='span.read').map(r=>groups.get(r.source?.artifact_id||r.object.id)).filter(Boolean)).size);
  assert.equal(model.counts.facts,rows.filter(r=>r.kind==='fact.extract'&&r.source&&r.result?.verification_required!==false).length);
  assert.equal(model.counts.rules,rows.filter(r=>['condition.evaluate','node.evaluate','dependency.evaluate','process.inspect','document.require'].includes(r.kind)).length);
  assert.equal(model.counts.met,new Set(rows.filter(r=>r.kind==='step.complete'&&r.result?.status==='completed'&&state.graph.nodes.some(n=>n.node_id===r.object.id)).map(r=>r.object.id)).size);
 }
 const unknown=ui.deskOperationModel(state);assert.equal(unknown.counts.documents,null);assert.equal(unknown.counts.facts,null);assert.equal(unknown.counts.rules,null);
 const sources=new Map(all.filter(r=>r.kind==='source.open').map(r=>[r.object.id,r.result])),trace={binding:frames[0],headState:state,rows:all,sources,finished:true,verifiedResult:true};
 const html=ui.agentDeskMarkup(state,{},null,[],{},{operations:trace});
 assert.ok(html.includes('All documents checked. Please review before replying.'));
 assert.ok(html.indexOf('All documents checked. Please review before replying.') < html.indexOf('data-au-desk-answer'), 'the next step leads the completed desk');
 for(const legal of state.outcome.legal_predicates){assert.ok(ui.DESK_LEGAL_TESTS[legal.predicate_id],`explicit glossary entry: ${legal.predicate_id}`);assert.ok(html.includes(ui.deskLegalLabel(legal.predicate_id).replace(/&/g,'&amp;')));}
 for(const step of state.graph.nodes){
  assert.ok(ui.DESK_STEPS[step.node_id],`explicit step glossary entry: ${step.node_id}`);
  assert.ok(html.includes(step.label),`reasoning retains recorded label: ${step.node_id}`);
  assert.ok(html.includes(`data-au-desk-select="${step.node_id}"`));
  const selected=ui.agentDeskMarkup(state,{},step.node_id,[],{},{operations:trace,chosenNode:step.node_id});
  assert.ok(selected.includes('data-au-desk-quote='),`${step.node_id} shows its cited passage`);
 }
 const model=ui.deskOperationModel(state,trace);for(const operation of all)assert.equal(model.operationNodes.get(operation.id)||null,ui.operationNodeId(operation,state.graph,state,trace),`${operation.id} keeps the source/cause destination`);
 for(const doc of state.graph.nodes.flatMap(n=>n.document_types||[]))assert.ok(html.includes(`data-au-desk-document-select="${doc}"`));
 assert.ok(html.includes(ui.deskLegalStatus(state.outcome.legal_predicates).label));
 const caveat=state.outcome.summary.slice(state.outcome.summary.match(/^.*?[.!?](?=\s|$)/u)[0].length).trim();
 assert.ok(html.includes(`Still open: ${caveat}`), 'recorded unresolved sentence remains in the answer');
 assert.equal((html.match(/All cases are fictional\./g)||[]).length,1);
 const before=JSON.stringify(state);const binding=ui.deskDraftBinding(state);assert.equal(binding.body,state.outcome.request_draft.body);assert.equal(JSON.stringify(state),before);
});
test('legal status keeps missing and unresolved tests distinct from met tests',()=>{
 assert.equal(ui.deskLegalLabel('new_legal_condition'),'New legal condition');
 assert.equal(ui.deskLegalStatus([]).label,'No checks available');
 assert.equal(ui.deskLegalStatus([{status:'unresolved'}]).label,'1 of 1 checks still open');
 assert.equal(ui.deskLegalStatus([{status:'failed'},{status:'supported'}]).label,'1 of 2 checks not met');
});
test('local draft copies reject a different case or original and invalid stored values',()=>{
 const entry={contract:'casepath.local-draft/1',binding:'case-and-original-hash',subject:'My subject',body:'My changes',saved_at:'2026-10-21T10:00:00Z'};
 assert.equal(ui.checkedDeskDraft(entry,entry.binding).body,'My changes');
 for(const changed of [{binding:'different'}, {contract:'other'}, {subject:'x'.repeat(501)}, {body:'x'.repeat(50001)}, {saved_at:'not a date'}])assert.equal(ui.checkedDeskDraft({...entry,...changed},entry.binding),null);
 assert.equal(ui.deskDraftBinding({claim_id:'not-sent',outcome:{request_draft:{status:'sent',body:'No editable draft'}}}),null);
});

test('unknown step labels use only mechanical paraphrases',()=>{
 assert.equal(ui.deskStepLabel({node_id:'new_step',label:'Assess notification context'}),'Check notification context');
 assert.equal(ui.deskStepLabel({node_id:'new_step'}),'New step');
});

test('next step uses recorded gaps, recipients and graph nodes without inventing them',()=>{
 const state={graph:{nodes:[{node_id:'lt_form',label:'Assess whether the termination notice is valid'}]},outcome:{missing_evidence:[{document_type:'notice',label:'Termination notice',node_ids:['lt_form'],requested_from:'the customer',reason:'Check the required notice form.'}]}};
 const before=JSON.stringify(state),html=ui.deskNextStepMarkup(state);
 assert.match(html,/Request: /);assert.match(html,/Needed for step 1:/);assert.match(html,/Why: Check the required notice form/);assert.match(html,/Ask the customer\./);assert.match(html,/data-au-desk-document-select="notice"/);assert.match(html,/data-au-desk-select="lt_form"/);assert.match(html,/Check whether the termination notice is valid/);assert.equal(JSON.stringify(state),before);
 const unknown=ui.deskNextStepMarkup({outcome:{missing_evidence:[{label:'Delivery proof',node_ids:['not-recorded']}]}});
 assert.match(unknown,/Who to ask is not on file/);assert.match(unknown,/step requiring this document is not on file/);assert.doesNotMatch(unknown,/data-au-desk-select|Nothing missing/);
 assert.match(ui.deskNextStepMarkup({outcome:{}}),/document needs.*not been recorded/);assert.doesNotMatch(ui.deskNextStepMarkup({outcome:{}}),/Nothing missing/);
});
