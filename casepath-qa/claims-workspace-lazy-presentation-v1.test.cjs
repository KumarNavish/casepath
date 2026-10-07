'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {createHash,webcrypto}=require('node:crypto');
const source=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
const asset='assets/claims-workspace-presentation-v1.js?sha256='+'a'.repeat(64);
const canonical=value=>value===null||typeof value!=='object'?JSON.stringify(value):Array.isArray(value)?'['+value.map(canonical).join(',')+']':'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
const sha=value=>createHash('sha256').update(canonical(value)).digest('hex');
function detail(id){
 const state={contract:'casepath.claim-workspace-state/1.0.0',claim_id:id,workflow_state:'received',last_event_sha256:'b'.repeat(64)};
 state.state_sha256=sha(state);
 const value={contract:'casepath.claim-workspace-detail/1.0.0',authority:'claim_loop_events',state,artifacts:[],message:null};
 return {...value,detail_sha256:sha(value)};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function fixture({hash='',meta=asset}={}){
 const nodes=[],scripts=[],events=[],requests=[],timers=new Map(),listeners={};let nextTimer=0;
 const location=new URL('http://localhost/'+hash);
 class Node{
  constructor(tag='div'){this.tagName=tag.toUpperCase();this.dataset={};this.style={};this.attrs={};this.options=[];this.value='';this.hidden=false;this.isConnected=true;this.listeners={};nodes.push(this);}
  set innerHTML(html){this.html=html;for(const match of html.matchAll(/<(\w+)\b([^>]*)\bid="([^"]+)"([^>]*)>/g)){const node=new Node(match[1]);node.id=match[3];node.hidden=/\bhidden\b/.test(match[2]+match[4]);if(node.tagName==='SELECT')node.options=[{value:''}];}if(html.includes('class="cw-shell ')){const node=new Node();node.className='cw-shell cp-queue-shell';}}
  get innerHTML(){return this.html||'';}
  matches(s){return s==='#'+this.id||s==='.'+this.className?.split(' ')[0];}
  querySelector(s){return nodes.find(node=>node!==this&&node.matches(s))||null;}
  querySelectorAll(){return [];}
  setAttribute(k,v){this.attrs[k]=v;} removeAttribute(k){delete this.attrs[k];}
  add(option){this.options.push(option);} addEventListener(type,fn){this.listeners[type]=fn;}
  remove(){this.isConnected=false;this.removed=true;} before(){} after(node){node.isConnected=true;}
  append(node){if(node.tagName==='SCRIPT')scripts.push(node);node.isConnected=true;}
  appendChild(node){this.append(node);} contains(){return false;}
  focus(){document.activeElement=this;}
 }
 const body=new Node('body');
 const document={body,activeElement:body,documentElement:{dataset:{}},
  createElement:tag=>new Node(tag),createComment:()=>new Node('comment'),
  querySelector:s=>s==='meta[name="casepath-workspace-presentation-script"]'?(meta===null?null:{content:meta}):nodes.find(node=>node.matches(s))||null,
  addEventListener(type,fn){listeners[type]=fn;}};
 const window={scrollY:0,rendered:[],addEventListener(type,fn){listeners[type]=fn;},dispatchEvent(event){events.push(event.type);},scrollTo(){}};
 const history={state:null,pushState(state,_,url){this.state=state;location.href=new URL(url,location).href;},replaceState(state,_,url){this.state=state;location.href=new URL(url,location).href;},back(){}};
 const storage=new Map(),store={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)};
 const c={window,document,location,history,localStorage:store,sessionStorage:store,URL,URLSearchParams,Event,AbortController,TextEncoder,Uint8Array,crypto:webcrypto,
  CSS:{escape:value=>value},Option:function(text,value){this.text=text;this.value=value;},matchMedia:()=>({matches:false,addEventListener(){}}),
  setTimeout(fn){const id=++nextTimer;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id),
  fetch:async(url,opts)=>{requests.push({url,opts});const id=decodeURIComponent(url.split('/claims/')[1]);return {ok:true,json:async()=>detail(id)};}};
 vm.createContext(c);
 // Keep the production boot, request verification and navigation intact. Detail
 // markup is covered separately; record arrival here without emulating its DOM.
 vm.runInContext(source.replace('  function renderDetail(detail) {','  function renderDetail(detail) { window.rendered.push(detail); window.onRender?.(detail); return;'),c);
 const install=()=>{window.CasePathPresentation={shell(){throw Error('Lazy arrival must not replace the desk scaffold');},detail(){},workbench(){}};};
 return {c,window,document,nodes,scripts,events,requests,timers,listeners,install};
}

test('native desk boot needs no presentation global or asset, including restored queue filters',()=>{
 const f=fixture();
 assert.ok(f.window.CasePathWorkspace);assert.equal(f.scripts.length,0);assert.equal(f.requests.length,0);
 assert.ok(f.events.includes('casepath:desk-refresh'));
 assert.ok(f.window.CasePathWorkspace.queueRoot().querySelector('#cwQueue'));
 assert.equal(f.document.querySelector('#cwDetail').hidden,true);
 f.c.location.search='?owner=Unassigned&sort=priority';f.listeners.popstate();
 assert.equal(f.document.querySelector('#cwOwner').value,'Unassigned');assert.equal(f.scripts.length,0);
});

test('desk-to-claim loads one content-bound module and preserves the desk route after closing',async()=>{
 const f=fixture(),queue=f.window.CasePathWorkspace.queueRoot();
 const opening=f.window.CasePathWorkspace.openClaim('claim-a');
 assert.equal(f.scripts.length,1);assert.equal(f.scripts[0].src,asset);
 assert.equal(f.window.rendered.length,0);assert.match(f.document.querySelector('#cwDetailPanel').innerHTML,/Opening claim/);
 f.install();f.scripts[0].onload();await opening;
 assert.equal(f.window.rendered[0].state.claim_id,'claim-a');
 f.window.CasePathWorkspace.closeDetail({fromHistory:true,refresh:false});
 assert.equal(f.window.CasePathWorkspace.queueRoot(),queue);assert.equal(queue.isConnected,true);
 await f.window.CasePathWorkspace.openClaim('claim-b');assert.equal(f.scripts.length,1);
 assert.deepEqual(f.window.rendered.map(d=>d.state.claim_id),['claim-a','claim-b']);
});

test('direct claim links load presentation before verified detail arrives',{timeout:2000},async()=>{
 const f=fixture({hash:'#claim=claim-deep'});
 assert.equal(f.scripts.length,1);assert.equal(f.requests.length,1);assert.equal(f.window.rendered.length,0);
 assert.equal(f.document.querySelector('#cwDetail').hidden,false);
 const arrival=new Promise(resolve=>f.window.onRender=resolve);
 f.install();f.scripts[0].onload();await arrival;
 assert.equal(f.window.CasePathWorkspace.snapshot().claim.state.claim_id,'claim-deep');
 assert.equal(f.window.rendered[0].state.claim_id,'claim-deep');
});

test('overlapping claim navigation shares the load and cannot paint the earlier claim',async()=>{
 const f=fixture();
 const first=f.window.CasePathWorkspace.openClaim('claim-a'),second=f.window.CasePathWorkspace.openClaim('claim-b');
 assert.equal(f.scripts.length,1);f.install();f.scripts[0].onload();await Promise.all([first,second]);
 assert.deepEqual(f.window.rendered.map(d=>d.state.claim_id),['claim-b']);
 assert.equal(f.requests[0].opts.signal.aborted,true);
});

test('returning to desk during a load cannot reopen or repaint that claim',async()=>{
 const f=fixture();const opening=f.window.CasePathWorkspace.openClaim('claim-a');
 f.window.CasePathWorkspace.closeDetail({fromHistory:true,refresh:false});
 f.install();f.scripts[0].onload();await opening;
 assert.equal(f.window.rendered.length,0);assert.equal(f.window.CasePathWorkspace.snapshot().claim,null);
 assert.equal(f.document.querySelector('#cwDetail').hidden,true);
});

test('failed presentation load is recoverable through the existing claim retry',async()=>{
 const f=fixture();let opening=f.window.CasePathWorkspace.openClaim('claim-a');
 f.scripts[0].onerror();await opening;
 const panel=f.document.querySelector('#cwDetailPanel');
 assert.match(panel.innerHTML,/Claim unavailable/);assert.match(panel.innerHTML,/data-retry-claim="claim-a"/);
 assert.match(panel.innerHTML,/data-close-detail/);assert.equal(f.scripts[0].removed,true);
 opening=f.window.CasePathWorkspace.openClaim('claim-a');assert.equal(f.scripts.length,2);
 f.install();f.scripts[1].onload();await opening;assert.equal(f.window.rendered[0].state.claim_id,'claim-a');
});

test('missing, unbound or wrong script metadata fails closed without an asset request',async()=>{
 for(const meta of [null,'assets/claims-workspace-presentation-v1.js','https://external.invalid/claims-workspace-presentation-v1.js?sha256='+'a'.repeat(64)]){
  const f=fixture({meta});await f.window.CasePathWorkspace.openClaim('claim-a');
  assert.equal(f.scripts.length,0);assert.equal(f.window.rendered.length,0);
  assert.match(f.document.querySelector('#cwDetailPanel').innerHTML,/Claim presentation script is unavailable/);
 }
});

test('timeout and invalid module arrival release the failed load for a real retry',async()=>{
 for(const failure of ['timeout','incomplete']){
  const f=fixture();const opening=f.window.CasePathWorkspace.openClaim('claim-a');await settle();
  if(failure==='timeout'){
   assert.equal(f.timers.size,1);[...f.timers.values()][0]();
  }else{f.window.CasePathPresentation={shell(){}};f.scripts[0].onload();}
  await opening;assert.equal(f.scripts[0].removed,true);assert.equal(f.window.rendered.length,0);
  const retry=f.window.CasePathWorkspace.openClaim('claim-a');assert.equal(f.scripts.length,2);
  f.install();f.scripts[1].onload();await retry;assert.equal(f.window.rendered.length,1);
 }
});
