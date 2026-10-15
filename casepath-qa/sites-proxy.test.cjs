'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const {resolve} = require('node:path');
const {gzipSync, gunzipSync} = require('node:zlib');
const origin = 'https://casepath-demo.example';
const env = {CASEPATH_API_ORIGIN: 'https://casepath-api.example', CASEPATH_PROXY_TOKEN: 'x'.repeat(48)};
const load = async () => (await import(pathToFileURL(resolve(__dirname, '../casepath/tools/sites_worker.mjs')).href)).default;

test('public Sites refuses visitor-forged work authority before any upstream request', async t => {
  const worker = await load();
  const fetch = t.mock.method(globalThis, 'fetch', async () => Response.json({saved:true}, {status:202}));
  const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/autonomous/claims', {
    method:'POST', headers:{Origin:origin, 'Content-Type':'application/json',
      'X-CasePath-Agent-Work':'1', 'X-CasePath-User-Id':'owner', 'X-CasePath-User-Email':'owner@example.test'},
    body:'{"title":"Public visitor","message":"Untrusted intake","files":[],"idempotency_key":"public-forged-work-1"}',
  }), env);
  assert.equal(response.status,403);
  assert.equal(fetch.mock.callCount(),0);
});

test('public Sites rejects every work verb across current generic aliased and unknown paths without reading bodies',async t=>{
  const worker=await load(),upstream=t.mock.method(globalThis,'fetch',async()=>{throw Error('must not send');});
  const assets=t.mock.fn(async()=>{throw Error('must not fetch assets');});
  const prefix='/api/claim-loops/v1/autonomous',paths=[prefix+'/claims',...['start','sources','pause','resume','reconcile-saved-results'].map(action=>`${prefix}/claims/example/${action}`),
    '/api/claim-loops/v1/claims/example/commands','/api/agent-work/v1/start','/api/demo/reset','/api/unknown/','/api','/api/','/healthz','/healthz/','/readyz','/deployment-health','/index.html','/unknown'];
  for(const method of ['POST','PUT','PATCH','DELETE','OPTIONS','TRACE','CONNECT'])for(const path of paths) {
    // Minimal request surface also proves no body/header evaluation precedes denial.
    const request={method,url:origin+path,get body(){throw Error('must not read body');},get headers(){throw Error('must not read headers');}};
    const result=await worker.fetch(request,{...env,CASEPATH_HOSTED_WRITABLE:'1',CASEPATH_AUTONOMOUS_ENABLED:'1',ASSETS:{fetch:assets}});
    assert.equal(result.status,403,`${method} ${path}`);assert.equal(result.headers.get('cache-control'),'no-store');
  }
  assert.equal(upstream.mock.callCount(),0);assert.equal(assets.mock.callCount(),0);
});

test('public Sites keeps GET and HEAD inspection transport available on every public API shape',async t=>{
  const worker=await load(),calls=[];
  t.mock.method(globalThis,'fetch',async request=>{calls.push(request);return new Response(null,{headers:{'Set-Cookie':'upstream-private=1'}});});
  const prefix='/api/claim-loops/v1/autonomous';
  for(const method of ['GET','HEAD'])for(const path of ['/healthz','/readyz','/deployment-health',prefix+'/status',prefix+'/claims',prefix+'/claims/example',prefix+'/claims/example/snapshot',prefix+'/claims/example/events',prefix+'/claims/example/replay?through_seq=1',prefix+'/sources/example/source',prefix+'/sources/example/source/text',prefix+'/sources/example/source/preview',prefix+'/knowledge']) {
    const result=await worker.fetch(new Request(origin+path,{method,headers:{Cookie:'browser-private',Authorization:'browser-private'}}),env);
    assert.equal(result.status,200);assert.equal(result.headers.get('set-cookie'),null);
    const sent=calls.at(-1);assert.equal(sent.method,method);assert.equal(sent.headers.get('x-casepath-proxy-token'),env.CASEPATH_PROXY_TOKEN);
    assert.equal(sent.headers.get('cookie'),null);assert.equal(sent.headers.get('authorization'),null);
  }
  assert.equal(calls.length,26);
});

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
    assert.equal(await req.text(), '');
    return Response.json({saved:true});
  });
  const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/autonomous/claims', {
    method:'GET', headers:{Origin:origin, 'Content-Type':'application/json',
      'X-CasePath-Agent-Work':'1', Cookie:'private', Authorization:'private',
      'OAI-Sites-Authorization':'private', 'X-Forwarded-Host':'hostile.example',
      'X-CasePath-Proxy-Token':'forged', 'X-CasePath-Site-Origin':'https://hostile.example'},
  }), env);
  assert.equal(response.status,200);
  assert.equal(response.headers.get('cache-control'),'no-store');
});

test('Sites streams an operation before completion and cancels upstream when its reader leaves', async t => {
  const worker = await load(), controller = new AbortController();
  let upstream;
  t.mock.method(globalThis, 'fetch', async request => {
    upstream = request;
    return new Response(new ReadableStream({start(stream) {
      stream.enqueue(new TextEncoder().encode('{"type":"operation","kind":"source.open"}\n'));
      request.signal.addEventListener('abort', () => stream.error(request.signal.reason), {once:true});
    }}), {headers:{'Content-Type':'application/x-ndjson'}});
  });
  const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/autonomous/claims/example/operations?mode=live', {
    signal:controller.signal, headers:{Accept:'application/x-ndjson'},
  }), env);
  assert.equal(response.headers.get('content-type'), 'application/x-ndjson');
  assert.equal(response.headers.get('cache-control'), 'no-store');
  const reader = response.body.getReader();
  assert.match(new TextDecoder().decode((await reader.read()).value), /source.open/);
  controller.abort();
  assert.equal(upstream.signal.aborted, true);
  await assert.rejects(reader.read(), {name:'AbortError'});
});

test('Sites forwards operation encoding negotiation and untouched compressed bytes without buffering', async t => {
  const worker = await load();
  const clear = Buffer.from('{"type":"binding","claim_id":"example"}\n{"type":"result"}\n');
  const encoded = gzipSync(clear), requests = [];
  let source;
  t.mock.method(globalThis, 'fetch', async request => {
    requests.push(request);
    assert.equal(request.headers.get('accept-encoding'), 'gzip;q=0.8, identity;q=0.2');
    return new Response(new ReadableStream({start(controller) {
      source = controller;
      controller.enqueue(encoded.subarray(0, 12));
    }}), {headers:{'Content-Type':'application/x-ndjson', 'Content-Encoding':'gzip', 'Vary':'Accept-Encoding'}});
  });
  for (const mode of ['live', 'recorded']) {
    const response = await worker.fetch(new Request(origin+`/api/claim-loops/v1/autonomous/claims/example/operations?mode=${mode}`, {
      headers:{'Accept-Encoding':'gzip;q=0.8, identity;q=0.2'},
    }), env);
    assert.equal(response.headers.get('content-encoding'), 'gzip');
    assert.equal(response.headers.get('vary'), 'Accept-Encoding');
    assert.equal(response.headers.get('cache-control'), 'no-store');
    const reader = response.body.getReader();
    const first = await reader.read();
    assert.deepEqual(Buffer.from(first.value), encoded.subarray(0, 12));
    source.enqueue(encoded.subarray(12));
    source.close();
    const rest = await reader.read();
    assert.equal((await reader.read()).done, true);
    const body = Buffer.concat([first.value, rest.value]);
    assert.deepEqual(body, encoded);
    assert.deepEqual(gunzipSync(body), clear);
  }
  assert.equal(requests.length, 2);
});

test('Sites preserves operation identity refusals and leaves other API negotiation unchanged', async t => {
  const worker = await load();
  t.mock.method(globalThis, 'fetch', async request => {
    const operation = new URL(request.url).pathname.endsWith('/operations');
    assert.equal(request.headers.get('accept-encoding'), operation ? 'gzip;q=0, identity;q=1' : null);
    return new Response('{"type":"binding"}\n', {headers:{'Content-Type':'application/x-ndjson'}});
  });
  for (const path of ['/api/claim-loops/v1/autonomous/claims/example/operations',
    '/api/claim-loops/v1/autonomous/claims/example/snapshot']) {
    const response = await worker.fetch(new Request(origin+path, {headers:{'Accept-Encoding':'gzip;q=0, identity;q=1'}}), env);
    assert.equal(response.headers.get('content-encoding'), null);
    assert.equal(await response.text(), '{"type":"binding"}\n');
  }
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

test('Sites preserves allowlisted Review read headers without requiring an agent-work header', async t => {
  const worker = await load();
  t.mock.method(globalThis,'fetch',async req => {
    assert.equal(req.headers.get('x-casepath-idempotency-key'),'review-operation-1');
    assert.equal(req.headers.get('x-casepath-native-research-mode'),'1');
    assert.equal(req.headers.get('x-casepath-session'),'review-session-1');
    return Response.json({saved:true});
  });
  const response = await worker.fetch(new Request(origin+'/api/claim-loops/v1/claims/example/commands', {
    method:'GET',headers:{Origin:origin,'Content-Type':'application/json',
      'X-CasePath-Idempotency-Key':'review-operation-1','X-CasePath-Native-Research-Mode':'1',
      'X-CasePath-Session':'review-session-1'},
  }),env);
  assert.equal(response.status,200);
});
