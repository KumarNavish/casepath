'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {resolve} = require('node:path');
const origin = 'https://casepath-demo.example';
const env = {CASEPATH_API_ORIGIN: 'https://casepath-api.example', CASEPATH_PROXY_TOKEN: 'x'.repeat(48)};
const load = async () => (await import(pathToFileURL(resolve(__dirname, '../casepath/tools/sites_worker.mjs')).href)).default;

test('Sites sends native and normalized legacy collection entries to Cases without fetching data', async t => {
  const worker = await load();
  const fetch = t.mock.method(globalThis, 'fetch', async () => {throw Error('must not send');});
  const assets = t.mock.fn(async () => {throw Error('must not open the older collection');});
  for (const path of ['/corpus.html?legacy=1', '/corpus?legacy=1']) {
    for (const method of ['GET', 'HEAD']) {
      const response = await worker.fetch(new Request(origin + path, {method}),
        {...env, ASSETS:{fetch:assets}});
      assert.equal(response.status, 302);
      assert.equal(response.headers.get('location'), origin + '/#autonomous/cases');
    }
  }
  assert.equal(fetch.mock.callCount(), 0);
  assert.equal(assets.mock.callCount(), 0);
});

test('Sites authenticates its upstream request without leaking browser credentials', async t => {
  const worker = await load();
  t.mock.method(globalThis, 'fetch', async req => {
    assert.equal(req.url, 'https://casepath-api.example/api/claim-loops/v1/autonomous/claims');
    assert.equal(req.headers.get('x-casepath-proxy-token'), env.CASEPATH_PROXY_TOKEN);
    assert.equal(req.headers.get('x-casepath-site-origin'), origin);
    assert.equal(req.headers.get('origin'), origin);
    assert.equal(req.headers.get('cookie'), null);
    assert.equal(req.headers.get('authorization'), null);
    assert.equal(req.headers.get('oai-sites-authorization'), null);
    assert.equal(req.headers.get('x-forwarded-host'), null);
    assert.equal(await req.text(), '{"idempotency_key":"unchanged"}');
    return Response.json({saved:true});
  });
  const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/autonomous/claims', {
    method:'POST', headers:{Origin:origin, 'Content-Type':'application/json',
      'X-CasePath-Agent-Work':'1', Cookie:'private', Authorization:'private',
      'OAI-Sites-Authorization':'private', 'X-Forwarded-Host':'hostile.example',
      'X-CasePath-Proxy-Token':'forged', 'X-CasePath-Site-Origin':'https://hostile.example'},
    body:'{"idempotency_key":"unchanged"}',
  }), env);
  assert.equal(response.status,200);
  assert.equal(response.headers.get('cache-control'),'no-store');
});

test('Sites refuses cross-origin mutations before calling the backend', async t => {
  const worker = await load();
  const fetch = t.mock.method(globalThis,'fetch',async()=>{throw Error('must not send');});
  const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/autonomous/claims', {
    method:'POST',headers:{Origin:'https://hostile.example','X-CasePath-Agent-Work':'1'},body:'{}',
  }),env);
  assert.equal(response.status,403);
  assert.equal(fetch.mock.callCount(),0);
});

test('Sites requires configured HTTPS upstream and a server secret', async t => {
  const worker = await load();
  const fetch = t.mock.method(globalThis,'fetch',async()=>{throw Error('must not send');});
  for (const config of [{}, {...env,CASEPATH_API_ORIGIN:'http://localhost:4173'}, {...env,CASEPATH_PROXY_TOKEN:''}]) {
    const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/autonomous/status'),config);
    assert.equal(response.status,503);
  }
  assert.equal(fetch.mock.callCount(),0);
});

test('Sites reports an unavailable backend without exposing upstream details', async t => {
  const worker = await load();
  t.mock.method(globalThis,'fetch',async()=>{throw Error('private token or internal details');});
  const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/autonomous/status'),env);
  assert.equal(response.status,503);
  assert.doesNotMatch(await response.text(),/private token/);
});

test('Sites preserves the Review workspace application headers without requiring an agent-work header', async t => {
  const worker = await load();
  t.mock.method(globalThis,'fetch',async req => {
    assert.equal(req.headers.get('x-casepath-idempotency-key'),'review-operation-1');
    assert.equal(req.headers.get('x-casepath-native-research-mode'),'1');
    assert.equal(req.headers.get('x-casepath-session'),'review-session-1');
    return Response.json({saved:true});
  });
  const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/claims/example/commands', {
    method:'POST',headers:{Origin:origin,'Content-Type':'application/json',
      'X-CasePath-Idempotency-Key':'review-operation-1','X-CasePath-Native-Research-Mode':'1',
      'X-CasePath-Session':'review-session-1'},body:'{}',
  }),env);
  assert.equal(response.status,200);
});
