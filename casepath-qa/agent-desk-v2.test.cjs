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

test('closed desk peeks leave the saved reason, real work, coverage and unsent draft visible',()=>{
 const reviewed={...claim,review_started:true,run_status:'completed',coverage:{note:'3 of 3 original bound sources read.'},latest_activity:{type:'RUN_COMPLETED',label:'All six roles completed. Claim readiness remains governed by the existing authority.'}};
 const original=JSON.stringify(reviewed),html=desk.row(reviewed),visible=html.split('<details class="ad-peek">')[0];
 assert.match(visible,/<p class="ad-reason">Two sources disagree\.<\/p>/);
 assert.match(visible,/<p class="ad-work-summary">/);
 for(const text of ['Six review roles finished; findings need handler review.','3 of 3 original bound sources read.','Draft, not sent.'])assert.ok(visible.includes(text),text);
 assert.match(html,/<details class="ad-peek"><summary>What was checked<\/summary>/);
 assert.match(html,/data-desk-evidence="clm_1"/);assert.equal(JSON.stringify(reviewed),original);
});

test('a later prepared draft retains the signed completed review without inventing role counts',()=>{
 const visible=desk.row({...claim,review_started:true,run_status:'completed',latest_activity:{type:'DRAFT_PREPARED',label:'Prepared the missing-evidence request for handler review; not sent'}}).split('<details class="ad-peek">')[0];
 assert.match(visible,/Review finished; findings need handler review\./);
 assert.match(visible,/Draft, not sent\./);assert.doesNotMatch(visible,/Six|6 roles/);
 const done=desk.row({...claim,agent_state:'done',run_status:'completed',latest_activity:null}).split('<details class="ad-peek">')[0];
 assert.match(done,/Review finished\./);assert.doesNotMatch(done,/findings need handler review/);
});

test('unstarted and incomplete reviews never acquire completed work or a draft from absent fields',()=>{
 const unstarted={...claim,review_started:false,run_status:null,latest_activity:null,draft_status:'not_prepared',coverage:{note:'0 of 3 original bound sources read. Remaining sources have not been read by this review.'}};
 let visible=desk.row(unstarted).split('<details class="ad-peek">')[0];
 assert.match(visible,/No agent review has started\./);assert.match(visible,/0 of 3 original bound sources read/);
 assert.doesNotMatch(visible,/review roles finished|Review finished|Draft, not sent/);
 visible=desk.row({...unstarted,review_started:true,run_status:'running',draft_status:undefined,coverage:null}).split('<details class="ad-peek">')[0];
 assert.match(visible,/No agent activity is recorded\./);assert.match(visible,/Source coverage is unknown\./);
 assert.doesNotMatch(visible,/review roles finished|Review finished|Draft, not sent/);
});

test('visible work preserves coverage qualifications and escapes persisted reason and activity',()=>{
 const html=desk.row({...claim,why:'A <different> dated notice still needs a receipt.',coverage:{note:'1 of 3 original bound sources read. 1 has limited text coverage. Remaining sources have not been read.'},latest_activity:{type:'AGENT_COMPLETED',label:'Facts <candidate> checked.'}});
 const visible=html.split('<details class="ad-peek">')[0];
 assert.match(visible,/A &lt;different&gt; dated notice still needs a receipt\./);
 assert.match(visible,/Facts &lt;candidate&gt; checked\./);assert.match(visible,/limited text coverage/);assert.match(visible,/Remaining sources have not been read/);
 assert.doesNotMatch(visible,/<different>|<candidate>|review roles finished|Review finished/);
 const opened=desk.row({...claim,latest_activity:{type:'SOURCE_OPENED',label:'Opened the exact original source filename.eml'}});
 assert.match(opened.split('<details class="ad-peek">')[0],/Source opened\./);
 assert.ok(opened.includes('Opened the exact original source filename.eml'));
});

test('desk names the accountable handler and only explicit unassignment changes its displayed wait',()=>{
 const assigned={...claim,owner:'Navish Kumar',accountable:'Navish Kumar',decider:'Navish Kumar'};
 const html=desk.row(assigned);
 assert.match(html,/<span>Handler: Navish Kumar<\/span>/);assert.match(html,/<span class="ad-state">Waiting for you<\/span>/);
 const unassigned=desk.row({...assigned,owner:null,accountable:null,decider:'Unassigned handler'});
 assert.match(unassigned,/data-state="waiting_for_you"/);assert.match(unassigned,/<span class="ad-state">Handler needed<\/span>/);
 assert.match(unassigned,/<span>Handler: Unassigned<\/span>/);assert.doesNotMatch(unassigned,/>Waiting for you</);
 const named=desk.row({...assigned,owner:'Unassigned Family <handler>',accountable:'Unassigned Family <handler>',decider:'Unassigned Family <handler>'});
 assert.match(named,/Handler: Unassigned Family &lt;handler&gt;/);assert.match(named,/>Waiting for you</);assert.doesNotMatch(named,/>Handler needed</);
 const recovery=desk.row({...assigned,owner:null,accountable:null,recovery_required:true});assert.match(recovery,/>Recovery needed</);
});

test('queued and running reviews distinguish earlier draft work from a current unsent draft',()=>{
 for(const run_status of ['queued','running']){
  const saved={...claim,agent_state:'working',review_started:true,run_status,draft_status:'not_prepared',latest_activity:{type:'DRAFT_PREPARED',label:'Prepared the missing-evidence request for handler review; not sent'}};
  const html=desk.row(saved),visible=html.split('<details class="ad-peek">')[0];
  assert.match(visible,/Earlier draft preparation is recorded; no current draft\./);
  assert.doesNotMatch(visible,/Prepared the missing-evidence request|Draft, not sent\.|Review finished/);
  assert.ok(html.includes(saved.latest_activity.label));
  const current=desk.row({...saved,draft_status:'draft_not_sent'}).split('<details class="ad-peek">')[0];
  assert.match(current,/Draft, not sent\./);assert.doesNotMatch(current,/Earlier draft preparation/);
  const unknown=desk.row({...saved,draft_status:undefined}).split('<details class="ad-peek">')[0];
  assert.match(unknown,/current draft status is unknown/);assert.doesNotMatch(unknown,/no current draft\.|Draft, not sent\./);
 }
});

test('source focus follows the exact passage after reordering and never a reused index',()=>{
 const source={artifact_id:'notice',sha256:'original',quote:'The notice was received.',page:2,start:40,end:64};
 const other={...source,start:140,end:164};
 assert.equal(desk.sourceIndex(source,[other,{...source}]),1);
 assert.equal(desk.sourceIndex(source,[other]),-1);
 assert.equal(desk.sourceIndex(source,[{...source,sha256:'replacement'}]),-1);
 const extracted={...source,source_sha256:'source-one',text_sha256:'same-extracted-text'};
 assert.equal(desk.sourceIndex(extracted,[{...extracted,source_sha256:'source-two'}]),-1);
 assert.equal(desk.sourceIndex(source,[{artifact_id:'notice',sha256:'original',locator:{char_end:64,page:2,exact_text:source.quote,char_start:40}}]),0);
});
