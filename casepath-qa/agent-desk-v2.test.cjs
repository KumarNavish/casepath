const {test}=require('node:test');
const assert=require('node:assert/strict');
const desk=require('../casepath/assets/agent-desk-v2.js');
const claim={claim_id:'clm_1',title:'Family home <script>',agent_state:'waiting_for_you',ask:'Confirm which notice applies.',why:'Two sources disagree.',decider:'Handler',draft_status:'draft_not_sent',coverage:{note:'One unreadable page.'},latest_activity:{type:'source_read',label:'Read the customer message.'}};
test('desk exposes the ask, reason, coverage gap and actual last work without implying dispatch',()=>{
 const html=desk.row(claim);
 for(const text of ['Confirm which notice applies.','Two sources disagree.','One unreadable page.','Read the customer message.','Draft, not sent.'])assert.ok(html.includes(text));
 assert.ok(!html.includes('<script>'));assert.ok(html.includes('Waiting for you'));
});
test('unknown activity and source coverage are explicit',()=>{
 const html=desk.row({...claim,coverage:null,latest_activity:null,draft_status:'not_prepared'});
 assert.ok(html.includes('Source coverage is unknown.'));assert.ok(html.includes('No agent activity is recorded.'));assert.ok(!html.includes('Draft, not sent.'));
});
test('quiet work is collapsed while real handler asks stay visible',()=>{
 const html=desk.groups({groups:[{id:'needs_you',count:1,claims:[claim]},{id:'quiet',count:149,claims:[{...claim,claim_id:'clm_2',agent_state:'not_started'}]}]});
 assert.ok(html.includes('<section class="ad-group"'));assert.ok(html.includes('<details class="ad-group ad-quiet"'));assert.ok(!html.includes('<details class="ad-group ad-quiet" open'));
 assert.ok(html.includes('<span>149</span>'));
});
test('search crosses group boundaries and preserves supplied counts',()=>{
 const data={groups:[{id:'quiet',count:149,claims:[claim]}]};
 assert.ok(desk.groups(data,'family').includes('149 · 1 shown'));
 assert.ok(desk.groups(data,'absent').includes('Clear search'));
});
test('approved requests remain explicitly unsent',()=>{
 assert.ok(desk.row({...claim,draft_status:'approved_not_sent'}).includes('Request approved, not sent.'));
});
test('quiet counts distinguish explicit unstarted reviews from checked or unknown coverage',()=>{
 const data={total:3,groups:[{id:'quiet',count:3,claims:[{...claim,review_started:false},{...claim,review_started:true,coverage:{read_sources:0}},{...claim,coverage:null}]}]};
 assert.ok(desk.shell(data).includes('1 not yet reviewed'));
 assert.ok(!desk.shell(data).includes('3 not yet reviewed'));
 assert.ok(desk.row(claim).includes('Open claim'));
});

test('desk evidence keeps exact passages and rejects a different saved claim prefix',()=>{
 const row={...claim,workspace_revision:7,workspace_state_sha256:'state-seven'};
 const packet={claim_id:row.claim_id,workspace_revision:7,workspace_state_sha256:'state-seven',questions:[{sources:[{artifact_id:'original-pdf',file_name:'Notice <unconfirmed>.pdf',quote:'30. Juni <unconfirmed>',page:1}]}]};
 const evidence=desk.peekEvidence(packet,row);
 assert.equal(evidence.sources[0],packet.questions[0].sources[0]);
 assert.ok(evidence.html.includes('data-desk-source="0"'));
 assert.ok(evidence.html.includes('30. Juni &lt;unconfirmed&gt;'));
 assert.ok(!evidence.html.includes('<unconfirmed>'));
 for(const changed of [{claim_id:'other'},{workspace_revision:8},{workspace_state_sha256:'changed'}])assert.throws(()=>desk.peekEvidence({...packet,...changed},row),/Saved work changed/);
 assert.deepEqual(desk.peekEvidence({...packet,questions:[]},row).sources,[]);
 assert.ok(desk.peekEvidence({...packet,questions:[]},row).html.includes('No exact source passage'));
});
