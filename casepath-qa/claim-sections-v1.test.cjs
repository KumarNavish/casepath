'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');

// Execute the production navigation functions without starting the claim API.
function fixture({mobile=false}={}){
 const names=['overview','process','documents'],storage=new Map();
 const tabs=names.map(name=>({dataset:{claimSection:name},attrs:{},setAttribute(k,v){this.attrs[k]=v},focus(){this.focused=true},closest(selector){return selector==='[data-claim-section]'?this:null}}));
 const panes=names.map(name=>({dataset:{claimPane:name},fields:[{value:'Unsaved handler explanation'}]}));
 const column={scrollTop:150},rail={setAttribute(){},removeAttribute(){}},toggle={setAttribute(k,v){this[k]=v}};
 const panel={dataset:{},scrollTop:150,querySelector:s=>s==='.cp-work-column'?column:null,querySelectorAll:s=>s==='[data-claim-section]'?tabs:s==='[data-claim-pane]'?panes:s==='[data-open-inspector]'?[toggle]:[]};
 Object.defineProperty(panel,'innerHTML',{set(){throw Error('Navigation must keep mounted forms');}});
 const motions=[],listeners={};
 const context={state:{detail:{state:{claim_id:'claim-a'}},claimSection:'overview',sectionScroll:{},inspectorOpen:false,motion:0},window:{CasePathMotion:{enter(...args){motions.push(args);}}},
  mobileWorkbench:{matches:mobile},
  sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value)},
  $:s=>({'#cwDetailPanel':panel,'#cwDetail':{hidden:false},'.cp-source-rail':rail}[s]),root:{querySelector(){return null},addEventListener(type,handler){listeners[type]=handler;}},closeDetail(){throw Error('Unexpected close');}};
 vm.createContext(context);
 for(const [from,to] of [['claimScrollRegion','savePresentation'],['savePresentation','syncReasoning'],['selectClaimSection','showWorkspaceSection'],['applyInspectorState','openInspector'],['workspaceKeyboard','packetSelection']]){
  const start=source.indexOf('  function '+from+'('),end=source.indexOf('  function '+to+'(');
  assert.ok(start>=0&&end>start);vm.runInContext(source.slice(start,end),context);
 }
 return {context,tabs,panes,panel,column,rail,toggle,motions,listeners};
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

test('mobile sections restore the page scroll owner and ignore nested source scrolling',()=>{
 const {context:c,panel,column,rail,panes,listeners}=fixture({mobile:true}),fields=panes.map(p=>p.fields[0]);
 panel.scrollTop=212;listeners.scroll({target:panel});
 assert.equal(c.state.sectionScroll.overview,212);
 column.scrollTop=48;listeners.scroll({target:column});
 rail.scrollTop=67;listeners.scroll({target:rail});
 assert.equal(c.state.sectionScroll.overview,212);
 c.selectClaimSection('documents');assert.equal(panel.scrollTop,0);
 panel.scrollTop=91;listeners.scroll({target:panel});
 c.selectClaimSection('overview');assert.equal(panel.scrollTop,212);
 c.selectClaimSection('documents');assert.equal(panel.scrollTop,91);
 assert.equal(column.scrollTop,48,'Mobile navigation must not restore the desktop column');
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

function contextualPaneFixture({deferred=false}={}){
 const f=fixture(),c=f.context,selected={selected:'a',expanded:true,mode:null,preview:{},error:'Earlier view error'};
 const process={claim_id:'claim-a',workspace_revision:4,workspace_state_sha256:'saved-state',graph:{nodes:[{node_id:'a'},{node_id:'b'}],edges:[{edge_id:'e',source_node_id:'a',target_node_id:'b'}]},evaluation:{documents:[{document_type:'notice',required_at_node_ids:['b']}]}};
 c.state.detail={state:{claim_id:'claim-a',revision:4,state_sha256:'saved-state',intake_assessment:{}},artifacts:[]};c.state.detailEpoch=1;c.state.causal=deferred?null:process;
 const panel=c.$('#cwDetailPanel'),originalQuery=panel.querySelector,focuses=[],clicks=[],requests=[],renders=[];let nodes;
 const target=(kind)=>({kind,parentElement:null,closest(){return null;},scrollIntoView(){this.scrolled=true;},focus(){focuses.push(this);}});
 function mount(){
  const docRow=target('requirement:notice'),node=target('node:'+selected.selected),field=target(selected.mode||'field'),form={querySelector:()=>field};
  const control=(kind,mode)=>({...target(kind),click(){clicks.push(kind);selected.mode=mode;mount();}});
  nodes={docRow,node,field,form,docControl:control('review:notice','document:notice'),edgeControl:control('edge:e','edge:e')};
  panel.querySelector=selector=>{
   if(selector==='#cpPane-documents [data-document-type="notice"]')return nodes.docRow;
   if(selector===`[data-causal-node="${selected.selected}"]`)return nodes.node;
   if(selector==='.cp-process-inspector [data-causal-document-open="notice"]')return selected.selected==='b'?nodes.docControl:null;
   if(selector==='.cp-process-inspector [data-causal-edge="e"]')return nodes.edgeControl;
   if(selector==='[data-causal-document="notice"]')return selected.mode==='document:notice'?nodes.form:null;
   if(selector==='[data-causal-form="edge-edit"]')return selected.mode==='edge:e'?nodes.form:null;
   return originalQuery.call(panel,selector);
  };
 }
 mount();c.window.CasePathCausal={session:()=>selected};c.CSS={escape:value=>value};
 c.activeDetailContext=()=>({epoch:c.state.detailEpoch,claimId:c.state.detail.state.claim_id});
 c.isActiveDetail=context=>context.epoch===c.state.detailEpoch&&context.claimId===c.state.detail.state.claim_id&&!c.$('#cwDetail').hidden;
 c.syncReasoning=()=>{};c.setAdjacentClaims=()=>{};
 vm.runInContext(source.slice(source.indexOf('  function restoreWorkbenchPresentation('),source.indexOf("  compactWorkbench.addEventListener('change'")),c);
 c.renderDetail=detail=>{renders.push(detail);mount();c.restoreWorkbenchPresentation();};c.verifyCausalResponse=async value=>value;
 let releaseRead,releaseEditor;
 const read=deferred?new Promise(resolve=>releaseRead=resolve):Promise.resolve(process),editor=deferred?new Promise(resolve=>releaseEditor=resolve):Promise.resolve();
 c.request=(url,options)=>{requests.push({url,options});return read;};c.loadCausalEditor=()=>editor;
 c.openInspector=()=>{c.state.inspectorOpen=true;};
 vm.runInContext(source.slice(source.indexOf('  let causalRead;'),source.indexOf('  async function reloadCausalProcess(')),c);
 return {...f,c,selected,process,focuses,clicks,requests,renders,nodes:()=>nodes,ready(){releaseRead?.(process);releaseEditor?.();}};
}

test('contextual process navigation selects a real node and uses its existing exact source review',async()=>{
 const f=contextualPaneFixture(),c=f.c;
 assert.equal(await c.openPane('process',{node_id:'b',document_type:'notice'}),true);
 assert.equal(f.selected.selected,'b');assert.equal(f.selected.expanded,false);assert.equal(f.selected.preview,null);
 assert.deepEqual(f.clicks,['review:notice']);assert.equal(f.selected.mode,'document:notice');
 assert.equal(f.focuses.at(-1),f.nodes().field);assert.ok(f.focuses.at(-1).scrolled);assert.equal(f.requests.length,0);
 const invalid=contextualPaneFixture();assert.equal(await invalid.c.openPane('process',{node_id:'missing',document_type:'notice'}),false);
 assert.equal(invalid.clicks.length,0);assert.equal(invalid.focuses.length,0);
 const unrelated=contextualPaneFixture();assert.equal(await unrelated.c.openPane('process',{node_id:'a',document_type:'notice'}),false);
 assert.equal(unrelated.clicks.length,0);assert.equal(unrelated.selected.mode,null);
 const busy=contextualPaneFixture(),savedPreview=busy.selected.preview;busy.selected.busy=true;
 assert.equal(await busy.c.openPane('process',{node_id:'b',document_type:'notice'}),false);
 assert.equal(busy.selected.selected,'a');assert.equal(busy.selected.preview,savedPreview);assert.equal(busy.clicks.length,0);
});

test('contextual edge and Documents targets focus their actual controls without changing saved work',async()=>{
 const f=contextualPaneFixture(),before=JSON.stringify(f.process);
 assert.equal(await f.c.openPane('process',{edge_id:'e'}),true);assert.equal(f.selected.selected,'b');
 assert.deepEqual(f.clicks,['edge:e']);assert.equal(f.selected.mode,'edge:e');assert.equal(f.focuses.at(-1),f.nodes().field);
 assert.equal(await f.c.openPane('documents',{document_type:'notice'}),true);assert.equal(f.c.state.claimSection,'documents');
 assert.equal(f.focuses.at(-1),f.nodes().docRow);assert.ok(f.nodes().docRow.scrolled);
 assert.equal(await f.c.openPane('documents',{document_type:'not-present'}),false);
 assert.equal(await f.c.openPane('process',{edge_id:'not-present'}),false);
 assert.equal(JSON.stringify(f.process),before);assert.equal(f.requests.length,0);
});

test('context navigation shares the real process/editor load and waits for both before focusing',async()=>{
 const f=contextualPaneFixture({deferred:true}),c=f.c;
 const existing=c.loadCausalProcess(c.activeDetailContext()),opening=c.openPane('process',{node_id:'b',document_type:'notice'});
 assert.equal(c.state.claimSection,'process');assert.equal(f.requests.length,1);assert.equal(f.focuses.length,0);
 assert.equal(f.requests[0].options.method,undefined);f.ready();await existing;assert.equal(await opening,true);
 assert.equal(f.requests.length,1);assert.equal(f.selected.mode,'document:notice');assert.equal(f.focuses.at(-1),f.nodes().field);
});

test('late contextual navigation cannot steal focus after another pane, tab or claim is chosen',async()=>{
 for(const later of ['pane','tab','claim']){
  const f=contextualPaneFixture({deferred:true}),c=f.c,opening=c.openPane('process',{node_id:'b',document_type:'notice'});
  if(later==='pane')await c.openPane('sources');
  else if(later==='tab')c.selectClaimSection('documents');
  else{c.state.detailEpoch++;c.state.detail={state:{claim_id:'claim-b',revision:1,state_sha256:'other',intake_assessment:{}}};}
  f.ready();assert.equal(await opening,false);assert.equal(f.focuses.length,0);assert.equal(f.clicks.length,0);
  if(later==='pane')assert.equal(c.state.inspectorOpen,true);
  if(later==='tab')assert.equal(c.state.claimSection,'documents');
 }
});

test('a refresh during process hash verification cannot publish a stale loading error',async()=>{
 const f=contextualPaneFixture({deferred:true}),c=f.c;let finishVerification;
 c.verifyCausalResponse=()=>new Promise(resolve=>finishVerification=resolve);
 const reading=c.loadCausalProcess(c.activeDetailContext());f.ready();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(typeof finishVerification,'function');
 c.state.detail.state.revision=5;c.state.detail.state.state_sha256='new-state';
 finishVerification(f.process);await reading;
 assert.equal(c.state.causal,null);assert.equal(c.state.causalLoading,null);
 assert.equal(f.renders.length,1,'The current claim can render and request its fresh process');
});

test('an older process load cannot clear a newer revision load',async()=>{
 for(const sharedContext of [false,true]){
  const f=contextualPaneFixture(),c=f.c,reads=[];c.state.causal=null;
  c.request=()=>new Promise(resolve=>reads.push(resolve));
  const context=c.activeDetailContext(),first=c.loadCausalProcess(context);
  c.state.detail.state.revision=5;c.state.detail.state.state_sha256='new-state';
  const nextContext=sharedContext?context:c.activeDetailContext(),second=c.loadCausalProcess(nextContext),newRead=c.state.causalLoading;
  assert.equal(newRead.context,nextContext);assert.equal(newRead.revision,5);
  assert.equal(reads.length,2);reads[0](f.process);await first;
  assert.equal(c.state.causalLoading,newRead);assert.equal(c.state.causal,null);assert.equal(f.renders.length,0);
  reads[1]({...f.process,workspace_revision:5,workspace_state_sha256:'new-state'});await second;
  assert.equal(c.state.causal.workspace_revision,5);assert.equal(c.state.causalLoading,null);assert.equal(f.renders.length,1);
 }
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

test('full review exposes each recorded source event through the existing detail handler',()=>{
 const agent=fs.readFileSync(path.join(__dirname,'../casepath/assets/agent-work-v1.js'),'utf8');
 const events=[
  {sequence:7,operation:'SOURCE_SPAN_SELECTED',timestamp:'2026-10-07T12:00:00Z',sources:[{extraction:'message_body',quote:'Receipt: 30. Juni <unconfirmed>'}]},
  {sequence:11,operation:'SOURCE_SPAN_SELECTED',timestamp:'2026-10-07T12:00:01Z',sources:[{extraction:'message_body',quote:'A separate original source remains unread.'}]},
 ];
 const original=JSON.stringify(events),host={dataset:{}},listeners={},inspected=[];
 const c={state:{run:{},summary:{run_id:'saved-run'},events,assessment:null,revealCount:0},
  document:{getElementById:id=>id==='cpPanel-activity'?{}:id==='awTimeline'?host:null,addEventListener(type,handler){listeners[type]=handler;}},
  time:value=>value,inspect:event=>inspected.push(event),request(){throw Error('Inspection must not create a request');}};
 vm.createContext(c);
 vm.runInContext(agent.slice(agent.indexOf('  const h='),agent.indexOf('  const icon=')),c);
 vm.runInContext(agent.slice(agent.indexOf('  function narrativeEvent('),agent.indexOf('  function syncLivePath(')),c);
 vm.runInContext(agent.slice(agent.indexOf('  function renderTimeline('),agent.indexOf('  function renderProcess(')),c);
 vm.runInContext(agent.slice(agent.indexOf("  document.addEventListener('click',"),agent.indexOf("  document.addEventListener('keydown',e=>")),c);
 c.renderTimeline();
 const buttons=[...host.innerHTML.matchAll(/<button type="button" class="aw-text-button" data-aw-event="(\d+)">Inspect work detail<\/button>/g)];
 assert.deepEqual(buttons.map(match=>Number(match[1])),events.map(event=>event.sequence));
 assert.match(host.innerHTML,/data-aw-quote="30\. Juni &lt;unconfirmed&gt;"/);
 assert.match(host.innerHTML,/<\/a><button type="button"/);
 for(const [,sequence] of buttons){
  const button={tagName:'BUTTON',dataset:{awEvent:sequence},hasAttribute:name=>name==='data-aw-event'};
  listeners.click({target:{closest:()=>button},preventDefault(){throw Error('A native detail button needs no link override');}});
 }
 assert.equal(inspected[0],events[0]);assert.equal(inspected[1],events[1]);
 assert.equal(JSON.stringify(events),original);
 c.state.events=[];c.renderTimeline();
 assert.doesNotMatch(host.innerHTML,/data-aw-event/);
 assert.match(host.innerHTML,/Source reads will appear here as they are saved\./);
});

test('queued work cannot borrow a customer quote before its persisted source read',()=>{
 const agent=fs.readFileSync(path.join(__dirname,'../casepath/assets/agent-work-v1.js'),'utf8');
 const queued={sequence:1,operation:'RUN_QUEUED',message:'Review queued',sources:[]};
 const read={sequence:8,operation:'SOURCE_SPAN_SELECTED',timestamp:'2026-10-07T12:00:00Z',sources:[{extraction:'message_body',quote:'The persisted receipt date is still unconfirmed.'}]};
 const host={dataset:{}},inspected=[],listeners={};let domReads=0;
 const c={state:{run:{},summary:{run_id:'saved-run'},events:[queued],assessment:null,revealCount:0},
  document:{querySelector(){domReads++;return {textContent:'Customer message\n\nA DOM-only quote was never read by this run.'};},getElementById:id=>id==='cpPanel-activity'?{}:id==='awTimeline'?host:null,addEventListener(type,handler){listeners[type]=handler;}},
  time:value=>value,inspect:event=>inspected.push(event)};
 vm.createContext(c);
 vm.runInContext(agent.slice(agent.indexOf('  const h='),agent.indexOf('  const icon=')),c);
 vm.runInContext(agent.slice(agent.indexOf('  function narrativeEvent('),agent.indexOf('  function syncLivePath(')),c);
 vm.runInContext(agent.slice(agent.indexOf('  function renderTimeline('),agent.indexOf('  function renderProcess(')),c);
 vm.runInContext(agent.slice(agent.indexOf("  document.addEventListener('click',"),agent.indexOf("  document.addEventListener('keydown',e=>")),c);
 c.renderTimeline();
 assert.doesNotMatch(host.innerHTML,/DOM-only quote|Customer:|data-aw-quote|data-aw-event/);
 assert.match(host.innerHTML,/Source reads will appear here as they are saved\./);
 c.state.events=[queued,read];c.renderTimeline();
 assert.match(host.innerHTML,/The persisted receipt date is still unconfirmed/);
 assert.doesNotMatch(host.innerHTML,/DOM-only quote|data-aw-event="1"/);
 const buttons=[...host.innerHTML.matchAll(/data-aw-event="(\d+)"/g)];assert.deepEqual(buttons.map(match=>Number(match[1])),[read.sequence]);
 const button={tagName:'BUTTON',dataset:{awEvent:String(read.sequence)},hasAttribute:()=>false};
 listeners.click({target:{closest:()=>button}});
 assert.equal(inspected[0],read);assert.equal(inspected[0].sources[0],read.sources[0]);assert.equal(domReads,0);
});

test('connected source work has a named target and still opens the complete recorded source',()=>{
 const agent=fs.readFileSync(path.join(__dirname,'../casepath/assets/agent-work-v1.js'),'utf8');
 const text='Original customer message with unconfirmed dates. '.repeat(100)+'<not established>';
 const opened={id:'source:message',kind:'opened_source',value:{extraction:'message_body',filename:'original.eml',text,complete:true}};
 const span={id:'span:receipt',kind:'span',value:{quote:'My form arrived on Monday',start:7,end:32}};
 const event={sequence:7,operation:'SOURCE_SPAN_SELECTED',object_id:span.id,role:'canonical_facts',status:'observed',sources:[span.value],links:[opened.id]};
 const summary={run_id:'run-one',claim_id:'claim-one',subject:'A longer original claim subject',currentness:'current'};
 const run={summary,objects:[opened,span]},original=JSON.stringify(run),host={textContent:''};
 const dialog={open:false,querySelector:()=>host,showModal(){this.open=true;}};
 const c={state:{run,summary,events:[event]},window:{CasePathPresentation:{title:value=>value}},
  document:{getElementById:id=>id==='awInspector'?dialog:null,querySelector:()=>({textContent:'Family-home termination notices'})},
  getClaim:()=>summary.claim_id,roleName:()=> 'Facts',time:()=> '12:00',icon:()=> '<svg></svg>'};
 vm.createContext(c);
 vm.runInContext(agent.slice(agent.indexOf('  const h='),agent.indexOf('  const icon=')),c);
 vm.runInContext(agent.slice(agent.indexOf('  function objectTitle('),agent.indexOf('  async function request(')),c);
 vm.runInContext(agent.slice(agent.indexOf('  function detailDialog('),agent.indexOf('  async function showWorkforce(')),c);
 c.inspect(event);
 const related=dialog.innerHTML.match(/<button type="button" class="aw-related"[\s\S]*?<\/button>/)[0];
 assert.match(related,/data-aw-object="source:message"/);
 assert.match(related,/Customer message · Family-home termination notices/);
 assert.doesNotMatch(related,/Original customer message|not established/);
 c.inspect(null,opened.id);
 assert.match(dialog.innerHTML,/<h2>Customer message · Family-home termination notices<\/h2>/);
 assert.match(dialog.innerHTML,/Read scope/);
 assert.ok(dialog.innerHTML.includes(text.replaceAll('<','&lt;').replaceAll('>','&gt;')),'The complete original text remains inspectable');
 assert.equal(JSON.stringify(run),original);
 c.state.inspection.run.summary={...summary,claim_id:'another-claim',subject:'The saved claim title <unconfirmed>'};
 assert.equal(c.objectTitle(opened),'Customer message · The saved claim title <unconfirmed>');
 c.inspect(null,opened.id);
 assert.match(dialog.innerHTML,/<h2>Customer message · The saved claim title &lt;unconfirmed&gt;<\/h2>/);
 assert.equal(c.objectTitle({kind:'opened_source',value:{extraction:'pdf_text',filename:'Separate_notice.pdf',text:'Full PDF extraction'}}),'Separate notice.pdf');
});

test('a completed save for an old visit cannot replace the current claim loop',async()=>{
 const f=contextualPaneFixture(),c=f.c;
 vm.runInContext(source.slice(source.indexOf('  async function reloadCausalProcess('),source.indexOf('  function chooseEvidence(')),c);
 const aContext=c.activeDetailContext(),aDetail=c.state.detail,aLoop={claim_id:'claim-a'},bLoop={claim_id:'claim-b'};
 let releaseLoop,entered;
 const atLoop=new Promise(resolve=>entered=resolve),heldLoop=new Promise(resolve=>releaseLoop=resolve);
 c.request=async()=>aDetail;c.validateDetailResponse=async value=>value;c.state.loop=aLoop;
 c.loadClaimLoop=()=>{entered();return heldLoop;};
 let followups=0;c.loadDraftList=async()=>{followups++;};c.loadCausalProcess=async()=>{followups++;};
 const pending=c.reloadCausalProcess(aContext,f.process);await atLoop;
 const bDetail={state:{claim_id:'claim-b',revision:9,state_sha256:'b-state'},artifacts:[]},bProcess={claim_id:'claim-b',workspace_revision:9};
 c.state.detailEpoch++;c.state.detail=bDetail;c.state.causal=bProcess;c.state.loop=bLoop;
 releaseLoop(aLoop);await pending;
 assert.strictEqual(c.state.detail,bDetail);assert.strictEqual(c.state.causal,bProcess);assert.strictEqual(c.state.loop,bLoop);assert.equal(followups,0);
});

function northstarScrollFixture(width=1440){
 const f=fixture({mobile:width<=540}),c=f.context,originalQuery=f.panel.querySelector;
 f.panel.dataset.reviewView='northstar';c.northstarReview=true;c.northstarCompactWorkbench={matches:width<=760};
 const byName=new Map(f.panes.map(pane=>{pane.scrollTop=0;pane.attrs={};pane.setAttribute=function(name,value){this.attrs[name]=String(value);};return [pane.dataset.claimPane,pane];}));
 f.panel.querySelector=selector=>selector.startsWith('#cpPane-')?byName.get(selector.slice(8))||null:originalQuery(selector);
 c.state.claimSection='process';c.state.reviewRole='builder';
 return {...f,c,process:byName.get('process'),documents:byName.get('documents')};
}
test('northstar restores the destination pane without overwriting the pane being left',()=>{
 const f=northstarScrollFixture(),{c,process,documents,listeners}=f,fields=f.panes.map(p=>p.fields[0]);
 process.scrollTop=240;documents.scrollTop=11;c.state.sectionScroll.documents=91;
 c.selectClaimSection('documents');
 assert.equal(c.claimScrollRegion(),documents);assert.equal(c.state.sectionScroll.process,240);
 assert.equal(process.scrollTop,240);assert.equal(documents.scrollTop,91);
 documents.scrollTop=183;listeners.scroll({target:documents});c.selectClaimSection('process');
 assert.equal(c.claimScrollRegion(),process);assert.equal(process.scrollTop,240);assert.equal(documents.scrollTop,183);
 process.scrollTop=275;listeners.scroll({target:process});c.selectClaimSection('documents');
 assert.equal(process.scrollTop,275);assert.equal(documents.scrollTop,183);
 f.panes.forEach((pane,index)=>{assert.equal(pane.fields[0],fields[index]);assert.equal(pane.fields[0].value,'Unsaved handler explanation');});
});
test('northstar uses the panel through 760px while preserving the standard 540px breakpoint',()=>{
 for(const width of [541,650,760]){
  const {c,panel,process,documents,column,rail,listeners}=northstarScrollFixture(width);
  assert.equal(c.mobileWorkbench.matches,false);assert.equal(c.claimScrollRegion(),panel,width+'px uses the northstar CSS scroll owner');
  panel.scrollTop=212;process.scrollTop=17;documents.scrollTop=23;listeners.scroll({target:panel});
  assert.equal(c.state.sectionScroll.process,212);
  for(const target of [process,column,rail])listeners.scroll({target});
  assert.equal(c.state.sectionScroll.process,212);
  c.selectClaimSection('documents');assert.equal(panel.scrollTop,0);
  panel.scrollTop=91;listeners.scroll({target:panel});c.selectClaimSection('process');assert.equal(panel.scrollTop,212);
  c.selectClaimSection('documents');assert.equal(panel.scrollTop,91);assert.equal(process.scrollTop,17);assert.equal(documents.scrollTop,23);
 }
 const f=northstarScrollFixture(761);assert.equal(f.c.claimScrollRegion(),f.process);
});

test('a rejected loop refresh cannot partially publish a newer claim revision',async()=>{
 const f=contextualPaneFixture(),c=f.c;
 vm.runInContext(source.slice(source.indexOf('  async function reloadCausalProcess('),source.indexOf('  function chooseEvidence(')),c);
 const context=c.activeDetailContext(),oldDetail=c.state.detail,oldProcess=c.state.causal;
 const oldLoop={claim_id:'claim-a',revision:4},oldPriority={claim_id:'claim-a',state_sha256:'saved-state'};
 c.state.loop=oldLoop;c.state.detailPriority=oldPriority;
 const fresh={...oldDetail,state:{...oldDetail.state,revision:5,state_sha256:'state-five'}},accepted={...f.process,workspace_revision:5,workspace_state_sha256:'state-five'},failure=new Error('Loop read unavailable');
 let rejectLoop,entered;const atLoop=new Promise(resolve=>entered=resolve),heldLoop=new Promise((resolve,reject)=>rejectLoop=reject);
 c.request=async()=>fresh;c.validateDetailResponse=async value=>value;c.loadClaimLoop=()=>{entered();return heldLoop;};
 let followups=0;c.loadDraftList=async()=>{followups++;};c.loadCausalProcess=async()=>{followups++;};
 const rejected=assert.rejects(c.reloadCausalProcess(context,accepted),error=>error===failure);await atLoop;
 const during={detail:c.state.detail,causal:c.state.causal,loop:c.state.loop,priority:c.state.detailPriority};
 rejectLoop(failure);await rejected;
 for(const snapshot of [during,{detail:c.state.detail,causal:c.state.causal,loop:c.state.loop,priority:c.state.detailPriority}]){
  assert.strictEqual(snapshot.detail,oldDetail);assert.strictEqual(snapshot.causal,oldProcess);assert.strictEqual(snapshot.loop,oldLoop);assert.strictEqual(snapshot.priority,oldPriority);
 }
 assert.equal(followups,0);assert.ok(f.renders.every(detail=>detail===oldDetail));
});
test('a slow same-visit loop refresh cannot replace a newer coherent revision',async()=>{
 const f=contextualPaneFixture(),c=f.c;
 vm.runInContext(source.slice(source.indexOf('  async function reloadCausalProcess('),source.indexOf('  function chooseEvidence(')),c);
 const context=c.activeDetailContext(),oldDetail=c.state.detail;
 c.state.loop={claim_id:'claim-a',revision:4};
 const five={...oldDetail,state:{...oldDetail.state,revision:5,state_sha256:'state-five'}},six={...oldDetail,state:{...oldDetail.state,revision:6,state_sha256:'state-six'}};
 const sixProcess={...f.process,workspace_revision:6,workspace_state_sha256:'state-six'},sixLoop={claim_id:'claim-a',revision:6};
 let resolveLoop,entered;const atLoop=new Promise(r=>entered=r),held=new Promise(r=>resolveLoop=r);
 c.request=async()=>five;c.validateDetailResponse=async v=>v;c.loadClaimLoop=()=>{entered();return held;};
 let followups=0;c.loadDraftList=async()=>{followups++;};c.loadCausalProcess=async()=>{followups++;};
 const pending=c.reloadCausalProcess(context);await atLoop;
 c.state.detail=six;c.state.causal=sixProcess;c.state.loop=sixLoop;
 resolveLoop({claim_id:'claim-a',revision:5});await pending;
 assert.strictEqual(c.state.detail,six);assert.strictEqual(c.state.causal,sixProcess);assert.strictEqual(c.state.loop,sixLoop);assert.equal(followups,0);
});

test('post-commit read failures retain a coherent snapshot and render recovery only in the active visit',async()=>{
 for(const phase of ['draft','process']){
  const f=contextualPaneFixture(),c=f.c;
  vm.runInContext(source.slice(source.indexOf('  async function reloadCausalProcess('),source.indexOf('  function chooseEvidence(')),c);
  const context=c.activeDetailContext(),fresh={...c.state.detail,state:{...c.state.detail.state,revision:5,state_sha256:'state-five'}},loop={claim_id:'claim-a',revision:5};
  const accepted={...f.process,workspace_revision:5,workspace_state_sha256:'state-five'},failure=new Error(phase+' unavailable');
  c.state.loop={claim_id:'claim-a',revision:4};c.request=async()=>fresh;c.validateDetailResponse=async v=>v;c.loadClaimLoop=async()=>loop;
  c.loadDraftList=async()=>{if(phase==='draft')throw failure;};c.loadCausalProcess=async()=>{throw failure;};
  await assert.rejects(c.reloadCausalProcess(context,accepted),error=>error===failure);
  assert.strictEqual(c.state.detail,fresh);assert.equal(c.state.causal.workspace_revision,5);assert.strictEqual(c.state.loop,loop);
  assert.strictEqual(f.renders.at(-1),c.state.detail);
 }
});

test('northstar restores the selected review role after reload and refuses an incompatible role',()=>{
 const f=northstarScrollFixture(),c=f.c;c.state.reviewRole='result';c.selectClaimSection('overview');
 c.recoverPresentation('claim-a');assert.equal(c.state.claimSection,'overview');assert.equal(c.state.reviewRole,'result');
 c.sessionStorage.setItem('casepath:presentation:claim-a',JSON.stringify({claimSection:'documents',reviewRole:'result'}));
 c.recoverPresentation('claim-a');c.selectClaimSection(c.state.claimSection,{restoring:true});assert.equal(c.state.reviewRole,'finder');
});
