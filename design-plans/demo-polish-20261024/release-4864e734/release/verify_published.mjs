// Published-site check: two cold windows, nine demonstration histories, nine original
// histories, Knowledge, and the in-product executive film played in real time.
// Usage: node verify_published.mjs <expected-commit> <fresh-output-dir>
import fs from 'node:fs';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import path from 'node:path';
import {createRequire} from 'node:module';

const require = createRequire('/Users/kumar0002/Documents/Die Mobiliar/casepath-canonical/casepath-qa/package.json');
const {chromium} = require('playwright');
const frozenUI = require('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024/casepath/assets/autonomous-workspace-v1.js');
const [commit, out] = process.argv.slice(2);
assert.match(commit, /^[0-9a-f]{40}$/);
assert.equal(fs.existsSync(out), false, 'use a fresh output directory');
fs.mkdirSync(out, {recursive: true});
const SITE = 'https://casepath-autonomous.kumarnavish.chatgpt.site';
const PUBLIC_BUILD = '/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-sites-distribution-20261009/dist/client';
assert.equal(JSON.parse(fs.readFileSync(`${PUBLIC_BUILD}/deployment.json`, 'utf8')).source_commit, commit, 'public build identifies the expected canonical release');
const builtIndex = fs.readFileSync(path.join(PUBLIC_BUILD, 'index.html'), 'utf8');
const requiredStaticAssets = [...new Set([...builtIndex.matchAll(/<(?:script|link)\b[^>]*(?:src|href)="(assets\/[^"?]+\.(?:js|css))(?:\?[^"]*)?"[^>]*>/g)].map(match => '/' + match[1]))];
assert.ok(requiredStaticAssets.length > 0);
const expectedAssets = new Map();
function expectedAsset(pathname) {
  const decoded = decodeURIComponent(pathname);
  const file = path.resolve(PUBLIC_BUILD, '.' + decoded);
  assert.ok(file.startsWith(PUBLIC_BUILD + path.sep), 'asset belongs to the public build');
  assert.ok(fs.lstatSync(file).isFile(), 'expected asset is a regular file');
  if (!expectedAssets.has(file)) {
    const bytes = fs.readFileSync(file);
    expectedAssets.set(file, {bytes: bytes.length, sha256: crypto.createHash('sha256').update(bytes).digest('hex')});
  }
  return expectedAssets.get(file);
}
const DEMO = ['clm_314f2d309fea25e6', 'clm_4a07dbbbd859a3ce', 'clm_95d08975bc575592', 'clm_0f4f13b1e3e1328c', 'clm_393285577dcb12c4',
  'clm_4a53299cfe619303', 'clm_2c55cdd816b1d0e8', 'clm_543f08f2415b2a33', 'clm_7dbd7c7d1c4ddf90'];
const ORIGINALS = ['clm_0c5e7c7723a3c694', 'clm_2a9c260c26afaa34', 'clm_521c20913f4e0f9b', 'clm_7dbd7c7d1c4ddf90', 'clm_9a179a4481767d43',
  'clm_c44ddc0914ba9298', 'clm_e262801f9368bc12', 'clm_ee29ac770b1bf7b9', 'clm_f69b1747447bc221'];
const EXPECTED_TITLES = Object.fromEntries([...new Set([...DEMO, ...ORIGINALS])].map(id => {
  const title = frozenUI.caseLabel(id).primary;
  assert.ok(typeof title === 'string' && title.length > 0 && title !== id, 'case has a frozen display identity: ' + id);
  return [id, title];
}));
assert.equal(new Set(Object.values(EXPECTED_TITLES)).size, Object.keys(EXPECTED_TITLES).length, 'case titles uniquely identify the requested cases');
const report = {site: SITE, expected_commit: commit, expected_case_titles: EXPECTED_TITLES, started_utc: new Date().toISOString(), windows: []};
const {audit}=await import('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024/design-plans/tools/desktop_overlap_audit.mjs');
const {auditPresentation}=await import('/Users/kumar0002/Documents/Die Mobiliar/.work/casepath-commander-demo-polish-clone-20261024/design-plans/w9-20261021/audit_presentation.mjs');
const browser = await chromium.launch({executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
report.browser = browser.version();
try {

async function window_(name, viewport, steps) {
  // A fresh context has an empty cache, cookie jar and storage: a cold window.
  const context = await browser.newContext({viewport, serviceWorkers: 'block', locale: 'en-GB'});
  const page = await context.newPage();
  const row = {name, viewport, errors: [], writes: [], failed_requests: [], api_requests: 0, cases: [], edge_beacons: []};
  report.windows.push(row);
  const assetReads = [], observedAssets = new Map();
  function observeAsset(response) {
    const url = new URL(response.url()), type = response.request().resourceType();
    if (url.origin !== SITE || !url.pathname.startsWith('/assets/') || !['script', 'stylesheet'].includes(type)) return;
    assetReads.push((async () => {
      assert.equal(response.status(), 200, 'loaded asset returned HTTP 200: ' + url.pathname);
      const expected = expectedAsset(url.pathname), body = await response.body();
      const sha256 = crypto.createHash('sha256').update(body).digest('hex');
      assert.equal(body.length, expected.bytes, 'loaded asset byte length: ' + url.pathname);
      assert.equal(sha256, expected.sha256, 'loaded asset digest: ' + url.pathname);
      const previous = observedAssets.get(url.href);
      observedAssets.set(url.href, {url: url.href, pathname: url.pathname, type, sha256, bytes: body.length, observations: (previous?.observations || 0) + 1});
    })().catch(error => { row.errors.push('served-asset: ' + error.message); }));
  }
  page.on('response', observeAsset);
  page.on('pageerror', e => row.errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') row.errors.push('console: ' + m.text()); });
  page.on('requestfailed', r => row.failed_requests.push(r.method() + ' ' + r.url() + ' ' + r.failure()?.errorText));
  page.on('request', r => { if (new URL(r.url()).pathname.startsWith('/api/')) row.api_requests++; });
  await page.route('**/*', route => {
    const r = route.request();
    if (!['GET', 'HEAD'].includes(r.method())) { const u=new URL(r.url()); if(u.origin===SITE && u.pathname.startsWith('/cdn-cgi/')) {row.edge_beacons.push(r.method()+' '+u.pathname); return route.continue();} row.writes.push(r.method() + ' ' + u.origin+u.pathname); return route.abort(); }
    return route.continue();
  });
  await page.addInitScript(()=>{window.__cold=[];let previous='';function sample(){const v=document.querySelector('[data-au-ns]')?'northstar':document.querySelector('[data-au-agent-desk]')?'interim-desk':document.querySelector('[data-au-claim-title]')?'claim':'loading';if(v!==previous){window.__cold.push({ms:performance.now(),view:v});previous=v;}if(!window.__coldDone)requestAnimationFrame(sample);}requestAnimationFrame(sample);});
  const t0 = Date.now();
  await page.goto(SITE + '/', {waitUntil: 'domcontentloaded'});
  row.dom_ms = Date.now() - t0;
  // The root opens the Demonstration on its first recorded case; Cases is one hash away.
  await page.waitForSelector('[data-au-claim-title]', {timeout: 90000});
  row.first_content_ms = Date.now() - t0;
  if(viewport.width>=1000)await page.waitForSelector('[data-au-ns]',{timeout:90000});
  row.cold_timeline=await page.evaluate(()=>{window.__coldDone=true;return window.__cold;});
  if(viewport.width>=1000)assert.ok(!row.cold_timeline.some(x=>['interim-desk','claim'].includes(x.view)),'no older desk during cold landing');
  row.landing = await page.evaluate(() => ({hash: location.hash, title: document.querySelector('[data-au-claim-title]')?.textContent.trim()}));
  await page.screenshot({path: `${out}/${name}-landing.png`});
  await page.evaluate(() => { location.hash = '#autonomous/cases'; });
  await page.waitForSelector('[data-au-claim-row]', {timeout: 90000});
  row.cases_visible_ms = Date.now() - t0;
  row.case_rows = await page.locator('[data-au-claim-row]').count();
  row.deployment = await page.evaluate(() => fetch('/deployment.json', {cache: 'no-store'}).then(r => r.json()));
  row.home_overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  await page.screenshot({path: `${out}/${name}-home.png`});
  await steps(page, row);
  page.off('response', observeAsset);
  await Promise.all(assetReads);
  row.served_assets = [...observedAssets.values()].sort((a,b) => a.url.localeCompare(b.url));
  assert.ok(row.served_assets.some(asset => asset.pathname === '/assets/autonomous-workspace-v1.js'), 'the actual workspace script was verified');
  assert.ok(row.served_assets.some(asset => asset.type === 'stylesheet'), 'actual stylesheets were verified');
  const observedPaths = new Set(row.served_assets.map(asset => asset.pathname));
  assert.ok(requiredStaticAssets.every(name => observedPaths.has(name)), 'all initial scripts and styles were actually served');
  row.required_static_assets = requiredStaticAssets;
  row.review_assets = [];
  for (const pathname of ['/assets/review-northstar-v1.js', '/assets/review-northstar-v1.css']) {
    const expected = expectedAsset(pathname);
    const response = await context.request.get(SITE + pathname + '?sha256=' + expected.sha256);
    assert.equal(response.status(), 200, pathname);
    const bytes = await response.body(), sha256 = crypto.createHash('sha256').update(bytes).digest('hex');
    assert.equal(sha256, expected.sha256); assert.equal(bytes.length, expected.bytes);
    row.review_assets.push({pathname, sha256, bytes:bytes.length, method:'GET'});
  }
  await context.close();
}

function auditMobileDocumentRows() {
  const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
  return [...document.querySelectorAll('.au-quiet-claim .au-stage-thumbnail')].filter(e=>e.getClientRects().length).map(e=>{
    const n=e.querySelector(':scope > .au-stage-source-name'),s=e.querySelector(':scope > .au-stage-source-check');
    if(!n||!s)return null;
    const a=rect(n),b=rect(s),c=rect(e);
    const overlap=a.x<b.right&&a.right>b.x&&a.y<b.bottom&&a.bottom>b.y;
    const gap=b.x-a.right,contained=b.x>=c.x-.5&&b.right<=c.right+.5&&b.y>=c.y-.5&&b.bottom<=c.bottom+.5;
    const accessible=e.getAttribute('aria-label')?.startsWith(n.textContent);
    return {name:n.textContent,status:s.textContent,nameRect:a,statusRect:b,buttonRect:c,gap,overlap,
      passed:!overlap&&gap>=11.5&&contained&&c.height>=43.5&&n.clientWidth>0&&getComputedStyle(n).overflow==='hidden'&&accessible};
  }).filter(Boolean);
}

async function openCase(page, row, id, group) {
  const t0 = Date.now();
  await page.goto(SITE+'/?release_readback='+encodeURIComponent(group+'-'+id)+'#autonomous/claim/'+id,{waitUntil:'domcontentloaded'});
  let state = 'timeout';
  try {
    await page.waitForFunction(({id, primary}) => {
      const status = document.querySelector('[data-au-desk-trace-status]:not([hidden])')?.textContent || '';
      if (/could not be opened/i.test(status) || /could not|unavailable/i.test(document.querySelector('.au-global-status')?.textContent || '')) return true;
      const title = document.querySelector('[data-au-claim-title]')?.textContent?.trim();
      const legacyDesk = document.querySelector('[data-au-agent-desk]') && !document.querySelector('[data-au-ns]');
      const expectedTitle = legacyDesk ? primary.replace(/\brecord\b/giu, 'documents') : primary;
      return title === expectedTitle && !document.querySelector('[data-au-desk-loading]') && location.hash.includes(id);
    }, {id, primary: EXPECTED_TITLES[id]}, {timeout: 60000});
    state = 'rendered';
  } catch { /* recorded below */ }
  const seen = await page.evaluate(() => ({
    title: document.querySelector('[data-au-claim-title]')?.textContent?.trim() || null,
    status: [...document.querySelectorAll('[data-au-desk-trace-status]:not([hidden]),.au-global-status,[data-au-claim-status]')].map(e => e.textContent.trim()).filter(Boolean).join(' | ').slice(0, 300),
    view: document.querySelector('[data-au-ns]') ? 'northstar-desk' : document.querySelector('[data-au-agent-desk]') ? 'desk' : document.querySelector('.au-quiet-claim') ? 'claim' : 'other',
    outcome: document.querySelector('.au-stage-outcome > p, .au-assessment-conclusion p, .au-desk-answer p')?.textContent?.trim().slice(0, 300) || null,
    overflow: document.documentElement.scrollWidth > innerWidth + 1,
  }));
  const expectedTitle = seen.view === 'desk' ? EXPECTED_TITLES[id].replace(/\brecord\b/giu, 'documents') : EXPECTED_TITLES[id];
  const titleIdentityOk = seen.title === expectedTitle;
  if (/could not|unavailable/i.test(seen.status) || !seen.title || seen.view==='other' || !titleIdentityOk) state = 'failed';
  const shot = `${out}/${row.name}-${group}-${id}.png`;
  await page.screenshot({path: shot});
  const overlaps=seen.view==='northstar-desk'?await page.evaluate(audit):[];
  const mobileDocuments=row.viewport.width<=700?await page.evaluate(auditMobileDocumentRows):[];
  row.cases.push({group, id, state, ms: Date.now() - t0, ...seen, expected_title: expectedTitle, title_identity_ok: titleIdentityOk, overlaps, mobileDocuments});
}

await window_('cold-a-desktop-1440x900', {width: 1440, height: 900}, async (page, row) => {
  for (const id of DEMO) await openCase(page, row, id, 'demo');
  for (const id of ORIGINALS) await openCase(page, row, id, 'original');
  await page.evaluate(() => { location.hash = '#autonomous/knowledge'; });
  await page.waitForSelector('[data-au-knowledge-identity]', {timeout:90000});
  await page.waitForFunction(()=>!document.querySelector('[data-au-knowledge-error]'),undefined,{timeout:90000});
  row.knowledge = await page.evaluate(() => ({identities:document.querySelectorAll('[data-au-knowledge-identity]').length, error:document.querySelector('[data-au-knowledge-error]')?.dataset.auKnowledgeError||null, text: document.querySelector('[data-au-view]')?.innerText.slice(0, 400), overflow: document.documentElement.scrollWidth > innerWidth + 1}));
  await page.screenshot({path: `${out}/${row.name}-knowledge.png`});
  assert.ok(row.knowledge.identities>0&&!row.knowledge.error&&!row.knowledge.overflow,'Knowledge loaded without errors or overflow');
});

await window_('cold-b-mobile-390x844', {width: 390, height: 844}, async (page, row) => {
  for (const id of DEMO) await openCase(page, row, id, 'demo');
});

// The executive film lives in the product: play it hands-free in real time at 1440x900.
{
  const recordingRequestedAt = Date.now();
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, serviceWorkers: 'block', reducedMotion: 'no-preference', recordVideo: {dir: path.join(out, 'film-recording'), size: {width: 1440, height: 900}}});
  const page = await context.newPage();
  const filmVideo = page.video();
  assert.ok(filmVideo, 'continuous published film recording exists');
  const film = {recording_requested_at: new Date(recordingRequestedAt).toISOString(), source_commit: commit, viewport: {width: 1440, height: 900}, errors: [], writes: [], samples: [], edge_beacons: []};
  report.film=film;
  page.on('pageerror', e => film.errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') film.errors.push(m.text()); });
  await page.route('**/*', route => {const r=route.request(),u=new URL(r.url());if(['GET','HEAD'].includes(r.method()))return route.continue();if(u.origin===SITE&&u.pathname.startsWith('/cdn-cgi/')){film.edge_beacons.push(r.method()+' '+u.pathname);return route.continue();}film.writes.push(r.method()+' '+u.origin+u.pathname);return route.abort();});
  await page.goto(SITE + '/?present=1#autonomous/demonstration');
  await page.waitForFunction(() => window.CasepathPresentation?.active, undefined, {timeout: 120000});
  film.playback_first_observed_at = new Date().toISOString();
if(await page.locator('[data-au-ns-start]').count())await page.locator('[data-au-ns-start]').click();
  film.duration_ms = await page.evaluate(() => CasepathPresentation.active.manifest.duration);
  const t0 = Date.now();
  let n = 0;
  while (Date.now() - t0 < film.duration_ms + 20000) {
    const s = await page.evaluate(() => {
      const a = CasepathPresentation.active, host = document.querySelector('[data-au-view]');
      return {t: a ? Math.round(a.time) : null, beat: host?.dataset.auPresentationBeat ?? null,
        act: a ? a.manifest.beats[Number(host?.dataset.auPresentationBeat)]?.act ?? null : null,
        four_x: [...document.querySelectorAll('body *')].some(e => e.children.length === 0 && e.textContent.trim() === '4×' && e.getClientRects().length),
        heading: document.querySelector('h1')?.textContent?.trim().slice(0, 80) || null};
    });
    s.overlaps=await page.evaluate(auditPresentation);film.samples.push(s);
    if (n % 8 === 0) await page.screenshot({path: `${out}/film-${String(n).padStart(3, '0')}.png`});
    n++;
    if (s.t !== null && s.t >= film.duration_ms) break;
    await page.waitForTimeout(1500);
  }
  film.wall_ms = Date.now() - t0;
  film.playback_observed_end_at = new Date().toISOString();
  film.reached_end = film.samples.at(-1)?.t >= film.duration_ms;
  film.acts_seen = [...new Set(film.samples.map(s => s.act).filter(Boolean))];
  film.four_x_seen = film.samples.some(s => s.four_x);
  await page.screenshot({path: `${out}/film-end.png`});
  report.film = film;
  await context.close();
  film.video_path = path.join(out, 'public-walkthrough.webm');
  await filmVideo.saveAs(film.video_path);
  const filmBytes = fs.readFileSync(film.video_path);
  assert.ok(filmBytes.length > 10000, 'continuous film contains recorded frames');
  film.video_sha256 = crypto.createHash('sha256').update(filmBytes).digest('hex');
  film.video_bytes = filmBytes.length;
}
const {verifySupplement}=await import('./verify_supplement.mjs');
report.supplement=await verifySupplement(browser,SITE,out);
}catch(error){if(error.supplement)report.supplement=error.supplement;report.failure=String(error);throw error;}finally{await browser.close();report.cleanup={browser_closed:!browser.isConnected()};report.finished_utc=new Date().toISOString();fs.writeFileSync(`${out}/published-verification.json`,JSON.stringify(report,null,2)+'\n');}
report.finished_utc = new Date().toISOString();
fs.writeFileSync(`${out}/published-verification.json`, JSON.stringify(report, null, 2) + '\n');
const summary = {
  windows: report.windows.map(w => ({name: w.name, commit_ok: w.deployment?.source_commit === commit, cases_visible_ms: w.cases_visible_ms,
    rendered: w.cases.filter(c => c.state === 'rendered').length, total: w.cases.length, identity_failures: w.cases.filter(c => !c.title_identity_ok).length, errors: w.errors.length, writes: w.writes.length,
    overflow: w.home_overflow || w.cases.some(c => c.overflow), served_assets_verified: w.served_assets?.length || 0, required_static_assets_verified: w.required_static_assets?.length || 0, review_assets_verified:w.review_assets?.length || 0,
    mobile_document_rows:w.cases.reduce((n,c)=>n+c.mobileDocuments.length,0), mobile_document_failures:w.cases.reduce((n,c)=>n+c.mobileDocuments.filter(r=>!r.passed).length,0)})),
  film: {recorded_video: !!report.film.video_sha256, video_sha256: report.film.video_sha256, duration_ms: report.film.duration_ms, reached_end: report.film.reached_end, acts: report.film.acts_seen, four_x: report.film.four_x_seen, errors: report.film.errors.length, writes: report.film.writes.length},
};
fs.writeFileSync(`${out}/summary.json`, JSON.stringify(summary, null, 2) + '\n');
console.log(JSON.stringify(summary, null, 1));

assert.ok(summary.windows.every(w=>w.commit_ok&&w.rendered===w.total&&!w.identity_failures&&!w.errors&&!w.writes&&!w.overflow&&w.served_assets_verified>0));
assert.ok(report.windows.every(w=>w.cases.every(c=>!c.overlaps.length)));
assert.ok(report.windows.filter(w=>w.viewport.width<=700).every(w=>w.cases.every(c=>c.mobileDocuments.length>0&&c.mobileDocuments.every(r=>r.passed))),'all published mobile document names/statuses are separate and accessible');
assert.ok(report.film.four_x_seen,'published accelerated process visibly shows 4×');assert.equal(report.film.duration_ms,88050);assert.ok(report.film.reached_end);assert.equal(report.film.errors.length,0);assert.equal(report.film.writes.length,0);assert.ok(report.film.samples.every(s=>!s.overlaps.length));assert.equal(report.film.acts_seen.length,6);

