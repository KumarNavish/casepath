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
test('decision trace keeps an opened source separate from accepted evidence',()=>{
 const decision={
  loop_state:{
   process:{nodes:[{node_id:'intake',title:'Capture notice details',evidence_requirement_ids:['item']}],current_overlay:{current_node_id:'intake'},selected_path:['intake']},
   selected_action:{process_node_id:'gap',evidence_item_id:'item'},
   obligations:[{obligation_id:'item',status:'active'}],
   facts:[{fact_id:'fact',label:'Notice details',state:'unknown',source_refs:[{excerpt:'Hello'}]}],
   checklist:{items:[{item_id:'item',legal_basis_ids:[]}]},observations:[],
  },
  operational_projection:{evidence_items:[{...item('missing',true),fact_id:'fact'}]},
 };
 const before=view.canvasTrace(decision,detail,'intake');
 assert.match(before,/No supporting passage accepted yet/);
 assert.doesNotMatch(before,/Hello|Open original source|Request inspection report/);
 decision.loop_state.observations.push({evidence_item_id:'item',source_refs:[{source_id:'message-one',source_sha256:rawHash,sanitized_excerpt:'Exact accepted passage'}]});
 decision.loop_state.facts[0].state='known';
 decision.loop_state.facts[0].normalized_value='unresolved';
 const after=view.canvasTrace(decision,detail,'intake');
 assert.match(after,/Exact accepted passage/);
 assert.match(after,/Unresolved condition recorded/);
 assert.doesNotMatch(after,/>Established</);
 assert.match(after,/data-source-artifact="0"/);
});
test('resize callbacks do not measure a replaced claim header',()=>{
 const source=require('node:fs').readFileSync(require('node:path').join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
 assert.match(source,/measuredHeader\?\.isConnected && panel\.contains\(measuredHeader\)/);
 assert.doesNotMatch(source,/panel\.querySelector\('\.cw-detail-head'\)\.getBoundingClientRect/);
});
