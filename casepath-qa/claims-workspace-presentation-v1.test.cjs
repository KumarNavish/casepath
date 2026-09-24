'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const view = require('../casepath/assets/claims-workspace-presentation-v1.js');
const hash = 'a'.repeat(64), rawHash = 'b'.repeat(64);
const detail = {message:{message_id:'message-one',body:'Customer account'},state:{binding:{source_documents:[{sha256:hash}]},intake_assessment:{policy_clause_refs:[]}},artifacts:[{artifact_id:'message-one',role:'customer_message',sha256:rawHash}]};
const projectionRef = {source_id:'message-one.message-body-projection',source_version:'casepath.message-body-projection/1.0.0',source_sha256:hash};
test('provisional plan coverage never certifies claim readiness',()=>{
 assert.equal(view.readiness({readiness_state:'decision_ready',readiness_scope:'provisional_plan'}),'Plan covered · review needed');
});
test('a conflicting record is shown independently of its unknown class',()=>{
 assert.equal(view.evidenceStatus({evidence_class:'unknown',raw_status:'conflicting'}),'Conflicting information');
});
test('an uncertain action outcome takes precedence over readiness',()=>{
 assert.equal(view.readiness({failure_or_unknown_effect:true,readiness_state:'decision_ready'}),'Action needs checking');
});
test('an unresolved requirement without an action calls for handler review',()=>{
 assert.equal(view.copy('mandatory evidence is unresolved and no bounded action remains'),'The evidence remains unresolved. A handler must review it before the process can advance.');
});
test('HTML in source material is escaped',()=>{
 assert.equal(view.h('<script>"&'), '&lt;script&gt;&quot;&amp;');
});
test('correction summaries do not expose normalized branch identifiers',()=>{
 const text=view.semanticText({fact_state:'known',normalized_value:'lt_e01',evidence_status:'provided_sufficient',explanation:'A fixed-version server interpreter'});
 assert.equal(text,'Established · Sufficient evidence');
});
test('original byte-matched source is linked',()=>{
 assert.equal(view.sourceArtifactIndex({source_id:'message-one',source_sha256:rawHash},detail),0);
});
test('artifact identifiers alone cannot bind altered source bytes',()=>{
 assert.equal(view.sourceArtifactIndex({source_id:'message-one',source_sha256:'c'.repeat(64)},detail),-1);
});
test('a registered message projection links to its original message',()=>{
 assert.equal(view.sourceArtifactIndex(projectionRef,detail),0);
});
test('an unregistered projection hash cannot link to an original',()=>{
 assert.equal(view.sourceArtifactIndex({...projectionRef,source_sha256:'d'.repeat(64)},detail),-1);
});
test('a projection from another claim cannot inherit the original link',()=>{
 assert.equal(view.sourceArtifactIndex({...projectionRef,source_id:'other.message-body-projection'},detail),-1);
});
const item=(evidenceClass,mandatory)=>({evidence_item_id:'item',title:'First question',fact_state:'unknown',raw_status:evidenceClass,evidence_class:evidenceClass,mandatory_now:mandatory,current_path:mandatory});
const loop=(id,revision,items,observations=[])=>({claim_id:id,revision,loop_state:{observations},operational_projection:{evidence_items:items,readiness_state:'blocked',pending_evidence_count:items.filter(i=>i.mandatory_now).length,current_process:{node_title:'Current question'}}});
test('replanning distinguishes resolved and newly active requirements',()=>{
 const before=loop('one',2,[item('missing',true)]);
 const after=loop('one',4,[item('received',false)],[{}]);
 const delta=view.compareLoops(before,after);
 assert.equal(delta.accepted,true);assert.equal(delta.changes.length,1);
 assert.equal(delta.changes[0].wasRequired,true);assert.equal(delta.changes[0].isRequired,false);
});
test('no cross-claim replan comparison is presented',()=>{
 assert.equal(view.compareLoops(loop('one',2,[]),loop('two',4,[])),null);
});
test('a rejected source is never described as a new observation',()=>{
 const delta=view.compareLoops(loop('one',2,[item('missing',true)]),loop('one',2,[item('missing',true)]));
 assert.equal(delta.accepted,false);assert.equal(delta.changes.length,0);
 assert.match(view.changeMarkup(delta),/Evidence not accepted/);
});
test('queue activation is confined to queue rows, not the claim panel',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
 assert.doesNotMatch(source,/panel\.dataset\.claimId/);
 assert.doesNotMatch(source,/root\.querySelectorAll\('\[data-claim-id\]'\)/);
});
test('scrollable source text remains reachable by keyboard',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-presentation-v1.js'),'utf8');
 assert.match(source,/class="cw-message(?: [^"]+)?" tabindex="0"/);
});
test('PDFs open the verified original instead of an unusable sandboxed plug-in',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
 assert.match(source,/data-open-original-pdf/);
 assert.match(source,/rel="noopener noreferrer"/);
 assert.doesNotMatch(source,/<iframe class="cw-document-preview" sandbox=""/);
});
test('source text has no duplicated focus attributes',()=>{
 for(const name of ['claims-workspace-presentation-v1.js','claims-workspace-v1.js']) {
  const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/'+name),'utf8');
  assert.doesNotMatch(source,/tabindex="0" tabindex="0"/);
 }
});
const assessment={language:'en',next_step:'Ask for the receipt date.',noticed:[],conflicts:[],candidate_deadline:null,conditions:{termination_received:{verdict:'true',quote:'My form arrived on Monday'}},steps:[
 {node_id:'done',label:'Capture notice details',state:'done',condition_chips:[],authority:null},
 {node_id:'now',label:'Preserve the deadline',state:'active',condition_chips:[{condition_flag:'termination_received',label:'termination received',verdict:'true',quote:'My form arrived on Monday'}],authority:{article:'Art. 273'}},
 {node_id:'later',label:'Check service',state:'not_reached',condition_chips:[],authority:null},
],documents:[
 {document_type:'proof_of_receipt',label:'Proof of receipt',route_state:'needed_now',required_at_node_ids:['now'],held_files:[],authority:{article:'Art. 273'}},
 {document_type:'spouse_notice_copy',label:'Separate spouse notice',route_state:'held_not_reviewed',required_at_node_ids:['later'],held_files:[{file_name:'Spouse notice.pdf'}],authority:{article:'Art. 266n'}},
]};
const assessedDetail={...detail,state:{...detail.state,intake_assessment:{claim_assessment:assessment}}};
test('why chain uses distinct need, step, quote and article',()=>{
 const markup=view.canvasTrace(null,assessedDetail,'now');
 assert.match(markup,/Proof of receipt/);
 assert.match(markup,/Preserve the deadline/);
 assert.match(markup,/My form arrived on Monday/);
 assert.match(markup,/Art. 273/);
 const values=[...markup.matchAll(/<strong(?: [^>]*)?>([^<]*)<\/strong>/g)].map(match=>match[1]);
 assert(values.every((value,index)=>index===0||value!==values[index-1]));
});
test('canvas shows all steps and separates needed from held documents',()=>{
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail});
 assert.match(markup,/Capture notice details/);
 assert.match(markup,/Preserve the deadline/);
 assert.match(markup,/Check service/);
 assert.match(markup,/data-path-state="active"/);
 assert.match(markup,/data-condition-state="true"/);
 assert.match(markup,/data-need-state="now"/);
 assert.match(markup,/data-route-state="held_not_reviewed"/);
 assert.match(markup,/Spouse notice copy/);
 assert.doesNotMatch(markup,/All steps|data-workbench-tab/);
});
test('assessed claim has one next action and a source-only record control',()=>{
 const oldAction={title:'Capture issuer, receipt and end date',action_sha256:hash,evidence_item_id:'old-item'};
 const savedLoop={outcome:'blocked',loop_state:{selected_action:oldAction,checklist:{items:[]}},operational_projection:{readiness_scope:'current',evidence_items:[],pending_evidence_count:0}};
 const markup=view.workbench(savedLoop,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail});
 assert.match(markup,/Ask for the receipt date/);
 assert.match(markup,/Source record/);
 assert.doesNotMatch(markup,/id="cwLoopCommit"/);
 assert.doesNotMatch(markup,/Capture issuer, receipt and end date|supporting evidence is still missing/i);
});
test('noticed dates and both sides of a conflict open exact source spans',()=>{
 const changed={...assessment,noticed:[{text:'Tenant notice: 30. Juni',source_id:'tenant-pdf',source_kind:'pdf_text'}],conflicts:[{fact:'termination end date',message:'The two notices give different end dates.',sources:[{artifact_id:'tenant-pdf',quote:'30. Juni',value:'30. Juni'},{artifact_id:'spouse-pdf',quote:'31. Juli',value:'31. Juli'}]}]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/class="cp-a-review-ready" data-status="completed"/);
 assert.match(markup,/data-noticed-source="tenant-pdf" data-noticed-quote="30. Juni"/);
 assert.match(markup,/data-noticed-source="spouse-pdf" data-noticed-quote="31. Juli"/);
 assert.doesNotMatch(markup,/Review saved/);
});
test('noticed facts name the party, start date and PDF page without losing source spans',()=>{
 const changed={...assessment,noticed:[
  {text:'Robin Foster',source_id:'tenant-pdf',source_kind:'pdf_text',page:1,fact_kind:'named_party_candidate'},
  {text:'Casey Foster',source_id:'spouse-pdf',source_kind:'pdf_text',page:1,fact_kind:'named_party_candidate'},
  {text:'19 August 2025',source_id:'message-one',source_kind:'customer_message',fact_kind:'reported_date'},
  {text:'Tenant_termination_notice.pdf: 30. Juni',source_id:'tenant-pdf',source_kind:'pdf_text',page:1},
 ],attachment_pages:[{artifact_id:'tenant-pdf',file_name:'Tenant_termination_notice.pdf'},{artifact_id:'spouse-pdf',file_name:'Spouse_termination_notice.pdf'}]};
 const source={...assessedDetail,message:{...assessedDetail.message,body:'As far as I remember, it started around 19 August 2025.'}};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:source});
 for(const [name,value] of [['Tenant','Robin Foster'],['Spouse','Casey Foster'],['Started','19 August 2025'],['Tenant notice, page 1','end date 30 June']])assert.match(markup,new RegExp(name+'<\\/span>.*>'+value.replaceAll(' ','\\s*')));
 assert.match(markup,/data-noticed-source="tenant-pdf" data-noticed-quote="30. Juni"/);
});
test('path chips name the transition whose verdict they show',()=>{
 const step={node_id:'later',label:'Build the dated timeline',state:'not_reached',condition_chips:[{condition_flag:'health_effects',label:'no immediate health escalation',verdict:'false',quote:'Mein Sohn hustet mehr'}],authority:null};
 const changed={...assessment,conditions:{...assessment.conditions,health_effects:{verdict:'false',quote:'Mein Sohn hustet mehr'}},steps:[...assessment.steps.slice(0,-1),step]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/Health effects <em>false<\/em>/);
});
test('candidate deadlines display the paragraph from the cited authority',()=>{
 const changed={...assessment,candidate_deadline:{date:null,question:'When did the notice arrive?',authority:{article:'Art. 273',authority_id:'or-art-273-para1-20260101-de'}}};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/Candidate deadline · Art\. 273 Abs\. 1/);
 assert.match(markup,/When did the notice arrive/);
});
test('resize callbacks do not measure a replaced claim header',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
 assert.match(source,/measuredHeader\?\.isConnected && panel\.contains\(measuredHeader\)/);
 assert.doesNotMatch(source,/panel\.querySelector\('\.cw-detail-head'\)\.getBoundingClientRect/);
});

test('minimal claim presentation guards',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const css=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-presentation-v1.css'),'utf8');
 const agentCss=fs.readFileSync(path.join(__dirname,'../casepath/assets/agent-work-v1.css'),'utf8');
 assert.doesNotMatch(css,/text-transform\s*:\s*uppercase|\.cp-card\b/);
 assert.doesNotMatch(agentCss,/\.cp-a-[^{}]*\{[^}]*text-transform\s*:\s*uppercase/);
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:assessment}},{detail:assessedDetail});
 const top=markup.split('<footer class="cp-a-footer"')[0];
 const regions=[...top.matchAll(/<(?:section)\b[^>]*class="(cp-a-(?:next|review|path|questions|needs|draft))"/g)].length+1;
 assert(regions<=9,`claim has ${regions} regions`);
 assert.equal([...top.matchAll(/<button\b/g)].length,1);
 assert.doesNotMatch(view.packetLibrary(assessedDetail),/<button\b/);
 const visibleText=top.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ');
 assert.doesNotMatch(visibleText,/deterministic|assessment|journal|projection|authority|saved claim record|workspace/i);
 assert.doesNotMatch(markup,/class="[^"]*cp-card|class="[^"]*bordered-panel/);
});
test('queue groups claims as list items without table headers or chevrons',()=>{
 const markup=view.queueRows([{claim_id:'one',subject:'Test claim',received_at:'2026-09-24',language:'en',owner:null,triage:{waiting_on:'Customer',noticed_fact:'The notice is incomplete.',next_step:'Ask for the missing page.'}}]);
 assert.match(markup,/<h2 class="cp-triage-group">Waiting on customer/);
 assert.match(markup,/<ul><li tabindex="0" data-claim-id="one"/);
 assert.doesNotMatch(markup,/<table|<th|cp-row-chevron/);
});
