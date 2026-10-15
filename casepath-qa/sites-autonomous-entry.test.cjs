'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const {pathToFileURL} = require('node:url');
const index = readFileSync(resolve(__dirname, '../casepath/index.html'), 'utf8');
const configuration = '<script>window.CASEPATH_API = window.location.origin;window.CASEPATH_HOSTED_AUTONOMOUS = true;window.CASEPATH_PUBLIC_READ_ONLY = true;</script>';
const entry = '<script src="assets/autonomous-entry-v1.js';

for (const preconfigured of [false, true]) {
  test(`Sites serves the autonomous entry with one preceding same-origin configuration (configured=${preconfigured})`, async () => {
    const worker = (await import(pathToFileURL(resolve(__dirname, '../casepath/tools/sites_worker.mjs')).href)).default;
    const html = preconfigured ? index.replace('<head>', '<head>' + configuration) : index;
    const response = await worker.fetch(new Request('https://casepath.invalid/'), {
      ASSETS: {fetch: async request => {
        assert.equal(new URL(request.url).pathname, '/index.html');
        return new Response(html);
      }},
    });
    assert.equal(response.status, 200);
    const served = await response.text();
    assert.equal(served.split(configuration).length - 1, 1);
    assert.ok(served.indexOf(configuration) < served.indexOf(entry));
    assert.ok(served.indexOf(configuration) < served.indexOf('<script>\n'), 'capability must precede entry selection');
    assert.match(response.headers.get('content-type'), /text\/html/);
    assert.equal(response.headers.get('cache-control'), 'no-cache');
  });
}

test('public hosted index aliases always select passive autonomous inspection before legacy boot work',async()=>{
  const {runInNewContext}=require('node:vm');
  const worker=(await import(pathToFileURL(resolve(__dirname,'../casepath/tools/sites_worker.mjs')).href)).default;
  for(const search of ['?journey=review','?journey=legacy-v20','?journey=insurance-v1','?foundation=live-v1','']) {
    const location=new URL('https://casepath.invalid/index.html'+search),dataset={},calls=[],loaded=[];
    const response=await worker.fetch(new Request(location.href),{ASSETS:{fetch:async()=>new Response(index)}});
    const served=await response.text();
    const context={location,URLSearchParams,window:{location},document:{documentElement:{dataset},head:{append:script=>loaded.push(script.src)},createElement:()=>({}),querySelector:()=>({content:'legacy.js'})},sessionStorage:{getItem:()=>null,setItem(){}},crypto:{randomUUID:()=> 'fixture-uuid'},fetch:async(...args)=>{calls.push(args);return {ok:true,json:async()=>({})};}};
    for(const match of served.matchAll(/<script>([\s\S]*?)<\/script>/g))runInNewContext(match[1],context);
    assert.equal(dataset.autonomousWorkspace,'true',search);assert.equal(dataset.claimsWorkspace,undefined,search);
    assert.deepEqual(calls,[],search);assert.deepEqual(loaded,[],search);
  }
});

test('Sites rejects an index without its executable workspace entry', async () => {
  const worker = (await import(pathToFileURL(resolve(__dirname, '../casepath/tools/sites_worker.mjs')).href)).default;
  const response = await worker.fetch(new Request('https://casepath.invalid/'), {
    ASSETS: {fetch: async () => new Response('<html><body>No workspace entry</body></html>')},
  });
  assert.equal(response.status, 500);
});

test('autonomous entry preserves the cached controller on persisted pagehide and destroys a departing page',async()=>{
  const {runInNewContext}=require('node:vm'),listeners=new Map(),workspace={innerHTML:'verified prefix'},loaded=[];
  let mounts=0,destroys=0;
  const window={CasePathAutonomous:{mount(container){assert.equal(container,workspace);mounts++;},destroy(){destroys++;workspace.innerHTML='';}},addEventListener(type,listener){listeners.set(type,listener);}};
  const document={documentElement:{dataset:{autonomousWorkspace:'true'}},createElement:()=>({}),querySelector:()=>({content:'verified-workspace.js'}),getElementById:()=>workspace,body:{append(script){loaded.push(script.src);script.onload();}}};
  await runInNewContext(readFileSync(resolve(__dirname,'../casepath/assets/autonomous-entry-v1.js'),'utf8'),{window,document,location:new URL('https://casepath.invalid/')});
  assert.equal(mounts,1);assert.deepEqual(loaded,['verified-workspace.js']);
  listeners.get('pagehide')({persisted:true});assert.equal(destroys,0,'a native back-forward cache entry retains its controller and verified view');assert.equal(workspace.innerHTML,'verified prefix');
  listeners.get('pagehide')({persisted:false});assert.equal(destroys,1);assert.equal(workspace.innerHTML,'');
});

test('the hosted opening preloads exact recorded bytes without waiting or enabling private replay data',async()=>{
  const {runInNewContext}=require('node:vm');
  const {createHash}=require('node:crypto');
  const descriptor=JSON.parse(index.match(/<meta name="casepath-recorded-opening" content='([^']+)'/)[1]);
  const bytes=readFileSync(resolve(__dirname,'../casepath/assets/autonomous-recorded-heating-v1.json'));
  assert.equal(bytes.length,descriptor.bytes);
  assert.equal(createHash('sha256').update(bytes).digest('hex'),descriptor.sha256);
  assert.equal(JSON.parse(bytes).deployment_commit,descriptor.deployment_commit);
  for(const publicReadOnly of [true,false]) {
    const location=new URL('https://casepath.invalid/'),links=[],calls=[],mounted=[];
    const window={location,CASEPATH_PUBLIC_READ_ONLY:publicReadOnly,CasePathAutonomous:{mount:(_container,options)=>mounted.push(options)},addEventListener(){}};
    const document={documentElement:{dataset:{}},createElement:()=>({}),querySelector:selector=>({content:selector.includes('casepath-recorded-opening')?JSON.stringify(descriptor):'workspace.js'}),head:{append:link=>links.push(link)},body:{append:script=>script.onload()},getElementById:()=>({})};
    const context={location,URLSearchParams,window,document,sessionStorage:{getItem:()=>null,setItem(){}},crypto:{randomUUID:()=> 'fixture-uuid'},fetch:async(...args)=>{calls.push(args);throw Error('Boot must not fetch the API');}};
    const boot=index.match(/<script>\n([\s\S]*?)<\/script>/)[1];
    runInNewContext(boot,context);
    assert.equal(links.length,publicReadOnly?1:0);
    if(publicReadOnly) { assert.equal(links[0].rel,'preload');assert.equal(links[0].as,'fetch');assert.equal(links[0].href,descriptor.url);assert.equal(links[0].fetchPriority,'high'); }
    await runInNewContext(readFileSync(resolve(__dirname,'../casepath/assets/autonomous-entry-v1.js'),'utf8'),context);
    assert.equal(mounted.length,1,'mount must not await preload completion');
    assert.equal(JSON.stringify(mounted[0].recordedPacket),publicReadOnly?JSON.stringify(descriptor):undefined);
    assert.deepEqual(calls,[],'opening assets never grant API write or inference authority');
  }
});
