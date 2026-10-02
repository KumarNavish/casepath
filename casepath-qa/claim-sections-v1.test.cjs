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
 const context={state:{detail:{state:{claim_id:'claim-a'}},claimSection:'overview',sectionScroll:{},inspectorOpen:false},
  sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
  $:s=>({'#cwDetailPanel':panel,'#cwDetail':{hidden:false},'.cp-source-rail':rail}[s]),root:{querySelector(){return null}},closeDetail(){throw Error('Unexpected close');}};
 vm.createContext(context);
 for(const [from,to] of [['savePresentation','syncReasoning'],['selectClaimSection','showWorkspaceSection'],['applyInspectorState','openInspector'],['workspaceKeyboard','packetSelection']]){
  const start=source.indexOf('  function '+from+'('),end=source.indexOf('  function '+to+'(');
  assert.ok(start>=0&&end>start);vm.runInContext(source.slice(start,end),context);
 }
 return {context,tabs,panes,column,rail,toggle};
}

test('switching sections preserves mounted edits and remembers each scroll position',()=>{
 const {context:c,tabs,panes,column}=fixture(),fields=panes.map(p=>p.fields[0]);
 c.selectClaimSection('documents');
 assert.deepEqual(panes.map(p=>p.hidden),[true,true,false]);
 assert.deepEqual(panes.map(p=>p.inert),[true,true,false]);
 assert.deepEqual(tabs.map(t=>t.attrs['aria-selected']),['false','false','true']);
 assert.deepEqual(tabs.map(t=>t.tabIndex),[-1,-1,0]);
 assert.equal(column.scrollTop,0);column.scrollTop=90;
 c.selectClaimSection('overview');assert.equal(column.scrollTop,150);
 c.selectClaimSection('documents');assert.equal(column.scrollTop,90);
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
