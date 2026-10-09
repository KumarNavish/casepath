'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {gunzipSync} = require('node:zlib');
const {createHash} = require('node:crypto');
const {setTimeout: delay} = require('node:timers/promises');
const {chromium} = require('playwright');

const root = path.resolve(__dirname, '..');
const base = '/api/claim-loops/v1/autonomous';
const captured = JSON.parse(gunzipSync(fs.readFileSync(path.join(root, 'design/evidence-path/recorded-fixtures.json.gz')))).responses;
const historicalIds = captured[`${base}/claims`].claims.map(row => row.claim_id);
// Deliberately independent of the production DEMO_CASES export. A roster change
// must not silently make its own regression assertion pass.
const demoIds = [
  'clm_e262801f9368bc12', 'clm_521c20913f4e0f9b', 'clm_ee29ac770b1bf7b9',
  'clm_f69b1747447bc221', 'clm_0c5e7c7723a3c694', 'clm_2a9c260c26afaa34',
  'clm_c44ddc0914ba9298', 'clm_7dbd7c7d1c4ddf90', 'clm_9a179a4481767d43',
];
const processedId = demoIds[3];
const otherId = demoIds[4];
const unprocessedId = 'clm_fixture_001';
const sha = value => createHash('sha256').update(value).digest('hex');
const sorted = values => [...values].sort();
const clone = value => structuredClone(value);
const canonical = value => Array.isArray(value)
  ? `[${value.map(canonical).join(',')}]`
  : value && typeof value === 'object'
    ? `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`
    : JSON.stringify(value);

function processedEnvelope(id, recordedId) {
  const envelope = clone(captured[`${base}/claims/${recordedId}`]);
  envelope.state.claim_id = id;
  envelope.state.graph.claim_id = id;
  envelope.state.source_descriptors.forEach(source => { source.claim_id = id; });
  Object.assign(envelope.projection, {
    claim_id: id, revision: envelope.state.revision, state_sha256: envelope.state.state_sha256,
    parent_revision: envelope.state.revision, parent_state_sha256: envelope.state.state_sha256,
  });
  return envelope;
}

function unprocessedEnvelope(id, index) {
  const message = `Original fictional packet ${index}: please inspect the attached notice before determining any facts.`;
  const state = {
    claim_id: id, title: `Original intake ${String(index).padStart(3, '0')}`,
    mode: 'unprocessed', status: 'not_started', phase: 'not_run', phase_summary: '',
    revision: 0, state_sha256: sha(`unprocessed fixture ${id}`),
    message, source_preview: {text: message},
    graph: null, evaluation: null, facts: [], obligations: [], actions: [], results: [],
    outcome: null, deferral: null, acquired_sources: [], knowledge_uses: [], knowledge_published: [],
    source_descriptors: [{claim_id: id, artifact_id: `original-${index}`, file_name: `incoming-${index}.txt`, media_type: 'text/plain', sha256: sha(message)}],
  };
  return {state, projection: {claim_id: id, revision: 0, state_sha256: state.state_sha256}};
}

function fixtureData(config = {}) {
  const envelopes = {}, sources = {};
  demoIds.forEach((id, index) => { envelopes[id] = processedEnvelope(id, historicalIds[index]); });
  historicalIds.forEach(id => { envelopes[id] = processedEnvelope(id, id); });
  for (let index = 1; index <= 132; index++) {
    const id = `clm_fixture_${String(index).padStart(3, '0')}`;
    const envelope = unprocessedEnvelope(id, index);
    envelopes[id] = envelope;
    const source = envelope.state.source_descriptors[0];
    const preview = {...source, text_sha256: sha(envelope.state.message), text: envelope.state.message,
      extraction: 'local_text_preview', coverage: 'full', preview_only: true, evidence_admitted: false};
    preview.preview_sha256 = sha(canonical(preview));
    sources[`${id}/${source.artifact_id}`] = preview;
  }
  if (config.originalStartId) envelopes[config.originalStartId] = unprocessedEnvelope(config.originalStartId, 151);
  const rows = Object.values(envelopes).map(({state}) => ({
    claim_id: state.claim_id, title: state.title, mode: state.mode, status: state.status,
    phase: state.phase, phase_summary: state.phase_summary, revision: state.revision,
    state_sha256: state.state_sha256, outcome: state.outcome,
    browse_metadata: {domain: state.claim_id === unprocessedId ? 'termination' : 'other'},
  }));
  assert.equal(rows.length, 150);
  return {envelopes, sources, rows};
}

let browser;
test.before(async () => {
  browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH || '/usr/bin/chromium',
    headless: true, args: ['--no-sandbox'],
  });
});
test.after(async () => { await browser?.close(); });

async function eventually(read, message, timeout = 5000) {
  const deadline = Date.now() + timeout;
  do {
    if (await read()) return;
    await delay(10);
  } while (Date.now() < deadline);
  assert.fail(message);
}

async function fixturePage(t, config = {}) {
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, serviceWorkers: 'block'});
  const page = await context.newPage(), errors = [], network = [];
  page.on('pageerror', error => errors.push(error.message));
  t.after(async () => {
    const writes = await page.evaluate(() => window.__fixture?.calls.filter(call => call.method !== 'GET') || []);
    const startViolations = await page.evaluate(() => window.__fixture?.startViolations || []);
    await page.evaluate(() => window.__controller?.destroy());
    await context.close();
    if (config.originalStartId) {
      assert.ok(writes.every(call => call.method === 'POST' && call.url === `${base}/claims/${config.originalStartId}/start`), 'only the explicitly configured Start POST is permitted');
      assert.deepEqual(startViolations, [], 'every mocked Start must carry the original guard and unchanged retry identity');
    } else assert.deepEqual(writes, [], 'opening and browsing product views must not write');
    assert.deepEqual(errors, [], 'production controller browser errors');
    assert.ok(network.every(request => request.method === 'GET'), 'browser requests cannot write');
    assert.equal(network.filter(request => request.url.includes('/api/')).length, 0, 'the API fixture must remain entirely local');
  });
  // The only document is fulfilled in memory. Every actual asset/API/provider
  // request is blocked; the response seam below never uses the network. The
  // original-start scenario alone permits its explicitly guarded mock POST.
  await page.route('**/*', route => {
    network.push({url: route.request().url(), method: route.request().method()});
    return route.request().isNavigationRequest()
      ? route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><html><head><meta charset="utf-8"></head><body><main id="workspace"></main></body></html>'})
      : route.abort('blockedbyclient');
  });
  await page.goto('http://localhost:41999/');
  const time = new Date('2026-10-09T12:00:00Z');
  await page.clock.install({time});
  await page.clock.pauseAt(time);
  await page.addStyleTag({path: path.join(root, 'casepath/assets/autonomous-workspace-v1.css')});
  await page.addScriptTag({path: path.join(root, 'casepath/assets/autonomous-workspace-v1.js')});
  await page.evaluate(({data, config, base}) => {
    window.__fixture = {...data, ...config, calls: [], held: [], splitRevision: {}, startPosts: 0, startViolations: []};
    const fixture = window.__fixture;
    const originalStart = fixture.originalStartId ? structuredClone(fixture.envelopes[fixture.originalStartId]) : null;
    const response = (status, body) => ({ok: status >= 200 && status < 300, status, json: async () => structuredClone(body)});
    const advance = id => {
      const envelope = fixture.envelopes[id];
      envelope.state.revision++;
      envelope.state.state_sha256 = (envelope.state.revision % 16).toString(16).repeat(64);
      envelope.state.last_event_sha256 = ((envelope.state.revision + 1) % 16).toString(16).repeat(64);
      Object.assign(envelope.projection, {
        claim_id: id, revision: envelope.state.revision, state_sha256: envelope.state.state_sha256,
        parent_revision: envelope.state.revision, parent_state_sha256: envelope.state.state_sha256,
      });
      return envelope;
    };
    const batch = (state, after) => ({
      events: Array.from({length: Math.max(0, state.revision - after)}, (_, index) => {
        const seq = after + index + 1;
        return {seq, claim_id: state.claim_id, revision: seq, state_sha256: seq === state.revision ? state.state_sha256 : 'e'.repeat(64), event_sha256: seq === state.revision ? state.last_event_sha256 : 'd'.repeat(64), kind: seq === 1 ? 'intake' : 'work.phase', payload: {summary: 'Deterministic browser fixture revision'}};
      }),
      current_revision: state.revision, current_state_sha256: state.state_sha256,
      cursor_sha256: state.revision === 0 ? null : state.last_event_sha256,
    });
    const fetch = async (url, init = {}) => {
      const parsed = new URL(String(url), location.origin), method = init.method || 'GET';
      fixture.calls.push({url: parsed.pathname + parsed.search, method, time: performance.now(), body: init.body, headers: init.headers || {}});
      const relative = parsed.pathname.slice(base.length);
      if (method === 'POST' && originalStart && relative === `/claims/${fixture.originalStartId}/start`) {
        const body = JSON.parse(init.body), headers = init.headers || {};
        const correct = body.expected_revision === 0 && body.expected_state_sha256 === originalStart.state.state_sha256
          && typeof body.idempotency_key === 'string' && body.idempotency_key.startsWith('browser.')
          && headers['X-CasePath-Agent-Work'] === '1' && headers['Content-Type'] === 'application/json'
          && (!fixture.firstStartBody || init.body === fixture.firstStartBody);
        if (!correct) {
          fixture.startViolations.push('Start guard, intent header or retry body changed.');
          return response(422, {detail: 'Start fixture rejected a changed guard or retry identity.'});
        }
        fixture.startPosts++;
        fixture.firstStartBody ||= init.body;
        // The first request is accepted at revision 1, but its response is lost.
        // Background reads can observe acceptance while the browser retains
        // the unconfirmed original guard and idempotency key.
        const state = {...structuredClone(originalStart.state), mode: 'started', status: 'running', phase: 'acquiring',
          revision: 1, state_sha256: '1'.repeat(64), last_event_sha256: '2'.repeat(64),
          graph: {claim_id: fixture.originalStartId, title: 'Original packet investigation', graph_sha256: '3'.repeat(64),
            nodes: [{node_id: 'investigate_packet', label: 'Inspect original packet', entry: true}], edges: []},
          evaluation: {nodes: [{node_id: 'investigate_packet', execution_state: 'ready'}], edges: [], documents: []}};
        const envelope = {state, projection: {claim_id: state.claim_id, revision: 1, state_sha256: state.state_sha256}};
        const accepted = structuredClone(envelope);
        fixture.envelopes[state.claim_id] = envelope;
        if (fixture.startPosts === 1) throw new TypeError('Isolated Start network outcome is uncertain.');
        // The explicit retry returns the same accepted result. A concurrent
        // writer advances the live head before the follow-up snapshot.
        advance(state.claim_id);
        return response(200, accepted);
      }
      if (method !== 'GET') return response(405, {detail: 'This browser fixture prohibits writes.'});
      if (relative === '/claims') {
        const limit = Number(parsed.searchParams.get('limit') || 50), offset = Number(parsed.searchParams.get('offset') || 0);
        return response(200, {claims: fixture.rows.slice(offset, offset + limit), total: fixture.rows.length, limit, offset});
      }
      if (relative === '/knowledge') return response(200, {versions: [], uses: [], quarantined: []});
      if (relative === '/status') return response(200, {enabled: true, provider_ready: fixture.providerReady ?? Boolean(fixture.originalStartId)});
      const source = relative.match(/^\/sources\/([^/]+)\/([^/]+)\/(?:text|preview)$/);
      if (source) return response(fixture.sources[`${source[1]}/${source[2]}`] ? 200 : 404, fixture.sources[`${source[1]}/${source[2]}`] || {detail: 'No source in this fixture.'});
      const read = relative.match(/^\/claims\/([^/]+)(?:\/(snapshot|events|replay))?$/);
      if (!read || !fixture.envelopes[read[1]]) return response(404, {detail: 'No GET response in this fixture.'});
      const [, id, kind] = read, after = Number(parsed.searchParams.get('after') || 0);
      if (kind === 'replay') {
        const live = fixture.envelopes[id], through = Number(parsed.searchParams.get('through_seq') || 0);
        const envelope = structuredClone(live), state = envelope.state;
        state.revision = through;
        state.state_sha256 = through === live.state.revision ? live.state.state_sha256 : (through % 16).toString(16).repeat(64);
        state.last_event_sha256 = through === live.state.revision ? live.state.last_event_sha256 ?? null : through === 0 ? null : ((through + 1) % 16).toString(16).repeat(64);
        state.status = fixture.replayStatus || 'running';
        if (through === 0) Object.assign(state, {mode: 'unprocessed', status: 'not_started', phase: 'not_run', graph: null, evaluation: null, facts: [], obligations: [], actions: [], acquired_sources: [], outcome: null, deferral: null});
        Object.assign(envelope.projection, {claim_id: id, revision: through, state_sha256: state.state_sha256, parent_revision: through, parent_state_sha256: state.state_sha256});
        const provenance = {claim_id: id, prefix_revision: through, fixture: 'deterministic accepted prefix',
          sources: structuredClone(state.source_descriptors), source_map: structuredClone(state.original_binding?.source_map || []),
          rule_pack_sha256: [...new Set((state.receipts || []).map(row => row.receipt?.rule_pack_sha256).filter(Boolean))].sort()};
        for (const [field, stateField] of [['source_roster_sha256', 'source_roster_sha256'], ['policy_id', 'policy_id'], ['run_id', 'run_id'], ['event_sha256', 'last_event_sha256']]) {
          if (state[stateField] !== undefined) provenance[field] = state[stateField];
        }
        for (const field of ['original_binding_sha256', 'claim_binding_sha256', 'corpus_manifest_sha256', 'static_template_sha256']) {
          if (state.original_binding?.[field] !== undefined) provenance[field] = state.original_binding[field];
        }
        const currentEvent = live.state.revision === 0 ? null : live.state.last_event_sha256;
        return response(200, {...envelope, ...batch(state, 0), mode: 'replay', replay_only: true, through_seq: through,
          current_revision: live.state.revision, current_state_sha256: live.state.state_sha256, current_event_sha256: currentEvent,
          current_head: {revision: live.state.revision, state_sha256: live.state.state_sha256, event_sha256: currentEvent}, provenance});
      }
      if (kind === 'snapshot') {
        if (fixture.snapshotStatus && fixture.snapshotStatus !== 200) return response(fixture.snapshotStatus, {detail: 'Configured snapshot transport response.'});
        const envelope = structuredClone(fixture.envelopes[id]);
        const snapshot = {...envelope, ...batch(envelope.state, after)};
        if (fixture.atomicWriter) advance(id); // writer runs after the complete read was captured
        if (fixture.mismatchedSnapshots > 0) { fixture.mismatchedSnapshots--; snapshot.current_revision++; }
        if (fixture.corruptProjection) snapshot.projection.state_sha256 = '0'.repeat(64);
        if (fixture.holdId === id) return new Promise(resolve => fixture.held.push({id, release: () => resolve(response(200, snapshot))}));
        return response(200, snapshot);
      }
      if (!kind) {
        if (fixture.splitWriter) advance(id);
        return response(200, fixture.envelopes[id]);
      }
      if (fixture.splitWriter) advance(id); // a writer advances between the legacy pair
      const events = batch(fixture.envelopes[id].state, after);
      if (fixture.corruptLegacyHash) events.current_state_sha256 = '0'.repeat(64);
      return response(200, events);
    };
    window.__controller = window.CasePathAutonomous.mount(document.querySelector('#workspace'), {fetch});
  }, {data: fixtureData(config), config, base});
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'Cases did not load all 150 fixture rows');
  return page;
}

const calls = (page, suffix) => page.evaluate(suffix => window.__fixture.calls.filter(call => new URL(call.url, location.origin).pathname.endsWith(suffix)), suffix);
async function open(page, id) {
  await page.evaluate(id => { void window.__controller.openClaim(id); }, id);
}
async function title(page, id) {
  await eventually(async () => {
    const rendered = await page.locator('[data-au-claim-title]').count() ? await page.locator('[data-au-claim-title]').textContent() : null;
    const expected = await page.evaluate(id => window.__fixture.envelopes[id].state.title, id);
    return rendered === expected;
  }, `The matching saved claim ${id} did not render`);
}

test('Cases pages all 150 IDs and Demonstration contains exactly the nine canonical Cases IDs', async t => {
  const page = await fixturePage(t);
  const actual = await page.locator('[data-au-claim-row]').evaluateAll(rows => rows.map(row => row.dataset.auClaimRow));
  const expected = await page.evaluate(() => window.__fixture.rows.map(row => row.claim_id));
  assert.equal(new Set(actual).size, 150);
  assert.deepEqual(sorted(actual), sorted(expected));
  const collectionCalls = await calls(page, '/claims');
  assert.ok(collectionCalls.length >= 2, 'a 50-row first page must cause another collection read');
  let nextOffset = 0;
  for (const call of collectionCalls) {
    const params = new URL(call.url, 'http://fixture.invalid').searchParams;
    assert.equal(Number(params.get('offset') || 0), nextOffset, 'collection pages must not skip or repeat rows');
    nextOffset += Math.min(Number(params.get('limit') || 50), 150 - nextOffset);
  }
  assert.equal(nextOffset, 150);
  await page.locator('.au-nav [data-au-nav="work"]').click();
  assert.equal(new URL(page.url()).hash, '#autonomous/cases');
  await page.locator('.au-nav [data-au-nav="demonstration"]').click();
  await eventually(() => page.locator('[data-au-demo-case]').count().then(count => count === 9), 'Demonstration did not render exactly nine cases');
  const demo = await page.locator('[data-au-demo-case]').evaluateAll(rows => rows.map(row => row.dataset.auDemoCase));
  assert.deepEqual(sorted(demo), sorted(demoIds));
  assert.ok(demo.every(id => actual.includes(id)), 'demonstrations must refer to Cases identities');
  assert.ok(demo.every(id => !historicalIds.includes(id)), 'historical autonomous captures cannot become demonstration members');
  assert.equal(new URL(page.url()).hash.split('?')[0], '#autonomous/demonstration');
  assert.equal(await page.locator('[data-au-demo-mode="replay"]').getAttribute('aria-pressed'), 'true');
  await page.locator('[data-au-demo-mode="live"]').click();
  assert.equal(await page.locator('[data-au-demo-mode="live"]').getAttribute('aria-pressed'), 'true');
  await page.locator('[data-au-demo-mode="replay"]').click();
  assert.equal(await page.locator('[data-au-demo-mode="replay"]').getAttribute('aria-pressed'), 'true');
  await page.evaluate(() => { location.hash = '#autonomous/work'; });
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'The prior Work route did not resolve to Cases');
});

test('Verified replay stays visible as presentation mode when the accepted prefix status is Working', async t => {
  const page = await fixturePage(t, {replayStatus: 'running'});
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {mode: 'replay', through: 2}); }, processedId);
  await title(page, processedId);
  assert.equal(await page.locator('[data-au-presentation-mode]').innerText(), 'Verified replay');
  assert.equal(await page.locator('.au-work-head .au-status').innerText(), 'Working');
  assert.match(new URL(page.url()).hash, /mode=replay/);
  assert.match(new URL(page.url()).hash, /through=2/);
  assert.equal((await calls(page, `/claims/${processedId}/replay`)).length, 1);
  assert.equal(await page.locator('[data-au-arrival], [data-au-pause], [data-au-resume], [data-au-start]').count(), 0, 'a replay cannot expose live write controls');
  const before = (await calls(page, `/claims/${processedId}/snapshot`)).length;
  await page.evaluate(async () => { await window.__controller.refresh(); await window.__controller.refresh(); });
  await page.clock.runFor(7000);
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, before, 'a replay must not poll live state');
  assert.equal(await page.locator('[data-au-presentation-mode]').innerText(), 'Verified replay');
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {mode: 'replay', through: 0}); }, processedId);
  await title(page, processedId);
  assert.equal(await page.locator('[data-au-arrival], [data-au-pause], [data-au-resume], [data-au-start]').count(), 0, 'a revision-zero replay cannot expose Start or file arrival');
  await page.evaluate(() => window.__controller.refresh());
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, before);
  assert.deepEqual(await page.evaluate(() => window.__fixture.calls.filter(call => call.method !== 'GET')), []);
});

test('an explicit original Start preserves its guarded retry after background acceptance and navigation', async t => {
  const page = await fixturePage(t, {originalStartId: processedId});
  const original = await page.evaluate(id => structuredClone(window.__fixture.envelopes[id].state), processedId);
  const posts = async () => (await calls(page, `/claims/${processedId}/start`)).filter(call => call.method === 'POST');
  await open(page, processedId);
  await title(page, processedId);
  await eventually(() => page.locator('[data-au-start]').isEnabled(), 'the configured original Start did not become available');
  assert.equal(original.revision, 0);
  assert.equal((await posts()).length, 0, 'opening an original claim cannot start it');
  await page.locator('[data-au-start]').click();
  await eventually(() => page.locator('.au-global-status').innerText().then(value => value.includes('Response unconfirmed')), 'the uncertain Start response was not retained for retry');
  const [first] = await posts(), firstBody = JSON.parse(first.body);
  assert.equal((await posts()).length, 1, 'one Start click must make exactly one POST');
  assert.deepEqual(sorted(Object.keys(firstBody)), ['expected_revision', 'expected_state_sha256', 'idempotency_key']);
  assert.equal(firstBody.expected_revision, 0);
  assert.equal(firstBody.expected_state_sha256, original.state_sha256);
  assert.match(firstBody.idempotency_key, /^browser\.[a-f0-9-]+$/i);
  assert.equal(first.headers['X-CasePath-Agent-Work'], '1');
  assert.equal(first.headers['Content-Type'], 'application/json');
  await page.clock.runFor(7000);
  await eventually(async () => {
    if (!await page.locator('[data-au-disclosure="claim-record"] pre').count()) return false;
    return JSON.parse(await page.locator('[data-au-disclosure="claim-record"] pre').textContent()).state.revision === 1;
  }, 'background polling did not observe the accepted revision after the Start response was lost');
  assert.match(await page.locator('.au-work-head').innerText(), /revision 1\b/i);
  assert.equal(await page.locator('[data-au-start]').innerText(), 'Retry start');
  assert.equal(await page.locator('[data-au-start]').isEnabled(), true, 'the nonzero accepted revision must retain its original pending Start retry');
  assert.equal((await posts()).length, 1, 'a network-uncertain Start cannot retry automatically');
  const liveReads = (await calls(page, `/claims/${processedId}/snapshot`)).length;
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {mode: 'replay', through: 1}); }, processedId);
  await title(page, processedId);
  assert.equal(await page.locator('[data-au-presentation-mode]').innerText(), 'Verified replay');
  assert.equal(await page.locator('[data-au-arrival], [data-au-pause], [data-au-resume], [data-au-start]').count(), 0, 'replay must hide write controls even when that claim has a pending Start');
  await page.evaluate(() => window.__controller.refresh());
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, liveReads, 'refreshing the pending claim in replay cannot read live state');
  assert.equal((await posts()).length, 1, 'entering replay cannot submit the pending Start');
  await page.evaluate(() => { window.__fixture.providerReady = false; });
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'Cases did not restore after an uncertain Start');
  await page.locator(`[data-au-claim-row="${processedId}"] [data-au-claim="${processedId}"]`).click();
  await title(page, processedId);
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${processedId}`);
  assert.equal((await posts()).length, 1, 'returning to the original must preserve the pending request without submitting it');
  await eventually(() => page.locator('[data-au-start]').isEnabled(), 'the original pending Start retry must remain available after readiness changes');
  assert.equal(await page.locator('[data-au-start]').innerText(), 'Retry start');
  await page.locator('[data-au-start]').click();
  await eventually(async () => {
    const record = await page.locator('[data-au-disclosure="claim-record"] pre').count();
    if (!record) return false;
    return JSON.parse(await page.locator('[data-au-disclosure="claim-record"] pre').textContent()).state.revision >= 2;
  }, 'Start did not read the concurrently advanced matching snapshot');
  const [initial, retry] = await posts();
  assert.equal((await posts()).length, 2, 'each explicit Start click must make one POST');
  assert.equal(retry.body, initial.body, 'retry must preserve the exact JSON and idempotency key across navigation');
  assert.deepEqual(retry.headers, initial.headers);
  const saved = JSON.parse(await page.locator('[data-au-disclosure="claim-record"] pre').textContent());
  assert.equal(saved.state.claim_id, processedId);
  assert.equal(saved.state.revision, 2);
  assert.equal(saved.projection.state_sha256, saved.state.state_sha256);
  assert.deepEqual(saved.state.source_descriptors, original.source_descriptors, 'Start must preserve the original source identity');
  assert.equal(saved.state.title, original.title);
  assert.equal(await page.locator('[data-au-presentation-mode]').innerText(), 'Live execution');
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${processedId}`);
  assert.match(await page.locator('.au-work-head').innerText(), /revision 2\b/i);
  assert.equal(await page.locator('[data-au-start]').count(), 0);
  await page.clock.runFor(10000);
  assert.equal((await posts()).length, 2, 'neither snapshot polling nor accepted Start can submit another POST');
});

test('an original revision-zero packet exposes its source without a substantive graph or outcome', async t => {
  const page = await fixturePage(t);
  await open(page, unprocessedId);
  await title(page, unprocessedId);
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${unprocessedId}`);
  assert.equal(await page.locator('[data-au-node], [data-au-edge]').count(), 0);
  assert.equal(await page.locator('.au-outcome').count(), 0);
  assert.match(await page.locator('[data-au-view]').innerText(), /not started|not run|unprocessed/i);
  await page.locator('[data-au-source="original-1"]').click();
  await eventually(() => page.locator('dialog').getAttribute('open').then(value => value !== null), 'The original source did not open');
  assert.match(await page.locator('[data-au-source-content]').innerText(), /Original fictional packet 1: please inspect the attached notice/);
  assert.equal(await page.locator('[data-au-node], [data-au-edge]').count(), 0);
});

test('an atomic snapshot renders a matching state and cursor even while a writer advances after each read', async t => {
  const page = await fixturePage(t, {atomicWriter: true, splitWriter: true});
  const revision = await page.evaluate(id => window.__fixture.envelopes[id].state.revision, processedId);
  await open(page, processedId);
  await title(page, processedId);
  assert.match(await page.locator('.au-work-head').innerText(), new RegExp(`revision ${revision}\\b`, 'i'));
  assert.ok(await page.locator('[data-au-node]').count() > 1, 'the verified snapshot renders its saved substantive graph');
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0, 'atomic reads cannot split state and events');
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
  assert.deepEqual((await calls(page, `/claims/${processedId}/snapshot`)).map(call => new URL(call.url, 'http://fixture.invalid').searchParams.get('after')), ['0']);
  await page.evaluate(() => window.__controller.refresh());
  await eventually(async () => new RegExp(`revision ${revision + 1}\\b`, 'i').test(await page.locator('.au-work-head').innerText()), 'polling did not render the next atomic revision');
  assert.deepEqual((await calls(page, `/claims/${processedId}/snapshot`)).map(call => new URL(call.url, 'http://fixture.invalid').searchParams.get('after')), ['0', String(revision)]);
  await page.locator('[data-au-detail="documents"]').click();
  assert.equal(await page.locator('[data-au-graph]').isVisible(), false, 'Documents must hide the process graph');
  await page.locator('[data-au-detail="sources"]').click();
  assert.equal(await page.locator('[data-au-graph]').isVisible(), false, 'Original sources must hide the process graph');
  await page.locator('[data-au-detail="step"]').click();
  assert.equal(await page.locator('[data-au-graph]').isVisible(), true);
});

test('three mismatched legacy pairs stay unrendered and recover on the scheduled retry without manual Retry', async t => {
  const page = await fixturePage(t, {snapshotStatus: 404, splitWriter: true});
  await open(page, processedId);
  await eventually(async () => (await calls(page, `/claims/${processedId}/events`)).length === 3, 'opening did not make three bounded legacy read pairs');
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 3);
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0, 'an advancing legacy cursor must not render the mismatched state');
  assert.equal(await page.locator('[data-au-node]').count(), 0);
  await page.evaluate(() => { window.__fixture.splitWriter = false; });
  await page.clock.runFor(7000);
  await title(page, processedId);
  assert.ok((await calls(page, `/claims/${processedId}/events`)).length >= 4, 'the recovery must issue a timed new read pair');
  assert.ok(await page.locator('[data-au-node]').count() > 1);
});

test('three mismatched atomic snapshots also recover automatically and never fall back to split reads', async t => {
  const page = await fixturePage(t, {mismatchedSnapshots: 3});
  await open(page, processedId);
  await eventually(async () => (await calls(page, `/claims/${processedId}/snapshot`)).length === 3, 'opening did not retry the mismatched snapshot three times');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  await page.clock.runFor(7000);
  await title(page, processedId);
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
});

test('visibility resume recovers an initial opening after three mismatched snapshots without manual Retry', async t => {
  const page = await fixturePage(t, {mismatchedSnapshots: 3});
  await page.evaluate(id => { void window.__controller.openClaim(id, true, {detail: 'sources'}); }, processedId);
  await eventually(async () => (await calls(page, `/claims/${processedId}/snapshot`)).length === 3
    && /automatically/i.test(await page.locator('.au-global-status').innerText()), 'the initial three mismatches did not reach automatic recovery');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', {configurable: true, value: false});
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await page.clock.runFor(7000);
  await title(page, processedId);
  assert.equal(await page.locator('[data-au-panel="sources"]').isVisible(), true, 'visibility recovery must retain the requested claim detail');
  assert.equal(await page.locator('[data-au-graph]').isVisible(), false);
  assert.ok((await calls(page, `/claims/${processedId}/snapshot`)).length >= 4);
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
});

test('an unknown claim snapshot and legacy 404 cannot disable atomic reads for the next known claim', async t => {
  const page = await fixturePage(t), unknownId = 'clm_ffffffffffffffff';
  await open(page, unknownId);
  await eventually(() => page.locator('.au-global-status').innerText().then(value => value.includes('No GET response in this fixture.')), 'the unknown claim response was not surfaced');
  assert.equal((await calls(page, `/claims/${unknownId}/snapshot`)).length, 1);
  assert.equal((await calls(page, `/claims/${unknownId}`)).length, 1);
  assert.equal((await calls(page, `/claims/${unknownId}/events`)).length, 0, 'an unknown legacy claim cannot request events');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  await open(page, processedId);
  await title(page, processedId);
  assert.equal((await calls(page, `/claims/${processedId}/snapshot`)).length, 1, 'the known claim must still use its atomic snapshot');
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
});

test('snapshot compatibility fallback is restricted to 404, 405 and 501', async t => {
  for (const status of [404, 405, 501, 401, 403, 409, 500]) {
    await t.test(String(status), async t => {
      const page = await fixturePage(t, {snapshotStatus: status});
      await open(page, processedId);
      await eventually(async () => (await calls(page, `/claims/${processedId}/snapshot`)).length > 0, 'the snapshot endpoint was not read');
      if ([404, 405, 501].includes(status)) {
        await title(page, processedId);
        assert.equal((await calls(page, `/claims/${processedId}`)).length, 1);
        assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 1);
      } else {
        await eventually(() => page.locator('.au-global-status').innerText().then(value => value.includes('Configured snapshot transport response.')), 'the snapshot error was not surfaced');
        assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
        assert.equal((await calls(page, `/claims/${processedId}`)).length, 0, 'transport errors cannot downgrade consistency');
        assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 0);
      }
    });
  }
});

test('a snapshot capability projection with a different state hash remains unrendered', async t => {
  const page = await fixturePage(t, {corruptProjection: true});
  await open(page, processedId);
  await eventually(() => page.locator('.au-global-status').innerText().then(value => /different saved claim revision|projection/i.test(value)), 'the mismatched capability projection was not rejected');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  assert.equal(await page.locator('[data-au-node]').count(), 0);
  assert.equal((await calls(page, `/claims/${processedId}`)).length, 0);
});

test('legacy fallback also rejects a same-revision cursor with a different state hash', async t => {
  const page = await fixturePage(t, {snapshotStatus: 501, corruptLegacyHash: true});
  await open(page, processedId);
  await eventually(() => page.locator('.au-global-status').innerText().then(value => /event response differs from the saved claim identity/i.test(value)), 'the legacy hash mismatch was not rejected');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  assert.equal(await page.locator('[data-au-node]').count(), 0);
});

test('navigation abandons the scheduled recovery of an opening that never matched', async t => {
  const page = await fixturePage(t, {snapshotStatus: 404, splitWriter: true});
  await open(page, processedId);
  await eventually(async () => (await calls(page, `/claims/${processedId}/events`)).length === 3, 'the initial read pairs did not complete');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'navigation did not restore Cases');
  await page.evaluate(() => { window.__fixture.splitWriter = false; });
  await page.clock.runFor(7000);
  assert.equal((await calls(page, `/claims/${processedId}/events`)).length, 3, 'a cancelled opening must not retry after navigation');
  assert.equal(await page.locator('[data-au-claim-title]').count(), 0);
  assert.equal(await page.locator('[data-au-claim-row]').count(), 150);
  assert.equal(new URL(page.url()).hash, '#autonomous/cases');
});

test('a delayed response from an abandoned claim cannot replace the next claim or its route', async t => {
  const page = await fixturePage(t, {holdId: processedId});
  await open(page, processedId);
  await eventually(() => page.evaluate(() => window.__fixture.held.length === 1), 'the first claim snapshot was not held');
  await page.locator('.au-nav [data-au-nav="work"]').click();
  await eventually(() => page.locator('[data-au-claim-row]').count().then(count => count === 150), 'navigation did not return to Cases');
  await open(page, otherId);
  await title(page, otherId);
  const renderedIdentity = () => page.evaluate(() => ({
    title: document.querySelector('[data-au-claim-title]')?.textContent,
    header: document.querySelector('.au-work-head')?.textContent,
    nodes: [...document.querySelectorAll('[data-au-node]')].map(node => node.dataset.auNode),
    savedRecord: document.querySelector('[data-au-disclosure="claim-record"] pre')?.textContent,
  }));
  const before = await renderedIdentity();
  await page.evaluate(() => { for (const held of window.__fixture.held.splice(0)) held.release(); });
  await page.evaluate(() => new Promise(resolve => queueMicrotask(resolve)));
  await title(page, otherId);
  assert.equal(new URL(page.url()).hash, `#autonomous/claim/${otherId}`);
  assert.deepEqual(await renderedIdentity(), before, 'the abandoned response must not replace the visible saved claim');
});
