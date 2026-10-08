'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {createHash,webcrypto}=require('node:crypto');
const source=fs.readFileSync(path.join(__dirname,'../casepath/assets/claims-workspace-v1.js'),'utf8');
const asset='assets/claims-workspace-presentation-v1.js?sha256='+'a'.repeat(64);
const agentAsset='assets/agent-claim-v2.js?sha256='+'c'.repeat(64);
const motionAsset='assets/agent-work-motion-v3.js?sha256='+'d'.repeat(64);
const canonical=value=>value===null||typeof value!=='object'?JSON.stringify(value):Array.isArray(value)?'['+value.map(canonical).join(',')+']':'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
const sha=value=>createHash('sha256').update(canonical(value)).digest('hex');
function detail(id){
 const state={contract:'casepath.claim-workspace-state/1.0.0',claim_id:id,workflow_state:'received',last_event_sha256:'b'.repeat(64)};
 state.state_sha256=sha(state);
 const value={contract:'casepath.claim-workspace-detail/1.0.0',authority:'claim_loop_events',state,artifacts:[],message:null};
 return {...value,detail_sha256:sha(value)};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function fixture({hash='',meta=asset,agentMeta=agentAsset,agentReady=true,motionMeta=motionAsset,motionReady=true}={}){
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
  querySelector:s=>s==='meta[name="casepath-workspace-presentation-script"]'?(meta===null?null:{content:meta}):s==='meta[name="casepath-agent-claim-script"]'?(agentMeta===null?null:{content:agentMeta}):s==='meta[name="casepath-work-motion-script"]'?(motionMeta===null?null:{content:motionMeta}):nodes.find(node=>node.matches(s))||null,
  addEventListener(type,fn){listeners[type]=fn;}};
 const window={scrollY:0,rendered:[],addEventListener(type,fn){listeners[type]=fn;},dispatchEvent(event){events.push(event.type);},scrollTo(){}};
 const installAgent=()=>{window.CasePathAgentClaim={render(){},bind(){},session(){}};};
 const installMotion=()=>{window.CasePathWorkMotion={markup(){},observe(){},dispose(){}};};
 if(agentReady)installAgent();
 if(motionReady)installMotion();
 const history={state:null,pushState(state,_,url){this.state=state;location.href=new URL(url,location).href;},replaceState(state,_,url){this.state=state;location.href=new URL(url,location).href;},back(){}};
 const storage=new Map(),store={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)};
 const c={window,document,location,history,localStorage:store,sessionStorage:store,URL,URLSearchParams,Event,AbortController,TextEncoder,Uint8Array,crypto:webcrypto,
  CSS:{escape:value=>value},Option:function(text,value){this.text=text;this.value=value;},matchMedia:()=>({matches:false,addEventListener(){}}),
  setTimeout(fn){const id=++nextTimer;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id),
  fetch:async(url,opts)=>{requests.push({url,opts});const id=decodeURIComponent(url.split('/claims/')[1]);return new Response(JSON.stringify(detail(id)));}};
 vm.createContext(c);
 // Keep the production boot, request verification and navigation intact. Detail
 // markup is covered separately; record arrival here without emulating its DOM.
 vm.runInContext(source.replace('  function renderDetail(detail) {','  function renderDetail(detail) { window.rendered.push(detail); window.onRender?.(detail); return;'),c);
 const install=()=>{window.CasePathPresentation={shell(){throw Error('Lazy arrival must not replace the desk scaffold');},detail(){},workbench(){}};};
 return {c,window,document,nodes,scripts,events,requests,timers,listeners,install,installAgent,installMotion};
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

test('a fresh desk has no claim module and claim entry waits for both local modules',async()=>{
 for(const first of ['presentation','agent']){
  const f=fixture({agentReady:false});
  assert.equal(f.window.CasePathAgentClaim,undefined);assert.equal(f.scripts.length,0);
  const opening=f.window.CasePathWorkspace.openClaim('claim-lazy');
  assert.deepEqual(f.scripts.map(script=>script.src),[asset,agentAsset]);
  assert.match(f.document.querySelector('#cwDetailPanel').innerHTML,/Opening claim/);
  const presentation=f.scripts[0],agent=f.scripts[1];
  if(first==='presentation'){f.install();presentation.onload();}else{f.installAgent();agent.onload();}
  await settle();assert.equal(f.window.rendered.length,0,'One ready module cannot render a claim');
  if(first==='presentation'){f.installAgent();agent.onload();}else{f.install();presentation.onload();}
  await opening;assert.equal(f.window.rendered[0].state.claim_id,'claim-lazy');
  f.window.CasePathWorkspace.closeDetail({fromHistory:true,refresh:false});
  await f.window.CasePathWorkspace.openClaim('claim-next');assert.equal(f.scripts.length,2);
 }
 const index=fs.readFileSync(path.join(__dirname,'../casepath/index.html'),'utf8');
 const match=index.match(/<meta name="casepath-agent-claim-script" content="([^\"]+)">/);
 const digest=createHash('sha256').update(fs.readFileSync(path.join(__dirname,'../casepath/assets/agent-claim-v2.js'))).digest('hex');
 assert.equal(match?.[1],`assets/agent-claim-v2.js?sha256=${digest}`);
 assert.doesNotMatch(index,/<script[^>]+src="assets\/agent-claim-v2\.js/);
});

test('concurrent claim entries share both lazy loads and cannot paint an abandoned claim',async()=>{
 const f=fixture({agentReady:false});
 const first=f.window.CasePathWorkspace.openClaim('claim-a'),second=f.window.CasePathWorkspace.openClaim('claim-b');
 assert.equal(f.scripts.length,2);f.install();f.scripts[0].onload();f.installAgent();f.scripts[1].onload();
 await Promise.all([first,second]);assert.deepEqual(f.window.rendered.map(d=>d.state.claim_id),['claim-b']);
 assert.equal(f.requests[0].opts.signal.aborted,true);
 const abandoned=fixture({agentReady:false}),opening=abandoned.window.CasePathWorkspace.openClaim('claim-a');
 abandoned.window.CasePathWorkspace.closeDetail({fromHistory:true,refresh:false});
 abandoned.install();abandoned.scripts[0].onload();abandoned.installAgent();abandoned.scripts[1].onload();
 await opening;assert.equal(abandoned.window.rendered.length,0);assert.equal(abandoned.document.querySelector('#cwDetail').hidden,true);
});

test('invalid claim-module metadata never requests claim controls or renders a claim',async()=>{
 for(const agentMeta of [null,'assets/agent-claim-v2.js','https://external.invalid/agent-claim-v2.js?sha256='+'c'.repeat(64)]){
  const f=fixture({agentReady:false,agentMeta}),opening=f.window.CasePathWorkspace.openClaim('claim-a');
  assert.deepEqual(f.scripts.map(script=>script.src),[asset]);f.install();f.scripts[0].onload();await opening;
  assert.equal(f.window.rendered.length,0);assert.match(f.document.querySelector('#cwDetailPanel').innerHTML,/Claim controls script is unavailable/);
 }
});

test('claim-module error, timeout and incomplete arrival all permit the existing retry',async()=>{
 for(const failure of ['error','timeout','incomplete']){
  const f=fixture({agentReady:false}),opening=f.window.CasePathWorkspace.openClaim('claim-a');
  f.install();f.scripts[0].onload();const agent=f.scripts[1];
  await settle();
  if(failure==='error')agent.onerror();
  else if(failure==='timeout'){assert.equal(f.timers.size,1);[...f.timers.values()][0]();}
  else{f.window.CasePathAgentClaim={render(){}};agent.onload();}
  await opening;assert.equal(agent.removed,true);assert.equal(f.window.rendered.length,0);
  assert.match(f.document.querySelector('#cwDetailPanel').innerHTML,/data-retry-claim="claim-a"/);
  const retry=f.window.CasePathWorkspace.openClaim('claim-a');assert.equal(f.scripts.length,3);assert.equal(f.scripts[2].src,agentAsset);
  f.installAgent();f.scripts[2].onload();await retry;assert.equal(f.window.rendered[0].state.claim_id,'claim-a');
 }
});

test('live review stays lazy and claim rendering waits for all three complete modules',async()=>{
 const f=fixture({agentReady:false,motionReady:false});
 assert.equal(f.scripts.length,0);assert.equal(f.window.CasePathWorkMotion,undefined);
 const first=f.window.CasePathWorkspace.openClaim('claim-a'),second=f.window.CasePathWorkspace.openClaim('claim-b');
 assert.deepEqual(f.scripts.map(script=>script.src),[asset,agentAsset,motionAsset]);
 f.install();f.scripts[0].onload();f.installAgent();f.scripts[1].onload();await settle();
 assert.equal(f.window.rendered.length,0,'Claim presentation and controls cannot omit live review');
 f.installMotion();f.scripts[2].onload();await Promise.all([first,second]);
 assert.deepEqual(f.window.rendered.map(d=>d.state.claim_id),['claim-b']);assert.equal(f.requests[0].opts.signal.aborted,true);
 await f.window.CasePathWorkspace.openClaim('claim-c');assert.equal(f.scripts.length,3);
 const index=fs.readFileSync(path.join(__dirname,'../casepath/index.html'),'utf8');
 const bound=index.match(/<meta name="casepath-work-motion-script" content="([^"]+)">/);
 const digest=createHash('sha256').update(fs.readFileSync(path.join(__dirname,'../casepath/assets/agent-work-motion-v3.js'))).digest('hex');
 assert.equal(bound?.[1],`assets/agent-work-motion-v3.js?sha256=${digest}`);
 assert.doesNotMatch(index,/<script[^>]+src="assets\/agent-work-motion-v3\.js/);
});

test('live-review failed, incomplete and timed-out loads preserve the real claim retry',async()=>{
 for(const failure of ['error','incomplete','timeout']){
  const f=fixture({motionReady:false}),opening=f.window.CasePathWorkspace.openClaim('claim-a');
  f.install();f.scripts[0].onload();const motion=f.scripts[1];await settle();
  if(failure==='error')motion.onerror();
  else if(failure==='timeout'){assert.equal(f.timers.size,1);[...f.timers.values()][0]();}
  else{f.window.CasePathWorkMotion={markup(){},observe(){}};motion.onload();}
  await opening;assert.equal(motion.removed,true);assert.equal(f.window.rendered.length,0);
  assert.match(f.document.querySelector('#cwDetailPanel').innerHTML,/data-retry-claim="claim-a"/);
  const retry=f.window.CasePathWorkspace.openClaim('claim-a');assert.equal(f.scripts[2].src,motionAsset);
  f.installMotion();f.scripts[2].onload();await retry;assert.equal(f.window.rendered[0].state.claim_id,'claim-a');
 }
});

test('unbound live-review metadata fails closed, and leaving during load cannot reopen the claim',async()=>{
 for(const motionMeta of [null,'assets/agent-work-motion-v3.js','https://external.invalid/agent-work-motion-v3.js?sha256='+'d'.repeat(64)]){
  const f=fixture({motionReady:false,motionMeta}),opening=f.window.CasePathWorkspace.openClaim('claim-a');
  assert.deepEqual(f.scripts.map(script=>script.src),[asset]);f.install();f.scripts[0].onload();await opening;
  assert.equal(f.window.rendered.length,0);assert.match(f.document.querySelector('#cwDetailPanel').innerHTML,/Live review script is unavailable/);
 }
 const f=fixture({motionReady:false}),opening=f.window.CasePathWorkspace.openClaim('claim-a');
 f.window.CasePathWorkspace.closeDetail({fromHistory:true,refresh:false});
 f.install();f.scripts[0].onload();f.installMotion();f.scripts[1].onload();await opening;
 assert.equal(f.window.rendered.length,0);assert.equal(f.document.querySelector('#cwDetail').hidden,true);
});
