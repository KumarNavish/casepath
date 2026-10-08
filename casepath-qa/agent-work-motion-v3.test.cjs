'use strict';
const {test} = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const modulePath = '../casepath/assets/agent-work-motion-v3.js', ui = require(modulePath);
function projection(sequence = 1, extra = {}) {
  return {claim_id:'claim', run_id:'run', status:'running', currentness:'current', last_sequence:sequence,
    headline:'Reading the source', active_stage:'sources', scope:'recorded_review_work_not_claim_authority',
    reader:{kind:'reference'}, stages:[{id:'sources',label:'Sources',state:'working',count:1,unit:'sources read',milestone_sequence:sequence}],
    milestones:[{sequence,stage:'sources',summary:'One exact quotation',sources:[{artifact_id:'message',quote:'30. Juni <unconfirmed>',start:0,end:22}],nodes:[],documents:[],connections:[]}], ...extra};
}
function harness() {
  const listeners = {}, calls = [], cancellations = [];
  const reduced = {matches:false,addEventListener(type,fn){listeners.reduced=fn;},removeEventListener(){delete listeners.reduced;}};
  const document = {hidden:false,activeElement:null,addEventListener(type,fn){listeners[type]=fn;},removeEventListener(type){delete listeners[type];}};
  const global = {document,innerHeight:900,matchMedia:()=>reduced};
  vm.runInNewContext(fs.readFileSync(require.resolve(modulePath),'utf8'),global);
  const node = {isConnected:true,contains:()=>false,closest:()=>null,getBoundingClientRect:()=>({width:200,height:40,top:20,bottom:60}),animate(frames,options){calls.push({frames,options});return {cancel(){cancellations.push(true);},finished:new Promise(()=>{})};}};
  return {ui:global.CasePathWorkMotion,root:{querySelector:()=>node},node,listeners,calls,cancellations,reduced,document};
}
test('milestones preserve exact quotes and native source links without rendering raw reasoning',()=>{
  const seen=[],work=projection();work.reasoning='PRIVATE TOKEN';
  const html=ui.markup(work,{sourceLink:source=>{seen.push(source);return '<button data-av-source="0">Customer message</button>';}});
  assert.equal(seen[0],work.milestones[0].sources[0]);
  assert.match(html,/30\. Juni &lt;unconfirmed&gt;/);assert.match(html,/data-av-source="0"/);
  assert.match(html,/data-av-work-stage="sources" aria-pressed="true"/);
  assert.doesNotMatch(html,/PRIVATE TOKEN|setTimeout|spinner|typing/);
  assert.equal(ui.markup({...work,scope:'unverified'}),'');
});
test('a recorded step requirement is connected; historical work never opens the current graph',()=>{
  const work=projection(8,{active_stage:'documents',stages:[{id:'documents',label:'Documents',state:'complete',count:1,unit:'requirements checked',milestone_sequence:8}]});
  work.milestones=[{sequence:8,stage:'documents',summary:'The notice is required here.',sources:[],nodes:[{node_id:'notice',label:'Notice step'}],documents:[{document_type:'notice',label:'Notice copy'}],connections:[{from:'node:notice',to:'obligation:notice',relation:'required_by_process'}]}];
  const links={nodeLink:()=>'<button data-node>Node</button>',documentLink:()=>'<button data-document>Document</button>'};
  assert.match(ui.markup(work,links),/data-recorded-relation="required_by_process"/);
  assert.match(ui.markup(work,links),/data-node/);
  assert.doesNotMatch(ui.markup({...work,currentness:'historical'},links),/data-node|data-document/);
  work.milestones[0].connections=[];assert.doesNotMatch(ui.markup(work),/class="av-live-relation"|data-recorded-relation/);
});
test('document connector respects required-now, optional and ambiguous recorded timing',()=>{
  const work=projection(8,{active_stage:'documents',stages:[{id:'documents',label:'Documents',state:'complete',count:1,unit:'requirements checked',milestone_sequence:8}]});
  work.milestones=[{sequence:8,stage:'documents',summary:'Recorded document timing',sources:[],nodes:[{node_id:'notice',label:'Notice step'}],documents:[],connections:[{from:'node:notice',to:'obligation:notice',relation:'required_by_process'}]}];
  for(const [state,needed_now,label] of [['missing',true,'requires'],['optional',false,'may use'],['conditional',false,'lists'],['missing',false,'lists'],['unknown',undefined,'lists']]){
    work.milestones[0].documents=[{document_type:'notice',label:'Notice copy',state,needed_now}];
    const html=ui.markup(work);
    assert.match(html,new RegExp(`class="av-live-relation">${label}</span>`));
    assert.match(html,/data-recorded-relation="required_by_process"/);
    if(needed_now!==true)assert.doesNotMatch(html,/>requires</);
  }
});
test('retained passage or step is labelled as recorded detail without pretending it just arrived',()=>{
  const work=projection(3);work.stages[0].milestone_sequence=1;work.stages[0].latest_milestone_sequence=3;
  work.milestones=[{...work.milestones[0],sequence:1},{...work.milestones[0],sequence:3,sources:[],summary:'Later source integrity read'}];
  const html=ui.markup(work,{sourceLink:()=>'<button>Exact passage</button>'});
  assert.match(html,/Last cited passage/);assert.match(html,/data-av-work-sequence="1"/);assert.match(html,/data-av-work-arrival="3"/);
  assert.match(html,/Exact passage/);assert.doesNotMatch(html,/Later source integrity read/);
  work.stages[0]={...work.stages[0],id:'process',label:'Process'};work.active_stage='process';
  assert.match(ui.markup(work),/Last mapped step/);
});
test('cold loads, replayed updates, previous runs and out-of-order packets do not animate',()=>{
  const h=harness();h.ui.observe(h.root,projection(4));assert.equal(h.calls.length,0);
  h.ui.observe(h.root,projection(4));h.ui.observe(h.root,projection(2));h.ui.observe(h.root,projection(4));assert.equal(h.calls.length,0);
  h.ui.observe(h.root,projection(1,{run_id:'new'}));assert.equal(h.calls.length,0);
  h.ui.observe(h.root,projection(2,{run_id:'new',currentness:'historical'}));assert.equal(h.calls.length,0);
  h.ui.observe(h.root,projection(3,{run_id:'new'}));assert.equal(h.calls.length,0);
});
test('a newly persisted milestone moves once, using only transform and opacity below250ms',()=>{
  const h=harness();h.ui.observe(h.root,projection());h.ui.observe(h.root,projection(3));assert.equal(h.calls.length,2);
  for(const call of h.calls){assert.ok(call.options.duration<=250);for(const frame of call.frames)assert.deepEqual(Object.keys(frame).sort(),['opacity','transform']);}
  h.ui.observe(h.root,projection(3));assert.equal(h.calls.length,2);
  h.ui.observe(h.root,projection(4,{milestones:[]}));assert.equal(h.calls.length,2);
});
test('reduced motion, keyboard use and hidden surfaces cancel and consume arrivals without replay',()=>{
  const h=harness();h.ui.observe(h.root,projection());h.ui.observe(h.root,projection(2));
  h.reduced.matches=true;h.listeners.reduced();assert.ok(h.cancellations.length);
  h.ui.observe(h.root,projection(3));assert.equal(h.calls.length,2);
  h.reduced.matches=false;h.ui.observe(h.root,projection(3));assert.equal(h.calls.length,2);
  h.listeners.keydown();h.ui.observe(h.root,projection(4));assert.equal(h.calls.length,2);
  h.listeners.pointerdown();h.document.hidden=true;h.listeners.visibilitychange();h.ui.observe(h.root,projection(5));assert.equal(h.calls.length,2);
  h.document.hidden=false;h.ui.observe(h.root,projection(5));assert.equal(h.calls.length,2);
  h.ui.observe(h.root,projection(6));assert.equal(h.calls.length,4);
  h.ui.dispose();assert.deepEqual(Object.keys(h.listeners),[]);
});
test('focused, detached, inert and offscreen content stays still; no focus or scrolling occurs',()=>{
  for(const modify of [h=>h.node.contains=()=>true,h=>h.node.isConnected=false,h=>h.node.closest=()=>({}),h=>h.node.getBoundingClientRect=()=>({width:100,height:40,top:1000,bottom:1040})]){
    const h=harness();h.node.focus=()=>assert.fail('focus moved');h.node.scrollIntoView=()=>assert.fail('scrolled');
    h.ui.observe(h.root,projection());modify(h);h.ui.observe(h.root,projection(2));assert.equal(h.calls.length,0);
  }
});
