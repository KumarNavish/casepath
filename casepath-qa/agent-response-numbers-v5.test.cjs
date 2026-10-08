'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),{createHash,webcrypto}=require('node:crypto');
const workspaceSource=fs.readFileSync(require.resolve('../casepath/assets/claims-workspace-v1.js'),'utf8');
const deskSource=fs.readFileSync(require.resolve('../casepath/assets/agent-desk-v2.js'),'utf8');
const hash=text=>createHash('sha256').update(text).digest('hex');
function harness({fetch,JSON:parser}={}){
 const timers=new Map(),requests=[];let next=0;
 const c={api:'',AbortController,TextEncoder,crypto:webcrypto,
  setTimeout(fn){timers.set(++next,fn);return next;},clearTimeout:id=>timers.delete(id),
  fetch:async(path,options)=>{requests.push({path,options});return fetch(path,options);}};
 if(parser)c.JSON=parser;
 vm.createContext(c);
 vm.runInContext(workspaceSource.slice(workspaceSource.indexOf('  const responseNumbers ='),workspaceSource.indexOf('  async function requireVerifiedResponse(')),c);
 c.workspace={canonicalResponse:c.canonicalResponse};
 vm.runInContext(deskSource.slice(deskSource.indexOf('    async function verify('),deskSource.indexOf('    function display()')),c);
 return {c,timers,requests};
}
function receipt(cost='1e-05',seconds='1.0'){
 // These spellings are emitted by Python json.dumps, including integral floats.
 const material='{"contract":"casepath.agent-work/1.0.0","objects":[],"summary":{"provider_cost_usd":'+cost+',"roles":[{"seconds":'+seconds+'}]}}';
 const wire='{ "summary": { "roles": [{"seconds":'+seconds+'}], "provider_cost_usd":'+cost+' }, "response_sha256":"'+hash(material)+'", "objects":[], "contract":"casepath.agent-work/1.0.0" }';
 return {material,wire};
}

test('real response parsing verifies Python numeric spellings without changing values or sealed bytes',async()=>{
 for(const cost of ['1e-05','1e-07','0.0','-0.0','0','0.001']){
  const {wire,material}=receipt(cost),h=harness({fetch:async()=>new Response(wire)});
  const value=await h.c.request('/api/agent-work/v1/claims/example/runs/work.example');
  assert.equal(h.c.canonicalResponse(value,'response_sha256'),material);
  assert.equal(typeof value.summary.provider_cost_usd,'number');
  assert.ok(Object.is(value.summary.provider_cost_usd,Number(cost)));
  await h.c.verify(value,'response_sha256','casepath.agent-work/1.0.0');
  await h.c.verify(value,'response_sha256','casepath.agent-work/1.0.0'); // Same cached object retains provenance.
  assert.equal(h.requests.length,1);assert.equal(h.timers.size,0);
  assert.deepEqual(Object.keys(value).sort(),['contract','objects','response_sha256','summary']);
 }
});

test('nested agent packets retain their own numeric provenance inside a sealed control receipt',async()=>{
 const inner='{"contract":"casepath.agent-desk-claim/1.0.0","live_work":{"reader":{"provider_cost_usd":1e-05}},"run":{"provider_cost_usd":1e-05,"roles":[{"seconds":0.0}]}}';
 const agent=inner.slice(0,-1)+',"projection_sha256":"'+hash(inner)+'"}';
 const h=harness({fetch:async()=>new Response('{"agent":'+agent+'}')});
 const packet=await h.c.request('/control');
 await h.c.verify(packet.agent,'projection_sha256','casepath.agent-desk-claim/1.0.0');
 assert.equal(h.c.canonicalResponse(packet.agent,'projection_sha256'),inner);
});

test('changed members, cloned payloads, and tampered server values cannot use original numeric tokens',async()=>{
 const changes=[v=>v.summary.provider_cost_usd=0.1,v=>v.summary.roles[0].seconds=2,
  v=>v.summary.roles.push({seconds:1}),v=>v.contract='changed',v=>v.extra=true,
  v=>delete v.summary.roles,v=>Object.defineProperty(v.summary,'provider_cost_usd',{get(){return 0.00001;}})];
 for(const change of changes){
  const h=harness({fetch:async()=>new Response(receipt().wire)}),value=await h.c.request('/read');
  change(value);assert.throws(()=>h.c.canonicalResponse(value,'response_sha256'),/changed after/);
 }
 const h=harness({fetch:async()=>new Response(receipt().wire)}),value=await h.c.request('/read');
 assert.throws(()=>h.c.canonicalResponse({...value},'response_sha256'),/changed after/);
 assert.throws(()=>h.c.canonicalResponse(JSON.parse(JSON.stringify(value)),'response_sha256'),/changed after/);
 const tampered=harness({fetch:async()=>new Response(receipt().wire.replace('1e-05','1e-04'))});
 await assert.rejects(()=>tampered.c.verify(tampered.c.parseResponseJSON(receipt().wire.replace('1e-05','1e-04')),'response_sha256','casepath.agent-work/1.0.0'),/identity differs/);
});

test('unsupported numeric provenance and unsafe numeric values fail closed as received but unverified',async()=>{
 const unsupported={...JSON,parse(text,reviver){return JSON.parse(text,function(key,value){return reviver.call(this,key,value);});}};
 const h=harness({fetch:async()=>new Response(receipt().wire),JSON:unsupported});
 await assert.rejects(()=>h.c.request('/write',{method:'POST'}),error=>/current browser/.test(error.message)&&error.responseReceived===true&&error.ambiguousResponse===true&&!error.transportFailure);
 for(const token of ['9007199254740993','1e400']){
  const unsafe=harness({fetch:async()=>new Response('{"value":'+token+'}')});
  await assert.rejects(()=>unsafe.c.request('/read'),/cannot be represented safely/);
 }
 assert.equal(h.timers.size,0);
});

test('HTTP rejections, malformed replies and transport timeouts retain request recovery semantics',async()=>{
 const rejected=harness({fetch:async()=>new Response('{"detail":{"reason":"Busy","code":"request_in_progress"}}',{status:409})});
 await assert.rejects(()=>rejected.c.request('/write',{method:'POST'}),error=>error.message==='Busy'&&error.responseReceived===true&&error.ambiguousResponse===true&&error.status===409);
 const malformed=harness({fetch:async()=>new Response('not json')});assert.equal(await malformed.c.request('/read'),null);
 const timed=harness({fetch:(_,options)=>new Promise((_,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('aborted'))))});
 const pending=timed.c.request('/read');[...timed.timers.values()][0]();
 await assert.rejects(()=>pending,error=>/timed out/.test(error.message)&&error.transportFailure===true);
 assert.equal(timed.timers.size,0);
});
