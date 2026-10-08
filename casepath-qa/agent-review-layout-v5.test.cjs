'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const ui=require('../casepath/assets/agent-claim-v2.js'),motion=require('../casepath/assets/agent-work-motion-v3.js');
const question=()=>({question_id:'condition:family_home',kind:'condition',prompt:'Does the family-home condition apply?',previewable:true,proposal:{answer_id:'true',reason:'The message describes a family home.'},answers:[{answer_id:'true',label:'Yes, it applies'},{answer_id:'false',label:'No, it does not apply'},{answer_id:'unresolved',label:'Keep it unresolved'}],sources:[]});
const input=id=>({claim:{claim_id:id,owner:'Handler'},agent:{claim_id:id,state:'waiting_for_you',owner:{accountable:'Handler'},questions:[question()],coverage:{},learning:{},activity:[]}});
const work=status=>({scope:'recorded_review_work_not_claim_authority',claim_id:'claim',run_id:'run',status,currentness:'current',last_sequence:8,active_stage:status==='running'?'process':null,headline:'Review recorded. Your decision comes next.',reader:{kind:'reference'},stages:[{id:'sources',label:'Sources',state:'complete',count:3,unit:'sources read',milestone_sequence:2},{id:'process',label:'Process',state:'complete',count:11,unit:'steps mapped',milestone_sequence:8}],milestones:[{sequence:2,stage:'sources',summary:'Exact recorded passage',sources:[{artifact_id:'message',quote:'Exact source text',start:0,end:17}],nodes:[],documents:[],connections:[]},{sequence:8,stage:'process',summary:'Mapped from saved rules; this does not validate the step.',sources:[],nodes:[{node_id:'notice',label:'Check notice'}],documents:[],connections:[]}]});
const comparison=html=>html.match(/<p class="av-answer-comparison">([\s\S]*?)<\/p>/)?.[1]||'';
test('saved comparison is absent without the exact persisted condition and never borrows a proposed graph',()=>{
 const value=input('v5-missing');value.process={process_adopted:false,graph:{nodes:[],conditions:{family_home:{verdict:'true'}}}};
 assert.equal(comparison(ui.render(value)),'');
 value.claim.intake_assessment={claim_assessment:{conditions:{family_home:{verdict:'unresolved'}}}};
 assert.match(comparison(ui.render(value)),/Intake reading · unconfirmed: <strong>Keep it unresolved/);
 value.claim.causal_process={conditions:{other:{verdict:'false'}}};
 assert.equal(comparison(ui.render(value)),'','An adopted graph cannot fall back to an old intake verdict');
 value.claim.causal_process.conditions.family_home={verdict:'invalid'};assert.equal(comparison(ui.render(value)),'');
 value.claim.causal_process.conditions.family_home={verdict:'true'};
 value.agent.questions[0].kind='source_conflict';assert.equal(comparison(ui.render(value)),'');
});
test('stored condition, intake reading and chosen answer are distinct without changing the proposal',()=>{
 const value=input('v5-comparison');value.claim.causal_process={conditions:{family_home:{verdict:'unresolved'}}};
 value.claim.intake_assessment={claim_assessment:{conditions:{family_home:{verdict:'true'}}}};
 const before=structuredClone(value),html=ui.render(value);
 assert.match(comparison(html),/Saved reading · unconfirmed: <strong>Keep it unresolved/);
 assert.match(comparison(html),/Proposed answer: <strong>Yes, it applies<\/strong> · not saved/);
 ui.session(value.claim.claim_id).answers['condition:family_home']='false';
 assert.match(comparison(ui.render(value)),/Your answer: <strong>No, it does not apply<\/strong> · not saved/);
 assert.deepEqual(value,before);
});
test('choosing an answer updates comparison immediately without rerender, focus or an API call',()=>{
 const value=input('v5-live-choice');value.claim.causal_process={conditions:{family_home:{verdict:'true'}}};
 ui.render(value);const listeners=new Map(),current={outerHTML:''},calls=[];
 const root={isConnected:true,querySelector(selector){return selector==='[data-av-claim]'?{dataset:{avClaim:value.claim.claim_id}}:null;},addEventListener(type,fn){listeners.set(type,fn);},removeEventListener(){},contains(){return true;},set innerHTML(_){assert.fail('The focused form was rerendered');}};
 ui.bind({root,api:{request:async()=>{calls.push('request');}}});
 const form={dataset:{avDecision:'condition:family_home'},elements:{answer_id:{value:'false'},reason:{value:'Household changed'},actor:{value:'Handler'}},querySelector(selector){return selector==='.av-answer-comparison'?current:null;}};
 listeners.get('change')({type:'change',target:{matches:()=>false,closest:selector=>selector==='[data-av-decision]'?form:null}});
 assert.match(current.outerHTML,/Saved reading · unconfirmed: <strong>Yes, it applies/);
 assert.match(current.outerHTML,/Your answer: <strong>No, it does not apply/);
 assert.deepEqual(calls,[]);assert.equal(value.agent.questions[0].proposal.answer_id,'true');
});
test('completed history follows the decision while paid-start and active or interrupted work stay reachable',()=>{
 const prior=global.CasePathWorkMotion;global.CasePathWorkMotion=motion;
 try{
  for(const [status,state,after] of [['completed','waiting_for_you',true],['running','working',false],['interrupted','paused',false]]){
   const value=input('v5-order-'+status);value.agent.state=state;value.agent.live_work=work(status);
   value.agent.live_review={available:true,can_start:true,model:'model',context_sha256:'a'.repeat(64),run_cost_limit_usd:.01};
   const html=ui.render(value),decision=html.indexOf('class="av-decision-mount"'),review=html.indexOf('class="av-live-work"'),launch=html.indexOf('data-av-live-start');
   assert.ok(launch>=0&&launch<decision);assert.equal(review>decision,after);
   assert.equal([...html.matchAll(/data-av-live-start/g)].length,1);
  }
 }finally{global.CasePathWorkMotion=prior;}
});
test('stage selectors expose every recorded count while selected detail stays visibly readable and unvalidated',()=>{
 const value=work('completed');const html=motion.markup(value,{stage:'process'});
 assert.match(html,/aria-label="Sources review, Review recorded, 3 sources read"/);
 assert.match(html,/aria-label="Process review, Review recorded, 11 steps mapped"/);
 assert.equal([...html.matchAll(/class="av-work-stage-count"/g)].length,1);
 assert.match(html,/class="av-work-stage-count">11 steps mapped/);
 assert.match(html,/this does not validate the step/);assert.doesNotMatch(html,/>Checked</);
 assert.ok(html.indexOf('class="av-live-reader"')>html.indexOf('id="av-work-finding"'));
});
const reviewBeforeDecision=html=>html.indexOf('class="av-live-work"')<html.indexOf('class="av-decision-mount"');
const liveDisclosureOpen=html=>/class="av-live-details" data-av-disclosure="live-work" open/.test(html);
function disclosureRoot(id,{focused=false,afterFocus='unchanged'}={}){
 const listeners=new Map(),moved=[],document={body:{tagName:'BODY'}},other={id:'other-control'};
 const summary={id:'av-live-summary',isConnected:true,ownerDocument:document,focus(options){this.focused=options;document.activeElement=this;},scrollIntoView(options){this.scrolled=options;}};
 document.activeElement=focused?summary:other;
 const decision={after(node){moved.push(node);if(afterFocus==='body')document.activeElement=document.body;else if(afterFocus==='none')document.activeElement=null;else if(afterFocus==='other')document.activeElement=other;}};
 return {listeners,moved,summary,document,other,isConnected:true,innerHTML:'',querySelector(selector){return selector==='[data-av-claim]'?{dataset:{avClaim:id}}:selector==='#av-live-summary'?summary:selector==='.av-decision-mount'?decision:null;},addEventListener(type,fn){listeners.set(type,fn);},removeEventListener(type,fn){if(listeners.get(type)===fn)listeners.delete(type);},contains(){return true;}};
}
function nativeDisclosure(root,key,open=false){
 const details={dataset:{avDisclosure:key},open,querySelector:selector=>selector==='summary'?root.summary:null};
 root.summary.parentElement=details;
 return {details,activation:{target:{closest:selector=>selector==='summary'?root.summary:null},isTrusted:true,defaultPrevented:false,preventDefault(){assert.fail('Native summary activation must not be cancelled');}}};
}
test('native pointer and keyboard summary activation survive refresh before the queued toggle',()=>{
 for(const detail of [1,0]){
  const value=input('v5-native-summary-'+detail),root=disclosureRoot(value.claim.claim_id),calls=[];
  ui.render(value);ui.bind({root,api:{request:async()=>calls.push('unexpected request')}});
  const {details,activation}=nativeDisclosure(root,'supervision');activation.detail=detail;
  root.listeners.get('click')(activation);
  assert.equal(details.open,false,'The browser retains ownership of the native toggle');
  assert.match(ui.render(value),/class="av-supervision" data-av-disclosure="supervision" open/);
  details.open=true;root.listeners.get('toggle')({target:details});
  root.listeners.get('click')(activation);
  assert.equal(details.open,true,'Closing also waits for native activation');
  assert.doesNotMatch(ui.render(value),/class="av-supervision" data-av-disclosure="supervision" open/);
  details.open=false;root.listeners.get('toggle')({target:details});
  root.listeners.get('click')({...activation,defaultPrevented:true});
  assert.equal(ui.session(value.claim.claim_id).open.has('supervision'),false);
  assert.equal(root.innerHTML,'');assert.equal(root.summary.focused,undefined);assert.deepEqual(calls,[]);
 }
});
test('detached targets, replaced roots and obsolete toggle bindings cannot erase current disclosure intent',()=>{
 for(const stale of ['target','root','binding']){
  const value=input('v5-stale-toggle-'+stale),root=disclosureRoot(value.claim.claim_id);
  ui.render(value);ui.bind({root});const oldToggle=root.listeners.get('toggle');
  const {details}=nativeDisclosure(root,'supervision',true);oldToggle({target:details});
  assert.equal(ui.session(value.claim.claim_id).open.has('supervision'),true);
  if(stale==='target')root.contains=node=>node!==details;
  else if(stale==='root')root.isConnected=false;
  else ui.bind({root});
  details.open=false;oldToggle({target:details});
  assert.equal(ui.session(value.claim.claim_id).open.has('supervision'),true,stale+' event must be ignored');
 }
});
test('native completed-review close saves placement before refresh but moves only on the real toggle',()=>{
 const prior=global.CasePathWorkMotion;global.CasePathWorkMotion=motion;
 try{
  const value=input('v5-native-review-close'),root=disclosureRoot(value.claim.claim_id,{focused:true,afterFocus:'body'});
  value.agent.state='working';value.agent.live_work=work('running');ui.render(value);ui.bind({root});
  value.agent.state='waiting_for_you';value.agent.live_work.status='completed';ui.render(value);
  const {details,activation}=nativeDisclosure(root,'live-work',true);
  root.listeners.get('click')(activation);
  assert.equal(details.open,true);assert.equal(root.moved.length,0);assert.equal(root.summary.focused,undefined);
  const next=ui.render(value);assert.equal(reviewBeforeDecision(next),false);assert.equal(liveDisclosureOpen(next),false);
  details.open=false;root.listeners.get('toggle')({target:details});
  assert.equal(root.moved[0],details);assert.equal(root.document.activeElement,root.summary);
  assert.deepEqual(root.summary.focused,{preventScroll:true});
 }finally{global.CasePathWorkMotion=prior;}
});
test('a review observed working stays open and above the decision at completion until explicit close',()=>{
 const prior=global.CasePathWorkMotion;global.CasePathWorkMotion=motion;
 try{
  const value=input('v5-anchor'),root=disclosureRoot(value.claim.claim_id),calls=[];
  value.agent.state='working';value.agent.live_work=work('running');
  let html=ui.render(value);assert.ok(reviewBeforeDecision(html));assert.ok(liveDisclosureOpen(html));
  ui.bind({root,api:{request:async()=>{calls.push('unexpected request');}}});
  value.agent.state='waiting_for_you';value.agent.live_work={...value.agent.live_work,status:'completed',active_stage:null};
  const before=structuredClone(value);html=ui.render(value);
  assert.ok(reviewBeforeDecision(html));assert.ok(liveDisclosureOpen(html));
  assert.deepEqual(value,before);assert.deepEqual(calls,[]);assert.equal(root.summary.focused,undefined);
  const closed={dataset:{avDisclosure:'live-work'},open:false,querySelector:()=>root.summary};
  root.listeners.get('toggle')({target:closed});
  assert.equal(root.moved[0],closed,'The same native disclosure moves only on explicit close');
  assert.equal(root.innerHTML,'','Closing does not replace the focused form or source controls');assert.equal(root.summary.focused,undefined);
  html=ui.render(value);assert.equal(reviewBeforeDecision(html),false);assert.equal(liveDisclosureOpen(html),false);
  root.listeners.get('toggle')({target:{dataset:{avDisclosure:'live-work'},open:true,querySelector:()=>root.summary}});
  html=ui.render(value);assert.equal(reviewBeforeDecision(html),false);assert.ok(liveDisclosureOpen(html));assert.deepEqual(calls,[]);
 }finally{global.CasePathWorkMotion=prior;}
});
test('closing completed history restores only native summary focus lost by its move and reveals that summary',()=>{
 const prior=global.CasePathWorkMotion;global.CasePathWorkMotion=motion;
 try{
  for(const afterFocus of ['body','none','unchanged']){
   const value=input('v5-close-focus-'+afterFocus),root=disclosureRoot(value.claim.claim_id,{focused:true,afterFocus}),calls=[];
   value.agent.state='working';value.agent.live_work=work('running');ui.render(value);
   ui.bind({root,api:{request:async()=>calls.push('unexpected request')}});
   value.agent.state='waiting_for_you';value.agent.live_work.status='completed';ui.render(value);
   const before=structuredClone(value),closed={dataset:{avDisclosure:'live-work'},open:false,querySelector:()=>root.summary};
   root.listeners.get('toggle')({target:closed});
   assert.equal(root.moved[0],closed);assert.equal(root.document.activeElement,root.summary);
   assert.deepEqual(root.summary.focused,afterFocus==='unchanged'?undefined:{preventScroll:true});
   assert.deepEqual(root.summary.scrolled,{block:'nearest',inline:'nearest',behavior:'instant'});
   assert.equal(root.innerHTML,'');assert.deepEqual(calls,[]);assert.deepEqual(value,before);
  }
 }finally{global.CasePathWorkMotion=prior;}
});
test('moving completed history never takes focus or scroll from another control',()=>{
 const prior=global.CasePathWorkMotion;global.CasePathWorkMotion=motion;
 try{
  for(const [focused,afterFocus] of [[true,'other'],[false,'body'],[false,'unchanged']]){
   const value=input('v5-close-no-steal-'+focused+'-'+afterFocus),root=disclosureRoot(value.claim.claim_id,{focused,afterFocus});
   value.agent.state='working';value.agent.live_work=work('running');ui.render(value);ui.bind({root});
   value.agent.state='waiting_for_you';value.agent.live_work.status='completed';ui.render(value);
   root.listeners.get('toggle')({target:{dataset:{avDisclosure:'live-work'},open:false,querySelector:()=>root.summary}});
   assert.equal(root.document.activeElement,afterFocus==='body'?root.document.body:root.other);
   assert.equal(root.summary.focused,undefined);assert.equal(root.summary.scrolled,undefined);
  }
 }finally{global.CasePathWorkMotion=prior;}
});
test('closing during active work remains closed across updates and releases placement on completion',()=>{
 const prior=global.CasePathWorkMotion;global.CasePathWorkMotion=motion;
 try{
  const value=input('v5-active-close'),root=disclosureRoot(value.claim.claim_id);
  value.agent.state='working';value.agent.live_work=work('running');ui.render(value);ui.bind({root});
  root.listeners.get('toggle')({target:{dataset:{avDisclosure:'live-work'},open:false}});
  assert.equal(liveDisclosureOpen(ui.render(value)),false);
  value.agent.live_work={...value.agent.live_work,last_sequence:9};assert.equal(liveDisclosureOpen(ui.render(value)),false);
  value.agent.state='waiting_for_you';value.agent.live_work.status='completed';
  const html=ui.render(value);assert.equal(reviewBeforeDecision(html),false);assert.equal(liveDisclosureOpen(html),false);
 }finally{global.CasePathWorkMotion=prior;}
});
test('anchors do not cross runs or visits and release preserves unsaved answers, reasons and requests',()=>{
 const prior=global.CasePathWorkMotion;global.CasePathWorkMotion=motion;
 try{
  const value=input('v5-anchor-visit');value.agent.state='working';value.agent.live_work=work('running');ui.render(value);
  const s=ui.session(value.claim.claim_id);s.answers={'condition:family_home':'false'};s.reasons={'condition:family_home':'Saved locally'};s.pending={kind:'live',key:'same-request'};
  value.agent.state='waiting_for_you';value.agent.live_work.status='completed';assert.ok(reviewBeforeDecision(ui.render(value)));
  ui.releaseReviewPosition(value.claim.claim_id);
  assert.equal(reviewBeforeDecision(ui.render(value)),false);
  assert.deepEqual(s.answers,{'condition:family_home':'false'});assert.deepEqual(s.reasons,{'condition:family_home':'Saved locally'});assert.deepEqual(s.pending,{kind:'live',key:'same-request'});
  value.agent.state='working';value.agent.live_work={...work('running'),run_id:'next'};assert.ok(reviewBeforeDecision(ui.render(value)));
  value.agent.state='waiting_for_you';value.agent.live_work={...work('completed'),run_id:'new-cold-completed'};assert.equal(reviewBeforeDecision(ui.render(value)),false);
 }finally{global.CasePathWorkMotion=prior;}
});
test('reopening the same still-active review protects its visible position through completion',()=>{
 const prior=global.CasePathWorkMotion;global.CasePathWorkMotion=motion;
 try{
  const value=input('v5-active-reopen'),root=disclosureRoot(value.claim.claim_id);
  value.agent.state='working';value.agent.live_work=work('running');ui.render(value);ui.bind({root});
  root.listeners.get('toggle')({target:{dataset:{avDisclosure:'live-work'},open:false}});
  root.listeners.get('toggle')({target:{dataset:{avDisclosure:'live-work'},open:true}});
  value.agent.state='waiting_for_you';value.agent.live_work.status='completed';
  const html=ui.render(value);assert.ok(reviewBeforeDecision(html));assert.ok(liveDisclosureOpen(html));
 }finally{global.CasePathWorkMotion=prior;}
});
test('the live-start price is explicit while model and scope are in a closed native disclosure',()=>{
 const value=input('v5-compact-live-start');value.agent.live_review={available:true,can_start:true,model:'configured/provider-model',context_sha256:'a'.repeat(64),run_cost_limit_usd:.02};
 const html=ui.render(value),launch=html.slice(html.indexOf('class="av-live-launch"'),html.indexOf('class="av-decision-mount"'));
 assert.match(launch,/up to \$0\.02 per review/);assert.match(launch,/data-av-live-start>Review sources live/);
 assert.match(launch,/data-av-disclosure="live-configuration"><summary id="av-live-config-summary">Review details/);
 const details=launch.match(/<details class="av-live-config"[\s\S]*?<\/details>/)?.[0];
 assert.match(details,/Model: configured\/provider-model/);assert.match(details,/Reads synthetic sources\. Process changes need your approval\./);
 assert.ok(launch.indexOf('up to $0.02 per review')<launch.indexOf('<details'));
});
