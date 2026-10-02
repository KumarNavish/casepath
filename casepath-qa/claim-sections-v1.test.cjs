'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');

// Execute the production navigation functions without starting the claim API.
function fixture(){
 const names=['overview','process','documents'],storage=new Map();
 const tabs=names.map(name=>({dataset:{claimSection:name},attrs:{},setAttribute(k,v){this.attrs[k]=v},focus(){this.focused=true},closest(){return this}}));
 const panes=names.map(name=>({dataset:{claimPane:name},fields:[{value:'Unsaved handler explanation'}]}));
 const column={scrollTop:150},rail={setAttribute(){},removeAttribute(){}},toggle={setAttribute(k,v){this[k]=v}};
 const panel={dataset:{},querySelector:s=>s==='.cp-work-column'?column:null,querySelectorAll:s=>s==='[data-claim-section]'?tabs:s==='[data-claim-pane]'?panes:s==='[data-open-inspector]'?[toggle]:[]};
 Object.defineProperty(panel,'innerHTML',{set(){throw Error('Navigation must keep mounted forms');}});
 const motions=[];
 const context={state:{detail:{state:{claim_id:'claim-a'}},claimSection:'overview',sectionScroll:{},inspectorOpen:false,motion:0},window:{CasePathMotion:{enter(...args){motions.push(args);}}},
  sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
  $:s=>({'#cwDetailPanel':panel,'#cwDetail':{hidden:false},'.cp-source-rail':rail}[s]),root:{querySelector(){return null}},closeDetail(){throw Error('Unexpected close');}};
 vm.createContext(context);
 for(const [from,to] of [['savePresentation','syncReasoning'],['selectClaimSection','showWorkspaceSection'],['applyInspectorState','openInspector'],['workspaceKeyboard','packetSelection']]){
  const start=source.indexOf('  function '+from+'('),end=source.indexOf('  function '+to+'(');
  assert.ok(start>=0&&end>start);vm.runInContext(source.slice(start,end),context);
 }
 return {context,tabs,panes,column,rail,toggle,motions};
}

test('switching sections preserves mounted edits and remembers each scroll position',()=>{
 const {context:c,tabs,panes,column,motions}=fixture(),fields=panes.map(p=>p.fields[0]);
 c.selectClaimSection('documents');
 assert.deepEqual(panes.map(p=>p.hidden),[true,true,false]);
 assert.deepEqual(panes.map(p=>p.inert),[true,true,false]);
 assert.deepEqual(tabs.map(t=>t.attrs['aria-selected']),['false','false','true']);
 assert.deepEqual(tabs.map(t=>t.tabIndex),[-1,-1,0]);
 assert.equal(column.scrollTop,0);column.scrollTop=90;
 c.selectClaimSection('overview');assert.equal(column.scrollTop,150);
 c.selectClaimSection('documents');assert.equal(column.scrollTop,90);
 assert.equal(motions.length,3);c.selectClaimSection('documents');assert.equal(motions.length,3);
 panes.forEach((pane,index)=>{assert.equal(pane.fields[0],fields[index]);assert.equal(pane.fields[0].value,'Unsaved handler explanation');});
});

test('Arrow keys wrap with roving focus and Home and End activate their tabs',()=>{
 const {context:c,tabs}=fixture();
 const press=(index,key)=>{let prevented=false;c.workspaceKeyboard({target:tabs[index],key,preventDefault(){prevented=true}});assert.ok(prevented);};
 press(0,'ArrowLeft');assert.equal(c.state.claimSection,'documents');assert.ok(tabs[2].focused);
 press(2,'ArrowRight');assert.equal(c.state.claimSection,'overview');assert.ok(tabs[0].focused);
 press(0,'End');assert.equal(c.state.claimSection,'documents');
 press(2,'Home');assert.equal(c.state.claimSection,'overview');
});

test('section choice is claim-scoped and restoring a source never opens its panel',()=>{
 const {context:c,rail,toggle}=fixture();
 c.state.sourceSelection={kind:'artifact',index:1};c.state.inspectorOpen=true;c.selectClaimSection('documents');
 c.state.detail={state:{claim_id:'claim-b'}};c.recoverPresentation('claim-b');assert.equal(c.state.claimSection,'overview');
 c.selectClaimSection('process');c.state.detail={state:{claim_id:'claim-a'}};c.recoverPresentation('claim-a');
 assert.equal(c.state.claimSection,'documents');assert.equal(c.state.sourceSelection.index,1);assert.equal(c.state.inspectorOpen,false);
 c.applyInspectorState();assert.ok(rail.hidden&&rail.inert);assert.equal(toggle['aria-expanded'],'false');
 c.state.inspectorOpen=true;c.applyInspectorState();assert.equal(rail.hidden,false);assert.equal(rail.inert,false);assert.equal(toggle['aria-expanded'],'true');
});

test('the queue omits the legacy paper-method loader while both legacy modes retain it',()=>{
 const index=fs.readFileSync(path.join(__dirname,'../casepath/index.html'),'utf8');
 const bootstrap=index.match(/<script>([\s\S]*?)<\/script>/)[1];
 for(const [search,expected] of [['',0],['?foundation=live-v1',1],['?journey=legacy-v20',1],['?journey=insurance-v1',1]]){
  const inserted=[],document={documentElement:{dataset:{}},createElement:()=>({}),querySelector:()=>({content:'assets/process-evidence-v2.js?sha256=verified'}),head:{append:script=>inserted.push(script)}};
  vm.runInNewContext(bootstrap,{location:{protocol:'http:',origin:'http://localhost',search},document,window:{},URLSearchParams,sessionStorage:{getItem(){return 'ui-sessionvalid'},setItem(){}},fetch(){return Promise.resolve({ok:true,json(){return {}}})}});
  assert.equal(inserted.length,expected,search||'default queue');
 }
});

function motionFixture(){
 const agent=fs.readFileSync(path.join(__dirname,'../casepath/assets/agent-work-v1.js'),'utf8');
 const listeners={},media={matches:false,addEventListener(name,callback){this[name]=callback;}},animations=[];
 const document={hidden:false,addEventListener(name,callback){listeners[name]=callback;}};
 let reads=0;
 const window={matchMedia:()=>media,getComputedStyle(){reads++;return {opacity:'.4',transform:'matrix(1, 0, 0, 1, 0, 2)'};}};
 const c={window,document};vm.createContext(c);
 vm.runInContext(agent.slice(agent.indexOf('  function createMotion('),agent.indexOf('  const ROOT=')),c);
 const element=()=>({isConnected:true,hidden:false,closest(){return this.hidden?this:null;},animate(frames,options){let resolve;const job={frames,options,cancelled:0,cancel(){this.cancelled++;},finished:new Promise(done=>resolve=done),finish:()=>resolve()};animations.push(job);return job;}});
 return {motion:window.CasePathMotion,element,animations,listeners,media,document,reads:()=>reads};
}

test('motion deduplicates saved events and interrupted entrances continue from their current position',async()=>{
 const f=motionFixture(),node=f.element();
 f.motion.enter(node,'work:run:7');f.motion.enter(f.element(),'work:run:7');assert.equal(f.animations.length,1);
 f.motion.enter(node,'pane:2','left');assert.equal(f.animations[0].cancelled,1);assert.equal(f.reads(),1);
 assert.equal(f.animations[1].frames[0].opacity,'.4');assert.equal(f.animations[1].frames[0].transform,'matrix(1, 0, 0, 1, 0, 2)');
 f.animations[0].finish();await Promise.resolve();
 f.motion.enter(node,'pane:3');assert.equal(f.animations[1].cancelled,1);
 f.animations[2].finish();await Promise.resolve();
 f.motion.enter(node,'source:4','left');assert.equal(f.reads(),2);assert.equal(f.animations[3].frames[0].transform,'translateX(-10px)');assert.equal(f.animations[3].options.duration,220);
});

test('motion stops for reduced motion and keyboard use and never replays hidden arrivals',()=>{
 const f=motionFixture(),node=f.element();
 f.motion.enter(node,'pane:1');f.media.matches=true;f.media.change();assert.equal(f.animations[0].cancelled,1);
 f.motion.enter(node,'pane:2');assert.equal(f.animations.length,1);
 f.media.matches=false;f.media.change();f.motion.enter(node,'pane:2');assert.equal(f.animations.length,1);
 f.listeners.keydown();f.motion.enter(node,'pane:3');assert.equal(f.animations.length,1);
 f.listeners.pointerdown();f.motion.enter(node,'pane:4');assert.equal(f.animations.length,2);
 node.hidden=true;f.motion.enter(node,'work:run:8');node.hidden=false;f.motion.enter(node,'work:run:8');assert.equal(f.animations.length,2);
 f.motion.enter(node,'pane:5');f.document.hidden=true;f.listeners.visibilitychange();assert.equal(f.animations[2].cancelled,1);
});
