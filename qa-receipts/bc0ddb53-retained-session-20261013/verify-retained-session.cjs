'use strict';
// Temporary, fixed-commit evidence runner. No repository files or live services are modified.
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {execFileSync} = require('node:child_process');
const Module = require('node:module');
const {chromium} = require('playwright');
const repo = '/workspace/casepath-release-ae0-inventory';
const out = '/tmp/casepath-retained-session-bc0-20261013';
const commit = 'bc0ddb5340e4251360ee0f4dcb960ddb190a4114';
const origin = 'http://localhost:41999';
const api = '/api/claim-loops/v1/autonomous';
const sessionKey = 'casepath:demo-session';
const referenceId = 'clm_314f2d309fea25e6';
const legacyId = 'clm_e262801f9368bc12';
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const canonical = value => Array.isArray(value) ? '[' + value.map(canonical).join(',') + ']' : value && typeof value === 'object' ? '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}' : JSON.stringify(value);
const shaCanonical = value => hash(Buffer.from(canonical(value)));
const expectedHashes = {
  'casepath/index.html':'4f1afa9c7bba6cb7ff01a6bd8f359afe0eca45985395938bec5a1ba93d64fa2d',
  'casepath/assets/autonomous-workspace-v1.js':'2672ee416edb88ccbff7cd41619899f91b8a9c9d4a0ebdf175dfbfb6a53e36ea',
  'casepath/assets/autonomous-entry-v1.js':'297350135d60467afc7bdeff0f9389594014549d6acbe5b4b940211cd81223b8',
  'casepath/assets/autonomous-workspace-v1.css':'dce83453e21eddd70eb9471083343a86579f87a195b224a872252ab9a650740f'
};
const assets = new Map(Object.keys(expectedHashes).map(file => [file, fs.readFileSync(path.join(repo, file))]));
for (const [file, bytes] of assets) assert.equal(hash(bytes), expectedHashes[file]);
assert.equal(execFileSync('git', ['rev-parse', 'HEAD'], {cwd:repo, encoding:'utf8'}).trim(), commit);
assert.equal(execFileSync('git', ['status', '--porcelain'], {cwd:repo, encoding:'utf8'}), '');
const referenceFile = '/tmp/casepath-reference-native-85a-fixture.json';
const referenceBytes = fs.readFileSync(referenceFile);
const reference = JSON.parse(referenceBytes);
// Evaluate only the pre-test existing fixture definitions. No test(), hooks,
// broad test runner, Python fixture generation, or product module injection runs.
const qaFile = path.join(repo, 'casepath-qa/unified-product-browser-v1.test.cjs');
const qaBytes = fs.readFileSync(qaFile);
const qaSource = qaBytes.toString();
const cutoff = qaSource.indexOf('\nlet browser;');
assert.ok(cutoff > 0);
const fixtureModule = new Module(qaFile, module);
fixtureModule.filename = qaFile;
fixtureModule.paths = Module._nodeModulePaths(path.dirname(qaFile));
fixtureModule._compile(qaSource.slice(0, cutoff) + '\nmodule.exports={fixtureData};\n', qaFile);
const legacy = fixtureModule.exports.fixtureData({presentationSuite:'replay'});
const legacyPrefixes = {};
for (let through = 0; through <= 2; through++) {
  const envelope = structuredClone(legacy.acceptedHistories[legacyId][through]);
  const state = envelope.state;
  if (through === 0) Object.assign(state, {mode:'unprocessed',status:'not_started',phase:'not_run',graph:null,evaluation:null,facts:[],obligations:[],actions:[],acquired_sources:[],outcome:null,deferral:null});
  Object.assign(envelope.projection, {claim_id:legacyId,revision:through,state_sha256:state.state_sha256,parent_revision:through,parent_state_sha256:state.state_sha256});
  const head = legacy.envelopes[legacyId].state;
  const provenance = {claim_id:legacyId,prefix_revision:through,fixture:'deterministic accepted prefix',sources:structuredClone(state.source_descriptors),source_map:structuredClone(state.original_binding?.source_map || []),rule_pack_sha256:[...new Set((state.receipts || []).map(row => row.receipt?.rule_pack_sha256).filter(Boolean))].sort()};
  for (const [field, stateField] of [['source_roster_sha256','source_roster_sha256'],['policy_id','policy_id'],['run_id','run_id'],['event_sha256','last_event_sha256']]) if (state[stateField] !== undefined) provenance[field] = state[stateField];
  for (const field of ['original_binding_sha256','claim_binding_sha256','corpus_manifest_sha256','static_template_sha256']) if (state.original_binding?.[field] !== undefined) provenance[field] = state.original_binding[field];
  legacyPrefixes[through] = {...envelope,events:structuredClone(legacy.authoredEvents[legacyId].filter(event => event.seq <= through)),cursor_sha256:through ? state.last_event_sha256 : null,mode:'replay',replay_only:true,through_seq:through,current_revision:head.revision,current_state_sha256:head.state_sha256,current_event_sha256:head.last_event_sha256,current_head:{revision:head.revision,state_sha256:head.state_sha256,event_sha256:head.last_event_sha256},provenance};
}
const seeds = [
  {id:'old_valid',value:'ui-00000000-0000-4000-8000-000000000001'},
  {id:'unknown_valid',value:'ui-unknown-valid-session-20261013'}
];
const validKey = value => /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/.test(value || '');
const rows = Object.values(reference.snapshots).map(row => ({...row.state,origin:'canonical_original'}));
rows.push({...legacy.envelopes[legacyId].state,origin:'canonical_original'});
const prefix = (id, through) => id === legacyId ? legacyPrefixes[through] : reference.prefixes[id]?.[through];
const expectedRecord = (id, through) => { const row = prefix(id, through); return {state:row.state,projection:row.projection}; };
const summary = {commit,sourceHashes:expectedHashes,qaFixtureDefinitionSha256:hash(qaBytes),referenceFixture:{path:referenceFile,sha256:hash(referenceBytes),kind:'actual native synthetic reference controller GET states'},legacyFixture:{kind:'existing authored scheduler/navigation-only fixture; no legal or model outcome supplied',claim_id:legacyId,stateHashes:Object.values(legacyPrefixes).map(row => row.state.state_sha256)},seeds,clock:{kind:'Playwright virtual clock',initial:'2026-10-13T12:00:00Z',stepMs:100,maximumAdvancePerExpectedPrefixMs:12000,inspectionHoldMs:9000,note:'Virtual dwell verifies scheduler behavior, not hosted latency or wall-clock speed.'},limits:['Both capability profiles are mocks; no authenticated published account, Mac browser, public endpoint, provider, or durable journal was accessed.','Index receives only the mock capability configuration before its normal boot script; all JS/CSS loader bytes and query hashes are the exact published assets.'],runs:[],startedAt:new Date().toISOString()};
let browser, currentPage, currentRun;
fs.mkdirSync(out, {recursive:true});
const flush = () => fs.writeFileSync(path.join(out, 'matrix.json'), JSON.stringify(summary, null, 2));
async function sample(page) {
  return page.evaluate(key => {
    const surface = document.querySelector('[data-au-revision]');
    return {url:location.href,route:location.hash,revision:surface ? Number(surface.dataset.auRevision) : null,state_sha256:surface?.dataset.auStateSha,nav:document.querySelector('.au-nav [aria-current]')?.dataset.auNav,panel:document.querySelector('[data-au-context]')?.dataset.auContext,nodeIds:[...document.querySelectorAll('[data-au-node]')].map(row => row.dataset.auNode),sourceControls:[...document.querySelectorAll('[data-au-source]')].map(row => ({artifact_id:row.dataset.auSource,identity:row.dataset.auSourceIdentity,citation:row.dataset.auCitation})),playing:!!document.querySelector('[data-au-demo-stop]'),play:!!document.querySelector('[data-au-demo-play]'),resume:!!document.querySelector('[data-au-demo-resume]'),sessionBeforeBoot:window.__matrixKeyBeforeBoot,sessionAfterBoot:sessionStorage.getItem(key),virtualTime:Date.now(),workspaceMode:document.documentElement.dataset.autonomousWorkspace,publicReadOnly:window.CASEPATH_PUBLIC_READ_ONLY === true,secureContext:isSecureContext,subtleAvailable:!!globalThis.crypto?.subtle,scriptURLs:[...document.scripts].filter(row => row.src).map(row => row.src),cssURLs:[...document.querySelectorAll('link[rel=stylesheet]')].map(row => row.href),message:document.querySelector('.au-global-status')?.textContent};
  }, sessionKey);
}
async function recordState(page, id, through) {
  const panel = await page.locator('[data-au-panel]').getAttribute('data-au-panel');
  const playing = await page.locator('[data-au-demo-stop]').count() === 1;
  if (panel !== 'activity') await page.locator('.au-work-head [data-au-detail=activity]').click();
  await page.locator('[data-au-panel=activity] [data-au-inspect=claim]').click();
  const record = JSON.parse(await page.locator('.au-record-dialog[open] pre[data-au-record-kind=claim]').textContent());
  assert.deepEqual(record, expectedRecord(id, through), 'technical drawer must expose the complete exact accepted state and projection');
  await page.locator('[data-au-close-record]').click();
  if (panel !== 'activity') await page.locator(`.au-context-nav [data-au-detail=${panel}]`).click();
  if (playing) await page.locator('[data-au-demo-resume]').click();
  return {completeStateAndProjectionEqual:true,recordSha256:shaCanonical(record),state_sha256:record.state.state_sha256,revision:record.state.revision,projectionSha256:shaCanonical(record.projection),original_binding_sha256:record.state.original_binding?.original_binding_sha256};
}
async function check(page, run, stage, id, through, fullState = false) {
  const actual = await sample(page), wanted = prefix(id, through);
  assert.equal(actual.revision, through, stage);
  assert.equal(actual.state_sha256, wanted.state.state_sha256, stage);
  assert.equal(actual.nav, 'demonstration', stage);
  assert.ok(actual.route.startsWith(`#autonomous/claim/${id}?`), stage);
  if (actual.panel === 'step') assert.deepEqual(actual.nodeIds.slice().sort(), (wanted.state.graph?.nodes || []).map(row => row.node_id).sort(), stage);
  const row = {stage,...actual,expectedClaim:id,expectedRevision:through,expectedStateSha256:wanted.state.state_sha256};
  if (fullState) row.technicalRecord = await recordState(page, id, through);
  run.stages.push(row);
  return row;
}
async function advance(page, run, stage, id, from, to) {
  const start = (await sample(page)).virtualTime;
  for (let tick = 0; tick < 120 && (await sample(page)).revision < to; tick++) await page.clock.runFor(100);
  const actual = await check(page, run, stage, id, to);
  actual.advance = {from,to,virtualElapsedMs:actual.virtualTime - start};
  return actual;
}
async function hold(page, run, stage, id, through, panel) {
  const before = await sample(page);
  assert.equal(before.playing, false, 'direct inspection must not autoplay');
  await page.clock.runFor(9000);
  const after = await check(page, run, stage, id, through, true);
  if (panel) assert.equal(after.panel, panel);
  assert.equal(after.playing, false);
  assert.equal(after.play, true);
  return after;
}
async function inspectSource(page, run, stage, through) {
  if (await page.locator('[data-au-panel]').getAttribute('data-au-panel') !== 'sources') await page.locator('.au-context-nav [data-au-detail=sources]').click();
  const descriptor = reference.prefixes[referenceId][through].state.source_descriptors[0];
  const source = reference.sources[`${referenceId}/${descriptor.artifact_id}`];
  await page.locator(`[data-au-panel=sources] [data-au-source="${descriptor.artifact_id}"]`).first().click();
  await page.locator('.au-source-dialog[open] .au-source-body').waitFor();
  const actualText = await page.locator('.au-source-dialog .au-source-body').textContent();
  assert.equal(actualText, source.text);
  assert.equal(hash(Buffer.from(actualText)), source.text_sha256);
  const identity = await page.locator('.au-source-dialog .au-source-identity').textContent();
  assert.ok(identity.includes(descriptor.sha256));
  assert.ok(identity.includes(source.text_sha256));
  const row = {stage,through,descriptor,originalBytesSha256:descriptor.sha256,textSha256:hash(Buffer.from(actualText)),textLength:actualText.length,exactBodyEqual:true};
  run.sources.push(row);
  await page.locator('[data-au-close]').click();
  return row;
}
async function createCase(seed, publicReadOnly, journey) {
  const context = await browser.newContext({serviceWorkers:'block'}), page = await context.newPage();
  currentPage = page;
  page.setDefaultTimeout(7000);
  const run = currentRun = {id:`${publicReadOnly ? 'public_mock' : 'owner_mock'}-${seed.id}-${journey}`,profile:publicReadOnly ? 'public read-only capability MOCK' : 'owner-capability MOCK',seed,journey,status:'running',stages:[],sources:[],requests:[],errors:[],consoleErrors:[],servedAssets:{},startedAt:new Date().toISOString()};
  summary.runs.push(run);flush();
  page.on('pageerror', error => run.errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') run.consoleErrors.push(message.text()); });
  await page.addInitScript(({seed,key}) => {
    if (sessionStorage.getItem('casepath-matrix-seeded') !== '1') {
      if (seed.value === null) sessionStorage.removeItem(key); else sessionStorage.setItem(key, seed.value);
      sessionStorage.setItem('casepath-matrix-seeded', '1');
    }
    window.__matrixKeyBeforeBoot = sessionStorage.getItem(key);
  }, {seed,key:sessionKey});
  const clockTime = new Date('2026-10-13T12:00:00Z');
  await page.clock.install({time:clockTime});await page.clock.pauseAt(clockTime);
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url()), name = decodeURIComponent(url.pathname);
    const trace = {path:name + url.search,method:request.method(),status:null,wallTime:new Date().toISOString(),sessionHeader:request.headers()['x-casepath-session'] || null};run.requests.push(trace);
    assert.equal(url.origin, origin, 'no request may leave the local interception fixture');assert.equal(request.method(), 'GET');
    if (name.startsWith(api)) {
      const suffix = name.slice(api.length), claim = suffix.match(/^\/claims\/([^/]+)(?:\/(snapshot|replay|events))?$/), source = suffix.match(/^\/sources\/([^/]+)\/([^/]+)(?:\/(text|preview))?$/);
      let data, raw;
      if (suffix === '/claims') data = {claims:rows,total:rows.length};
      else if (suffix === '/knowledge') data = reference.knowledge;
      else if (suffix === '/status') data = {enabled:true,provider_ready:false,writable:!publicReadOnly,read_only:publicReadOnly,limits:{}};
      else if (claim) {
        const id = claim[1];
        if (claim[2] === 'replay') data = prefix(id, Number(url.searchParams.get('through_seq') || 0));
        else if (id === legacyId) { const head = legacyPrefixes[2];data = claim[2] === 'events' ? {...head,events:head.events.filter(row => row.seq > Number(url.searchParams.get('after') || 0))} : head; }
        else { const snapshot = reference.snapshots[id];data = snapshot && claim[2] === 'events' ? {...snapshot,events:snapshot.events.filter(row => row.seq > Number(url.searchParams.get('after') || 0))} : snapshot; }
      } else if (source) {
        const identity = `${source[1]}/${source[2]}`;
        if (source[3]) data = reference.sources[identity] || legacy.sources[identity];
        else if (reference.raw_sources[identity]) raw = Buffer.from(reference.raw_sources[identity], 'base64');
      }
      trace.status = data || raw ? 200 : 404;
      if (data?.state) { trace.fixtureRevision = data.state.revision;trace.fixtureStateSha256 = data.state.state_sha256; }
      if (raw) return route.fulfill({status:trace.status,contentType:'application/octet-stream',body:raw});
      return route.fulfill({status:trace.status,contentType:'application/json',body:JSON.stringify(data || {detail:'No synthetic GET response.'})});
    }
    const file = 'casepath/' + (name === '/' ? 'index.html' : name.slice(1));
    let body = assets.get(file);
    if (!body && !file.includes('..') && fs.existsSync(path.join(repo, file))) body = fs.readFileSync(path.join(repo, file));
    if (!body) { trace.status=404;return route.fulfill({status:404,body:'Unavailable synthetic static path'}); }
    const sourceHash = hash(body);
    if (file === 'casepath/index.html') body = Buffer.from(body.toString().replace('<head>', `<head><script>window.CASEPATH_PUBLIC_READ_ONLY=${publicReadOnly};window.CASEPATH_HOSTED_AUTONOMOUS=true;</script>`));
    trace.status=200;trace.sourceAssetSha256=sourceHash;trace.servedBodySha256=hash(body);
    run.servedAssets[file] = {sourceSha256:sourceHash,servedSha256:hash(body)};
    return route.fulfill({status:200,contentType:{'.html':'text/html','.js':'application/javascript','.css':'text/css','.ttf':'font/ttf','.json':'application/json'}[path.extname(file)] || 'application/octet-stream',body});
  });
  try {
    const initialFragment = journey === 'default' ? '#autonomous/demonstration?mode=replay' : journey === 'legacy' ? `#autonomous/claim/${legacyId}?mode=replay&through=0` : `#autonomous/claim/${referenceId}?collection=reference&mode=replay&through=18&detail=sources`;
    await page.goto(origin + '/' + initialFragment);await page.locator('[data-au-revision]').waitFor();
    const initial = await sample(page);
    assert.equal(initial.secureContext,true);assert.equal(initial.subtleAvailable,true);
    assert.equal(initial.sessionBeforeBoot, seed.value);
    assert.equal(validKey(initial.sessionAfterBoot), true);
    if (validKey(seed.value)) assert.equal(initial.sessionAfterBoot, seed.value); else assert.notEqual(initial.sessionAfterBoot, seed.value);
    run.session = {key:sessionKey,before:initial.sessionBeforeBoot,after:initial.sessionAfterBoot,retainedInitially:initial.sessionAfterBoot === seed.value};
    assert.equal(initial.publicReadOnly, publicReadOnly);
    assert.equal(initial.workspaceMode, 'true');
    for (const [file, expected] of Object.entries(expectedHashes)) assert.equal(run.servedAssets[file]?.sourceSha256, expected, 'actual loader must serve exact published source bytes');
    for (const file of ['casepath/assets/autonomous-workspace-v1.js','casepath/assets/autonomous-entry-v1.js','casepath/assets/autonomous-workspace-v1.css']) assert.ok((file.endsWith('.css') ? initial.cssURLs : initial.scriptURLs).some(url => url.includes(file.slice('casepath/'.length) + '?sha256=' + expectedHashes[file])), 'actual DOM asset query SHA must match served published bytes');
    if (journey === 'default') {
      await check(page, run, 'requested-demonstration-opening', referenceId, 0);assert.equal(initial.playing, true);
      await advance(page, run, 'autoplay-real-prefix-1', referenceId, 0, 1);
      await advance(page, run, 'autoplay-real-prefix-2', referenceId, 1, 2);
      await page.locator('[data-au-demo-stop]').click();
      await check(page, run, 'paused-before-reload', referenceId, 2, true);
      await page.reload();await page.locator('[data-au-revision]').waitFor();
      const reload = await hold(page, run, 'canonical-reload-keeps-exact-prefix-2', referenceId, 2);
      assert.equal(reload.sessionBeforeBoot, run.session.after);assert.equal(reload.sessionAfterBoot, run.session.after);
      await page.locator('[data-au-demo-play]').click();
      await advance(page, run, 'reload-deliberate-Play-exact-prefix-3', referenceId, 2, 3);
      await page.locator('[data-au-demo-stop]').click();await check(page, run, 'prefix-3-complete-state', referenceId, 3, true);
      await page.locator('.au-nav [data-au-nav=demonstration]').click();
      await page.locator('[data-au-revision="0"]').waitFor();
      const reopened = await check(page, run, 'manual-Demonstration-native-nav-fresh-prefix-0', referenceId, 0);assert.equal(reopened.playing, true);
      await advance(page, run, 'manual-Demonstration-autoplay-exact-prefix-1', referenceId, 0, 1);
      await page.locator('[data-au-demo-stop]').click();
    } else if (journey === 'legacy') {
      await hold(page, run, 'legacy-absent-collection-prefix-0-inspection', legacyId, 0);
      await page.locator('[data-au-demo-play]').click();
      const advanced = await advance(page, run, 'legacy-deliberate-Play-exact-prefix-1', legacyId, 0, 1);
      assert.equal(new URLSearchParams(advanced.route.split('?')[1]).get('collection'), 'legacy');
      await page.locator('[data-au-demo-stop]').click();await check(page, run, 'legacy-prefix-1-complete-state', legacyId, 1, true);
    } else {
      await hold(page, run, 'explicit-reference-prefix-18-Sources-inspection', referenceId, 18, 'sources');
      const before = await inspectSource(page, run, 'prefix-18-original-source', 18);
      await check(page, run, 'source-close-retains-prefix-18-context', referenceId, 18);
      await page.locator('[data-au-demo-play]').click();
      await advance(page, run, 'explicit-Play-exact-native-prefix-19', referenceId, 18, 19);
      await page.locator('[data-au-demo-stop]').click();await check(page, run, 'prefix-19-complete-state', referenceId, 19, true);
      const after = await inspectSource(page, run, 'prefix-19-same-original-source', 19);
      assert.deepEqual(after.descriptor, before.descriptor);assert.equal(after.textSha256, before.textSha256);
      await check(page, run, 'source-inspection-retains-prefix-19', referenceId, 19);
    }
    const final = await sample(page);assert.equal(final.sessionAfterBoot, run.session.after);run.session.final = final.sessionAfterBoot;
    assert.deepEqual(run.errors, []);assert.deepEqual(run.consoleErrors, []);
    assert.equal(run.requests.some(row => row.method !== 'GET' || row.path === '/api/demo' || row.sessionHeader !== null), false);
    assert.equal(run.requests.some(row => row.status !== 200), false);
    run.status='passed';run.finishedAt=new Date().toISOString();run.wallElapsedMs=Date.parse(run.finishedAt)-Date.parse(run.startedAt);
    fs.writeFileSync(path.join(out, run.id + '.json'), JSON.stringify(run, null, 2));flush();
    console.log(JSON.stringify({id:run.id,status:run.status,session:run.session,stages:run.stages.map(row=>({stage:row.stage,revision:row.revision,state_sha256:row.state_sha256})),requests:run.requests.length,wallElapsedMs:run.wallElapsedMs}));
  } catch (error) {
    run.status='failed';run.failure={message:error.message,stack:error.stack};run.currentDOM=await sample(page).catch(problem=>({captureError:problem.message}));run.bodyText=await page.locator('body').innerText().catch(()=>null);
    fs.writeFileSync(path.join(out, run.id + '-failure.json'), JSON.stringify(run, null, 2));flush();throw error;
  } finally { await context.close();currentPage=null; }
}
async function main() {
  browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  console.log(JSON.stringify({status:'BROWSER_STARTED',commit,scope:'latest parent narrowing: retained owner old token and public unknown token; default and legacy, plus one public Sources control'}));
  try {
    if (process.env.CASEPATH_RETAINED_SOURCES_ONLY === '1') {
      const completed = JSON.parse(fs.readFileSync(path.join(out,'mandatory-four-plus-sources-harness/matrix.json')));
      assert.equal(completed.commit,commit);
      summary.runs = completed.runs.filter(row=>row.status==='passed');assert.equal(summary.runs.length,4);
      summary.priorCompletedMandatoryCases = 4;
      summary.priorAttempt = 'mandatory-four-plus-sources-harness';
    } else {
      for (const [publicReadOnly,seed] of [[false,seeds[0]],[true,seeds[1]]]) for (const journey of ['default','legacy']) await createCase(seed, publicReadOnly, journey);
    }
    await createCase(seeds[1],true,'sources');
    summary.status='passed';summary.finishedAt=new Date().toISOString();summary.wallElapsedMs=Date.parse(summary.finishedAt)-Date.parse(summary.startedAt);summary.passed=summary.runs.length;summary.failed=0;
    assert.equal(summary.passed,5);
    assert.equal(execFileSync('git', ['status','--porcelain'], {cwd:repo,encoding:'utf8'}), '');
    for (const [file, expected] of Object.entries(expectedHashes)) assert.equal(hash(fs.readFileSync(path.join(repo,file))),expected);
    summary.repositoryUnchanged=true;flush();console.log(JSON.stringify({status:summary.status,passed:summary.passed,failed:summary.failed,wallElapsedMs:summary.wallElapsedMs,artifact:path.join(out,'matrix.json')}));
  } catch (error) {
    summary.status='failed';summary.failed=1;summary.failure={message:error.message,stack:error.stack};summary.finishedAt=new Date().toISOString();flush();throw error;
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
