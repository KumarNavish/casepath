const {test}=require('node:test');
const assert=require('node:assert/strict');
const {liveStream}=require('../casepath/assets/agent-desk-v2.js');
const fs=require('node:fs');
const vm=require('node:vm');
const crypto=require('node:crypto');

function harness({available=true,throws=false}={}) {
 const sources=[],timers=new Map(),cancelled=[],statuses=[],invalidations=[];let next=1;
 class FakeEventSource {
  constructor(url){if(throws)throw new Error('transport unavailable');this.url=url;this.handlers=new Map();this.closed=false;sources.push(this);}
  addEventListener(kind,listener){this.handlers.set(kind,listener);}
  close(){this.closed=true;}
  emit(kind,event={}){this.handlers.get(kind)?.(event);}
 }
 const stream=liveStream({EventSource:available?FakeEventSource:undefined,
  onInvalidate:(...args)=>invalidations.push(args),onStatus:text=>statuses.push(text),
  schedule:(fn,delay)=>{const id=next++;timers.set(id,{fn,delay});return id;},
  cancel:id=>{cancelled.push(timers.get(id)?.fn);timers.delete(id);}});
 const flush=()=>{const jobs=[...timers.values()];timers.clear();for(const {fn}of jobs)fn();};
 return {stream,sources,timers,cancelled,statuses,invalidations,flush};
}
const agent=(claim='claim-one',run='run-one',status='running',sequence=8)=>({claim_id:claim,run:{run_id:run,status,last_sequence:sequence}});

test('event bursts coalesce into one sealed-read invalidation without consuming event data',()=>{
 const h=harness();h.stream.update(agent());
 const event={get data(){throw new Error('raw event data must never be parsed or rendered');}};
 for(let i=0;i<20;i++)h.sources[0].emit('work',event);
 assert.equal(h.timers.size,1);assert.equal(h.invalidations.length,0);
 assert.ok([...h.timers.values()][0].delay<250);
 h.flush();assert.deepEqual(h.invalidations,[[]]);
 h.sources[0].emit('work',event);h.flush();assert.equal(h.invalidations.length,2);
});

test('stream begins after the verified run sequence and URL-encodes identities',()=>{
 const h=harness();h.stream.update(agent('claim/one','run?two','queued',91));
 assert.equal(h.sources[0].url,'/api/agent-work/v1/claims/claim%2Fone/runs/run%3Ftwo/stream?after=91');
 for(const value of [undefined,-1,1.5,'91',Number.MAX_SAFE_INTEGER+1]){
  const snapshot=agent('claim','run');snapshot.run.last_sequence=value;
  h.stream.close();h.stream.update(snapshot);
  assert.match(h.sources.at(-1).url,/after=0$/);
 }
});

test('same verified run does not churn connections as its projection advances',()=>{
 const h=harness();h.stream.update(agent());h.sources[0].emit('open');
 h.stream.update(agent('claim-one','run-one','running',20));
 assert.equal(h.sources.length,1);assert.equal(h.sources[0].closed,false);assert.equal(h.statuses.at(-1),'');
});

test('changing claim or run closes the previous connection and rejects its queued callbacks',()=>{
 const h=harness();h.stream.update(agent());const first=h.sources[0];
 first.emit('work');h.stream.update(agent('claim-two','run-two'));
 assert.equal(first.closed,true);assert.equal(h.timers.size,0);
 const before=[h.statuses.length,h.invalidations.length];
 first.emit('open');first.emit('error');first.emit('done');first.emit('work');
 for(const fn of h.cancelled)fn?.();h.flush();
 assert.deepEqual([h.statuses.length,h.invalidations.length],before);
 const second=h.sources[1];h.stream.update(agent('claim-two','run-three'));
 assert.equal(second.closed,true);assert.equal(h.sources.length,3);
 second.emit('done');assert.equal(h.sources[2].closed,false);
});

test('terminal projections and navigation close streams and cancel pending reads',()=>{
 for(const next of [null,{},agent('claim-one','run-one','completed'),agent('claim-one','run-one','paused'),agent('claim-one','run-one','failed')]){
  const h=harness();h.stream.update(agent());h.sources[0].emit('work');h.stream.update(next);
  assert.equal(h.sources[0].closed,true);assert.equal(h.timers.size,0);h.flush();assert.equal(h.invalidations.length,0);
  assert.equal(h.statuses.at(-1),'');
 }
 const h=harness();h.stream.update(agent());h.sources[0].emit('work');h.stream.close();
 h.sources[0].emit('work');for(const fn of h.cancelled)fn?.();h.flush();assert.equal(h.invalidations.length,0);
});

test('a done notification closes its transport and requests one sealed reread, never a UI completion',()=>{
 const h=harness();h.stream.update(agent());const source=h.sources[0];
 source.emit('work');source.emit('done',{data:'{"state":"completed","ready":true}'});
 assert.equal(source.closed,true);assert.equal(h.invalidations.length,0);assert.equal(h.timers.size,1);
 h.flush();assert.deepEqual(h.invalidations,[[]]);
 // A queued callback from the closed terminal connection cannot revive it.
 const statusCount=h.statuses.length;
 source.emit('work');source.emit('error');source.emit('open');source.emit('done');h.flush();
 assert.equal(h.invalidations.length,1);assert.equal(h.statuses.length,statusCount);
 h.stream.update(agent('claim-one','run-one','completed'));assert.equal(h.sources.length,1);
});

test('an unavailable or failed constructor reports periodic-read fallback without inventing activity',()=>{
 for(const options of [{available:false},{throws:true}]){
  const h=harness(options);h.stream.update(agent());
  assert.match(h.statuses.at(-1),/periodically/);assert.equal(h.sources.length,0);
  assert.equal(h.invalidations.length,0);h.stream.update(agent());assert.equal(h.timers.size,0);
 }
});

test('transport error falls back to periodic sealed reads and ignores later closed-connection events',()=>{
 const h=harness();h.stream.update(agent());const source=h.sources[0];
 source.emit('error',{data:'untrusted error payload'});
 assert.match(h.statuses.at(-1),/interrupted.*periodically/);
 assert.equal(source.closed,true);h.flush();assert.deepEqual(h.invalidations,[[]]);
 const statusCount=h.statuses.length;
 source.emit('open');source.emit('error');source.emit('work');h.flush();
 assert.equal(h.statuses.length,statusCount);assert.equal(h.invalidations.length,1);
 h.stream.update(agent());assert.equal(h.sources.length,1);
});

function integrated({state='working',runStatus='running',available=true}={}) {
 const listeners={},timers=new Map(),sources=[],requests=[],reads=[],renders=[];let next=1,refreshes=0;
 const canonical=value=>value===null||typeof value!=='object'?JSON.stringify(value):Array.isArray(value)?'['+value.map(canonical).join(',')+']':'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
 const seal=value=>{const content=Object.fromEntries(Object.entries(value).filter(([key])=>key!=='projection_sha256'));return {...content,projection_sha256:crypto.createHash('sha256').update(canonical(content)).digest('hex')};};
 let packet=seal({...agent('claim-one','run-one',runStatus),state,contract:'casepath.agent-desk-claim/1.0.0',workspace_revision:4,workspace_state_sha256:'saved-state'});
 const mount={dataset:{agentSha:packet.projection_sha256},contains:()=>false,setAttribute(){}};
 const original={before(){},hidden:false},desk={addEventListener(){},setAttribute(){},querySelector(){return null;}};
 const snapshot={claim:{state:{claim_id:'claim-one',revision:4,state_sha256:'saved-state'}}};
 const workspace={snapshot:()=>snapshot,queueRoot:()=>({querySelector:selector=>selector==='#cwQueue'?original:null}),
  canonicalResponse:(...args)=>context.canonicalResponse(...args),
  request:(path,options)=>{requests.push({path,method:options?.method||'GET'});return path.endsWith('/agent')?new Promise(resolve=>reads.push(resolve)):new Promise(()=>{});},
  refresh:async()=>{refreshes++;await Promise.resolve();snapshot.claim.state={claim_id:packet.claim_id,revision:packet.workspace_revision,state_sha256:packet.workspace_state_sha256};mount.dataset={};void listeners['casepath:claim-rendered']({detail:snapshot});}};
 class EventSource {
  constructor(url){this.url=url;this.handlers={};this.closed=false;sources.push(this);}
  addEventListener(type,fn){this.handlers[type]=fn;}
  close(){this.closed=true;}
 }
 const body={};
 const document={body,activeElement:body,documentElement:{dataset:{}},querySelectorAll:()=>[],querySelector:()=>null,createElement:()=>desk,
  getElementById:id=>id==='agentClaimMount'?mount:null,addEventListener(){}};
 const window={CasePathWorkspace:workspace,EventSource:available?EventSource:undefined,
  CasePathAgentClaim:{session:()=>({busy:false,sources:[]}),render:input=>{renders.push(input);return 'Verified claim '+input.claim.revision;},renderInto:(target,html)=>{target.innerHTML=html;},bind(){}},
  addEventListener:(name,fn)=>{listeners[name]=fn;}};
 const context=vm.createContext({module:{exports:{}},document,window,location:{hash:'#claim=claim-one'},
  TextEncoder,crypto:{subtle:{digest:async(_,bytes)=>crypto.createHash('sha256').update(bytes).digest()}},
  setTimeout:(fn,delay)=>{const id=next++;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),
  console,performance:{getEntriesByName:()=>[{}]}});
 const workspaceSource=fs.readFileSync(require.resolve('../casepath/assets/claims-workspace-v1.js'),'utf8');
 vm.runInContext(workspaceSource.slice(workspaceSource.indexOf('  const responseNumbers ='),workspaceSource.indexOf('  async function request(')),context);
 vm.runInContext(fs.readFileSync(require.resolve('../casepath/assets/agent-desk-v2.js'),'utf8'),context);
 context.module.exports.start();
 return {listeners,timers,sources,context,requests,renders,mount,snapshot,get refreshes(){return refreshes;},
  save:change=>{packet=seal({...packet,...change});},resolve:()=>reads.shift()(context.parseResponseJSON(JSON.stringify(packet))),
  fire:delay=>{const entry=[...timers].find(([,timer])=>timer.delay===delay);assert.ok(entry,'Expected a '+delay+'ms saved-work poll');timers.delete(entry[0]);entry[1].fn();}};
}
const settled=()=>new Promise(resolve=>setImmediate(resolve));

test('a pagehide during a sealed read cannot reopen a live connection after navigation',async()=>{
 const h=integrated();h.listeners.pagehide();h.resolve();await settled();
 assert.equal(h.sources.length,0);assert.equal(h.timers.size,0);
});

test('hash navigation invalidates an old read before the next claim has mounted',async()=>{
 const h=integrated();h.context.location.hash='#claim=claim-two';h.listeners.hashchange();h.resolve();await settled();
 assert.equal(h.sources.length,0);assert.equal(h.timers.size,0);
});

test('without EventSource, working projections keep the existing periodic sealed-read fallback',async()=>{
 const h=integrated({available:false});h.resolve();await settled();
 assert.equal(h.sources.length,0);assert.equal([...h.timers.values()].filter(x=>x.delay===1400).length,1);
});

test('a pause request while the run is still active remains polled until its saved checkpoint',async()=>{
 const h=integrated({state:'paused',runStatus:'running',available:false});h.resolve();await settled();
 assert.equal(h.sources.length,0);assert.equal([...h.timers.values()].filter(x=>x.delay===1400).length,1);
});

test('completed claims quietly reread and adopt a draft saved after the run completed',async()=>{
 const h=integrated({state:'waiting_for_you',runStatus:'completed'});h.resolve();await settled();
 assert.equal(h.sources.length,0);assert.equal([...h.timers.values()].filter(x=>x.delay===5000).length,1);
 // The first quiet read returns the same completed snapshot. Settlement must
 // remain observable even when its draft callback takes more than one interval.
 h.fire(5000);h.resolve();await settled();assert.equal(h.refreshes,0);
 h.save({workspace_revision:5,workspace_state_sha256:'draft-state',questions:[{question_id:'draft:request',draft:{event_sha256:'saved-draft'}}]});
 h.fire(5000);h.resolve();await settled();
 assert.equal(h.refreshes,1);assert.equal(h.snapshot.claim.state.revision,5);
 h.resolve();await settled();
 assert.equal(h.renders.length,1);assert.equal(h.renders[0].claim.revision,5);
 assert.equal(h.renders[0].agent.workspace_revision,5);assert.equal(h.renders[0].agent.questions[0].draft.event_sha256,'saved-draft');
 assert.equal(h.mount.dataset.agentSha,h.renders[0].agent.projection_sha256);
 assert.equal(h.requests.filter(request=>request.path.endsWith('/agent')).length,4,'Each poll bypasses the cached completed agent');
 assert.ok(h.requests.every(request=>request.method==='GET'));
 assert.ok(h.requests.every(request=>!request.path.includes('/start')&&!request.path.includes('/runs')));
 assert.equal(h.sources.length,0);assert.equal([...h.timers.values()].filter(x=>x.delay===5000).length,1);
});

test('quiet claim polling stops on navigation and discards a terminal read already in flight',async()=>{
 for(const event of ['hashchange','pagehide']){
  const h=integrated({state:'waiting_for_you',runStatus:'completed'});h.resolve();await settled();
  const stale=[...h.timers.values()].find(timer=>timer.delay===5000)?.fn;assert.ok(stale);
  h.fire(5000);
  h.context.location.hash='#claim=claim-two';h.listeners[event]();
  const before=h.requests.length;stale();assert.equal(h.requests.length,before);
  h.save({workspace_revision:5,workspace_state_sha256:'late-draft-state'});h.resolve();await settled();
  assert.equal(h.timers.size,0);assert.equal(h.refreshes,0);assert.equal(h.renders.length,0);
  assert.ok(h.requests.every(request=>request.method==='GET'));
 }
});
