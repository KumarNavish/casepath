'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const view=require('../casepath/assets/claims-workspace-presentation-v1.js');
test('a substantive colon is never erased from a claim title',()=>{
 assert.equal(view.title('Notice: termination for arrears'),'Notice: termination for arrears');
 assert.equal(view.title('Heating: bedroom and kitchen affected'),'Heating: bedroom and kitchen affected');
});
test('only recognised intake framing is shortened; the allegation is unchanged',()=>{
 assert.equal(view.title('Request for review: arrears termination'),'Arrears termination');
 assert.equal(view.title('Bitte um Prüfung: wiederholter Heizungsausfall'),'Wiederholter Heizungsausfall');
 assert.equal(view.title('Chronology still unclear: damage after repair'),'Damage after repair');
});
test('workspace counts use saved status rather than inferred optimism',()=>{
 const items=[{urgency:'high',readiness_state:'not_assessed',pending_evidence_count:null,owner:null},
 {urgency:'normal',readiness_state:'blocked',pending_evidence_count:1,owner:'A'},
 {urgency:'elevated',readiness_state:'decision_ready',pending_evidence_count:0,owner:'B'},
 {urgency:'normal',readiness_state:'safe_abstention',failure_or_unknown_effect:true,owner:null}];
 assert.deepEqual(view.queueSummary(items),{all:4,urgent:1,evidence:1,ready:1,attention:1,unassigned:2,unassessed:1});
 assert.deepEqual(view.queueSummary([]),{all:0,urgent:0,evidence:0,ready:0,attention:0,unassigned:0,unassessed:0});
});
test('a report excerpt quotes the message without adding a finding',()=>{
 const paragraph='The heating has failed again. We supplied the repair invoice, but the replacement part has not arrived.';
 assert.equal(view.reportExcerpt('Dear Sir or Madam\n\n'+paragraph),paragraph);
});
test('the claims list keeps search and filters behind one disclosure',()=>{
 const html=view.shell();for(const id of ['cwSearch','cwSort','cwReadiness','cwFailure','cwState','cwOwner','cwPendingEvidence','cwDetailPanel'])assert.match(html,new RegExp('id="'+id+'"'));
 assert.match(html,/<details class="cp-filter-popover"><summary>Filter<\/summary>/);
 assert.doesNotMatch(html,/data-queue-view=|aria-modal="true"/);
});
test('a source correction is exposed only for the exact server-permitted finding',()=>{
 const detail={state:{intake_assessment:{policy_clause_refs:[]}},artifacts:[]};
 const item={fact_id:'fact-a',evidence_item_id:'evidence-a',evidence_class:'received',title:'Receipt date'};
 const loop={loop_state:{checklist:{items:[]},observations:[]},correction_candidates:[{target_fact_id:'fact-a'}]};
 assert.match(view.evidenceSource(item,loop,detail),/data-correct-source="fact-a"/);
 assert.doesNotMatch(view.evidenceSource({...item,fact_id:'fact-b'},loop,detail),/data-correct-source=/);
});
test('causal changes retain exact evidence and distinguish insufficient from resolved',()=>{
 const row=(cls,required)=>({evidence_item_id:'e',title:'Receipt date',evidence_class:cls,mandatory_now:required,current_path:required,raw_status:cls,fact_state:cls==='received'?'known':'unknown'});
 const make=(rev,item,observations)=>({claim_id:'c',revision:rev,loop_state:{observations},operational_projection:{evidence_items:[item],readiness_state:'blocked',pending_evidence_count:1,current_process:{node_title:'Review receipt'}}});
 const old=make(2,row('missing',true),[]),next=make(4,row('insufficient',true),[{value:'Exact source passage',evidence_item_id:'e',source_refs:[]}]);
 const delta=view.compareLoops(old,next);assert.equal(delta.accepted,true);assert.equal(delta.sourceQuote,'Exact source passage');
 const html=view.changeMarkup(delta);assert.match(html,/Further evidence is still needed/);assert.match(html,/Source statement recorded/);assert.doesNotMatch(html,/No longer requested|path updated/);
});
test('recovery of committed evidence is never described as a rejected observation',()=>{
 const item={evidence_item_id:'e',title:'Receipt date',evidence_class:'received',mandatory_now:false,current_path:true,raw_status:'provided_sufficient',fact_state:'known'};
 const saved={claim_id:'c',revision:4,loop_state:{observations:[{value:'Received on 12 May',evidence_item_id:'e',source_refs:[]}]},operational_projection:{evidence_items:[item],readiness_state:'blocked',pending_evidence_count:1,current_process:{node_title:'Review next requirement'}}};
 const change=view.advanceChange(saved,saved,{revision:3,observationCount:0},true);
 assert.equal(change.kind,'recovery');assert.equal(change.accepted,true);assert.equal(change.sourceQuote,'Received on 12 May');
 const html=view.changeMarkup(change);assert.match(html,/Saved evidence recovered/);assert.doesNotMatch(html,/Evidence not accepted|No finding was added|One less thing to request/);
});
test('recovery never invents an observation when none was committed',()=>{
 const saved={claim_id:'c',revision:3,loop_state:{observations:[]},operational_projection:{evidence_items:[],readiness_state:'blocked',pending_evidence_count:1,current_process:{node_title:'Review receipt'}}};
 const change=view.advanceChange(saved,saved,{revision:3,observationCount:0},true);
 assert.equal(change.kind,'recovery');assert.equal(change.accepted,false);
 assert.match(view.changeMarkup(change),/Saved action recovered/);
});

test('a correction preview takes focus without a stale replan above it',()=>{
 const loop={claim_id:'c',outcome:'decision_ready',correction_candidates:[],
  operational_projection:{readiness_scope:'claim_process',readiness_state:'decision_ready',
   evidence_items:[],pending_evidence_count:0,evidence_class_counts:{received:0,irrelevant:0,conditional:0},
   principal_blocker:'No evidence outstanding',next_state:{title:'Review'}},
  loop_state:{selected_action:null,observations:[],checklist:{items:[]},
   process:{nodes:[],main_spine:[],current_overlay:{current_node_id:null,completed_node_ids:[],blocked_node_ids:[]}}}};
 const assessment={language:'en',noticed:[],conflicts:[],next_step:'Review receipt',
  conditions:{health_effects:{verdict:'unresolved'}},documents:[],candidate_deadline:null,
  steps:[{node_id:'receipt',state:'active',label:'Review receipt',condition_chips:[]}]};
 const html=view.workbench(loop,{claim_id:'c',binding:{},intake_assessment:{claim_assessment:assessment}},{
  correctionPreview:{effect:{fact_id:'f'}},
  change:{kind:'evidence',accepted:true,changes:[],remaining:0,afterState:'Ready for review'}
 });
 assert.match(html,/id="cwCorrectionPreview"/);
 assert.doesNotMatch(html,/id="cwReplanDelta"/);
 const preview=html.match(/<section class="cp-correction"[\s\S]*?<\/section>/)?.[0];
 assert.ok(preview);
 assert.match(preview,/id="cwCorrectionConfirm"/);
 assert.equal((preview.match(/class="cw-button cw-button-primary"/g)||[]).length,1);
 assert.match(html,/id="cwDraftOpen"/);
});
