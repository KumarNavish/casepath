'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {gunzipSync}=require('node:zlib'),ui=require('../casepath/assets/autonomous-workspace-v1.js');
const fixture=JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures/desk-v3.json.gz'))));
for(const item of fixture.cases)test(`request row opens the recorded answer without changing it: ${item.id}`,()=>{
 const state=item.envelope.state,request=ui.deskRequest(state.message),claim={...state,customer_request:request,browse_metadata:{domain:state.graph.family}},before=JSON.stringify(claim),html=ui.claimsMarkup([claim]);
 assert.ok(state.message.includes(request));assert.match(html,/data-au-customer-request="true"/);assert.ok(html.includes(request.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;')));assert.ok(html.includes(`data-au-claim="${state.claim_id}"`));assert.match(html,/>Answer ready</);
 assert.doesNotMatch(html,/au-case-facts|au-claim-excerpt|In demonstration|Recorded status/);
 for(const row of state.outcome.legal_predicates.filter(r=>r.status==='failed'))assert.ok(html.includes(ui.deskLegalLabel(row.predicate_id)));
 assert.ok(html.includes(ui.caseLabel(state.claim_id,claim).primary));
 if(state.outcome.legal_predicates.length&&state.outcome.legal_predicates.every(p=>p.status==='supported'))assert.match(html,/All legal tests met/);else assert.doesNotMatch(html,/All legal tests met/);
 assert.equal(JSON.stringify(claim),before);assert.equal(ui.matchingClaims([claim],{search:request}).length,1);assert.equal(ui.matchingClaims([claim],{search:'answer ready'}).length,1);
});
test('missing documents take priority and unknown states do not become ready',()=>{
 assert.equal(ui.caseListStatus({status:'deferred',outcome:{missing_evidence:[{label:'Notice'},{label:'Delivery'}]}}).label,'Needs 2 documents');
 assert.equal(ui.caseListStatus({status:'deferred',outcome:{missing_evidence:[{label:'Notice'}]}}).label,'Needs 1 document');
 assert.equal(ui.caseListStatus({status:'not_started'}).label,'Not started');
 assert.equal(ui.caseListStatus({status:'new_unknown'}).label,'Status unknown');
});
test('absent requests retain the recorded title without inventing a quotation',()=>{
 const html=ui.claimsMarkup([{claim_id:'new',title:'Inspect <this>',customer_request:null,status:'received'}]);
 assert.match(html,/data-au-customer-request="false">Inspect &lt;this&gt;<\/span>/);assert.doesNotMatch(html,/“|Answer ready/);
});

test('unlabelled rows retain recorded identity and date, never infer a customer name',()=>{
 const claim={claim_id:'unlabelled',title:'Original subject',received_at:'2025-10-22T12:00:00+02:00',customer_request:'Check the notice',status:'not_started'};
 assert.match(ui.claimsMarkup([claim]),/Original subject · 22 Oct 2025/);
 assert.match(ui.claimsMarkup([{...claim,customer_name:'Taylor'}]),/Taylor · 22 Oct 2025/);
 const unknown={...claim,status:'completed',outcome:{legal_predicates:[{status:'unresolved'}]}};assert.doesNotMatch(ui.claimsMarkup([unknown]),/All legal tests met/);
 assert.doesNotMatch(ui.claimsMarkup([{...unknown,outcome:{legal_predicates:[]}}]),/All legal tests met/);
});
