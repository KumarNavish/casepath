'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');

// Execute the production source-navigation handlers without a browser or API.
// Library links reject focus while their native disclosure is closed.
function fixture({message=true,attachment=true}={}){
 const document={activeElement:{id:'caller'}},focuses=[],storage=[];
 const state={detail:{state:{claim_id:'claim-a'},artifacts:[{role:'customer_message'},{role:'attachment'}]},sourceSelection:{kind:'artifact',index:1},inspectorOpen:true,motion:0};
 const library={open:false},rail={scrollTop:77},reset={hidden:false},inspector={offsetTop:142,focus(){document.activeElement=this;focuses.push(this);}},summary={focus(){document.activeElement=this;focuses.push(this);}};
 const link=(kind,index)=>({kind,attrs:{'aria-current':'false'},dataset:index===undefined?{}:{packetArtifact:String(index)},setAttribute(key,value){this.attrs[key]=value;},focus(){assert.equal(library.open,true,'A closed disclosure child must never receive focus');document.activeElement=this;focuses.push(this);}});
 const links=[...(message?[link('message')]:[]),...(attachment?[link('attachment',1)]:[])];
 const query=selector=>selector==='[aria-current="true"]'?links.find(item=>item.attrs['aria-current']==='true')||null:selector==='summary'?summary:selector==='[data-packet-message]'?links.find(item=>item.kind==='message')||null:selector==='[data-packet-message],[data-packet-artifact]'?links[0]||null:null;
 library.querySelector=query;rail.querySelector=query;
 const root={addEventListener(){},querySelectorAll:selector=>selector==='[data-packet-artifact]'?links.filter(item=>item.kind==='attachment'):selector==='[data-packet-message]'?links.filter(item=>item.kind==='message'):selector==='[data-source-reset]'?[reset]:[]};
 const context={state,document,root,Math,window:{},$:(selector)=>({'#cwSourceLibrary':library,'#cwSourceInspector':inspector,'.cp-source-rail':rail}[selector]),savePresentation:()=>storage.push(state.sourceSelection),openInspector(){state.inspectorOpen=true;inspector.focus();},resetSource(focus){state.sourceSelection=null;context.focusSource(focus);}};
 vm.createContext(context);
 for(const[from,to]of[['  function packetSelection(', '  function releaseSourcePreview('],['  function focusSource(', '  function resetSource('],['  function presentationClick(', '  function workspaceKeyboard(']]){
  const start=source.indexOf(from),end=source.indexOf(to,start);assert.ok(start>=0&&end>start);vm.runInContext(source.slice(start,end),context);
 }
 const button=name=>({dataset:{},hasAttribute:key=>key===name,matches:()=>false});
 context.packetSelection();return{context,state,document,library,rail,inspector,summary,reset,links,focuses,storage,button};
}

test('an explicit source view closes the library before focusing and scrolling its inspector',()=>{
 const f=fixture();f.library.open=true;const selection=f.state.sourceSelection;
 f.context.focusSource(true);
 assert.equal(f.library.open,false);assert.equal(f.document.activeElement,f.inspector);assert.equal(f.rail.scrollTop,80);
 assert.equal(f.state.sourceSelection,selection);assert.equal(f.storage.length,1);
});

test('a passive source refresh preserves either native disclosure state and current focus',()=>{
 for(const open of [false,true]){const f=fixture();f.library.open=open;const active=f.document.activeElement,selection=f.state.sourceSelection;
  f.context.focusSource(false);assert.equal(f.library.open,open);assert.equal(f.document.activeElement,active);assert.equal(f.state.sourceSelection,selection);assert.equal(f.storage.length,0);
 }
});

test('Packet opens the library before focusing the current attachment without changing the source',()=>{
 const f=fixture(),selection=f.state.sourceSelection;
 assert.equal(f.context.packetClick(f.button('data-packet-library')),true);
 assert.equal(f.library.open,true);assert.equal(f.document.activeElement,f.links.find(item=>item.kind==='attachment'));assert.equal(f.rail.scrollTop,0);assert.equal(f.state.sourceSelection,selection);
});

test('explicit canvas source browsing opens the library and focuses the customer message',()=>{
 const f=fixture();assert.equal(f.context.presentationClick(f.button('data-canvas-source')),true);
 assert.equal(f.library.open,true);assert.equal(f.document.activeElement,f.links.find(item=>item.kind==='message'));assert.equal(f.state.sourceSelection,null);assert.equal(f.rail.scrollTop,0);
});

test('library navigation has visible fallbacks when the customer message or every artifact is absent',()=>{
 for(const options of [{message:false},{message:false,attachment:false}]){const f=fixture(options);f.state.sourceSelection=null;f.context.packetSelection();
  assert.equal(f.context.packetClick(f.button('data-packet-library')),true);assert.equal(f.library.open,true);assert.equal(f.document.activeElement,f.links[0]||f.summary);
 }
});

test('Back to message appears only when the current view is different from the customer message',()=>{
 const f=fixture();
 for(const [selection,hidden]of [[null,true],[{kind:'artifact',index:0},true],[{kind:'artifact',index:1},false],[{kind:'evidence',id:'evidence-a'},false],[{kind:'process',id:'node-a'},false]]){
  f.state.sourceSelection=selection;f.context.focusSource(false);assert.equal(f.reset.hidden,hidden,JSON.stringify(selection));assert.equal(f.state.sourceSelection,selection);
 }
});
