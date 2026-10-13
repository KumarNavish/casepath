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
