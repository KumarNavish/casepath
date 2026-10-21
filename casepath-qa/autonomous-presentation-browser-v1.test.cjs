'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {gunzipSync}=require('node:zlib'),{chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),load=name=>JSON.parse(gunzipSync(fs.readFileSync(path.join(__dirname,'fixtures',name+'.json.gz'))));
const wire=load('presentation-v1').responses,recorded=load('desk-v3');

test('the admitted six-act product uses one deterministic clock, preserves sources and handles pause',async()=>{
 const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_EXECUTABLE_PATH||(fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':chromium.executablePath())});
 const context=await browser.newContext({viewport:{width:1440,height:900},serviceWorkers:'block'}),page=await context.newPage(),errors=[],writes=[],missing=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url()),key=url.pathname+url.search;
  if(!['GET','HEAD'].includes(request.method())){writes.push(key);return route.abort();}
  if(request.isNavigationRequest())return route.fulfill({contentType:'text/html',body:'<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0"><main id="workspace"></main></body></html>'});
  if(/\/fonts\/[^/]+\.ttf$/.test(url.pathname))return route.fulfill({contentType:'font/ttf',path:path.join(root,'casepath/assets/fonts',path.basename(url.pathname))});
  const id=url.pathname.match(/\/claims\/([^/]+)\/operations$/)?.[1],record=id&&recorded.cases.find(row=>row.id===id);
  if(record)return route.fulfill({contentType:'application/x-ndjson',body:record.trace});
  if(wire[key])return route.fulfill({contentType:'application/json',body:JSON.stringify(wire[key])});
  missing.push(key);return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({detail:'No recorded fixture for '+key})});
 });
 try{
  await page.goto('http://localhost:41999/#autonomous/demonstration');
  await page.addStyleTag({path:path.join(root,'casepath/assets/autonomous-workspace-v1.css')});
  for(const asset of ['autonomous-language-v1.js','autonomous-presentation-v1.js','autonomous-workspace-v1.js'])await page.addScriptTag({path:path.join(root,'casepath/assets',asset)});
  await page.evaluate(()=>{window.product=CasePathAutonomous.mount(document.querySelector('#workspace'),{fetch:window.fetch.bind(window)});});
  await page.waitForFunction(()=>window.CasepathPresentation?.active,{},{timeout:45000});await page.evaluate(()=>document.fonts.ready);
  assert.deepEqual(errors,[]);assert.equal(await page.locator('[data-au-ns-start]').count(),1);assert.equal(await page.evaluate(()=>CasepathPresentation.active.time),0);
  await page.locator('[data-au-ns-start]').click();await page.waitForTimeout(50);assert.equal(await page.locator('[data-au-demo-stop]').count(),1);
  await page.locator('[data-au-demo-stop]').click();const at=await page.evaluate(()=>CasepathPresentation.active.time);await page.waitForTimeout(60);assert.equal(await page.evaluate(()=>CasepathPresentation.active.time),at);
  await page.locator('[data-au-demo-resume]').click();await page.waitForTimeout(60);assert.ok(await page.evaluate(()=>CasepathPresentation.active.time)>at);
  const proof=await page.evaluate(()=>{
   const active=CasepathPresentation.active,manifest=active.manifest,failures=[];
   for(const beat of manifest.beats){for(const at of [beat.start,beat.start+beat.duration/2,beat.end-.001]){active.advanceTo(at);const host=document.querySelector('[data-au-view]');if(document.getAnimations().length)failures.push('native motion');if(Number(host.dataset.auPresentationTime)!==at)failures.push('wrong clock');if(beat.act==='process'&&host.querySelector('[data-au-film-speed]').textContent!=='4×')failures.push('missing pace');}}
   active.seek(manifest.beats.find(b=>b.phase==='fact-rest').start);
   const fact=document.querySelector('[data-au-ns-fact]'),citation=JSON.parse(fact.dataset.auCitation);
   return {manifest,failures,citation,factOperation:fact.dataset.auNsFact,animations:document.getAnimations().length};
  });
  for(const beat of proof.manifest.beats){if(beat.operation){const bound=recorded.cases.find(c=>c.id===beat.claim)?.trace.trim().split('\n').map(JSON.parse).find(row=>row.id===beat.operation);assert.ok(bound,'recorded operation '+beat.operation);assert.equal(bound.seq,beat.seq);}}
  assert.deepEqual(proof.failures,[]);assert.deepEqual(proof.manifest.acts.map(a=>a.id),['customer','reading','process','decision','learning','cases']);
  const op=recorded.cases[0].trace.trim().split('\n').map(JSON.parse).find(row=>row.id===proof.factOperation);assert.deepEqual(proof.citation,op.source);
  await page.locator('[data-au-ns-fact]').first().click();await page.locator('dialog[open]').waitFor();assert.equal(await page.evaluate(()=>CasepathPresentation.active.paused),true);
  await page.keyboard.press('Escape');await page.locator('dialog[open]').waitFor({state:'detached'});await page.locator('[data-au-demo-resume]').click();
  await page.evaluate(()=>product.showWork());assert.equal(await page.evaluate(()=>Boolean(CasepathPresentation.active)),false);assert.equal(await page.locator('html[data-casepath-presentation]').count(),0);await page.evaluate(()=>product.destroy());
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);assert.deepEqual(missing,[],'all reads use frozen fixtures');
 }catch(error){error.message+='\nMissing fixture reads: '+JSON.stringify(missing)+'\nPage errors: '+JSON.stringify(errors)+'\nUI: '+(await page.locator('body').innerText()).slice(-1000);throw error;}
 finally{for(const close of [()=>page.close(),()=>context.close(),()=>browser.close()]){let timer;await Promise.race([close(),new Promise(resolve=>{timer=setTimeout(resolve,10000);})]);clearTimeout(timer);}}
});
