'use strict';
// Exact independent native loader/lifecycle check used for the final evidence.
// Run from the task clone with the prepared Node/Playwright runtime.
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const {createHash} = require('crypto');
const {chromium} = require('playwright');
const repo = process.cwd();
const api = '/api/claim-loops/v1/autonomous';
const id = 'clm_314f2d309fea25e6';
const fixture = JSON.parse(fs.readFileSync('/tmp/casepath-reference-native-85a-fixture.json', 'utf8'));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const files = ['casepath/index.html', 'casepath/assets/autonomous-entry-v1.js', 'casepath/assets/autonomous-workspace-v1.js', 'casepath/assets/autonomous-workspace-v1.css'];
const assets = new Map(files.map(file => [file, fs.readFileSync(file)]));
assert.equal(hash(assets.get(files[1])), '297350135d60467afc7bdeff0f9389594014549d6acbe5b4b940211cd81223b8');
assert.equal(hash(assets.get(files[2])), '2672ee416edb88ccbff7cd41619899f91b8a9c9d4a0ebdf175dfbfb6a53e36ea');
const evidence = {mode:'actual index/native entry public synthetic GET fixture; BFCache enabled', hashes:Object.fromEntries([...assets].map(([file, bytes]) => [file, hash(bytes)])), runs:[]};
async function main() {
  const browser = await chromium.launch({executablePath:'/usr/bin/chromium', headless:true, args:['--no-sandbox'], ignoreDefaultArgs:['--disable-back-forward-cache']});
  try {
    for (const fragment of [`#autonomous/claim/${id}?collection=reference&mode=replay&through=18&detail=sources`, '#autonomous/demonstration?mode=replay']) {
      const context = await browser.newContext({serviceWorkers:'block'});
      const page = await context.newPage();
      const calls = [], errors = [], shows = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.exposeFunction('reviewPageShow', row => shows.push(row));
      await page.addInitScript(() => addEventListener('pageshow', event => void window.reviewPageShow({persisted:event.persisted, path:location.pathname})));
      await page.clock.install({time:new Date('2026-10-13T12:00:00Z')});
      await page.clock.pauseAt(new Date('2026-10-13T12:00:00Z'));
      await page.route('**/*', async route => {
        const url = new URL(route.request().url()), name = decodeURIComponent(url.pathname);
        calls.push({path:name + url.search, method:route.request().method()});
        assert.equal(route.request().method(), 'GET');
        if (name === '/away') {
          await route.fulfill({status:200, contentType:'text/html', body:'<!doctype html><title>Away</title><p>away</p>'});
          return;
        }
        if (name.startsWith(api)) {
          const suffix = name.slice(api.length), match = suffix.match(/^\/claims\/([^/]+)(?:\/(snapshot|replay|events))?$/);
          const data = suffix === '/claims' ? {claims:Object.values(fixture.snapshots).map(row => ({...row.state, origin:'canonical_original'})), total:9}
            : suffix === '/knowledge' ? fixture.knowledge
            : suffix === '/status' ? {enabled:true, provider_ready:false, read_only:true, writable:false, limits:{}}
            : match ? match[2] === 'replay' ? fixture.prefixes[match[1]]?.[Number(url.searchParams.get('through_seq') || 0)] : fixture.snapshots[match[1]] : null;
          await route.fulfill({status:data ? 200 : 404, contentType:'application/json', body:JSON.stringify(data || {detail:'Synthetic GET unavailable'})});
          return;
        }
        const file = 'casepath/' + (name === '/' ? 'index.html' : name.slice(1));
        let body = assets.get(file);
        if (!body && !file.includes('..') && fs.existsSync(path.join(repo, file))) body = fs.readFileSync(path.join(repo, file));
        if (!body) { await route.fulfill({status:404, body:'Unavailable'}); return; }
        if (file === 'casepath/index.html') body = Buffer.from(body.toString().replace('<head>', '<head><script>window.CASEPATH_PUBLIC_READ_ONLY=true;window.CASEPATH_HOSTED_AUTONOMOUS=true;</script>'));
        await route.fulfill({status:200, contentType:{'.html':'text/html', '.js':'application/javascript', '.css':'text/css', '.ttf':'font/ttf', '.json':'application/json'}[path.extname(file)] || 'application/octet-stream', body});
      });
      await page.goto('http://native-entry.invalid/' + fragment);
      await page.locator('[data-au-revision]').waitFor();
      const sample = () => page.evaluate(() => ({hash:location.hash, revision:Number(document.querySelector('[data-au-revision]')?.dataset.auRevision), state_sha256:document.querySelector('[data-au-state-sha]')?.dataset.auStateSha, nav:document.querySelector('.au-nav [aria-current]')?.dataset.auNav, panel:document.querySelector('[data-au-context]')?.dataset.auContext, play:!!document.querySelector('[data-au-demo-play]'), pause:!!document.querySelector('[data-au-demo-stop]'), resume:!!document.querySelector('[data-au-demo-resume]'), workspaceLength:document.querySelector('#autonomousWorkspace').innerHTML.length, hidden:document.hidden}));
      if (fragment.startsWith('#autonomous/demonstration')) { await page.clock.runFor(4100); await new Promise(resolve => setTimeout(resolve, 30)); }
      const before = await sample();
      assert.equal(before.nav, 'demonstration');
      assert.equal(before.state_sha256, fixture.prefixes[id][before.revision].state.state_sha256);
      await page.evaluate(() => addEventListener('pagehide', event => sessionStorage.setItem('casepath-review-lifecycle', JSON.stringify({persisted:event.persisted, workspaceLength:document.querySelector('#autonomousWorkspace')?.innerHTML.length, revision:document.querySelector('[data-au-revision]')?.dataset.auRevision, resume:!!document.querySelector('[data-au-demo-resume]')}))));
      await page.goto('http://native-entry.invalid/away');
      await page.goBack({waitUntil:'commit', timeout:3000});
      await new Promise(resolve => setTimeout(resolve, 70));
      const restored = await sample();
      assert.ok(shows.some(show => show.path === '/' && show.persisted === true));
      assert.equal(restored.revision, before.revision);
      assert.equal(restored.state_sha256, before.state_sha256);
      assert.equal(restored.hash, before.hash);
      assert.equal(restored.nav, 'demonstration');
      assert.equal(restored.panel, before.panel);
      assert.ok(restored.workspaceLength > 0);
      const persistedHide = await page.evaluate(() => JSON.parse(sessionStorage.getItem('casepath-review-lifecycle')));
      assert.equal(persistedHide.persisted, true);
      await page.clock.runFor(9000);
      await new Promise(resolve => setTimeout(resolve, 30));
      const held = await sample();
      assert.equal(held.revision, before.revision);
      if (fragment.startsWith('#autonomous/demonstration')) {
        assert.equal(restored.resume, true);
        await page.locator('[data-au-demo-resume]').click();
        await page.clock.runFor(4100);
        await new Promise(resolve => setTimeout(resolve, 30));
        assert.ok((await sample()).revision > held.revision);
      }
      await page.reload();
      await page.locator('[data-au-revision]').waitFor();
      const departure = await page.evaluate(() => JSON.parse(sessionStorage.getItem('casepath-review-lifecycle'))), reloaded = await sample();
      assert.equal(departure.persisted, false);
      assert.equal(departure.workspaceLength, 0);
      assert.equal(reloaded.nav, 'demonstration');
      assert.deepEqual(errors, []);
      assert.equal(calls.some(call => call.method !== 'GET' || call.path === '/api/demo'), false);
      evidence.runs.push({fragment, before, shows, persistedHide, restored, held, departure, reloaded, calls, errors});
      await context.close();
    }
  } finally { await browser.close(); }
  fs.writeFileSync('/tmp/casepath-replay-entry-independent-review-20261013/actual-index-bfcache-fixed.json', JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
