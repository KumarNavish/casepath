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
test('why chain uses distinct action, need, step, quote and article',()=>{
 const markup=view.canvasTrace(null,assessedDetail,'now');
 assert.match(markup,/Ask for the receipt date/);
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
 assert.match(markup,/data-need-state="needed_now"/);
 assert.match(markup,/data-need-state="held_not_reviewed"/);
 assert.match(markup,/Spouse notice copy/);
 assert.doesNotMatch(markup,/All steps|data-workbench-tab/);
});
test('path chips name the transition whose verdict they show',()=>{
 const step={node_id:'later',label:'Build the dated timeline',state:'not_reached',condition_chips:[{condition_flag:'health_effects',label:'no immediate health escalation',verdict:'false',quote:'Mein Sohn hustet mehr'}],authority:null};
 const changed={...assessment,steps:[...assessment.steps.slice(0,-1),step]};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/no immediate health escalation <span>false<\/span>/);
 assert.doesNotMatch(markup,/Health effects alleged <span>false<\/span>/);
});
test('candidate deadlines display the paragraph from the cited authority',()=>{
 const changed={...assessment,candidate_deadline:{date:null,question:'When did the notice arrive?',authority:{article:'Art. 273',authority_id:'or-art-273-para1-20260101-de'}}};
 const markup=view.workbench(null,{intake_assessment:{claim_assessment:changed}},{detail:assessedDetail});
 assert.match(markup,/Candidate deadline · Art\. 273 Abs\. 1/);
 assert.match(markup,/Waiting for the anchoring date/);
 assert.match(markup,/When did the notice arrive/);
});
test('resize callbacks do not measure a replaced claim header',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
 assert.match(source,/measuredHeader\?\.isConnected && panel\.contains\(measuredHeader\)/);
 assert.doesNotMatch(source,/panel\.querySelector\('\.cw-detail-head'\)\.getBoundingClientRect/);
});
