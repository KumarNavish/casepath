'use strict';
const test=require('node:test'), assert=require('node:assert/strict');
const view=require('../casepath/assets/claims-workspace-presentation-v1.js');
const proposal={readiness_scope:'provisional_plan',provisional_next_action:{enabled:true,audience:'provider',requested_contents:['Offer an alternative service window.','Confirm availability.']}};
test('saved provider follow-up is visible but never dispatched',()=>{
 const html=view.provisionalFollowupMarkup(proposal);
 assert.match(html,/Request from the provider/);
 assert.match(html,/Offer an alternative service window\./);
 assert.match(html,/Confirm availability\./);
 assert.match(html,/not been sent/);
 assert.match(html,/does not certify/);
 assert.doesNotMatch(html,/<button|<form|fetch\(/);
});
test('no follow-up is fabricated for a non-provisional claim',()=>{
 assert.equal(view.provisionalFollowupMarkup({...proposal,readiness_scope:'claim_process'}),'');
});
test('retired proposals are absent instead of remaining active requests',()=>{
 assert.equal(view.provisionalFollowupMarkup({...proposal,provisional_next_action:{...proposal.provisional_next_action,enabled:false}}),'');
 assert.equal(view.provisionalFollowupMarkup({...proposal,provisional_next_action:null}),'');
});
test('proposal content is escaped and its audience is bounded',()=>{
 assert.match(view.provisionalFollowupMarkup({...proposal,provisional_next_action:{...proposal.provisional_next_action,requested_contents:['<script>alert(1)</script>']}}),/&lt;script&gt;/);
 assert.equal(view.provisionalFollowupMarkup({...proposal,provisional_next_action:{...proposal.provisional_next_action,audience:'invented'}}),'');
});
test('an enabled follow-up is not described as completed plan coverage',()=>{
 assert.equal(view.readiness({...proposal,readiness_state:'decision_ready'}),'Follow-up proposed');
});
const fixture=(enabled=true)=>({claim_id:'test',outcome:'decision_ready',operational_projection:{...proposal,provisional_next_action:{...proposal.provisional_next_action,enabled},readiness_state:'decision_ready',evidence_items:[],evidence_class_counts:{received:0,irrelevant:0},pending_evidence_count:0,principal_blocker:'Review proposal',next_state:{title:'Review proposal'}},loop_state:{selected_action:null,observations:[],checklist:{items:[]},six_agent_cycle_receipt:{agent_ids:[],deterministic_gate_ids:[],agent_receipt_sha256s:[],gate_receipt_sha256s:[]},process:{main_spine:[],nodes:[],current_overlay:{current_node_id:null,completed_node_ids:[]}}},correction_candidates:[]});
test('full provisional workbench keeps one review action and all follow-up content',()=>{
 const html=view.workbench(fixture(),{claim_id:'test'});
 assert.match(html,/id="cwProvisionalNextAction"/);
 assert.match(html,/Review the proposed follow-up/);
 assert.equal((html.match(/class="cw-button cw-button-primary"/g)||[]).length,1);
 assert.match(html,/data-show-investigation/);
 assert.doesNotMatch(html,/id="cwLoopCommit"|id="cwExport"|No model call was made\./);
});
test('a cleared provisional plan may be exported for review but never approved',()=>{
 const html=view.workbench(fixture(false),{claim_id:'test'});
 assert.doesNotMatch(html,/id="cwProvisionalNextAction"/);
 assert.match(html,/id="cwExport"/);
 assert.match(html,/not a certified claim decision/);
});
