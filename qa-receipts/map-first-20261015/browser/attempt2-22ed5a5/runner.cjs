'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{createHash}=require('node:crypto'),{execFileSync}=require('node:child_process'),{chromium}=require('playwright');
const root='/workspace/casepath-map-first-qa-20261015';
const referenceIds=['clm_314f2d309fea25e6'];
const focusedReceiptRoot=process.env.CASEPATH_FOCUSED_RECEIPTS;
const sha=value=>createHash('sha256').update(value).digest('hex'),sorted=values=>[...values].sort();
const canonical=value=>Array.isArray(value)?'['+value.map(canonical).join(',')+']':value&&typeof value==='object'?'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}':JSON.stringify(value);
let browser;
test.before(async()=>{browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});});
test.after(async()=>{await browser?.close();});
// Reuse the existing GET-only native fixture server and operation sidecars.
// These opt-in checks use real Chromium time; ordinary in-memory browser tests
// retain their existing fixture and clock. No provider or write is permitted.
const mapFirstNativeURL = process.env.CASEPATH_MAP_FIRST_NATIVE_URL;
let mapFirstNativeData;
function mapFirstNativeFixture(id = referenceIds[0]) {
  assert.ok(process.env.CASEPATH_OPERATION_NATIVE_FIXTURE, 'supply the existing native fixture');
  assert.ok(process.env.CASEPATH_OPERATION_NATIVE_SIDECARS, 'supply its existing operation sidecars');
  mapFirstNativeData ||= JSON.parse(fs.readFileSync(process.env.CASEPATH_OPERATION_NATIVE_FIXTURE, 'utf8'));
  const bytes = fs.readFileSync(path.join(process.env.CASEPATH_OPERATION_NATIVE_SIDECARS, `${id}.json`));
  const sidecar = JSON.parse(bytes), operations = sidecar.frames.filter(row => row.type === 'operation');
  return {id, native: mapFirstNativeData, head: mapFirstNativeData.snapshots[id], sidecar,
    sidecar_sha256: sha(bytes), operations: new Map(operations.map(row => [row.id, row])),
    sources: new Map(operations.filter(row => row.kind === 'source.open').map(row => [row.object.id, row.result]))};
}

async function mapFirstNativePage(t, {width = 1280, height = 800, reduced = false} = {}) {
  const target = new URL(mapFirstNativeURL);
  if (focusedReceiptRoot) fs.mkdirSync(focusedReceiptRoot, {recursive: true});
  assert.ok(['127.0.0.1', 'localhost'].includes(target.hostname), 'native QA stays on loopback');
  const context = await browser.newContext({viewport: {width, height}, reducedMotion: reduced ? 'reduce' : 'no-preference', serviceWorkers: 'block'});
  const page = await context.newPage(), errors = [], requests = [], served = {}, reads = [];
  page.setDefaultTimeout(10000);
  const javascript = fs.readFileSync(process.env.CASEPATH_BROWSER_JS_ASSET || path.join(root, 'casepath/assets/autonomous-workspace-v1.js'));
  const css = fs.readFileSync(process.env.CASEPATH_BROWSER_CSS_ASSET || path.join(root, 'casepath/assets/autonomous-workspace-v1.css'));
  page.__mapFirst = {errors, requests, served, assets: {javascript: sha(javascript), css: sha(css)}};
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    const match = /\/assets\/autonomous-workspace-v1\.(js|css)(?:\?|$)/.exec(response.url());
    if (match) reads.push(response.body().then(bytes => { served[match[1] === 'js' ? 'javascript' : 'css'] = sha(bytes); }));
  });
  await page.route('**/*', route => {
    const request = route.request();
    requests.push({method: request.method(), url: request.url()});
    assert.ok(['GET', 'HEAD'].includes(request.method()), 'native browser checks cannot write');
    assert.equal(new URL(request.url()).origin, target.origin, 'native browser checks cannot reach a provider or production');
    const match = /\/assets\/autonomous-workspace-v1\.(js|css)(?:\?|$)/.exec(request.url());
    return match ? route.fulfill({status: 200, contentType: match[1] === 'js' ? 'application/javascript' : 'text/css', body: match[1] === 'js' ? javascript : css}) : route.continue();
  });
  await page.addInitScript(() => {
    window.CASEPATH_PUBLIC_READ_ONLY = true;
    const receipt = window.__mapFirstTrace = {bound: null, available: null, operations: [], docks: [], animations: [], frames: [], longtasks: [], result: null};
    let prior;
    requestAnimationFrame(function tick(now) { if (prior) receipt.frames.push({at: now, dt: now - prior}); prior = now; requestAnimationFrame(tick); });
    new PerformanceObserver(list => receipt.longtasks.push(...list.getEntries().map(row => ({at: row.startTime, ms: row.duration})))).observe({entryTypes: ['longtask']});
    const animate = Element.prototype.animate;
    Element.prototype.animate = function (keyframes, options) {
      const animation = animate.call(this, keyframes, options);
      if (this.matches('.au-operation-attention,.au-operation-fact-token,[data-au-read-trail]')) {
        const row = {at: performance.now(), class: this.className, operation: this.dataset.auOperationId || this.dataset.auOperationAttention || this.dataset.auReadTrail,
          text: this.textContent, quote: this.querySelector('span')?.textContent || this.textContent, source: this.dataset.auSourceArtifact, start: Number(this.dataset.auSourceStartChar), end: Number(this.dataset.auSourceEndChar),
          citation_start: Number(this.dataset.auCitationStartChar), citation_end: Number(this.dataset.auCitationEndChar), duration: typeof options === 'number' ? options : options?.duration,
          keyframes, locked: document.querySelector('mark[data-au-phrase-locked]')?.dataset.auPhraseLocked};
        const target = this.classList.contains('au-operation-fact-token') ? [...document.querySelectorAll('[data-au-stage-fact],[data-au-check-operation]')].find(element => element.dataset.auFactOperation === row.operation || element.dataset.auCheckOperation === row.operation) : null;
        const visibleTarget = () => { if (!target?.isConnected) return null; const r=target.getBoundingClientRect(),css=getComputedStyle(target),clip=target.closest('[data-au-graph-pan]')?.getBoundingClientRect();return {at:performance.now(),opacity:css.opacity,visibility:css.visibility,rect:r.toJSON(),clip:clip?.toJSON(),visible:r.width>0&&r.height>0&&css.opacity!=='0'&&css.visibility==='visible'&&r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1&&(!clip||r.left>=clip.left-1&&r.right<=clip.right+1&&r.top>=clip.top-1&&r.bottom<=clip.bottom+1)}; };
        row.target_before=visibleTarget(); receipt.animations.push(row);
        if(target) setTimeout(()=>{row.target_mid=visibleTarget();},Math.min(300,(row.duration||600)/2));
        animation.finished.then(() => { row.finished = performance.now(); requestAnimationFrame(()=>{row.landing=visibleTarget();}); }, () => { row.cancelled = performance.now(); });
      }
      return animation;
    };
    new MutationObserver(() => {
      const host = document.querySelector('[data-au-view]');
      if (!host) return;
      const at = performance.now(), mode = host.dataset.auOperationRunMode, operation = host.dataset.auCurrentOperation;
      if (receipt.bound === null && ['live', 'recorded', 'recorded_operations', 'historical_recomputed'].includes(mode)) receipt.bound = at;
      if (receipt.available === null && host.dataset.auOperationResultAvailable === 'true') receipt.available = at;
      if (operation && receipt.operations.at(-1)?.id !== operation) receipt.operations.push({id: operation, at});
      for (const element of host.querySelectorAll('[data-au-stage-fact],[data-au-check-operation]')) {
        const operation = element.dataset.auFactOperation || element.dataset.auCheckOperation;
        if (!operation || element.hasAttribute('data-au-fact-docking') || getComputedStyle(element).opacity === '0' || getComputedStyle(element).visibility !== 'visible' || receipt.docks.some(row => row.operation === operation)) continue;
        receipt.docks.push({at, operation, kind: element.hasAttribute('data-au-stage-fact') ? 'fact' : 'document', id: element.dataset.auStageFact || element.closest('[data-au-stage-document]')?.dataset.auStageDocument,
          node: element.closest('[data-au-stage-step]')?.dataset.auStageStep, text: element.textContent});
      }
      if (!receipt.result && host.dataset.auOperationResultVerified === 'true') {
        receipt.result = {at, revision: Number(host.querySelector('[data-au-revision]')?.dataset.auRevision), state_sha256: host.querySelector('[data-au-state-sha]')?.dataset.auStateSha};
        // End unattended traversal only after the genuine verified result.
        host.querySelector('[data-au-demo-stop]')?.click();
      }
    }).observe(document, {subtree: true, childList: true, attributes: true, attributeFilter: ['data-au-current-operation', 'data-au-operation-run-mode', 'data-au-operation-result-available', 'data-au-operation-result-verified', 'data-au-fact-docking', 'style']});
  });
  t.after(async () => {
    await Promise.all(reads);
    await context.close();
    assert.deepEqual(served, page.__mapFirst.assets, 'native fixture served the selected immutable asset bytes');
    assert.deepEqual(errors, [], 'native product browser errors');
  });
  await page.goto(`${target.origin}/?journey=autonomous#autonomous/demonstration${process.env.CASEPATH_MAP_FIRST_RECORDED === '1' ? '?operations=recorded' : ''}`);
  await page.waitForFunction(() => window.__mapFirstTrace?.bound !== null, null, {timeout: 60000});
  return page;
}

async function mapFirstNativeSnapshot(page) {
  return page.evaluate(() => {
    const host = document.querySelector('[data-au-view]'), stage = host.querySelector('.au-operation-stage'), rail = stage?.querySelector('.au-stage-process'), pane = stage?.querySelector('.au-operation-passage'), transport = host.querySelector('.au-stage-transport');
    const rect = element => element?.getBoundingClientRect().toJSON();
    const graph = rail?.querySelector('[data-au-graph-pan]'), title = element => element.querySelector('.au-node-title');
    return {at: performance.now(), bound: window.__mapFirstTrace.bound, operation: host.dataset.auCurrentOperation, verified: host.dataset.auOperationResultVerified,
      revision: Number(host.querySelector('[data-au-revision]')?.dataset.auRevision), state_sha256: host.querySelector('[data-au-state-sha]')?.dataset.auStateSha,
      stage: rect(stage), rail: rect(rail), planned: rail?.dataset.auPlannedProcess, planned_authority: rail?.dataset.auPlannedAuthority,
      graph: graph && {rect: rect(graph), clientWidth: graph.clientWidth, scrollWidth: graph.scrollWidth, scrollLeft: graph.scrollLeft, scrollTop: graph.scrollTop},
      nodes: [...(rail?.querySelectorAll('[data-au-node]') || [])].map(element => ({id: element.dataset.auNode, status: element.dataset.status, rect: rect(element), font: parseFloat(getComputedStyle(title(element)).fontSize)})),
      edges: [...(rail?.querySelectorAll('[data-au-edge]') || [])].map(element => ({id: element.dataset.auEdge, source: element.dataset.auEdgeSource, target: element.dataset.auEdgeTarget})),
      marks: [...(stage?.querySelectorAll('[data-au-operation-span]') || [])].map(element => ({operation: element.dataset.auOperationSpan, source: pane?.dataset.auOperationSource, start: Number(element.dataset.auOperationStartChar), end: Number(element.dataset.auOperationEndChar), quote: element.textContent, font: parseFloat(getComputedStyle(element).fontSize)})),
      pane: pane && {rect: rect(pane), scrollTop: pane.scrollTop, scrollHeight: pane.scrollHeight, clientHeight: pane.clientHeight, text: pane.textContent},
      facts: [...(rail?.querySelectorAll('[data-au-stage-fact]') || [])].map(element => ({id: element.dataset.auStageFact, operation: element.dataset.auFactOperation, start: Number(element.dataset.auFactStartChar), end: Number(element.dataset.auFactEndChar), text: element.textContent, state: element.dataset.auFactState})),
      documents: [...(rail?.querySelectorAll('[data-au-stage-document]') || [])].map(element => ({id: element.dataset.auStageDocument, checked: element.dataset.auDocumentChecked, check: element.querySelector('[data-au-check-operation]')?.dataset.auCheckOperation, citation: element.querySelector('[data-au-citation]')?.dataset.auCitation})),
      transport: transport && {rect: rect(transport), controls: [...transport.querySelectorAll('button,input,select')].map(element => ({text: element.textContent, rect: rect(element)}))},
      outcome: stage?.querySelector('[data-au-stage-outcome] > p')?.textContent,
      articles: [...(stage?.querySelectorAll('[data-au-law-article]') || [])].map(element => element.dataset.auLawArticle),
      reuse: [...(stage?.querySelectorAll('.au-stage-reuse [data-au-knowledge]') || [])].map(element => ({id: element.dataset.auKnowledge, version: element.dataset.auVersion})),
      overflow: document.documentElement.scrollWidth > innerWidth + 1, viewport: {width: innerWidth, height: innerHeight}};
  });
}

function assertMapFirstNativeSnapshot(sample, fixture) {
  assert.ok(sample.rail?.width > 0 && sample.rail.height > 0 && sample.nodes.length > 0, 'every sampled frame retains a real process map');
  assert.ok(sample.nodes.every(row => row.font >= 16), 'actual process labels remain at least 16px');
  assert.equal(sample.overflow, false, 'the page does not overflow horizontally');
  const accepted = fixture.native.prefixes[fixture.id]?.[sample.revision]?.state;
  assert.ok(accepted, 'the shown revision is an actual native prefix');
  assert.equal(sample.state_sha256, accepted.state_sha256, 'every displayed accepted prefix retains its original state hash');
  if (sample.planned) {
    assert.equal(sample.planned, fixture.head.state.state_sha256);
    assert.equal(sample.planned_authority, 'none');
    assert.ok(sample.nodes.every(row => row.status === 'planned'), 'the verified outline does not claim accepted completion');
    assert.equal(sample.documents.filter(row => row.checked === 'true').length, 0, 'the planned outline has no invented checked document');
  }
  if (sample.nodes.length > 1) assert.ok(Math.max(...sample.nodes.map(row => row.rect.left)) > Math.min(...sample.nodes.map(row => row.rect.left)) + 20, 'the process remains horizontal, including mobile');
  if (sample.pane) {
    assert.equal(sample.pane.scrollTop, 0, 'the compact excerpt does not scroll a whole document');
    assert.ok(sample.pane.scrollHeight <= sample.pane.clientHeight + 1, 'the excerpt fits its source pocket');
  }
  for (const mark of sample.marks) {
    const operation = fixture.operations.get(mark.operation), source = fixture.sources.get(mark.source);
    assert.ok(operation?.source && source, 'the excerpt refers to an actual checked operation and opened source');
    assert.ok(mark.start >= operation.source.start_char && mark.end <= operation.source.end_char);
    assert.equal(Array.from(source.text).slice(mark.start, mark.end).join(''), mark.quote, 'excerpt is an exact Unicode subspan');
    assert.ok(mark.font >= 18, 'actual evidence text remains at least 18px');
  }
  for (const fact of sample.facts) {
    const operation = fixture.operations.get(fact.operation), source = fixture.sources.get(operation?.source?.artifact_id);
    assert.equal(operation?.kind, 'fact.extract');
    assert.equal(fact.id, operation.object.id);
    assert.equal(Array.from(source.text).slice(fact.start, fact.end).join(''), fact.text, 'docked fact remains literal original evidence');
  }
  for (const document of sample.documents.filter(row => row.checked === 'true')) {
    const operation = fixture.operations.get(document.check);
    assert.equal(operation?.kind, 'document.check');
    assert.equal(operation.result.assessment, 'sufficient');
    assert.equal(operation.object.id, document.id);
    assert.deepEqual(JSON.parse(document.citation), operation.source, 'filled document retains the complete actual checked pin');
  }
  assert.ok(sample.transport && sample.transport.controls.length > 0 && sample.transport.controls.length <= 3);
}

async function mapFirstNativeReceipt(page, name, measurements) {
  if (!focusedReceiptRoot) return;
  fs.mkdirSync(focusedReceiptRoot, {recursive: true});
  fs.writeFileSync(path.join(focusedReceiptRoot, `${name}.json`), JSON.stringify({...measurements,
    disclosure: 'Existing local native fictional fixture and operation sidecars; actual Chromium time; no provider, production request or write.',
    checkout_commit: execFileSync('git', ['rev-parse', 'HEAD'], {cwd: root, encoding: 'utf8'}).trim(),
    candidate_commit: process.env.CASEPATH_CANDIDATE_COMMIT || null, test_sha256: sha(fs.readFileSync(__filename)),
    ...page.__mapFirst}, null, 2));
}

test('map first native: distinct real consequences dock promptly and the horizontal map persists in every two second frame', async t => {
  const fixture = mapFirstNativeFixture(), page = await mapFirstNativePage(t), frames = [], frameFailures = [];
  try {
    const bound = await page.evaluate(() => window.__mapFirstTrace.bound);
    for (let index = 0; index <= 20; index++) {
      const remaining = bound + index * 2000 - await page.evaluate(() => performance.now());
      if (remaining > 0) await page.waitForTimeout(remaining);
      const sample = await mapFirstNativeSnapshot(page); frames.push(sample);
      if (focusedReceiptRoot) await page.screenshot({path: path.join(focusedReceiptRoot, `map-first-frame-${String(index).padStart(2, '0')}.png`)});
      try { assertMapFirstNativeSnapshot(sample, fixture); if (sample.verified !== 'true') assert.ok(sample.transport.controls.every(control=>control.rect.top>=0&&control.rect.bottom<=800+1), 'all running desktop controls remain inside the viewport'); } catch (error) { frameFailures.push({index,operation:sample.operation,message:error.message}); }
    }
    const trace = await page.evaluate(() => window.__mapFirstTrace), distinct = new Map();
    for (const dock of trace.docks) {
      const operation = fixture.operations.get(dock.operation);
      if (!operation?.source || !['fact.extract', 'document.check'].includes(operation.kind)) continue;
      const flight = trace.animations.find(row => row.operation === dock.operation && row.class.includes('fact-token') && row.finished && !row.cancelled);
      if (!flight) continue; // A rendered row alone is not a completed handoff.
      assert.equal(flight.target_before?.visible, false, 'the final landing is not visibly filled during flight');
      assert.equal(flight.target_mid?.visible, false, 'the final landing remains hidden until its actual flight completes');
      if (!flight.landing?.visible) continue; // Only a finished visible landing counts.
      assert.ok(dock.at >= flight.at, 'the final landing is not visibly filled during its highlight wash');
      assert.equal(flight.locked, operation.id, 'the genuine chip follows its own completed highlight');
      assert.ok(flight.duration > 0 && flight.duration <= 700, 'genuine chip flight is bounded around 0.6 seconds');
      assert.equal(Array.from(fixture.sources.get(flight.source).text).slice(flight.start, flight.end).join(''), flight.quote);
      const key = canonical([operation.kind, operation.object.id, operation.source]);
      if (!distinct.has(key)) distinct.set(key, {...dock, completed: Math.max(dock.at, flight.finished), key});
    }
    const firstForty = [...distinct.values()].filter(row => row.completed - bound <= 40000).sort((a, b) => a.completed - b.completed);
    assert.ok(firstForty.length >= 8, `at least eight distinct completed fact/document handoffs in the first40s; got ${firstForty.length}`);
    assert.ok(firstForty[0].completed - bound <= 3000, `first genuine completed dock <=3s after available binding; got ${firstForty[0].completed - bound}ms`);
    const gaps = firstForty.slice(1).map((row, index) => row.completed - firstForty[index].completed);
    assert.ok(gaps.reduce((sum, gap) => sum + gap, 0) / gaps.length <= 4000, 'average interval between distinct genuine handoffs is at most4s');
    assert.ok(trace.animations.filter(row => row.class.includes('attention')).every(row => row.duration <= 1100), 'highlight sweeps are bounded around one second');
    if (await page.locator('[data-au-operation-skip]').count()) await page.locator('[data-au-operation-skip]').click();
    await page.waitForFunction(() => document.querySelector('[data-au-view]')?.dataset.auOperationResultVerified === 'true', null, {timeout: 15000});
    const result = await mapFirstNativeSnapshot(page);
    assert.equal(result.state_sha256, fixture.head.state.state_sha256);
    await mapFirstNativeReceipt(page, 'map-first-native-timing', {sidecar_sha256: fixture.sidecar_sha256, frames, trace, frameFailures, distinct: firstForty, gaps, result});
    assert.deepEqual(frameFailures, [], 'every two-second frame satisfies the map, excerpt and running-control requirements');
  } finally {
    await mapFirstNativeReceipt(page, 'map-first-native-raw', {sidecar_sha256: fixture.sidecar_sha256, frames, frameFailures, trace: await page.evaluate(() => window.__mapFirstTrace)});
  }
});

test('map first native: requested viewports keep controls usable and real inspection holds until Resume', async t => {
  const fixture = mapFirstNativeFixture(), rows = [];
  for (const [width, height] of [[1280,800], [1428,771], [1360,900], [390,844]]) await t.test(`${width}x${height}`, async t => {
    const page = await mapFirstNativePage(t, {width, height});
    await page.waitForSelector('.au-stage-source-title[data-au-citation]');
    const running = await mapFirstNativeSnapshot(page);
    assertMapFirstNativeSnapshot(running, fixture);
    if (width > 1000) assert.ok(running.transport.controls.every(row => row.rect.top >= 0 && row.rect.bottom <= height + 1 && row.rect.left >= 0 && row.rect.right <= width + 1), 'all three running desktop controls are visible');
    const origin = page.locator('.au-stage-source-title[data-au-citation]'), pin = JSON.parse(await origin.getAttribute('data-au-citation'));
    await origin.click();
    await page.locator('.au-source-dialog[open] mark').waitFor();
    assert.equal(await page.locator('.au-source-dialog[open] mark').textContent(), pin.quote, 'inspection opens the exact complete native source pin');
    const held = await mapFirstNativeSnapshot(page);
    await page.locator('[data-au-close]').click();
    await page.waitForTimeout(1800);
    assert.equal((await mapFirstNativeSnapshot(page)).operation, held.operation, 'actual inspection remains paused after closing');
    await page.locator('[data-au-demo-resume]').click();
    await page.waitForFunction(prior => document.querySelector('[data-au-view]')?.dataset.auCurrentOperation !== prior, held.operation, {timeout: 10000});
    const started = Date.now();
    await page.locator('[data-au-operation-skip]').click();
    await page.waitForFunction(() => document.querySelector('[data-au-view]')?.dataset.auOperationResultVerified === 'true', null, {timeout: 15000});
    const result = await mapFirstNativeSnapshot(page);
    assert.equal(result.state_sha256, fixture.head.state.state_sha256);
    assert.equal(result.outcome, fixture.head.state.outcome.summary);
    assert.ok(Date.now() - started < 3000, 'Skip delivers the exact result without presentation dwell');
    assert.deepEqual(sorted(result.nodes.map(row => row.id)), sorted(fixture.head.state.graph.nodes.map(row => row.node_id)));
    assert.deepEqual(result.edges, fixture.head.state.graph.edges.map(row => ({id: row.edge_id, source: row.source_node_id, target: row.target_node_id})));
    assert.deepEqual(sorted(result.articles), ['259', '259a', '259d']);
    await page.locator('.au-work-controls [data-au-detail="activity"]').click();
    assert.equal(await page.locator('[data-au-inspect="operation"]').count(), fixture.operations.size, 'every checked native operation remains in History');
    const record = page.locator(`[data-au-inspect="operation"][data-au-record-id="${held.operation}"]`);
    await record.click();
    assert.deepEqual(JSON.parse(await page.locator('.au-record-dialog[open] pre').textContent()), fixture.operations.get(held.operation), 'History retains the exact checked operation, source pin and causes');
    await page.locator('[data-au-close-record]').click();
    rows.push({width, height, running, held, result, skip_ms: Date.now() - started});
    await mapFirstNativeReceipt(page, `map-first-native-controls-${width}x${height}`, {sidecar_sha256: fixture.sidecar_sha256, rows});
  });
});
